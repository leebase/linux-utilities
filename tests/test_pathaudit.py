"""Contract tests for the pathaudit vertical slice.

Encodes docs/pathaudit-contract.md. Builds src/pathaudit.c into a test-owned
temporary directory, exercises only deterministic temporary fixtures, and never
inspects the worker's ambient PATH for discovery, requires root, uses the
network, or leaves binaries in the workspace. Child processes receive a
controlled environment: explicit-root cases seal PATH against search, while
`--path` and `--command` cases set or unset PATH deliberately. Sanitizer/Valgrind
options declared by Makefile memory gates are allowlist-forwarded into the child
environment.

Also encodes the stable Makefile contract for pathaudit-sanitize and
pathaudit-valgrind: ASan+UBSan with strict warnings and frame pointers, a
separate non-sanitized Valgrind debug binary with full leak checking and a
nonzero error-exitcode, temporary paths under /tmp cleaned on every exit, and
regression pins for existing pathaudit behavior and Make targets.

Command-query coverage (`pathaudit --command NAME`) encodes MATCH lines in
PATH order for one basename, applicable existing PATH hazards only, and no
unrelated benign basename-collision flood.

Non-directory PATH entry coverage (`pathaudit --path`) pins that an existing
PATH component which is not a directory (regular file, symlink-to-file,
ENOTDIR) reports `NON_DIRECTORY_ROOT` with exit status 1 while preserving
usable directories, missing entries, empty components, ordering, and duplicates.

Executable-shadowing coverage (`pathaudit --path`) pins that a command basename
present as a regular executable in two or more distinct PATH directories yields
`SHADOWED` lines naming the command, the first-PATH winner realpath, and each
later *distinct* shadowed executable realpath. Exact duplicate
`(command, winner, shadow)` tuples are emitted once; repeated identical
non-winner realpaths must not append the same row again. Non-executables and
distinct command names never produce `SHADOWED`.

Writable resolved-executable coverage pins that `--path` and `--command` apply
the existing trust model to final executable targets resolved through PATH:
owner-only write modes stay silent, `S_IWGRP` / `S_IWOTH` reuse
`GROUP_WRITABLE` / `WORLD_WRITABLE` on the executable realpath, symlink
resolution follows the final target, and unsafe inspection stays reject-closed
via `INSPECTION_ERROR_N`. Explicit-root mode still does not search executables.

Unsafe ownership coverage pins that `--path` and `--command` apply one shared
trust policy to resolved executables, each usable PATH directory entry, and
every ancestor directory through `/`: emit `UNSAFE_OWNER` naming the canonical
offending realpath when final-target `st_uid` is neither root UID 0 nor the
invoking real user from `getuid`. Current-user and root ownership are trusted;
foreign ownership is unsafe. Symlink resolution uses the final target. Shared
ancestor realpaths are deduplicated to the lowest PATH index that observed
them. Ownership findings interact with `GROUP_WRITABLE` / `WORLD_WRITABLE`
under the shared code rank, exit status 1, and deterministic ordering. A
trusted executable reached only through an unsafe PATH directory or unsafe
ancestor must still report that directory ownership gap. Explicit-root mode
never searches executables and remains ownership-blind. Fixture helpers may
observe untrusted ancestors of the temporary tree without privileged `chown`;
optional foreign-owner plants inside the test tree skip honestly when the host
cannot establish a distinct owner.

Hostile-PATH regression coverage pins security-sensitive malformed and
adversarial `PATH` shapes already supported by the utility: empty components,
nonexistent directories, duplicate entries, and deterministic finding order.
Fixtures plant attacker-controlled executable-looking files that would leave a
side-effect marker if executed; the scanner must classify PATH components
without ever running those plants. The same corpus also pins that hostile PATH
component text carrying control characters and terminal-escape sequences reaches
stdout findings and stderr diagnostics only in quote-escaped printable form:
single-line, unambiguous, and free of raw terminal-control effects.
"""

from __future__ import annotations

import errno as errno_mod
import os
import pwd
import re
import shutil
import stat as stat_mod
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pathaudit.c"
MAKEFILE = ROOT / "Makefile"

# Stable pathaudit-only memory-verification Make targets (authored ahead of the
# Makefile recipes that must satisfy this contract).
PATHAUDIT_SANITIZE_TARGET = "pathaudit-sanitize"
PATHAUDIT_VALGRIND_TARGET = "pathaudit-valgrind"
STRICT_WARNING_FLAGS = (
    "-std=c17",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
)
FRAME_POINTER_FLAG = "-fno-omit-frame-pointer"

# Allowlisted sanitizer/runtime knobs forwarded from the ambient environment so
# Makefile memory gates (ASAN_OPTIONS / UBSAN_OPTIONS) reach the binary under
# test without re-opening PATH to ambient search.
SANITIZER_ENV_KEYS = (
    "ASAN_OPTIONS",
    "UBSAN_OPTIONS",
    "LSAN_OPTIONS",
    "ASAN_SYMBOLIZER_PATH",
)

USAGE_SYNOPSIS = (
    b"usage: pathaudit [--] ROOT...\n"
    b"   or: pathaudit --path\n"
    b"   or: pathaudit --command NAME\n"
)
HELP_STDOUT = (
    b"usage: pathaudit [--] ROOT...\n"
    b"   or: pathaudit --path\n"
    b"   or: pathaudit --command NAME\n"
    b"Scan PATH directory roots for hazards.\n"
)
VERSION_STDOUT = b"pathaudit 0.1.0\n"
# Retained alias: usage diagnostics append the synopsis.
USAGE_LINE = USAGE_SYNOPSIS

CODE_RANK = (
    "EMPTY_ROOT",
    "RELATIVE_ROOT",
    "MISSING_ROOT",
    "NON_DIRECTORY_ROOT",
    "GROUP_WRITABLE",
    "WORLD_WRITABLE",
    "UNSAFE_OWNER",
)
CODE_RANK_INDEX = {code: index for index, code in enumerate(CODE_RANK)}

# Directory-root taxonomy under `--path` / `--command`, including UNSAFE_OWNER
# for PATH entries and ancestors. Explicit-root mode stays ownership-blind and
# never emits UNSAFE_OWNER even when the same codes apply for writability.
DIRECTORY_CODE_RANK = CODE_RANK
# Historical name: ownership is no longer executable-only under `--path` /
# `--command` (directories and ancestors share the same UNSAFE_OWNER code).
EXECUTABLE_ONLY_CODES = frozenset()

MAX_ROOT_COUNT = 65536
MAX_ROOT_LENGTH = 65536
MAX_ROOT_BYTES = 1024 * 1024

# Controllable mode bits for the shared writability trust model.
# Directory and regular-file targets share the same write bits: group/other
# write is untrusted; owner write alone is trusted. Ownership is a separate
# additive check (UNSAFE_OWNER) on final-target st_uid for executables, PATH
# directories, and ancestors through /.
MODE_PRIVATE = 0o700
MODE_GROUP_WRITABLE = 0o720
MODE_WORLD_WRITABLE = 0o702
MODE_BOTH_WRITABLE = 0o722
# Trusted executable default: owner rwx, group/other rx, no group/other write.
MODE_EXE_TRUSTED = 0o755


def escape_root(root: bytes | str | os.PathLike[str]) -> bytes:
    """Quote-escape an operand the way pathaudit must emit it."""

    if isinstance(root, bytes):
        data = root
    else:
        data = os.fsencode(os.fspath(root))
    out = bytearray(b'"')
    for byte in data:
        if byte == ord('"'):
            out.extend(b'\\"')
        elif byte == ord("\\"):
            out.extend(b"\\\\")
        elif 0x20 <= byte <= 0x7E:
            out.append(byte)
        else:
            out.extend(f"\\x{byte:02X}".encode("ascii"))
    out.append(ord('"'))
    return bytes(out)


def finding_line(code: str, root: bytes | str | os.PathLike[str]) -> bytes:
    if code not in CODE_RANK_INDEX:
        raise ValueError(f"unknown hazard code: {code}")
    return f"{code}\t".encode("ascii") + escape_root(root) + b"\n"


def match_line(exe: bytes | str | os.PathLike[str]) -> bytes:
    """One command-query MATCH record for an executable candidate."""

    return b"MATCH\t" + escape_root(exe) + b"\n"


def findings_stdout(
    items: list[tuple[str, bytes | str | os.PathLike[str]]],
) -> bytes:
    """Build expected stdout for (code, root) pairs already in contract order."""

    return b"".join(finding_line(code, root) for code, root in items)


def command_query_stdout(
    matches: list[bytes | str | os.PathLike[str]],
    findings: list[tuple[str, bytes | str | os.PathLike[str]]] | None = None,
) -> bytes:
    """MATCH lines in PATH order, then applicable hazard findings."""

    body = b"".join(match_line(exe) for exe in matches)
    if findings:
        body += findings_stdout(findings)
    return body


def shadowed_line(
    command: bytes | str,
    winner: bytes | str | os.PathLike[str],
    shadow: bytes | str | os.PathLike[str],
) -> bytes:
    """One executable-shadowing record: command, first-PATH winner, shadowed path."""

    return (
        b"SHADOWED\t"
        + escape_root(command)
        + b"\t"
        + escape_root(winner)
        + b"\t"
        + escape_root(shadow)
        + b"\n"
    )


def shadowing_stdout(
    items: list[
        tuple[
            bytes | str,
            bytes | str | os.PathLike[str],
            bytes | str | os.PathLike[str],
        ]
    ],
) -> bytes:
    """Build expected stdout for SHADOWED triples already in contract order."""

    return b"".join(
        shadowed_line(command, winner, shadow)
        for command, winner, shadow in items
    )


def install_executable(
    directory: Path, name: str, mode: int = MODE_EXE_TRUSTED
) -> Path:
    """Create a regular executable basename under directory; return resolved path.

    Default mode is writability-trusted (no group/other write). Pass
    MODE_GROUP_WRITABLE, MODE_WORLD_WRITABLE, or MODE_BOTH_WRITABLE to plant an
    untrusted write mode. Ownership defaults to the creating UID (trusted when
    that UID is the invoking real user); use the ownership helpers below to
    plant root-owned or foreign-owned targets inside the fixture tree.
    """

    path = directory / name
    path.write_bytes(b"#!/bin/sh\nexit 0\n")
    os.chmod(path, mode)
    return path.resolve()


def _foreign_uid_candidates() -> list[int]:
    """UIDs distinct from root and the invoking real user (no host paths)."""

    me = os.getuid()
    seen: set[int] = set()
    ordered: list[int] = []
    for entry in pwd.getpwall():
        uid = int(entry.pw_uid)
        if uid in (0, me) or uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)
    # Common nobody/nfsnobody-style IDs even when absent from passwd.
    for uid in (65534, 65533, 99, 65535, 1, 2):
        if uid in (0, me) or uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)
    return ordered


def _try_set_owner(path: Path, uid: int) -> bool:
    """Return True only when path's final st_uid equals uid after chown."""

    try:
        os.chown(path, uid, -1)
    except OSError:
        return False
    try:
        return path.stat().st_uid == uid
    except OSError:
        return False


def require_root_owned_executable(
    directory: Path, name: str, mode: int = MODE_EXE_TRUSTED
) -> Path:
    """Install an executable owned by UID 0; skip if the host cannot establish it."""

    exe = install_executable(directory, name, mode=mode)
    if exe.stat().st_uid == 0:
        return exe
    if not _try_set_owner(exe, 0):
        pytest.skip(
            "host cannot establish root ownership for a trusted-owner fixture"
        )
    return exe


def require_foreign_owned_executable(
    directory: Path, name: str, mode: int = MODE_EXE_TRUSTED
) -> Path:
    """Install an executable owned by neither root nor getuid(); skip if unable.

    Never consults uncontrolled host paths: ownership is changed only on the
    fixture file created under directory.
    """

    candidates = _foreign_uid_candidates()
    if not candidates:
        pytest.skip("no distinct non-root foreign UID available on host")

    exe = install_executable(directory, name, mode=mode)
    me = os.getuid()
    for uid in candidates:
        if not _try_set_owner(exe, uid):
            continue
        owner = exe.stat().st_uid
        if owner not in (0, me):
            return exe

    pytest.skip(
        "executing user lacks permission to create a distinct-owner fixture"
    )


def ownership_is_trusted(uid: int) -> bool:
    """Established trust policy: only UID 0 and getuid() are trusted."""

    return uid == 0 or uid == os.getuid()


def iter_realpath_ancestors(path: bytes | str | os.PathLike[str]):
    """Yield realpath(path) then each ancestor directory through `/`."""

    cur = Path(os.path.realpath(os.fspath(path)))
    while True:
        yield cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent


def require_foreign_owned_directory(directory: Path) -> Path:
    """Chown an existing directory to a foreign UID; skip if the host cannot.

    Non-privileged coverage prefers ambient untrusted ancestors of the fixture
    tree via ownership_finding_triples(); this helper is optional enrichment
    when the host can establish a distinct-owner directory inside tmp.
    """

    candidates = _foreign_uid_candidates()
    if not candidates:
        pytest.skip("no distinct non-root foreign UID available on host")

    me = os.getuid()
    directory = directory.resolve()
    if not directory.is_dir():
        raise AssertionError(f"foreign-owner fixture is not a directory: {directory}")
    for uid in candidates:
        if not _try_set_owner(directory, uid):
            continue
        owner = directory.stat().st_uid
        if owner not in (0, me):
            return directory
    pytest.skip(
        "executing user lacks permission to create a distinct-owner directory"
    )


def ownership_finding_triples(
    indexed_dirs: list[tuple[int, bytes | str | os.PathLike[str]]],
) -> list[tuple[int, Path, str]]:
    """Build UNSAFE_OWNER triples for untrusted PATH dirs and ancestors.

    Only existing directories are walked (followed-target metadata). Shared
    offending realpaths are deduplicated to the lowest PATH index that
    observed them. Missing, non-directory, and empty components contribute
    nothing here.
    """

    best_index: dict[str, int] = {}
    best_path: dict[str, Path] = {}
    for index, raw in indexed_dirs:
        try:
            st = os.stat(os.fspath(raw))
        except OSError:
            continue
        if not stat_mod.S_ISDIR(st.st_mode):
            continue
        for node in iter_realpath_ancestors(raw):
            try:
                node_st = node.stat()
            except OSError:
                continue
            if ownership_is_trusted(node_st.st_uid):
                continue
            key = str(node)
            if key not in best_index or index < best_index[key]:
                best_index[key] = index
                best_path[key] = node
    return [
        (best_index[key], best_path[key], "UNSAFE_OWNER") for key in best_index
    ]


def expect_path_findings(
    items: list[tuple[int, bytes | str | os.PathLike[str], str]],
    ownership_dirs: list[tuple[int, bytes | str | os.PathLike[str]]],
) -> tuple[int, bytes]:
    """Combine hazard items with PATH/ancestor ownership; return status + stdout."""

    combined: list[tuple[int, bytes | str | os.PathLike[str], str]] = list(items)
    combined.extend(ownership_finding_triples(ownership_dirs))
    if not combined:
        return 0, b""
    return 1, findings_stdout(sort_findings(combined))


def expect_command_query(
    matches: list[bytes | str | os.PathLike[str]],
    items: list[tuple[int, bytes | str | os.PathLike[str], str]],
    ownership_dirs: list[tuple[int, bytes | str | os.PathLike[str]]],
) -> tuple[int, bytes]:
    """MATCH lines plus applicable hazards including directory ownership."""

    combined: list[tuple[int, bytes | str | os.PathLike[str], str]] = list(items)
    combined.extend(ownership_finding_triples(ownership_dirs))
    findings = sort_findings(combined) if combined else None
    status = 1 if combined else 0
    return status, command_query_stdout(matches, findings)


def sort_findings(
    items: list[tuple[int, bytes | str | os.PathLike[str], str]],
) -> list[tuple[str, bytes]]:
    """Sort (operand_index, root, code) by root bytes, index, then code rank."""

    normalized: list[tuple[bytes, int, int, str]] = []
    for operand_index, root, code in items:
        root_bytes = root if isinstance(root, bytes) else os.fsencode(os.fspath(root))
        normalized.append(
            (root_bytes, operand_index, CODE_RANK_INDEX[code], code)
        )
    normalized.sort()
    return [(code, root_bytes) for root_bytes, _, _, code in normalized]


def assert_no_raw_unsafe_bytes(data: bytes) -> None:
    for index, byte in enumerate(data):
        if byte == 0x0A or byte == 0x09:
            continue
        if byte < 0x20 or byte > 0x7E:
            raise AssertionError(
                f"unsafe raw byte 0x{byte:02X} at offset {index} in output"
            )


def _valgrind_command(cmd: list[str]):
    if os.environ.get("PATHAUDIT_UNDER_VALGRIND") != "1":
        return cmd, None

    valgrind = shutil.which("valgrind")
    if valgrind is None:
        raise AssertionError(
            "PATHAUDIT_UNDER_VALGRIND=1 but valgrind was not found on PATH"
        )

    fd, vg_log = tempfile.mkstemp(prefix="pathaudit-valgrind.", dir="/tmp")
    os.close(fd)
    wrapped = [
        valgrind,
        "--quiet",
        "--error-exitcode=99",
        "--leak-check=full",
        "--errors-for-leak-kinds=definite,possible",
        f"--log-file={vg_log}",
        *cmd,
    ]
    return wrapped, vg_log


def _finish_valgrind(result, vg_log):
    if vg_log is None:
        return result
    try:
        log_size = os.path.getsize(vg_log)
        if result.returncode == 99 or log_size > 0:
            with open(vg_log, "rb") as handle:
                log_bytes = handle.read()
            detail = log_bytes.decode("utf-8", errors="replace")
            raise AssertionError(
                f"valgrind reported errors (status {result.returncode}):\n{detail}"
            )
    finally:
        os.unlink(vg_log)
    return result


def _base_child_env(
    extra: dict[str, str | None] | None = None,
) -> dict[str, str]:
    """Build a controlled child env, forwarding declared sanitizer knobs.

    Default PATH is an unreachable sealed value so ambient search cannot leak
    in. Callers may override PATH with a fixture string, or pass PATH=None to
    unset it for the reject-closed PATH_UNSET contract.
    """

    run_env: dict[str, str] = {
        # Never consult the worker PATH; keep an explicit unreachable value.
        "PATH": "/pathaudit-tests-must-not-search-here",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for key in SANITIZER_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None:
            run_env[key] = value
    if extra:
        for key, value in extra.items():
            if value is None:
                run_env.pop(key, None)
            else:
                run_env[key] = value
    return run_env


def run_pathaudit(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str | None] | None = None,
):
    """Run pathaudit with byte-preserving argv and a controlled environment."""

    argv: list[str] = [str(binary)]
    for arg in args:
        if isinstance(arg, bytes):
            argv.append(os.fsdecode(arg))
        else:
            argv.append(os.fspath(arg))

    run_env = _base_child_env(env)

    cmd, vg_log = _valgrind_command(argv)
    result = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        cwd=None if cwd is None else os.fspath(cwd),
        env=run_env,
    )
    return _finish_valgrind(result, vg_log)


def run_pathaudit_path_mode(
    binary: Path,
    path_value: str | None,
    *extra_args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str | None] | None = None,
):
    """Run exclusive `pathaudit --path` with a controlled PATH value or unset."""

    path_env: dict[str, str | None] = dict(env) if env else {}
    path_env["PATH"] = path_value
    return run_pathaudit(
        binary,
        "--path",
        *extra_args,
        cwd=cwd,
        env=path_env,
    )


def run_pathaudit_command_mode(
    binary: Path,
    command: bytes | str,
    path_value: str | None,
    *extra_args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str | None] | None = None,
):
    """Run exclusive `pathaudit --command NAME` with a controlled PATH value."""

    path_env: dict[str, str | None] = dict(env) if env else {}
    path_env["PATH"] = path_value
    return run_pathaudit(
        binary,
        "--command",
        command,
        *extra_args,
        cwd=cwd,
        env=path_env,
    )


def run_with_closed_stdout_pipe(
    binary: Path,
    *args: str,
    env: dict[str, str | None] | None = None,
):
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    cmd, vg_log = _valgrind_command([str(binary), *args])
    proc = subprocess.Popen(
        cmd,
        stdout=write_fd,
        stderr=subprocess.PIPE,
        env=_base_child_env(env),
    )
    os.close(write_fd)
    _, stderr = proc.communicate()
    _finish_valgrind(types.SimpleNamespace(returncode=proc.returncode), vg_log)
    return proc.returncode, stderr


def diagnostic_lines(reason: str, root: bytes | str | os.PathLike[str] | None = None):
    if root is None:
        first = f"pathaudit: {reason}\n".encode("ascii")
    else:
        first = f"pathaudit: {reason}: ".encode("ascii") + escape_root(root) + b"\n"
    if reason in ("USAGE", "UNKNOWN_OPTION"):
        return first + USAGE_LINE
    return first


def resolve_pathaudit_override(env_bin: str) -> Path:
    """Resolve PATHAUDIT_BIN once so a relative override cannot track cwd changes.

    Popen looks up a relative program path against the child cwd. The fixture must
    therefore expand and resolve the override at session start, not at exec time.
    """

    resolved = Path(env_bin).expanduser().resolve()
    if not resolved.is_absolute():
        raise ValueError(
            f"PATHAUDIT_BIN did not resolve to an absolute path: {env_bin!r}"
        )
    return resolved


@pytest.fixture(scope="session")
def pathaudit_bin(tmp_path_factory):
    env_bin = os.environ.get("PATHAUDIT_BIN")
    if env_bin:
        # Resolve at fixture time so a relative override cannot be re-looked-up
        # against a later per-test cwd= (Popen resolves relative programs vs cwd).
        binary = resolve_pathaudit_override(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"PATHAUDIT_BIN is not an executable file: {env_bin}")
        return binary

    if not SRC.is_file():
        pytest.fail(f"{SRC} is missing; pathaudit contract suite requires the source")

    # Compile into pytest's session temp tree only — never build/ or the repo root.
    build_dir = tmp_path_factory.mktemp("pathaudit-build")
    binary = build_dir / "pathaudit"
    compile_result = subprocess.run(
        [
            os.environ.get("CC", "cc"),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-o",
            str(binary),
            str(SRC),
        ],
        capture_output=True,
        check=False,
    )
    if compile_result.returncode != 0:
        detail = compile_result.stderr.decode("utf-8", errors="replace")
        pytest.fail(f"failed to compile {SRC} into {binary}:\n{detail}")
    assert binary.is_file()
    assert os.access(binary, os.X_OK)
    assert binary.resolve() != (ROOT / "pathaudit").resolve()
    assert binary.resolve() != (ROOT / "build" / "pathaudit").resolve()
    return binary


@pytest.fixture
def fixture_tree(tmp_path):
    """Deterministic absolute roots with exact, controllable permission bits."""

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    # Pin modes on every directory the relative-root cases may resolve through.
    os.chmod(tmp_path, MODE_PRIVATE)
    os.chmod(cwd, MODE_PRIVATE)

    private = tmp_path / "private"
    group_w = tmp_path / "group-writable"
    world_w = tmp_path / "world-writable"
    both_w = tmp_path / "both-writable"
    for path in (private, group_w, world_w, both_w):
        path.mkdir()

    os.chmod(private, MODE_PRIVATE)
    os.chmod(group_w, MODE_GROUP_WRITABLE)
    os.chmod(world_w, MODE_WORLD_WRITABLE)
    os.chmod(both_w, MODE_BOTH_WRITABLE)

    regular = tmp_path / "regular-file"
    regular.write_bytes(b"not-a-directory\n")
    os.chmod(regular, 0o644)

    missing = tmp_path / "missing-root"
    assert not missing.exists()

    dangling = tmp_path / "dangling-symlink"
    dangling.symlink_to("definitely-absent-target")

    link_private = tmp_path / "link-to-private"
    link_private.symlink_to(private)

    link_world = tmp_path / "link-to-world"
    link_world.symlink_to(world_w)

    link_file = tmp_path / "link-to-file"
    link_file.symlink_to(regular)

    unusual = tmp_path / 'name with "quotes" and \\backslashes\\'
    unusual.mkdir()
    os.chmod(unusual, MODE_PRIVATE)

    control_name = os.fsdecode(b"name-with-\x1b-esc")
    control_path = tmp_path / control_name
    control_path.mkdir()
    os.chmod(control_path, MODE_PRIVATE)

    non_utf8_name = os.fsdecode(b"name-with-\xff-byte")
    non_utf8 = tmp_path / non_utf8_name
    non_utf8.mkdir()
    os.chmod(non_utf8, MODE_PRIVATE)

    enotdir = regular.resolve() / "nested"
    # Path exists only as a component failure through the regular file.

    loop_a = tmp_path / "loop-a"
    loop_b = tmp_path / "loop-b"
    loop_a.symlink_to(loop_b)
    loop_b.symlink_to(loop_a)

    # absolute() keeps symlink operands as supplied roots; resolve() would
    # follow links and raise on the intentional loop fixture.
    return types.SimpleNamespace(
        root=tmp_path,
        cwd=cwd,
        private=private.resolve(),
        group_w=group_w.resolve(),
        world_w=world_w.resolve(),
        both_w=both_w.resolve(),
        regular=regular.resolve(),
        missing=missing.resolve(),
        dangling=dangling.absolute(),
        link_private=link_private.absolute(),
        link_world=link_world.absolute(),
        link_file=link_file.absolute(),
        unusual=unusual.resolve(),
        control=control_path.resolve(),
        non_utf8=non_utf8.resolve(),
        enotdir=enotdir,
        loop_a=loop_a.absolute(),
        loop_b=loop_b.absolute(),
    )


def test_escape_root_contract_helpers():
    assert escape_root(b"") == b'""'
    assert escape_root(b"abc") == b'"abc"'
    assert escape_root(b'a"b\\c') == b'"a\\"b\\\\c"'
    assert escape_root(b"a\x1b\t\xff") == b'"a\\x1B\\x09\\xFF"'
    # Newline must become \\x0A so an operand cannot forge an extra diagnostic line.
    assert escape_root(b"a\npathaudit: FORGED") == b'"a\\x0Apathaudit: FORGED"'
    assert finding_line("EMPTY_ROOT", b"") == b'EMPTY_ROOT\t""\n'


def test_help_and_version(pathaudit_bin):
    help_result = run_pathaudit(pathaudit_bin, "--help")
    assert help_result.returncode == 0
    assert help_result.stdout == HELP_STDOUT
    assert help_result.stderr == b""

    version_result = run_pathaudit(pathaudit_bin, "--version")
    assert version_result.returncode == 0
    assert version_result.stdout == VERSION_STDOUT
    assert version_result.stderr == b""


def test_help_and_version_reject_extra_operands(pathaudit_bin, fixture_tree):
    for flag in ("--help", "--version"):
        result = run_pathaudit(pathaudit_bin, flag, str(fixture_tree.private))
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr == diagnostic_lines("USAGE")


def test_usage_errors_for_missing_roots_and_unknown_options(pathaudit_bin):
    no_args = run_pathaudit(pathaudit_bin)
    assert no_args.returncode == 2
    assert no_args.stdout == b""
    assert no_args.stderr == diagnostic_lines("USAGE")

    unknown = run_pathaudit(pathaudit_bin, "--not-an-option")
    assert unknown.returncode == 2
    assert unknown.stdout == b""
    assert unknown.stderr == diagnostic_lines("UNKNOWN_OPTION")

    short_unknown = run_pathaudit(pathaudit_bin, "-x")
    assert short_unknown.returncode == 2
    assert short_unknown.stdout == b""
    assert short_unknown.stderr == diagnostic_lines("UNKNOWN_OPTION")


def test_leading_dash_root_requires_end_of_options(pathaudit_bin, tmp_path):
    dash_root = tmp_path / "-dash-root"
    dash_root.mkdir()
    os.chmod(dash_root, MODE_PRIVATE)
    abs_dash = str(dash_root.resolve())

    without = run_pathaudit(pathaudit_bin, "-dash-root", cwd=tmp_path)
    assert without.returncode == 2
    assert without.stdout == b""
    assert without.stderr == diagnostic_lines("UNKNOWN_OPTION")

    with_end = run_pathaudit(pathaudit_bin, "--", abs_dash)
    assert with_end.returncode == 0
    assert with_end.stdout == b""
    assert with_end.stderr == b""


def test_safe_private_absolute_root_exits_zero(pathaudit_bin, fixture_tree):
    result = run_pathaudit(pathaudit_bin, str(fixture_tree.private), cwd=fixture_tree.cwd)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_does_not_consult_path_environment(pathaudit_bin, fixture_tree):
    """Explicit-root mode must ignore PATH; only `--path` reads it."""

    polluted = {
        "PATH": f"{fixture_tree.world_w}:/bin:/usr/bin",
        "LC_ALL": "C",
        "LANG": "C",
    }
    clean = {
        "PATH": "",
        "LC_ALL": "C",
        "LANG": "C",
    }
    first = run_pathaudit(
        pathaudit_bin, str(fixture_tree.private), cwd=fixture_tree.cwd, env=polluted
    )
    second = run_pathaudit(
        pathaudit_bin, str(fixture_tree.private), cwd=fixture_tree.cwd, env=clean
    )
    assert first.returncode == 0
    assert second.returncode == 0
    assert first.stdout == second.stdout == b""
    assert first.stderr == second.stderr == b""


def test_path_mode_private_component_exits_zero(pathaudit_bin, fixture_tree):
    result = run_pathaudit_path_mode(
        pathaudit_bin, str(fixture_tree.private), cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings([], [(0, fixture_tree.private)])
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stderr == b""


def test_path_mode_group_world_and_both_writable(pathaudit_bin, fixture_tree):
    group = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.group_w))
    code, expected = expect_path_findings(
        [(0, fixture_tree.group_w, "GROUP_WRITABLE")],
        [(0, fixture_tree.group_w)],
    )
    assert group.returncode == code
    assert group.stderr == b""
    assert group.stdout == expected

    world = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.world_w))
    code, expected = expect_path_findings(
        [(0, fixture_tree.world_w, "WORLD_WRITABLE")],
        [(0, fixture_tree.world_w)],
    )
    assert world.returncode == code
    assert world.stderr == b""
    assert world.stdout == expected

    both = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.both_w))
    code, expected = expect_path_findings(
        [
            (0, fixture_tree.both_w, "GROUP_WRITABLE"),
            (0, fixture_tree.both_w, "WORLD_WRITABLE"),
        ],
        [(0, fixture_tree.both_w)],
    )
    assert both.returncode == code
    assert both.stderr == b""
    assert both.stdout == expected


def test_path_mode_relative_empty_missing_nondirectory(pathaudit_bin, fixture_tree):
    empty = run_pathaudit_path_mode(pathaudit_bin, "", cwd=fixture_tree.cwd)
    assert empty.returncode == 1
    assert empty.stderr == b""
    assert empty.stdout == findings_stdout([("EMPTY_ROOT", b"")])

    relative = run_pathaudit_path_mode(
        pathaudit_bin, "rel-missing", cwd=fixture_tree.cwd
    )
    assert relative.returncode == 1
    assert relative.stderr == b""
    assert relative.stdout == findings_stdout(
        [
            ("RELATIVE_ROOT", "rel-missing"),
            ("MISSING_ROOT", "rel-missing"),
        ]
    )

    missing = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.missing))
    assert missing.returncode == 1
    assert missing.stderr == b""
    assert missing.stdout == findings_stdout(
        [("MISSING_ROOT", fixture_tree.missing)]
    )

    nondir = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.regular))
    assert nondir.returncode == 1
    assert nondir.stderr == b""
    assert nondir.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.regular)]
    )


def test_path_mode_unset_path_is_reject_closed(pathaudit_bin):
    result = run_pathaudit_path_mode(pathaudit_bin, None)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_lines("PATH_UNSET")
    assert b"usage:" not in result.stderr


def test_path_mode_empty_path_is_single_empty_root(pathaudit_bin):
    result = run_pathaudit_path_mode(pathaudit_bin, "")
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout([("EMPTY_ROOT", b"")])


def test_path_mode_colon_split_retains_empty_and_duplicates(pathaudit_bin, fixture_tree):
    private = str(fixture_tree.private)
    missing = str(fixture_tree.missing)

    # PATH value -> list of (index, component, codes)
    cases: list[tuple[str, list[tuple[int, bytes | str, list[str]]]]] = [
        (":", [(0, b"", ["EMPTY_ROOT"]), (1, b"", ["EMPTY_ROOT"])]),
        (
            "::",
            [
                (0, b"", ["EMPTY_ROOT"]),
                (1, b"", ["EMPTY_ROOT"]),
                (2, b"", ["EMPTY_ROOT"]),
            ],
        ),
        (
            f"{private}:{private}",
            [(0, private, []), (1, private, [])],
        ),
        (
            f"{private}:",
            [(0, private, []), (1, b"", ["EMPTY_ROOT"])],
        ),
        (
            f":{private}",
            [(0, b"", ["EMPTY_ROOT"]), (1, private, [])],
        ),
        (
            f"{private}::{missing}",
            [
                (0, private, []),
                (1, b"", ["EMPTY_ROOT"]),
                (2, missing, ["MISSING_ROOT"]),
            ],
        ),
    ]
    for path_value, components in cases:
        result = run_pathaudit_path_mode(
            pathaudit_bin, path_value, cwd=fixture_tree.cwd
        )
        items: list[tuple[int, bytes | str, str]] = []
        ownership_dirs: list[tuple[int, bytes | str]] = []
        for index, component, codes in components:
            for code in codes:
                items.append((index, component, code))
            # Usable directory components participate in ownership walks.
            if component not in (b"", "") and "MISSING_ROOT" not in codes:
                try:
                    if Path(os.fsdecode(component) if isinstance(component, bytes) else component).is_dir():
                        ownership_dirs.append((index, component))
                except OSError:
                    pass
        code, expected = expect_path_findings(items, ownership_dirs)
        assert result.returncode == code, path_value
        assert result.stderr == b"", path_value
        assert result.stdout == expected, path_value


def test_path_mode_duplicate_components_preserve_position(pathaudit_bin, fixture_tree):
    root = str(fixture_tree.group_w)
    result = run_pathaudit_path_mode(pathaudit_bin, f"{root}:{root}")
    code, expected = expect_path_findings(
        [
            (0, root, "GROUP_WRITABLE"),
            (1, root, "GROUP_WRITABLE"),
        ],
        [(0, root), (1, root)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_path_mode_leading_dash_component(pathaudit_bin, tmp_path):
    dash_root = tmp_path / "-dash-component"
    dash_root.mkdir()
    os.chmod(dash_root, MODE_PRIVATE)
    abs_dash = str(dash_root.resolve())

    absolute = run_pathaudit_path_mode(pathaudit_bin, abs_dash)
    code, expected = expect_path_findings([], [(0, abs_dash)])
    assert absolute.returncode == code
    assert absolute.stdout == expected
    assert absolute.stderr == b""

    relative = run_pathaudit_path_mode(
        pathaudit_bin, "-dash-component", cwd=tmp_path
    )
    code, expected = expect_path_findings(
        [(0, "-dash-component", "RELATIVE_ROOT")],
        [(0, abs_dash)],
    )
    assert relative.returncode == code
    assert relative.stderr == b""
    assert relative.stdout == expected

    # Leading-dash on argv remains an option error; only PATH components may
    # begin with '-' without `--`.
    argv_dash = run_pathaudit(pathaudit_bin, "-dash-component", cwd=tmp_path)
    assert argv_dash.returncode == 2
    assert argv_dash.stdout == b""
    assert argv_dash.stderr == diagnostic_lines("UNKNOWN_OPTION")


def test_path_mode_stable_ordering_across_component_permutations(
    pathaudit_bin, fixture_tree
):
    a = str(fixture_tree.both_w)
    b = str(fixture_tree.missing)
    c = str(fixture_tree.private)
    d = str(fixture_tree.regular)
    _, expected = expect_path_findings(
        [
            (0, a, "GROUP_WRITABLE"),
            (0, a, "WORLD_WRITABLE"),
            (1, b, "MISSING_ROOT"),
            (3, d, "NON_DIRECTORY_ROOT"),
        ],
        [(0, a), (2, c)],
    )

    first = run_pathaudit_path_mode(pathaudit_bin, f"{a}:{b}:{c}:{d}")
    second = run_pathaudit_path_mode(pathaudit_bin, f"{d}:{c}:{b}:{a}")
    # Second permutation remaps indices; recompute expected for that PATH.
    _, expected_second = expect_path_findings(
        [
            (0, d, "NON_DIRECTORY_ROOT"),
            (2, b, "MISSING_ROOT"),
            (3, a, "GROUP_WRITABLE"),
            (3, a, "WORLD_WRITABLE"),
        ],
        [(1, c), (3, a)],
    )

    assert first.returncode == 1
    assert second.returncode == 1
    assert first.stderr == second.stderr == b""
    assert first.stdout == expected
    assert second.stdout == expected_second
    # Same multiset of finding lines regardless of PATH order (byte identity
    # of roots still drives primary sort; indices only break ties).
    assert sorted(first.stdout.splitlines()) == sorted(second.stdout.splitlines())


def test_path_mode_rejects_extra_operands_and_options(pathaudit_bin, fixture_tree):
    with_root = run_pathaudit(
        pathaudit_bin,
        "--path",
        str(fixture_tree.private),
        env={"PATH": str(fixture_tree.private)},
    )
    assert with_root.returncode == 2
    assert with_root.stdout == b""
    assert with_root.stderr == diagnostic_lines("USAGE")

    double = run_pathaudit(
        pathaudit_bin,
        "--path",
        "--path",
        env={"PATH": str(fixture_tree.private)},
    )
    assert double.returncode == 2
    assert double.stdout == b""
    assert double.stderr == diagnostic_lines("USAGE")

    mixed_option = run_pathaudit(
        pathaudit_bin,
        "--path",
        "--version",
        env={"PATH": str(fixture_tree.private)},
    )
    assert mixed_option.returncode == 2
    assert mixed_option.stdout == b""
    assert mixed_option.stderr == diagnostic_lines("USAGE")

    root_then_path = run_pathaudit(
        pathaudit_bin,
        str(fixture_tree.private),
        "--path",
        env={"PATH": str(fixture_tree.private)},
    )
    assert root_then_path.returncode == 2
    assert root_then_path.stdout == b""
    # Leading absolute root is fine; trailing `--path` is an unknown option
    # under explicit-root scanning, or USAGE if exclusive-mode parsing rejects
    # the mixture. Either way status is 2 with the shared usage synopsis.
    assert root_then_path.stderr in (
        diagnostic_lines("USAGE"),
        diagnostic_lines("UNKNOWN_OPTION"),
    )


def test_path_mode_component_count_limit(pathaudit_bin, fixture_tree):
    # n colons produce n+1 empty components; stay under OS env size.
    at_path = ":" * (MAX_ROOT_COUNT - 1)
    assert at_path.count(":") + 1 == MAX_ROOT_COUNT
    at_result = run_pathaudit_path_mode(pathaudit_bin, at_path, cwd=fixture_tree.cwd)
    assert at_result.returncode == 1
    assert at_result.stderr == b""
    assert b"ROOT_COUNT_LIMIT" not in at_result.stderr
    assert at_result.stdout.count(b"EMPTY_ROOT\t") == MAX_ROOT_COUNT

    over_path = ":" * MAX_ROOT_COUNT
    assert over_path.count(":") + 1 == MAX_ROOT_COUNT + 1
    over = run_pathaudit_path_mode(pathaudit_bin, over_path, cwd=fixture_tree.cwd)
    assert over.returncode == 2
    assert over.stdout == b""
    assert over.stderr == diagnostic_lines("ROOT_COUNT_LIMIT")


def test_path_mode_component_bytes_limit(pathaudit_bin):
    # Aggregate component bytes (with NULs) must exceed 1 MiB. On Linux each
    # environment string is also capped near MAX_ARG_STRLEN (~128 KiB), and
    # colon-split aggregate size is len(PATH)+1, so a real PATH cannot reach the
    # contract's ROOT_BYTES_LIMIT. Probe first; skip when the OS rejects the env.
    chunk = "/" + ("b" * 4095)
    per_component = len(chunk) + 1
    count = (MAX_ROOT_BYTES // per_component) + 1
    path_value = ":".join([chunk] * count)
    aggregate = sum(len(part) + 1 for part in path_value.split(":"))
    assert aggregate > MAX_ROOT_BYTES
    assert count <= MAX_ROOT_COUNT

    probe_env = _base_child_env({"PATH": path_value})
    try:
        probe = subprocess.run(
            [str(pathaudit_bin), "--path"],
            capture_output=True,
            check=False,
            env=probe_env,
        )
    except OSError as exc:
        if exc.errno == errno_mod.E2BIG:
            pytest.skip(
                "host rejects PATH large enough to exceed ROOT_BYTES_LIMIT "
                f"(aggregate={aggregate}, path_len={len(path_value)}); "
                "explicit-root test_root_bytes_limit covers the same gate"
            )
        raise

    assert probe.returncode == 2
    assert probe.stdout == b""
    assert probe.stderr == diagnostic_lines("ROOT_BYTES_LIMIT")


def test_path_mode_large_but_host_legal_path_is_not_bytes_limit(
    pathaudit_bin, fixture_tree
):
    """A large PATH under host env limits must not spuriously hit ROOT_BYTES_LIMIT."""

    # Stay under typical MAX_ARG_STRLEN (128 KiB) while exercising many components.
    chunk = str(fixture_tree.private)
    path_value = ":".join([chunk] * 200)
    assert len(path_value) < 128 * 1024
    aggregate = sum(len(part) + 1 for part in path_value.split(":"))
    assert aggregate < MAX_ROOT_BYTES

    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    assert b"ROOT_BYTES_LIMIT" not in result.stderr
    ownership_dirs = [(index, chunk) for index in range(200)]
    code, expected = expect_path_findings([], ownership_dirs)
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stderr == b""


def test_path_mode_component_length_limit(pathaudit_bin):
    at_limit = "/" + ("a" * (MAX_ROOT_LENGTH - 1))
    over_limit = "/" + ("a" * MAX_ROOT_LENGTH)
    assert len(at_limit) == MAX_ROOT_LENGTH
    assert len(over_limit) == MAX_ROOT_LENGTH + 1

    at_result = run_pathaudit_path_mode(pathaudit_bin, at_limit)
    assert at_result.returncode in (0, 1, 2)
    assert b"ROOT_LENGTH_LIMIT" not in at_result.stderr
    if at_result.returncode == 2:
        assert at_result.stdout == b""
        assert at_result.stderr.startswith(b"pathaudit: INSPECTION_ERROR_")
    else:
        assert at_result.stderr == b""

    over = run_pathaudit_path_mode(pathaudit_bin, over_limit)
    assert over.returncode == 2
    assert over.stdout == b""
    assert over.stderr == diagnostic_lines("ROOT_LENGTH_LIMIT")


def test_path_mode_does_not_traverse_nested_directories(pathaudit_bin, fixture_tree):
    """Nested dirs are not hazard-inspected; trusted top-level executables stay silent.

    `--path` may scan top-level regular executables for shadowing and for the
    shared writability trust model, but nested directories must not contribute
    WORLD_WRITABLE (or other) findings, nested same-basename executables must
    not invent SHADOWED lines or executable-writability findings, and a
    trusted-mode basename present in only one PATH directory must not emit
    SHADOWED or permission findings by itself.
    """

    nested_world = fixture_tree.private / "nested-world"
    nested_world.mkdir()
    os.chmod(nested_world, MODE_WORLD_WRITABLE)
    # Trusted top-level executable: owner write only → no permission finding.
    install_executable(fixture_tree.private, "evil-bin", mode=MODE_EXE_TRUSTED)

    # Nested colliding basenames across two PATH roots must not invent shadows
    # or executable-writability findings: only top-level regular executables
    # participate in PATH executable inspection.
    other = fixture_tree.cwd / "other-root"
    other.mkdir()
    os.chmod(other, MODE_PRIVATE)
    nested_other = other / "nested-other"
    nested_other.mkdir()
    os.chmod(nested_other, MODE_PRIVATE)
    # Even world-writable nested targets must remain invisible without traversal.
    install_executable(nested_world, "nested-tool", mode=MODE_WORLD_WRITABLE)
    install_executable(nested_other, "nested-tool", mode=MODE_WORLD_WRITABLE)

    result = run_pathaudit_path_mode(
        pathaudit_bin,
        f"{fixture_tree.private}:{other}",
        cwd=fixture_tree.cwd,
    )
    code, expected = expect_path_findings(
        [],
        [(0, fixture_tree.private), (1, other)],
    )
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stderr == b""
    assert b"WORLD_WRITABLE" not in result.stdout
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"evil-bin" not in result.stdout
    assert b"SHADOWED\t" not in result.stdout
    assert b"nested-tool" not in result.stdout


def test_path_mode_exit_status_classes(pathaudit_bin, fixture_tree):
    ok = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.private))
    ok_code, _ = expect_path_findings([], [(0, fixture_tree.private)])
    assert ok.returncode == ok_code

    hazard = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.group_w))
    assert hazard.returncode == 1

    # Existing non-directory PATH components are hazards (status 1), not
    # operational errors (status 2) and not silent successes (status 0).
    nondir = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.regular))
    assert nondir.returncode == 1
    assert nondir.stderr == b""
    assert nondir.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.regular)]
    )

    unset = run_pathaudit_path_mode(pathaudit_bin, None)
    assert unset.returncode == 2
    assert unset.stderr == diagnostic_lines("PATH_UNSET")

    usage = run_pathaudit(
        pathaudit_bin, "--path", "extra", env={"PATH": str(fixture_tree.private)}
    )
    assert usage.returncode == 2
    assert usage.stderr == diagnostic_lines("USAGE")


def test_path_mode_exact_diagnostics_for_inspection_error(pathaudit_bin, fixture_tree):
    result = run_pathaudit_path_mode(pathaudit_bin, str(fixture_tree.loop_a))
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    assert result.stderr == diagnostic_lines(reason, fixture_tree.loop_a)
    assert_no_raw_unsafe_bytes(result.stderr)


def test_path_mode_mixed_hazard_components_deterministic(
    pathaudit_bin, fixture_tree
):
    empty = ""
    relative = "rel-missing"
    missing = str(fixture_tree.missing)
    nondir = str(fixture_tree.regular)
    group = str(fixture_tree.group_w)
    world = str(fixture_tree.world_w)
    path_value = ":".join([empty, relative, missing, nondir, group, world])

    result = run_pathaudit_path_mode(
        pathaudit_bin, path_value, cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (1, relative, "RELATIVE_ROOT"),
            (1, relative, "MISSING_ROOT"),
            (2, missing, "MISSING_ROOT"),
            (3, nondir, "NON_DIRECTORY_ROOT"),
            (4, group, "GROUP_WRITABLE"),
            (5, world, "WORLD_WRITABLE"),
        ],
        [(4, group), (5, world)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    for hazard_code in DIRECTORY_CODE_RANK:
        # UNSAFE_OWNER appears when this host has untrusted ancestors; otherwise
        # writable codes still cover the directory taxonomy surface.
        if hazard_code == "UNSAFE_OWNER" and hazard_code.encode("ascii") not in expected:
            continue
        assert hazard_code.encode("ascii") in result.stdout


# ---------------------------------------------------------------------------
# Detect non-directory PATH entries (`pathaudit --path`)
#
# An existing PATH component that is not a directory (regular file, symlink to
# a file, ENOTDIR through a non-directory component) cannot participate in
# normal command lookup. Report NON_DIRECTORY_ROOT on stdout with exit status
# 1 and empty stderr. Preserve established behavior for usable private
# directories (silent), missing entries, empty components, duplicate positions,
# and bytewise finding order.
# ---------------------------------------------------------------------------


def test_path_mode_regular_file_component_reports_non_directory_root(
    pathaudit_bin, fixture_tree
):
    """Regular-file PATH component: exact NON_DIRECTORY_ROOT, exit 1, empty stderr."""

    nondir = str(fixture_tree.regular)
    result = run_pathaudit_path_mode(pathaudit_bin, nondir, cwd=fixture_tree.cwd)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.regular)]
    )
    assert result.stdout == (
        b"NON_DIRECTORY_ROOT\t" + escape_root(fixture_tree.regular) + b"\n"
    )
    assert b"MISSING_ROOT" not in result.stdout
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"WORLD_WRITABLE" not in result.stdout


def test_path_mode_symlink_to_file_and_enotdir_are_non_directory(
    pathaudit_bin, fixture_tree
):
    """Symlink-to-file and ENOTDIR PATH components share NON_DIRECTORY_ROOT."""

    link = run_pathaudit_path_mode(
        pathaudit_bin, str(fixture_tree.link_file), cwd=fixture_tree.cwd
    )
    assert link.returncode == 1
    assert link.stderr == b""
    assert link.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.link_file)]
    )

    enotdir = run_pathaudit_path_mode(
        pathaudit_bin, str(fixture_tree.enotdir), cwd=fixture_tree.cwd
    )
    assert enotdir.returncode == 1
    assert enotdir.stderr == b""
    assert enotdir.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.enotdir)]
    )


def test_path_mode_relative_regular_file_is_relative_and_non_directory(
    pathaudit_bin, fixture_tree
):
    """Relative PATH file keeps RELATIVE_ROOT and adds NON_DIRECTORY_ROOT."""

    rel_file = "regular-file"
    (fixture_tree.cwd / rel_file).write_bytes(b"not-a-directory\n")
    result = run_pathaudit_path_mode(
        pathaudit_bin, rel_file, cwd=fixture_tree.cwd
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [
            ("RELATIVE_ROOT", rel_file),
            ("NON_DIRECTORY_ROOT", rel_file),
        ]
    )


def test_path_mode_non_directory_mixed_with_valid_missing_empty_duplicates(
    pathaudit_bin, fixture_tree
):
    """Non-directory detection preserves dirs, missing, empty, order, duplicates.

    PATH shape: private : regular : missing : "" : regular
    - private absolute directory: no finding
    - regular file twice: NON_DIRECTORY_ROOT at each original index
    - missing: MISSING_ROOT
    - empty field: EMPTY_ROOT retained as ""
    Exit status 1; stderr empty; findings in contract bytewise order.
    """

    private = str(fixture_tree.private)
    nondir = str(fixture_tree.regular)
    missing = str(fixture_tree.missing)
    path_value = f"{private}:{nondir}:{missing}::{nondir}"

    # Solo private may still report PATH/ancestor ownership under the shared policy.
    alone = run_pathaudit_path_mode(pathaudit_bin, private, cwd=fixture_tree.cwd)
    alone_code, alone_expected = expect_path_findings([], [(0, private)])
    assert alone.returncode == alone_code
    assert alone.stdout == alone_expected
    assert alone.stderr == b""

    result = run_pathaudit_path_mode(
        pathaudit_bin, path_value, cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [
            (3, b"", "EMPTY_ROOT"),
            (2, missing, "MISSING_ROOT"),
            (1, nondir, "NON_DIRECTORY_ROOT"),
            (4, nondir, "NON_DIRECTORY_ROOT"),
        ],
        [(0, private)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"NON_DIRECTORY_ROOT\t") == 2
    assert result.stdout.count(b"EMPTY_ROOT\t") == 1
    assert result.stdout.count(b"MISSING_ROOT\t") == 1
    assert b"RELATIVE_ROOT" not in result.stdout
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"WORLD_WRITABLE" not in result.stdout

    # Permuting PATH remaps indices but keeps the same finding multiset shape
    # for identical root bytes (duplicates distinguished only by index).
    permuted = f"{nondir}:{private}:{nondir}:{missing}:"
    second = run_pathaudit_path_mode(
        pathaudit_bin, permuted, cwd=fixture_tree.cwd
    )
    code2, expected2 = expect_path_findings(
        [
            (4, b"", "EMPTY_ROOT"),
            (3, missing, "MISSING_ROOT"),
            (0, nondir, "NON_DIRECTORY_ROOT"),
            (2, nondir, "NON_DIRECTORY_ROOT"),
        ],
        [(1, private)],
    )
    assert second.returncode == code2
    assert second.stderr == b""
    assert second.stdout == expected2


def test_path_mode_cwd_dependent_empty_fields_leading_middle_trailing(
    pathaudit_bin, fixture_tree
):
    """Empty PATH fields mean cwd for command search; report EMPTY_ROOT only.

    Leading, middle, and trailing empty colon fields are retained with their
    original positions. Empty components are not looked up as `.` and must not
    be rewritten to a relative path string.
    """

    private = str(fixture_tree.private)

    leading = run_pathaudit_path_mode(
        pathaudit_bin, f":{private}", cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [(0, b"", "EMPTY_ROOT")],
        [(1, private)],
    )
    assert leading.returncode == code
    assert leading.stderr == b""
    assert leading.stdout == expected
    assert b"RELATIVE_ROOT" not in leading.stdout
    assert escape_root(b"") in leading.stdout
    assert escape_root(b".") not in leading.stdout

    middle = run_pathaudit_path_mode(
        pathaudit_bin, f"{private}::{private}", cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [(1, b"", "EMPTY_ROOT")],
        [(0, private), (2, private)],
    )
    assert middle.returncode == code
    assert middle.stderr == b""
    assert middle.stdout == expected

    trailing = run_pathaudit_path_mode(
        pathaudit_bin, f"{private}:", cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [(1, b"", "EMPTY_ROOT")],
        [(0, private)],
    )
    assert trailing.returncode == code
    assert trailing.stderr == b""
    assert trailing.stdout == expected

    # Leading + middle + trailing empties around safe absolutes.
    combo = run_pathaudit_path_mode(
        pathaudit_bin, f":{private}::{private}:", cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (2, b"", "EMPTY_ROOT"),
            (4, b"", "EMPTY_ROOT"),
        ],
        [(1, private), (3, private)],
    )
    assert combo.returncode == code
    assert combo.stderr == b""
    assert combo.stdout == expected


def test_path_mode_cwd_dependent_repeated_empty_fields(pathaudit_bin, fixture_tree):
    """Repeated empty fields remain distinct and keep original indices."""

    private = str(fixture_tree.private)

    only_colons = run_pathaudit_path_mode(
        pathaudit_bin, ":::", cwd=fixture_tree.cwd
    )
    assert only_colons.returncode == 1
    assert only_colons.stderr == b""
    assert only_colons.stdout == findings_stdout(
        sort_findings(
            [
                (0, b"", "EMPTY_ROOT"),
                (1, b"", "EMPTY_ROOT"),
                (2, b"", "EMPTY_ROOT"),
                (3, b"", "EMPTY_ROOT"),
            ]
        )
    )
    assert only_colons.stdout.count(b"EMPTY_ROOT\t") == 4

    # Three consecutive empty fields between safe absolutes (four colons).
    mixed = run_pathaudit_path_mode(
        pathaudit_bin, f"{private}::::{private}", cwd=fixture_tree.cwd
    )
    assert f"{private}::::{private}".split(":") == [
        private,
        "",
        "",
        "",
        private,
    ]
    code, expected = expect_path_findings(
        [
            (1, b"", "EMPTY_ROOT"),
            (2, b"", "EMPTY_ROOT"),
            (3, b"", "EMPTY_ROOT"),
        ],
        [(0, private), (4, private)],
    )
    assert mixed.returncode == code
    assert mixed.stderr == b""
    assert mixed.stdout == expected


def test_path_mode_cwd_dependent_dot_dotdot_dotslash_and_bin(
    pathaudit_bin, fixture_tree
):
    """Non-absolute PATH entries are working-directory-dependent hazards."""

    cwd = fixture_tree.cwd
    bin_dir = cwd / "bin"
    bin_dir.mkdir()
    os.chmod(bin_dir, MODE_PRIVATE)

    cases = (
        (".", [("RELATIVE_ROOT", ".")]),
        ("..", [("RELATIVE_ROOT", "..")]),
        ("./bin", [("RELATIVE_ROOT", "./bin")]),
        ("bin", [("RELATIVE_ROOT", "bin")]),
    )
    for component, expected_items in cases:
        result = run_pathaudit_path_mode(
            pathaudit_bin, component, cwd=cwd
        )
        resolved = (cwd / component).resolve()
        ownership = [(0, resolved)] if resolved.is_dir() else []
        items = [(0, root, code) for code, root in expected_items]
        code, expected = expect_path_findings(items, ownership)
        assert result.returncode == code, component
        assert result.stderr == b"", component
        assert result.stdout == expected, component
        assert b"EMPTY_ROOT" not in result.stdout, component

    # Combined PATH: preserve entry text and emit RELATIVE_ROOT for each.
    path_value = ".:..:./bin:bin"
    combined = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=cwd)
    code, expected = expect_path_findings(
        [
            (0, ".", "RELATIVE_ROOT"),
            (1, "..", "RELATIVE_ROOT"),
            (2, "./bin", "RELATIVE_ROOT"),
            (3, "bin", "RELATIVE_ROOT"),
        ],
        [
            (0, cwd.resolve()),
            (1, (cwd / "..").resolve()),
            (2, (cwd / "bin").resolve()),
            (3, (cwd / "bin").resolve()),
        ],
    )
    assert combined.returncode == code
    assert combined.stderr == b""
    assert combined.stdout == expected


def test_path_mode_cwd_dependent_absolute_entries_not_misclassified(
    pathaudit_bin, fixture_tree
):
    """Absolute PATH components must not be reported as cwd-dependent."""

    private = str(fixture_tree.private)
    missing = str(fixture_tree.missing)
    group = str(fixture_tree.group_w)
    assert private.startswith("/")
    assert missing.startswith("/")
    assert group.startswith("/")

    # Safe absolute alone: no EMPTY_ROOT / RELATIVE_ROOT (ownership may still fire).
    safe = run_pathaudit_path_mode(pathaudit_bin, private, cwd=fixture_tree.cwd)
    code, expected = expect_path_findings([], [(0, private)])
    assert safe.returncode == code
    assert safe.stdout == expected
    assert safe.stderr == b""

    # Mixed absolute hazards still omit RELATIVE_ROOT / EMPTY_ROOT.
    mixed = run_pathaudit_path_mode(
        pathaudit_bin, f"{private}:{missing}:{group}", cwd=fixture_tree.cwd
    )
    code, expected = expect_path_findings(
        [
            (1, missing, "MISSING_ROOT"),
            (2, group, "GROUP_WRITABLE"),
        ],
        [(0, private), (2, group)],
    )
    assert mixed.returncode == code
    assert mixed.stderr == b""
    assert mixed.stdout == expected
    assert b"RELATIVE_ROOT" not in mixed.stdout
    assert b"EMPTY_ROOT" not in mixed.stdout

    # Absolute beside empty/relative: only the non-absolute entries are
    # cwd-dependent; absolute private still participates in ownership.
    beside = run_pathaudit_path_mode(
        pathaudit_bin,
        f"{private}:bin:{private}:",
        cwd=fixture_tree.cwd,
    )
    # `bin` is absent under fixture_tree.cwd → RELATIVE + MISSING; trailing empty.
    code, expected = expect_path_findings(
        [
            (1, "bin", "RELATIVE_ROOT"),
            (1, "bin", "MISSING_ROOT"),
            (3, b"", "EMPTY_ROOT"),
        ],
        [(0, private), (2, private)],
    )
    assert beside.returncode == code
    assert beside.stderr == b""
    assert beside.stdout == expected


def test_path_mode_cwd_dependent_stable_ordering_and_indexing(
    pathaudit_bin, fixture_tree
):
    """Findings sort by root bytes, then original PATH index, then code rank."""

    private = str(fixture_tree.private)
    cwd = fixture_tree.cwd
    (cwd / "bin").mkdir()
    os.chmod(cwd / "bin", MODE_PRIVATE)

    # Indices: 0="", 1="bin", 2=".", 3="", 4="./bin", 5="..", 6=private, 7="bin"
    path_value = f":bin:.:{''}:./bin:..:{private}:bin"
    # The f-string above yields ":bin:.::./bin:..:{private}:bin"
    assert path_value == f":bin:.::./bin:..:{private}:bin"

    result = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=cwd)
    code, expected = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (3, b"", "EMPTY_ROOT"),
            (2, ".", "RELATIVE_ROOT"),
            (5, "..", "RELATIVE_ROOT"),
            (4, "./bin", "RELATIVE_ROOT"),
            (1, "bin", "RELATIVE_ROOT"),
            (7, "bin", "RELATIVE_ROOT"),
        ],
        [
            (0, cwd.resolve()),
            (1, (cwd / "bin").resolve()),
            (2, cwd.resolve()),
            (4, (cwd / "bin").resolve()),
            (5, (cwd / "..").resolve()),
            (6, private),
            (7, (cwd / "bin").resolve()),
        ],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected

    # Permuting PATH remaps indices but keeps the same primary byte order for
    # distinct roots; identical `bin` / empty entries break ties by index.
    # Trailing `bin::` yields two empty components at indices 6 and 7.
    permuted = f"{private}:bin:..:./bin:.:bin::"
    assert permuted.split(":") == [
        private,
        "bin",
        "..",
        "./bin",
        ".",
        "bin",
        "",
        "",
    ]
    second = run_pathaudit_path_mode(pathaudit_bin, permuted, cwd=cwd)
    code, expected = expect_path_findings(
        [
            (6, b"", "EMPTY_ROOT"),
            (7, b"", "EMPTY_ROOT"),
            (4, ".", "RELATIVE_ROOT"),
            (2, "..", "RELATIVE_ROOT"),
            (3, "./bin", "RELATIVE_ROOT"),
            (1, "bin", "RELATIVE_ROOT"),
            (5, "bin", "RELATIVE_ROOT"),
        ],
        [
            (0, private),
            (1, (cwd / "bin").resolve()),
            (2, (cwd / "..").resolve()),
            (3, (cwd / "bin").resolve()),
            (4, cwd.resolve()),
            (5, (cwd / "bin").resolve()),
            (6, cwd.resolve()),
        ],
    )
    assert second.returncode == code
    assert second.stderr == b""
    assert second.stdout == expected


def test_path_mode_cwd_dependent_behavior_across_two_working_directories(
    pathaudit_bin, tmp_path
):
    """Same PATH bytes resolve differently under two working directories."""

    cwd_a = tmp_path / "cwd-a"
    cwd_b = tmp_path / "cwd-b"
    cwd_a.mkdir()
    cwd_b.mkdir()
    os.chmod(tmp_path, MODE_PRIVATE)
    os.chmod(cwd_a, MODE_PRIVATE)
    os.chmod(cwd_b, MODE_WORLD_WRITABLE)

    # Under cwd-a: private bin/ (also reached via ./bin). Under cwd-b: the
    # same relative names resolve to a world-writable bin/.
    bin_a = cwd_a / "bin"
    bin_a.mkdir()
    os.chmod(bin_a, MODE_PRIVATE)

    bin_b = cwd_b / "bin"
    bin_b.mkdir()
    os.chmod(bin_b, MODE_WORLD_WRITABLE)

    safe_abs = tmp_path / "absolute-safe"
    safe_abs.mkdir()
    os.chmod(safe_abs, MODE_PRIVATE)
    abs_safe = str(safe_abs.resolve())

    # Empty + relative forms + one absolute that must stay clean in both cwds.
    path_value = f":.:..:./bin:bin:{abs_safe}:"

    from_a = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=cwd_a)
    from_b = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=cwd_b)

    _, expected_a = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (6, b"", "EMPTY_ROOT"),
            (1, ".", "RELATIVE_ROOT"),
            (2, "..", "RELATIVE_ROOT"),
            (3, "./bin", "RELATIVE_ROOT"),
            (4, "bin", "RELATIVE_ROOT"),
        ],
        [
            (1, cwd_a.resolve()),
            (2, (cwd_a / "..").resolve()),
            (3, bin_a.resolve()),
            (4, bin_a.resolve()),
            (5, abs_safe),
        ],
    )
    _, expected_b = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (6, b"", "EMPTY_ROOT"),
            (1, ".", "RELATIVE_ROOT"),
            (1, ".", "WORLD_WRITABLE"),
            (2, "..", "RELATIVE_ROOT"),
            (3, "./bin", "RELATIVE_ROOT"),
            (3, "./bin", "WORLD_WRITABLE"),
            (4, "bin", "RELATIVE_ROOT"),
            (4, "bin", "WORLD_WRITABLE"),
        ],
        [
            (1, cwd_b.resolve()),
            (2, (cwd_b / "..").resolve()),
            (3, bin_b.resolve()),
            (4, bin_b.resolve()),
            (5, abs_safe),
        ],
    )

    assert from_a.returncode == 1
    assert from_b.returncode == 1
    assert from_a.stderr == from_b.stderr == b""
    assert from_a.stdout == expected_a
    assert from_b.stdout == expected_b
    # Absolute safe entry itself is trusted; cwd-dependent permission findings differ.
    assert finding_line("UNSAFE_OWNER", abs_safe) not in from_a.stdout
    assert finding_line("UNSAFE_OWNER", abs_safe) not in from_b.stdout
    assert from_a.stdout != from_b.stdout
    assert b"WORLD_WRITABLE" not in from_a.stdout
    assert b"WORLD_WRITABLE" in from_b.stdout

    # Missing relative under one cwd only: proves lookup uses process cwd.
    path_missing = "rel-only-in-a"
    (cwd_a / path_missing).mkdir()
    os.chmod(cwd_a / path_missing, MODE_PRIVATE)
    assert not (cwd_b / path_missing).exists()

    miss_a = run_pathaudit_path_mode(pathaudit_bin, path_missing, cwd=cwd_a)
    miss_b = run_pathaudit_path_mode(pathaudit_bin, path_missing, cwd=cwd_b)
    _, expected_miss_a = expect_path_findings(
        [(0, path_missing, "RELATIVE_ROOT")],
        [(0, (cwd_a / path_missing).resolve())],
    )
    # Missing relative has no usable directory to walk for ownership.
    expected_miss_b = findings_stdout(
        [
            ("RELATIVE_ROOT", path_missing),
            ("MISSING_ROOT", path_missing),
        ]
    )
    assert miss_a.stdout == expected_miss_a
    assert miss_b.stdout == expected_miss_b
    assert miss_a.stdout != miss_b.stdout


def test_group_writable_world_writable_and_both(pathaudit_bin, fixture_tree):
    group = run_pathaudit(pathaudit_bin, str(fixture_tree.group_w))
    assert group.returncode == 1
    assert group.stderr == b""
    assert group.stdout == findings_stdout(
        [("GROUP_WRITABLE", fixture_tree.group_w)]
    )

    world = run_pathaudit(pathaudit_bin, str(fixture_tree.world_w))
    assert world.returncode == 1
    assert world.stderr == b""
    assert world.stdout == findings_stdout(
        [("WORLD_WRITABLE", fixture_tree.world_w)]
    )

    both = run_pathaudit(pathaudit_bin, str(fixture_tree.both_w))
    assert both.returncode == 1
    assert both.stderr == b""
    assert both.stdout == findings_stdout(
        [
            ("GROUP_WRITABLE", fixture_tree.both_w),
            ("WORLD_WRITABLE", fixture_tree.both_w),
        ]
    )


def test_missing_and_non_directory_roots(pathaudit_bin, fixture_tree):
    missing = run_pathaudit(pathaudit_bin, str(fixture_tree.missing))
    assert missing.returncode == 1
    assert missing.stderr == b""
    assert missing.stdout == findings_stdout(
        [("MISSING_ROOT", fixture_tree.missing)]
    )

    nondir = run_pathaudit(pathaudit_bin, str(fixture_tree.regular))
    assert nondir.returncode == 1
    assert nondir.stderr == b""
    assert nondir.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.regular)]
    )

    enotdir = run_pathaudit(pathaudit_bin, str(fixture_tree.enotdir))
    assert enotdir.returncode == 1
    assert enotdir.stderr == b""
    assert enotdir.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.enotdir)]
    )


def test_empty_and_relative_roots(pathaudit_bin, fixture_tree):
    empty = run_pathaudit(pathaudit_bin, b"", cwd=fixture_tree.cwd)
    assert empty.returncode == 1
    assert empty.stderr == b""
    assert empty.stdout == findings_stdout([("EMPTY_ROOT", b"")])

    dot = run_pathaudit(pathaudit_bin, ".", cwd=fixture_tree.cwd)
    assert dot.returncode == 1
    assert dot.stderr == b""
    assert dot.stdout == findings_stdout([("RELATIVE_ROOT", ".")])

    dotdot = run_pathaudit(pathaudit_bin, "..", cwd=fixture_tree.cwd)
    assert dotdot.returncode == 1
    assert dotdot.stderr == b""
    assert dotdot.stdout == findings_stdout([("RELATIVE_ROOT", "..")])

    rel_missing = run_pathaudit(pathaudit_bin, "no-such-relative", cwd=fixture_tree.cwd)
    assert rel_missing.returncode == 1
    assert rel_missing.stderr == b""
    assert rel_missing.stdout == findings_stdout(
        [
            ("RELATIVE_ROOT", "no-such-relative"),
            ("MISSING_ROOT", "no-such-relative"),
        ]
    )

    rel_file = "regular-file"
    (fixture_tree.cwd / rel_file).write_bytes(b"file\n")
    rel_nondir = run_pathaudit(pathaudit_bin, rel_file, cwd=fixture_tree.cwd)
    assert rel_nondir.returncode == 1
    assert rel_nondir.stderr == b""
    assert rel_nondir.stdout == findings_stdout(
        [
            ("RELATIVE_ROOT", rel_file),
            ("NON_DIRECTORY_ROOT", rel_file),
        ]
    )


def test_relative_writable_directory_emits_permission_codes(
    pathaudit_bin, fixture_tree
):
    rel = "rel-world"
    target = fixture_tree.cwd / rel
    target.mkdir()
    os.chmod(target, MODE_WORLD_WRITABLE)

    result = run_pathaudit(pathaudit_bin, rel, cwd=fixture_tree.cwd)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [
            ("RELATIVE_ROOT", rel),
            ("WORLD_WRITABLE", rel),
        ]
    )


def test_symlinks_follow_like_stat_and_are_not_themselves_hazards(
    pathaudit_bin, fixture_tree
):
    private_link = run_pathaudit(pathaudit_bin, str(fixture_tree.link_private))
    assert private_link.returncode == 0
    assert private_link.stdout == b""
    assert private_link.stderr == b""

    world_link = run_pathaudit(pathaudit_bin, str(fixture_tree.link_world))
    assert world_link.returncode == 1
    assert world_link.stderr == b""
    assert world_link.stdout == findings_stdout(
        [("WORLD_WRITABLE", fixture_tree.link_world)]
    )

    file_link = run_pathaudit(pathaudit_bin, str(fixture_tree.link_file))
    assert file_link.returncode == 1
    assert file_link.stderr == b""
    assert file_link.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.link_file)]
    )

    dangling = run_pathaudit(pathaudit_bin, str(fixture_tree.dangling))
    assert dangling.returncode == 1
    assert dangling.stderr == b""
    assert dangling.stdout == findings_stdout(
        [("MISSING_ROOT", fixture_tree.dangling)]
    )


def test_unusual_but_valid_names_escape_safely(pathaudit_bin, fixture_tree):
    for path in (fixture_tree.unusual, fixture_tree.control, fixture_tree.non_utf8):
        result = run_pathaudit(pathaudit_bin, str(path))
        assert result.returncode == 0
        assert result.stdout == b""
        assert result.stderr == b""

    # Force a finding so escaping appears on stdout.
    os.chmod(fixture_tree.control, MODE_WORLD_WRITABLE)
    result = run_pathaudit(pathaudit_bin, str(fixture_tree.control))
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [("WORLD_WRITABLE", fixture_tree.control)]
    )
    assert_no_raw_unsafe_bytes(result.stdout)
    assert b"\x1b" not in result.stdout


def test_repeated_roots_preserve_operand_position_order(pathaudit_bin, fixture_tree):
    root = str(fixture_tree.group_w)
    result = run_pathaudit(pathaudit_bin, root, root)
    assert result.returncode == 1
    assert result.stderr == b""
    expected = findings_stdout(
        [
            ("GROUP_WRITABLE", root),
            ("GROUP_WRITABLE", root),
        ]
    )
    assert result.stdout == expected


def test_stable_ordering_across_input_permutations(pathaudit_bin, fixture_tree):
    a = str(fixture_tree.both_w)
    b = str(fixture_tree.missing)
    c = str(fixture_tree.private)
    d = str(fixture_tree.regular)

    # private is safe and contributes no lines; remaining findings sort by root.
    items = [
        (0, a, "GROUP_WRITABLE"),
        (0, a, "WORLD_WRITABLE"),
        (1, b, "MISSING_ROOT"),
        (3, d, "NON_DIRECTORY_ROOT"),
    ]
    expected = findings_stdout(sort_findings(items))

    first = run_pathaudit(pathaudit_bin, a, b, c, d)
    second = run_pathaudit(pathaudit_bin, d, c, b, a)
    third = run_pathaudit(pathaudit_bin, b, d, a, c)

    assert first.returncode == 1
    assert second.returncode == 1
    assert third.returncode == 1
    assert first.stderr == second.stderr == third.stderr == b""
    assert first.stdout == expected
    assert second.stdout == expected
    assert third.stdout == expected


def test_all_hazard_classes_in_one_invocation(pathaudit_bin, fixture_tree):
    empty = b""
    relative = "rel-missing"
    missing = str(fixture_tree.missing)
    nondir = str(fixture_tree.regular)
    group = str(fixture_tree.group_w)
    world = str(fixture_tree.world_w)

    result = run_pathaudit(
        pathaudit_bin,
        empty,
        relative,
        missing,
        nondir,
        group,
        world,
        cwd=fixture_tree.cwd,
    )
    assert result.returncode == 1
    assert result.stderr == b""

    ordered = sort_findings(
        [
            (0, empty, "EMPTY_ROOT"),
            (1, relative, "RELATIVE_ROOT"),
            (1, relative, "MISSING_ROOT"),
            (2, missing, "MISSING_ROOT"),
            (3, nondir, "NON_DIRECTORY_ROOT"),
            (4, group, "GROUP_WRITABLE"),
            (5, world, "WORLD_WRITABLE"),
        ]
    )
    assert result.stdout == findings_stdout(ordered)
    for code in DIRECTORY_CODE_RANK:
        # Explicit-root stays ownership-blind; UNSAFE_OWNER is PATH/command-only.
        if code == "UNSAFE_OWNER":
            continue
        assert code.encode("ascii") in result.stdout
    # Explicit-root mode never searches executables; UNSAFE_OWNER stays absent.
    assert b"UNSAFE_OWNER" not in result.stdout


def test_missing_and_nondirectory_get_no_permission_findings(
    pathaudit_bin, fixture_tree
):
    # Even if a missing path string looks absolute, only MISSING_ROOT applies.
    result = run_pathaudit(
        pathaudit_bin,
        str(fixture_tree.missing),
        str(fixture_tree.regular),
    )
    assert result.returncode == 1
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"WORLD_WRITABLE" not in result.stdout
    assert b"UNSAFE_OWNER" not in result.stdout
    assert result.stdout == findings_stdout(
        sort_findings(
            [
                (0, fixture_tree.missing, "MISSING_ROOT"),
                (1, fixture_tree.regular, "NON_DIRECTORY_ROOT"),
            ]
        )
    )


def test_symlink_loop_is_inspection_error(pathaudit_bin, fixture_tree):
    result = run_pathaudit(pathaudit_bin, str(fixture_tree.loop_a))
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    assert result.stderr == diagnostic_lines(reason, fixture_tree.loop_a)
    assert_no_raw_unsafe_bytes(result.stderr)


def test_inspection_error_escapes_hostile_bytes_on_stderr(pathaudit_bin, tmp_path):
    """PAC-M4 / PA-M2: operand diagnostics must quote-escape like stdout findings.

    Embeds LF, TAB, and a forged-looking `pathaudit: FORGED` token in the PATH
    entry name. Raw LF would split the diagnostic into an extra line; raw TAB
    would ambiguate fields. Escaping must keep a single safe diagnostic line.
    """

    # Adversarial PATH entry: LF forges a second line; TAB ambiguates fields.
    hostile_name = os.fsdecode(b'loop-\n\tpathaudit: FORGED-\x1b-\xff-"-\\-a')
    partner_name = os.fsdecode(b'loop-\n\tpathaudit: FORGED-\x1b-\xff-"-\\-b')
    early_loop = tmp_path / hostile_name
    partner = tmp_path / partner_name
    early_loop.symlink_to(partner)
    partner.symlink_to(early_loop)
    loop = str(early_loop.absolute())

    result = run_pathaudit(pathaudit_bin, loop)
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    expected = diagnostic_lines(reason, loop)
    assert result.stderr == expected
    assert_no_raw_unsafe_bytes(result.stderr)
    assert b"\x1b" not in result.stderr
    assert b"\xff" not in result.stderr
    assert b'\\x1B' in result.stderr
    assert b'\\xFF' in result.stderr
    assert b'\\x0A' in result.stderr
    assert b'\\x09' in result.stderr
    # No raw TAB from the hostile entry (stderr has no structural TAB).
    assert result.stderr.count(b"\t") == 0
    # Single structural LF terminator only — no raw LF from the hostile entry.
    assert result.stderr.count(b"\n") == 1
    assert result.stderr.endswith(b"\n")
    # Unescaped LF before the embedded token would forge this second line.
    assert b"\npathaudit:" not in result.stderr
    assert b"\npathaudit: FORGED" not in result.stderr
    # Printable forged token remains visible only inside the escaped quotes.
    assert b"pathaudit: FORGED" in result.stderr
    assert result.stderr.startswith(b"pathaudit: INSPECTION_ERROR_")


def test_unreadable_path_is_inspection_error_when_provable(pathaudit_bin, tmp_path):
    if os.geteuid() == 0:
        pytest.skip("EACCES fixture is unreliable when running as root")

    blocked = tmp_path / "blocked"
    secret = blocked / "secret"
    blocked.mkdir()
    secret.mkdir()
    os.chmod(secret, MODE_PRIVATE)
    os.chmod(blocked, 0)
    target = str(secret.resolve())
    try:
        result = run_pathaudit(pathaudit_bin, target)
        assert result.returncode == 2
        assert result.stdout == b""
        reason = f"INSPECTION_ERROR_{errno_mod.EACCES}"
        assert result.stderr == diagnostic_lines(reason, target)
        assert_no_raw_unsafe_bytes(result.stderr)
    finally:
        os.chmod(blocked, 0o700)


def test_root_length_limit(pathaudit_bin):
    at_limit = b"/" + (b"a" * (MAX_ROOT_LENGTH - 1))
    over_limit = b"/" + (b"a" * MAX_ROOT_LENGTH)
    assert len(at_limit) == MAX_ROOT_LENGTH
    assert len(over_limit) == MAX_ROOT_LENGTH + 1

    # At-limit roots are accepted by the length gate. Lookup may yield a hazard
    # or an operational metadata error (for example ENAMETOOLONG); it must not
    # be reported as ROOT_LENGTH_LIMIT.
    at_result = run_pathaudit(pathaudit_bin, at_limit)
    assert at_result.returncode in (0, 1, 2)
    assert b"ROOT_LENGTH_LIMIT" not in at_result.stderr
    if at_result.returncode == 2:
        assert at_result.stdout == b""
        assert at_result.stderr.startswith(b"pathaudit: INSPECTION_ERROR_")
    else:
        assert at_result.stderr == b""

    over = run_pathaudit(pathaudit_bin, over_limit)
    assert over.returncode == 2
    assert over.stdout == b""
    assert over.stderr == diagnostic_lines("ROOT_LENGTH_LIMIT")


def test_root_count_limit(pathaudit_bin, fixture_tree):
    # Short relative operands keep argv under OS ARG_MAX while hitting the gate.
    at_result = run_pathaudit(
        pathaudit_bin, *(["."] * MAX_ROOT_COUNT), cwd=fixture_tree.cwd
    )
    assert at_result.returncode == 1
    assert at_result.stderr == b""
    assert b"ROOT_COUNT_LIMIT" not in at_result.stderr
    assert at_result.stdout.count(b"RELATIVE_ROOT\t") == MAX_ROOT_COUNT

    over = run_pathaudit(
        pathaudit_bin, *(["."] * (MAX_ROOT_COUNT + 1)), cwd=fixture_tree.cwd
    )
    assert over.returncode == 2
    assert over.stdout == b""
    assert over.stderr == diagnostic_lines("ROOT_COUNT_LIMIT")


def test_root_bytes_limit(pathaudit_bin):
    # Each root contributes len(root)+1 (NUL). Use max-length roots so a small
    # argv count crosses 1 MiB without relying on host PATH entries.
    chunk = b"/" + (b"b" * (MAX_ROOT_LENGTH - 1))
    assert len(chunk) == MAX_ROOT_LENGTH
    per_arg = len(chunk) + 1
    count = (MAX_ROOT_BYTES // per_arg) + 1
    args = [chunk] * count
    aggregate = sum(len(arg) + 1 for arg in args)
    assert aggregate > MAX_ROOT_BYTES
    assert count <= MAX_ROOT_COUNT

    result = run_pathaudit(pathaudit_bin, *args)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_lines("ROOT_BYTES_LIMIT")


def test_control_bytes_quotes_and_non_utf8_in_stdout_findings(pathaudit_bin, tmp_path):
    # TAB is the finding-record separator; LF would forge a second finding line.
    weird = tmp_path / os.fsdecode(
        b'diag-\n\tWORLD_WRITABLE\t"forged"-\x1b-\xff-"-\\-name'
    )
    # Missing path keeps the hazard on the operand text itself (stdout path).
    result = run_pathaudit(pathaudit_bin, str(weird.resolve()))
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout([("MISSING_ROOT", weird.resolve())])
    assert_no_raw_unsafe_bytes(result.stdout)
    assert b"\x1b" not in result.stdout
    assert b"\xff" not in result.stdout
    assert b'\\x09' in result.stdout
    assert b'\\x0A' in result.stdout
    # One structural CODE<TAB> separator only — operand TABs must be escaped.
    assert result.stdout.count(b"\t") == 1
    # One structural LF terminator only — operand LF must not split the record.
    assert result.stdout.count(b"\n") == 1
    assert result.stdout.endswith(b"\n")
    assert b"\nWORLD_WRITABLE" not in result.stdout


def test_closed_stdout_pipe_reports_stdout_write(
    pathaudit_bin, fixture_tree, tmp_path
):
    status, stderr = run_with_closed_stdout_pipe(pathaudit_bin, "--help")
    assert status == 2
    assert stderr == diagnostic_lines("STDOUT_WRITE")
    assert_no_raw_unsafe_bytes(stderr)

    # Hazard emission must also fail closed on a broken stdout pipe.
    status, stderr = run_with_closed_stdout_pipe(
        pathaudit_bin, str(fixture_tree.group_w)
    )
    assert status == 2
    assert stderr == diagnostic_lines("STDOUT_WRITE")
    assert_no_raw_unsafe_bytes(stderr)

    # --path SHADOWED emission must likewise exit 2 with STDOUT_WRITE and
    # release winner/shadow tables (including indexes) on the failure path.
    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    install_executable(early, "tool")
    install_executable(late, "tool")
    path_value = f"{early.resolve()}:{late.resolve()}:{late.resolve()}"
    status, stderr = run_with_closed_stdout_pipe(
        pathaudit_bin, "--path", env={"PATH": path_value}
    )
    assert status == 2
    assert stderr == diagnostic_lines("STDOUT_WRITE")
    assert_no_raw_unsafe_bytes(stderr)


def test_inspection_error_discards_buffered_findings(pathaudit_bin, tmp_path):
    # Name the loop so it sorts before the writable root; input order is reversed
    # to prove inspection follows sorted order and reject-closes stdout.
    early_loop = tmp_path / "a-loop"
    late_world = tmp_path / "z-world"
    partner = tmp_path / "a-loop-partner"
    early_loop.symlink_to(partner)
    partner.symlink_to(early_loop)
    late_world.mkdir()
    os.chmod(late_world, MODE_WORLD_WRITABLE)

    loop = str(early_loop.absolute())
    world = str(late_world.absolute())
    assert loop < world

    result = run_pathaudit(pathaudit_bin, world, loop)
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    assert result.stderr == diagnostic_lines(reason, loop)


def test_exit_status_classes(pathaudit_bin, fixture_tree):
    ok = run_pathaudit(pathaudit_bin, str(fixture_tree.private))
    assert ok.returncode == 0

    hazard = run_pathaudit(pathaudit_bin, str(fixture_tree.group_w))
    assert hazard.returncode == 1

    usage = run_pathaudit(pathaudit_bin)
    assert usage.returncode == 2


def test_runners_forward_sanitizer_options_without_reopening_path(monkeypatch):
    """Makefile ASan/UBSan knobs must reach the child; PATH must stay sealed."""

    monkeypatch.setenv("ASAN_OPTIONS", "detect_leaks=1:abort_on_error=1")
    monkeypatch.setenv("UBSAN_OPTIONS", "halt_on_error=1:print_stacktrace=1")
    monkeypatch.setenv("LSAN_OPTIONS", "verbosity=0")
    monkeypatch.setenv("ASAN_SYMBOLIZER_PATH", "/usr/bin/llvm-symbolizer")

    run_env = _base_child_env()
    assert run_env["PATH"] == "/pathaudit-tests-must-not-search-here"
    assert run_env["LC_ALL"] == "C"
    assert run_env["LANG"] == "C"
    assert run_env["ASAN_OPTIONS"] == "detect_leaks=1:abort_on_error=1"
    assert run_env["UBSAN_OPTIONS"] == "halt_on_error=1:print_stacktrace=1"
    assert run_env["LSAN_OPTIONS"] == "verbosity=0"
    assert run_env["ASAN_SYMBOLIZER_PATH"] == "/usr/bin/llvm-symbolizer"

    # Explicit caller env still overrides allowlisted keys without reopening PATH.
    overridden = _base_child_env({"ASAN_OPTIONS": "detect_leaks=0", "EXTRA": "1"})
    assert overridden["ASAN_OPTIONS"] == "detect_leaks=0"
    assert overridden["PATH"] == "/pathaudit-tests-must-not-search-here"
    assert overridden["EXTRA"] == "1"

    # PATH=None unsets for PATH_UNSET coverage; empty string remains set-but-empty.
    unset = _base_child_env({"PATH": None})
    assert "PATH" not in unset
    empty = _base_child_env({"PATH": ""})
    assert empty["PATH"] == ""


def test_run_pathaudit_forwards_sanitizer_options_to_real_child(
    tmp_path, monkeypatch
):
    """PAC-M3 integration: ASAN/UBSAN options reach the executed binary."""

    monkeypatch.setenv("ASAN_OPTIONS", "detect_leaks=1:abort_on_error=1")
    monkeypatch.setenv("UBSAN_OPTIONS", "halt_on_error=1:print_stacktrace=1")
    # Ensure ambient PATH-like noise cannot leak into the child.
    monkeypatch.setenv("HOST_ONLY_VAR", "must-not-appear")

    probe = tmp_path / "env-probe"
    probe.write_text(
        "#!/bin/sh\n"
        "printf 'ASAN=%s\\n' \"$ASAN_OPTIONS\"\n"
        "printf 'UBSAN=%s\\n' \"$UBSAN_OPTIONS\"\n"
        "printf 'PATH=%s\\n' \"$PATH\"\n"
        "if [ -n \"${HOST_ONLY_VAR+x}\" ]; then printf 'LEAKED\\n'; exit 2; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    probe.chmod(0o755)

    result = run_pathaudit(probe, "--version")
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        b"ASAN=detect_leaks=1:abort_on_error=1\n"
        b"UBSAN=halt_on_error=1:print_stacktrace=1\n"
        b"PATH=/pathaudit-tests-must-not-search-here\n"
    )
    assert b"LEAKED" not in result.stdout
    assert b"LEAKED" not in result.stderr


def _read_makefile() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def _makefile_target_block(makefile: str, target: str) -> str:
    """Return the header line plus tab-indented recipe for an exact target."""

    header_re = re.compile(rf"^{re.escape(target)}\s*:")
    lines = makefile.splitlines(keepends=True)
    start = None
    for index, line in enumerate(lines):
        if header_re.match(line):
            start = index
            break
    if start is None:
        raise AssertionError(f"Makefile is missing Make target {target!r}")

    collected = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("\t"):
            collected.append(line)
            continue
        # Stop at the next rule, variable, or directive; blank separators end
        # the recipe block for contract inspection.
        break
    return "".join(collected)


def _makefile_declares_phony(*targets: str) -> None:
    makefile = _read_makefile()
    lines = makefile.splitlines()
    phony_chunks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(".PHONY:"):
            chunk = [line]
            while chunk[-1].rstrip().endswith("\\"):
                index += 1
                if index >= len(lines):
                    break
                chunk.append(lines[index])
            phony_chunks.append(
                " ".join(part.rstrip("\\").strip() for part in chunk)
            )
        index += 1
    phony_text = "\n".join(phony_chunks)
    assert phony_chunks, "Makefile must declare .PHONY targets"
    for target in targets:
        assert re.search(
            rf"(?:^|[\s]){re.escape(target)}(?:[\s]|$)",
            phony_text,
        ), f"{target!r} must be listed in .PHONY"


def _make_dry_run(target: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("make") is None:
        pytest.skip("GNU make required for Makefile seam checks")
    return subprocess.run(
        ["make", "-C", str(ROOT), "-n", target],
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_temp_outside_workspace_with_cleanup(recipe: str, target: str) -> None:
    """Both quality targets must mktemp under /tmp and trap-clean every exit."""

    assert "mktemp" in recipe, f"{target} must create a temporary work directory"
    assert re.search(
        r"mktemp(?:\s+[^\n]*)?/tmp/",
        recipe,
    ), (
        f"{target} must create its temporary directory under /tmp "
        "(outside the workspace), not under an ambient TMPDIR"
    )
    assert "trap" in recipe, f"{target} must install a cleanup trap"
    assert "rm -rf" in recipe, f"{target} must remove its temporary directory"
    assert re.search(
        r"trap\s+'[^']*rm\s+-rf[^']*'\s+EXIT",
        recipe,
    ) or re.search(
        r'trap\s+"[^"]*rm\s+-rf[^"]*"\s+EXIT',
        recipe,
    ), f"{target} must clean temporary paths on EXIT (success and failure)"
    # Do not emit a durable workspace pathaudit binary from these gates.
    assert "build/pathaudit" not in recipe
    assert not re.search(
        r"(?:^|[^\w-])-o\s+(?:\$\(CURDIR\)/)?(?:\./)?pathaudit(?:\s|$)",
        recipe,
        flags=re.MULTILINE,
    ), f"{target} must not write a top-level ./pathaudit workspace binary"


def test_makefile_test_suite_scrubs_inherited_pathaudit_routing():
    """PAC-M1: make -n test-suite must scrub ambient PATHAUDIT / PERMGUARD routing."""

    if shutil.which("make") is None:
        pytest.skip("GNU make required for Makefile seam checks")

    makefile = _read_makefile()
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in makefile
    assert "-u PERMGUARD_BIN -u PERMGUARD_UNDER_VALGRIND" in makefile
    assert 'SYSDIFF_BIN="$(CURDIR)/$(BIN)"' in makefile

    dry = _make_dry_run("test-suite")
    assert dry.returncode == 0, dry.stderr + dry.stdout
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in dry.stdout
    assert "-u PERMGUARD_BIN -u PERMGUARD_UNDER_VALGRIND" in dry.stdout
    assert "SYSDIFF_BIN=" in dry.stdout


def test_inherited_pathaudit_bin_decoy_fails_unless_scrubbed(tmp_path):
    """PAC-M1 regression: a stale PATHAUDIT_BIN decoy must not silently pass.

    Exercises the real fixture PATHAUDIT_BIN seam (not a mocked subprocess
    boundary). The Makefile scrub is pinned separately; this proves the old
    failure class when the override is left in place.
    """

    decoy = tmp_path / "decoy-pathaudit"
    decoy.write_text(
        "#!/bin/sh\nprintf 'wrong\\n'\nexit 0\n",
        encoding="utf-8",
    )
    decoy.chmod(0o755)

    env = os.environ.copy()
    env["PATHAUDIT_BIN"] = str(decoy)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Drop Valgrind wrapping so the decoy is executed directly.
    env.pop("PATHAUDIT_UNDER_VALGRIND", None)
    env.pop("SYSDIFF_UNDER_VALGRIND", None)

    poisoned = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/test_pathaudit.py::test_safe_private_absolute_root_exits_zero",
            "-q",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert poisoned.returncode != 0, poisoned.stdout + poisoned.stderr
    assert "FAILED" in poisoned.stdout or "failed" in poisoned.stdout.lower()

    scrubbed = subprocess.run(
        [
            "env",
            "-u",
            "PATHAUDIT_BIN",
            "-u",
            "PATHAUDIT_UNDER_VALGRIND",
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/test_pathaudit.py::test_safe_private_absolute_root_exits_zero",
            "-q",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert scrubbed.returncode == 0, scrubbed.stdout + scrubbed.stderr


def test_makefile_release_and_distcheck_require_pathaudit_members():
    makefile = _read_makefile()
    for required in (
        "src/pathaudit.c",
        "man/pathaudit.1",
        "tests/test_pathaudit.py",
    ):
        assert required in makefile
    # Release staging required-file loop must name pathaudit members explicitly.
    # permguard remains outside the published release/dist required-member loops
    # for this unreleased bootstrap (PG-NG-3); quality/man/sanitize surfaces cover it.
    release_idx = makefile.index("error: release staging missing required product file")
    release_window = makefile[max(0, release_idx - 500) : release_idx]
    assert "src/pathaudit.c" in release_window
    assert "man/pathaudit.1" in release_window
    assert "tests/test_pathaudit.py" in release_window
    dist_idx = makefile.index("error: archive missing required member")
    dist_window = makefile[max(0, dist_idx - 700) : dist_idx]
    assert "src/pathaudit.c" in dist_window
    assert "man/pathaudit.1" in dist_window
    assert "tests/test_pathaudit.py" in dist_window


def test_pathaudit_bin_relative_override_resolves_before_cwd_changes(
    tmp_path_factory, monkeypatch
):
    """Relative PATHAUDIT_BIN must resolve via the shared fixture helper."""

    build_dir = tmp_path_factory.mktemp("pathaudit-rel-bin")
    binary = build_dir / "pathaudit"
    compile_result = subprocess.run(
        [
            os.environ.get("CC", "cc"),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-o",
            str(binary),
            str(SRC),
        ],
        capture_output=True,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    rel = os.path.relpath(binary, Path.cwd())
    assert not Path(rel).is_absolute()
    monkeypatch.setenv("PATHAUDIT_BIN", rel)

    # Call the same helper the pathaudit_bin fixture uses (mutation pin).
    resolved = resolve_pathaudit_override(os.environ["PATHAUDIT_BIN"])
    assert resolved == binary.resolve()
    assert resolved.is_absolute()
    assert resolved.is_file()

    foreign_cwd = tmp_path_factory.mktemp("foreign-cwd")
    result = run_pathaudit(resolved, "--version", cwd=foreign_cwd)
    assert result.returncode == 0
    assert result.stdout == VERSION_STDOUT


def test_relative_pathaudit_bin_fixture_survives_foreign_cwd(tmp_path):
    """PAH-1: nested pytest must exercise the real pathaudit_bin fixture resolve.

    A relative PATHAUDIT_BIN that is not resolved at fixture time validates
    against the suite cwd but fails under any test that passes cwd= to Popen.
    """

    binary = tmp_path / "pathaudit"
    compile_result = subprocess.run(
        [
            os.environ.get("CC", "cc"),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-o",
            str(binary),
            str(SRC),
        ],
        capture_output=True,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    rel = os.path.relpath(binary, ROOT)
    assert not Path(rel).is_absolute()

    env = os.environ.copy()
    env["PATHAUDIT_BIN"] = rel
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PATHAUDIT_UNDER_VALGRIND", None)
    env.pop("SYSDIFF_UNDER_VALGRIND", None)

    nested = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/test_pathaudit.py::test_safe_private_absolute_root_exits_zero",
            "-q",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert nested.returncode == 0, nested.stdout + nested.stderr


def test_makefile_declares_stable_pathaudit_sanitize_and_valgrind_targets():
    """Stable Make target names for pathaudit-only sanitizer/Valgrind gates."""

    makefile = _read_makefile()
    sanitize = _makefile_target_block(makefile, PATHAUDIT_SANITIZE_TARGET)
    valgrind = _makefile_target_block(makefile, PATHAUDIT_VALGRIND_TARGET)
    assert sanitize.strip(), f"{PATHAUDIT_SANITIZE_TARGET} recipe must not be empty"
    assert valgrind.strip(), f"{PATHAUDIT_VALGRIND_TARGET} recipe must not be empty"
    _makefile_declares_phony(PATHAUDIT_SANITIZE_TARGET, PATHAUDIT_VALGRIND_TARGET)


def test_makefile_pathaudit_sanitize_builds_and_runs_with_asan_ubsan():
    """pathaudit-sanitize: ASan+UBSan, strict warnings, frame pointers, execute."""

    makefile = _read_makefile()
    recipe = _makefile_target_block(makefile, PATHAUDIT_SANITIZE_TARGET)
    joined = recipe.replace("\\\n", " ")

    for flag in STRICT_WARNING_FLAGS:
        assert flag in joined or flag in makefile, (
            f"{PATHAUDIT_SANITIZE_TARGET} must compile with strict warning flag {flag}"
        )
    # Allow either separate -fsanitize=address / =undefined or a combined form.
    has_asan = (
        "-fsanitize=address" in joined
        or re.search(r"-fsanitize=[^\s]*address", joined) is not None
    )
    has_ubsan = (
        "-fsanitize=undefined" in joined
        or re.search(r"-fsanitize=[^\s]*undefined", joined) is not None
    )
    # Variable-indirection form: $(ASAN_CFLAGS) / $(UBSAN_CFLAGS) expand the flags.
    if "ASAN_CFLAGS" in joined:
        has_asan = has_asan or "-fsanitize=address" in makefile
    if "UBSAN_CFLAGS" in joined:
        has_ubsan = has_ubsan or "-fsanitize=undefined" in makefile
    if "ASAN_CFLAGS" in joined and "UBSAN_CFLAGS" in joined:
        # Two-phase recipes still satisfy the combined sanitizer contract.
        pass
    assert has_asan, (
        f"{PATHAUDIT_SANITIZE_TARGET} must build pathaudit with AddressSanitizer"
    )
    assert has_ubsan, (
        f"{PATHAUDIT_SANITIZE_TARGET} must build pathaudit with "
        "UndefinedBehaviorSanitizer"
    )
    assert FRAME_POINTER_FLAG in joined or (
        FRAME_POINTER_FLAG in makefile
        and ("ASAN_CFLAGS" in joined or "UBSAN_CFLAGS" in joined)
    ), f"{PATHAUDIT_SANITIZE_TARGET} must retain frame pointers"

    assert "PATHAUDIT_SRC" in joined or "src/pathaudit.c" in joined, (
        f"{PATHAUDIT_SANITIZE_TARGET} must compile the existing pathaudit source"
    )
    # Must execute the instrumented binary (representative pathaudit flow).
    assert re.search(r"\bpathaudit(?:-asan|-ubsan|-sanitize)?\b", joined), (
        f"{PATHAUDIT_SANITIZE_TARGET} must reference the instrumented pathaudit binary"
    )
    assert "--help" in joined or "--version" in joined, (
        f"{PATHAUDIT_SANITIZE_TARGET} must run a representative pathaudit invocation"
    )

    _assert_temp_outside_workspace_with_cleanup(joined, PATHAUDIT_SANITIZE_TARGET)

    dry = _make_dry_run(PATHAUDIT_SANITIZE_TARGET)
    assert dry.returncode == 0, dry.stderr + dry.stdout
    dry_out = dry.stdout
    assert (
        "-fsanitize=address" in dry_out
        or "address" in dry_out.lower()
        or "ASAN" in dry_out
    )
    assert (
        "-fsanitize=undefined" in dry_out
        or "undefined" in dry_out.lower()
        or "UBSAN" in dry_out
    )
    assert FRAME_POINTER_FLAG in dry_out
    for flag in ("-Wall", "-Wextra", "-Wpedantic", "-Werror"):
        assert flag in dry_out
    assert "src/pathaudit.c" in dry_out or "pathaudit.c" in dry_out
    assert "mktemp" in dry_out
    assert "trap" in dry_out


def test_makefile_pathaudit_valgrind_uses_nonsanitized_debug_with_leak_check():
    """pathaudit-valgrind: separate debug binary, leak check, nonzero exitcode."""

    makefile = _read_makefile()
    recipe = _makefile_target_block(makefile, PATHAUDIT_VALGRIND_TARGET)
    joined = recipe.replace("\\\n", " ")

    for flag in STRICT_WARNING_FLAGS:
        assert flag in joined or (
            "VALGRIND_CFLAGS" in joined and flag in makefile
        ), f"{PATHAUDIT_VALGRIND_TARGET} must use strict warning flag {flag}"
    assert "-g" in joined or (
        "VALGRIND_CFLAGS" in joined and "-g" in makefile
    ), f"{PATHAUDIT_VALGRIND_TARGET} must build a debug executable"
    assert FRAME_POINTER_FLAG in joined or (
        "VALGRIND_CFLAGS" in joined and FRAME_POINTER_FLAG in makefile
    ), f"{PATHAUDIT_VALGRIND_TARGET} must retain frame pointers"

    # Separate non-sanitized binary: the Valgrind recipe must not enable sanitizers.
    assert "-fsanitize=" not in joined, (
        f"{PATHAUDIT_VALGRIND_TARGET} must use a non-sanitized debug executable"
    )
    assert "ASAN_CFLAGS" not in joined
    assert "UBSAN_CFLAGS" not in joined

    assert "valgrind" in joined, (
        f"{PATHAUDIT_VALGRIND_TARGET} must run the binary under Valgrind"
    )
    assert "--leak-check=full" in joined, (
        f"{PATHAUDIT_VALGRIND_TARGET} must enable full leak checking"
    )
    assert "--show-leak-kinds=all" in joined, (
        f"{PATHAUDIT_VALGRIND_TARGET} must show all leak kinds"
    )
    exitcode_match = re.search(r"--error-exitcode=(\d+)", joined)
    assert exitcode_match is not None, (
        f"{PATHAUDIT_VALGRIND_TARGET} must set a Valgrind --error-exitcode"
    )
    assert int(exitcode_match.group(1)) != 0, (
        f"{PATHAUDIT_VALGRIND_TARGET} must use a nonzero Valgrind error-exitcode"
    )

    assert "PATHAUDIT_SRC" in joined or "src/pathaudit.c" in joined, (
        f"{PATHAUDIT_VALGRIND_TARGET} must compile the existing pathaudit source"
    )
    assert re.search(r"\bpathaudit(?:-valgrind)?\b", joined), (
        f"{PATHAUDIT_VALGRIND_TARGET} must reference the Valgrind pathaudit binary"
    )
    assert "--help" in joined or "--version" in joined, (
        f"{PATHAUDIT_VALGRIND_TARGET} must run a representative pathaudit invocation"
    )

    _assert_temp_outside_workspace_with_cleanup(joined, PATHAUDIT_VALGRIND_TARGET)

    dry = _make_dry_run(PATHAUDIT_VALGRIND_TARGET)
    assert dry.returncode == 0, dry.stderr + dry.stdout
    dry_out = dry.stdout
    assert "valgrind" in dry_out
    assert "--leak-check=full" in dry_out
    assert "--show-leak-kinds=all" in dry_out
    dry_exit = re.search(r"--error-exitcode=(\d+)", dry_out)
    assert dry_exit is not None and int(dry_exit.group(1)) != 0
    assert "-fsanitize=" not in dry_out
    assert FRAME_POINTER_FLAG in dry_out
    assert "-g" in dry_out
    for flag in ("-Wall", "-Wextra", "-Wpedantic", "-Werror"):
        assert flag in dry_out
    assert "src/pathaudit.c" in dry_out or "pathaudit.c" in dry_out
    assert "mktemp" in dry_out
    assert "trap" in dry_out


def test_makefile_pathaudit_quality_targets_preserve_existing_make_surface():
    """New pathaudit gates must not regress existing Make targets or wiring."""

    makefile = _read_makefile()
    for target in (
        "pathaudit",
        "test-sanitize",
        "test-asan",
        "test-ubsan",
        "test-valgrind",
        "test-suite",
        "gcc-strict",
        "clang-strict",
        "quality",
    ):
        block = _makefile_target_block(makefile, target)
        assert block.strip(), f"existing Make target {target!r} must remain"

    # Existing memory gates must still compile pathaudit under mktemp.
    asan = _makefile_target_block(makefile, "test-asan")
    ubsan = _makefile_target_block(makefile, "test-ubsan")
    valgrind = _makefile_target_block(makefile, "test-valgrind")
    for name, recipe in (
        ("test-asan", asan),
        ("test-ubsan", ubsan),
        ("test-valgrind", valgrind),
    ):
        assert "PATHAUDIT_SRC" in recipe or "src/pathaudit.c" in recipe, (
            f"{name} must keep compiling pathaudit"
        )
        assert "PERMGUARD_SRC" in recipe or "src/permguard.c" in recipe, (
            f"{name} must keep compiling permguard"
        )
        assert "mktemp" in recipe
        assert "trap" in recipe
        assert "PATHAUDIT_BIN" in recipe
        assert "PERMGUARD_BIN" in recipe

    # Non-writing default pathaudit recipe remains (no workspace binary).
    pathaudit_recipe = _makefile_target_block(makefile, "pathaudit")
    assert "mktemp" in pathaudit_recipe
    assert "trap" in pathaudit_recipe
    assert "build/pathaudit" not in pathaudit_recipe

    # Non-writing default permguard recipe remains (no workspace binary).
    permguard_recipe = _makefile_target_block(makefile, "permguard")
    assert "mktemp" in permguard_recipe
    assert "trap" in permguard_recipe
    assert "build/permguard" not in permguard_recipe

    # Existing scrub / routing contracts stay intact.
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in makefile
    assert "-u PERMGUARD_BIN -u PERMGUARD_UNDER_VALGRIND" in makefile
    test_suite = _makefile_target_block(makefile, "test-suite")
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in test_suite
    assert "-u PERMGUARD_BIN -u PERMGUARD_UNDER_VALGRIND" in test_suite

    # Dry-run pins: existing targets still expand without error.
    for target in ("pathaudit", "permguard", "test-asan", "test-valgrind", "test-suite"):
        dry = _make_dry_run(target)
        assert dry.returncode == 0, f"{target}: {dry.stderr + dry.stdout}"


def test_pathaudit_behavior_contract_pins_remain_stable():
    """Protect existing pathaudit CLI/hazard contract surface from drift."""

    assert HELP_STDOUT == (
        b"usage: pathaudit [--] ROOT...\n"
        b"   or: pathaudit --path\n"
        b"   or: pathaudit --command NAME\n"
        b"Scan PATH directory roots for hazards.\n"
    )
    assert USAGE_SYNOPSIS == (
        b"usage: pathaudit [--] ROOT...\n"
        b"   or: pathaudit --path\n"
        b"   or: pathaudit --command NAME\n"
    )
    assert USAGE_LINE == USAGE_SYNOPSIS
    assert VERSION_STDOUT == b"pathaudit 0.1.0\n"
    assert CODE_RANK == (
        "EMPTY_ROOT",
        "RELATIVE_ROOT",
        "MISSING_ROOT",
        "NON_DIRECTORY_ROOT",
        "GROUP_WRITABLE",
        "WORLD_WRITABLE",
        "UNSAFE_OWNER",
    )
    assert DIRECTORY_CODE_RANK == CODE_RANK
    assert EXECUTABLE_ONLY_CODES == frozenset()
    assert MAX_ROOT_COUNT == 65536
    assert MAX_ROOT_LENGTH == 65536
    assert MAX_ROOT_BYTES == 1024 * 1024
    assert escape_root(b"a\npathaudit: FORGED") == b'"a\\x0Apathaudit: FORGED"'
    assert finding_line("EMPTY_ROOT", b"") == b'EMPTY_ROOT\t""\n'
    assert finding_line("UNSAFE_OWNER", "/tmp/tool") == (
        b'UNSAFE_OWNER\t"/tmp/tool"\n'
    )
    assert match_line("/tmp/tool") == b'MATCH\t"/tmp/tool"\n'
    assert diagnostic_lines("PATH_UNSET") == b"pathaudit: PATH_UNSET\n"
    assert diagnostic_lines("INVALID_COMMAND", "a/b") == (
        b'pathaudit: INVALID_COMMAND: "a/b"\n'
    )
    assert diagnostic_lines("USAGE") == (
        b"pathaudit: USAGE\n" + USAGE_SYNOPSIS
    )
    assert SRC.is_file()
    assert MAKEFILE.is_file()


# ---------------------------------------------------------------------------
# Bounded command-specific PATH risk inspection (`pathaudit --command NAME`)
#
# Authored ahead of implementation. Encodes: PATH-order MATCH lines for one
# basename, applicable existing PATH hazards only (no unrelated basename
# flood), missing commands, repeated PATH entries, shadowing, unsafe or
# malformed PATH entries in the existing risk model, invalid query arguments,
# diagnostics, and exit status. Existing no-argument USAGE behavior remains
# covered by test_usage_errors_for_missing_roots_and_unknown_options.
# ---------------------------------------------------------------------------


def test_command_mode_single_private_match_exits_zero(pathaudit_bin, fixture_tree):
    cmd = "tool"
    exe = install_executable(fixture_tree.private, cmd)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private), cwd=fixture_tree.cwd
    )
    code, expected = expect_command_query(
        [exe], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_reports_matches_in_path_resolution_order(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    first = install_executable(fixture_tree.private, cmd)
    second = install_executable(fixture_tree.group_w, cmd)
    path_value = f"{fixture_tree.private}:{fixture_tree.group_w}"
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, path_value, cwd=fixture_tree.cwd
    )
    # First MATCH wins; second is a shadow. GROUP_WRITABLE applies to the
    # match-bearing later component.
    code, expected = expect_command_query(
        [first, second],
        [(1, fixture_tree.group_w, "GROUP_WRITABLE")],
        [(0, fixture_tree.private), (1, fixture_tree.group_w)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_shadowing_across_safe_directories_exits_zero(
    pathaudit_bin, tmp_path
):
    """Multiple private matches are reported in order without hazard noise."""

    early = tmp_path / "early"
    late = tmp_path / "late"
    early.mkdir()
    late.mkdir()
    os.chmod(tmp_path, MODE_PRIVATE)
    os.chmod(early, MODE_PRIVATE)
    os.chmod(late, MODE_PRIVATE)
    cmd = "shadowed"
    first = install_executable(early, cmd)
    second = install_executable(late, cmd)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, f"{early.resolve()}:{late.resolve()}"
    )
    code, expected = expect_command_query(
        [first, second],
        [],
        [(0, early.resolve()), (1, late.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # Winner is the first PATH hit.
    assert result.stdout.startswith(match_line(first))


def test_command_mode_does_not_flood_unrelated_basename_collisions(
    pathaudit_bin, tmp_path
):
    """Querying one command must not list other executables in the same dirs."""

    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    os.chmod(tmp_path, MODE_PRIVATE)
    os.chmod(d1, MODE_PRIVATE)
    os.chmod(d2, MODE_PRIVATE)

    wanted = install_executable(d1, "wanted")
    install_executable(d1, "unrelated-a")
    install_executable(d1, "unrelated-b")
    install_executable(d2, "unrelated-c")
    install_executable(d2, "wanted")
    second = (d2 / "wanted").resolve()

    result = run_pathaudit_command_mode(
        pathaudit_bin, "wanted", f"{d1.resolve()}:{d2.resolve()}"
    )
    code, expected = expect_command_query(
        [wanted, second],
        [],
        [(0, d1.resolve()), (1, d2.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    for noise in (b"unrelated-a", b"unrelated-b", b"unrelated-c"):
        assert noise not in result.stdout


def test_command_mode_missing_command_on_clean_path_exits_zero(
    pathaudit_bin, fixture_tree
):
    result = run_pathaudit_command_mode(
        pathaudit_bin, "absent-tool", str(fixture_tree.private)
    )
    # No MATCH, but the consulted PATH directory still receives ownership audit.
    code, expected = expect_command_query(
        [], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stderr == b""


def test_command_mode_non_executable_same_basename_is_not_a_match(
    pathaudit_bin, fixture_tree
):
    decoy = fixture_tree.private / "tool"
    decoy.write_bytes(b"not-executable\n")
    os.chmod(decoy, 0o644)
    result = run_pathaudit_command_mode(
        pathaudit_bin, "tool", str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stderr == b""


def test_command_mode_directory_same_basename_is_not_a_match(
    pathaudit_bin, fixture_tree
):
    named = fixture_tree.private / "tool"
    named.mkdir()
    os.chmod(named, MODE_PRIVATE)
    result = run_pathaudit_command_mode(
        pathaudit_bin, "tool", str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stderr == b""


def test_command_mode_repeated_path_entries_preserve_match_positions(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    exe = install_executable(fixture_tree.private, cmd)
    root = str(fixture_tree.private)
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, f"{root}:{root}")
    code, expected = expect_command_query(
        [exe, exe], [], [(0, root), (1, root)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_writable_earlier_entry_is_applicable_plant_risk(
    pathaudit_bin, fixture_tree
):
    """A writable absolute dir before the winner is applicable even without a hit."""

    cmd = "tool"
    winner = install_executable(fixture_tree.private, cmd)
    # world_w has no matching executable; it still precedes the winner.
    path_value = f"{fixture_tree.world_w}:{fixture_tree.private}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    code, expected = expect_command_query(
        [winner],
        [(0, fixture_tree.world_w, "WORLD_WRITABLE")],
        [(0, fixture_tree.world_w), (1, fixture_tree.private)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_skips_unrelated_absolute_missing_before_winner(
    pathaudit_bin, fixture_tree
):
    """Absolute MISSING_ROOT before a clean winner must not flood command output."""

    cmd = "tool"
    winner = install_executable(fixture_tree.private, cmd)
    path_value = f"{fixture_tree.missing}:{fixture_tree.private}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    code, expected = expect_command_query(
        [winner], [], [(1, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"MISSING_ROOT" not in result.stdout


def test_command_mode_skips_unrelated_absolute_nondirectory_before_winner(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    winner = install_executable(fixture_tree.private, cmd)
    path_value = f"{fixture_tree.regular}:{fixture_tree.private}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    code, expected = expect_command_query(
        [winner], [], [(1, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"NON_DIRECTORY_ROOT" not in result.stdout


def test_command_mode_writable_after_winner_without_match_is_not_applicable(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    winner = install_executable(fixture_tree.private, cmd)
    path_value = f"{fixture_tree.private}:{fixture_tree.world_w}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    # Later world_w without a match is not applicable; winner dir still is.
    code, expected = expect_command_query(
        [winner], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"WORLD_WRITABLE" not in result.stdout
    assert finding_line("UNSAFE_OWNER", fixture_tree.world_w) not in result.stdout


def test_command_mode_match_in_writable_directory_reports_permission(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    # Executable itself is writability-trusted and current-user owned; the
    # match-bearing directory may still report GROUP/WORLD_WRITABLE plus
    # PATH/ancestor UNSAFE_OWNER under the shared trust policy.
    exe = install_executable(
        fixture_tree.both_w, cmd, mode=MODE_EXE_TRUSTED
    )
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.both_w)
    )
    code, expected = expect_command_query(
        [exe],
        [
            (0, fixture_tree.both_w, "GROUP_WRITABLE"),
            (0, fixture_tree.both_w, "WORLD_WRITABLE"),
        ],
        [(0, fixture_tree.both_w)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # Permission findings name the directory, not the trusted executable.
    assert finding_line("GROUP_WRITABLE", exe) not in result.stdout
    assert finding_line("WORLD_WRITABLE", exe) not in result.stdout
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_empty_and_relative_path_entries_remain_applicable(
    pathaudit_bin, fixture_tree
):
    """Empty/relative PATH fields stay cwd-dependent hazards for the query."""

    cmd = "tool"
    cwd = fixture_tree.cwd
    bin_dir = cwd / "bin"
    bin_dir.mkdir()
    os.chmod(bin_dir, MODE_PRIVATE)
    via_rel = install_executable(bin_dir, cmd)
    via_cwd = install_executable(cwd, cmd)

    # Empty component searches cwd; relative `bin` searches cwd/bin.
    path_value = f":bin:{fixture_tree.private}"
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, path_value, cwd=cwd
    )
    code, expected = expect_command_query(
        [via_cwd, via_rel],
        [
            (0, b"", "EMPTY_ROOT"),
            (1, "bin", "RELATIVE_ROOT"),
        ],
        [(0, cwd), (1, bin_dir.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # Private absolute without a match is not plant-risk applicable.
    assert escape_root(fixture_tree.private) not in result.stdout


def test_command_mode_missing_command_still_reports_cwd_dependent_hazards(
    pathaudit_bin, fixture_tree
):
    path_value = f":rel-missing:{fixture_tree.private}"
    result = run_pathaudit_command_mode(
        pathaudit_bin, "absent-tool", path_value, cwd=fixture_tree.cwd
    )
    code, expected = expect_command_query(
        [],
        [
            (0, b"", "EMPTY_ROOT"),
            (1, "rel-missing", "RELATIVE_ROOT"),
            (1, "rel-missing", "MISSING_ROOT"),
        ],
        [(0, fixture_tree.cwd), (2, fixture_tree.private)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"MATCH\t" not in result.stdout


def test_command_mode_symlink_executable_counts_as_match(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    real = install_executable(fixture_tree.private, cmd)
    link_dir = fixture_tree.root / "link-dir"
    link_dir.mkdir()
    os.chmod(link_dir, MODE_PRIVATE)
    link = link_dir / cmd
    link.symlink_to(real)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(link_dir.resolve())
    )
    code, expected = expect_command_query(
        [link.resolve()], [], [(0, link_dir.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_unset_path_is_reject_closed(pathaudit_bin):
    result = run_pathaudit_command_mode(pathaudit_bin, "tool", None)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_lines("PATH_UNSET")
    assert b"usage:" not in result.stderr


def test_command_mode_rejects_missing_name_and_extra_operands(
    pathaudit_bin, fixture_tree
):
    missing_name = run_pathaudit(
        pathaudit_bin,
        "--command",
        env={"PATH": str(fixture_tree.private)},
    )
    assert missing_name.returncode == 2
    assert missing_name.stdout == b""
    assert missing_name.stderr == diagnostic_lines("USAGE")

    extra = run_pathaudit_command_mode(
        pathaudit_bin,
        "tool",
        str(fixture_tree.private),
        "extra",
    )
    assert extra.returncode == 2
    assert extra.stdout == b""
    assert extra.stderr == diagnostic_lines("USAGE")


def test_command_mode_rejects_mixture_with_path_and_roots(
    pathaudit_bin, fixture_tree
):
    with_path = run_pathaudit(
        pathaudit_bin,
        "--command",
        "tool",
        "--path",
        env={"PATH": str(fixture_tree.private)},
    )
    assert with_path.returncode == 2
    assert with_path.stdout == b""
    assert with_path.stderr == diagnostic_lines("USAGE")

    path_then_command = run_pathaudit(
        pathaudit_bin,
        "--path",
        "--command",
        "tool",
        env={"PATH": str(fixture_tree.private)},
    )
    assert path_then_command.returncode == 2
    assert path_then_command.stdout == b""
    assert path_then_command.stderr == diagnostic_lines("USAGE")

    with_root = run_pathaudit(
        pathaudit_bin,
        "--command",
        "tool",
        str(fixture_tree.private),
        env={"PATH": str(fixture_tree.private)},
    )
    assert with_root.returncode == 2
    assert with_root.stdout == b""
    assert with_root.stderr == diagnostic_lines("USAGE")


def test_command_mode_rejects_empty_and_path_like_command_names(
    pathaudit_bin, fixture_tree
):
    empty = run_pathaudit_command_mode(
        pathaudit_bin, b"", str(fixture_tree.private)
    )
    assert empty.returncode == 2
    assert empty.stdout == b""
    assert empty.stderr == diagnostic_lines("INVALID_COMMAND", b"")
    assert b"usage:" not in empty.stderr

    nested = run_pathaudit_command_mode(
        pathaudit_bin, "foo/bar", str(fixture_tree.private)
    )
    assert nested.returncode == 2
    assert nested.stdout == b""
    assert nested.stderr == diagnostic_lines("INVALID_COMMAND", "foo/bar")

    abs_like = run_pathaudit_command_mode(
        pathaudit_bin, "/bin/tool", str(fixture_tree.private)
    )
    assert abs_like.returncode == 2
    assert abs_like.stdout == b""
    assert abs_like.stderr == diagnostic_lines("INVALID_COMMAND", "/bin/tool")

    dotted = run_pathaudit_command_mode(
        pathaudit_bin, "../tool", str(fixture_tree.private)
    )
    assert dotted.returncode == 2
    assert dotted.stdout == b""
    assert dotted.stderr == diagnostic_lines("INVALID_COMMAND", "../tool")


def test_command_mode_accepts_leading_dash_command_name(
    pathaudit_bin, fixture_tree
):
    cmd = "-dash-tool"
    exe = install_executable(fixture_tree.private, cmd)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [exe], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_escapes_hostile_command_name_in_diagnostics(
    pathaudit_bin, fixture_tree
):
    hostile = os.fsdecode(b'bad-\n\tpathaudit: FORGED-\x1b-\xff/"-\\-name')
    # Slash makes it path-like -> INVALID_COMMAND with escaped operand.
    result = run_pathaudit_command_mode(
        pathaudit_bin, hostile, str(fixture_tree.private)
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_lines("INVALID_COMMAND", hostile)
    assert_no_raw_unsafe_bytes(result.stderr)
    assert b"\npathaudit: FORGED" not in result.stderr
    assert result.stderr.count(b"\n") == 1


def test_command_mode_match_path_escaping_on_stdout(pathaudit_bin, tmp_path):
    weird_dir = tmp_path / os.fsdecode(b'dir-\n\tMATCH\t"forged"-\x1b-\xff')
    weird_dir.mkdir()
    os.chmod(tmp_path, MODE_PRIVATE)
    os.chmod(weird_dir, MODE_PRIVATE)
    exe = install_executable(weird_dir, "tool")
    result = run_pathaudit_command_mode(
        pathaudit_bin, "tool", str(weird_dir.resolve())
    )
    code, expected = expect_command_query(
        [exe], [], [(0, weird_dir.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert_no_raw_unsafe_bytes(result.stdout)
    # Escaped MATCH path must not introduce raw control separators; ownership
    # may add further finding lines under the shared trust policy.
    assert b"\nMATCH\t" not in result.stdout
    assert result.stdout.startswith(b"MATCH\t")


def test_command_mode_preserves_no_argument_usage_behavior(pathaudit_bin):
    """Existing no-operand invocation remains a USAGE error (exit 2)."""

    no_args = run_pathaudit(pathaudit_bin)
    assert no_args.returncode == 2
    assert no_args.stdout == b""
    assert no_args.stderr == diagnostic_lines("USAGE")


def test_command_mode_exit_status_classes(pathaudit_bin, fixture_tree):
    cmd = "tool"
    install_executable(fixture_tree.private, cmd)
    install_executable(fixture_tree.world_w, cmd)

    ok = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private)
    )
    ok_code, _ = expect_command_query(
        [fixture_tree.private / cmd], [], [(0, fixture_tree.private)]
    )
    assert ok.returncode == ok_code

    hazard = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.world_w)
    )
    assert hazard.returncode == 1

    unset = run_pathaudit_command_mode(pathaudit_bin, cmd, None)
    assert unset.returncode == 2
    assert unset.stderr == diagnostic_lines("PATH_UNSET")

    invalid = run_pathaudit_command_mode(
        pathaudit_bin, "a/b", str(fixture_tree.private)
    )
    assert invalid.returncode == 2
    assert invalid.stderr == diagnostic_lines("INVALID_COMMAND", "a/b")

    usage = run_pathaudit(
        pathaudit_bin, "--command", env={"PATH": str(fixture_tree.private)}
    )
    assert usage.returncode == 2
    assert usage.stderr == diagnostic_lines("USAGE")


def test_command_mode_inspection_error_on_loop_component_reject_closes(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    install_executable(fixture_tree.private, cmd)
    # Loop sorts before private by path bytes when under the same parent; use
    # the fixture loop as the sole earlier component.
    path_value = f"{fixture_tree.loop_a}:{fixture_tree.private}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    assert result.stderr == diagnostic_lines(reason, fixture_tree.loop_a)


def test_command_mode_does_not_alter_explicit_root_relative_operands(
    pathaudit_bin, fixture_tree
):
    """Bare relative operands remain explicit-root mode, not command query."""

    result = run_pathaudit(
        pathaudit_bin, "rel-missing", cwd=fixture_tree.cwd
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [
            ("RELATIVE_ROOT", "rel-missing"),
            ("MISSING_ROOT", "rel-missing"),
        ]
    )
    assert b"MATCH\t" not in result.stdout


def test_command_mode_mixed_shadow_and_plant_risk_deterministic(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    early_private = install_executable(fixture_tree.private, cmd)
    late_world = install_executable(fixture_tree.world_w, cmd)
    # Missing absolute between them must stay silent; group_w before winner
    # without a hit is applicable plant risk.
    path_value = ":".join(
        [
            str(fixture_tree.group_w),
            str(fixture_tree.missing),
            str(fixture_tree.private),
            str(fixture_tree.world_w),
        ]
    )
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    code, expected = expect_command_query(
        [early_private, late_world],
        [
            (0, fixture_tree.group_w, "GROUP_WRITABLE"),
            (3, fixture_tree.world_w, "WORLD_WRITABLE"),
        ],
        [
            (0, fixture_tree.group_w),
            (2, fixture_tree.private),
            (3, fixture_tree.world_w),
        ],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"MISSING_ROOT" not in result.stdout
    assert b"unrelated" not in result.stdout


# ---------------------------------------------------------------------------
# Detect executable shadowing across PATH entries (`pathaudit --path`)
#
# Additive contract: when two or more distinct PATH directories each contain a
# regular executable with the same basename, report each later *distinct*
# realpath as shadowed against the first-PATH winner. Uniqueness is by
# (command, winner realpath, shadow realpath): exact duplicate tuples emit
# once; genuinely distinct later realpaths still emit one row each.
#
# Line shape (TAB-separated, quote-escaped fields):
#   SHADOWED<TAB>"COMMAND"<TAB>"WINNER_REALPATH"<TAB>"SHADOWED_REALPATH"<LF>
#
# PATH order is authoritative for precedence. Shared-taxonomy directory hazard
# lines (when any) precede SHADOWED lines; SHADOWED lines are ordered by
# command basename bytes, then by PATH position of the shadowed executable.
# Non-executable same-basename files and distinct command names never produce
# SHADOWED. Repeated identical directory components do not self-shadow.
# Repeated identical non-winner shadow realpaths (PATH=winner:shadow:shadow)
# emit one SHADOWED row, keep exit status 1, and leave stderr empty.
# Maintenance regressions also pin a bounded many-basename fixture that
# exercises winner indexing and retained canonical-path ownership without
# treating wall-clock timing as the sole oracle.
# ---------------------------------------------------------------------------


def _private_path_dirs(tmp_path: Path, names: tuple[str, ...]) -> list[Path]:
    """Create mode-0700 sibling directories under an isolated private parent."""

    os.chmod(tmp_path, MODE_PRIVATE)
    dirs: list[Path] = []
    for name in names:
        directory = tmp_path / name
        directory.mkdir()
        os.chmod(directory, MODE_PRIVATE)
        dirs.append(directory)
    return dirs


def test_path_mode_shadowing_two_executables_reports_winner_and_shadow(
    pathaudit_bin, tmp_path
):
    """Two distinct PATH dirs with the same executable basename → one SHADOWED."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    winner = install_executable(early, cmd)
    shadow = install_executable(late, cmd)
    path_value = f"{early.resolve()}:{late.resolve()}"
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert shadowed_line(cmd, winner, shadow) in result.stdout


def test_path_mode_shadowing_first_entry_precedence_is_deterministic(
    pathaudit_bin, tmp_path
):
    """Swapping PATH order swaps the winner; each layout stays deterministic."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "shadowed"
    first = install_executable(early, cmd)
    second = install_executable(late, cmd)

    forward = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, owned = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    assert forward.returncode == 1
    assert forward.stderr == b""
    assert forward.stdout == owned + shadowing_stdout([(cmd, first, second)])

    reversed_order = run_pathaudit_path_mode(
        pathaudit_bin, f"{late.resolve()}:{early.resolve()}"
    )
    code, owned_r = expect_path_findings(
        [], [(0, late.resolve()), (1, early.resolve())]
    )
    assert reversed_order.returncode == 1
    assert reversed_order.stderr == b""
    assert reversed_order.stdout == owned_r + shadowing_stdout(
        [(cmd, second, first)]
    )
    assert forward.stdout != reversed_order.stdout


def test_path_mode_shadowing_reports_every_later_shadowed_location(
    pathaudit_bin, tmp_path
):
    """Three distinct later realpaths → winner plus one SHADOWED per distinct shadow.

    Distinct non-winner realpaths must each produce a row. This is the
    compatibility pin that duplicate suppression must not collapse.
    """

    first_dir, second_dir, third_dir = _private_path_dirs(
        tmp_path, ("a", "b", "c")
    )
    cmd = "multi"
    winner = install_executable(first_dir, cmd)
    shadow_b = install_executable(second_dir, cmd)
    shadow_c = install_executable(third_dir, cmd)
    assert shadow_b != shadow_c
    path_value = ":".join(
        str(d.resolve()) for d in (first_dir, second_dir, third_dir)
    )
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [],
        [
            (0, first_dir.resolve()),
            (1, second_dir.resolve()),
            (2, third_dir.resolve()),
        ],
    )
    expected = owned + shadowing_stdout(
        [
            (cmd, winner, shadow_b),
            (cmd, winner, shadow_c),
        ]
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 2
    assert shadowed_line(cmd, winner, shadow_b) in result.stdout
    assert shadowed_line(cmd, winner, shadow_c) in result.stdout


def test_path_mode_shadowing_ignores_non_executable_same_basename(
    pathaudit_bin, tmp_path
):
    """Non-executable same-basename files are not winners and not shadows."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"

    # Non-executable in the early entry must not create a shadow against a
    # later executable, and must not be treated as a winner.
    decoy = early / cmd
    decoy.write_bytes(b"not-executable\n")
    os.chmod(decoy, 0o644)
    install_executable(late, cmd)

    no_shadow = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, expected = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    assert no_shadow.returncode == code
    assert no_shadow.stderr == b""
    assert no_shadow.stdout == expected
    assert b"SHADOWED\t" not in no_shadow.stdout

    # Non-executable in a later entry must not be reported as shadowed when an
    # earlier executable exists.
    pair2 = tmp_path / "pair2"
    pair2.mkdir()
    early2, late2 = _private_path_dirs(pair2, ("early", "late"))
    winner = install_executable(early2, cmd)
    late_decoy = late2 / cmd
    late_decoy.write_bytes(b"also-not-executable\n")
    os.chmod(late_decoy, 0o644)
    still_clean = run_pathaudit_path_mode(
        pathaudit_bin, f"{early2.resolve()}:{late2.resolve()}"
    )
    code, expected = expect_path_findings(
        [], [(0, early2.resolve()), (1, late2.resolve())]
    )
    assert still_clean.returncode == code
    assert still_clean.stderr == b""
    assert still_clean.stdout == expected
    assert escape_root(winner) not in still_clean.stdout
    assert b"SHADOWED\t" not in still_clean.stdout


def test_path_mode_shadowing_ignores_distinct_command_names(
    pathaudit_bin, tmp_path
):
    """Distinct basenames across PATH dirs never produce SHADOWED noise."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    install_executable(early, "alpha")
    install_executable(early, "beta")
    install_executable(late, "gamma")
    install_executable(late, "delta")
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, expected = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"SHADOWED\t" not in result.stdout
    for name in (b"alpha", b"beta", b"gamma", b"delta"):
        assert name not in result.stdout


def test_path_mode_shadowing_only_reports_the_colliding_basename(
    pathaudit_bin, tmp_path
):
    """Unrelated distinct executables beside a real collision stay silent."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "collide"
    winner = install_executable(early, cmd)
    shadow = install_executable(late, cmd)
    install_executable(early, "only-early")
    install_executable(late, "only-late")
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, owned = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"only-early" not in result.stdout
    assert b"only-late" not in result.stdout
    assert result.stdout.count(b"SHADOWED\t") == 1


def test_path_mode_shadowing_repeated_directory_does_not_self_shadow(
    pathaudit_bin, tmp_path
):
    """The same PATH directory repeated does not invent a shadow against itself."""

    (only,) = _private_path_dirs(tmp_path, ("only",))
    cmd = "tool"
    install_executable(only, cmd)
    root = str(only.resolve())
    result = run_pathaudit_path_mode(pathaudit_bin, f"{root}:{root}")
    code, expected = expect_path_findings([], [(0, root), (1, root)])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"SHADOWED\t" not in result.stdout


def test_path_mode_shadowing_repeated_identical_shadow_realpath_emits_once(
    pathaudit_bin, tmp_path
):
    """PATH=winner:shadow:shadow emits one SHADOWED tuple (pathaudit-shadow-3).

    The live pre-repair implementation compares only against the winner, so a
    repeated later directory appends the identical winner/shadow row twice and
    still exits 1. After repair, the exact tuple is emitted once; status stays
    1 (dedup must not turn a genuine hazard into 0) and stderr stays empty.
    """

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    winner = install_executable(early, cmd)
    shadow = install_executable(late, cmd)
    early_s = str(early.resolve())
    late_s = str(late.resolve())
    # Contract fixture shape: first-PATH winner, then the same non-winner
    # component twice (PATH=early:late:late).
    path_value = f"{early_s}:{late_s}:{late_s}"
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [], [(0, early_s), (1, late_s), (2, late_s)]
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    # Unique SHADOWED forces status 1 even when PATH dirs/ancestors are trusted
    # (expect_path_findings ownership-only code may be 0 on such hosts).
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 1
    assert result.stdout.count(shadowed_line(cmd, winner, shadow)) == 1
    # First PATH hit remains the winner; the later realpath is never promoted.
    assert shadowed_line(cmd, shadow, winner) not in result.stdout


def test_path_mode_shadowing_duplicate_among_distinct_later_realpaths(
    pathaudit_bin, tmp_path
):
    """Distinct later realpaths stay; only exact duplicate tuples disappear.

    PATH=winner:mid:late:late → two SHADOWED rows (mid and late once each).
    """

    winner_dir, mid_dir, late_dir = _private_path_dirs(
        tmp_path, ("winner", "mid", "late")
    )
    cmd = "tool"
    winner = install_executable(winner_dir, cmd)
    shadow_mid = install_executable(mid_dir, cmd)
    shadow_late = install_executable(late_dir, cmd)
    assert shadow_mid != shadow_late
    path_value = ":".join(
        [
            str(winner_dir.resolve()),
            str(mid_dir.resolve()),
            str(late_dir.resolve()),
            str(late_dir.resolve()),
        ]
    )
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [],
        [
            (0, winner_dir.resolve()),
            (1, mid_dir.resolve()),
            (2, late_dir.resolve()),
            (3, late_dir.resolve()),
        ],
    )
    expected = owned + shadowing_stdout(
        [
            (cmd, winner, shadow_mid),
            (cmd, winner, shadow_late),
        ]
    )
    # Unique SHADOWED rows force status 1 regardless of ownership findings.
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 2
    assert result.stdout.count(shadowed_line(cmd, winner, shadow_mid)) == 1
    assert result.stdout.count(shadowed_line(cmd, winner, shadow_late)) == 1


def test_path_mode_shadowing_symlink_alias_of_shadow_dir_dedups_by_realpath(
    pathaudit_bin, tmp_path
):
    """Portability: distinct PATH text resolving to one shadow realpath → one row.

    A symlink PATH component that canonicalizes to the same late directory as
    an earlier non-winner must not invent a second identical SHADOWED tuple.
    """

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    late_link = tmp_path / "late-link"
    late_link.symlink_to(late.resolve())
    cmd = "tool"
    winner = install_executable(early, cmd)
    shadow = install_executable(late, cmd)
    early_s = str(early.resolve())
    late_s = str(late.resolve())
    # Absolute symlink PATH text (not followed) so the component bytes differ
    # from late_s while realpath(link) == late.
    link_s = str(late_link.absolute())
    assert Path(link_s).resolve() == Path(late_s)
    assert link_s != late_s
    path_value = f"{early_s}:{late_s}:{link_s}"
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [], [(0, early_s), (1, late_s), (2, link_s)]
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    # Unique SHADOWED forces status 1 regardless of ownership findings.
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 1
    assert result.stdout.count(shadowed_line(cmd, winner, shadow)) == 1


def test_path_mode_shadowing_many_basenames_bounded_winner_index(
    pathaudit_bin, tmp_path
):
    """Bounded many-basename fixture for winner/shadow indexes + path ownership.

    Exercises pathaudit-shadow-1 / pathaudit-shadow-2 functionally: many
    distinct winners and one shadow each must complete with exact SHADOWED
    output, first-PATH winners, basename-byte ordering, status 1, and empty
    stderr. Assertions are exact output and counts — not wall-clock timing.
    Completing with short canonical paths also pins that retained winner and
    shadow strings remain usable through emission (right-sized ownership).
    """

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    # Bound large enough to stress indexed winner/shadow lookup and many
    # retained canonical strings, small enough for ordinary and Valgrind runs.
    basename_count = 192
    commands = [f"cmd-{index:03d}" for index in range(basename_count)]
    # Install out of sort order so emission order cannot follow creation.
    install_order = list(reversed(commands))
    winners: dict[str, Path] = {}
    shadows: dict[str, Path] = {}
    for name in install_order:
        winners[name] = install_executable(early, name)
        shadows[name] = install_executable(late, name)

    path_value = f"{early.resolve()}:{late.resolve()}"
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    # Shadow rows sort by raw command-basename bytes, then PATH position.
    ordered_items = [
        (name, winners[name], shadows[name]) for name in sorted(commands)
    ]
    expected = owned + shadowing_stdout(ordered_items)
    # Unique SHADOWED rows force status 1 regardless of ownership findings.
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == basename_count
    # Retained paths in output are the short resolved fixture paths (not
    # padded scratch); each winner remains the early PATH hit.
    for name in commands:
        assert shadowed_line(name, winners[name], shadows[name]) in result.stdout
        assert shadowed_line(name, shadows[name], winners[name]) not in result.stdout
        assert os.fsencode(os.fspath(winners[name])) in result.stdout
        assert os.fsencode(os.fspath(shadows[name])) in result.stdout


def test_command_mode_repeated_later_match_keeps_match_not_shadowed(
    pathaudit_bin, tmp_path
):
    """`--command` keeps PATH-ordered MATCH rows; never invents SHADOWED.

    Compatibility baseline outside the --path duplicate-tuple repair: a
    winner:shadow:shadow layout still reports MATCH lines (including the
    repeated later hit) and leaves stderr empty under the shared ownership
    status rules.
    """

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    first = install_executable(early, cmd)
    second = install_executable(late, cmd)
    early_s = str(early.resolve())
    late_s = str(late.resolve())
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, f"{early_s}:{late_s}:{late_s}"
    )
    code, expected = expect_command_query(
        [first, second, second],
        [],
        [(0, early_s), (1, late_s), (2, late_s)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"SHADOWED\t" not in result.stdout
    assert result.stdout.count(b"MATCH\t") == 3
    assert result.stdout.startswith(match_line(first))


def test_path_mode_shadow_repair_preserves_reject_closed_path_unset_diagnostic(
    pathaudit_bin,
):
    """Diagnostics isolation: unset PATH still exits 2 with PATH_UNSET only.

    The shadow uniqueness repair must not soften reject-closed environment
    failures into a hazard (1) or success (0) path, invent SHADOWED/MATCH
    rows, or leave stdout non-empty.
    """

    result = run_pathaudit_path_mode(pathaudit_bin, None)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_lines("PATH_UNSET")
    assert b"SHADOWED\t" not in result.stdout
    assert b"MATCH\t" not in result.stdout
    assert b"usage:" not in result.stderr


def test_path_mode_shadowing_no_shadow_single_hit_exits_zero(
    pathaudit_bin, tmp_path
):
    """A basename present in only one PATH directory is not a shadowing hazard."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    install_executable(early, "solo")
    # late remains empty.
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, expected = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"SHADOWED\t" not in result.stdout
    assert b"solo" not in result.stdout


def test_path_mode_shadowing_multiple_commands_ordered_by_basename(
    pathaudit_bin, tmp_path
):
    """Multiple colliding basenames emit SHADOWED lines ordered by command bytes."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    # Install out of alphabetical order so ordering cannot follow creation.
    winner_z = install_executable(early, "z-cmd")
    shadow_z = install_executable(late, "z-cmd")
    winner_a = install_executable(early, "a-cmd")
    shadow_a = install_executable(late, "a-cmd")
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, owned = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    expected = owned + shadowing_stdout(
        [
            ("a-cmd", winner_a, shadow_a),
            ("z-cmd", winner_z, shadow_z),
        ]
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected


def test_path_mode_shadowing_directory_hazards_precede_shadowed_lines(
    pathaudit_bin, fixture_tree
):
    """Shared-taxonomy directory findings remain first; SHADOWED follows them."""

    cmd = "tool"
    # Trusted executables: directory WORLD_WRITABLE is the only permission line.
    winner = install_executable(
        fixture_tree.private, cmd, mode=MODE_EXE_TRUSTED
    )
    shadow = install_executable(
        fixture_tree.world_w, cmd, mode=MODE_EXE_TRUSTED
    )
    path_value = f"{fixture_tree.private}:{fixture_tree.world_w}"
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    assert result.returncode == 1
    assert result.stderr == b""
    code, owned = expect_path_findings(
        [(1, fixture_tree.world_w, "WORLD_WRITABLE")],
        [(0, fixture_tree.private), (1, fixture_tree.world_w)],
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert result.stdout == expected
    world_at = result.stdout.find(b"WORLD_WRITABLE\t")
    shadow_at = result.stdout.find(b"SHADOWED\t")
    assert world_at != -1 and shadow_at != -1
    assert world_at < shadow_at
    assert finding_line("WORLD_WRITABLE", winner) not in result.stdout
    assert finding_line("WORLD_WRITABLE", shadow) not in result.stdout


def test_path_mode_shadowing_duplicate_with_hazard_keeps_status_one_empty_stderr(
    pathaudit_bin, fixture_tree
):
    """PATH=private:world:world → hazards + one SHADOWED; status 1; empty stderr.

    Exit-status and diagnostics pin for pathaudit-shadow-3: after exact-tuple
    suppression the run remains a completed hazard path (status 1, empty
    stderr). Shared-taxonomy lines still precede the unique shadow row, and the
    repeated late component must not invent a second SHADOWED line or soften
    the status to 0.
    """

    cmd = "tool"
    winner = install_executable(
        fixture_tree.private, cmd, mode=MODE_EXE_TRUSTED
    )
    shadow = install_executable(
        fixture_tree.world_w, cmd, mode=MODE_EXE_TRUSTED
    )
    private = str(fixture_tree.private)
    world = str(fixture_tree.world_w)
    path_value = f"{private}:{world}:{world}"
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    code, owned = expect_path_findings(
        [
            (1, world, "WORLD_WRITABLE"),
            (2, world, "WORLD_WRITABLE"),
        ],
        [(0, private), (1, world), (2, world)],
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert code == 1
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 1
    assert result.stdout.count(shadowed_line(cmd, winner, shadow)) == 1
    world_at = result.stdout.find(b"WORLD_WRITABLE\t")
    shadow_at = result.stdout.find(b"SHADOWED\t")
    assert world_at != -1 and shadow_at != -1
    assert world_at < shadow_at


def test_explicit_roots_do_not_emit_shadowed_for_colliding_executables(
    pathaudit_bin, tmp_path
):
    """Explicit-root mode never searches executables and never emits SHADOWED."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    install_executable(early, cmd)
    install_executable(late, cmd)
    result = run_pathaudit(
        pathaudit_bin, str(early.resolve()), str(late.resolve())
    )
    assert result.returncode == 0
    assert result.stderr == b""
    assert result.stdout == b""
    assert b"SHADOWED\t" not in result.stdout
    assert b"MATCH\t" not in result.stdout
    assert cmd.encode("ascii") not in result.stdout


def test_path_mode_shadowing_skips_unreadable_directory_without_inventing_shadow(
    pathaudit_bin, tmp_path
):
    """Unreadable PATH components are skipped for shadowing without new codes."""

    if os.geteuid() == 0:
        pytest.skip("EACCES fixture is unreliable when running as root")

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    winner = install_executable(early, cmd)
    install_executable(late, cmd)
    os.chmod(late, 0)
    try:
        result = run_pathaudit_path_mode(
            pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
        )
    finally:
        os.chmod(late, MODE_PRIVATE)

    # Late remains a directory for classify_root (stat succeeds; mode 000 has
    # no group/other write bits), so no writability hazard. opendir fails and
    # shadowing skips the component without inventing SHADOWED. Ownership still
    # walks usable directory components (including the unreadable late dir).
    code, expected = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"SHADOWED\t" not in result.stdout
    assert escape_root(winner) not in result.stdout
    assert b"INSPECTION_ERROR_" not in result.stderr


def test_shadowed_line_helper_contract():
    """Pin the SHADOWED helper shape independently of a compiled binary."""

    assert shadowed_line("tool", "/a/tool", "/b/tool") == (
        b'SHADOWED\t"tool"\t"/a/tool"\t"/b/tool"\n'
    )
    assert shadowing_stdout(
        [("tool", "/a/tool", "/b/tool"), ("tool", "/a/tool", "/c/tool")]
    ) == (
        b'SHADOWED\t"tool"\t"/a/tool"\t"/b/tool"\n'
        b'SHADOWED\t"tool"\t"/a/tool"\t"/c/tool"\n'
    )
    # Unit pin for uniqueness: one exact (command, winner, shadow) tuple is
    # one expected line. Distinct later realpaths remain two lines.
    once = shadowing_stdout([("tool", "/a/tool", "/b/tool")])
    assert once.count(b"SHADOWED\t") == 1
    two_distinct = shadowing_stdout(
        [("tool", "/a/tool", "/b/tool"), ("tool", "/a/tool", "/c/tool")]
    )
    assert two_distinct.count(b"SHADOWED\t") == 2


# ---------------------------------------------------------------------------
# Hostile PATH regression coverage (`pathaudit --path`)
#
# Narrow security-sensitive corpus for adversarial PATH shapes the utility
# already supports: empty colon fields, nonexistent directories, duplicate
# components (including repeated non-winner shadow realpaths that must emit
# one SHADOWED tuple), and deterministic bytewise finding order. Every fixture
# tree is isolated under pytest tmp paths. Attacker-controlled plants are
# regular +x files whose bodies would create a marker file if ever executed;
# after each scan the marker must remain absent so coverage cannot accidentally
# run fixture content.
#
# Terminal-diagnostic pins additionally feed PATH components that embed LF,
# TAB, ESC/CSI sequences, non-UTF-8 bytes, quotes, and forged diagnostic tokens
# through run_pathaudit_path_mode, and assert stdout findings / stderr
# diagnostics stay quote-escaped, single-line, unambiguous, and free of raw
# terminal-control bytes.
# ---------------------------------------------------------------------------


def _shell_safe_path(path: Path) -> str:
    """Return an absolute path restricted to characters safe in an unquoted shell word."""

    text = os.fspath(path.resolve())
    for byte in os.fsencode(text):
        if not (
            (0x30 <= byte <= 0x39)
            or (0x41 <= byte <= 0x5A)
            or (0x61 <= byte <= 0x7A)
            or byte in (ord("/"), ord("-"), ord("_"), ord("."), ord("="))
        ):
            raise AssertionError(
                f"hostile-PATH probe path must be shell-safe ASCII: {text!r}"
            )
    return text


def _plant_execution_probe(directory: Path, basename: str, marker: Path) -> Path:
    """Install a regular +x plant that would create *marker* if executed.

    Returns the resolved plant path. Callers assert the marker stays absent
    after pathaudit runs.
    """

    marker_text = _shell_safe_path(marker)
    plant = directory / basename
    plant.write_bytes(
        b"#!/bin/sh\n"
        + f"printf executed >{marker_text}\n".encode("ascii")
        + b"exit 0\n"
    )
    os.chmod(plant, 0o755)
    return plant.resolve()


def _assert_probe_not_executed(marker: Path) -> None:
    """Fail if an attacker-controlled plant left its execution side-effect."""

    if marker.exists():
        raise AssertionError(
            f"attacker-controlled PATH plant was executed; marker present: {marker}"
        )


def test_hostile_path_empty_missing_duplicates_ordered_without_executing_plants(
    pathaudit_bin, tmp_path
):
    """Empty, missing, and duplicate PATH entries keep contract order; plants idle.

    PATH shape: "" : attacker : missing : "" : attacker : private
    - leading and middle empty fields → EMPTY_ROOT retained as ""
    - nonexistent absolute → MISSING_ROOT
    - duplicate attacker directory → no self-shadow; private stays silent
    - planted +x trojan under attacker must never run
    """

    os.chmod(tmp_path, MODE_PRIVATE)
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"

    attacker, private = _private_path_dirs(tmp_path, ("attacker", "private"))
    missing = tmp_path / "missing-hostile-root"
    assert not missing.exists()
    _plant_execution_probe(attacker, "trojan", marker)

    attacker_s = str(attacker.resolve())
    private_s = str(private.resolve())
    missing_s = str(missing)
    path_value = f":{attacker_s}:{missing_s}::{attacker_s}:{private_s}"

    assert not marker.exists()
    result = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=tmp_path)
    _assert_probe_not_executed(marker)

    code, expected = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (3, b"", "EMPTY_ROOT"),
            (2, missing_s, "MISSING_ROOT"),
        ],
        [(1, attacker_s), (4, attacker_s), (5, private_s)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"EMPTY_ROOT\t") == 2
    assert result.stdout.count(b"MISSING_ROOT\t") == 1
    assert finding_line("UNSAFE_OWNER", attacker_s) not in result.stdout
    assert finding_line("UNSAFE_OWNER", private_s) not in result.stdout
    assert b"SHADOWED\t" not in result.stdout
    assert b"trojan" not in result.stdout


def test_hostile_path_duplicate_hazard_entries_preserve_position_without_execution(
    pathaudit_bin, tmp_path
):
    """Duplicate writable PATH entries emit one finding each, never execute plants."""

    os.chmod(tmp_path, MODE_PRIVATE)
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"

    (world,) = _private_path_dirs(tmp_path, ("world-dup",))
    os.chmod(world, MODE_WORLD_WRITABLE)
    _plant_execution_probe(world, "plant", marker)

    root = str(world.resolve())
    path_value = f"{root}:{root}"

    assert not marker.exists()
    result = run_pathaudit_path_mode(pathaudit_bin, path_value)
    _assert_probe_not_executed(marker)

    assert result.returncode == 1
    assert result.stderr == b""
    code, expected = expect_path_findings(
        [
            (0, root, "WORLD_WRITABLE"),
            (1, root, "WORLD_WRITABLE"),
        ],
        [(0, root), (1, root)],
    )
    assert result.returncode == code
    assert result.stdout == expected
    assert result.stdout.count(b"WORLD_WRITABLE\t") == 2
    assert b"SHADOWED\t" not in result.stdout
    assert b"plant" not in result.stdout


def test_hostile_path_permutation_ordering_with_empty_and_missing(
    pathaudit_bin, tmp_path
):
    """Permuting empty/missing/hazard components remaps indices deterministically."""

    os.chmod(tmp_path, MODE_PRIVATE)
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"

    (group,) = _private_path_dirs(tmp_path, ("group-hostile",))
    os.chmod(group, MODE_GROUP_WRITABLE)
    _plant_execution_probe(group, "decoy", marker)
    missing = tmp_path / "no-such-hostile-dir"
    assert not missing.exists()

    group_s = str(group.resolve())
    missing_s = str(missing)

    first_path = f":{group_s}:{missing_s}"
    second_path = f"{missing_s}::{group_s}"

    assert not marker.exists()
    first = run_pathaudit_path_mode(pathaudit_bin, first_path, cwd=tmp_path)
    second = run_pathaudit_path_mode(pathaudit_bin, second_path, cwd=tmp_path)
    _assert_probe_not_executed(marker)

    _, expected_first = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (1, group_s, "GROUP_WRITABLE"),
            (2, missing_s, "MISSING_ROOT"),
        ],
        [(1, group_s)],
    )
    _, expected_second = expect_path_findings(
        [
            (1, b"", "EMPTY_ROOT"),
            (2, group_s, "GROUP_WRITABLE"),
            (0, missing_s, "MISSING_ROOT"),
        ],
        [(2, group_s)],
    )
    assert first.returncode == second.returncode == 1
    assert first.stderr == second.stderr == b""
    assert first.stdout == expected_first
    assert second.stdout == expected_second
    # Same finding multiset modulo operand-index tie-breaks encoded in order.
    assert sorted(first.stdout.splitlines()) == sorted(second.stdout.splitlines())
    assert b"decoy" not in first.stdout
    assert b"decoy" not in second.stdout


def test_hostile_path_shadow_observation_does_not_execute_attacker_plants(
    pathaudit_bin, tmp_path
):
    """SHADOWED observation of colliding plants must not execute either body.

    Two distinct PATH directories each contain the same attacker basename as a
    regular +x file. The scanner may report shadowing, but neither plant may
    run. Empty and missing components around the collision stay classified
    under the shared taxonomy and do not invent extra shadows.
    """

    os.chmod(tmp_path, MODE_PRIVATE)
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker_early = probe_dir / "executed-early"
    marker_late = probe_dir / "executed-late"

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    missing = tmp_path / "missing-between"
    assert not missing.exists()
    cmd = "collide"
    winner = _plant_execution_probe(early, cmd, marker_early)
    shadow = _plant_execution_probe(late, cmd, marker_late)

    early_s = str(early.resolve())
    late_s = str(late.resolve())
    missing_s = str(missing)
    # Empty : early : missing : late : empty — empties and missing skipped for
    # shadowing; collision still observed across the two real directories.
    path_value = f":{early_s}:{missing_s}:{late_s}:"

    assert not marker_early.exists()
    assert not marker_late.exists()
    result = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=tmp_path)
    _assert_probe_not_executed(marker_early)
    _assert_probe_not_executed(marker_late)

    code, owned = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (4, b"", "EMPTY_ROOT"),
            (2, missing_s, "MISSING_ROOT"),
        ],
        [(1, early_s), (3, late_s)],
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 1
    assert result.stdout.count(b"EMPTY_ROOT\t") == 2
    assert result.stdout.count(b"MISSING_ROOT\t") == 1


def test_hostile_path_repeated_shadow_component_dedups_without_executing_plants(
    pathaudit_bin, tmp_path
):
    """Hostile PATH=.:early:missing:late:late:. keeps one SHADOWED; plants idle.

    Empty and missing components stay classified; the repeated later directory
    must not append a duplicate SHADOWED tuple or execute either plant. Exit
    status remains 1 with empty stderr after dedup.
    """

    os.chmod(tmp_path, MODE_PRIVATE)
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker_early = probe_dir / "executed-early-dup"
    marker_late = probe_dir / "executed-late-dup"

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    missing = tmp_path / "missing-between-dup"
    assert not missing.exists()
    cmd = "collide-dup"
    winner = _plant_execution_probe(early, cmd, marker_early)
    shadow = _plant_execution_probe(late, cmd, marker_late)

    early_s = str(early.resolve())
    late_s = str(late.resolve())
    missing_s = str(missing)
    # Empty : early : missing : late : late : empty — exact duplicate shadow
    # realpath appears twice after a missing gap.
    path_value = f":{early_s}:{missing_s}:{late_s}:{late_s}:"

    assert not marker_early.exists()
    assert not marker_late.exists()
    result = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=tmp_path)
    _assert_probe_not_executed(marker_early)
    _assert_probe_not_executed(marker_late)

    code, owned = expect_path_findings(
        [
            (0, b"", "EMPTY_ROOT"),
            (5, b"", "EMPTY_ROOT"),
            (2, missing_s, "MISSING_ROOT"),
        ],
        [(1, early_s), (3, late_s), (4, late_s)],
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert code == 1
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.count(b"SHADOWED\t") == 1
    assert result.stdout.count(shadowed_line(cmd, winner, shadow)) == 1
    assert result.stdout.count(b"EMPTY_ROOT\t") == 2
    assert result.stdout.count(b"MISSING_ROOT\t") == 1
    assert_no_raw_unsafe_bytes(result.stdout)


def test_hostile_path_control_and_csi_bytes_escaped_in_stdout_findings(
    pathaudit_bin, tmp_path
):
    """Hostile PATH component text must not inject raw terminal controls on stdout.

    Embeds LF (forge a second finding line), TAB (forge fields), ESC/CSI clear
    and SGR sequences (raw terminal effects), a forged WORLD_WRITABLE token,
    non-UTF-8 0xFF, quote, and backslash inside one missing absolute PATH
    component. Escaping must keep a single unambiguous MISSING_ROOT record.
    """

    os.chmod(tmp_path, MODE_PRIVATE)
    (private,) = _private_path_dirs(tmp_path, ("private",))
    # Absolute so the component is not also RELATIVE_ROOT; missing so the
    # finding root is the hostile PATH text itself (no filesystem rename).
    hostile = os.fsdecode(
        b'/no-such-\n\tWORLD_WRITABLE\t"forged"-\x1b[2J-\x1b[0m-\xff-"-\\-comp'
    )
    path_value = f"{hostile}:{private.resolve()}"

    result = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=tmp_path)
    code, expected = expect_path_findings(
        [(0, hostile, "MISSING_ROOT")],
        [(1, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert_no_raw_unsafe_bytes(result.stdout)
    assert b"\x1b" not in result.stdout
    assert b"\xff" not in result.stdout
    assert b"\\x1B" in result.stdout
    assert b"\\xFF" in result.stdout
    assert b"\\x0A" in result.stdout
    assert b"\\x09" in result.stdout
    # MISSING_ROOT line plus any UNSAFE_OWNER ancestor lines.
    assert finding_line("MISSING_ROOT", hostile) in result.stdout
    assert b"\nWORLD_WRITABLE" not in result.stdout
    assert finding_line("UNSAFE_OWNER", private.resolve()) not in result.stdout


def test_hostile_path_writable_dir_with_esc_name_escapes_terminal_bytes(
    pathaudit_bin, tmp_path
):
    """Existing PATH dirs whose names carry ESC/CSI still emit escaped findings."""

    os.chmod(tmp_path, MODE_PRIVATE)
    # CSI SGR red + reset around printable text; also LF/TAB/0xFF metacharacters.
    hostile_name = os.fsdecode(b'dir-\x1b[31mRED\x1b[0m-\n\t-\xff-"-\\-name')
    hostile_dir = tmp_path / hostile_name
    hostile_dir.mkdir()
    os.chmod(hostile_dir, MODE_WORLD_WRITABLE)
    root = str(hostile_dir.resolve())

    result = run_pathaudit_path_mode(pathaudit_bin, root)
    assert result.returncode == 1
    assert result.stderr == b""
    code, expected = expect_path_findings(
        [(0, root, "WORLD_WRITABLE")],
        [(0, root)],
    )
    assert result.returncode == code
    assert result.stdout == expected
    assert_no_raw_unsafe_bytes(result.stdout)
    assert b"\x1b" not in result.stdout
    assert b"\xff" not in result.stdout
    assert b"\\x1B" in result.stdout
    assert b"\\xFF" in result.stdout
    assert b"\\x0A" in result.stdout
    assert b"\\x09" in result.stdout
    # One tab per finding line; ambient ancestor UNSAFE_OWNER may add lines.
    assert result.stdout.count(b"\t") == result.stdout.count(b"\n")
    assert result.stdout.endswith(b"\n")
    # Printable CSI tail stays visible only inside the escaped quotes.
    assert b"[31mRED" in result.stdout
    assert b"[0m" in result.stdout


def test_hostile_path_inspection_error_escapes_control_component_on_stderr(
    pathaudit_bin, tmp_path
):
    """PATH-mode INSPECTION_ERROR diagnostics must escape hostile component text.

    A symlink-loop PATH component carrying LF, TAB, ESC/CSI, forged
    `pathaudit: FORGED`, non-UTF-8, quote, and backslash must yield one
    reject-closed stderr line with empty stdout — never raw terminal controls
    and never a forged second diagnostic line.
    """

    os.chmod(tmp_path, MODE_PRIVATE)
    hostile_name = os.fsdecode(
        b'loop-\n\tpathaudit: FORGED-\x1b[2J-\x1b[0m-\xff-"-\\-a'
    )
    partner_name = os.fsdecode(
        b'loop-\n\tpathaudit: FORGED-\x1b[2J-\x1b[0m-\xff-"-\\-b'
    )
    early_loop = tmp_path / hostile_name
    partner = tmp_path / partner_name
    early_loop.symlink_to(partner)
    partner.symlink_to(early_loop)
    # absolute() keeps the hostile operand text; resolve() would raise on ELOOP.
    component = str(early_loop.absolute())
    (private,) = _private_path_dirs(tmp_path, ("private",))
    path_value = f"{component}:{private.resolve()}"

    result = run_pathaudit_path_mode(pathaudit_bin, path_value, cwd=tmp_path)
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    expected = diagnostic_lines(reason, component)
    assert result.stderr == expected
    assert_no_raw_unsafe_bytes(result.stderr)
    assert b"\x1b" not in result.stderr
    assert b"\xff" not in result.stderr
    assert b"\\x1B" in result.stderr
    assert b"\\xFF" in result.stderr
    assert b"\\x0A" in result.stderr
    assert b"\\x09" in result.stderr
    # stderr diagnostics have no structural TAB; operand TAB must be escaped.
    assert result.stderr.count(b"\t") == 0
    # Single structural LF terminator only — no raw LF from the PATH component.
    assert result.stderr.count(b"\n") == 1
    assert result.stderr.endswith(b"\n")
    assert b"\npathaudit:" not in result.stderr
    assert b"\npathaudit: FORGED" not in result.stderr
    assert b"pathaudit: FORGED" in result.stderr
    assert result.stderr.startswith(b"pathaudit: INSPECTION_ERROR_")
    # CSI clear-screen / SGR tails remain printable inside the quotes only.
    assert b"[2J" in result.stderr
    assert b"[0m" in result.stderr


# ---------------------------------------------------------------------------
# Detect writable executables resolved through PATH
#
# Authored ahead of implementation. Additive contract: when `--path` or
# `--command` resolves a regular executable through PATH, apply the existing
# directory trust model to the final executable target. Owner-only write
# (trusted) stays silent. `S_IWGRP` / `S_IWOTH` reuse GROUP_WRITABLE /
# WORLD_WRITABLE with the executable realpath as the finding root. Symlink
# resolution follows the final target. Paths/files that cannot be inspected
# safely reject-close with INSPECTION_ERROR_N. Explicit-root mode still does
# not search executables. Shared-taxonomy findings (directory and executable)
# precede SHADOWED lines; `--command` keeps MATCH lines before hazards.
# Current-user ownership of executable fixtures is trusted for the file itself;
# PATH directories and ancestors still participate in the shared UNSAFE_OWNER
# walk. Assertions below allow ancestor ownership while forbidding inventing
# UNSAFE_OWNER on the invoking-UID executable realpath.
# ---------------------------------------------------------------------------


def test_path_mode_trusted_executable_is_silent(pathaudit_bin, tmp_path):
    """Owner-writable-only executables are trusted; PATH ownership may still fire."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = install_executable(private, "tool", mode=MODE_EXE_TRUSTED)
    # Also cover MODE_PRIVATE (0700): owner rwx only, still trusted.
    install_executable(private, "private-tool", mode=MODE_PRIVATE)
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"WORLD_WRITABLE" not in result.stdout
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout
    assert b"SHADOWED\t" not in result.stdout


def test_path_mode_group_writable_executable_reports_group_writable(
    pathaudit_bin, tmp_path
):
    """Group-writable final executable targets reuse GROUP_WRITABLE."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = install_executable(private, "tool", mode=MODE_GROUP_WRITABLE)
    assert exe.stat().st_uid == os.getuid()
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings(
        [(0, exe, "GROUP_WRITABLE")],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"WORLD_WRITABLE" not in result.stdout
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_path_mode_world_writable_executable_reports_world_writable(
    pathaudit_bin, tmp_path
):
    """Other-writable final executable targets reuse WORLD_WRITABLE."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = install_executable(private, "tool", mode=MODE_WORLD_WRITABLE)
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings(
        [(0, exe, "WORLD_WRITABLE")],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"GROUP_WRITABLE" not in result.stdout
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_path_mode_both_writable_executable_reports_both_codes(
    pathaudit_bin, tmp_path
):
    """Executables with both untrusted write bits emit both shared codes."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = install_executable(private, "tool", mode=MODE_BOTH_WRITABLE)
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings(
        [
            (0, exe, "GROUP_WRITABLE"),
            (0, exe, "WORLD_WRITABLE"),
        ],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_path_mode_symlink_executable_uses_final_writable_target(
    pathaudit_bin, tmp_path
):
    """Symlink resolution reports writability of the final executable target."""

    target_dir, link_dir = _private_path_dirs(tmp_path, ("target-dir", "link-dir"))
    cmd = "tool"
    real = install_executable(target_dir, cmd, mode=MODE_WORLD_WRITABLE)
    link = link_dir / cmd
    link.symlink_to(real)
    # PATH names the private link directory; the final target is world-writable.
    result = run_pathaudit_path_mode(pathaudit_bin, str(link_dir.resolve()))
    code, expected = expect_path_findings(
        [(0, real, "WORLD_WRITABLE")],
        [(0, link_dir.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # Finding root is the realpath (final target), matching MATCH/SHADOWED.
    assert link.resolve() == real
    assert finding_line("UNSAFE_OWNER", real) not in result.stdout


def test_path_mode_directory_and_executable_writability_both_report(
    pathaudit_bin, tmp_path
):
    """Directory and executable trust-model findings coexist under one scan."""

    (world,) = _private_path_dirs(tmp_path, ("world",))
    os.chmod(world, MODE_WORLD_WRITABLE)
    exe = install_executable(world, "tool", mode=MODE_GROUP_WRITABLE)
    root = str(world.resolve())
    result = run_pathaudit_path_mode(pathaudit_bin, root)
    code, expected = expect_path_findings(
        [
            (0, root, "WORLD_WRITABLE"),
            (0, exe, "GROUP_WRITABLE"),
        ],
        [(0, root)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_path_mode_writable_executable_findings_precede_shadowed(
    pathaudit_bin, tmp_path
):
    """Executable writability is shared-taxonomy output and precedes SHADOWED."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    winner = install_executable(early, cmd, mode=MODE_WORLD_WRITABLE)
    shadow = install_executable(late, cmd, mode=MODE_EXE_TRUSTED)
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, owned = expect_path_findings(
        [(0, winner, "WORLD_WRITABLE")],
        [(0, early.resolve()), (1, late.resolve())],
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.find(b"WORLD_WRITABLE\t") < result.stdout.find(
        b"SHADOWED\t"
    )
    assert finding_line("WORLD_WRITABLE", shadow) not in result.stdout
    assert finding_line("UNSAFE_OWNER", winner) not in result.stdout


def test_path_mode_non_executable_writable_same_basename_is_not_reported(
    pathaudit_bin, tmp_path
):
    """Non-executable group/other-writable files are not executable findings."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    decoy = private / "tool"
    decoy.write_bytes(b"not-executable\n")
    os.chmod(decoy, MODE_WORLD_WRITABLE)
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"WORLD_WRITABLE" not in result.stdout
    assert b"tool" not in result.stdout


def test_explicit_roots_do_not_report_writable_executables(
    pathaudit_bin, tmp_path
):
    """Explicit-root mode never searches executables for writability."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    install_executable(private, "tool", mode=MODE_BOTH_WRITABLE)
    result = run_pathaudit(pathaudit_bin, str(private.resolve()))
    assert result.returncode == 0
    assert result.stderr == b""
    assert result.stdout == b""
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"WORLD_WRITABLE" not in result.stdout
    assert b"UNSAFE_OWNER" not in result.stdout
    assert b"MATCH\t" not in result.stdout
    assert b"tool" not in result.stdout


def test_command_mode_trusted_executable_match_exits_zero(
    pathaudit_bin, fixture_tree
):
    """Trusted-mode MATCH has no permission findings; PATH ownership may still fire."""

    cmd = "tool"
    exe = install_executable(
        fixture_tree.private, cmd, mode=MODE_EXE_TRUSTED
    )
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [exe], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"WORLD_WRITABLE" not in result.stdout
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_world_writable_executable_reports_after_match(
    pathaudit_bin, fixture_tree
):
    """`--command` emits MATCH then WORLD_WRITABLE on the executable realpath."""

    cmd = "tool"
    exe = install_executable(
        fixture_tree.private, cmd, mode=MODE_WORLD_WRITABLE
    )
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [exe],
        [(0, exe, "WORLD_WRITABLE")],
        [(0, fixture_tree.private)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.startswith(match_line(exe))
    assert finding_line("WORLD_WRITABLE", fixture_tree.private) not in (
        result.stdout
    )
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_group_writable_executable_reports_group_writable(
    pathaudit_bin, fixture_tree
):
    cmd = "tool"
    exe = install_executable(
        fixture_tree.private, cmd, mode=MODE_GROUP_WRITABLE
    )
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [exe],
        [(0, exe, "GROUP_WRITABLE")],
        [(0, fixture_tree.private)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_symlink_match_reports_final_writable_target(
    pathaudit_bin, fixture_tree
):
    """Symlinked MATCH uses realpath; writability follows that final target."""

    cmd = "tool"
    real = install_executable(
        fixture_tree.private, cmd, mode=MODE_BOTH_WRITABLE
    )
    link_dir = fixture_tree.root / "link-dir-writable-exe"
    link_dir.mkdir()
    os.chmod(link_dir, MODE_PRIVATE)
    link = link_dir / cmd
    link.symlink_to(real)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(link_dir.resolve())
    )
    code, expected = expect_command_query(
        [link.resolve()],
        [
            (0, link.resolve(), "GROUP_WRITABLE"),
            (0, link.resolve(), "WORLD_WRITABLE"),
        ],
        [(0, link_dir.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    resolved = link.resolve()
    assert resolved == real
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", resolved) not in result.stdout


def test_command_mode_writable_dir_and_writable_exe_both_report(
    pathaudit_bin, fixture_tree
):
    """Directory plant-risk and executable writability combine deterministically."""

    cmd = "tool"
    exe = install_executable(
        fixture_tree.private, cmd, mode=MODE_WORLD_WRITABLE
    )
    path_value = f"{fixture_tree.group_w}:{fixture_tree.private}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    code, expected = expect_command_query(
        [exe],
        [
            (0, fixture_tree.group_w, "GROUP_WRITABLE"),
            (1, exe, "WORLD_WRITABLE"),
        ],
        [(0, fixture_tree.group_w), (1, fixture_tree.private)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_unreadable_symlink_target_is_inspection_error(
    pathaudit_bin, tmp_path
):
    """Executable candidates that cannot be inspected safely reject-close."""

    if os.geteuid() == 0:
        pytest.skip("EACCES fixture is unreliable when running as root")

    os.chmod(tmp_path, MODE_PRIVATE)
    link_dir = tmp_path / "link-dir"
    blocked = tmp_path / "blocked"
    secret = blocked / "secret"
    link_dir.mkdir()
    blocked.mkdir()
    secret.mkdir()
    os.chmod(link_dir, MODE_PRIVATE)
    os.chmod(secret, MODE_PRIVATE)

    cmd = "tool"
    real = install_executable(secret, cmd, mode=MODE_EXE_TRUSTED)
    link_root = str(link_dir.resolve())
    link = link_dir / cmd
    link.symlink_to(real)
    # pathaudit joins PATH component text with the basename for the candidate.
    candidate = f"{link_root}/{cmd}"
    os.chmod(blocked, 0)
    try:
        result = run_pathaudit_command_mode(pathaudit_bin, cmd, link_root)
        assert result.returncode == 2
        assert result.stdout == b""
        reason = f"INSPECTION_ERROR_{errno_mod.EACCES}"
        assert result.stderr == diagnostic_lines(reason, candidate)
        assert_no_raw_unsafe_bytes(result.stderr)
    finally:
        os.chmod(blocked, MODE_PRIVATE)


def test_path_mode_unreadable_symlink_target_is_inspection_error(
    pathaudit_bin, tmp_path
):
    """`--path` scanning rejects closed when an executable candidate is opaque."""

    if os.geteuid() == 0:
        pytest.skip("EACCES fixture is unreliable when running as root")

    os.chmod(tmp_path, MODE_PRIVATE)
    link_dir = tmp_path / "link-dir"
    blocked = tmp_path / "blocked"
    secret = blocked / "secret"
    link_dir.mkdir()
    blocked.mkdir()
    secret.mkdir()
    os.chmod(link_dir, MODE_PRIVATE)
    os.chmod(secret, MODE_PRIVATE)

    cmd = "tool"
    real = install_executable(secret, cmd, mode=MODE_EXE_TRUSTED)
    link_root = str(link_dir.resolve())
    link = link_dir / cmd
    link.symlink_to(real)
    candidate = f"{link_root}/{cmd}"
    os.chmod(blocked, 0)
    try:
        result = run_pathaudit_path_mode(pathaudit_bin, link_root)
        assert result.returncode == 2
        assert result.stdout == b""
        reason = f"INSPECTION_ERROR_{errno_mod.EACCES}"
        assert result.stderr == diagnostic_lines(reason, candidate)
        assert_no_raw_unsafe_bytes(result.stderr)
        assert b"SHADOWED\t" not in result.stdout
    finally:
        os.chmod(blocked, MODE_PRIVATE)


# ---------------------------------------------------------------------------
# PA-W1: bounded self-basename ELOOP discriminator
#
# Closes docs/pathaudit-open-repairs-contract.md Low finding PA-W1. The helper
# that distinguishes a bare self-basename loop (tool -> tool) from other ELOOP
# shapes must not reserve a PATHAUDIT_MAX_ROOT_LENGTH automatic readlink
# buffer; temporary storage is command-length + one truncation-detection byte,
# heap-owned, and freed on every return. Bare self links stay reject-closed
# (AC-2 / AC-3 below). Slash-bearing and byte-different loop targets must not
# be reclassified as bare self-basename links, must not invent MATCH/SHADOWED,
# and must never execute planted target content (AC-4).
# ---------------------------------------------------------------------------


def _extract_c_function_body(source: str, name: str) -> str:
    """Return the outermost brace body of a C function definition named *name*."""

    match = re.search(
        rf"(?:^|\n)(?:static\s+)?(?:[\w\s\*]+?\s|\*){re.escape(name)}\s*\(",
        source,
    )
    if match is None:
        raise AssertionError(f"C function {name!r} not found in source")
    param_open = source.find("(", match.start())
    if param_open < 0:
        raise AssertionError(f"C function {name!r}: missing parameter list")
    depth = 0
    i = param_open
    while i < len(source):
        ch = source[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                i += 1
                break
        i += 1
    else:
        raise AssertionError(f"C function {name!r}: unterminated parameter list")
    while i < len(source) and source[i] in " \t\r\n":
        i += 1
    if i >= len(source) or source[i] != "{":
        raise AssertionError(f"C function {name!r}: missing opening brace")
    body_start = i
    depth = 0
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[body_start : i + 1]
        i += 1
    raise AssertionError(f"C function {name!r}: unterminated body")


def test_paw1_self_basename_buffer_is_command_bounded_and_owned():
    """AC-1: symlink_is_self_basename uses command-bounded heap storage, not a root-sized stack array."""

    if not SRC.is_file():
        pytest.fail(f"{SRC} is missing; PA-W1 regression requires the source")
    source = SRC.read_text(encoding="utf-8")
    body = _extract_c_function_body(source, "symlink_is_self_basename")

    # Old PA-W1 blast radius: automatic readlink buffer sized by the root limit.
    assert re.search(
        r"\[\s*PATHAUDIT_MAX_ROOT_LENGTH(?:\s*\+\s*\d+)?\s*\]",
        body,
    ) is None, (
        "symlink_is_self_basename must not declare an automatic buffer sized "
        "by PATHAUDIT_MAX_ROOT_LENGTH (PA-W1)"
    )
    assert re.search(
        r"\b(?:malloc|calloc)\s*\(\s*PATHAUDIT_MAX_ROOT_LENGTH",
        body,
    ) is None, (
        "symlink_is_self_basename must not heap-allocate a root-length "
        "readlink buffer (PA-W1)"
    )
    assert "PATHAUDIT_MAX_ROOT_LENGTH" not in body, (
        "symlink_is_self_basename temporary storage must not be keyed off "
        "PATHAUDIT_MAX_ROOT_LENGTH (PA-W1)"
    )

    assert re.search(r"\b(?:malloc|calloc)\s*\(", body), (
        "symlink_is_self_basename must allocate temporary readlink storage"
    )
    assert re.search(r"\bstrlen\s*\(\s*command\s*\)", body), (
        "symlink_is_self_basename buffer bound must derive from strlen(command)"
    )
    # Extra byte is the truncation / longer-payload detector (command_len + 1).
    assert re.search(
        r"(?:strlen\s*\(\s*command\s*\)|command_len|cmd_len).{0,120}?\+\s*1"
        r"|size_add_ok\s*\(\s*(?:strlen\s*\(\s*command\s*\)|command_len|cmd_len)"
        r"\s*,\s*1\b",
        body,
        flags=re.DOTALL,
    ), (
        "symlink_is_self_basename allocation must be command length plus one "
        "detection byte (PA-W1)"
    )
    free_sites = re.findall(r"\bfree\s*\(", body)
    assert len(free_sites) >= 2, (
        "symlink_is_self_basename must free temporary storage on success, "
        "mismatch, and readlink-failure paths (PA-W1)"
    )
    assert re.search(r"\breadlink\s*\(", body), (
        "symlink_is_self_basename must call readlink without following the candidate"
    )


def test_path_mode_symlink_loop_executable_candidate_is_inspection_error(
    pathaudit_bin, tmp_path
):
    """AC-2: bare self-basename loop under `--path` is unsafe inspection, not a silent skip."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    cmd = "tool"
    private_root = str(private.resolve())
    # Single self-referential symlink so readdir order cannot ambiguate the
    # diagnostic operand (avoid a two-node loop with two basenames).
    loop = private / cmd
    loop.symlink_to(cmd)
    candidate = f"{private_root}/{cmd}"
    result = run_pathaudit_path_mode(pathaudit_bin, private_root)
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    assert result.stderr == diagnostic_lines(reason, candidate)
    assert_no_raw_unsafe_bytes(result.stderr)


def test_command_mode_symlink_loop_executable_is_inspection_error(
    pathaudit_bin, tmp_path
):
    """AC-3: bare self-basename loop under `--command` matches AC-2 status/stdout/stderr bytes."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    cmd = "tool"
    private_root = str(private.resolve())
    loop = private / cmd
    loop.symlink_to(cmd)
    candidate = f"{private_root}/{cmd}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, private_root)
    assert result.returncode == 2
    assert result.stdout == b""
    reason = f"INSPECTION_ERROR_{errno_mod.ELOOP}"
    assert result.stderr == diagnostic_lines(reason, candidate)
    assert_no_raw_unsafe_bytes(result.stderr)


def test_paw1_path_mode_slash_bearing_loop_is_not_bare_self_basename(
    pathaudit_bin, tmp_path
):
    """AC-4: `tool -> ./tool` is not bare self-basename; no MATCH/SHADOWED/exec."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"
    plant = _plant_execution_probe(private, "plant", marker)

    cmd = "tool"
    private_root = str(private.resolve())
    loop = private / cmd
    loop.symlink_to("./tool")
    candidate = f"{private_root}/{cmd}"
    eloop = f"INSPECTION_ERROR_{errno_mod.ELOOP}"

    assert not marker.exists()
    result = run_pathaudit_path_mode(pathaudit_bin, private_root)
    _assert_probe_not_executed(marker)

    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert diagnostic_lines(eloop, candidate) not in result.stderr
    assert eloop.encode("ascii") not in result.stderr
    assert b"MATCH\t" not in result.stdout
    assert b"SHADOWED\t" not in result.stdout
    assert escape_root(cmd) not in result.stdout
    assert escape_root(plant) not in result.stdout
    assert_no_raw_unsafe_bytes(result.stdout)


def test_paw1_command_mode_slash_bearing_loop_is_not_bare_self_basename(
    pathaudit_bin, tmp_path
):
    """AC-4: `--command` keeps `tool -> ./tool` as a non-self ELOOP non-match."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"
    plant = _plant_execution_probe(private, "plant", marker)

    cmd = "tool"
    private_root = str(private.resolve())
    loop = private / cmd
    loop.symlink_to("./tool")
    candidate = f"{private_root}/{cmd}"
    eloop = f"INSPECTION_ERROR_{errno_mod.ELOOP}"

    assert not marker.exists()
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, private_root)
    _assert_probe_not_executed(marker)

    code, expected = expect_command_query([], [], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert diagnostic_lines(eloop, candidate) not in result.stderr
    assert eloop.encode("ascii") not in result.stderr
    assert b"MATCH\t" not in result.stdout
    assert b"SHADOWED\t" not in result.stdout
    assert escape_root(plant) not in result.stdout
    assert_no_raw_unsafe_bytes(result.stdout)


def test_paw1_path_mode_byte_different_mutual_loop_is_not_bare_self_basename(
    pathaudit_bin, tmp_path
):
    """AC-4: mutual `alpha <-> bravo` loops stay non-candidates under `--path`."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"
    plant = _plant_execution_probe(private, "plant", marker)

    private_root = str(private.resolve())
    alpha = private / "alpha"
    bravo = private / "bravo"
    # Byte-different targets (and unequal lengths) so neither is a bare
    # self-basename payload of its own command name.
    alpha.symlink_to("bravo")
    bravo.symlink_to("alpha")
    alpha_candidate = f"{private_root}/alpha"
    bravo_candidate = f"{private_root}/bravo"
    eloop = f"INSPECTION_ERROR_{errno_mod.ELOOP}"

    assert not marker.exists()
    result = run_pathaudit_path_mode(pathaudit_bin, private_root)
    _assert_probe_not_executed(marker)

    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert diagnostic_lines(eloop, alpha_candidate) not in result.stderr
    assert diagnostic_lines(eloop, bravo_candidate) not in result.stderr
    assert eloop.encode("ascii") not in result.stderr
    assert b"MATCH\t" not in result.stdout
    assert b"SHADOWED\t" not in result.stdout
    assert escape_root("alpha") not in result.stdout
    assert escape_root("bravo") not in result.stdout
    assert escape_root(plant) not in result.stdout
    assert_no_raw_unsafe_bytes(result.stdout)


def test_paw1_command_mode_byte_different_mutual_loop_is_not_bare_self_basename(
    pathaudit_bin, tmp_path
):
    """AC-4: `--command` does not reject-close or MATCH a mutual-loop basename."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    probe_dir = tmp_path / "probes"
    probe_dir.mkdir()
    os.chmod(probe_dir, MODE_PRIVATE)
    marker = probe_dir / "executed"
    plant = _plant_execution_probe(private, "plant", marker)

    private_root = str(private.resolve())
    alpha = private / "alpha"
    bravo = private / "bravo"
    alpha.symlink_to("bravo")
    bravo.symlink_to("alpha")
    alpha_candidate = f"{private_root}/alpha"
    bravo_candidate = f"{private_root}/bravo"
    eloop = f"INSPECTION_ERROR_{errno_mod.ELOOP}"

    assert not marker.exists()
    for cmd, candidate in (
        ("alpha", alpha_candidate),
        ("bravo", bravo_candidate),
    ):
        result = run_pathaudit_command_mode(pathaudit_bin, cmd, private_root)
        _assert_probe_not_executed(marker)
        code, expected = expect_command_query([], [], [(0, private.resolve())])
        assert result.returncode == code
        assert result.stderr == b""
        assert result.stdout == expected
        assert diagnostic_lines(eloop, candidate) not in result.stderr
        assert eloop.encode("ascii") not in result.stderr
        assert b"MATCH\t" not in result.stdout
        assert b"SHADOWED\t" not in result.stdout
        assert escape_root(plant) not in result.stdout
        assert_no_raw_unsafe_bytes(result.stdout)


# ---------------------------------------------------------------------------
# Detect executables with unsafe ownership
#
# Additive contract for `--path` and `--command`: a regular executable whose
# final-target st_uid is neither root UID 0 nor the invoking real user from
# getuid() emits UNSAFE_OWNER naming the executable realpath. Current-user and
# root ownership are trusted for that executable. PATH directories and ancestors
# still participate in the same UNSAFE_OWNER policy. Symlinks follow the final
# target owner. UNSAFE_OWNER ranks after GROUP_WRITABLE / WORLD_WRITABLE for
# the same root, exits status 1, and sorts with other shared-taxonomy findings
# ahead of SHADOWED. Explicit-root mode never searches executables and never
# emits UNSAFE_OWNER. Foreign-owner fixtures chown only files created inside
# the test tree and skip honestly when the host cannot establish a distinct
# owner.
# ---------------------------------------------------------------------------


def test_path_mode_current_user_owned_executable_is_trusted(
    pathaudit_bin, tmp_path
):
    """Invoking-user executable ownership is trusted; PATH ownership may still fire."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = install_executable(private, "tool", mode=MODE_EXE_TRUSTED)
    assert exe.stat().st_uid == os.getuid()
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_path_mode_root_owned_executable_is_trusted_when_establishable(
    pathaudit_bin, tmp_path
):
    """Root UID 0 executable ownership is trusted where the fixture can establish it."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = require_root_owned_executable(private, "tool", mode=MODE_EXE_TRUSTED)
    assert exe.stat().st_uid == 0
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_path_mode_foreign_owned_executable_reports_unsafe_owner(
    pathaudit_bin, tmp_path
):
    """Foreign final-target ownership emits UNSAFE_OWNER with exit status 1."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = require_foreign_owned_executable(
        private, "tool", mode=MODE_EXE_TRUSTED
    )
    owner = exe.stat().st_uid
    assert owner not in (0, os.getuid())
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings(
        [(0, exe, "UNSAFE_OWNER")],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_path_mode_symlink_executable_uses_final_target_owner(
    pathaudit_bin, tmp_path
):
    """Symlink resolution reports ownership of the final executable target."""

    target_dir, link_dir = _private_path_dirs(
        tmp_path, ("target-dir", "link-dir")
    )
    cmd = "tool"
    real = require_foreign_owned_executable(
        target_dir, cmd, mode=MODE_EXE_TRUSTED
    )
    link = link_dir / cmd
    link.symlink_to(real)
    result = run_pathaudit_path_mode(pathaudit_bin, str(link_dir.resolve()))
    code, expected = expect_path_findings(
        [(0, real, "UNSAFE_OWNER")],
        [(0, link_dir.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert link.resolve() == real
    assert escape_root(link) not in result.stdout


def test_path_mode_unsafe_owner_with_writability_orders_by_code_rank(
    pathaudit_bin, tmp_path
):
    """UNSAFE_OWNER interacts with GROUP/WORLD_WRITABLE under CODE_RANK order."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = require_foreign_owned_executable(
        private, "tool", mode=MODE_BOTH_WRITABLE
    )
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings(
        [
            (0, exe, "GROUP_WRITABLE"),
            (0, exe, "WORLD_WRITABLE"),
            (0, exe, "UNSAFE_OWNER"),
        ],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert CODE_RANK_INDEX["GROUP_WRITABLE"] < CODE_RANK_INDEX["UNSAFE_OWNER"]
    assert CODE_RANK_INDEX["WORLD_WRITABLE"] < CODE_RANK_INDEX["UNSAFE_OWNER"]
    assert result.stdout.find(b"GROUP_WRITABLE\t") < result.stdout.find(
        b"UNSAFE_OWNER\t"
    )
    assert result.stdout.find(b"WORLD_WRITABLE\t") < result.stdout.find(
        b"UNSAFE_OWNER\t"
    )


def test_path_mode_unsafe_owner_findings_precede_shadowed(
    pathaudit_bin, tmp_path
):
    """Ownership findings are shared-taxonomy output and precede SHADOWED."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    cmd = "tool"
    winner = require_foreign_owned_executable(
        early, cmd, mode=MODE_EXE_TRUSTED
    )
    shadow = install_executable(late, cmd, mode=MODE_EXE_TRUSTED)
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    code, owned = expect_path_findings(
        [(0, winner, "UNSAFE_OWNER")],
        [(0, early.resolve()), (1, late.resolve())],
    )
    expected = owned + shadowing_stdout([(cmd, winner, shadow)])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.find(b"UNSAFE_OWNER\t") < result.stdout.find(
        b"SHADOWED\t"
    )
    assert finding_line("UNSAFE_OWNER", shadow) not in result.stdout


def test_path_mode_directory_and_executable_ownership_both_report(
    pathaudit_bin, tmp_path
):
    """Directory writability and executable ownership coexist deterministically."""

    (world,) = _private_path_dirs(tmp_path, ("world",))
    os.chmod(world, MODE_WORLD_WRITABLE)
    exe = require_foreign_owned_executable(
        world, "tool", mode=MODE_EXE_TRUSTED
    )
    root = str(world.resolve())
    result = run_pathaudit_path_mode(pathaudit_bin, root)
    code, expected = expect_path_findings(
        [
            (0, root, "WORLD_WRITABLE"),
            (0, exe, "UNSAFE_OWNER"),
        ],
        [(0, root)],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_explicit_roots_do_not_report_unsafe_owner(
    pathaudit_bin, tmp_path
):
    """Explicit-root mode never searches executables or emits UNSAFE_OWNER."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = require_foreign_owned_executable(
        private, "tool", mode=MODE_EXE_TRUSTED
    )
    assert exe.stat().st_uid not in (0, os.getuid())
    result = run_pathaudit(pathaudit_bin, str(private.resolve()))
    assert result.returncode == 0
    assert result.stderr == b""
    assert result.stdout == b""
    assert b"UNSAFE_OWNER" not in result.stdout
    assert b"MATCH\t" not in result.stdout
    assert b"tool" not in result.stdout


def test_command_mode_current_user_owned_match_is_trusted(
    pathaudit_bin, fixture_tree
):
    """`--command` MATCH owned by getuid() is trusted; PATH ownership may still fire."""

    cmd = "tool"
    exe = install_executable(
        fixture_tree.private, cmd, mode=MODE_EXE_TRUSTED
    )
    assert exe.stat().st_uid == os.getuid()
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(fixture_tree.private)
    )
    code, expected = expect_command_query(
        [exe], [], [(0, fixture_tree.private)]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_root_owned_match_is_trusted_when_establishable(
    pathaudit_bin, tmp_path
):
    """Root-owned MATCH is trusted where the fixture can establish UID 0."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    cmd = "tool"
    exe = require_root_owned_executable(private, cmd, mode=MODE_EXE_TRUSTED)
    assert exe.stat().st_uid == 0
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(private.resolve())
    )
    code, expected = expect_command_query(
        [exe], [], [(0, private.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout


def test_command_mode_foreign_owned_match_reports_unsafe_owner(
    pathaudit_bin, tmp_path
):
    """`--command` emits MATCH then UNSAFE_OWNER for a foreign-owned target."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    cmd = "tool"
    exe = require_foreign_owned_executable(
        private, cmd, mode=MODE_EXE_TRUSTED
    )
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(private.resolve())
    )
    code, expected = expect_command_query(
        [exe],
        [(0, exe, "UNSAFE_OWNER")],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.startswith(match_line(exe))


def test_command_mode_symlink_match_uses_final_target_owner(
    pathaudit_bin, tmp_path
):
    """Symlinked MATCH ownership follows the final realpath target."""

    target_dir, link_dir = _private_path_dirs(
        tmp_path, ("target-dir", "link-dir")
    )
    cmd = "tool"
    real = require_foreign_owned_executable(
        target_dir, cmd, mode=MODE_EXE_TRUSTED
    )
    link = link_dir / cmd
    link.symlink_to(real)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(link_dir.resolve())
    )
    code, expected = expect_command_query(
        [link.resolve()],
        [(0, link.resolve(), "UNSAFE_OWNER")],
        [(0, link_dir.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    resolved = link.resolve()
    assert resolved == real
    assert result.stdout == expected


def test_command_mode_unsafe_owner_with_writability_orders_by_code_rank(
    pathaudit_bin, tmp_path
):
    """`--command` ranks GROUP/WORLD_WRITABLE before UNSAFE_OWNER on one target."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    cmd = "tool"
    exe = require_foreign_owned_executable(
        private, cmd, mode=MODE_BOTH_WRITABLE
    )
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(private.resolve())
    )
    code, expected = expect_command_query(
        [exe],
        [
            (0, exe, "GROUP_WRITABLE"),
            (0, exe, "WORLD_WRITABLE"),
            (0, exe, "UNSAFE_OWNER"),
        ],
        [(0, private.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_command_mode_writable_dir_and_unsafe_owner_both_report(
    pathaudit_bin, tmp_path
):
    """Directory plant-risk and executable ownership combine deterministically."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    os.chmod(early, MODE_GROUP_WRITABLE)
    cmd = "tool"
    exe = require_foreign_owned_executable(late, cmd, mode=MODE_EXE_TRUSTED)
    path_value = f"{early.resolve()}:{late.resolve()}"
    result = run_pathaudit_command_mode(pathaudit_bin, cmd, path_value)
    code, expected = expect_command_query(
        [exe],
        [
            (0, early.resolve(), "GROUP_WRITABLE"),
            (1, exe, "UNSAFE_OWNER"),
        ],
        [(0, early.resolve()), (1, late.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected


def test_path_mode_non_executable_foreign_owned_same_basename_is_not_reported(
    pathaudit_bin, tmp_path
):
    """Foreign-owned non-executable decoys are not UNSAFE_OWNER findings."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    decoy = private / "tool"
    decoy.write_bytes(b"not-executable\n")
    os.chmod(decoy, MODE_EXE_TRUSTED)
    candidates = _foreign_uid_candidates()
    if not candidates:
        pytest.skip("no distinct non-root foreign UID available on host")
    owned = False
    for uid in candidates:
        if _try_set_owner(decoy, uid):
            if decoy.stat().st_uid not in (0, os.getuid()):
                owned = True
                break
    if not owned:
        pytest.skip(
            "executing user lacks permission to create a distinct-owner fixture"
        )
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", decoy) not in result.stdout
    assert b"tool" not in result.stdout

# ---------------------------------------------------------------------------
# Detect unsafe ownership of PATH directories and ancestors
#
# Extends the established executable-ownership trust policy (UID 0 and getuid()
# trusted; every other final-target st_uid is UNSAFE_OWNER) to every usable PATH
# directory consulted by `--path` / `--command` and to each ancestor through `/`.
# Shared ancestor realpaths are deduplicated to the lowest PATH index that
# observed them. Findings name the canonical offending directory realpath.
# Missing, empty, and non-directory components stay reject/hazard-stable without
# inventing ownership lines. Explicit-root mode remains ownership-blind.
#
# Non-privileged coverage uses ambient untrusted ancestors of the temporary
# fixture tree when present, and optional in-tree foreign-owner directory plants
# when the host can establish them without requiring a successful chown for the
# suite to remain meaningful.
# ---------------------------------------------------------------------------


def _require_unsafe_path_dirs_for_gap(path: Path) -> list[Path]:
    """Return untrusted dirs on path's ancestor chain, or plant/skip as needed."""

    owned = [node for _, node, _ in ownership_finding_triples([(0, path)])]
    if owned:
        return owned

    # Try an in-tree foreign-owned parent so the gap is still coverable when the
    # host's ancestors through `/` are all trusted.
    parent = path.parent
    if parent == path:
        pytest.skip("no unsafe ancestor available and PATH entry has no parent")
    require_foreign_owned_directory(parent)
    owned = [node for _, node, _ in ownership_finding_triples([(0, path)])]
    if not owned:
        pytest.skip("host cannot expose an unsafe PATH directory or ancestor")
    return owned


def test_path_mode_trusted_path_directory_ownership_is_accepted(
    pathaudit_bin, tmp_path
):
    """Invoking-UID PATH directories themselves are trusted under the shared policy."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    assert private.stat().st_uid == os.getuid()
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # The PATH entry itself must not be named when it is trusted.
    assert finding_line("UNSAFE_OWNER", private.resolve()) not in result.stdout


def test_path_mode_reports_unsafe_ancestors_of_trusted_path_directory(
    pathaudit_bin, tmp_path
):
    """Trusted PATH entry still reports untrusted ancestors through `/`."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    unsafe = _require_unsafe_path_dirs_for_gap(private.resolve())
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    for node in unsafe:
        assert finding_line("UNSAFE_OWNER", node) in result.stdout
    assert finding_line("UNSAFE_OWNER", private.resolve()) not in result.stdout


def test_path_mode_trusted_executable_through_unsafe_ancestor_reports_directory(
    pathaudit_bin, tmp_path
):
    """Security gap: trusted executable via unsafe ancestor still emits UNSAFE_OWNER."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    exe = install_executable(private, "tool", mode=MODE_EXE_TRUSTED)
    assert ownership_is_trusted(exe.stat().st_uid)
    unsafe = _require_unsafe_path_dirs_for_gap(private.resolve())
    result = run_pathaudit_path_mode(pathaudit_bin, str(private.resolve()))
    code, expected = expect_path_findings([], [(0, private.resolve())])
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout
    for node in unsafe:
        assert finding_line("UNSAFE_OWNER", node) in result.stdout


def test_path_mode_foreign_owned_path_directory_reports_unsafe_owner_when_establishable(
    pathaudit_bin, tmp_path
):
    """Foreign-owned PATH directory itself is UNSAFE_OWNER when chown works."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    foreign = require_foreign_owned_directory(private)
    assert not ownership_is_trusted(foreign.stat().st_uid)
    result = run_pathaudit_path_mode(pathaudit_bin, str(foreign.resolve()))
    code, expected = expect_path_findings([], [(0, foreign.resolve())])
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    assert finding_line("UNSAFE_OWNER", foreign.resolve()) in result.stdout


def test_path_mode_shared_ancestors_dedup_to_lowest_path_index(
    pathaudit_bin, tmp_path
):
    """Shared untrusted ancestors appear once at the earliest PATH index."""

    early, late = _private_path_dirs(tmp_path, ("early", "late"))
    result = run_pathaudit_path_mode(
        pathaudit_bin, f"{early.resolve()}:{late.resolve()}"
    )
    triples = ownership_finding_triples(
        [(0, early.resolve()), (1, late.resolve())]
    )
    code, expected = expect_path_findings(
        [], [(0, early.resolve()), (1, late.resolve())]
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # Each offending realpath appears exactly once.
    for _, node, _ in triples:
        assert result.stdout.count(finding_line("UNSAFE_OWNER", node)) == 1


def test_path_mode_missing_and_nondirectory_skip_ownership_walk(
    pathaudit_bin, fixture_tree
):
    """Missing/non-directory PATH entries do not invent ownership findings."""

    missing = run_pathaudit_path_mode(
        pathaudit_bin, str(fixture_tree.missing)
    )
    assert missing.returncode == 1
    assert missing.stderr == b""
    assert missing.stdout == findings_stdout(
        [("MISSING_ROOT", fixture_tree.missing)]
    )
    assert b"UNSAFE_OWNER" not in missing.stdout

    nondir = run_pathaudit_path_mode(
        pathaudit_bin, str(fixture_tree.regular)
    )
    assert nondir.returncode == 1
    assert nondir.stderr == b""
    assert nondir.stdout == findings_stdout(
        [("NON_DIRECTORY_ROOT", fixture_tree.regular)]
    )
    assert b"UNSAFE_OWNER" not in nondir.stdout


def test_path_mode_empty_component_preserves_diagnostics_without_ownership(
    pathaudit_bin,
):
    """Empty PATH fields stay EMPTY_ROOT-only (no ownership walk of cwd here)."""

    result = run_pathaudit_path_mode(pathaudit_bin, "")
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout([("EMPTY_ROOT", b"")])
    assert b"UNSAFE_OWNER" not in result.stdout


def test_command_mode_trusted_match_through_unsafe_ancestor_reports_directory(
    pathaudit_bin, tmp_path
):
    """`--command` MATCH owned by getuid() still reports unsafe PATH ancestors."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    cmd = "tool"
    exe = install_executable(private, cmd, mode=MODE_EXE_TRUSTED)
    unsafe = _require_unsafe_path_dirs_for_gap(private.resolve())
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(private.resolve())
    )
    code, expected = expect_command_query(
        [exe], [], [(0, private.resolve())]
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    assert result.stdout.startswith(match_line(exe))
    assert finding_line("UNSAFE_OWNER", exe) not in result.stdout
    for node in unsafe:
        assert finding_line("UNSAFE_OWNER", node) in result.stdout


def test_command_mode_ownership_composes_with_writability_under_code_rank(
    pathaudit_bin, tmp_path
):
    """Directory WORLD_WRITABLE ranks before PATH/ancestor UNSAFE_OWNER."""

    (world,) = _private_path_dirs(tmp_path, ("world",))
    os.chmod(world, MODE_WORLD_WRITABLE)
    cmd = "tool"
    exe = install_executable(world, cmd, mode=MODE_EXE_TRUSTED)
    result = run_pathaudit_command_mode(
        pathaudit_bin, cmd, str(world.resolve())
    )
    code, expected = expect_command_query(
        [exe],
        [(0, world.resolve(), "WORLD_WRITABLE")],
        [(0, world.resolve())],
    )
    assert result.returncode == code
    assert result.stderr == b""
    assert result.stdout == expected
    # Per-root code rank: WORLD_WRITABLE precedes UNSAFE_OWNER when both name
    # the same directory realpath. Cross-root order follows root-byte sort.
    world_line = finding_line("WORLD_WRITABLE", world.resolve())
    owner_line = finding_line("UNSAFE_OWNER", world.resolve())
    if owner_line in result.stdout:
        assert result.stdout.find(world_line) < result.stdout.find(owner_line)


def test_explicit_roots_remain_ownership_blind_for_directories(
    pathaudit_bin, tmp_path
):
    """Explicit-root mode does not emit PATH/ancestor UNSAFE_OWNER findings."""

    (private,) = _private_path_dirs(tmp_path, ("private",))
    # Even when ambient ancestors are untrusted, explicit-root stays blind.
    result = run_pathaudit(pathaudit_bin, str(private.resolve()))
    assert result.returncode == 0
    assert result.stderr == b""
    assert result.stdout == b""
    assert b"UNSAFE_OWNER" not in result.stdout
