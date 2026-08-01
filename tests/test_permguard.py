"""Contract tests for the permguard bootstrap slice.

Encodes docs/permguard-bootstrap-contract.md and the Medium-repairs acceptance
contract in docs/permguard-medium-repairs-contract.md. Builds src/permguard.c
into a pytest-owned temporary directory, exercises only deterministic temporary
fixtures with lstat-visible mode bits, and never leaves binaries in the
workspace. Child processes receive a sealed, locale-stable environment.
Missing source fails closed; host-capability skips state the missing
capability explicitly and are never reported as passes.

Coverage maps to bootstrap acceptance checks AC-01 through AC-09: CLI/usage,
clean and hazardous file/directory fixtures, every closed taxonomy bit and
combinations, multi-operand ordering with duplicates, missing/inaccessible/
invalid operands, symlink non-follow for safe and hazardous targets,
mixed-success precedence, exact statuses 0/1/2 with pinned stdout/stderr
bytes, and a narrow lstat-only inspection surface.

Medium-repairs coverage maps to PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and
PG-DOC-512 (contract AC-01..AC-07): architecture and authority-document pins,
STDOUT_WRITE / ignored-SIGPIPE regressions, header-owned POSIX lstat plus
pytest/Make `_POSIX_C_SOURCE` flags, and QUALITY/TESTING gate membership.

Hostile-filesystem fixture coverage maps to the additive contract in
docs/permguard-hostile-filesystem-fixtures-contract.md (PGH_* taxonomy labels
are test-plan only and must never appear in product stdout/stderr): dangling
final links, final and intermediate symbolic-link loops, mode-000 versus
EACCES inaccessibility, sequential permission transitions, unusual names,
deep paths, FIFO/special files, and deterministic replacement-race seams.
"""

from __future__ import annotations

import errno
import os
import re
import shutil
import signal
import socket
import stat as stat_mod
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "permguard.c"
MAKEFILE = ROOT / "Makefile"
CONTRACT = ROOT / "docs" / "permguard-bootstrap-contract.md"
HOSTILE_FIXTURES_CONTRACT = (
    ROOT / "docs" / "permguard-hostile-filesystem-fixtures-contract.md"
)
MEDIUM_REPAIRS_CONTRACT = ROOT / "docs" / "permguard-medium-repairs-contract.md"
ONE_CODE_CONTRACT = ROOT / "docs" / "permguard-first-vertical-slice-contract.md"
ONE_CODE_PLAN = ROOT / "plans" / "permguard-first-vertical-slice-plan.md"
ARCHITECTURE = ROOT / "architecture.md"
QUALITY = ROOT / "QUALITY.md"
TESTING = ROOT / "TESTING.md"
SMOKE_MANIFEST = ROOT / "tests" / "smoke_manifest.json"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke.sh"

# Bounded timeouts so an accidental FIFO open / loop follow fails the test
# instead of hanging the suite (hostile-fixture contract).
PERMGUARD_HOSTILE_TIMEOUT_SEC = 15.0

HOSTILE_FIXTURE_HAZARDS = (
    "PGH_DANGLING_SYMBOLIC_LINK",
    "PGH_SYMBOLIC_LINK_LOOP",
    "PGH_UNREADABLE_ENTRY",
    "PGH_PERMISSION_CHANGE",
    "PGH_UNUSUAL_FILENAME",
    "PGH_DEEP_PATH",
    "PGH_FIFO_OR_SPECIAL_FILE",
    "PGH_REPLACEMENT_RACE",
)

MODE_UNREADABLE = 0o000

STRICT_WARNING_FLAGS = (
    "-std=c17",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
)

# Intended permguard compile contract (PG-PORT-505 / AC-03): libc owns lstat
# via the platform header under an explicit POSIX feature-test flag.
POSIX_C_SOURCE_FLAG = "-D_POSIX_C_SOURCE=200809L"

MEDIUM_REPAIR_FINDING_IDS = (
    "PG-DOC-501",
    "PG-DOC-502",
    "PG-TEST-503",
    "PG-PORT-505",
    "PG-DOC-512",
)

# Surfaces named in the Medium-repairs blast radius. A path being listed does
# not require a textual edit in every repair; each must stay consistent.
MEDIUM_REPAIR_BLAST_RADIUS = (
    "src/permguard.c",
    "Makefile",
    "tests/test_permguard.py",
    "tests/smoke_manifest.json",
    "scripts/smoke.sh",
    "README.md",
    "man/permguard.1",
    "CHANGELOG.md",
    "architecture.md",
    "QUALITY.md",
    "TESTING.md",
    "docs/permguard-bootstrap-contract.md",
    "docs/permguard.md",
    "docs/permguard-first-vertical-slice-contract.md",
    "plans/permguard-bootstrap-implementation-plan.md",
    "plans/permguard-first-vertical-slice-plan.md",
)

SANITIZER_ENV_KEYS = (
    "ASAN_OPTIONS",
    "UBSAN_OPTIONS",
    "LSAN_OPTIONS",
    "ASAN_SYMBOLIZER_PATH",
)

USAGE_SYNOPSIS = b"usage: permguard [--] PATH...\n"

# Closed bootstrap taxonomy in fixed emission rank.
HAZARD_RANK = (
    "GROUP_WRITABLE",
    "OTHER_WRITABLE",
    "SET_USER_ID",
    "SET_GROUP_ID",
)
HAZARD_RANK_INDEX = {code: index for index, code in enumerate(HAZARD_RANK)}

# Controllable mode bits. Always chmod after create, then re-read via lstat.
MODE_CLEAN_FILE = 0o600
MODE_OWNER_WRITABLE_FILE = 0o644
MODE_GROUP_WRITABLE_FILE = 0o620
MODE_OTHER_WRITABLE_FILE = 0o602
MODE_BOTH_WRITABLE_FILE = 0o622
MODE_SETUID_FILE = 0o4600
MODE_SETGID_FILE = 0o2600
MODE_SETUID_SETGID_FILE = 0o6600
MODE_ALL_FOUR_FILE = 0o6622
MODE_CLEAN_DIR = 0o700
MODE_GROUP_WRITABLE_DIR = 0o720
MODE_OTHER_WRITABLE_DIR = 0o702
MODE_BOTH_WRITABLE_DIR = 0o722
MODE_SETGID_DIR = 0o2700
MODE_STICKY_CLEAN_DIR = 0o1700

MODE_MASK = (
    stat_mod.S_IRWXU
    | stat_mod.S_IRWXG
    | stat_mod.S_IRWXO
    | stat_mod.S_ISUID
    | stat_mod.S_ISGID
    | stat_mod.S_ISVTX
)

CONTRACT_HEADINGS = (
    "Authority",
    "Overview",
    "CLI Surface",
    "Hazard Taxonomy",
    "Exit Statuses",
    "Constraints",
    "Acceptance Checks",
)


def escape_path(path: bytes | str | os.PathLike[str]) -> bytes:
    """Quote-escape an operand the way permguard must emit it."""

    if isinstance(path, bytes):
        data = path
    else:
        data = os.fsencode(os.fspath(path))
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


def hazards_for_mode(mode: int) -> list[str]:
    """Return present bootstrap hazard codes in fixed taxonomy rank."""

    codes: list[str] = []
    if mode & stat_mod.S_IWGRP:
        codes.append("GROUP_WRITABLE")
    if mode & stat_mod.S_IWOTH:
        codes.append("OTHER_WRITABLE")
    if mode & stat_mod.S_ISUID:
        codes.append("SET_USER_ID")
    if mode & stat_mod.S_ISGID:
        codes.append("SET_GROUP_ID")
    return codes


def finding_line(code: str, path: bytes | str | os.PathLike[str]) -> bytes:
    if code not in HAZARD_RANK_INDEX:
        raise ValueError(f"unknown hazard code: {code}")
    return f"{code}\t".encode("ascii") + escape_path(path) + b"\n"


def findings_stdout(
    items: list[tuple[str, bytes | str | os.PathLike[str]]],
) -> bytes:
    """Build expected stdout for (code, path) pairs already in contract order."""

    return b"".join(finding_line(code, path) for code, path in items)


def findings_for_path(
    path: bytes | str | os.PathLike[str], mode: int
) -> bytes:
    return findings_stdout([(code, path) for code in hazards_for_mode(mode)])


def assert_no_raw_unsafe_bytes(data: bytes) -> None:
    for index, byte in enumerate(data):
        if byte == 0x0A or byte == 0x09:
            continue
        if byte < 0x20 or byte > 0x7E:
            raise AssertionError(
                f"unsafe raw byte 0x{byte:02X} at offset {index} in output"
            )


def diagnostic_usage() -> bytes:
    return b"permguard: USAGE\n" + USAGE_SYNOPSIS


def diagnostic_unknown_option(option: bytes | str) -> bytes:
    return (
        b"permguard: UNKNOWN_OPTION: "
        + escape_path(option)
        + b"\n"
        + USAGE_SYNOPSIS
    )


def diagnostic_operand(reason: str, path: bytes | str | os.PathLike[str]) -> bytes:
    return (
        f"permguard: {reason}: ".encode("ascii") + escape_path(path) + b"\n"
    )


def diagnostic_missing(path: bytes | str | os.PathLike[str]) -> bytes:
    return diagnostic_operand("MISSING", path)


def diagnostic_inaccessible(path: bytes | str | os.PathLike[str]) -> bytes:
    return diagnostic_operand("INACCESSIBLE", path)


def diagnostic_symbolic_link(path: bytes | str | os.PathLike[str]) -> bytes:
    return diagnostic_operand("SYMBOLIC_LINK", path)


def diagnostic_inspection_error(
    errno_value: int, path: bytes | str | os.PathLike[str]
) -> bytes:
    return diagnostic_operand(f"INSPECTION_ERROR_{errno_value}", path)


def diagnostic_stdout_write() -> bytes:
    """Exact stderr for checked stdout write/flush failure (PG-TEST-503)."""

    return b"permguard: STDOUT_WRITE\n"


def _mode_bits(path: Path) -> int:
    return os.lstat(path).st_mode


def require_mode(path: Path, expected: int, *, label: str) -> None:
    """Fail closed / skip when the fixture cannot represent required mode bits."""

    actual = _mode_bits(path)
    wanted = expected & MODE_MASK
    got = actual & MODE_MASK
    if got != wanted:
        pytest.skip(
            f"host filesystem cannot establish {label} mode "
            f"0o{wanted:04o} on {path} (got 0o{got:04o})"
        )


def write_regular(path: Path, mode: int, data: bytes = b"payload\n") -> Path:
    """Create a regular file, chmod last, and verify lstat-visible mode bits."""

    path.write_bytes(data)
    os.chmod(path, mode)
    require_mode(path, mode, label="regular-file")
    assert stat_mod.S_ISREG(_mode_bits(path))
    return path


def write_setid_regular(path: Path, mode: int) -> Path:
    """Create a set-ID regular file; skip only when set-ID bits cannot stick."""

    return write_regular(path, mode, data=b"#!/bin/sh\nexit 0\n")


def make_directory(path: Path, mode: int) -> Path:
    path.mkdir(exist_ok=True)
    os.chmod(path, mode)
    require_mode(path, mode, label="directory")
    assert stat_mod.S_ISDIR(_mode_bits(path))
    return path


def snapshot_entry(path: Path) -> tuple[int, bytes | None]:
    """Record lstat mode and, for regular files, content bytes."""

    mode = _mode_bits(path)
    if stat_mod.S_ISREG(mode):
        return mode, path.read_bytes()
    return mode, None


def assert_unchanged(path: Path, before: tuple[int, bytes | None]) -> None:
    after = snapshot_entry(path)
    assert after == before, f"permguard mutated fixture {path}"


def _valgrind_command(cmd: list[str]):
    if os.environ.get("PERMGUARD_UNDER_VALGRIND") != "1":
        return cmd, None

    valgrind = shutil.which("valgrind")
    if valgrind is None:
        raise AssertionError(
            "PERMGUARD_UNDER_VALGRIND=1 but valgrind was not found on PATH"
        )

    fd, vg_log = tempfile.mkstemp(prefix="permguard-valgrind.", dir="/tmp")
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
    """Build a sealed child env, forwarding declared sanitizer knobs."""

    run_env: dict[str, str] = {
        "PATH": "/permguard-tests-must-not-search-here",
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


def run_permguard(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str | None] | None = None,
    timeout: float | None = None,
):
    """Run permguard with byte-preserving argv and a controlled environment."""

    argv: list[str] = [str(binary)]
    for arg in args:
        if isinstance(arg, bytes):
            argv.append(os.fsdecode(arg))
        else:
            argv.append(os.fspath(arg))

    cmd, vg_log = _valgrind_command(argv)
    result = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        cwd=None if cwd is None else os.fspath(cwd),
        env=_base_child_env(env),
        timeout=timeout,
    )
    return _finish_valgrind(result, vg_log)


def run_permguard_hostile(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str | None] | None = None,
):
    """Hostile-fixture runs always carry a bounded timeout."""

    return run_permguard(
        binary,
        *args,
        cwd=cwd,
        env=env,
        timeout=PERMGUARD_HOSTILE_TIMEOUT_SEC,
    )


def _argv_for_permguard(
    binary: Path, *args: bytes | str | os.PathLike[str]
) -> list[str]:
    argv: list[str] = [str(binary)]
    for arg in args:
        if isinstance(arg, bytes):
            argv.append(os.fsdecode(arg))
        else:
            argv.append(os.fspath(arg))
    return argv


def run_with_closed_stdout_pipe(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    env: dict[str, str | None] | None = None,
):
    """Run permguard with stdout attached to a pipe whose reader is closed.

    Descriptor ownership: the parent closes the read end before Popen, passes
    only the write end as child stdout, then closes its own write-end copy so
    the child alone holds the writer. No parent reader remains that could
    accidentally drain or deadlock the pipe.
    """

    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    cmd, vg_log = _valgrind_command(_argv_for_permguard(binary, *args))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=write_fd,
            stderr=subprocess.PIPE,
            env=_base_child_env(env),
        )
    finally:
        os.close(write_fd)
    _, stderr = proc.communicate()
    _finish_valgrind(types.SimpleNamespace(returncode=proc.returncode), vg_log)
    return proc.returncode, stderr


def run_with_stdout_to_dev_full(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    env: dict[str, str | None] | None = None,
):
    """Run permguard with stdout redirected to /dev/full when the host allows.

    Returns (status, stderr). Skips with an explicit host-capability reason
    when /dev/full is absent or unsuitable — never counts as a pass.
    """

    full_path = Path("/dev/full")
    if not full_path.exists():
        pytest.skip(
            "host lacks /dev/full; cannot exercise STDOUT_WRITE device failure"
        )
    try:
        full_fd = os.open(full_path, os.O_WRONLY)
    except OSError as exc:
        pytest.skip(
            f"host /dev/full is not usable for write "
            f"(errno {exc.errno}); cannot exercise STDOUT_WRITE device failure"
        )

    # Suitability probe (PGR-TEST-705 / AC-04): character device that returns
    # ENOSPC on write. A regular file or null-style sink must not be treated
    # as a product regression when status 1 is returned instead of 2.
    mode = os.fstat(full_fd).st_mode
    if not stat_mod.S_ISCHR(mode):
        os.close(full_fd)
        pytest.skip(
            "host /dev/full is not a character device "
            f"(st_mode 0o{mode:o}); cannot exercise STDOUT_WRITE "
            "device failure"
        )
    try:
        os.write(full_fd, b"\0")
    except OSError as exc:
        if exc.errno != errno.ENOSPC:
            os.close(full_fd)
            pytest.skip(
                "host /dev/full write failed with errno "
                f"{exc.errno} rather than ENOSPC; cannot exercise "
                "STDOUT_WRITE device failure"
            )
        # ENOSPC — suitable full device; keep full_fd for the child.
    else:
        os.close(full_fd)
        pytest.skip(
            "host /dev/full accepted a write without ENOSPC; "
            "unsuitable for STDOUT_WRITE device failure"
        )

    cmd, vg_log = _valgrind_command(_argv_for_permguard(binary, *args))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=full_fd,
            stderr=subprocess.PIPE,
            env=_base_child_env(env),
        )
    finally:
        os.close(full_fd)
    _, stderr = proc.communicate()
    _finish_valgrind(types.SimpleNamespace(returncode=proc.returncode), vg_log)
    return proc.returncode, stderr


def resolve_permguard_override(env_bin: str) -> Path:
    """Resolve PERMGUARD_BIN once so a relative override cannot track cwd."""

    resolved = Path(env_bin).expanduser().resolve()
    if not resolved.is_absolute():
        raise ValueError(
            f"PERMGUARD_BIN did not resolve to an absolute path: {env_bin!r}"
        )
    return resolved


# Last compile argv used by the session fixture when it builds from source.
# Empty when PERMGUARD_BIN overrides compilation (PGR-TEST-703).
_LAST_PERMGUARD_COMPILE_ARGV: list[str] = []


@pytest.fixture(scope="session")
def permguard_bin(tmp_path_factory):
    env_bin = os.environ.get("PERMGUARD_BIN")
    if env_bin:
        binary = resolve_permguard_override(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"PERMGUARD_BIN is not an executable file: {env_bin}")
        _LAST_PERMGUARD_COMPILE_ARGV.clear()
        return binary

    if not SRC.is_file():
        pytest.fail(
            f"{SRC} is missing; permguard bootstrap suite requires the source"
        )

    # Compile into pytest's session temp tree only — never build/ or the repo.
    # PG-PORT-505: pass the POSIX feature-test flag on the compiler command
    # line so <sys/stat.h> owns lstat (no hand-written prototype).
    build_dir = tmp_path_factory.mktemp("permguard-build")
    binary = build_dir / "permguard"
    compile_argv = [
        os.environ.get("CC", "cc"),
        *STRICT_WARNING_FLAGS,
        POSIX_C_SOURCE_FLAG,
        "-o",
        str(binary),
        str(SRC),
    ]
    compile_result = subprocess.run(
        compile_argv,
        capture_output=True,
        check=False,
    )
    if compile_result.returncode != 0:
        detail = compile_result.stderr.decode("utf-8", errors="replace")
        pytest.fail(f"failed to compile {SRC} into {binary}:\n{detail}")
    assert binary.is_file()
    assert os.access(binary, os.X_OK)
    assert binary.resolve() != (ROOT / "permguard").resolve()
    assert binary.resolve() != (ROOT / "build" / "permguard").resolve()
    _LAST_PERMGUARD_COMPILE_ARGV[:] = list(compile_argv)
    return binary


@pytest.fixture
def fixtures(tmp_path):
    """Deterministic absolute paths with exact, lstat-visible permission bits."""

    os.chmod(tmp_path, MODE_CLEAN_DIR)

    clean_file = write_regular(tmp_path / "clean-file", MODE_CLEAN_FILE)
    owner_file = write_regular(
        tmp_path / "owner-file", MODE_OWNER_WRITABLE_FILE
    )
    group_file = write_regular(
        tmp_path / "group-file", MODE_GROUP_WRITABLE_FILE
    )
    other_file = write_regular(
        tmp_path / "other-file", MODE_OTHER_WRITABLE_FILE
    )
    both_writable = write_regular(
        tmp_path / "both-writable", MODE_BOTH_WRITABLE_FILE
    )

    clean_dir = make_directory(tmp_path / "clean-dir", MODE_CLEAN_DIR)
    group_dir = make_directory(
        tmp_path / "group-dir", MODE_GROUP_WRITABLE_DIR
    )
    other_dir = make_directory(
        tmp_path / "other-dir", MODE_OTHER_WRITABLE_DIR
    )
    sticky_dir = make_directory(
        tmp_path / "sticky-clean-dir", MODE_STICKY_CLEAN_DIR
    )

    safe_target = write_regular(tmp_path / "safe-target", MODE_CLEAN_FILE)
    hazardous_target = write_regular(
        tmp_path / "hazardous-target", MODE_OTHER_WRITABLE_FILE
    )

    link_to_safe = tmp_path / "link-to-safe"
    link_to_safe.symlink_to(safe_target)
    assert stat_mod.S_ISLNK(_mode_bits(link_to_safe))

    link_to_hazardous = tmp_path / "link-to-hazardous"
    link_to_hazardous.symlink_to(hazardous_target)
    assert stat_mod.S_ISLNK(_mode_bits(link_to_hazardous))

    dangling = tmp_path / "dangling-symlink"
    dangling.symlink_to("definitely-absent-target")
    assert stat_mod.S_ISLNK(_mode_bits(dangling))

    missing = tmp_path / "missing-path"
    assert not missing.exists()

    unusual = write_regular(
        tmp_path / 'name with "quotes" and \\backslashes\\',
        MODE_CLEAN_FILE,
    )

    control_name = os.fsdecode(b"name-with-\x1b-esc")
    control_path = write_regular(
        tmp_path / control_name, MODE_OTHER_WRITABLE_FILE
    )

    non_utf8_name = os.fsdecode(b"name-with-\xff-byte")
    non_utf8 = write_regular(tmp_path / non_utf8_name, MODE_CLEAN_FILE)

    return types.SimpleNamespace(
        root=tmp_path,
        clean_file=clean_file,
        owner_file=owner_file,
        group_file=group_file,
        other_file=other_file,
        both_writable=both_writable,
        clean_dir=clean_dir,
        group_dir=group_dir,
        other_dir=other_dir,
        sticky_dir=sticky_dir,
        safe_target=safe_target,
        hazardous_target=hazardous_target,
        link_to_safe=link_to_safe,
        link_to_hazardous=link_to_hazardous,
        dangling=dangling,
        missing=missing,
        unusual=unusual,
        control_path=control_path,
        non_utf8=non_utf8,
    )


# ---------------------------------------------------------------------------
# Unit-style: escaping helpers, usage grammar, status matrix
# ---------------------------------------------------------------------------


def test_unit_escape_path_printable_and_hostile_bytes():
    assert escape_path(b"plain") == b'"plain"'
    assert escape_path(b'a"b\\c') == b'"a\\"b\\\\c"'
    assert escape_path(b"a\tb\nc\x1b\xff") == (
        b'"a\\x09b\\x0Ac\\x1B\\xFF"'
    )
    assert escape_path("ascii") == b'"ascii"'


def test_unit_finding_line_shape_and_rank():
    assert HAZARD_RANK == (
        "GROUP_WRITABLE",
        "OTHER_WRITABLE",
        "SET_USER_ID",
        "SET_GROUP_ID",
    )
    line = finding_line("GROUP_WRITABLE", "/tmp/x")
    assert line == b'GROUP_WRITABLE\t"/tmp/x"\n'
    assert_no_raw_unsafe_bytes(line)
    assert hazards_for_mode(MODE_ALL_FOUR_FILE) == list(HAZARD_RANK)
    assert hazards_for_mode(MODE_CLEAN_FILE) == []
    assert hazards_for_mode(MODE_OWNER_WRITABLE_FILE) == []


def test_unit_no_operands_is_usage_error(permguard_bin):
    result = run_permguard(permguard_bin)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_usage()


def test_unit_bare_double_dash_is_usage_error(permguard_bin):
    result = run_permguard(permguard_bin, "--")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_usage()


def test_unit_unknown_option_is_usage_error(permguard_bin):
    result = run_permguard(permguard_bin, "--bogus")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_unknown_option("--bogus")


def test_unit_help_is_sole_argument(permguard_bin):
    """Sole-argument --help matches the quality-floor probe and suite CLI."""

    help_stdout = (
        b"usage: permguard [--] PATH...\n"
        b"Inspect explicitly supplied paths without following symbolic links.\n"
    )
    result = run_permguard(permguard_bin, "--help")
    assert result.returncode == 0
    assert result.stdout == help_stdout
    assert result.stderr == b""

    extra = run_permguard(permguard_bin, "--help", "extra")
    assert extra.returncode == 2
    assert extra.stdout == b""
    assert extra.stderr == diagnostic_usage()


def test_unit_version_is_sole_argument(permguard_bin):
    result = run_permguard(permguard_bin, "--version")
    assert result.returncode == 0
    assert result.stdout == b"permguard 0.1.0\n"
    assert result.stderr == b""

    extra = run_permguard(permguard_bin, "--version", "extra")
    assert extra.returncode == 2
    assert extra.stdout == b""
    assert extra.stderr == diagnostic_usage()


def test_unit_unknown_option_hostile_bytes_are_escaped(permguard_bin):
    option = b"--bogus\x1b\xff"
    result = run_permguard(permguard_bin, option)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_unknown_option(option)
    assert b"\x1b" not in result.stderr
    assert b"\xff" not in result.stderr
    assert_no_raw_unsafe_bytes(result.stderr)


def test_unit_exit_status_matrix(permguard_bin, fixtures):
    clean = run_permguard(permguard_bin, fixtures.clean_file, fixtures.clean_dir)
    assert clean.returncode == 0
    assert clean.stdout == b""
    assert clean.stderr == b""

    hazard = run_permguard(permguard_bin, fixtures.other_file)
    assert hazard.returncode == 1
    assert hazard.stderr == b""
    assert hazard.stdout == findings_for_path(
        fixtures.other_file, MODE_OTHER_WRITABLE_FILE
    )

    usage = run_permguard(permguard_bin)
    assert usage.returncode == 2
    assert usage.stdout == b""
    assert usage.stderr == diagnostic_usage()

    missing = run_permguard(permguard_bin, fixtures.missing)
    assert missing.returncode == 2
    assert missing.stdout == b""
    assert missing.stderr == diagnostic_missing(fixtures.missing)

    symlink = run_permguard(permguard_bin, fixtures.link_to_safe)
    assert symlink.returncode == 2
    assert symlink.stdout == b""
    assert symlink.stderr == diagnostic_symbolic_link(fixtures.link_to_safe)


# ---------------------------------------------------------------------------
# Clean modes and every closed hazard category (files and directories)
# ---------------------------------------------------------------------------


def test_fixture_clean_private_regular_file(permguard_bin, fixtures):
    before = snapshot_entry(fixtures.clean_file)
    result = run_permguard(permguard_bin, fixtures.clean_file)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    assert_unchanged(fixtures.clean_file, before)


def test_fixture_owner_writable_regular_file_is_clean(permguard_bin, fixtures):
    mode = _mode_bits(fixtures.owner_file)
    assert mode & stat_mod.S_IWUSR
    assert not (mode & stat_mod.S_IWGRP)
    assert not (mode & stat_mod.S_IWOTH)
    result = run_permguard(permguard_bin, fixtures.owner_file)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_fixture_sticky_bit_alone_is_not_a_hazard(permguard_bin, fixtures):
    mode = _mode_bits(fixtures.sticky_dir)
    assert mode & stat_mod.S_ISVTX
    assert not (mode & stat_mod.S_IWGRP)
    assert not (mode & stat_mod.S_IWOTH)
    result = run_permguard(permguard_bin, fixtures.sticky_dir)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


def test_fixture_clean_directory(permguard_bin, fixtures):
    before = snapshot_entry(fixtures.clean_dir)
    result = run_permguard(permguard_bin, fixtures.clean_dir)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    assert_unchanged(fixtures.clean_dir, before)


@pytest.mark.parametrize(
    ("name", "mode", "expected_codes"),
    [
        ("group-only", MODE_GROUP_WRITABLE_FILE, ("GROUP_WRITABLE",)),
        ("other-only", MODE_OTHER_WRITABLE_FILE, ("OTHER_WRITABLE",)),
        ("setuid-only", MODE_SETUID_FILE, ("SET_USER_ID",)),
        ("setgid-only", MODE_SETGID_FILE, ("SET_GROUP_ID",)),
        (
            "group-other",
            MODE_BOTH_WRITABLE_FILE,
            ("GROUP_WRITABLE", "OTHER_WRITABLE"),
        ),
        (
            "both-setid",
            MODE_SETUID_SETGID_FILE,
            ("SET_USER_ID", "SET_GROUP_ID"),
        ),
        (
            "three-bit-no-setgid",
            0o4622,
            ("GROUP_WRITABLE", "OTHER_WRITABLE", "SET_USER_ID"),
        ),
        (
            "three-bit-no-setuid",
            0o2622,
            ("GROUP_WRITABLE", "OTHER_WRITABLE", "SET_GROUP_ID"),
        ),
        (
            "all-four",
            MODE_ALL_FOUR_FILE,
            (
                "GROUP_WRITABLE",
                "OTHER_WRITABLE",
                "SET_USER_ID",
                "SET_GROUP_ID",
            ),
        ),
    ],
)
def test_fixture_regular_file_hazard_combinations(
    permguard_bin, tmp_path, name, mode, expected_codes
):
    path = tmp_path / f"file-{name}"
    if mode & (stat_mod.S_ISUID | stat_mod.S_ISGID):
        write_setid_regular(path, mode)
    else:
        write_regular(path, mode)
    actual_mode = _mode_bits(path)
    assert hazards_for_mode(actual_mode) == list(expected_codes)

    before = snapshot_entry(path)
    result = run_permguard(permguard_bin, path)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [(code, path) for code in expected_codes]
    )
    assert result.stdout == findings_for_path(path, actual_mode)
    assert_unchanged(path, before)


@pytest.mark.parametrize(
    ("name", "mode", "expected_codes"),
    [
        ("group-only", MODE_GROUP_WRITABLE_DIR, ("GROUP_WRITABLE",)),
        ("other-only", MODE_OTHER_WRITABLE_DIR, ("OTHER_WRITABLE",)),
        ("both-writable", MODE_BOTH_WRITABLE_DIR, ("GROUP_WRITABLE", "OTHER_WRITABLE")),
        ("setgid-only", MODE_SETGID_DIR, ("SET_GROUP_ID",)),
    ],
)
def test_fixture_directory_hazard_combinations(
    permguard_bin, tmp_path, name, mode, expected_codes
):
    path = tmp_path / f"dir-{name}"
    make_directory(path, mode)
    actual_mode = _mode_bits(path)
    assert hazards_for_mode(actual_mode) == list(expected_codes)

    before = snapshot_entry(path)
    result = run_permguard(permguard_bin, path)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout(
        [(code, path) for code in expected_codes]
    )
    assert_unchanged(path, before)


def test_fixture_shared_fixtures_match_oracle(permguard_bin, fixtures):
    for path, mode in (
        (fixtures.group_file, MODE_GROUP_WRITABLE_FILE),
        (fixtures.other_file, MODE_OTHER_WRITABLE_FILE),
        (fixtures.both_writable, MODE_BOTH_WRITABLE_FILE),
        (fixtures.group_dir, MODE_GROUP_WRITABLE_DIR),
        (fixtures.other_dir, MODE_OTHER_WRITABLE_DIR),
    ):
        result = run_permguard(permguard_bin, path)
        assert result.returncode == 1
        assert result.stderr == b""
        assert result.stdout == findings_for_path(path, mode)


# ---------------------------------------------------------------------------
# Multi-operand ordering, duplicates, determinism
# ---------------------------------------------------------------------------


def test_integration_leading_dash_operand_requires_terminator(
    permguard_bin, fixtures
):
    write_regular(fixtures.root / "-artifact", MODE_CLEAN_FILE)

    rejected = run_permguard(permguard_bin, "-artifact")
    assert rejected.returncode == 2
    assert rejected.stdout == b""
    assert rejected.stderr == diagnostic_unknown_option("-artifact")

    accepted = run_permguard(
        permguard_bin, "--", "-artifact", cwd=fixtures.root
    )
    assert accepted.returncode == 0
    assert accepted.stdout == b""
    assert accepted.stderr == b""


def test_integration_multiple_paths_preserve_operand_and_taxonomy_order(
    permguard_bin, fixtures
):
    # Deliberately non-lexical operand order: z-* before a-*.
    z_other = write_regular(
        fixtures.root / "z-other", MODE_OTHER_WRITABLE_FILE
    )
    a_group = write_regular(
        fixtures.root / "a-group", MODE_GROUP_WRITABLE_FILE
    )
    combo = write_regular(
        fixtures.root / "m-combo", MODE_BOTH_WRITABLE_FILE
    )
    paths = (
        z_other,
        fixtures.clean_file,
        fixtures.clean_dir,
        a_group,
        combo,
        fixtures.group_dir,
    )
    expected = (
        findings_for_path(z_other, MODE_OTHER_WRITABLE_FILE)
        + findings_for_path(a_group, MODE_GROUP_WRITABLE_FILE)
        + findings_for_path(combo, MODE_BOTH_WRITABLE_FILE)
        + findings_for_path(fixtures.group_dir, MODE_GROUP_WRITABLE_DIR)
    )
    # combo must emit GROUP before OTHER (taxonomy rank), not lexical path order.
    assert b"GROUP_WRITABLE\t" in findings_for_path(
        combo, MODE_BOTH_WRITABLE_FILE
    )
    group_pos = expected.find(b"GROUP_WRITABLE\t" + escape_path(combo))
    other_pos = expected.find(b"OTHER_WRITABLE\t" + escape_path(combo))
    assert 0 <= group_pos < other_pos

    result = run_permguard(permguard_bin, *paths)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == expected
    # Prove ordering is not lexical by path basename.
    lexical = (
        findings_for_path(a_group, MODE_GROUP_WRITABLE_FILE)
        + findings_for_path(combo, MODE_BOTH_WRITABLE_FILE)
        + findings_for_path(fixtures.group_dir, MODE_GROUP_WRITABLE_DIR)
        + findings_for_path(z_other, MODE_OTHER_WRITABLE_FILE)
    )
    assert result.stdout != lexical


def test_integration_duplicate_operands_emit_duplicate_records(
    permguard_bin, fixtures
):
    result = run_permguard(
        permguard_bin, fixtures.other_file, fixtures.other_file
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == (
        findings_for_path(fixtures.other_file, MODE_OTHER_WRITABLE_FILE)
        + findings_for_path(fixtures.other_file, MODE_OTHER_WRITABLE_FILE)
    )


def test_integration_repeat_run_is_byte_identical(permguard_bin, fixtures):
    args = (
        fixtures.other_file,
        fixtures.clean_file,
        fixtures.group_dir,
        fixtures.both_writable,
    )
    first = run_permguard(permguard_bin, *args)
    second = run_permguard(permguard_bin, *args)
    assert first.returncode == 1
    assert second.returncode == first.returncode
    assert second.stdout == first.stdout
    assert second.stderr == first.stderr == b""
    assert first.stdout == (
        findings_for_path(fixtures.other_file, MODE_OTHER_WRITABLE_FILE)
        + findings_for_path(fixtures.group_dir, MODE_GROUP_WRITABLE_DIR)
        + findings_for_path(fixtures.both_writable, MODE_BOTH_WRITABLE_FILE)
    )


def test_integration_modes_and_contents_unchanged_after_scan(
    permguard_bin, fixtures
):
    watched = (
        fixtures.clean_file,
        fixtures.other_file,
        fixtures.group_dir,
        fixtures.both_writable,
        fixtures.safe_target,
        fixtures.hazardous_target,
    )
    before = {path: snapshot_entry(path) for path in watched}
    result = run_permguard(permguard_bin, *watched)
    assert result.returncode == 1
    for path in watched:
        assert_unchanged(path, before[path])


# ---------------------------------------------------------------------------
# Missing, inaccessible, and other invalid operands
# ---------------------------------------------------------------------------


def test_integration_missing_path_diagnostic(permguard_bin, fixtures):
    result = run_permguard(permguard_bin, fixtures.missing)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_missing(fixtures.missing)
    assert_no_raw_unsafe_bytes(result.stderr)
    assert b"No such file" not in result.stderr


def test_integration_inaccessible_path_diagnostic(permguard_bin, tmp_path):
    if os.geteuid() == 0:
        pytest.skip(
            "EACCES fixture is unreliable when running as root; "
            "host cannot produce a trustworthy inaccessible operand"
        )

    blocked = tmp_path / "blocked"
    blocked.mkdir()
    secret = blocked / "secret"
    write_regular(secret, MODE_CLEAN_FILE)
    os.chmod(blocked, 0)
    try:
        try:
            os.lstat(secret)
        except OSError as exc:
            if exc.errno != errno.EACCES:
                pytest.skip(
                    f"host did not produce EACCES for inaccessible operand "
                    f"(got errno {exc.errno})"
                )
        else:
            pytest.skip(
                "host bypassed directory search restriction; "
                "cannot produce EACCES inaccessible operand"
            )

        result = run_permguard(permguard_bin, secret)
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr == diagnostic_inaccessible(secret)
        assert_no_raw_unsafe_bytes(result.stderr)
    finally:
        os.chmod(blocked, 0o700)


def test_integration_enotdir_intermediate_component(permguard_bin, fixtures):
    nested = fixtures.clean_file / "nested"
    try:
        os.lstat(nested)
    except OSError as exc:
        expected_errno = exc.errno
    else:
        pytest.fail("ENOTDIR path unexpectedly became lstat-able")

    result = run_permguard(permguard_bin, nested)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_inspection_error(expected_errno, nested)


def test_integration_empty_string_operand_is_inspection_error(permguard_bin):
    try:
        os.lstat("")
        raise AssertionError("empty path unexpectedly exists")
    except OSError as exc:
        expected_errno = exc.errno

    result = run_permguard(permguard_bin, "")
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_inspection_error(expected_errno, b"")


# ---------------------------------------------------------------------------
# Symlinks must never be followed (safe, hazardous, dangling)
# ---------------------------------------------------------------------------


def test_symlink_to_safe_target_is_rejected(permguard_bin, fixtures):
    before_link = snapshot_entry(fixtures.link_to_safe)
    before_target = snapshot_entry(fixtures.safe_target)
    result = run_permguard(permguard_bin, fixtures.link_to_safe)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_symbolic_link(fixtures.link_to_safe)
    assert b"GROUP_WRITABLE" not in result.stdout
    assert b"OTHER_WRITABLE" not in result.stdout
    assert_unchanged(fixtures.link_to_safe, before_link)
    assert_unchanged(fixtures.safe_target, before_target)


def test_symlink_to_hazardous_target_is_rejected_without_target_findings(
    permguard_bin, fixtures
):
    before_target = snapshot_entry(fixtures.hazardous_target)
    result = run_permguard(permguard_bin, fixtures.link_to_hazardous)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_symbolic_link(fixtures.link_to_hazardous)
    # Target hazards must not leak; link and safe-target link share the same form.
    assert result.stderr == diagnostic_symbolic_link(fixtures.link_to_hazardous)
    for code in HAZARD_RANK:
        assert code.encode("ascii") not in result.stdout
        assert code.encode("ascii") not in result.stderr
    assert_unchanged(fixtures.hazardous_target, before_target)


def test_dangling_symlink_is_rejected_as_symbolic_link(permguard_bin, fixtures):
    result = run_permguard(permguard_bin, fixtures.dangling)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_symbolic_link(fixtures.dangling)
    assert b"MISSING" not in result.stderr


def test_safe_and_hazardous_symlinks_are_indistinguishable_at_boundary(
    permguard_bin, fixtures
):
    safe = run_permguard(permguard_bin, fixtures.link_to_safe)
    hazardous = run_permguard(permguard_bin, fixtures.link_to_hazardous)
    assert safe.returncode == hazardous.returncode == 2
    assert safe.stdout == hazardous.stdout == b""
    # Same diagnostic shape; only the quoted operand bytes differ.
    assert safe.stderr.startswith(b"permguard: SYMBOLIC_LINK: ")
    assert hazardous.stderr.startswith(b"permguard: SYMBOLIC_LINK: ")
    assert safe.stderr == diagnostic_symbolic_link(fixtures.link_to_safe)
    assert hazardous.stderr == diagnostic_symbolic_link(
        fixtures.link_to_hazardous
    )


def test_symlink_and_target_together_reports_target_and_rejects_link(
    permguard_bin, fixtures
):
    result = run_permguard(
        permguard_bin, fixtures.link_to_hazardous, fixtures.hazardous_target
    )
    assert result.returncode == 2
    assert result.stdout == findings_for_path(
        fixtures.hazardous_target, MODE_OTHER_WRITABLE_FILE
    )
    assert result.stderr == diagnostic_symbolic_link(fixtures.link_to_hazardous)


# ---------------------------------------------------------------------------
# Mixed-success: continue after errors; operational status overrides hazards
# ---------------------------------------------------------------------------


def test_integration_mixed_success_continues_and_returns_two(
    permguard_bin, fixtures
):
    # hazardous, missing, clean, symlink, hazardous — non-lexical names.
    z_hazard = write_regular(
        fixtures.root / "z-mixed-hazard", MODE_OTHER_WRITABLE_FILE
    )
    a_hazard = write_regular(
        fixtures.root / "a-mixed-hazard", MODE_GROUP_WRITABLE_FILE
    )
    operands = (
        z_hazard,
        fixtures.missing,
        fixtures.clean_file,
        fixtures.link_to_safe,
        a_hazard,
    )
    result = run_permguard(permguard_bin, *operands)
    assert result.returncode == 2
    assert result.stdout == (
        findings_for_path(z_hazard, MODE_OTHER_WRITABLE_FILE)
        + findings_for_path(a_hazard, MODE_GROUP_WRITABLE_FILE)
    )
    assert result.stderr == (
        diagnostic_missing(fixtures.missing)
        + diagnostic_symbolic_link(fixtures.link_to_safe)
    )
    assert_no_raw_unsafe_bytes(result.stdout)
    assert_no_raw_unsafe_bytes(result.stderr)


def test_integration_hazard_with_error_never_returns_status_one(
    permguard_bin, fixtures
):
    result = run_permguard(
        permguard_bin, fixtures.other_file, fixtures.missing
    )
    assert result.returncode == 2
    assert result.stdout == findings_for_path(
        fixtures.other_file, MODE_OTHER_WRITABLE_FILE
    )
    assert result.stderr == diagnostic_missing(fixtures.missing)


# ---------------------------------------------------------------------------
# Hostile / unusual path escaping
# ---------------------------------------------------------------------------


def test_hostile_path_escaping_in_findings(permguard_bin, fixtures):
    result = run_permguard(permguard_bin, fixtures.control_path)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_for_path(
        fixtures.control_path, MODE_OTHER_WRITABLE_FILE
    )
    assert b"\x1b" not in result.stdout
    assert_no_raw_unsafe_bytes(result.stdout)


def test_hostile_path_escaping_in_diagnostics(permguard_bin, tmp_path):
    missing_name = os.fsdecode(b"miss\x1bing")
    missing = tmp_path / missing_name
    result = run_permguard(permguard_bin, missing)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_missing(missing)
    assert b"miss\\x1Bing" in result.stderr
    assert b"\x1b" not in result.stderr
    assert_no_raw_unsafe_bytes(result.stderr)


def test_unusual_quote_and_backslash_filenames(permguard_bin, fixtures):
    os.chmod(fixtures.unusual, MODE_OTHER_WRITABLE_FILE)
    require_mode(fixtures.unusual, MODE_OTHER_WRITABLE_FILE, label="unusual")
    result = run_permguard(permguard_bin, fixtures.unusual)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_for_path(
        fixtures.unusual, MODE_OTHER_WRITABLE_FILE
    )
    assert b'\\"' in result.stdout
    assert b"\\\\" in result.stdout


def test_non_utf8_path_escaping_in_diagnostics(permguard_bin, tmp_path):
    missing_name = os.fsdecode(b"miss\xffing")
    missing = tmp_path / missing_name
    result = run_permguard(permguard_bin, missing)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_missing(missing)
    assert b"miss\\xFFing" in result.stderr
    assert b"\xff" not in result.stderr


def test_tab_newline_and_del_in_path_are_escaped(permguard_bin, tmp_path):
    cases = (
        (b"has\ttab", b"has\\x09tab"),
        (b"has\nnewline", b"has\\x0Anewline"),
        (b"has\x7fdel", b"has\\x7Fdel"),
    )
    for raw_name, escaped in cases:
        name = os.fsdecode(raw_name)
        path = tmp_path / name
        try:
            write_regular(path, MODE_OTHER_WRITABLE_FILE)
        except OSError as exc:
            pytest.skip(
                f"host filesystem cannot create path with {raw_name!r}: {exc}"
            )
        result = run_permguard(permguard_bin, path)
        assert result.returncode == 1
        assert result.stderr == b""
        assert escaped in result.stdout
        assert raw_name not in result.stdout
        assert_no_raw_unsafe_bytes(result.stdout)


# ---------------------------------------------------------------------------
# Source surface and contract document pins (AC-09)
# ---------------------------------------------------------------------------


def test_regression_source_uses_lstat_not_follow_apis():
    if not SRC.is_file():
        pytest.fail(
            f"{SRC} is missing; permguard bootstrap suite requires the source"
        )
    text = SRC.read_text(encoding="utf-8")
    for macro in ("S_IWGRP", "S_IWOTH", "S_ISUID", "S_ISGID", "S_ISLNK"):
        assert macro in text, f"src/permguard.c must use {macro}"
    for code in HAZARD_RANK:
        assert code in text, f"src/permguard.c must emit {code}"

    call_sites = re.findall(r"(?<!\w)lstat\s*\(\s*(?!\d)", text)
    assert len(call_sites) >= 1, "expected at least one lstat call site"

    forbidden = (
        (r"(?<!l)\bstat\s*\(", "bare stat("),
        (r"\brealpath\s*\(", "realpath("),
        (r"\breadlink\s*\(", "readlink("),
        (r"\baccess\s*\(", "access("),
        (r"\bopendir\s*\(", "opendir("),
        (r"\bfopen\s*\(", "fopen("),
        (r"(?<!f)\bopen\s*\(", "open("),
        (r"\bchmod\s*\(", "chmod("),
        (r"\bchown\s*\(", "chown("),
        (r"\bunlink\s*\(", "unlink("),
        (r"\brename\s*\(", "rename("),
    )
    for pattern, label in forbidden:
        assert re.search(pattern, text) is None, (
            f"src/permguard.c must not call {label}"
        )


def test_regression_taxonomy_is_closed_four_codes(permguard_bin, fixtures):
    setuid_path = write_setid_regular(
        fixtures.root / "tax-setuid", MODE_SETUID_FILE
    )
    setgid_path = write_setid_regular(
        fixtures.root / "tax-setgid", MODE_SETGID_FILE
    )
    combo = write_setid_regular(
        fixtures.root / "tax-all-four", MODE_ALL_FOUR_FILE
    )
    result = run_permguard(
        permguard_bin,
        fixtures.other_file,
        fixtures.group_dir,
        setuid_path,
        setgid_path,
        combo,
        fixtures.clean_file,
    )
    assert result.returncode == 1
    assert result.stderr == b""
    codes = {
        line.split(b"\t", 1)[0].decode("ascii")
        for line in result.stdout.splitlines()
    }
    assert codes <= set(HAZARD_RANK)
    assert "WORLD_WRITABLE_FILE" not in codes
    assert "WORLD_WRITABLE_DIRECTORY" not in result.stdout.decode("ascii")
    assert result.stdout == (
        findings_for_path(fixtures.other_file, MODE_OTHER_WRITABLE_FILE)
        + findings_for_path(fixtures.group_dir, MODE_GROUP_WRITABLE_DIR)
        + findings_for_path(setuid_path, MODE_SETUID_FILE)
        + findings_for_path(setgid_path, MODE_SETGID_FILE)
        + findings_for_path(combo, MODE_ALL_FOUR_FILE)
    )


def test_regression_contract_has_substantive_bootstrap_headings():
    if not CONTRACT.is_file():
        pytest.skip(
            "docs/permguard-bootstrap-contract.md is absent "
            "(workspace-only contract integrity check)"
        )
    text = CONTRACT.read_text(encoding="utf-8")
    for heading in CONTRACT_HEADINGS:
        pattern = rf"^## {re.escape(heading)}\s*$"
        match = re.search(pattern, text, flags=re.MULTILINE)
        assert match is not None, f"missing contract heading: {heading}"
        start = match.end()
        next_heading = re.search(r"^## ", text[start:], flags=re.MULTILINE)
        body = (
            text[start : start + next_heading.start()]
            if next_heading
            else text[start:]
        )
        assert body.strip(), f"empty contract section: {heading}"
    for code in HAZARD_RANK:
        assert code in text
    # Former one-code token may appear only in the Authority supersession
    # prose that names superseded drafts; it must not appear as a live code.
    authority = re.search(
        r"^## Authority\s*$(.*?)^## ",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert authority is not None
    authority_body = authority.group(1)
    assert "sole live product contract" in authority_body
    assert "permguard-first-vertical-slice-contract.md" in authority_body
    assert "superseded" in authority_body.lower()
    remainder = text[authority.end() :]
    assert "WORLD_WRITABLE_FILE" not in remainder
    for heading in ("Hazard Taxonomy", "CLI Surface", "Exit Statuses"):
        section = re.search(
            rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert section is not None
        assert "WORLD_WRITABLE_FILE" not in section.group(1)


def test_regression_inherited_permguard_bin_decoy_fails_unless_scrubbed(tmp_path):
    """Stale PERMGUARD_BIN decoy must not silently pass the contract suite."""

    decoy = tmp_path / "decoy-permguard"
    decoy.write_text(
        "#!/bin/sh\nprintf 'wrong\\n'\nexit 0\n",
        encoding="utf-8",
    )
    decoy.chmod(0o755)

    basetemp = tempfile.mkdtemp(prefix="permguard-pytest-decoy.", dir="/tmp")
    env = os.environ.copy()
    env["PERMGUARD_BIN"] = str(decoy)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PERMGUARD_UNDER_VALGRIND", None)
    env.pop("SYSDIFF_UNDER_VALGRIND", None)
    env.pop("PATHAUDIT_UNDER_VALGRIND", None)

    try:
        poisoned = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                f"--basetemp={basetemp}",
                "tests/test_permguard.py::test_unit_no_operands_is_usage_error",
                "-q",
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        shutil.rmtree(basetemp, ignore_errors=True)

    assert poisoned.returncode != 0, poisoned.stdout + poisoned.stderr
    assert "FAILED" in poisoned.stdout or "failed" in poisoned.stdout.lower()


# ---------------------------------------------------------------------------
# Medium repairs regressions (PG-DOC-501/502, PG-TEST-503, PG-PORT-505,
# PG-DOC-512). Encode docs/permguard-medium-repairs-contract.md intended
# behavior, not the pre-repair implementation. Old-behavior blast radius:
# src/permguard.c, Makefile, tests/test_permguard.py, tests/smoke_manifest.json,
# scripts/smoke.sh, README.md, man/permguard.1, CHANGELOG.md, architecture.md,
# QUALITY.md, TESTING.md, and the bootstrap / one-code docs and plans.
# ---------------------------------------------------------------------------


def _require_text_file(path: Path, *, label: str) -> str:
    if not path.is_file():
        pytest.fail(f"{label} is missing; Medium-repairs suite requires {path}")
    return path.read_text(encoding="utf-8")


# Development-checkout surfaces that `make dist` deliberately omits from the
# source archive (root architecture/QUALITY/TESTING, plans/, and any still-
# untracked Medium-repairs contract). Dist extracts still run product and
# Makefile/POSIX regressions; these authority pins skip rather than fail.
_DIST_OMITTED_MEDIUM_DOC_SURFACES = (
    ARCHITECTURE,
    QUALITY,
    TESTING,
    MEDIUM_REPAIRS_CONTRACT,
    ONE_CODE_PLAN,
    ROOT / "plans" / "permguard-bootstrap-implementation-plan.md",
)


def _skip_unless_dev_tree_medium_docs(*paths: Path) -> None:
    """Skip Medium doc pins when a source-distribution extract omits them."""

    missing = [path for path in paths if not path.is_file()]
    if not missing:
        return
    rels = ", ".join(
        str(path.relative_to(ROOT)) if path.is_absolute() else str(path)
        for path in missing
    )
    pytest.skip(
        "development-tree Medium-repair documentation surfaces absent "
        f"({rels}); source-distribution extracts omit root architecture/"
        "QUALITY/TESTING and plans/ under DIST_PATHSPECS, and untracked "
        "contracts are not packaged by git ls-files"
    )


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
        break
    return "".join(collected)


def _permguard_compile_lines(makefile: str) -> list[str]:
    """Return recipe/command lines that compile or analyze PERMGUARD_SRC.

    Backslash-continued Make recipe lines are joined so a flag on the first
    physical line still covers $(PERMGUARD_SRC) on a continuation line.
    """

    physical = makefile.splitlines()
    joined: list[str] = []
    pending = ""
    for line in physical:
        if pending:
            pending += " " + line.lstrip("\t")
            if line.rstrip().endswith("\\"):
                pending = pending.rstrip()[:-1].rstrip()
                continue
            joined.append(pending)
            pending = ""
            continue
        if line.rstrip().endswith("\\"):
            pending = line.rstrip()[:-1].rstrip()
            continue
        joined.append(line)
    if pending:
        joined.append(pending)

    lines: list[str] = []
    for line in joined:
        if "PERMGUARD_SRC" in line or "src/permguard.c" in line:
            # Variable-assignment lines that only name the source are not
            # compile routes; require a compiler / analyzer invocation shape.
            if re.search(
                r"(gcc|clang|\$\(CC\)|clang-tidy|cppcheck|scan-build|"
                r"-fsyntax-only|-o\s)",
                line,
            ):
                lines.append(line)
    return lines


def test_medium_ac01_closed_finding_scope_and_authority():
    """PG-DOC-502 / AC-01: Medium scope and live bootstrap authority."""

    _skip_unless_dev_tree_medium_docs(MEDIUM_REPAIRS_CONTRACT)
    medium = _require_text_file(
        MEDIUM_REPAIRS_CONTRACT, label="medium-repairs contract"
    )
    for finding_id in MEDIUM_REPAIR_FINDING_IDS:
        assert finding_id in medium, (
            f"medium-repairs contract must name closed finding {finding_id}"
        )
    # Low findings are explicitly out of scope for this slice.
    for low_id in (
        "PG-CRAFT-506",
        "PG-TEST-507",
        "PG-CLI-508",
        "PG-MAKE-509",
        "PG-MAKE-510",
        "PG-MAKE-511",
    ):
        assert low_id in medium, (
            f"medium-repairs contract must list Non-Goals finding {low_id}"
        )

    bootstrap = _require_text_file(CONTRACT, label="bootstrap contract")
    authority = re.search(
        r"^## Authority\s*$(.*?)^## ",
        bootstrap,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert authority is not None
    authority_body = authority.group(1)
    assert "sole live product contract" in authority_body
    assert "permguard-bootstrap-contract.md" in medium
    assert "sole live product" in medium.lower() or "sole live product authority" in medium.lower()


def test_medium_ac01_one_code_contract_superseded_in_shipped_docs():
    """PG-DOC-502: packaged one-code contract keeps a conspicuous superseded pin.

    Runs in both development checkouts and source-distribution extracts:
    docs/permguard-first-vertical-slice-contract.md is shipped; plans/ is not.
    """

    one_code = _require_text_file(
        ONE_CODE_CONTRACT, label="first-vertical-slice contract"
    )
    one_code_head = one_code[:800].lower()
    assert "superseded" in one_code_head, (
        "docs/permguard-first-vertical-slice-contract.md must open with a "
        "conspicuous superseded marker (PG-DOC-502)"
    )
    assert "permguard-bootstrap-contract.md" in one_code_head or (
        "bootstrap" in one_code_head and "authority" in one_code_head
    ), "superseded one-code contract must point readers to the bootstrap contract"


def test_medium_ac01_one_code_plan_superseded_in_dev_tree():
    """PG-DOC-502: development-tree one-code plan markers and false-removal ban."""

    _skip_unless_dev_tree_medium_docs(ONE_CODE_PLAN)
    one_plan = _require_text_file(
        ONE_CODE_PLAN, label="first-vertical-slice plan"
    )
    one_plan_head = one_plan[:800].lower()
    assert "superseded" in one_plan_head, (
        "plans/permguard-first-vertical-slice-plan.md must open with a "
        "conspicuous superseded marker (PG-DOC-502)"
    )
    assert "permguard-bootstrap-contract.md" in one_plan_head or (
        "bootstrap" in one_plan_head and "authority" in one_plan_head
    ), "superseded one-code plan must point readers to the bootstrap contract"

    # Old false claim: bootstrap docs "are removed from docs/ and plans/".
    assert not re.search(
        r"are removed from\s+`?docs/`?\s+and\s+`?plans/`?",
        one_plan,
        flags=re.IGNORECASE,
    ), (
        "first-vertical-slice plan must not falsely claim bootstrap documents "
        "were removed (PG-DOC-502 old-behavior blast radius)"
    )


def test_medium_ac02_architecture_describes_shipped_bootstrap_model():
    """PG-DOC-501 / AC-02: architecture matches four-code streaming bootstrap."""

    _skip_unless_dev_tree_medium_docs(ARCHITECTURE)
    text = _require_text_file(ARCHITECTURE, label="architecture.md")
    # Scope the permguard decision record; do not police pathaudit taxonomy.
    # Keep the heading match line-local ([^\n]*): with DOTALL, greedy .* before
    # $ would consume the rest of the document and leave group 1 empty.
    section = re.search(
        r"^## [^\n]*permguard[^\n]*$(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    assert section is not None, "architecture.md must contain a permguard section"
    body = section.group(1)

    for code in HAZARD_RANK:
        assert code in body, (
            f"architecture.md permguard section must name shipped code {code}"
        )

    # Reject superseded one-code / draft predicates (old PG-DOC-501 blast).
    assert "WORLD_WRITABLE_FILE" not in body
    assert not re.search(
        r"world-writable directories without\s+the sticky bit",
        body,
        flags=re.IGNORECASE,
    ), "architecture must not describe sticky-bit-conditioned directory hazards"
    assert not re.search(
        r"Findings are retained until all operands have been inspected",
        body,
    ), "architecture must not claim buffer-until-complete emission"
    assert not re.search(
        r"resource limit,\s*allocation",
        body,
        flags=re.IGNORECASE,
    ), "architecture must not invent allocation/resource-limit exit classes"

    # Intended streaming / continue-after-error model.
    assert re.search(r"stream|emit", body, flags=re.IGNORECASE)
    assert re.search(
        r"continu|does not stop|after (an )?error|operand error",
        body,
        flags=re.IGNORECASE,
    ) or (
        "continue" in body.lower() and "error" in body.lower()
    ), "architecture must describe continue-after-error / streaming inspection"


def test_medium_ac02_quality_and_testing_name_permguard_gates():
    """PG-DOC-512 / AC-02: QUALITY.md and TESTING.md name real permguard routes."""

    _skip_unless_dev_tree_medium_docs(QUALITY, TESTING)
    quality = _require_text_file(QUALITY, label="QUALITY.md")
    testing = _require_text_file(TESTING, label="TESTING.md")

    for document, text in (("QUALITY.md", quality), ("TESTING.md", testing)):
        assert re.search(r"\bpermguard\b", text, flags=re.IGNORECASE), (
            f"{document} must mention permguard (PG-DOC-512)"
        )
        assert "tests/test_permguard.py" in text, (
            f"{document} must name tests/test_permguard.py"
        )

    # PGR-DOC-701: the enumerated `make quality` floor itself must name
    # permguard membership; an appended section alone must not satisfy this.
    floor_match = re.search(
        r"in this order:\s*(.*?)(?=^## |\Z)",
        quality,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert floor_match is not None, (
        "QUALITY.md must introduce the make quality floor with 'in this order:'"
    )
    floor = floor_match.group(1)
    for token in (
        "src/permguard.c",
        "man/permguard.1",
        "PERMGUARD_UNDER_VALGRIND",
    ):
        assert token in floor, (
            "QUALITY.md enumerated make quality floor must name "
            f"{token} (PGR-DOC-701 / PG-DOC-512); an appended section alone "
            "is insufficient"
        )

    # Gate membership and override contract.
    for token in (
        "PERMGUARD_BIN",
        "PERMGUARD_UNDER_VALGRIND",
        "permguard-sanitize",
        "permguard-valgrind",
    ):
        assert token in quality or token in testing, (
            f"QUALITY.md or TESTING.md must document {token}"
        )

    combined = quality + "\n" + testing
    assert re.search(r"lstat", combined, flags=re.IGNORECASE), (
        "maintainer docs must describe the chmod-then-lstat fixture oracle"
    )
    assert re.search(
        r"skip|capability",
        combined,
        flags=re.IGNORECASE,
    ), "maintainer docs must describe honest host-capability skips"
    assert re.search(
        r"sanitiz|valgrind|AddressSanitizer|UndefinedBehaviorSanitizer",
        combined,
        flags=re.IGNORECASE,
    ), "maintainer docs must name sanitizer/Valgrind routes for permguard"


def test_medium_ac03_source_has_no_hand_declared_lstat():
    """PG-PORT-505 / AC-03: <sys/stat.h> owns lstat; no hand-written prototype."""

    text = _require_text_file(SRC, label="src/permguard.c")
    # Call sites remain required; prototypes are forbidden.
    assert re.search(r"(?<!\w)lstat\s*\(", text), (
        "src/permguard.c must call lstat"
    )
    for line in text.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped.startswith("//")
        ):
            continue
        if re.match(r"int\s+lstat\s*\(.*\)\s*;\s*$", stripped):
            raise AssertionError(
                "src/permguard.c must not hand-declare int lstat(...); "
                "pass -D_POSIX_C_SOURCE=200809L so the platform header "
                "provides it (PG-PORT-505 old-behavior blast radius: "
                "src/permguard.c)"
            )
    # Catch multi-line or oddly spaced prototypes as well.
    assert re.search(r"(?<!\w)int\s+lstat\s*\(", text) is None, (
        "src/permguard.c must not hand-declare lstat "
        "(PG-PORT-505 old-behavior blast radius: src/permguard.c)"
    )


def test_medium_ac03_pytest_compile_supplies_posix_c_source(permguard_bin):
    """PG-PORT-505 / AC-03: pytest-owned compile passes the POSIX feature flag."""

    assert POSIX_C_SOURCE_FLAG == "-D_POSIX_C_SOURCE=200809L"
    if os.environ.get("PERMGUARD_BIN"):
        # Override path does not compile; the argv oracle is N/A.
        assert not _LAST_PERMGUARD_COMPILE_ARGV
        return
    assert _LAST_PERMGUARD_COMPILE_ARGV, (
        "permguard_bin fixture must record the compile argv it used"
    )
    assert POSIX_C_SOURCE_FLAG in _LAST_PERMGUARD_COMPILE_ARGV, (
        "permguard_bin fixture compile argv must include "
        f"{POSIX_C_SOURCE_FLAG} (PG-PORT-505 / PGR-TEST-703)"
    )
    assert any(
        arg == str(SRC) or Path(arg).resolve() == SRC.resolve()
        for arg in _LAST_PERMGUARD_COMPILE_ARGV
    ), "recorded compile argv must mention src/permguard.c"
    assert str(permguard_bin) in _LAST_PERMGUARD_COMPILE_ARGV


def _makefile_permguard_posix_flag_ref(text: str) -> re.Match[str] | None:
    """Match a load-bearing POSIX flag: literal or $(PERMGUARD_*CFLAGS|FLAGS).

    $(PERMGUARD_SRC) alone must not satisfy this — that was PG-REV-601.
    """

    return re.search(
        rf"{re.escape(POSIX_C_SOURCE_FLAG)}|"
        r"\$\((PERMGUARD_[A-Z0-9_]*(?:CFLAGS|FLAGS))\)",
        text,
    )


def _makefile_var_definition(makefile: str, name: str) -> str | None:
    """Return the RHS of a simple or recursively expanded Make variable."""

    match = re.search(
        rf"^{re.escape(name)}\s*:?=\s*(.*)$",
        makefile,
        flags=re.MULTILINE,
    )
    return None if match is None else match.group(1)


def _shell_commands_mentioning_permguard(recipe: str) -> list[str]:
    """Split a Make recipe into shell commands that compile/analyze permguard.

    Joined backslash-continuations are split on `;` so a POSIX flag on a
    neighboring sysdiff/pathaudit command cannot satisfy the oracle
    (PGR-TEST-702).
    """

    commands: list[str] = []
    for chunk in recipe.split(";"):
        command = chunk.strip()
        if not command:
            continue
        if "$(PERMGUARD_SRC)" in command or "src/permguard.c" in command:
            commands.append(command)
    return commands


def _join_make_recipe_lines(block: str) -> str:
    """Join tabbed recipe lines, folding backslash continuations."""

    joined_parts: list[str] = []
    pending = ""
    for line in block.splitlines():
        if not line.startswith("\t"):
            continue
        body = line[1:]
        if pending:
            pending += " " + body.lstrip()
            if body.rstrip().endswith("\\"):
                pending = pending.rstrip()[:-1].rstrip()
                continue
            joined_parts.append(pending)
            pending = ""
            continue
        if body.rstrip().endswith("\\"):
            pending = body.rstrip()[:-1].rstrip()
            continue
        joined_parts.append(body)
    if pending:
        joined_parts.append(pending)
    return " ; ".join(joined_parts)


def test_medium_ac03_makefile_permguard_routes_supply_posix_c_source():
    """PG-PORT-505 / AC-03: every Make permguard compile route sets the flag."""

    makefile = _require_text_file(MAKEFILE, label="Makefile")
    assert POSIX_C_SOURCE_FLAG in makefile, (
        "Makefile must define or pass -D_POSIX_C_SOURCE=200809L for permguard"
    )

    # Prefer a dedicated Make *CFLAGS/*FLAGS variable over relying solely on
    # overridable CFLAGS. $(PERMGUARD_SRC) alone must not satisfy the oracle.
    var_match = re.search(
        r"^(PERMGUARD_[A-Z0-9_]*(?:CFLAGS|FLAGS))\s*:?=\s*(.*)$",
        makefile,
        flags=re.MULTILINE,
    )
    assert var_match is not None, (
        "Makefile must attach _POSIX_C_SOURCE=200809L via a permguard-specific "
        "Make *CFLAGS/*FLAGS variable that callers cannot accidentally drop by "
        "replacing CFLAGS"
    )
    posix_var = var_match.group(1)
    assert POSIX_C_SOURCE_FLAG in var_match.group(2), (
        f"$({posix_var}) definition must contain {POSIX_C_SOURCE_FLAG}"
    )

    compile_lines = _permguard_compile_lines(makefile)
    assert compile_lines, "expected at least one Makefile permguard compile route"
    for line in compile_lines:
        for command in _shell_commands_mentioning_permguard(line):
            match = _makefile_permguard_posix_flag_ref(command)
            assert match is not None, (
                "permguard compile/analyze command must pass the POSIX "
                f"feature-test flag or $(PERMGUARD_*CFLAGS|FLAGS): {command!r}"
            )
            if match.group(0).startswith("$("):
                ref_name = match.group(1)
                defn = _makefile_var_definition(makefile, ref_name)
                assert defn is not None and POSIX_C_SOURCE_FLAG in defn, (
                    f"$({ref_name}) must be defined with {POSIX_C_SOURCE_FLAG}"
                )

    for target in (
        "permguard",
        "gcc-strict",
        "clang-strict",
        "clang-syntax",
        "clang-tidy-check",
        "clang-analyzer-check",
        "test-asan",
        "test-ubsan",
        "test-valgrind",
        "permguard-sanitize",
        "permguard-valgrind",
    ):
        block = _makefile_target_block(makefile, target)
        if "$(PERMGUARD_SRC)" not in block and "src/permguard.c" not in block:
            raise AssertionError(
                f"Make target {target!r} must compile $(PERMGUARD_SRC)"
            )
        commands = _shell_commands_mentioning_permguard(
            _join_make_recipe_lines(block)
        )
        assert commands, (
            f"Make target {target!r} must contain a permguard compile command"
        )
        for command in commands:
            match = _makefile_permguard_posix_flag_ref(command)
            assert match is not None, (
                f"Make target {target!r} permguard command must supply "
                f"_POSIX_C_SOURCE=200809L (PG-PORT-505): {command!r}"
            )
            if match.group(0).startswith("$("):
                ref_name = match.group(1)
                defn = _makefile_var_definition(makefile, ref_name)
                assert defn is not None and POSIX_C_SOURCE_FLAG in defn, (
                    f"Make target {target!r} references $({ref_name}) which "
                    f"must define {POSIX_C_SOURCE_FLAG}"
                )


def test_stdout_write_failure_on_dev_full(permguard_bin, tmp_path):
    """PG-TEST-503 / AC-04: /dev/full hazard scan -> status 2 + STDOUT_WRITE.

    Old-behavior blast radius: src/permguard.c checked-stdio path, man page,
    CHANGELOG, and bootstrap contract already promised STDOUT_WRITE but no
    focused regression pinned the device-full failure.
    """

    path = write_regular(tmp_path / "full-hazard", MODE_OTHER_WRITABLE_FILE)
    before = snapshot_entry(path)
    status, stderr = run_with_stdout_to_dev_full(permguard_bin, path)
    assert status == 2
    assert stderr == diagnostic_stdout_write()
    assert_no_raw_unsafe_bytes(stderr)
    assert_unchanged(path, before)


def test_closed_stdout_pipe_is_status_two_not_sigpipe(permguard_bin, tmp_path):
    """PG-TEST-503 / AC-05: closed stdout pipe -> 2, not SIGPIPE / 141.

    Old-behavior blast radius: ignored-SIGPIPE plus final fflush checking in
    src/permguard.c; removing either regresses to negative signal status or
    shell 141 instead of the contracted STDOUT_WRITE operational failure.
    """

    path = write_regular(tmp_path / "pipe-hazard", MODE_OTHER_WRITABLE_FILE)
    before = snapshot_entry(path)
    status, stderr = run_with_closed_stdout_pipe(permguard_bin, path)

    assert status == 2
    assert status != -signal.SIGPIPE
    assert status != 141
    assert status > 0
    assert stderr == diagnostic_stdout_write()
    assert_no_raw_unsafe_bytes(stderr)
    assert_unchanged(path, before)

    # Informational stdout must take the same checked path.
    help_status, help_stderr = run_with_closed_stdout_pipe(
        permguard_bin, "--help"
    )
    assert help_status == 2
    assert help_status != -signal.SIGPIPE
    assert help_status != 141
    assert help_stderr == diagnostic_stdout_write()


def test_medium_ac07_blast_radius_surfaces_and_smoke_route_exist():
    """AC-07: named blast-radius surfaces exist; smoke still reaches make test.

    Intentional no-change for tests/smoke_manifest.json and scripts/smoke.sh
    is allowed when the transitive make test route remains intact.
    """

    # Always assert the archive-shipped blast-radius core + smoke route.
    shipped_core = (
        "src/permguard.c",
        "Makefile",
        "tests/test_permguard.py",
        "tests/smoke_manifest.json",
        "scripts/smoke.sh",
        "README.md",
        "man/permguard.1",
        "CHANGELOG.md",
        "docs/permguard-bootstrap-contract.md",
        "docs/permguard.md",
        "docs/permguard-first-vertical-slice-contract.md",
    )
    for relative in shipped_core:
        path = ROOT / relative
        assert path.exists(), f"blast-radius surface missing: {relative}"

    manifest = _require_text_file(SMOKE_MANIFEST, label="smoke manifest")
    script = _require_text_file(SMOKE_SCRIPT, label="smoke script")
    assert "make test" in script, (
        "scripts/smoke.sh must still transitively reach make test"
    )
    # Manifest remains the governed oracle; do not require permguard-specific
    # smoke scenarios — only that the file stays present and parseable JSON.
    stripped = manifest.lstrip()
    assert stripped.startswith("{") or stripped.startswith("["), (
        "tests/smoke_manifest.json must remain a JSON document"
    )

    # Development-tree-only surfaces (root maintainer docs + plans/) are
    # omitted from DIST_PATHSPECS; require them only in a full checkout.
    _skip_unless_dev_tree_medium_docs(*_DIST_OMITTED_MEDIUM_DOC_SURFACES)
    for relative in MEDIUM_REPAIR_BLAST_RADIUS:
        path = ROOT / relative
        assert path.exists(), f"blast-radius surface missing: {relative}"


# ---------------------------------------------------------------------------
# Hostile filesystem fixtures
# (docs/permguard-hostile-filesystem-fixtures-contract.md AC-01..AC-11)
#
# PGH_* labels organize tests only; they must never appear in product output.
# Mandatory cases are rootless and deterministic. Capability-gated additions
# skip with an explicit reason rather than pretending to pass.
# ---------------------------------------------------------------------------


_WRAP_LSTAT_C = r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

extern int __real_lstat(const char *path, struct stat *buf);

static void write_proof(const char *proof_path) {
  FILE *fp;
  if (proof_path == NULL || proof_path[0] == '\0') {
    return;
  }
  fp = fopen(proof_path, "w");
  if (fp == NULL) {
    return;
  }
  (void)fputs("1\n", fp);
  (void)fclose(fp);
}

static int atomic_replace(const char *target, const char *aside,
                          const char *fresh) {
  if (target == NULL || aside == NULL || fresh == NULL) {
    errno = EINVAL;
    return -1;
  }
  if (rename(target, aside) != 0) {
    return -1;
  }
  if (rename(fresh, target) != 0) {
    int saved = errno;
    (void)rename(aside, target);
    errno = saved;
    return -1;
  }
  return 0;
}

static int path_matches_target(const char *path, const char *target) {
  return path != NULL && target != NULL && strcmp(path, target) == 0;
}

/*
 * GNU ld --wrap=lstat interposition for deterministic replacement races.
 * PERMGUARD_WRAP_MODE=before|after selects the boundary; coordination paths
 * come from the environment. Ordinary production builds never see this file.
 */
int __wrap_lstat(const char *path, struct stat *buf) {
  const char *mode = getenv("PERMGUARD_WRAP_MODE");
  const char *target = getenv("PERMGUARD_WRAP_TARGET");
  const char *aside = getenv("PERMGUARD_WRAP_ASIDE");
  const char *fresh = getenv("PERMGUARD_WRAP_FRESH");
  const char *proof = getenv("PERMGUARD_WRAP_PROOF");

  write_proof(proof);

  if (mode != NULL && path_matches_target(path, target)) {
    if (strcmp(mode, "before") == 0) {
      if (atomic_replace(target, aside, fresh) != 0) {
        return -1;
      }
      return __real_lstat(path, buf);
    }
    if (strcmp(mode, "after") == 0) {
      int rc = __real_lstat(path, buf);
      int saved = errno;
      struct stat captured;
      if (rc == 0) {
        captured = *buf;
        if (atomic_replace(target, aside, fresh) != 0) {
          /* Keep the already-observed snapshot; surface replace failure via
           * a non-zero return only when lstat itself failed. */
        }
        *buf = captured;
      }
      errno = saved;
      return rc;
    }
  }
  return __real_lstat(path, buf);
}
"""

_SEAM_LSTAT_C = r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static void write_proof(const char *proof_path) {
  FILE *fp;
  if (proof_path == NULL || proof_path[0] == '\0') {
    return;
  }
  fp = fopen(proof_path, "w");
  if (fp == NULL) {
    return;
  }
  (void)fputs("1\n", fp);
  (void)fclose(fp);
}

static int atomic_replace(const char *target, const char *aside,
                          const char *fresh) {
  if (target == NULL || aside == NULL || fresh == NULL) {
    errno = EINVAL;
    return -1;
  }
  if (rename(target, aside) != 0) {
    return -1;
  }
  if (rename(fresh, target) != 0) {
    int saved = errno;
    (void)rename(aside, target);
    errno = saved;
    return -1;
  }
  return 0;
}

/* Compile-time seam used only when --wrap=lstat cannot prove interposition. */
int permguard_test_lstat(const char *path, struct stat *buf) {
  const char *mode = getenv("PERMGUARD_WRAP_MODE");
  const char *target = getenv("PERMGUARD_WRAP_TARGET");
  const char *aside = getenv("PERMGUARD_WRAP_ASIDE");
  const char *fresh = getenv("PERMGUARD_WRAP_FRESH");
  const char *proof = getenv("PERMGUARD_WRAP_PROOF");

  write_proof(proof);

  if (mode != NULL && path != NULL && target != NULL &&
      strcmp(path, target) == 0) {
    if (strcmp(mode, "before") == 0) {
      if (atomic_replace(target, aside, fresh) != 0) {
        return -1;
      }
      return lstat(path, buf);
    }
    if (strcmp(mode, "after") == 0) {
      int rc = lstat(path, buf);
      int saved = errno;
      struct stat captured;
      if (rc == 0) {
        captured = *buf;
        (void)atomic_replace(target, aside, fresh);
        *buf = captured;
      }
      errno = saved;
      return rc;
    }
  }
  return lstat(path, buf);
}
"""


def _hostile_private_root(tmp_path_factory=None) -> Path:
    """Create a mode-0700 private root under /tmp for short deep-path budgets."""

    del tmp_path_factory  # reserved for future session reuse
    root = Path(tempfile.mkdtemp(prefix="permguard-hostile-", dir="/tmp"))
    os.chmod(root, MODE_CLEAN_DIR)
    require_mode(root, MODE_CLEAN_DIR, label="hostile-private-root")
    return root


def _restore_tree_modes(root: Path) -> None:
    """Best-effort chmod walk so mode-000 trees remain deletable."""

    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames + dirnames:
            path = Path(dirpath) / name
            try:
                os.chmod(path, MODE_CLEAN_DIR if path.is_dir() else MODE_CLEAN_FILE)
            except OSError:
                try:
                    os.lchmod(path, MODE_CLEAN_FILE)  # type: ignore[attr-defined]
                except (AttributeError, OSError):
                    pass
        try:
            os.chmod(dirpath, MODE_CLEAN_DIR)
        except OSError:
            pass


def make_self_loop_symlink(path: Path) -> Path:
    path.symlink_to(path.name)
    assert stat_mod.S_ISLNK(_mode_bits(path))
    return path


def make_two_link_loop(path_a: Path, path_b: Path) -> tuple[Path, Path]:
    path_a.symlink_to(path_b.name)
    path_b.symlink_to(path_a.name)
    assert stat_mod.S_ISLNK(_mode_bits(path_a))
    assert stat_mod.S_ISLNK(_mode_bits(path_b))
    return path_a, path_b


def make_fifo(path: Path, mode: int) -> Path:
    os.mkfifo(path)
    os.chmod(path, mode)
    require_mode(path, mode, label="fifo")
    assert stat_mod.S_ISFIFO(_mode_bits(path))
    return path


def make_unix_socket(path: Path, mode: int) -> tuple[Path, socket.socket]:
    """Bind an AF_UNIX socket pathname; caller must close the socket."""

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(os.fspath(path))
    except OSError as exc:
        sock.close()
        pytest.skip(
            f"host cannot bind AF_UNIX pathname fixture ({exc}); "
            "optional special-file addition unavailable"
        )
    os.chmod(path, mode)
    require_mode(path, mode, label="af-unix-socket")
    assert stat_mod.S_ISSOCK(_mode_bits(path))
    return path, sock


def make_deep_existing_path(
    root: Path,
    *,
    min_components: int = 64,
    min_bytes: int = 1024,
    leaf_mode: int = MODE_OTHER_WRITABLE_FILE,
) -> Path:
    """Build a real multi-component path under a short /tmp private root."""

    cur = root
    # Long-enough components so pathname bytes and component count both clear
    # the contract floors while remaining under the host path limit.
    component = "n" * 20
    created = 0
    while created < min_components:
        cur = cur / f"d{created:02d}{component}"
        try:
            cur.mkdir()
        except OSError as exc:
            pytest.skip(
                f"host cannot create deep path component {created + 1} "
                f"under {root} (errno {exc.errno})"
            )
        created += 1

    leaf = cur / f"leaf{component}"
    try:
        write_regular(leaf, leaf_mode)
    except OSError as exc:
        pytest.skip(
            f"host cannot create deep path leaf under {root} (errno {exc.errno})"
        )

    encoded = os.fsencode(leaf)
    components = len(leaf.relative_to(root).parts)
    if components < min_components:
        pytest.skip(
            f"deep path only reached {components} components; "
            f"need at least {min_components}"
        )
    if len(encoded) < min_bytes:
        pytest.skip(
            f"deep path only reached {len(encoded)} pathname bytes; "
            f"need at least {min_bytes}"
        )

    try:
        limit = os.pathconf(root, "PC_PATH_MAX")
    except (OSError, ValueError):
        limit = None
    if limit is not None and len(encoded) >= int(limit):
        pytest.skip(
            f"constructed deep path length {len(encoded)} is not below "
            f"host PC_PATH_MAX {limit}"
        )
    return leaf


def _host_path_max(root: Path) -> int | None:
    try:
        return int(os.pathconf(root, "PC_PATH_MAX"))
    except (OSError, ValueError, TypeError):
        return None


def _compile_argv_base(output: Path, *sources: Path) -> list[str]:
    return [
        os.environ.get("CC", "cc"),
        *STRICT_WARNING_FLAGS,
        POSIX_C_SOURCE_FLAG,
        "-o",
        str(output),
        *[str(src) for src in sources],
    ]


def _write_proof_probe_env(proof: Path) -> dict[str, str | None]:
    return {
        "PERMGUARD_WRAP_MODE": None,
        "PERMGUARD_WRAP_TARGET": None,
        "PERMGUARD_WRAP_ASIDE": None,
        "PERMGUARD_WRAP_FRESH": None,
        "PERMGUARD_WRAP_PROOF": str(proof),
    }


def _build_wrapped_permguard(build_dir: Path) -> Path:
    """Build a pytest-owned interposed binary; prove the seam was invoked."""

    if not SRC.is_file():
        pytest.fail(f"{SRC} is missing; hostile replacement seam requires source")

    wrap_c = build_dir / "permguard_wrap_lstat.c"
    wrap_c.write_text(_WRAP_LSTAT_C, encoding="utf-8")
    binary = build_dir / "permguard-wrap"
    compile_argv = _compile_argv_base(binary, SRC, wrap_c) + [
        "-Wl,--wrap=lstat",
    ]
    compiled = subprocess.run(compile_argv, capture_output=True, check=False)
    if compiled.returncode == 0 and binary.is_file():
        proof = build_dir / "wrap-proof-probe"
        if proof.exists():
            proof.unlink()
        probe_target = build_dir / "probe-clean"
        write_regular(probe_target, MODE_CLEAN_FILE)
        probe = run_permguard_hostile(
            binary,
            probe_target,
            env=_write_proof_probe_env(proof),
        )
        if (
            probe.returncode == 0
            and proof.is_file()
            and proof.read_text(encoding="ascii") == "1\n"
        ):
            return binary

    # Deterministic compile-time seam fallback (never sleep / never silent skip).
    seam_c = build_dir / "permguard_seam_lstat.c"
    seam_c.write_text(_SEAM_LSTAT_C, encoding="utf-8")
    src_text = SRC.read_text(encoding="utf-8")
    patched, count = re.subn(
        r"(?<!\w)lstat\s*\(\s*path\s*,\s*&st\s*\)",
        "permguard_test_lstat(path, &st)",
        src_text,
        count=1,
    )
    if count != 1:
        pytest.fail(
            "unable to install compile-time lstat seam: expected exactly one "
            "lstat(path, &st) call site in src/permguard.c"
        )
    if "#include <sys/stat.h>" not in patched:
        pytest.fail("seamed source lost #include <sys/stat.h>")
    patched = patched.replace(
        "#include <sys/stat.h>\n",
        "#include <sys/stat.h>\n"
        "int permguard_test_lstat(const char *path, struct stat *buf);\n",
        1,
    )
    patched_src = build_dir / "permguard_seamed.c"
    patched_src.write_text(patched, encoding="utf-8")
    seam_binary = build_dir / "permguard-seam"
    seam_argv = _compile_argv_base(seam_binary, patched_src, seam_c)
    seamed = subprocess.run(seam_argv, capture_output=True, check=False)
    if seamed.returncode != 0:
        detail = seamed.stderr.decode("utf-8", errors="replace")
        wrap_detail = compiled.stderr.decode("utf-8", errors="replace")
        pytest.fail(
            "failed to build deterministic replacement seam binary.\n"
            f"wrap link:\n{wrap_detail}\nseam compile:\n{detail}"
        )

    proof = build_dir / "seam-proof-probe"
    if proof.exists():
        proof.unlink()
    probe_target = build_dir / "seam-probe-clean"
    write_regular(probe_target, MODE_CLEAN_FILE)
    probe = run_permguard_hostile(
        seam_binary,
        probe_target,
        env=_write_proof_probe_env(proof),
    )
    if not (
        probe.returncode == 0
        and proof.is_file()
        and proof.read_text(encoding="ascii") == "1\n"
    ):
        pytest.fail(
            "replacement-race seam binary did not prove metadata interposition; "
            "refusing to fall back to an uninterposed permguard"
        )
    return seam_binary


def _assert_no_pgh_tokens(*blobs: bytes) -> None:
    for blob in blobs:
        for label in HOSTILE_FIXTURE_HAZARDS:
            assert label.encode("ascii") not in blob


def test_hostile_contract_labels_are_not_product_tokens(permguard_bin, tmp_path):
    """AC-01: PGH_* names organize tests only; never appear in product output."""

    path = write_regular(tmp_path / "ac01-clean", MODE_CLEAN_FILE)
    result = run_permguard_hostile(permguard_bin, path)
    assert result.returncode == 0
    _assert_no_pgh_tokens(result.stdout, result.stderr)
    if HOSTILE_FIXTURES_CONTRACT.is_file():
        text = HOSTILE_FIXTURES_CONTRACT.read_text(encoding="utf-8")
        for label in HOSTILE_FIXTURE_HAZARDS:
            assert label in text


# --- PGH_DANGLING_SYMBOLIC_LINK -------------------------------------------------


def test_hostile_pgh_dangling_symbolic_link(permguard_bin, tmp_path):
    root = tmp_path
    os.chmod(root, MODE_CLEAN_DIR)
    dangling = root / "pgh-dangling"
    dangling.symlink_to("definitely-absent-pgh-target")
    assert stat_mod.S_ISLNK(_mode_bits(dangling))
    assert not (root / "definitely-absent-pgh-target").exists()

    before = snapshot_entry(dangling)
    result = run_permguard_hostile(permguard_bin, dangling)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_symbolic_link(dangling)
    assert b"MISSING" not in result.stderr
    for code in HAZARD_RANK:
        assert code.encode("ascii") not in result.stdout
        assert code.encode("ascii") not in result.stderr
    _assert_no_pgh_tokens(result.stdout, result.stderr)
    assert_unchanged(dangling, before)


# --- PGH_SYMBOLIC_LINK_LOOP -----------------------------------------------------


def test_hostile_pgh_final_self_loop_is_symbolic_link(permguard_bin, tmp_path):
    loop = make_self_loop_symlink(tmp_path / "self-loop")
    result = run_permguard_hostile(permguard_bin, loop)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_symbolic_link(loop)
    assert b"INSPECTION_ERROR_" not in result.stderr
    _assert_no_pgh_tokens(result.stdout, result.stderr)


def test_hostile_pgh_final_two_link_loop_is_symbolic_link(permguard_bin, tmp_path):
    link_a, link_b = make_two_link_loop(tmp_path / "loop-a", tmp_path / "loop-b")
    for link in (link_a, link_b):
        result = run_permguard_hostile(permguard_bin, link)
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr == diagnostic_symbolic_link(link)
        assert f"INSPECTION_ERROR_{errno.ELOOP}".encode("ascii") not in result.stderr
        for code in HAZARD_RANK:
            assert code.encode("ascii") not in result.stdout


def test_hostile_pgh_intermediate_loop_is_inspection_error_eloop(
    permguard_bin, tmp_path
):
    link_a, link_b = make_two_link_loop(
        tmp_path / "mid-loop-a", tmp_path / "mid-loop-b"
    )
    nested = link_a / "nested-child"
    try:
        os.lstat(nested)
    except OSError as exc:
        expected_errno = exc.errno
    else:
        pytest.fail("intermediate symlink loop unexpectedly became lstat-able")

    assert expected_errno == errno.ELOOP

    result = run_permguard_hostile(permguard_bin, nested)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == diagnostic_inspection_error(expected_errno, nested)
    assert b"SYMBOLIC_LINK" not in result.stderr
    for code in HAZARD_RANK:
        assert code.encode("ascii") not in result.stdout
    _assert_no_pgh_tokens(result.stdout, result.stderr)
    # Loop entries themselves remain untouched symlink fixtures.
    assert stat_mod.S_ISLNK(_mode_bits(link_a))
    assert stat_mod.S_ISLNK(_mode_bits(link_b))


# --- PGH_UNREADABLE_ENTRY -------------------------------------------------------


def test_hostile_pgh_mode_000_regular_file_is_metadata_inspectable(
    permguard_bin, tmp_path
):
    path = write_regular(tmp_path / "mode-000-file", MODE_CLEAN_FILE)
    os.chmod(path, MODE_UNREADABLE)
    require_mode(path, MODE_UNREADABLE, label="mode-000-file")
    actual = _mode_bits(path)
    assert hazards_for_mode(actual) == []
    assert stat_mod.S_ISREG(actual)

    # Content is intentionally unreadable; snapshot mode only (no open).
    before_mode = actual
    result = run_permguard_hostile(permguard_bin, path)
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    assert _mode_bits(path) == before_mode
    _assert_no_pgh_tokens(result.stdout, result.stderr)


def test_hostile_pgh_mode_000_directory_is_metadata_inspectable(
    permguard_bin, tmp_path
):
    path = make_directory(tmp_path / "mode-000-dir", MODE_CLEAN_DIR)
    os.chmod(path, MODE_UNREADABLE)
    require_mode(path, MODE_UNREADABLE, label="mode-000-dir")
    actual = _mode_bits(path)
    assert hazards_for_mode(actual) == []

    before = snapshot_entry(path)
    try:
        result = run_permguard_hostile(permguard_bin, path)
        assert result.returncode == 0
        assert result.stdout == b""
        assert result.stderr == b""
        assert_unchanged(path, before)
    finally:
        os.chmod(path, MODE_CLEAN_DIR)


def test_hostile_pgh_child_below_non_searchable_parent_is_inaccessible(
    permguard_bin, tmp_path
):
    if os.geteuid() == 0:
        pytest.skip(
            "EACCES inaccessible-child fixture is unreliable as root; "
            "host cannot produce a trustworthy search-denial oracle"
        )

    blocked = tmp_path / "blocked-parent"
    blocked.mkdir()
    child = blocked / "secret-child"
    write_regular(child, MODE_CLEAN_FILE)
    os.chmod(blocked, MODE_UNREADABLE)
    try:
        try:
            os.lstat(child)
        except OSError as exc:
            if exc.errno != errno.EACCES:
                pytest.skip(
                    "host did not produce EACCES for non-searchable parent "
                    f"child (got errno {exc.errno}); capability unavailable"
                )
        else:
            pytest.skip(
                "host bypassed directory search restriction; "
                "cannot produce EACCES inaccessible-child fixture"
            )

        result = run_permguard_hostile(permguard_bin, child)
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr == diagnostic_inaccessible(child)
        _assert_no_pgh_tokens(result.stdout, result.stderr)
    finally:
        os.chmod(blocked, MODE_CLEAN_DIR)


# --- PGH_PERMISSION_CHANGE ------------------------------------------------------


def test_hostile_pgh_permission_transitions_are_point_in_time(
    permguard_bin, tmp_path
):
    path = write_regular(tmp_path / "perm-transition", MODE_CLEAN_FILE)
    content_before = path.read_bytes()

    sequence = (
        (MODE_CLEAN_FILE, 0, b""),
        (
            MODE_GROUP_WRITABLE_FILE,
            1,
            findings_for_path(path, MODE_GROUP_WRITABLE_FILE),
        ),
        (
            MODE_OTHER_WRITABLE_FILE,
            1,
            findings_for_path(path, MODE_OTHER_WRITABLE_FILE),
        ),
        (MODE_CLEAN_FILE, 0, b""),
    )

    for mode, status, stdout in sequence:
        os.chmod(path, mode)
        require_mode(path, mode, label="permission-transition")
        before = snapshot_entry(path)
        result = run_permguard_hostile(permguard_bin, path)
        assert result.returncode == status
        assert result.stdout == stdout
        assert result.stderr == b""
        assert_unchanged(path, before)
        assert path.read_bytes() == content_before
        _assert_no_pgh_tokens(result.stdout, result.stderr)


# --- PGH_UNUSUAL_FILENAME -------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_name", "escaped_fragment", "mode", "status"),
    [
        (b"name with spaces", b"name with spaces", MODE_OTHER_WRITABLE_FILE, 1),
        (b'quote-"-name', b'quote-\\"-name', MODE_GROUP_WRITABLE_FILE, 1),
        (b"back\\slash", b"back\\\\slash", MODE_OTHER_WRITABLE_FILE, 1),
        (b"has\ttab", b"has\\x09tab", MODE_OTHER_WRITABLE_FILE, 1),
        (b"has\nnewline", b"has\\x0Anewline", MODE_OTHER_WRITABLE_FILE, 1),
        (b"has\x1besc", b"has\\x1Besc", MODE_OTHER_WRITABLE_FILE, 1),
        (b"has\x7fdel", b"has\\x7Fdel", MODE_OTHER_WRITABLE_FILE, 1),
    ],
)
def test_hostile_pgh_unusual_filename_escaping(
    permguard_bin, tmp_path, raw_name, escaped_fragment, mode, status
):
    name = os.fsdecode(raw_name)
    path = tmp_path / name
    try:
        write_regular(path, mode)
    except OSError as exc:
        pytest.skip(
            f"host filesystem cannot create unusual name {raw_name!r}: {exc}"
        )

    before = snapshot_entry(path)
    result = run_permguard_hostile(permguard_bin, path)
    assert result.returncode == status
    assert result.stderr == b""
    assert result.stdout == findings_for_path(path, mode)
    assert_no_raw_unsafe_bytes(result.stdout)
    assert escaped_fragment in result.stdout
    # Basenames that contain bytes needing \xHH escaping must not appear raw.
    if any(byte < 0x20 or byte > 0x7E for byte in raw_name):
        assert raw_name not in result.stdout
    assert_unchanged(path, before)
    _assert_no_pgh_tokens(result.stdout, result.stderr)


def test_hostile_pgh_leading_dash_name_after_terminator(permguard_bin, tmp_path):
    write_regular(tmp_path / "-leading-dash", MODE_OTHER_WRITABLE_FILE)
    # Operand bytes after `--` are relative; findings quote those bytes.
    result = run_permguard_hostile(
        permguard_bin, "--", "-leading-dash", cwd=tmp_path
    )
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_for_path(
        "-leading-dash", MODE_OTHER_WRITABLE_FILE
    )
    assert_no_raw_unsafe_bytes(result.stdout)


def test_hostile_pgh_non_utf8_filename_when_supported(permguard_bin, tmp_path):
    raw_name = b"nonutf8-\xff-name"
    name = os.fsdecode(raw_name)
    path = tmp_path / name
    try:
        write_regular(path, MODE_OTHER_WRITABLE_FILE)
    except OSError as exc:
        pytest.skip(
            f"host filesystem cannot create non-UTF-8 name {raw_name!r}: {exc}"
        )

    result = run_permguard_hostile(permguard_bin, path)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_for_path(path, MODE_OTHER_WRITABLE_FILE)
    assert b"\\xFF" in result.stdout
    assert b"\xff" not in result.stdout
    assert_no_raw_unsafe_bytes(result.stdout)


# --- PGH_DEEP_PATH --------------------------------------------------------------


def test_hostile_pgh_deep_existing_path_classifies_normally(permguard_bin):
    root = _hostile_private_root()
    try:
        leaf = make_deep_existing_path(
            root,
            min_components=64,
            min_bytes=1024,
            leaf_mode=MODE_OTHER_WRITABLE_FILE,
        )
        before = snapshot_entry(leaf)
        result = run_permguard_hostile(permguard_bin, leaf)
        assert result.returncode == 1
        assert result.stderr == b""
        assert result.stdout == findings_for_path(
            leaf, MODE_OTHER_WRITABLE_FILE
        )
        assert_unchanged(leaf, before)
        _assert_no_pgh_tokens(result.stdout, result.stderr)
        assert len(os.fsencode(leaf)) >= 1024
        assert len(leaf.relative_to(root).parts) >= 64
    finally:
        _restore_tree_modes(root)
        shutil.rmtree(root, ignore_errors=True)


def test_hostile_pgh_deep_path_over_limit_matches_preflight_errno(permguard_bin):
    root = _hostile_private_root()
    try:
        limit = _host_path_max(root)
        if limit is None or limit <= 0:
            pytest.skip(
                "host does not expose PC_PATH_MAX; cannot construct a "
                "process-level over-limit deep-path operand"
            )

        # Construct an argv pathname past the measured limit without requiring
        # the filesystem to materialize it.
        over = root / ("Z" * (int(limit) + 64))
        over_s = os.fspath(over)
        try:
            os.lstat(over_s)
        except OSError as exc:
            expected_errno = exc.errno
        except ValueError as exc:
            pytest.skip(
                f"Python rejected over-limit path before lstat ({exc}); "
                "cannot pin product errno oracle"
            )
        else:
            pytest.skip(
                "host accepted an over-limit pathname; cannot exercise "
                "failing deep-path lookup"
            )

        result = run_permguard_hostile(permguard_bin, over_s)
        assert result.returncode == 2
        assert result.stdout == b""
        if expected_errno == errno.ENOENT:
            assert result.stderr == diagnostic_missing(over_s)
        elif expected_errno == errno.EACCES:
            assert result.stderr == diagnostic_inaccessible(over_s)
        else:
            assert result.stderr == diagnostic_inspection_error(
                expected_errno, over_s
            )
        _assert_no_pgh_tokens(result.stdout, result.stderr)
    finally:
        _restore_tree_modes(root)
        shutil.rmtree(root, ignore_errors=True)


# --- PGH_FIFO_OR_SPECIAL_FILE ---------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [
        (MODE_CLEAN_FILE, 0),
        (MODE_GROUP_WRITABLE_FILE, 1),
        (MODE_OTHER_WRITABLE_FILE, 1),
        (MODE_BOTH_WRITABLE_FILE, 1),
    ],
)
def test_hostile_pgh_fifo_classifies_mode_bits_without_blocking(
    permguard_bin, tmp_path, mode, expected_status
):
    path = tmp_path / f"fifo-{mode:04o}"
    make_fifo(path, mode)
    before = snapshot_entry(path)
    result = run_permguard_hostile(permguard_bin, path)
    assert result.returncode == expected_status
    assert result.stderr == b""
    assert result.stdout == findings_for_path(path, mode)
    assert_unchanged(path, before)
    _assert_no_pgh_tokens(result.stdout, result.stderr)
    # Never open either end: re-check still a FIFO with the same mode.
    assert stat_mod.S_ISFIFO(_mode_bits(path))


def test_hostile_pgh_af_unix_socket_classifies_when_supported(
    permguard_bin, tmp_path
):
    path = tmp_path / "pgh.sock"
    sock_path = None
    sock = None
    try:
        sock_path, sock = make_unix_socket(path, MODE_OTHER_WRITABLE_FILE)
        before = snapshot_entry(sock_path)
        result = run_permguard_hostile(permguard_bin, sock_path)
        assert result.returncode == 1
        assert result.stderr == b""
        assert result.stdout == findings_for_path(
            sock_path, MODE_OTHER_WRITABLE_FILE
        )
        assert_unchanged(sock_path, before)
    finally:
        if sock is not None:
            sock.close()
        if sock_path is not None and sock_path.exists():
            sock_path.unlink()


def test_hostile_pgh_fifo_setid_bits_when_preserved(permguard_bin, tmp_path):
    path = tmp_path / "fifo-setgid"
    os.mkfifo(path)
    os.chmod(path, MODE_SETGID_FILE)
    actual = _mode_bits(path) & MODE_MASK
    if not (actual & stat_mod.S_ISGID):
        pytest.skip(
            "host filesystem did not preserve set-group-ID on FIFO; "
            "optional special-file set-ID addition unavailable"
        )
    require_mode(path, actual, label="fifo-setgid")
    result = run_permguard_hostile(permguard_bin, path)
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_for_path(path, actual)


# --- PGH_REPLACEMENT_RACE -------------------------------------------------------


def test_hostile_pgh_replacement_before_lstat_classifies_new_object(tmp_path):
    build_dir = tmp_path / "wrap-build-before"
    build_dir.mkdir()
    binary = _build_wrapped_permguard(build_dir)

    target = tmp_path / "race-target"
    aside = tmp_path / "race-aside"
    fresh = tmp_path / "race-fresh"
    proof = tmp_path / "race-proof-before"
    write_regular(target, MODE_CLEAN_FILE, data=b"old-clean\n")
    write_regular(fresh, MODE_OTHER_WRITABLE_FILE, data=b"new-other\n")

    env = {
        "PERMGUARD_WRAP_MODE": "before",
        "PERMGUARD_WRAP_TARGET": str(target),
        "PERMGUARD_WRAP_ASIDE": str(aside),
        "PERMGUARD_WRAP_FRESH": str(fresh),
        "PERMGUARD_WRAP_PROOF": str(proof),
    }
    result = run_permguard_hostile(binary, target, env=env)
    assert proof.is_file() and proof.read_text(encoding="ascii") == "1\n"
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_for_path(target, MODE_OTHER_WRITABLE_FILE)
    assert target.read_bytes() == b"new-other\n"
    assert aside.read_bytes() == b"old-clean\n"
    assert not fresh.exists()
    _assert_no_pgh_tokens(result.stdout, result.stderr)


def test_hostile_pgh_replacement_after_lstat_classifies_old_snapshot(tmp_path):
    build_dir = tmp_path / "wrap-build-after"
    build_dir.mkdir()
    binary = _build_wrapped_permguard(build_dir)

    target = tmp_path / "race-target-after"
    aside = tmp_path / "race-aside-after"
    fresh = tmp_path / "race-fresh-after"
    proof = tmp_path / "race-proof-after"
    write_regular(target, MODE_CLEAN_FILE, data=b"old-clean\n")
    write_regular(fresh, MODE_OTHER_WRITABLE_FILE, data=b"new-other\n")

    env = {
        "PERMGUARD_WRAP_MODE": "after",
        "PERMGUARD_WRAP_TARGET": str(target),
        "PERMGUARD_WRAP_ASIDE": str(aside),
        "PERMGUARD_WRAP_FRESH": str(fresh),
        "PERMGUARD_WRAP_PROOF": str(proof),
    }
    result = run_permguard_hostile(binary, target, env=env)
    assert proof.is_file() and proof.read_text(encoding="ascii") == "1\n"
    # Classification must use the pre-replacement clean snapshot.
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""
    # Path bytes now belong to the replacement object.
    assert target.read_bytes() == b"new-other\n"
    assert (_mode_bits(target) & MODE_MASK) == (
        MODE_OTHER_WRITABLE_FILE & MODE_MASK
    )
    assert aside.read_bytes() == b"old-clean\n"
    _assert_no_pgh_tokens(result.stdout, result.stderr)


def test_hostile_pgh_replacement_stress_outcomes_stay_in_closed_set(
    permguard_bin, tmp_path
):
    """Optional unsynchronized probe: each run yields only the closed set.

    Not a byte-repeatability claim. Does not replace the controlled-seam tests.
    """

    target = tmp_path / "stress-target"
    alt = tmp_path / "stress-alt"
    write_regular(target, MODE_CLEAN_FILE, data=b"a\n")
    write_regular(alt, MODE_OTHER_WRITABLE_FILE, data=b"b\n")

    for _ in range(8):
        # Flip names within the private root without sleeping.
        os.rename(target, tmp_path / "stress-tmp")
        os.rename(alt, target)
        os.rename(tmp_path / "stress-tmp", alt)
        result = run_permguard_hostile(permguard_bin, target)
        assert result.returncode in {0, 1, 2}
        _assert_no_pgh_tokens(result.stdout, result.stderr)
        if result.returncode == 2:
            assert result.stdout == b""
            assert result.stderr.startswith(b"permguard: ")
            assert (
                b"MISSING:" in result.stderr
                or b"INACCESSIBLE:" in result.stderr
                or b"SYMBOLIC_LINK:" in result.stderr
                or b"INSPECTION_ERROR_" in result.stderr
                or result.stderr == diagnostic_stdout_write()
            )
            continue

        assert result.stderr == b""
        mode = _mode_bits(target)
        expected = findings_for_path(target, mode)
        assert result.stdout == expected
        if expected:
            assert result.returncode == 1
        else:
            assert result.returncode == 0


def test_hostile_pgh_source_surface_unchanged_no_open_or_follow():
    """AC-11: hostile slice must not widen the production inspection surface."""

    if not SRC.is_file():
        pytest.fail(f"{SRC} is missing; hostile source-surface check requires it")
    text = SRC.read_text(encoding="utf-8")
    for label in HOSTILE_FIXTURE_HAZARDS:
        assert label not in text
    for pattern, name in (
        (r"(?<!l)\bstat\s*\(", "bare stat("),
        (r"\brealpath\s*\(", "realpath("),
        (r"\breadlink\s*\(", "readlink("),
        (r"\baccess\s*\(", "access("),
        (r"(?<!f)\bopen\s*\(", "open("),
        (r"\bmkfifo\s*\(", "mkfifo("),
        (r"\bsocket\s*\(", "socket("),
    ):
        assert re.search(pattern, text) is None, (
            f"src/permguard.c must not call {name}"
        )
    assert len(re.findall(r"(?<!\w)lstat\s*\(\s*(?!\d)", text)) >= 1
