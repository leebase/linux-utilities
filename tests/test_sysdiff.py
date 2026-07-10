import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sysdiff.c"


@pytest.fixture(scope="session")
def sysdiff_bin(tmp_path_factory):
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


def run_sysdiff(binary, *args):
    return subprocess.run(
        [str(binary), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def write_snapshot(path, text):
    path.write_text(text, encoding="utf-8")
    return path


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
