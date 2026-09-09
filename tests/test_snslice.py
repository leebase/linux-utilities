"""Contract tests for snslice first vertical slice.

Contract authority: docs/snslice-first-slice-contract.md
Implementation plan: plans/snslice-first-slice-implementation-plan.md

Covers:
- AC-1: CLI Surface, Grammar, Arity, and Informational Options
- AC-2: Bounded-Memory Streaming and Resource Safety
- AC-3: NDJSON Line Boundary and Complete Record Chunking
- AC-4: CSV Quoted Records Spanning Physical Lines (RFC 4180)
- AC-5: Deterministic Chunk Naming and Output Slicing
- AC-6: Chunk Collision Prevention and Atomic File Creation
- AC-7: Empty Input Stream Handling
- AC-8: Malformed Input and Unterminated Record Rejection
- AC-9: Chunk Write Failures and Operational I/O Safety
- AC-10: CLI Diagnostics and Hostile Byte Sanitization
- AC-11: Closed Hazard Taxonomy and Exit Status Integrity
- AC-12: Repository Build, Hardening, and Quality Floor Compatibility
- AC-13: User Journey Manifest Synchronization and Acceptance Check Traceability
"""

from __future__ import annotations

import atexit
import csv
import errno
import json
import os
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Generator, Sequence

import pytest

try:
    import jsonschema
except ImportError:
    jsonschema = None

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")
    USER_JOURNEYS_MANIFEST_SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["journeys", "command_allowlist"],
        "properties": {
            "journeys": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "authority": {
                            "enum": ["human", "mission", "author", "exploratory"]
                        },
                        "traces_to": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
            "command_allowlist": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
        },
    }

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "snslice.c"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SNSLICE_JOURNEYS_MANIFEST = ROOT / "journeys" / "snslice_user_journeys_manifest.json"

STATUS_OK = 0
STATUS_ERROR = 2

SNSLICE_IO_BUFFER_SIZE = 65536
SNSLICE_MAX_RECORD_BYTES = 16777216

CLOSED_HAZARD_TAXONOMY = {
    "USAGE_ERROR",
    "UNKNOWN_OPTION",
    "INVALID_LIMIT",
    "INVALID_FORMAT",
    "INPUT_NOT_FOUND",
    "INPUT_IS_DIRECTORY",
    "INPUT_READ_ERROR",
    "RECORD_LENGTH_LIMIT",
    "MALFORMED_NDJSON",
    "MALFORMED_CSV",
    "OUTPUT_DIR_ERROR",
    "OUTPUT_COLLISION",
    "CHUNK_OPEN_ERROR",
    "CHUNK_WRITE_ERROR",
    "OUT_OF_MEMORY",
    "BROKEN_PIPE",
}

DIAGNOSTIC_RE = re.compile(r"^snslice:\s+([A-Z_]+):\s*(.*)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Test Harness Compilation & Subprocess Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def snslice_bin() -> Path:
    """Resolve or compile snslice binary outside repository workspace.

    If SNSLICE_BIN is set in the environment, uses that binary.
    Otherwise, if src/snslice.c exists, compiles it to a temporary directory
    outside the workspace. If src/snslice.c does not exist yet, skips.
    """
    env_bin = os.environ.get("SNSLICE_BIN")
    if env_bin:
        binary = Path(env_bin).expanduser().resolve()
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"SNSLICE_BIN is not an executable file: {env_bin}")
        return binary

    if not SRC.is_file():
        pytest.skip(f"source {SRC} does not exist yet; skipping snslice compilation")

    build_dir = Path(tempfile.mkdtemp(prefix="snslice-test-build-", dir="/tmp"))
    resolved_build_dir = build_dir.resolve()
    resolved_root = ROOT.resolve()

    if resolved_build_dir == resolved_root or resolved_root in resolved_build_dir.parents:
        shutil.rmtree(build_dir, ignore_errors=True)
        pytest.fail(f"temporary build dir resolved inside workspace: {resolved_build_dir}")

    binary = build_dir / "snslice"
    cc = os.environ.get("CC", "gcc" if shutil.which("gcc") else "cc")
    cflags = os.environ.get("CFLAGS", "").split()
    cmd = [
        cc,
        "-std=c17",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-D_POSIX_C_SOURCE=200809L",
        "-D_FILE_OFFSET_BITS=64",
        "-O2",
        *cflags,
        "-o",
        str(binary),
        str(SRC),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        shutil.rmtree(build_dir, ignore_errors=True)
        pytest.fail(f"snslice compilation failed:\n{res.stderr}")

    atexit.register(lambda: shutil.rmtree(build_dir, ignore_errors=True))
    return binary


def run_snslice(
    binary: Path,
    args: Sequence[str],
    input_bytes: bytes | None = None,
    cwd: Path | None = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[bytes]:
    """Execute snslice with hermetic environment and captured output."""
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return subprocess.run(
        [str(binary), *args],
        input=input_bytes,
        capture_output=True,
        cwd=cwd or ROOT,
        env=env,
        timeout=timeout,
    )


def parse_diagnostic(stderr: bytes | str) -> tuple[str, str]:
    """Extract hazard code and details from formatted stderr."""
    text = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
    m = DIAGNOSTIC_RE.search(text)
    if not m:
        raise AssertionError(
            f"Expected stderr to match 'snslice: <HAZARD_CODE>: <details>', got:\n{text}"
        )
    hazard, details = m.group(1), m.group(2)
    assert hazard in CLOSED_HAZARD_TAXONOMY, f"Unknown hazard code: {hazard}"
    return hazard, details


def assert_stderr_sanitized(stderr: bytes) -> None:
    """Assert stderr contains only printable ASCII and escaped \\xHH sequences."""
    for b in stderr:
        assert b == 0x0A or (0x20 <= b <= 0x7E), (
            f"Unsanitized byte 0x{b:02X} found in stderr: {stderr!r}"
        )
    assert b"\x1b" not in stderr, "Raw ANSI escape byte 0x1B found in stderr"


# ---------------------------------------------------------------------------
# Suite 1: CLI Surface, Grammar, Arity, and Informational Options (AC-1)
# ---------------------------------------------------------------------------


def test_ac1_help_sole_argument(snslice_bin: Path) -> None:
    """AC-1: Sole-argument --help prints usage to stdout with exit status 0 and empty stderr."""
    res = run_snslice(snslice_bin, ["--help"])
    assert res.returncode == STATUS_OK
    assert b"Usage:" in res.stdout or b"snslice" in res.stdout
    assert res.stderr == b""


def test_ac1_version_sole_argument(snslice_bin: Path) -> None:
    """AC-1: Sole-argument --version prints 'snslice 0.1.0\\n' to stdout with exit status 0."""
    res = run_snslice(snslice_bin, ["--version"])
    assert res.returncode == STATUS_OK
    assert res.stdout == b"snslice 0.1.0\n"
    assert res.stderr == b""


@pytest.mark.parametrize(
    "extra_args",
    [
        ["-b", "1000"],
        ["--records", "5"],
        ["-f", "csv"],
        ["input.ndjson"],
        ["--out-dir", "/tmp"],
    ],
)
def test_ac1_help_combined_with_options_fails(
    snslice_bin: Path, extra_args: list[str]
) -> None:
    """AC-1: Combining --help with any other option or operand fails closed with USAGE_ERROR."""
    res = run_snslice(snslice_bin, ["--help", *extra_args])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"

    res_rev = run_snslice(snslice_bin, [*extra_args, "--help"])
    assert res_rev.returncode == STATUS_ERROR
    hazard_rev, _ = parse_diagnostic(res_rev.stderr)
    assert hazard_rev == "USAGE_ERROR"


@pytest.mark.parametrize(
    "extra_args",
    [
        ["-b", "1000"],
        ["--records", "5"],
        ["-f", "csv"],
        ["input.ndjson"],
        ["--prefix", "part_"],
    ],
)
def test_ac1_version_combined_with_options_fails(
    snslice_bin: Path, extra_args: list[str]
) -> None:
    """AC-1: Combining --version with any other option or operand fails closed with USAGE_ERROR."""
    res = run_snslice(snslice_bin, ["--version", *extra_args])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"

    res_rev = run_snslice(snslice_bin, [*extra_args, "--version"])
    assert res_rev.returncode == STATUS_ERROR
    hazard_rev, _ = parse_diagnostic(res_rev.stderr)
    assert hazard_rev == "USAGE_ERROR"


def test_ac1_missing_limits_fails(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-1: Omitting both --bytes and --records limits fails closed with USAGE_ERROR."""
    dummy_input = tmp_path / "dummy.ndjson"
    dummy_input.write_text('{"key":"value"}\n')

    res = run_snslice(snslice_bin, [str(dummy_input)])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"


def test_ac1_multiple_positional_operands_fails(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-1: Supplying more than one positional operand triggers an arity violation."""
    file1 = tmp_path / "f1.ndjson"
    file2 = tmp_path / "f2.ndjson"
    file1.write_text('{"a":1}\n')
    file2.write_text('{"b":2}\n')

    res = run_snslice(snslice_bin, ["-b", "1000", str(file1), str(file2)])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"


def test_ac1_option_terminator(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-1: Double-dash -- terminates option processing; operand with dash is treated as path."""
    weird_file = tmp_path / "-weird-input.ndjson"
    weird_file.write_text('{"msg":"hello"}\n')
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(out_dir), "--", str(weird_file)],
    )
    assert res.returncode == STATUS_OK
    assert (out_dir / "chunk_00001.ndjson").is_file()


def test_ac1_unknown_option(snslice_bin: Path) -> None:
    """AC-1: Unrecognized option flags fail closed with UNKNOWN_OPTION."""
    res = run_snslice(snslice_bin, ["--unknown-flag-xyz", "-b", "1000"])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "UNKNOWN_OPTION"


def test_ac1_invalid_format(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-1: Supplying invalid format value fails closed with INVALID_FORMAT."""
    res = run_snslice(snslice_bin, ["-f", "parquet", "-b", "1000"])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "INVALID_FORMAT"


@pytest.mark.parametrize(
    ("flag", "bad_val"),
    [
        ("-b", "0"),
        ("-b", "-10"),
        ("-b", "abc"),
        ("-b", "100MB"),
        ("-b", "18446744073709551616"),
        ("-r", "0"),
        ("-r", "-1"),
        ("-r", "xyz"),
        ("-r", "5.5"),
    ],
)
def test_ac1_invalid_limits(
    snslice_bin: Path, flag: str, bad_val: str
) -> None:
    """AC-1: Non-numeric, zero, negative, or overflowing limits fail closed with INVALID_LIMIT."""
    res = run_snslice(snslice_bin, [flag, bad_val])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "INVALID_LIMIT"


@pytest.mark.parametrize(
    "bad_prefix",
    [
        "dir/part",
        "/absolute/part",
        "../escape",
        "part/..",
        "",
    ],
)
def test_ac1_invalid_prefix(
    snslice_bin: Path, tmp_path: Path, bad_prefix: str
) -> None:
    """AC-1: Prefix containing directory separators, traversal tokens, or empty fails with USAGE_ERROR."""
    res = run_snslice(snslice_bin, ["-b", "1000", "--prefix", bad_prefix])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"


def test_ac1_options_with_equals_syntax(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-1: Long options with '=' syntax (--bytes=N, --records=N, --format=F, --out-dir=D, --prefix=P) parse correctly."""
    out_dir = tmp_path / "out_eq"
    out_dir.mkdir()
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"a":1}\n{"b":2}\n{"c":3}\n')

    res = run_snslice(
        snslice_bin,
        [
            "--bytes=1000",
            "--records=1",
            "--format=ndjson",
            f"--out-dir={out_dir}",
            "--prefix=eq_",
            str(input_file),
        ],
    )
    assert res.returncode == STATUS_OK
    assert (out_dir / "eq_00001.ndjson").is_file()
    assert (out_dir / "eq_00002.ndjson").is_file()
    assert (out_dir / "eq_00003.ndjson").is_file()


@pytest.mark.parametrize(
    "flag",
    [
        "-b",
        "--bytes",
        "-r",
        "--records",
        "-f",
        "--format",
        "-d",
        "--out-dir",
        "-p",
        "--prefix",
    ],
)
def test_ac1_options_missing_required_argument(
    snslice_bin: Path, flag: str
) -> None:
    """AC-1: Options requiring an argument fail closed with USAGE_ERROR when argument is missing at end of argv."""
    res = run_snslice(snslice_bin, [flag])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"


def test_cli_invalid_prefix_slash(snslice_bin: Path) -> None:
    """AC-1: Prefix containing directory separator fails closed with USAGE_ERROR."""
    res = run_snslice(snslice_bin, ["-b", "1000", "--prefix", "sub/dir"])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"


def test_cli_invalid_prefix_traversal(snslice_bin: Path) -> None:
    """AC-1: Prefix containing traversal token '..' fails closed with USAGE_ERROR."""
    res = run_snslice(snslice_bin, ["-b", "1000", "--prefix", "../escape"])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "USAGE_ERROR"


def test_cli_invalid_output_directory(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-1: Non-existent output directory fails closed with OUTPUT_DIR_ERROR."""
    nonexistent = tmp_path / "nonexistent_dir_xyz"
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"a":1}\n')
    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(nonexistent), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "OUTPUT_DIR_ERROR"


# ---------------------------------------------------------------------------
# Suite 2: Bounded-Memory Streaming and Resource Safety (AC-2)
# ---------------------------------------------------------------------------


def test_ac2_bounded_memory_streaming_rss(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-2: Ingesting a large stream exhibits constant O(1) resident memory without unbounded growth."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    record = b'{"id":12345,"sensor":"temperature","value":24.85,"status":"nominal","tags":["a","b","c"]}\n'
    num_records = 30000
    total_bytes = len(record) * num_records

    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANG"] = "C"

    proc = subprocess.Popen(
        [
            str(snslice_bin),
            "-b",
            "1048576",
            "--out-dir",
            str(out_dir),
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    max_rss_kb = 0
    block = record * 600
    assert proc.stdin is not None
    written = 0
    while written < total_bytes:
        to_write = min(len(block), total_bytes - written)
        proc.stdin.write(block[:to_write])
        written += to_write

        statm_path = Path(f"/proc/{proc.pid}/statm")
        if statm_path.is_file():
            try:
                pages = int(statm_path.read_text().split()[1])
                rss_kb = (pages * resource.getpagesize()) // 1024
                if rss_kb > max_rss_kb:
                    max_rss_kb = rss_kb
            except Exception:
                pass

    proc.stdin.close()
    proc.stdin = None
    stdout, stderr = proc.communicate(timeout=30)

    assert proc.returncode == STATUS_OK, f"Process failed: {stderr.decode()}"
    if max_rss_kb > 0:
        assert max_rss_kb < 35 * 1024, f"RSS exceeded bound: {max_rss_kb} KB"

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) >= 2
    total_reconstructed_records = 0
    for chunk in chunks:
        for line in chunk.read_text().splitlines():
            if line:
                data = json.loads(line)
                assert data["sensor"] == "temperature"
                total_reconstructed_records += 1
    assert total_reconstructed_records == num_records


@pytest.mark.parametrize(
    "boundary_size",
    [
        65535,
        65536,
        65537,
        131072,
    ],
)
def test_ac2_io_buffer_boundaries(
    snslice_bin: Path, tmp_path: Path, boundary_size: int
) -> None:
    """AC-2: Inputs crossing exact 64 KiB I/O buffer boundaries transition cleanly without byte loss."""
    out_dir = tmp_path / f"out_{boundary_size}"
    out_dir.mkdir()
    input_file = tmp_path / f"input_{boundary_size}.ndjson"

    line_payload = b'{"marker":"boundary_test"}\n'
    line_len = len(line_payload)
    count, remainder = divmod(boundary_size, line_len)
    if 0 < remainder < 3:
        count -= 1
        remainder += line_len

    content = bytearray(line_payload * count)
    if remainder > 0:
        pad_record = b"{}" + (b" " * (remainder - 3)) + b"\n"
        assert len(pad_record) == remainder
        json.loads(pad_record)
        content.extend(pad_record)

    assert len(content) == boundary_size
    input_file.write_bytes(content)

    res = run_snslice(
        snslice_bin,
        ["-b", "30000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    reconstructed = b"".join(chunk.read_bytes() for chunk in chunks)
    assert reconstructed == content


def test_ac2_record_larger_than_buffer_boundary(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-2: A single valid JSON record larger than 64 KiB buffer (e.g. 100 KiB) is read across buffers without corruption."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "large_record.ndjson"

    large_payload = "A" * (100 * 1024)
    rec1 = {"id": 1, "payload": large_payload}
    rec2 = {"id": 2, "payload": "small"}
    raw_data = json.dumps(rec1).encode() + b"\n" + json.dumps(rec2).encode() + b"\n"
    assert len(raw_data) > SNSLICE_IO_BUFFER_SIZE
    input_file.write_bytes(raw_data)

    res = run_snslice(
        snslice_bin,
        ["-r", "1", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) == 2
    c1_obj = json.loads(chunks[0].read_text().strip())
    assert c1_obj["id"] == 1
    assert len(c1_obj["payload"]) == 100 * 1024
    c2_obj = json.loads(chunks[1].read_text().strip())
    assert c2_obj["id"] == 2


def test_ac2_single_record_exceeds_bytes_limit(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-2: A single record exceeding --bytes threshold occupies its chunk entirely and is never split across chunks."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "exceeds_bytes.ndjson"

    rec1 = {"id": 1, "data": "x" * 450}
    rec2 = {"id": 2, "data": "small"}
    raw_data = json.dumps(rec1).encode() + b"\n" + json.dumps(rec2).encode() + b"\n"
    assert len(json.dumps(rec1).encode() + b"\n") > 100
    input_file.write_bytes(raw_data)

    res = run_snslice(
        snslice_bin,
        ["-b", "100", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) == 2
    c1_obj = json.loads(chunks[0].read_text().strip())
    assert c1_obj["id"] == 1
    c2_obj = json.loads(chunks[1].read_text().strip())
    assert c2_obj["id"] == 2


# ---------------------------------------------------------------------------
# Suite 3: NDJSON Line Boundary and Complete Record Chunking (AC-3)
# ---------------------------------------------------------------------------


def test_ac3_ndjson_split_by_bytes(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-3: Splits NDJSON streams by byte threshold strictly on complete line boundaries."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "data.ndjson"

    records = [
        {"id": i, "name": f"user_{i}", "payload": "x" * ((i * 17) % 80)}
        for i in range(1, 41)
    ]
    raw_lines = [json.dumps(r).encode() + b"\n" for r in records]
    input_file.write_bytes(b"".join(raw_lines))

    res = run_snslice(
        snslice_bin,
        ["-b", "400", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) > 1

    reconstructed_records = []
    for chunk in chunks:
        lines = chunk.read_text().splitlines()
        assert len(lines) > 0
        for line in lines:
            obj = json.loads(line)
            reconstructed_records.append(obj)

    assert reconstructed_records == records


def test_ac3_ndjson_split_by_records(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-3: Splits NDJSON streams by record count threshold strictly on complete record boundaries."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "records.ndjson"

    total_records = 23
    records = [{"index": i, "val": i * 10} for i in range(total_records)]
    input_file.write_bytes(
        b"".join(json.dumps(r).encode() + b"\n" for r in records)
    )

    res = run_snslice(
        snslice_bin,
        ["--records", "5", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks):
        lines = [l for l in chunk.read_text().splitlines() if l]
        if idx < 4:
            assert len(lines) == 5
        else:
            assert len(lines) == 3


def test_ac3_ndjson_both_thresholds(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-3: When both --bytes and --records are specified, cuts when either threshold is reached."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "both.ndjson"

    r1 = json.dumps({"id": 1, "data": "a" * 480}).encode() + b"\n"
    small_records = [json.dumps({"id": i}).encode() + b"\n" for i in range(2, 20)]

    input_file.write_bytes(r1 + b"".join(small_records))

    res = run_snslice(
        snslice_bin,
        ["-b", "400", "-r", "4", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) > 1
    c1_lines = chunks[0].read_text().splitlines()
    assert len(c1_lines) == 1
    assert json.loads(c1_lines[0])["id"] == 1


def test_ac3_ndjson_crlf_handling(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-3: Recognizes CRLF line delimiters and preserves record boundaries seamlessly."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "crlf.ndjson"

    records = [{"id": i, "val": f"crlf_{i}"} for i in range(1, 11)]
    crlf_content = b"".join(json.dumps(r).encode() + b"\r\n" for r in records)
    input_file.write_bytes(crlf_content)

    res = run_snslice(
        snslice_bin,
        ["-r", "3", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) == 4
    reconstructed = []
    for chunk in chunks:
        for line in chunk.read_text().splitlines():
            if line:
                reconstructed.append(json.loads(line))
    assert reconstructed == records


def test_ac3_ndjson_empty_lines_preserved(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-3: Preserves blank lines as valid NDJSON records without desynchronizing counters."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "blanks.ndjson"

    content = b'{"a":1}\n\n{"b":2}\n\n{"c":3}\n'
    input_file.write_bytes(content)

    res = run_snslice(
        snslice_bin,
        ["-r", "2", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) == 3
    recombined = b"".join(c.read_bytes() for c in chunks)
    assert recombined == content


def test_ac3_ndjson_default_format_and_stdin(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-3: Format defaults to ndjson and supports streaming from stdin via '-' operand."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    input_data = b'{"item":1}\n{"item":2}\n{"item":3}\n{"item":4}\n'
    res = run_snslice(
        snslice_bin,
        ["-r", "2", "--out-dir", str(out_dir), "-"],
        input_bytes=input_data,
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.ndjson"))
    assert len(chunks) == 2
    assert (out_dir / "chunk_00001.ndjson").read_bytes() == b'{"item":1}\n{"item":2}\n'
    assert (out_dir / "chunk_00002.ndjson").read_bytes() == b'{"item":3}\n{"item":4}\n'


# ---------------------------------------------------------------------------
# Suite 4: CSV Quoted Records Spanning Physical Lines (RFC 4180) (AC-4)
# ---------------------------------------------------------------------------


def test_ac4_csv_multiline_fields_preserved(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-4: Multiline CSV records with embedded newlines are never severed across chunk files."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "multiline.csv"

    raw_csv = (
        'id,name,bio,notes\n'
        '1,"Alice","Senior Systems Architect\nSpecializing in C17\nStrict Quality Gates","Primary lead"\n'
        '2,"Bob","DevOps Engineer\nContainer and Cloud Infrastructure","Backup lead"\n'
        '3,"Charlie","Security Auditor\nTerminal escape sequence defense","Consultant"\n'
        '4,"Dana","Data Engineer\nStreaming pipeline automation","Specialist"\n'
    )
    input_file.write_text(raw_csv)

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "80", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.csv"))
    assert len(chunks) > 1

    reconstructed_rows = []
    for chunk in chunks:
        with chunk.open("r", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                reconstructed_rows.append(row)

    with input_file.open("r", newline="") as f:
        expected_rows = list(csv.reader(f))

    assert reconstructed_rows == expected_rows


def test_ac4_csv_split_by_bytes(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-4: Slices CSV streams by byte threshold without severing multiline quoted fields across chunks."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "multiline_bytes.csv"

    raw_csv = (
        'id,description,status\n'
        '1,"First multiline\ndescription line 2\ndescription line 3","active"\n'
        '2,"Second multiline\ndescription line 2","pending"\n'
        '3,"Third single line description","completed"\n'
        '4,"Fourth multiline\npart a\npart b\npart c","active"\n'
    )
    input_file.write_text(raw_csv)

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "80", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.csv"))
    assert len(chunks) > 1

    reconstructed_rows = []
    for chunk in chunks:
        with chunk.open("r", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                reconstructed_rows.append(row)

    with input_file.open("r", newline="") as f:
        expected_rows = list(csv.reader(f))

    assert reconstructed_rows == expected_rows


def test_ac4_csv_both_thresholds(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-4: When both --bytes and --records are specified for CSV, cuts when either limit is reached."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "csv_both.csv"

    raw_csv = (
        'id,data\n'
        '1,"' + ('M' * 400) + '\nsecond line"\n'
        '2,"small row"\n'
        '3,"another small row"\n'
    )
    input_file.write_text(raw_csv)

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "200", "-r", "5", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.csv"))
    assert len(chunks) > 1

    reconstructed_rows = []
    for chunk in chunks:
        with chunk.open("r", newline="") as f:
            reconstructed_rows.extend(list(csv.reader(f)))

    with input_file.open("r", newline="") as f:
        expected_rows = list(csv.reader(f))

    assert reconstructed_rows == expected_rows


def test_ac4_csv_escaped_double_quotes(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-4: Handles consecutive double quotes ("") as escaped quotes within quoted fields."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "escaped_quotes.csv"

    raw_csv = (
        'id,quote,context\n'
        '1,"He said, ""Hello, world!"" and stepped forward","Greeting"\n'
        '2,"Contains ""multiple"" ""escaped"" quotes in one line","Test"\n'
        '3,"Multiline with ""escaped quotes""\nand a physical newline inside","Complex"\n'
    )
    input_file.write_text(raw_csv)

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "50", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.csv"))
    reconstructed_rows = []
    for chunk in chunks:
        with chunk.open("r", newline="") as f:
            reconstructed_rows.extend(list(csv.reader(f)))

    with input_file.open("r", newline="") as f:
        expected_rows = list(csv.reader(f))

    assert reconstructed_rows == expected_rows


def test_ac4_csv_split_by_records(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-4: Slices multiline CSV streams by record limit regardless of physical line count."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "records.csv"

    raw_csv = (
        'id,data\n'
        '1,"Row 1\nline 2\nline 3"\n'
        '2,"Row 2\nsingle line"\n'
        '3,"Row 3\nline 2"\n'
        '4,"Row 4\nline 2\nline 3\nline 4"\n'
        '5,"Row 5"\n'
    )
    input_file.write_text(raw_csv)

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-r", "2", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.csv"))
    assert len(chunks) == 3

    for chunk in chunks:
        with chunk.open("r", newline="") as f:
            rows = list(csv.reader(f))
            assert len(rows) == 2


def test_ac4_csv_crlf_record_delimiters(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-4: Respects CRLF record delimiters and CRLF inside quoted fields."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "crlf.csv"

    raw_csv = (
        b"id,value\r\n"
        b'1,"Field with\r\nliteral CRLF inside"\r\n'
        b'2,"Simple field"\r\n'
        b'3,"Another\r\nmultiline field"\r\n'
    )
    input_file.write_bytes(raw_csv)

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-r", "2", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    chunks = sorted(out_dir.glob("chunk_*.csv"))
    assert len(chunks) == 2

    reconstructed_rows = []
    for chunk in chunks:
        with chunk.open("r", newline="") as f:
            reconstructed_rows.extend(list(csv.reader(f)))

    with input_file.open("r", newline="") as f:
        expected_rows = list(csv.reader(f))

    assert reconstructed_rows == expected_rows


# ---------------------------------------------------------------------------
# Suite 5: Deterministic Chunk Naming and Output Slicing (AC-5)
# ---------------------------------------------------------------------------


def test_ac5_chunk_naming_default_ndjson(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-5: Default naming produces chunk_00001.ndjson, chunk_00002.ndjson, ..."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"a":1}\n{"b":2}\n{"c":3}\n')

    res = run_snslice(
        snslice_bin,
        ["-r", "1", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    names = sorted(f.name for f in out_dir.iterdir())
    assert names == [
        "chunk_00001.ndjson",
        "chunk_00002.ndjson",
        "chunk_00003.ndjson",
    ]


def test_ac5_chunk_naming_default_csv(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-5: CSV naming defaults to chunk_%05zu.csv."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "in.csv"
    input_file.write_text("1,alice\n2,bob\n")

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-r", "1", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    names = sorted(f.name for f in out_dir.iterdir())
    assert names == [
        "chunk_00001.csv",
        "chunk_00002.csv",
    ]
    assert (out_dir / "chunk_00001.csv").read_text() == "1,alice\n"
    assert (out_dir / "chunk_00002.csv").read_text() == "2,bob\n"


def test_ac5_chunk_naming_custom_prefix_and_outdir(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-5: Custom prefix and nested output directory are formatted deterministically."""
    out_dir = tmp_path / "deep" / "nested" / "output"
    out_dir.mkdir(parents=True)
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"x":1}\n{"y":2}\n')

    res = run_snslice(
        snslice_bin,
        [
            "-r",
            "1",
            "--prefix",
            "slice_batch_",
            "--out-dir",
            str(out_dir),
            str(input_file),
        ],
    )
    assert res.returncode == STATUS_OK

    names = sorted(f.name for f in out_dir.iterdir())
    assert names == ["slice_batch_00001.ndjson", "slice_batch_00002.ndjson"]


def test_ac5_chunk_naming_outdir_trailing_slash(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-5: Handles output directory paths with trailing slash without double-slash corruption."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"x":1}\n')

    res = run_snslice(
        snslice_bin,
        ["-r", "1", "--out-dir", f"{out_dir}/", str(input_file)],
    )
    assert res.returncode == STATUS_OK
    assert (out_dir / "chunk_00001.ndjson").is_file()


def test_ac5_chunk_naming_sequential_monotonicity(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-5: Emits monotonically sequential 5-digit indices without missing or skipped numbers."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "many.ndjson"

    input_file.write_bytes(b"".join(f'{{"i":{i}}}\n'.encode() for i in range(1, 13)))

    res = run_snslice(
        snslice_bin,
        ["-r", "1", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK

    expected_names = [f"chunk_{i:05d}.ndjson" for i in range(1, 13)]
    actual_names = sorted(f.name for f in out_dir.iterdir())
    assert actual_names == expected_names


# ---------------------------------------------------------------------------
# Suite 6: Chunk Collision Prevention and Atomic File Creation (AC-6)
# ---------------------------------------------------------------------------


def test_ac6_chunk_collision_first_chunk(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-6: Fails closed with OUTPUT_COLLISION and status 2 if target chunk file already exists."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    canary = out_dir / "chunk_00001.ndjson"
    canary_content = b"PRE_EXISTING_CANARY_NEVER_OVERWRITE\n"
    canary.write_bytes(canary_content)

    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"new":"data"}\n')

    res = run_snslice(
        snslice_bin,
        ["-b", "100", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "OUTPUT_COLLISION"

    assert canary.read_bytes() == canary_content


def test_ac6_chunk_collision_subsequent_chunk(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-6: Aborts cleanly on collision on subsequent chunks while preserving completed chunks."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    canary_chunk2 = out_dir / "chunk_00002.ndjson"
    canary_content = b"CANARY_CHUNK_TWO\n"
    canary_chunk2.write_bytes(canary_content)

    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"record":1}\n{"record":2}\n{"record":3}\n')

    res = run_snslice(
        snslice_bin,
        ["-r", "1", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "OUTPUT_COLLISION"

    assert (out_dir / "chunk_00001.ndjson").is_file()
    assert canary_chunk2.read_bytes() == canary_content


# ---------------------------------------------------------------------------
# Suite 7: Empty Input Stream Handling (AC-7)
# ---------------------------------------------------------------------------


def test_ac7_empty_file_input(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-7: Empty 0-byte input file exits cleanly with status 0 and creates zero chunk files."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    empty_file = tmp_path / "empty.ndjson"
    empty_file.touch()

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(out_dir), str(empty_file)],
    )
    assert res.returncode == STATUS_OK
    assert res.stdout == b""
    assert res.stderr == b""
    assert list(out_dir.iterdir()) == []


def test_ac7_empty_stdin_input(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-7: Empty stdin stream exits cleanly with status 0 and creates zero chunk files."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(out_dir), "-"],
        input_bytes=b"",
    )
    assert res.returncode == STATUS_OK
    assert res.stdout == b""
    assert res.stderr == b""
    assert list(out_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# Suite 8: Malformed Input and Unterminated Record Rejection (AC-8)
# ---------------------------------------------------------------------------


def test_ac8_malformed_csv_unterminated_quote(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: Unterminated quoted field reaching EOF in CSV fails closed with MALFORMED_CSV."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "bad.csv"
    input_file.write_text('id,text\n1,"unterminated field at eof')

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "1000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_CSV"


def test_ac8_malformed_ndjson_unterminated_line(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: NDJSON input ending at EOF without a terminating newline fails with MALFORMED_NDJSON."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "bad.ndjson"
    input_file.write_bytes(b'{"valid":1}\n{"missing_trailing_newline":2}')

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_NDJSON"


def test_ac8_malformed_ndjson_embedded_nul(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: NDJSON input containing embedded NUL bytes fails with MALFORMED_NDJSON."""
    out_dir = tmp_path / "out_ndjson"
    out_dir.mkdir(exist_ok=True)
    input_file = tmp_path / "nul.ndjson"
    input_file.write_bytes(b'{"key":"val\x00ue"}\n')

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_NDJSON"


def test_ac8_malformed_csv_embedded_nul(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: CSV input containing embedded NUL bytes fails with MALFORMED_CSV."""
    out_dir = tmp_path / "out_csv"
    out_dir.mkdir(exist_ok=True)
    input_file = tmp_path / "nul.csv"
    input_file.write_bytes(b'id,val\n1,embedded\x00nul\n')

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "1000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_CSV"


def test_ac8_record_length_limit_exceeded(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: Record exceeding 16 MiB without delimiter fails closed with RECORD_LENGTH_LIMIT."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    env = os.environ.copy()
    env["LC_ALL"] = "C"
    proc = subprocess.Popen(
        [
            str(snslice_bin),
            "-b",
            "100000",
            "--out-dir",
            str(out_dir),
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    chunk_1mb = b"X" * (1024 * 1024)
    assert proc.stdin is not None
    try:
        for _ in range(17):
            proc.stdin.write(chunk_1mb)
        proc.stdin.close()
    except BrokenPipeError:
        pass

    stdout, stderr = proc.communicate(timeout=30)
    assert proc.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(stderr)
    assert hazard == "RECORD_LENGTH_LIMIT"


def test_ac8_malformed_csv_invalid_char_after_quote(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: Malformed CSV with invalid character immediately after closing quote fails with MALFORMED_CSV."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "bad_quote_char.csv"
    input_file.write_text('id,text\n1,"quoted"extra_chars_here,valid\n')

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-b", "1000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_CSV"




def test_embedded_nul_preserves_output_directory(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-8: Embedded NUL failure does not remove or damage pre-existing empty output directory."""
    out_dir = tmp_path / "target_out"
    out_dir.mkdir()
    input_file = tmp_path / "nul_input.ndjson"
    input_file.write_bytes(b'{"bad":"data\x00here"}\n')

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_NDJSON"
    assert out_dir.is_dir(), "Output directory must be preserved on error"


def test_csv_record_limit_every_record_counts(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-4: In CSV mode, every record boundary counts toward record limit without arbitrary chunk 1 exceptions."""
    out_dir = tmp_path / "csv_out"
    out_dir.mkdir()
    input_file = tmp_path / "records_3.csv"
    input_file.write_text("header1,header2\nrow1,val1\nrow2,val2\n")

    res = run_snslice(
        snslice_bin,
        ["-f", "csv", "-r", "1", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_OK
    names = sorted(f.name for f in out_dir.iterdir())
    assert names == [
        "chunk_00001.csv",
        "chunk_00002.csv",
        "chunk_00003.csv",
    ]


# ---------------------------------------------------------------------------
# Suite 9: Chunk Write Failures and Operational I/O Safety (AC-9)
# ---------------------------------------------------------------------------


def test_ac9_write_failure_unlinks_partial_chunk_on_format_error(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-9: On abort during chunk creation, active partial chunk is unlinked; completed chunks remain."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    input_file = tmp_path / "partial.ndjson"

    content = (
        b'{"rec":1}\n'
        b'{"rec":2}\n'
        b'{"rec":3}\n'
        b'{"unterminated":4'
    )
    input_file.write_bytes(content)

    res = run_snslice(
        snslice_bin,
        ["-r", "2", "--out-dir", str(out_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "MALFORMED_NDJSON"

    chunk1 = out_dir / "chunk_00001.ndjson"
    assert chunk1.is_file()
    assert chunk1.read_bytes() == b'{"rec":1}\n{"rec":2}\n'

    chunk2 = out_dir / "chunk_00002.ndjson"
    assert not chunk2.exists(), "Active partial chunk was not unlinked on abort"


def test_ac9_active_chunk_unlinked_on_record_limit(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-9: Active chunk is unlinked when record length limit is exceeded during chunk generation."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    env = os.environ.copy()
    env["LC_ALL"] = "C"
    proc = subprocess.Popen(
        [
            str(snslice_bin),
            "-r",
            "1",
            "--out-dir",
            str(out_dir),
            "-",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    assert proc.stdin is not None
    proc.stdin.write(b'{"first_chunk":true}\n')
    proc.stdin.flush()
    time.sleep(0.05)

    chunk_1mb = b"Y" * (1024 * 1024)
    try:
        for _ in range(17):
            proc.stdin.write(chunk_1mb)
        proc.stdin.close()
    except BrokenPipeError:
        pass

    stdout, stderr = proc.communicate(timeout=30)
    assert proc.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(stderr)
    assert hazard == "RECORD_LENGTH_LIMIT"

    assert (out_dir / "chunk_00001.ndjson").is_file()
    assert not (out_dir / "chunk_00002.ndjson").exists()


def test_ac9_chunk_open_error_preserves_prior_chunks(
    snslice_bin: Path, tmp_path: Path
) -> None:
    """AC-9: Failure opening chunk in read-only directory fails with CHUNK_OPEN_ERROR/OUTPUT_DIR_ERROR."""
    out_dir_no_write = tmp_path / "no_write"
    out_dir_no_write.mkdir(mode=0o555)
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"a":1}\n')

    try:
        res = run_snslice(
            snslice_bin,
            ["-r", "1", "--out-dir", str(out_dir_no_write), str(input_file)],
        )
        assert res.returncode == STATUS_ERROR
        hazard, _ = parse_diagnostic(res.stderr)
        assert hazard in ("CHUNK_OPEN_ERROR", "OUTPUT_DIR_ERROR")
    finally:
        os.chmod(out_dir_no_write, 0o755)


# ---------------------------------------------------------------------------
# Suite 10: CLI Diagnostics and Hostile Byte Sanitization (AC-10)
# ---------------------------------------------------------------------------


def test_ac10_diagnostic_sanitization_ansi_escapes(snslice_bin: Path) -> None:
    """AC-10: Stderr diagnostics convert ANSI escape sequences to hexadecimal \\xHH representations."""
    hostile_arg = "\x1b[31;1mINJECTION\x1b[0m.ndjson"
    res = run_snslice(snslice_bin, ["-b", "1000", hostile_arg])
    assert res.returncode == STATUS_ERROR

    assert_stderr_sanitized(res.stderr)
    assert b"\\x1B" in res.stderr
    assert b"\x1b" not in res.stderr


def test_ac10_diagnostic_sanitization_control_chars_and_quotes(
    snslice_bin: Path,
) -> None:
    """AC-10: Non-printable control bytes, quotes, and backslashes are escaped in diagnostics."""
    hostile_arg = 'bad"\x07\x08\t\r\\filename.ndjson'
    res = run_snslice(snslice_bin, ["-b", "1000", hostile_arg])
    assert res.returncode == STATUS_ERROR

    assert_stderr_sanitized(res.stderr)
    stderr_text = res.stderr.decode("ascii")
    assert "\\x22" in stderr_text or "\\x5C" in stderr_text or "\\x07" in stderr_text


# ---------------------------------------------------------------------------
# Suite 11: Closed Hazard Taxonomy and Exit Status Integrity (AC-11)
# ---------------------------------------------------------------------------


def test_ac11_closed_hazard_taxonomy_membership() -> None:
    """AC-11: Verifies the closed hazard taxonomy contains exactly the 16 contract members."""
    expected_members = {
        "USAGE_ERROR",
        "UNKNOWN_OPTION",
        "INVALID_LIMIT",
        "INVALID_FORMAT",
        "INPUT_NOT_FOUND",
        "INPUT_IS_DIRECTORY",
        "INPUT_READ_ERROR",
        "RECORD_LENGTH_LIMIT",
        "MALFORMED_NDJSON",
        "MALFORMED_CSV",
        "OUTPUT_DIR_ERROR",
        "OUTPUT_COLLISION",
        "CHUNK_OPEN_ERROR",
        "CHUNK_WRITE_ERROR",
        "OUT_OF_MEMORY",
        "BROKEN_PIPE",
    }
    assert CLOSED_HAZARD_TAXONOMY == expected_members
    assert len(CLOSED_HAZARD_TAXONOMY) == 16


def test_ac11_input_not_found(snslice_bin: Path) -> None:
    """AC-11: Non-existent input operand triggers INPUT_NOT_FOUND with status 2."""
    res = run_snslice(snslice_bin, ["-b", "1000", "non_existent_file_xyz.ndjson"])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "INPUT_NOT_FOUND"


def test_ac11_input_is_directory(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-11: Input operand pointing to a directory triggers INPUT_IS_DIRECTORY with status 2."""
    dir_operand = tmp_path / "a_directory"
    dir_operand.mkdir()

    res = run_snslice(snslice_bin, ["-b", "1000", str(dir_operand)])
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "INPUT_IS_DIRECTORY"


def test_ac11_output_dir_error_missing(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-11: Non-existent output directory triggers OUTPUT_DIR_ERROR with status 2."""
    missing_dir = tmp_path / "does_not_exist_xyz"
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"a":1}\n')

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(missing_dir), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "OUTPUT_DIR_ERROR"


def test_ac11_output_dir_error_is_file(snslice_bin: Path, tmp_path: Path) -> None:
    """AC-11: Output directory operand pointing to a file triggers OUTPUT_DIR_ERROR with status 2."""
    regular_file = tmp_path / "not_a_dir"
    regular_file.touch()
    input_file = tmp_path / "in.ndjson"
    input_file.write_text('{"a":1}\n')

    res = run_snslice(
        snslice_bin,
        ["-b", "1000", "--out-dir", str(regular_file), str(input_file)],
    )
    assert res.returncode == STATUS_ERROR
    hazard, _ = parse_diagnostic(res.stderr)
    assert hazard == "OUTPUT_DIR_ERROR"


def test_ac11_sigpipe_handling(snslice_bin: Path) -> None:
    """AC-11: Broken stdout pipe does not result in uncontrolled crash (SIGPIPE ignored)."""
    proc = subprocess.Popen(
        [str(snslice_bin), "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    proc.stdout.close()
    proc.wait(timeout=5)
    assert proc.returncode in (STATUS_OK, STATUS_ERROR)


# ---------------------------------------------------------------------------
# Suite 12: Repository Build, Hardening, and Quality Floor Compatibility (AC-12)
# ---------------------------------------------------------------------------


def test_ac12_compiler_gcc_strict() -> None:
    """AC-12: Compiles src/snslice.c cleanly under GCC with -Wall -Wextra -Wpedantic -Werror."""
    if not SRC.is_file():
        pytest.skip(f"source {SRC} does not exist yet; skipping GCC compilation check")

    gcc = shutil.which("gcc")
    if not gcc:
        pytest.skip("gcc compiler not found")

    with tempfile.TemporaryDirectory(prefix="snslice-gcc-check-") as tmpdir:
        obj_target = Path(tmpdir) / "snslice.o"
        cmd = [
            gcc,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-D_POSIX_C_SOURCE=200809L",
            "-D_FILE_OFFSET_BITS=64",
            "-O2",
            "-c",
            str(SRC),
            "-o",
            str(obj_target),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"GCC build failed:\n{res.stderr}"
        assert res.stderr == "", f"GCC emitted warnings:\n{res.stderr}"


def test_ac12_compiler_clang_strict() -> None:
    """AC-12: Compiles src/snslice.c cleanly under Clang with -Wall -Wextra -Wpedantic -Werror."""
    if not SRC.is_file():
        pytest.skip(f"source {SRC} does not exist yet; skipping Clang compilation check")

    clang = shutil.which("clang")
    if not clang:
        pytest.skip("clang compiler not found")

    with tempfile.TemporaryDirectory(prefix="snslice-clang-check-") as tmpdir:
        obj_target = Path(tmpdir) / "snslice.o"
        cmd = [
            clang,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-D_POSIX_C_SOURCE=200809L",
            "-D_FILE_OFFSET_BITS=64",
            "-O2",
            "-c",
            str(SRC),
            "-o",
            str(obj_target),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Clang build failed:\n{res.stderr}"
        assert res.stderr == "", f"Clang emitted warnings:\n{res.stderr}"


def test_sanitizers_clean() -> None:
    """AC-12: Compiles src/snslice.c cleanly under Clang with AddressSanitizer and UndefinedBehaviorSanitizer."""
    if not SRC.is_file():
        pytest.skip(f"source {SRC} does not exist yet; skipping sanitizer check")

    clang = shutil.which("clang")
    if not clang:
        pytest.skip("clang compiler not found")

    with tempfile.TemporaryDirectory(prefix="snslice-san-check-") as tmpdir:
        obj_target = Path(tmpdir) / "snslice.o"
        cmd = [
            clang,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            "-D_POSIX_C_SOURCE=200809L",
            "-D_FILE_OFFSET_BITS=64",
            "-O1",
            "-c",
            str(SRC),
            "-o",
            str(obj_target),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Sanitizer build failed:\n{res.stderr}"
        assert res.stderr == "", f"Sanitizer build emitted warnings:\n{res.stderr}"




# ---------------------------------------------------------------------------
# Suite 13: User Journey Manifest Synchronization and Traceability (AC-13)
# ---------------------------------------------------------------------------


def test_ac13_manifest_exists_and_valid_json() -> None:
    """AC-13: journeys/snslice_user_journeys_manifest.json exists and is valid JSON."""
    if not SNSLICE_JOURNEYS_MANIFEST.is_file():
        pytest.skip(f"snslice manifest missing at {SNSLICE_JOURNEYS_MANIFEST}")
    data = json.loads(SNSLICE_JOURNEYS_MANIFEST.read_text())
    assert isinstance(data, dict)
    assert "journeys" in data
    assert "command_allowlist" in data


def test_ac13_manifest_schema_compliance() -> None:
    """AC-13: Manifest adheres strictly to canonical user journeys manifest schema."""
    if not SNSLICE_JOURNEYS_MANIFEST.is_file():
        pytest.skip(f"snslice manifest missing at {SNSLICE_JOURNEYS_MANIFEST}")
    data = json.loads(SNSLICE_JOURNEYS_MANIFEST.read_text())
    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(data))
        assert not errors, f"Schema validation errors:\n{[e.message for e in errors]}"


def test_ac13_manifest_command_allowlist() -> None:
    """AC-13: command_allowlist contains non-empty strings suitable for executing tmp/snslice."""
    if not SNSLICE_JOURNEYS_MANIFEST.is_file():
        pytest.skip(f"snslice manifest missing at {SNSLICE_JOURNEYS_MANIFEST}")
    data = json.loads(SNSLICE_JOURNEYS_MANIFEST.read_text())
    allowlist = data.get("command_allowlist")
    assert isinstance(allowlist, list) and len(allowlist) > 0
    for cmd in allowlist:
        assert isinstance(cmd, str) and len(cmd) > 0
    assert "tmp/snslice" in allowlist


def test_ac13_manifest_authorities() -> None:
    """AC-13: Every natural-language journey has authority in human, mission, author, exploratory."""
    if not SNSLICE_JOURNEYS_MANIFEST.is_file():
        pytest.skip(f"snslice manifest missing at {SNSLICE_JOURNEYS_MANIFEST}")
    data = json.loads(SNSLICE_JOURNEYS_MANIFEST.read_text())
    journeys = data.get("journeys", [])
    assert len(journeys) >= 13
    for idx, j in enumerate(journeys):
        auth = j.get("authority")
        assert auth in JOURNEY_AUTHORITIES, (
            f"Journey {idx} ('{j.get('name')}') has invalid authority: {auth}"
        )


def test_ac13_manifest_traces_to_ac_coverage() -> None:
    """AC-13: Non-exploratory journeys cite valid AC-N and collectively cover all AC-1 through AC-13."""
    if not SNSLICE_JOURNEYS_MANIFEST.is_file():
        pytest.skip(f"snslice manifest missing at {SNSLICE_JOURNEYS_MANIFEST}")
    data = json.loads(SNSLICE_JOURNEYS_MANIFEST.read_text())
    journeys = data.get("journeys", [])
    all_valid_acs = {f"AC-{i}" for i in range(1, 14)}
    covered_acs: set[str] = set()

    for idx, j in enumerate(journeys):
        name = j.get("name")
        auth = j.get("authority")
        assert isinstance(name, str) and len(name) > 0

        traces = j.get("traces_to", [])
        if auth != "exploratory":
            assert len(traces) > 0, f"Non-exploratory journey '{name}' lacks traces_to"
            for ac in traces:
                assert ac in all_valid_acs, f"Journey '{name}' cites invalid AC '{ac}'"
                covered_acs.add(ac)
        else:
            for ac in traces:
                assert ac in all_valid_acs, f"Exploratory journey '{name}' cites invalid AC '{ac}'"

    missing_acs = all_valid_acs - covered_acs
    assert not missing_acs, f"Non-exploratory journeys fail to cover: {missing_acs}"


def test_user_journeys_manifest_sync() -> None:
    """AC-13: tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are synchronized."""
    assert TESTS_MANIFEST.is_file(), f"Missing canonical manifest at {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.is_file(), f"Missing journeys manifest at {JOURNEYS_MANIFEST}"
    data_tests = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    data_journeys = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))
    assert data_tests == data_journeys, (
        "tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are not identical"
    )


def test_user_journeys_schema_compliance() -> None:
    """AC-13: tests/user_journeys_manifest.json adheres strictly to USER_JOURNEYS_MANIFEST_SCHEMA."""
    assert TESTS_MANIFEST.is_file(), f"Missing manifest at {TESTS_MANIFEST}"
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(data))
        assert not errors, f"Schema validation errors in {TESTS_MANIFEST}:\n{[e.message for e in errors]}"
    allowlist = data.get("command_allowlist", [])
    assert isinstance(allowlist, list) and len(allowlist) > 0
    for cmd in allowlist:
        assert isinstance(cmd, str) and len(cmd) > 0


def test_user_journeys_coverage_completeness() -> None:
    """AC-13: Non-exploratory journeys cite valid AC-1..3 and preserve all 21 repository baseline journeys."""
    assert TESTS_MANIFEST.is_file(), f"Missing manifest at {TESTS_MANIFEST}"
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = data.get("journeys", [])
    assert len(journeys) == 21, f"Expected exactly 21 baseline journeys, got {len(journeys)}"

    allowed_checks = {"AC-1", "AC-2", "AC-3"}
    covered: set[str] = set()

    for idx, j in enumerate(journeys):
        name = j.get("name")
        auth = j.get("authority")
        assert isinstance(name, str) and len(name) > 0
        assert auth in JOURNEY_AUTHORITIES, f"Journey {idx} ('{name}') has invalid authority: {auth}"

        traces = j.get("traces_to", [])
        if auth != "exploratory":
            assert len(traces) > 0, f"Non-exploratory journey '{name}' lacks traces_to"
            for ac in traces:
                assert ac in allowed_checks, f"Journey '{name}' cites invalid AC '{ac}'"
                covered.add(ac)
        else:
            for ac in traces:
                assert ac in allowed_checks, f"Exploratory journey '{name}' cites invalid AC '{ac}'"

    missing = allowed_checks - covered
    assert not missing, f"Acceptance checks lack baseline journey coverage: {missing}"
