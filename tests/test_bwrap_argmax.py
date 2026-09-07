"""Targeted test suite for diagnosing and preventing bwrap ARG_MAX failures.

This suite exercises the repair contract (docs/bwrap-argmax-repair-contract.md)
and implementation plan (plans/bwrap-argmax-repair-implementation-plan.md) across:
- AC-1: Prompt transport off-argv (WorkerLaunch.stdin_text) and hardened bwrap sandbox containment.
- AC-2: Pre-exec payload measurement, single-argument and total-payload boundary rejection,
        typed LAUNCH_PAYLOAD_TOO_LARGE refusal classification, and value-free diagnostic accounting.
- AC-3: Bounded validation output excerpting (head/tail bounds with elision accounting),
        user journeys manifest synchronization and schema adherence, and product non-regression.
"""

from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
_scripts_dir = str(ROOT / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
import sandbox_exec

try:
    import agent_orch.validators as validators
    import agent_orch.worker as worker
    from agent_orch.models import ValidationRule
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
        journey_authority,
    )
except ImportError:
    validators = None  # type: ignore[assignment]
    worker = None  # type: ignore[assignment]
    ValidationRule = None  # type: ignore[assignment]
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]
    journey_authority = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
CONTRACT = ROOT / "docs" / "bwrap-argmax-repair-contract.md"
PLAN = ROOT / "plans" / "bwrap-argmax-repair-implementation-plan.md"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"

# Kernel execve limits (standard Linux x86_64 architecture: 4 KiB pages)
MAX_ARG_STRLEN = 131072  # 32 kernel pages (128 KiB) including trailing NUL byte
HOST_ARG_MAX = 2097152  # Typically 2 MiB combined argv + envp + pointer table

PROCESS_OUTPUT_EXCERPT_HEAD_BYTES = 4000
PROCESS_OUTPUT_EXCERPT_TAIL_BYTES = 4000


def _require_worker_module():
    return sandbox_exec


def _require_validators_module():
    if validators is None:
        pytest.skip("agent_orch.validators is required for this test")
    return validators


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(root: Path, relative: str, value: object | str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _get_sysdiff_binary(tmp_path: Path) -> Path:
    existing = ROOT / "build" / "sysdiff"
    if existing.is_file() and os.access(existing, os.X_OK):
        return existing
    binary = tmp_path / "sysdiff"
    cc = os.environ.get("CC", "cc")
    subprocess.run(
        [
            cc,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-o",
            str(binary),
            str(SYSDIFF_SRC),
        ],
        check=True,
        capture_output=True,
    )
    return binary


# ============================================================================
# AC-1: Prompt Transport Off-Argv and Hardened Sandbox Containment
# ============================================================================


def test_worker_launch_transports_prompt_via_stdin_text() -> None:
    """AC-1 / Journey 1: Large prompt payloads are delivered via stdin_text off argv."""
    w = _require_worker_module()
    assert hasattr(w, "WorkerLaunch"), "WorkerLaunch class must be defined"

    # Construct a large prompt (e.g. 200 KiB, well above 128 KiB MAX_ARG_STRLEN)
    large_prompt = "MISSION_PROMPT_PAYLOAD_START\n" + ("x" * 200000) + "\nMISSION_PROMPT_PAYLOAD_END"
    fixed_command = ["/usr/bin/env", "python3", "-c", "import sys; data = sys.stdin.read(); sys.exit(0)"]

    launch = w.WorkerLaunch(command=fixed_command, stdin_text=large_prompt)

    # 1. Positional command argv must remain small and fixed
    assert launch.command == fixed_command
    for arg in launch.command:
        arg_bytes = len(arg.encode("utf-8")) + 1
        assert arg_bytes <= w.max_single_launch_entry_bytes(), (
            f"Command argument exceeds single entry limit: {arg_bytes} bytes"
        )
        assert large_prompt not in arg

    # 2. Prompt must be intact in stdin_text
    assert launch.stdin_text == large_prompt
    assert len(launch.stdin_text) > 200000

    # 3. Payload accounting on argv must reflect only fixed command arguments
    report = w.launch_payload_report(launch.command, {})
    assert report["argument_count"] == len(fixed_command)
    assert report["argument_bytes"] < 1000
    assert report["total_bytes"] < w.max_total_launch_bytes()


def test_bwrap_argv_length_under_kernel_page_limit(tmp_path: Path) -> None:
    """AC-1: bwrap command-line argument list contains no element exceeding MAX_ARG_STRLEN."""
    w = _require_worker_module()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    step_run_dir = tmp_path / "step_run_dir"
    step_run_dir.mkdir()
    scratch_dir = tmp_path / "scratch_dir"
    scratch_dir.mkdir()
    runs_root = tmp_path / "runs_root"
    runs_root.mkdir()
    trusted1 = tmp_path / "trusted1"
    trusted1.mkdir()
    writable1 = tmp_path / "writable1"
    writable1.mkdir()

    cmd = w.build_host_sandbox_command(
        "/usr/bin/bwrap",
        ["/bin/sh", "-c", "echo hello"],
        workspace=workspace,
        step_run_dir=step_run_dir,
        scratch_dir=scratch_dir,
        runs_root=runs_root,
        trusted_readonly_paths=[trusted1],
        extra_writable=[writable1],
    )

    assert isinstance(cmd, list) and len(cmd) > 0
    max_single = w.max_single_launch_entry_bytes()

    for index, arg in enumerate(cmd):
        arg_len = len(arg.encode("utf-8")) + 1
        assert arg_len <= max_single, (
            f"bwrap argument {index} ({arg!r}) size {arg_len} exceeds MAX_ARG_STRLEN {max_single}"
        )

    # Pre-exec measurement must accept the constructed bwrap command
    refusal = w.refuse_oversized_launch(cmd, {})
    assert refusal is None, f"Valid bwrap launch was unexpectedly refused: {refusal}"


def test_bwrap_sandbox_containment_enforced_on_linux(tmp_path: Path) -> None:
    """AC-1 / Journey 2: bwrap sandbox containment flags remain strictly enforced on Linux."""
    if not sys.platform.startswith("linux"):
        pytest.skip("bwrap sandbox containment tests require Linux")

    w = _require_worker_module()

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    step_run_dir = tmp_path / "step"
    step_run_dir.mkdir()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    runs_root = tmp_path / "runs"
    runs_root.mkdir()

    cmd = w.build_host_sandbox_command(
        "/usr/bin/bwrap",
        ["/bin/echo", "contained"],
        workspace=workspace,
        step_run_dir=step_run_dir,
        scratch_dir=scratch_dir,
        runs_root=runs_root,
    )

    assert cmd[0] == "/usr/bin/bwrap"

    # Mandatory security and namespace isolation flags
    required_flags = [
        "--unshare-pid",
        "--unshare-uts",
        "--unshare-ipc",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "--dev",
        "--proc",
        "--tmpfs",
    ]
    for flag in required_flags:
        assert flag in cmd, f"Mandatory bubblewrap isolation flag missing: {flag}"

    # Verify read-only root mount and tmpfs mounts
    cmd_str = " ".join(shlex.quote(c) for c in cmd)
    assert "--ro-bind / /" in cmd_str or ("--ro-bind" in cmd and "/" in cmd)
    assert "--tmpfs /run" in cmd_str
    assert "--tmpfs /tmp" in cmd_str


def test_user_journey_contract_oracle_integrity() -> None:
    """AC-1 / Journey 3: Manifest is a valid, readable named oracle covering acceptance checks."""
    assert TESTS_MANIFEST.exists(), f"Missing tests manifest: {TESTS_MANIFEST}"
    manifest = _load_json(TESTS_MANIFEST)

    # Schema validation
    if not USER_JOURNEYS_MANIFEST_SCHEMA:
        pytest.skip("USER_JOURNEYS_MANIFEST_SCHEMA is not available (agent_orch absent)")
    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
    errors = list(validator.iter_errors(manifest))
    assert not errors, f"User journeys manifest schema errors: {errors}"

    # Allowlist inspection
    allowlist = manifest.get("command_allowlist", [])
    assert "build/sysdiff" in allowlist

    # Journey inspection
    journeys = manifest.get("journeys", [])
    assert isinstance(journeys, list) and len(journeys) == 21

    # All journeys must map to valid AC identifiers
    all_traces = set()
    for journey in journeys:
        assert isinstance(journey.get("name"), str) and journey["name"]
        authority = journey.get("authority", "author")
        assert authority in JOURNEY_AUTHORITIES
        traces = journey.get("traces_to", [])
        assert isinstance(traces, list) and len(traces) > 0
        for trace in traces:
            assert trace in {"AC-1", "AC-2", "AC-3"}
            all_traces.add(trace)

    assert all_traces == {"AC-1", "AC-2", "AC-3"}, f"Not all ACs traced: {all_traces}"


# ============================================================================
# AC-2: Pre-Exec Payload Measurement and Typed Refusal
# ============================================================================


def test_pre_exec_payload_measurement_within_limits() -> None:
    """AC-2: Pre-exec measurement accurately calculates argv and env sizes within limits."""
    w = _require_worker_module()

    assert w.max_single_launch_entry_bytes() == MAX_ARG_STRLEN
    assert w.max_total_launch_bytes() == HOST_ARG_MAX

    cmd = ["/bin/echo", "hello", "world"]
    env = {"KEY1": "VAL1", "KEY2": "VAL2"}

    report = w.launch_payload_report(cmd, env)
    assert isinstance(report, dict)
    assert report["argument_count"] == 3
    assert report["environment_count"] == 2
    assert report["executable"] == "/bin/echo"
    assert report["single_entry_limit_bytes"] == MAX_ARG_STRLEN
    assert report["total_limit_bytes"] == HOST_ARG_MAX
    assert report["argument_bytes"] > 0
    assert report["environment_bytes"] > 0
    assert report["total_bytes"] == (
        report["argument_bytes"]
        + report["environment_bytes"]
        + (3 + 2 + 2) * 8  # argv pointers + envp pointers overhead on 64-bit
    )

    refusal = w.refuse_oversized_launch(cmd, env)
    assert refusal is None


def test_pre_exec_single_arg_boundary_rejection() -> None:
    """AC-2 / Journey 5: Test boundary payload sizes near the 128 KiB single argument limit."""
    w = _require_worker_module()

    # 1. Single argument of 131,071 chars + 1 trailing NUL = 131,072 bytes (exact limit) -> Accepted
    accepted_arg = "a" * (MAX_ARG_STRLEN - 1)
    refusal = w.refuse_oversized_launch(["/bin/echo", accepted_arg], {})
    assert refusal is None, "Argument exactly at MAX_ARG_STRLEN must not be refused"

    # 2. Single argument of 131,072 chars + 1 trailing NUL = 131,073 bytes (exceeds limit) -> Refused
    rejected_arg = "a" * MAX_ARG_STRLEN
    refusal = w.refuse_oversized_launch(["/bin/echo", rejected_arg], {})
    assert refusal is not None, "Argument exceeding MAX_ARG_STRLEN must be refused fail-closed"
    assert refusal["failure_classification"] == "launch_payload_too_large"
    assert refusal["failure_evidence"]["reason"] == "single_entry_exceeds_max_arg_strlen"
    payload_meta = refusal["failure_evidence"]["launch_payload"]
    assert payload_meta["largest_argument_bytes"] == MAX_ARG_STRLEN + 1
    assert payload_meta["single_entry_limit_bytes"] == MAX_ARG_STRLEN

    # 3. Single environment variable exceeding limit -> Refused
    rejected_env_val = "v" * (MAX_ARG_STRLEN - 2)  # "K=" (2 bytes) + val + NUL > MAX_ARG_STRLEN
    refusal_env = w.refuse_oversized_launch(["/bin/echo"], {"K": rejected_env_val})
    assert refusal_env is not None
    assert refusal_env["failure_classification"] == "launch_payload_too_large"
    assert refusal_env["failure_evidence"]["reason"] == "single_entry_exceeds_max_arg_strlen"


def test_pre_exec_total_argmax_boundary_rejection() -> None:
    """AC-2 / Journey 4: Cumulative argv + envp exceeding ARG_MAX triggers immediate refusal."""
    w = _require_worker_module()

    # Create 25 arguments of 100,000 bytes each (total ~2.5 MiB > 2 MiB ARG_MAX)
    args = ["/bin/echo"] + ["x" * 100000 for _ in range(25)]
    refusal = w.refuse_oversized_launch(args, {})

    assert refusal is not None, "Launch exceeding ARG_MAX must be refused prior to execve"
    assert refusal["failure_classification"] == "launch_payload_too_large"
    assert refusal["failure_evidence"]["reason"] == "total_launch_exceeds_arg_max"
    payload_meta = refusal["failure_evidence"]["launch_payload"]
    assert payload_meta["total_bytes"] > HOST_ARG_MAX
    assert payload_meta["total_limit_bytes"] == HOST_ARG_MAX


def test_typed_refusal_launch_payload_too_large() -> None:
    """AC-2: Refused launches emit LAUNCH_PAYLOAD_TOO_LARGE and classify E2BIG backstops."""
    w = _require_worker_module()

    assert w.LAUNCH_PAYLOAD_TOO_LARGE == "launch_payload_too_large"

    # Refusal metadata structure
    refusal = w.refuse_oversized_launch(["/bin/echo", "x" * 200000], {})
    assert refusal is not None
    assert refusal["failure_classification"] == w.LAUNCH_PAYLOAD_TOO_LARGE
    assert "failure_evidence" in refusal
    assert "launch_payload" in refusal["failure_evidence"]
    assert "operator_guidance" in refusal["failure_evidence"]

    # Test classify_launch_oserror for E2BIG backstop
    e2big_error = OSError(errno.E2BIG, "Argument list too long")
    classified = w.classify_launch_oserror(e2big_error, ["/bin/echo", "x" * 200000], {})
    assert classified is not None
    assert classified["failure_classification"] == w.LAUNCH_PAYLOAD_TOO_LARGE
    assert classified["failure_evidence"]["reason"] == "kernel_e2big"

    # Other OS errors must remain unclassified (not misdiagnosed as payload size issues)
    enoent_error = OSError(errno.ENOENT, "No such file or directory")
    assert w.classify_launch_oserror(enoent_error, ["/nonexistent"], {}) is None
    eacces_error = OSError(errno.EACCES, "Permission denied")
    assert w.classify_launch_oserror(eacces_error, ["/bin/echo"], {}) is None


def test_value_free_diagnostic_evidence_zero_leakage() -> None:
    """AC-2: Diagnostic reports contain numeric metrics and zero substrings of secrets or prompts."""
    w = _require_worker_module()

    secret_prompt = "TOP_SECRET_PROMPT_CONTENT_XYZ_987654321"
    secret_env_name = "CONFIDENTIAL_API_TOKEN_KEY"
    secret_env_value = "SECRET_AUTH_VALUE_ABC_123456789"

    cmd = ["/bin/echo", secret_prompt + ("x" * 200000)]
    env = {secret_env_name: secret_env_value}

    report = w.launch_payload_report(cmd, env)
    refusal = w.refuse_oversized_launch(cmd, env)

    report_json = json.dumps(report)
    refusal_json = json.dumps(refusal)

    # 1. Zero secret leakage
    for secret in (secret_prompt, secret_env_name, secret_env_value):
        assert secret not in report_json, f"Secret leaked in launch_payload_report: {secret}"
        assert secret not in refusal_json, f"Secret leaked in refuse_oversized_launch: {secret}"

    # 2. Presence of structural accounting
    assert report["argument_count"] == 2
    assert report["environment_count"] == 1
    assert report["largest_argument_bytes"] > 200000
    assert report["single_entry_limit_bytes"] == MAX_ARG_STRLEN


def test_manifest_tampering_rejected_by_pinned_oracle(tmp_path: Path) -> None:
    """AC-2 / Journey 6: Pinned journey hash oracle rejects manifest tampering."""
    v = _require_validators_module()
    assert ValidationRule is not None

    manifest = _load_json(TESTS_MANIFEST)
    path = _write_json(tmp_path, "tests/user_journeys_manifest.json", manifest)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    pin_rule = ValidationRule(
        type="file_hash_matches",
        path="tests/user_journeys_manifest.json",
        sha256=digest,
    )

    # Clean check passes
    outcome = v._run_structural_rule(pin_rule, tmp_path)
    assert outcome.passed is True

    # Mutated check fails
    mutated = copy.deepcopy(manifest)
    mutated["command_allowlist"] = ["build/sysdiff", "malicious_cmd"]
    path.write_text(json.dumps(mutated), encoding="utf-8")

    tampered_outcome = v._run_structural_rule(pin_rule, tmp_path)
    assert tampered_outcome.passed is False
    assert "SHA-256 mismatch" in tampered_outcome.message or "mismatch" in tampered_outcome.message.lower()


# ============================================================================
# AC-3: Bounded Validation Output, Test Integrity, and Blast Radius
# ============================================================================


def test_process_output_excerpt_head_tail_bounds() -> None:
    """AC-3 / Journey 7: Process output excerpting bounds stdout/stderr to head/tail slices."""
    v = _require_validators_module()

    assert v.PROCESS_OUTPUT_EXCERPT_HEAD_BYTES == PROCESS_OUTPUT_EXCERPT_HEAD_BYTES
    assert v.PROCESS_OUTPUT_EXCERPT_TAIL_BYTES == PROCESS_OUTPUT_EXCERPT_TAIL_BYTES

    # Short output remains unaltered
    short_text = "Compilation and unit tests passed cleanly.\n"
    assert v.bounded_process_output(short_text, "artifacts/build.log") == short_text

    # Large output (100 KiB) is excerpted
    head_marker = "BUILD_START_COMPILER_FLAGS_HEADER"
    tail_marker = "BUILD_END_TEST_SUITE_COMPLETION_FOOTER"
    head_fill = "H" * 3950
    middle_fill = "M" * 92000
    tail_fill = "T" * 3950

    large_text = f"{head_marker}\n{head_fill}\n{middle_fill}\n{tail_fill}\n{tail_marker}"
    assert len(large_text) > 99000

    bounded = v.bounded_process_output(large_text, "artifacts/build.log")

    assert len(bounded) < 15000, f"Bounded output is unexpectedly large: {len(bounded)} chars"
    assert head_marker in bounded
    assert tail_marker in bounded
    assert "bytes elided from this record" in bounded
    assert "artifacts/build.log" in bounded


def test_retry_packet_size_remains_bounded() -> None:
    """AC-3: Repeated test failures in retry loops do not cause prompt packets to expand without bound."""
    v = _require_validators_module()

    # Simulate 5 consecutive retry attempts with large compiler/test backtraces (50 KiB each)
    simulated_backtrace = "Error: Assertion failed in check_module()\n" + ("E" * 50000)
    artifact_log = "artifacts/attempt-retry.log"

    bounded_excerpts = []
    for _ in range(5):
        excerpt = v.bounded_process_output(simulated_backtrace, artifact_log)
        bounded_excerpts.append(excerpt)

    for excerpt in bounded_excerpts:
        assert len(excerpt) <= 10000, "Excerpt per retry step must remain strictly bounded"
        assert "elided from this record" in excerpt


def test_user_journeys_manifest_synchronization() -> None:
    """AC-3 / Journey 8: tests/user_journeys_manifest.json adheres to schema and contains all journeys."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"

    manifest = json.loads(TESTS_MANIFEST.read_bytes())
    assert len(manifest.get("journeys", [])) == 21
    assert manifest.get("command_allowlist") == ["build/sysdiff"]


def test_sysdiff_product_suite_zero_regressions() -> None:
    """AC-3 / Journey 9: sysdiff product C17 source and test files are intact and unaltered."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0
    assert MAN_PAGE.exists() and MAN_PAGE.stat().st_size > 0

    # Ensure required test files exist
    required_test_files = [
        "tests/test_sysdiff.py",
        "tests/test_sysdiff_fixture.sh",
        "tests/test_sysdiff_benchmark.py",
        "tests/test_sysdiff_malformed_fuzz.py",
    ]
    for rel_path in required_test_files:
        test_file = ROOT / rel_path
        assert test_file.exists(), f"Required product test file missing: {rel_path}"
        assert test_file.stat().st_size > 0

    # sysdiff source must remain pure C17 and contain no orchestrator or bwrap tokens
    src_content = SYSDIFF_SRC.read_text(encoding="utf-8")
    assert "bwrap" not in src_content
    assert "agent_orch" not in src_content


def test_sysdiff_cli_behavior_unaltered(tmp_path: Path) -> None:
    """AC-3 / Journeys 10-13: sysdiff binary CLI contracts remain unaltered."""
    binary = _get_sysdiff_binary(tmp_path)

    # Journey 10: No-arg invocation -> exit code 0, usage guidance on stdout, empty stderr
    no_arg = subprocess.run([str(binary)], capture_output=True, text=True, check=False)
    assert no_arg.returncode == 0
    assert "usage: sysdiff" in no_arg.stdout
    assert no_arg.stderr == ""

    # Journey 11: Help flag -> exit code 0, usage summary on stdout
    help_run = subprocess.run([str(binary), "--help"], capture_output=True, text=True, check=False)
    assert help_run.returncode == 0
    assert "usage" in help_run.stdout.lower() or "sysdiff" in help_run.stdout.lower()

    # Version flag -> exit code 0, version on stdout
    version_run = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=False)
    assert version_run.returncode == 0
    assert "sysdiff" in version_run.stdout.lower()

    # Journey 12: Compare two snapshots -> clean (exit 0) or changed (exit 1)
    f1 = tmp_path / "snap1.snapshot"
    f2 = tmp_path / "snap2.snapshot"
    f1.write_text("sys.key1=value1\nsys.key2=value2\n", encoding="utf-8")
    f2.write_text("sys.key1=value1\nsys.key2=value2\n", encoding="utf-8")

    same_run = subprocess.run([str(binary), "compare", str(f1), str(f2)], capture_output=True, text=True, check=False)
    assert same_run.returncode == 0
    assert same_run.stdout == "no changes\n"
    assert same_run.stderr == ""

    f3 = tmp_path / "snap3.snapshot"
    f3.write_text("sys.key1=value1\nsys.key2=modified\nsys.key3=added\n", encoding="utf-8")

    diff_run = subprocess.run([str(binary), "compare", str(f1), str(f3)], capture_output=True, text=True, check=False)
    assert diff_run.returncode == 1
    assert "~ sys.key2: value2 -> modified\n" in diff_run.stdout
    assert "+ sys.key3=added\n" in diff_run.stdout
    assert diff_run.stderr == ""

    # Journey 13: Malformed snapshot -> exit code 2 with diagnostic on stderr without partial stdout
    f_malformed = tmp_path / "malformed.snapshot"
    f_malformed.write_text("invalid line without equals separator\n", encoding="utf-8")

    malformed_run = subprocess.run(
        [str(binary), "compare", str(f1), str(f_malformed)], capture_output=True, text=True, check=False
    )
    assert malformed_run.returncode == 2
    assert malformed_run.stdout == ""
    assert "missing '='" in malformed_run.stderr.lower() or "error" in malformed_run.stderr.lower()
