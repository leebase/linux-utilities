"""Regression for governed run 9add44496178 sysdiff delimiter shielding.

Format-1 changed lines use a fixed `` -> `` separator between old and new
values. Before this repair, printable values may contain that same four-byte
sequence, so ``~ demo.key: a -> b -> c\\n`` is ambiguous. The contract requires
shielding every raw ``0x20 0x2D 0x3E`` occurrence by rendering the greater-than
byte as ``\\x3E``, leaving exactly one literal separator on each changed line.

See ``docs/governed-run-9add44496178-contract.md``.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sysdiff.c"

SEPARATOR = b" -> "
ARROW_SEQ = b" ->"  # space, hyphen, greater-than (three bytes)


@pytest.fixture(scope="session")
def sysdiff_bin(tmp_path_factory):
    env_bin = os.environ.get("SYSDIFF_BIN")
    if env_bin:
        binary = Path(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"SYSDIFF_BIN is not an executable file: {env_bin}")
        return binary

    build_dir = tmp_path_factory.mktemp("build-9add44496178")
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
    if os.environ.get("SYSDIFF_UNDER_VALGRIND") != "1":
        return cmd, None

    fd, vg_log = tempfile.mkstemp(prefix="sysdiff-valgrind-9add.")
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
                detail = handle.read().decode("utf-8", errors="replace")
            raise AssertionError(
                f"valgrind reported errors (status {result.returncode}):\n{detail}"
            )
    finally:
        os.unlink(vg_log)
    return result


def run_sysdiff_bytes(binary, *args):
    cmd, vg_log = _valgrind_command([str(binary), *map(str, args)])
    result = subprocess.run(cmd, capture_output=True, check=False)
    return _finish_valgrind(result, vg_log)


def write_snapshot_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def assert_no_raw_unsafe_bytes(data: bytes) -> None:
    for index, byte in enumerate(data):
        if byte == 0x0A:
            continue
        if byte < 0x20 or byte > 0x7E:
            raise AssertionError(
                f"unsafe raw byte 0x{byte:02X} at offset {index} in output"
            )


def render_value(raw: bytes) -> bytes:
    """Apply the contract value-rendering rule, including delimiter shielding."""

    out = bytearray()
    index = 0
    while index < len(raw):
        if raw.startswith(ARROW_SEQ, index):
            out.extend(b" -\\x3E")
            index += 3
            continue
        byte = raw[index]
        if byte == ord("\\"):
            out.extend(b"\\\\")
        elif 0x20 <= byte <= 0x7E:
            out.append(byte)
        else:
            out.extend(f"\\x{byte:02X}".encode("ascii"))
        index += 1
    return bytes(out)


def decode_rendered(text: bytes) -> bytes:
    """Undo ``\\\\`` and uppercase ``\\xNN`` escapes from a rendered value."""

    out = bytearray()
    index = 0
    while index < len(text):
        if text[index] != ord("\\"):
            out.append(text[index])
            index += 1
            continue
        if index + 1 < len(text) and text[index + 1] == ord("\\"):
            out.append(ord("\\"))
            index += 2
            continue
        if (
            index + 3 < len(text)
            and text[index + 1] == ord("x")
            and re.fullmatch(rb"[0-9A-F]{2}", text[index + 2 : index + 4])
        ):
            out.append(int(text[index + 2 : index + 4], 16))
            index += 4
            continue
        raise AssertionError(f"undecodable escape at offset {index} in {text!r}")
    return bytes(out)


def split_changed_line(line: bytes) -> tuple[bytes, bytes, bytes]:
    """Split a changed record at its sole literal `` -> `` separator."""

    assert line.startswith(b"~ "), line
    assert line.endswith(b"\n"), line
    body = line[2:-1]
    key, sep, rest = body.partition(b": ")
    assert sep == b": ", line
    assert rest.count(SEPARATOR) == 1, line
    old_rendered, _, new_rendered = rest.partition(SEPARATOR)
    return key, decode_rendered(old_rendered), decode_rendered(new_rendered)


def changed_line(key: bytes, old: bytes, new: bytes) -> bytes:
    return b"~ " + key + b": " + render_value(old) + SEPARATOR + render_value(new) + b"\n"


def added_line(key: bytes, value: bytes) -> bytes:
    return b"+ " + key + b"=" + render_value(value) + b"\n"


def removed_line(key: bytes, value: bytes) -> bytes:
    return b"- " + key + b"=" + render_value(value) + b"\n"


def compare_pair(binary, tmp_path, before_body: bytes, after_body: bytes):
    before = write_snapshot_bytes(tmp_path / "before.snapshot", before_body)
    after = write_snapshot_bytes(tmp_path / "after.snapshot", after_body)
    return run_sysdiff_bytes(binary, "compare", before, after)


def test_colliding_pairs_produce_distinct_shielded_lines(sysdiff_bin, tmp_path):
    """Acceptance: formerly identical ambiguous lines become distinct oracles."""

    left = compare_pair(
        sysdiff_bin, tmp_path / "left", b"demo.key=a\n", b"demo.key=b -> c\n"
    )
    right = compare_pair(
        sysdiff_bin, tmp_path / "right", b"demo.key=a -> b\n", b"demo.key=c\n"
    )

    expected_left = b"~ demo.key: a -> b -\\x3E c\n"
    expected_right = b"~ demo.key: a -\\x3E b -> c\n"

    assert left.returncode == 1
    assert right.returncode == 1
    assert left.stderr == b""
    assert right.stderr == b""
    assert left.stdout == expected_left
    assert right.stdout == expected_right
    assert left.stdout != right.stdout
    assert left.stdout.count(SEPARATOR) == 1
    assert right.stdout.count(SEPARATOR) == 1
    assert_no_raw_unsafe_bytes(left.stdout)
    assert_no_raw_unsafe_bytes(right.stdout)

    key, old, new = split_changed_line(left.stdout)
    assert key == b"demo.key"
    assert old == b"a"
    assert new == b"b -> c"

    key, old, new = split_changed_line(right.stdout)
    assert key == b"demo.key"
    assert old == b"a -> b"
    assert new == b"c"


def test_arrow_sequence_in_both_old_and_new(sysdiff_bin, tmp_path):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"demo.key=a -> b\n",
        b"demo.key=c -> d\n",
    )
    expected = b"~ demo.key: a -\\x3E b -> c -\\x3E d\n"
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert result.stdout.count(SEPARATOR) == 1
    key, old, new = split_changed_line(result.stdout)
    assert (key, old, new) == (b"demo.key", b"a -> b", b"c -> d")


def test_multiple_arrow_occurrences_are_each_shielded(sysdiff_bin, tmp_path):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"a.key=x -> y -> z\n",
        b"a.key=plain\n",
    )
    expected = b"~ a.key: x -\\x3E y -\\x3E z -> plain\n"
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert result.stdout.count(SEPARATOR) == 1
    _, old, new = split_changed_line(result.stdout)
    assert old == b"x -> y -> z"
    assert new == b"plain"


def test_old_value_ending_exactly_in_arrow_sequence(sysdiff_bin, tmp_path):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"a.key=ends ->\n",
        b"a.key=new\n",
    )
    expected = b"~ a.key: ends -\\x3E -> new\n"
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert result.stdout.count(SEPARATOR) == 1
    _, old, new = split_changed_line(result.stdout)
    assert old == b"ends ->"
    assert new == b"new"


def test_added_and_removed_values_shield_arrow_sequence(sysdiff_bin, tmp_path):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"gone.key=left -> right\n",
        b"new.key=left -> right\n",
    )
    expected = (
        b"- gone.key=left -\\x3E right\n"
        b"+ new.key=left -\\x3E right\n"
    )
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert SEPARATOR not in result.stdout
    assert_no_raw_unsafe_bytes(result.stdout)


def test_unspaced_arrow_remains_literal(sysdiff_bin, tmp_path):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"a.key=left->right\n",
        b"a.key=other\n",
    )
    expected = b"~ a.key: left->right -> other\n"
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert result.stdout.count(SEPARATOR) == 1
    _, old, new = split_changed_line(result.stdout)
    assert old == b"left->right"
    assert new == b"other"


def test_raw_backslash_x3e_spelling_doubles_backslash(sysdiff_bin, tmp_path):
    """Raw bytes backslash-x-3-E must render as ``\\\\x3E``, not as shielded ``>``."""

    raw_spelling = b"has\\x3E"
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"a.key=" + raw_spelling + b"\n",
        b"a.key=other\n",
    )
    expected = b"~ a.key: has\\\\x3E -> other\n"
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    _, old, new = split_changed_line(result.stdout)
    assert old == raw_spelling
    assert new == b"other"


def test_empty_values_keep_single_separator(sysdiff_bin, tmp_path):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"flip.empty=\nflip.full=text\n",
        b"flip.empty=text\nflip.full=\n",
    )
    expected = b"~ flip.empty:  -> text\n" b"~ flip.full: text -> \n"
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    for line in result.stdout.splitlines(keepends=True):
        assert line.count(SEPARATOR) == 1
        _, old, new = split_changed_line(line)
        assert isinstance(old, bytes)
        assert isinstance(new, bytes)


def test_identical_snapshot_with_arrow_sequence_is_no_changes(sysdiff_bin, tmp_path):
    snapshot = write_snapshot_bytes(
        tmp_path / "same.snapshot", b"demo.key=left -> right\n"
    )
    result = run_sysdiff_bytes(sysdiff_bin, "compare", snapshot, snapshot)
    assert result.returncode == 0
    assert result.stdout == b"no changes\n"
    assert result.stderr == b""


def test_independent_decoder_round_trips_hostile_values(sysdiff_bin, tmp_path):
    old = b"a\x1b -> b\\x3E\t -> \r\x7f\xff"
    new = b" -> tail -> \xc3\xa9"
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"k.v=" + old + b"\n",
        b"k.v=" + new + b"\n",
    )
    expected = changed_line(b"k.v", old, new)
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert_no_raw_unsafe_bytes(result.stdout)
    assert result.stdout.count(SEPARATOR) == 1
    key, decoded_old, decoded_new = split_changed_line(result.stdout)
    assert key == b"k.v"
    assert decoded_old == old
    assert decoded_new == new


def test_ordinary_golden_values_remain_byte_compatible(sysdiff_bin, tmp_path):
    """Values without the raw arrow sequence keep the historical surface."""

    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        (
            b"file./etc/ssh/sshd_config.sha256=old=hash\n"
            b"package.openssh-server.version=1:9.2p1-2+deb12u3\n"
            b"removed.key=gone\n"
            b"service.ssh.enabled=old # enabled=true\n"
            b"z.changed=old value\n"
        ),
        (
            b"added.key=new value\n"
            b"file./etc/ssh/sshd_config.sha256=new=hash\n"
            b"package.openssh-server.version=1:9.2p1-2+deb12u4\n"
            b"service.ssh.enabled=new # enabled=false\n"
            b"z.changed=new value\n"
        ),
    )
    expected = (
        b"+ added.key=new value\n"
        b"~ file./etc/ssh/sshd_config.sha256: old=hash -> new=hash\n"
        b"~ package.openssh-server.version: 1:9.2p1-2+deb12u3 -> "
        b"1:9.2p1-2+deb12u4\n"
        b"- removed.key=gone\n"
        b"~ service.ssh.enabled: old # enabled=true -> new # enabled=false\n"
        b"~ z.changed: old value -> new value\n"
    )
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""


def test_key_order_remains_bytewise_and_input_order_independent(sysdiff_bin, tmp_path):
    before_a = write_snapshot_bytes(
        tmp_path / "before-a", b"z.key=old\nb.key=a -> b\na.key=old\n"
    )
    after_a = write_snapshot_bytes(
        tmp_path / "after-a", b"c.key=b -> c\na.key=new\nb.key=c\n"
    )
    before_b = write_snapshot_bytes(
        tmp_path / "before-b", b"a.key=old\nz.key=old\nb.key=a -> b\n"
    )
    after_b = write_snapshot_bytes(
        tmp_path / "after-b", b"b.key=c\nc.key=b -> c\na.key=new\n"
    )

    first = run_sysdiff_bytes(sysdiff_bin, "compare", before_a, after_a)
    second = run_sysdiff_bytes(sysdiff_bin, "compare", before_b, after_b)
    expected = (
        b"~ a.key: old -> new\n"
        b"~ b.key: a -\\x3E b -> c\n"
        b"+ c.key=b -\\x3E c\n"
        b"- z.key=old\n"
    )
    assert first.returncode == 1
    assert second.returncode == 1
    assert first.stdout == second.stdout == expected
    assert first.stderr == second.stderr == b""


def test_comparison_is_raw_not_display_based(sysdiff_bin, tmp_path):
    """Shielding is presentation-only; equality still uses raw snapshot bytes."""

    # Distinct raw bytes that are easy to confuse after shielding: the three-byte
    # arrow sequence versus a literal spelling of the shielded form.
    raw_arrow = b" ->"
    raw_spelling = b" -\\x3E"
    assert render_value(raw_arrow) == b" -\\x3E"
    assert render_value(raw_spelling) == b" -\\\\x3E"

    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"a.key=" + raw_arrow + b"\n",
        b"a.key=" + raw_spelling + b"\n",
    )
    expected = changed_line(b"a.key", raw_arrow, raw_spelling)
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    _, old, new = split_changed_line(result.stdout)
    assert old == raw_arrow
    assert new == raw_spelling


@pytest.mark.parametrize(
    "raw_value",
    [
        b"\x1b",
        b"\t",
        b"\rX",
        b"\\",
        b"\x7f",
        b"\xc3\xa9",
        b"a\x1b\\b\t\rc\x7f\xff",
        b"safe -> unsafe\x1b",
    ],
)
def test_terminal_unsafe_bytes_remain_escaped_with_shielding(
    sysdiff_bin, tmp_path, raw_value
):
    result = compare_pair(
        sysdiff_bin,
        tmp_path,
        b"a.key=safe\n",
        b"a.key=" + raw_value + b"\n",
    )
    expected = changed_line(b"a.key", b"safe", raw_value)
    assert result.returncode == 1
    assert result.stdout == expected
    assert result.stderr == b""
    assert_no_raw_unsafe_bytes(result.stdout)
    assert result.stdout.count(SEPARATOR) == 1
    _, old, new = split_changed_line(result.stdout)
    assert old == b"safe"
    assert new == raw_value


def test_validation_error_keeps_stdout_empty_and_status_two(sysdiff_bin, tmp_path):
    before = write_snapshot_bytes(tmp_path / "before.snapshot", b"a.key=old\n")
    after = write_snapshot_bytes(
        tmp_path / "after.snapshot", b"a.key=new\nbad line\n"
    )
    result = run_sysdiff_bytes(sysdiff_bin, "compare", before, after)
    assert result.returncode == 2
    assert result.stdout == b""
    assert b"missing '=' separator" in result.stderr


def test_render_helper_matches_contract_examples():
    assert render_value(b"left -> right") == b"left -\\x3E right"
    assert render_value(b"left->right") == b"left->right"
    assert render_value(b"\\x3E") == b"\\\\x3E"
    assert render_value(b"ends ->") == b"ends -\\x3E"
    assert changed_line(b"demo.key", b"a", b"b -> c") == (
        b"~ demo.key: a -> b -\\x3E c\n"
    )
    assert changed_line(b"demo.key", b"a -> b", b"c") == (
        b"~ demo.key: a -\\x3E b -> c\n"
    )
    assert added_line(b"k", b"a -> b") == b"+ k=a -\\x3E b\n"
    assert removed_line(b"k", b"a -> b") == b"- k=a -\\x3E b\n"
