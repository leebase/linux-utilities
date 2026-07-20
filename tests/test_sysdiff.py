import errno as errno_mod
import os
import subprocess
import tarfile
import tempfile
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sysdiff.c"
EPIPE_MESSAGE = os.strerror(errno_mod.EPIPE).encode()


@pytest.fixture(scope="session")
def sysdiff_bin(tmp_path_factory):
    env_bin = os.environ.get("SYSDIFF_BIN")
    if env_bin:
        binary = Path(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"SYSDIFF_BIN is not an executable file: {env_bin}")
        return binary

    build_dir = tmp_path_factory.mktemp("build")
    binary = build_dir / "sysdiff"
    subprocess.run(
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
        check=True,
    )
    return binary


def _valgrind_command(cmd):
    """Wrap cmd in Valgrind when SYSDIFF_UNDER_VALGRIND=1; logs use TMPDIR."""

    if os.environ.get("SYSDIFF_UNDER_VALGRIND") != "1":
        return cmd, None

    fd, vg_log = tempfile.mkstemp(prefix="sysdiff-valgrind.")
    os.close(fd)
    wrapped = [
        "valgrind",
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


def run_sysdiff(binary, *args):
    cmd, vg_log = _valgrind_command([str(binary), *map(str, args)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    return _finish_valgrind(result, vg_log)


def run_sysdiff_bytes(binary, *args):
    cmd, vg_log = _valgrind_command([str(binary), *map(str, args)])
    result = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
    )
    return _finish_valgrind(result, vg_log)


def write_snapshot(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def write_snapshot_bytes(path, data):
    path.write_bytes(data)
    return path


def assert_no_raw_unsafe_bytes(data: bytes):
    for index, byte in enumerate(data):
        if byte == 0x0A:
            continue
        if byte < 0x20 or byte > 0x7E:
            raise AssertionError(
                f"unsafe raw byte 0x{byte:02X} at offset {index} in output"
            )


def test_help_and_version(sysdiff_bin):
    no_args_result = run_sysdiff(sysdiff_bin)
    assert no_args_result.returncode == 0
    assert "usage: sysdiff" in no_args_result.stdout
    assert no_args_result.stderr == ""

    help_result = run_sysdiff(sysdiff_bin, "--help")
    assert help_result.returncode == 0
    assert "usage: sysdiff" in help_result.stdout
    assert help_result.stderr == ""

    version_result = run_sysdiff(sysdiff_bin, "--version")
    assert version_result.returncode == 0
    assert version_result.stdout == "sysdiff 0.1.0\n"
    assert version_result.stderr == ""


def test_compare_reports_sorted_resource_diffs(sysdiff_bin, tmp_path):
    before = write_snapshot(
        tmp_path / "before.snapshot",
        """# before snapshot
sysdiff.snapshot_version=1
os.id=debian
kernel.release=6.1.0-21-amd64
package.openssh-server.version=1:9.2p1-2+deb12u3
service.ssh.active=
service.ssh.enabled=old # enabled=true
file./etc/ssh/sshd_config.sha256=old=hash
removed.key=gone
same.keep=stable
z.changed=old value
""",
    )
    after = write_snapshot(
        tmp_path / "after.snapshot",
        """same.keep=stable
z.changed=new value

   # comment with leading horizontal space
added.key=new value
sysdiff.snapshot_version=1
file./etc/ssh/sshd_config.sha256=new=hash
service.ssh.enabled=new # enabled=false
service.ssh.active=
package.openssh-server.version=1:9.2p1-2+deb12u4
kernel.release=6.1.0-21-amd64
os.id=debian
""",
    )

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 1
    assert result.stderr == ""
    assert result.stdout == (
        "+ added.key=new value\n"
        "~ file./etc/ssh/sshd_config.sha256: old=hash -> new=hash\n"
        "~ package.openssh-server.version: 1:9.2p1-2+deb12u3 -> "
        "1:9.2p1-2+deb12u4\n"
        "- removed.key=gone\n"
        "~ service.ssh.enabled: old # enabled=true -> new # enabled=false\n"
        "~ z.changed: old value -> new value\n"
    )


def test_identical_snapshots_report_no_changes_and_accept_final_line_without_newline(
    sysdiff_bin, tmp_path
):
    snapshot = write_snapshot(
        tmp_path / "snapshot",
        "sysdiff.snapshot_version=1\nos.id=debian\nservice.ssh.active=",
    )

    result = run_sysdiff(sysdiff_bin, "compare", snapshot, snapshot)

    assert result.returncode == 0
    assert result.stdout == "no changes\n"
    assert result.stderr == ""


def test_whitespace_only_space_and_tab_lines_are_ignored(sysdiff_bin, tmp_path):
    whitespace_only = write_snapshot(
        tmp_path / "whitespace-only.snapshot", " \t \n\t\t\n"
    )

    result = run_sysdiff(sysdiff_bin, "compare", whitespace_only, whitespace_only)

    assert result.returncode == 0
    assert result.stdout == "no changes\n"
    assert result.stderr == ""


def test_input_order_does_not_affect_diff_output(sysdiff_bin, tmp_path):
    before_a = write_snapshot(
        tmp_path / "before-a",
        "z.key=old\nb.key=old\nsame.key=value\na.key=old\n",
    )
    after_a = write_snapshot(
        tmp_path / "after-a",
        "same.key=value\nc.key=new\na.key=new\n",
    )
    before_b = write_snapshot(
        tmp_path / "before-b",
        "same.key=value\na.key=old\nz.key=old\nb.key=old\n",
    )
    after_b = write_snapshot(
        tmp_path / "after-b",
        "a.key=new\nc.key=new\nsame.key=value\n",
    )

    first = run_sysdiff(sysdiff_bin, "compare", before_a, after_a)
    second = run_sysdiff(sysdiff_bin, "compare", before_b, after_b)

    assert first.returncode == 1
    assert second.returncode == 1
    assert first.stdout == second.stdout
    assert first.stdout == (
        "~ a.key: old -> new\n" "- b.key=old\n" "+ c.key=new\n" "- z.key=old\n"
    )
    assert first.stderr == ""
    assert second.stderr == ""


# RC-001: bytewise order places uppercase before lowercase (A < a). Keys Alpha
# and alpha are required; Zebra/beta make a strcasecmp sort invert Zebra vs
# alpha deterministically (case-fold puts alpha before Zebra).
MIXED_CASE_BYTEWISE_EXPECTED = (
    "+ Alpha.item=1\n"
    "+ Zebra.item=1\n"
    "+ alpha.item=1\n"
    "+ beta.item=1\n"
)
MIXED_CASE_AFTER_BYTEWISE = (
    "Alpha.item=1\nZebra.item=1\nalpha.item=1\nbeta.item=1\n"
)
MIXED_CASE_AFTER_REVERSED = (
    "beta.item=1\nalpha.item=1\nZebra.item=1\nAlpha.item=1\n"
)
COMPARE_ENTRIES_STRCMP = (
    "return strcmp(left_entry->key, right_entry->key);"
)
COMPARE_ENTRIES_STRCASECMP = (
    "return strcasecmp(left_entry->key, right_entry->key);"
)


def _compile_sysdiff(source: Path, binary: Path):
    subprocess.run(
        [
            os.environ.get("CC", "cc"),
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-o",
            str(binary),
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _assert_mixed_case_bytewise_order(binary: Path, work: Path):
    work.mkdir(parents=True, exist_ok=True)
    before = write_snapshot(work / "before.snapshot", "same.keep=stable\n")
    after_bytewise = write_snapshot(
        work / "after-bytewise.snapshot",
        "same.keep=stable\n" + MIXED_CASE_AFTER_BYTEWISE,
    )
    after_reversed = write_snapshot(
        work / "after-reversed.snapshot",
        "same.keep=stable\n" + MIXED_CASE_AFTER_REVERSED,
    )

    first = run_sysdiff(binary, "compare", before, after_bytewise)
    second = run_sysdiff(binary, "compare", before, after_reversed)

    assert first.returncode == 1
    assert second.returncode == 1
    assert first.stderr == ""
    assert second.stderr == ""
    assert first.stdout == MIXED_CASE_BYTEWISE_EXPECTED
    assert second.stdout == MIXED_CASE_BYTEWISE_EXPECTED
    assert first.stdout == second.stdout


def test_mixed_case_keys_are_sorted_bytewise_in_both_input_orders(
    sysdiff_bin, tmp_path
):
    """RC-001: Alpha/alpha (and Zebra/beta) pin locale-independent byte order."""

    _assert_mixed_case_bytewise_order(sysdiff_bin, tmp_path)


def test_strcasecmp_key_sort_mutant_is_killed_from_clean_scratch():
    """Copy sources to /tmp, prove baseline, mutate only the copy, kill mutant.

    Replaces strcmp with strcasecmp solely in compare_entries_by_key inside the
    scratch tree. The governed workspace source must remain untouched.
    """

    original_text = SRC.read_text(encoding="utf-8")
    assert COMPARE_ENTRIES_STRCMP in original_text
    assert COMPARE_ENTRIES_STRCASECMP not in original_text

    scratch = Path(
        tempfile.mkdtemp(prefix="sysdiff-rc001-mutant.", dir="/tmp")
    )
    try:
        scratch_src_dir = scratch / "src"
        scratch_src_dir.mkdir()
        scratch_src = scratch_src_dir / "sysdiff.c"
        scratch_makefile = scratch / "Makefile"
        scratch_src.write_text(original_text, encoding="utf-8")
        scratch_makefile.write_text(
            (ROOT / "Makefile").read_text(encoding="utf-8"), encoding="utf-8"
        )

        baseline_bin = scratch / "sysdiff-baseline"
        _compile_sysdiff(scratch_src, baseline_bin)
        _assert_mixed_case_bytewise_order(baseline_bin, scratch / "baseline-work")

        mutant_text = scratch_src.read_text(encoding="utf-8")
        assert COMPARE_ENTRIES_STRCMP in mutant_text
        if "#include <strings.h>" not in mutant_text:
            mutant_text = mutant_text.replace(
                "#include <string.h>\n",
                "#include <string.h>\n#include <strings.h>\n",
                1,
            )
        mutant_text = mutant_text.replace(
            COMPARE_ENTRIES_STRCMP, COMPARE_ENTRIES_STRCASECMP, 1
        )
        assert COMPARE_ENTRIES_STRCASECMP in mutant_text
        scratch_src.write_text(mutant_text, encoding="utf-8")

        # Governed workspace must stay on strcmp while the scratch copy is mutated.
        assert SRC.read_text(encoding="utf-8") == original_text
        assert COMPARE_ENTRIES_STRCMP in SRC.read_text(encoding="utf-8")

        mutant_bin = scratch / "sysdiff-mutant"
        _compile_sysdiff(scratch_src, mutant_bin)

        before = write_snapshot(
            scratch / "mutant-before.snapshot", "same.keep=stable\n"
        )
        after_reversed = write_snapshot(
            scratch / "mutant-after-reversed.snapshot",
            "same.keep=stable\n" + MIXED_CASE_AFTER_REVERSED,
        )
        mutant_result = run_sysdiff(
            mutant_bin, "compare", before, after_reversed
        )
        assert mutant_result.returncode == 1
        assert mutant_result.stdout != MIXED_CASE_BYTEWISE_EXPECTED, (
            "strcasecmp mutant must not satisfy RC-001 bytewise golden; "
            f"got {mutant_result.stdout!r}"
        )
    finally:
        subprocess.run(["rm", "-rf", str(scratch)], check=False)
        assert SRC.read_text(encoding="utf-8") == original_text


@pytest.mark.parametrize(
    ("content", "stderr_fragment"),
    [
        ("valid.key=value\nmissing separator\n", "missing '=' separator"),
        ("=value\n", "empty key"),
        ("bad key=value\n", "invalid key syntax"),
        ("nodot=value\n", "invalid key syntax"),
        ("/starts.with.slash=value\n", "invalid key syntax"),
        ("ends.with.dot.=value\n", "invalid key syntax"),
        ("path..traversal=value\n", "invalid key syntax"),
        ("dup.key=first\ndup.key=second\n", "duplicate key"),
    ],
)
def test_malformed_before_snapshot_fails_without_stdout(
    sysdiff_bin, tmp_path, content, stderr_fragment
):
    before = write_snapshot(tmp_path / "bad.snapshot", content)
    after = write_snapshot(tmp_path / "after.snapshot", "valid.key=value\n")

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 2
    assert result.stdout == ""
    assert str(before) in result.stderr
    assert stderr_fragment in result.stderr


def test_malformed_after_snapshot_fails_without_partial_diff(sysdiff_bin, tmp_path):
    before = write_snapshot(tmp_path / "before.snapshot", "a.key=old\n")
    after = write_snapshot(tmp_path / "after.snapshot", "a.key=new\nbad line\n")

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 2
    assert result.stdout == ""
    assert str(after) in result.stderr
    assert "missing '=' separator" in result.stderr


def test_embedded_nul_is_rejected(sysdiff_bin, tmp_path):
    before = tmp_path / "nul.snapshot"
    before.write_bytes(b"valid.key=value\nbad.key=before\0after\n")
    after = write_snapshot(tmp_path / "after.snapshot", "valid.key=value\n")

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 2
    assert result.stdout == ""
    assert str(before) in result.stderr
    assert "embedded NUL byte" in result.stderr


def test_usage_file_and_directory_errors_keep_stdout_empty(sysdiff_bin, tmp_path):
    valid = write_snapshot(tmp_path / "valid.snapshot", "valid.key=value\n")
    missing = tmp_path / "missing.snapshot"
    directory = tmp_path / "snapshots"
    directory.mkdir()

    missing_arg = run_sysdiff(sysdiff_bin, "compare", valid)
    assert missing_arg.returncode == 2
    assert missing_arg.stdout == ""
    assert "compare requires" in missing_arg.stderr

    missing_file = run_sysdiff(sysdiff_bin, "compare", valid, missing)
    assert missing_file.returncode == 2
    assert missing_file.stdout == ""
    assert str(missing) in missing_file.stderr

    directory_file = run_sysdiff(sysdiff_bin, "compare", valid, directory)
    assert directory_file.returncode == 2
    assert directory_file.stdout == ""
    assert str(directory) in directory_file.stderr


def test_file_keys_are_compared_as_data(sysdiff_bin, tmp_path):
    before = write_snapshot(
        tmp_path / "before.snapshot",
        "file./path/that/should/not/be/opened.sha256=old\n",
    )
    after = write_snapshot(
        tmp_path / "after.snapshot",
        "file./path/that/should/not/be/opened.sha256=new\n",
    )

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 1
    assert result.stderr == ""
    assert result.stdout == (
        "~ file./path/that/should/not/be/opened.sha256: old -> new\n"
    )


@pytest.mark.parametrize(
    ("raw_value", "escaped_value"),
    [
        (b"\x1b", r"\x1B"),
        (b"\t", r"\x09"),
        (b"\rX", r"\x0DX"),
        (b"\\", r"\\"),
        (b"\x7f", r"\x7F"),
        (b"\xc3\xa9", r"\xC3\xA9"),
        (b"a\x1b\\b\t\rc\x7f\xff", r"a\x1B\\b\x09\x0Dc\x7F\xFF"),
    ],
)
def test_diff_values_are_safely_escaped(
    sysdiff_bin, tmp_path, raw_value, escaped_value
):
    before = write_snapshot_bytes(tmp_path / "before.snapshot", b"a.key=safe\n")
    after = write_snapshot_bytes(
        tmp_path / "after.snapshot", b"a.key=" + raw_value + b"\n"
    )

    result = run_sysdiff_bytes(sysdiff_bin, "compare", before, after)

    expected = f"~ a.key: safe -> {escaped_value}\n".encode("ascii")
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert_no_raw_unsafe_bytes(result.stdout)
    assert raw_value not in result.stdout or raw_value == b"\\"


def test_added_and_removed_values_are_safely_escaped(sysdiff_bin, tmp_path):
    before = write_snapshot_bytes(
        tmp_path / "before.snapshot", b"gone.key=old\x1b\t\r\\\x7f\xff\n"
    )
    after = write_snapshot_bytes(
        tmp_path / "after.snapshot", b"new.key=new\x1b\t\r\\\x7f\xff\n"
    )

    result = run_sysdiff_bytes(sysdiff_bin, "compare", before, after)

    expected = (
        b"- gone.key=old\\x1B\\x09\\x0D\\\\\\x7F\\xFF\n"
        b"+ new.key=new\\x1B\\x09\\x0D\\\\\\x7F\\xFF\n"
    )
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert_no_raw_unsafe_bytes(result.stdout)
    assert b"\x1b" not in result.stdout
    assert b"\t" not in result.stdout
    assert b"\r" not in result.stdout
    assert b"\x7f" not in result.stdout
    assert b"\xff" not in result.stdout


def test_opaque_comparison_ignores_display_escaping(sysdiff_bin, tmp_path):
    snapshot = write_snapshot_bytes(
        tmp_path / "same.snapshot", b"a.key=has\\backslash and\x09tab\n"
    )

    result = run_sysdiff_bytes(sysdiff_bin, "compare", snapshot, snapshot)

    assert result.returncode == 0
    assert result.stdout == b"no changes\n"
    assert result.stderr == b""


def test_unknown_command_with_esc_is_safely_escaped(sysdiff_bin):
    result = run_sysdiff_bytes(sysdiff_bin, "bad\x1bcmd")

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"unknown command: bad\\x1Bcmd" in result.stderr
    assert b"\x1b" not in result.stderr
    assert_no_raw_unsafe_bytes(result.stderr)


def test_path_with_esc_is_safely_escaped_in_diagnostics(sysdiff_bin, tmp_path):
    valid = write_snapshot(tmp_path / "valid.snapshot", "valid.key=value\n")
    missing = tmp_path / "miss\x1bing.snapshot"

    result = run_sysdiff_bytes(sysdiff_bin, "compare", valid, missing)

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"miss\\x1Bing.snapshot" in result.stderr
    assert b"\x1b" not in result.stderr
    assert_no_raw_unsafe_bytes(result.stderr)


def test_path_with_non_ascii_ff_is_safely_escaped(sysdiff_bin, tmp_path):
    valid = write_snapshot(tmp_path / "valid.snapshot", "valid.key=value\n")
    # Build a path whose filesystem name contains raw 0xFF via surrogateescape.
    missing_name = os.fsdecode(b"miss\xffing.snapshot")
    missing = tmp_path / missing_name

    result = run_sysdiff_bytes(sysdiff_bin, "compare", valid, missing)

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"miss\\xFFing.snapshot" in result.stderr
    assert b"\xff" not in result.stderr
    assert_no_raw_unsafe_bytes(result.stderr)


def run_with_closed_stdout_pipe(binary, *args):
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    cmd, vg_log = _valgrind_command([str(binary), *map(str, args)])
    proc = subprocess.Popen(
        cmd,
        stdout=write_fd,
        stderr=subprocess.PIPE,
    )
    os.close(write_fd)
    _, stderr = proc.communicate()
    _finish_valgrind(types.SimpleNamespace(returncode=proc.returncode), vg_log)
    return proc.returncode, stderr


def test_closed_stdout_pipe_on_help_returns_epipe(sysdiff_bin):
    status, stderr = run_with_closed_stdout_pipe(sysdiff_bin, "--help")

    assert status == 2
    assert status > 0
    assert b"stdout write error:" in stderr
    assert EPIPE_MESSAGE in stderr


def test_closed_stdout_pipe_on_changed_compare_returns_epipe(sysdiff_bin, tmp_path):
    before = write_snapshot(tmp_path / "before.snapshot", "a.key=old\n")
    after = write_snapshot(tmp_path / "after.snapshot", "a.key=new\n")
    status, stderr = run_with_closed_stdout_pipe(
        sysdiff_bin, "compare", before, after
    )

    assert status == 2
    assert status > 0
    assert b"stdout write error:" in stderr
    assert EPIPE_MESSAGE in stderr


def test_snapshot_byte_limit_boundary(sysdiff_bin, tmp_path):
    max_bytes = 16777216
    at_limit = tmp_path / "bytes-at-limit.snapshot"
    over_limit = tmp_path / "bytes-over-limit.snapshot"
    comments_over = tmp_path / "comments-over-limit.snapshot"
    nul_over = tmp_path / "nul-over-limit.snapshot"

    at_limit.write_bytes(b"#\n" * (max_bytes // 2))
    over_limit.write_bytes(b"#\n" * (max_bytes // 2) + b"\n")
    comments_over.write_bytes(b"\n" * max_bytes + b"#")
    nul_over.write_bytes(b"\n" * max_bytes + b"\0")

    at_result = run_sysdiff(sysdiff_bin, "compare", at_limit, at_limit)
    assert at_result.returncode == 0
    assert at_result.stdout == "no changes\n"
    assert at_result.stderr == ""

    over_result = run_sysdiff(sysdiff_bin, "compare", over_limit, at_limit)
    assert over_result.returncode == 2
    assert over_result.stdout == ""
    assert "snapshot byte limit exceeded" in over_result.stderr
    assert str(over_limit) in over_result.stderr

    comments_result = run_sysdiff(sysdiff_bin, "compare", comments_over, at_limit)
    assert comments_result.returncode == 2
    assert comments_result.stdout == ""
    assert "snapshot byte limit exceeded" in comments_result.stderr
    assert str(comments_over) in comments_result.stderr

    nul_result = run_sysdiff_bytes(sysdiff_bin, "compare", nul_over, at_limit)
    assert nul_result.returncode == 2
    assert nul_result.stdout == b""
    assert b"snapshot byte limit exceeded" in nul_result.stderr
    assert b"embedded NUL" not in nul_result.stderr
    assert str(nul_over).encode() in nul_result.stderr


DIST_ARCHIVE_NAME = "sysdiff-source.tar.gz"
DIST_CHECKSUM_NAME = "sysdiff-source.tar.gz.sha256"
DIST_EPOCH = "946684800"
REQUIRED_ARCHIVE_MEMBERS = (
    "sysdiff/Makefile",
    "sysdiff/LICENSE",
    "sysdiff/README.md",
    "sysdiff/CHANGELOG.md",
    "sysdiff/src/sysdiff.c",
    "sysdiff/man/sysdiff.1",
    "sysdiff/tests/test_sysdiff.sh",
    "sysdiff/tests/test_sysdiff.py",
    "sysdiff/tests/test_sysdiff_fixture.sh",
    "sysdiff/scripts/check_tools.py",
    "sysdiff/docs/sysdiff-snapshot-format-and-scope.md",
)
EXCLUDED_ARCHIVE_FRAGMENTS = (
    ".git/",
    "code-reviews/",
    "playbooks/",
    "plans/",
    "dist/",
    ".pytest_cache",
    "__pycache__",
    ".agent-orch",
    "artifacts/",
)


def _git_show_toplevel(path: Path):
    """Return the enclosing git work-tree root for path, or None."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    toplevel = result.stdout.strip()
    if not toplevel:
        return None
    return Path(toplevel).resolve()


def _path_is_git_worktree_root(path: Path) -> bool:
    """True only when path itself is the git work-tree root.

    Nested disposable trees under an enclosing repository still report
    ``git rev-parse --is-inside-work-tree=true`` against the parent. Those
    trees have no tracked release pathspecs at their own root, so ``make dist``
    must not run there. Quality-floor clean copies often land under Agent-Orch
    scratch ``TMPDIR`` inside the governed workspace and hit this case.
    """

    toplevel = _git_show_toplevel(path)
    return toplevel is not None and toplevel == path.resolve()


def _in_git_worktree():
    return _path_is_git_worktree_root(ROOT)


def _require_git_worktree():
    if not _in_git_worktree():
        pytest.skip(
            "make dist regression coverage requires the suite root to be a "
            "git work-tree root (nested copies under an enclosing repository skip)"
        )


def test_dist_git_root_detection_rejects_nested_enclosing_worktree_copy():
    """Nested paths under a parent git repo must not look like dist roots.

    Regression for the clean-checkout quality floor: a tar copy under workspace
    scratch TMPDIR is inside the parent work tree, so a bare
    ``--is-inside-work-tree`` check is a false positive and used to drive
    ``make dist`` into ``found no tracked release files``.
    """

    parent_toplevel = _git_show_toplevel(ROOT)
    if parent_toplevel is None:
        pytest.skip("requires an enclosing git work tree to exercise nested detection")

    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert inside.returncode == 0
    assert inside.stdout.strip() == "true"

    if not _path_is_git_worktree_root(ROOT):
        # Disposable quality-floor / scratch copy: ROOT is nested already.
        assert parent_toplevel != ROOT.resolve()
        assert not _in_git_worktree()
        return

    nested = Path(
        tempfile.mkdtemp(prefix="sysdiff-nested-dist-root.", dir=str(ROOT))
    )
    try:
        (nested / "Makefile").write_text("# decoy\n", encoding="utf-8")
        nested_inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(nested),
            capture_output=True,
            text=True,
            check=False,
        )
        assert nested_inside.returncode == 0
        assert nested_inside.stdout.strip() == "true"
        assert _git_show_toplevel(nested) == ROOT.resolve()
        assert not _path_is_git_worktree_root(nested)
    finally:
        subprocess.run(["rm", "-rf", str(nested)], check=False)


def _run_make(*args, check=True):
    return subprocess.run(
        ["make", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _dist_paths():
    dist_dir = ROOT / "dist"
    return dist_dir / DIST_ARCHIVE_NAME, dist_dir / DIST_CHECKSUM_NAME


def _build_dist(epoch=DIST_EPOCH):
    _require_git_worktree()
    result = _run_make(f"SOURCE_DATE_EPOCH={epoch}", "dist")
    archive, checksum = _dist_paths()
    assert archive.is_file(), result.stderr
    assert checksum.is_file(), result.stderr
    return archive, checksum, result


def _archive_member_names(archive_path):
    listing = subprocess.run(
        ["tar", "-tzf", str(archive_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in listing.stdout.splitlines() if line]


def _gzip_mtime(archive_path):
    with archive_path.open("rb") as handle:
        header = handle.read(10)
    assert len(header) >= 10
    assert header[0:2] == b"\x1f\x8b"
    return int.from_bytes(header[4:8], "little")


def test_dist_is_reproducible_for_fixed_epoch():
    archive, checksum, _ = _build_dist()
    first_archive = archive.read_bytes()
    first_checksum = checksum.read_text(encoding="utf-8")
    first_digest = first_checksum.split()[0]

    archive, checksum, _ = _build_dist()
    assert archive.read_bytes() == first_archive
    assert checksum.read_text(encoding="utf-8") == first_checksum
    assert checksum.read_text(encoding="utf-8").split()[0] == first_digest


def test_dist_checksum_matches_archive_basename_only():
    archive, checksum, _ = _build_dist()
    digest_line = checksum.read_text(encoding="utf-8").strip()
    assert digest_line.endswith(f"  {DIST_ARCHIVE_NAME}")
    assert "/" not in digest_line.split()[-1]
    expected = subprocess.run(
        ["sha256sum", str(archive)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[0]
    assert digest_line.split()[0] == expected
    check = subprocess.run(
        ["sha256sum", "-c", DIST_CHECKSUM_NAME],
        cwd=str(ROOT / "dist"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr


def test_dist_archive_layout_and_normalized_metadata():
    archive, _, _ = _build_dist()
    assert _gzip_mtime(archive) == 0

    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        names = [member.name for member in members]
        assert names == sorted(names)
        for member in members:
            assert not member.name.startswith("/")
            assert ".." not in Path(member.name).parts
            assert member.name == "sysdiff" or member.name.startswith("sysdiff/")
            assert member.uid == 0
            assert member.gid == 0
            assert member.uname in ("", "root")
            assert member.gname in ("", "root")
            assert member.mtime == int(DIST_EPOCH)
            if member.isdir():
                assert member.mode & 0o777 == 0o755
            elif member.isfile():
                if member.name.endswith(".sh"):
                    assert member.mode & 0o777 == 0o755
                else:
                    assert member.mode & 0o777 == 0o644

    name_set = set(_archive_member_names(archive))
    for required in REQUIRED_ARCHIVE_MEMBERS:
        assert required in name_set

    joined = "\n".join(name_set)
    for fragment in EXCLUDED_ARCHIVE_FRAGMENTS:
        assert fragment not in joined
    assert "sysdiff/code-reviews" not in joined
    assert "sysdiff/playbooks" not in joined
    assert "sysdiff/plans" not in joined


def test_dist_excludes_untracked_files():
    _require_git_worktree()
    decoy = ROOT / "UNTRACKED_DIST_DECOY.txt"
    decoy.write_text("untracked decoy must not enter the archive\n", encoding="utf-8")
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", str(decoy.relative_to(ROOT))],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        assert status.stdout.strip().startswith("??"), status.stdout
        archive, _, _ = _build_dist()
        names = _archive_member_names(archive)
        joined = "\n".join(names)
        assert "UNTRACKED_DIST_DECOY.txt" not in joined
        assert decoy.name not in {Path(name).name for name in names}
    finally:
        decoy.unlink(missing_ok=True)


def test_dist_extracts_builds_and_tests_outside_workspace():
    archive, _, _ = _build_dist()
    extract_root = Path(
        tempfile.mkdtemp(prefix="sysdiff-dist-extract.", dir="/tmp")
    )
    try:
        assert ROOT not in extract_root.parents and extract_root != ROOT
        subprocess.run(
            ["tar", "-xzf", str(archive), "-C", str(extract_root)],
            check=True,
        )
        sourcedir = extract_root / "sysdiff"
        assert (sourcedir / "Makefile").is_file()
        assert (sourcedir / "src" / "sysdiff.c").is_file()
        assert (sourcedir / "tests" / "test_sysdiff.sh").is_file()
        # Nested extract must not inherit workspace/memory-gate binary routing;
        # otherwise test-shell packaging compares against the wrong ORDINARY_BIN
        # and silently skips DESTDIR install/reinstall/uninstall coverage.
        nested_env = os.environ.copy()
        nested_env.pop("SYSDIFF_BIN", None)
        nested_env.pop("SYSDIFF_UNDER_VALGRIND", None)
        build = subprocess.run(
            ["make", "-C", str(sourcedir)],
            env=nested_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert build.returncode == 0, build.stderr
        binary = sourcedir / "build" / "sysdiff"
        assert binary.is_file()
        version = run_sysdiff(binary, "--version")
        assert version.returncode == 0
        assert version.stdout == "sysdiff 0.1.0\n"
        tested = subprocess.run(
            ["make", "-C", str(sourcedir), "test"],
            env=nested_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert tested.returncode == 0, tested.stderr + tested.stdout
    finally:
        subprocess.run(["rm", "-rf", str(extract_root)], check=False)


def test_dist_rejects_malformed_source_date_epoch():
    _require_git_worktree()
    for bad_epoch in ("", "abc", "12.5", "-1", "1e6", "946684800 "):
        result = _run_make(f"SOURCE_DATE_EPOCH={bad_epoch}", "dist", check=False)
        assert result.returncode != 0, bad_epoch
        assert "SOURCE_DATE_EPOCH" in result.stderr
