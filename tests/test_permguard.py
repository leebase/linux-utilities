"""Contract tests for the permguard bootstrap slice.

Encodes docs/permguard-bootstrap-contract.md. Builds src/permguard.c into a
pytest-owned temporary directory, exercises only deterministic temporary
fixtures with lstat-visible mode bits, and never leaves binaries in the
workspace. Child processes receive a sealed, locale-stable environment.
Missing source fails closed; host-capability skips state the missing
capability explicitly and are never reported as passes.

Coverage maps to acceptance checks AC-01 through AC-09: CLI/usage, clean and
hazardous file/directory fixtures, every closed taxonomy bit and combinations,
multi-operand ordering with duplicates, missing/inaccessible/invalid operands,
symlink non-follow for safe and hazardous targets, mixed-success precedence,
exact statuses 0/1/2 with pinned stdout/stderr bytes, and a narrow lstat-only
inspection surface.
"""

from __future__ import annotations

import errno
import os
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
SRC = ROOT / "src" / "permguard.c"
CONTRACT = ROOT / "docs" / "permguard-bootstrap-contract.md"

STRICT_WARNING_FLAGS = (
    "-std=c17",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
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
    )
    return _finish_valgrind(result, vg_log)


def resolve_permguard_override(env_bin: str) -> Path:
    """Resolve PERMGUARD_BIN once so a relative override cannot track cwd."""

    resolved = Path(env_bin).expanduser().resolve()
    if not resolved.is_absolute():
        raise ValueError(
            f"PERMGUARD_BIN did not resolve to an absolute path: {env_bin!r}"
        )
    return resolved


@pytest.fixture(scope="session")
def permguard_bin(tmp_path_factory):
    env_bin = os.environ.get("PERMGUARD_BIN")
    if env_bin:
        binary = resolve_permguard_override(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"PERMGUARD_BIN is not an executable file: {env_bin}")
        return binary

    if not SRC.is_file():
        pytest.fail(
            f"{SRC} is missing; permguard bootstrap suite requires the source"
        )

    # Compile into pytest's session temp tree only — never build/ or the repo.
    build_dir = tmp_path_factory.mktemp("permguard-build")
    binary = build_dir / "permguard"
    compile_result = subprocess.run(
        [
            os.environ.get("CC", "cc"),
            *STRICT_WARNING_FLAGS,
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
    assert binary.resolve() != (ROOT / "permguard").resolve()
    assert binary.resolve() != (ROOT / "build" / "permguard").resolve()
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
