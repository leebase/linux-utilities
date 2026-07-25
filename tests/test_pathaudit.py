"""Contract tests for the pathaudit vertical slice.

Encodes docs/pathaudit-contract.md. Builds src/pathaudit.c into a test-owned
temporary directory, exercises only deterministic temporary fixtures, and never
inspects the worker's real PATH, requires root, uses the network, or leaves
binaries in the workspace. Sanitizer/Valgrind options declared by Makefile
memory gates are allowlist-forwarded into the child environment.

Also encodes the stable Makefile contract for pathaudit-sanitize and
pathaudit-valgrind: ASan+UBSan with strict warnings and frame pointers, a
separate non-sanitized Valgrind debug binary with full leak checking and a
nonzero error-exitcode, temporary paths under /tmp cleaned on every exit, and
regression pins for existing pathaudit behavior and Make targets.
"""

from __future__ import annotations

import errno as errno_mod
import os
import re
import shutil
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

HELP_STDOUT = (
    b"usage: pathaudit [--] ROOT...\n"
    b"Scan explicitly supplied PATH directory roots.\n"
)
VERSION_STDOUT = b"pathaudit 0.1.0\n"
USAGE_LINE = b"usage: pathaudit [--] ROOT...\n"

CODE_RANK = (
    "EMPTY_ROOT",
    "RELATIVE_ROOT",
    "MISSING_ROOT",
    "NON_DIRECTORY_ROOT",
    "GROUP_WRITABLE",
    "WORLD_WRITABLE",
)
CODE_RANK_INDEX = {code: index for index, code in enumerate(CODE_RANK)}

MAX_ROOT_COUNT = 65536
MAX_ROOT_LENGTH = 65536
MAX_ROOT_BYTES = 1024 * 1024

# Controllable mode bits only (no ownership policy assertions).
MODE_PRIVATE = 0o700
MODE_GROUP_WRITABLE = 0o720
MODE_WORLD_WRITABLE = 0o702
MODE_BOTH_WRITABLE = 0o722


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


def findings_stdout(
    items: list[tuple[str, bytes | str | os.PathLike[str]]],
) -> bytes:
    """Build expected stdout for (code, root) pairs already in contract order."""

    return b"".join(finding_line(code, root) for code, root in items)


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


def _base_child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a PATH-hardened child env, forwarding declared sanitizer knobs."""

    run_env = {
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
        run_env.update(extra)
    return run_env


def run_pathaudit(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
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


def run_with_closed_stdout_pipe(binary: Path, *args: str):
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    cmd, vg_log = _valgrind_command([str(binary), *args])
    proc = subprocess.Popen(
        cmd,
        stdout=write_fd,
        stderr=subprocess.PIPE,
        env=_base_child_env(),
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
    for code in CODE_RANK:
        assert code.encode("ascii") in result.stdout


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


def test_closed_stdout_pipe_reports_stdout_write(pathaudit_bin, fixture_tree):
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
    """PAC-M1: make -n test-suite must scrub ambient PATHAUDIT routing."""

    if shutil.which("make") is None:
        pytest.skip("GNU make required for Makefile seam checks")

    makefile = _read_makefile()
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in makefile
    assert 'SYSDIFF_BIN="$(CURDIR)/$(BIN)"' in makefile

    dry = _make_dry_run("test-suite")
    assert dry.returncode == 0, dry.stderr + dry.stdout
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in dry.stdout
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
            "tests/test_pathaudit.py::test_help_and_version",
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
            "tests/test_pathaudit.py::test_help_and_version",
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
        assert "mktemp" in recipe
        assert "trap" in recipe
        assert "PATHAUDIT_BIN" in recipe

    # Non-writing default pathaudit recipe remains (no workspace binary).
    pathaudit_recipe = _makefile_target_block(makefile, "pathaudit")
    assert "mktemp" in pathaudit_recipe
    assert "trap" in pathaudit_recipe
    assert "build/pathaudit" not in pathaudit_recipe

    # Existing scrub / routing contracts stay intact.
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in makefile
    test_suite = _makefile_target_block(makefile, "test-suite")
    assert "env -u PATHAUDIT_BIN -u PATHAUDIT_UNDER_VALGRIND" in test_suite

    # Dry-run pins: existing targets still expand without error.
    for target in ("pathaudit", "test-asan", "test-valgrind", "test-suite"):
        dry = _make_dry_run(target)
        assert dry.returncode == 0, f"{target}: {dry.stderr + dry.stdout}"


def test_pathaudit_behavior_contract_pins_remain_stable():
    """Protect existing pathaudit CLI/hazard contract surface from drift."""

    assert HELP_STDOUT.startswith(b"usage: pathaudit")
    assert VERSION_STDOUT == b"pathaudit 0.1.0\n"
    assert CODE_RANK == (
        "EMPTY_ROOT",
        "RELATIVE_ROOT",
        "MISSING_ROOT",
        "NON_DIRECTORY_ROOT",
        "GROUP_WRITABLE",
        "WORLD_WRITABLE",
    )
    assert MAX_ROOT_COUNT == 65536
    assert MAX_ROOT_LENGTH == 65536
    assert MAX_ROOT_BYTES == 1024 * 1024
    assert escape_root(b"a\npathaudit: FORGED") == b'"a\\x0Apathaudit: FORGED"'
    assert finding_line("EMPTY_ROOT", b"") == b'EMPTY_ROOT\t""\n'
    assert SRC.is_file()
    assert MAKEFILE.is_file()
