"""Contract tests for the pathaudit vertical slice.

Encodes docs/pathaudit-contract.md before the C implementation exists.
Builds src/pathaudit.c into a test-owned temporary directory when present,
exercises only deterministic temporary fixtures, and never inspects the
worker's real PATH, requires root, uses the network, or leaves binaries in
the workspace.
"""

from __future__ import annotations

import errno as errno_mod
import os
import shutil
import subprocess
import tempfile
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pathaudit.c"

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

    fd, vg_log = tempfile.mkstemp(prefix="pathaudit-valgrind.")
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

    run_env = {
        # Never consult the worker PATH; keep an explicit unreachable value.
        "PATH": "/pathaudit-tests-must-not-search-here",
        "LC_ALL": "C",
        "LANG": "C",
    }
    if env:
        run_env.update(env)

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
        env={
            "PATH": "/pathaudit-tests-must-not-search-here",
            "LC_ALL": "C",
            "LANG": "C",
        },
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


@pytest.fixture(scope="session")
def pathaudit_bin(tmp_path_factory):
    env_bin = os.environ.get("PATHAUDIT_BIN")
    if env_bin:
        binary = Path(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"PATHAUDIT_BIN is not an executable file: {env_bin}")
        return binary

    if not SRC.is_file():
        pytest.skip("src/pathaudit.c is not implemented yet")

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


def test_control_bytes_quotes_and_non_utf8_in_diagnostics(pathaudit_bin, tmp_path):
    weird = tmp_path / os.fsdecode(b"diag-\x1b-\xff-\"-\\-name")
    # Missing path keeps the diagnostic on the operand text itself.
    result = run_pathaudit(pathaudit_bin, str(weird.resolve()))
    # Missing is a hazard (status 1), not a diagnostic path — pin escaping there.
    assert result.returncode == 1
    assert result.stderr == b""
    assert result.stdout == findings_stdout([("MISSING_ROOT", weird.resolve())])
    assert_no_raw_unsafe_bytes(result.stdout)
    assert b"\x1b" not in result.stdout
    assert b"\xff" not in result.stdout


def test_closed_stdout_pipe_reports_stdout_write(pathaudit_bin, fixture_tree):
    status, stderr = run_with_closed_stdout_pipe(pathaudit_bin, "--help")
    assert status == 2
    assert stderr == diagnostic_lines("STDOUT_WRITE") or stderr.startswith(
        b"pathaudit: STDOUT_WRITE"
    )
    assert b"STDOUT_WRITE" in stderr
    assert_no_raw_unsafe_bytes(stderr)

    # Hazard emission must also fail closed on a broken stdout pipe.
    status, stderr = run_with_closed_stdout_pipe(
        pathaudit_bin, str(fixture_tree.group_w)
    )
    assert status == 2
    assert b"STDOUT_WRITE" in stderr
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
