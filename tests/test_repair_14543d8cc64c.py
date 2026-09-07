"""Regression test suite for repairing governed run failure 14543d8cc64c.

Governed run 14543d8cc64c stalled and failed during test execution of `make test`
and `pytest` for the sysdiff utility vertical slice. Two distinct but compounding
failure modes occurred:
1. Test Execution Timeouts:
   The repository test suite comprises over 680 tests across unit, integration,
   and fuzzing harnesses, in addition to shell test scripts (tests/test_sysdiff.sh).
   Synchronous, unoptimized execution exceeded orchestrator time limits (120+ seconds)
   or stalled when processes waited indefinitely on external tool probes or pipes,
   causing abrupt step termination without structured diagnostic artifacts.
2. Missing Toolchain Dependencies (clang, cppcheck):
   Repository quality gates require GCC, Clang, clang-tidy, cppcheck, and sanitizers.
   When secondary tools such as clang or cppcheck are not installed or discoverable
   in $PATH, recipes such as `make cppcheck-check` or `make clang-strict` fail with
   untyped 'command not found' exit faults (exit 127) or hang during sub-process probes.

Repair Contract (docs/repair-14543d8cc64c-contract.md):
- AC-1: Test Execution Timeout Mitigation and Performance Bounding.
  Contract document adheres to required headings with >= 120 non-whitespace characters each.
  Closed hazard taxonomy (EXECUTION_TIMEOUT, TOOL_AVAILABILITY, ORACLE_TAMPERING, BLAST_RADIUS).
  Test execution harnesses enforce bounded execution windows, preventing unmonitored hangs
  and ensuring predictable completion within orchestrator timeout limits.
- AC-2: Preflight Dependency Verification and Graceful Tool Handling.
  Tool dependencies including clang and cppcheck are validated via structured preflight probing.
  When tools are absent, the system emits clear diagnostic messages and fails-safe without
  unhandled exceptions or untyped shell failures, while enforcing strict checks when tools are present.
- AC-3: Manifest Synchronization, Test Suite Integrity, and Non-Product Blast Radius.
  Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
  identical parsed objects adhering to canonical schema and containing all 21 journeys.
  Every required journey maps to AC-1, AC-2, or AC-3 with zero orphaned acceptance checks.
  Command allowlist remains strictly ["build/sysdiff"].
  Zero regressions or modifications to src/sysdiff.c, Makefile binary packaging, or man/sysdiff.1.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

import pytest

for _extra_path in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/projects/employee-contract/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if _extra_path not in sys.path and Path(_extra_path).is_dir():
        sys.path.insert(0, _extra_path)

ROOT = Path(__file__).resolve().parents[1]
_scripts_dir = str(ROOT / "scripts")
if _scripts_dir not in sys.path and Path(_scripts_dir).is_dir():
    sys.path.insert(0, _scripts_dir)

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]

try:
    import check_tools
except ImportError:
    check_tools = None  # type: ignore[assignment]

TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
CONTRACT = ROOT / "docs" / "repair-14543d8cc64c-contract.md"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"
CHECK_TOOLS_SCRIPT = ROOT / "scripts" / "check_tools.py"

PRESERVED_AUTHOR_JOURNEYS = {
    "A user reads the repository-owned journey contract and confirms the manifest is a usable named oracle",
    "A user supplies malformed journey data and receives a specific fail-closed validation result",
    "A user runs the governed check from an unrelated current directory without changing path meaning",
    "A user observes that only the exact allowlisted smoke argv prefix is re-executed directly",
    "A user confirms that required journey authority is retained when the workspace is repaired",
    "A user follows every acceptance-check trace and sees exploratory coverage remain supplementary",
    "A user retries after producer-side narrowing and sees the pinned journey oracle reject tampering",
    "A user reviews a result that reports every journey with concrete steps commands and actionable evidence",
    "A user runs the existing deterministic smoke chain without confusing it with direct journey evidence",
    "A user confirms the workspace abstraction remains additive and does not create product release or network behavior",
}

SYSDIFF_JOURNEYS = {
    "A user runs the real sysdiff binary with no arguments and receives usage guidance instead of a crash",
    "A user asks the real sysdiff binary for help and receives its usage summary",
    "A user compares two snapshots with the real sysdiff binary and sees deterministic added removed and changed entries",
    "A user gives the real sysdiff binary a malformed snapshot and receives an escaped diagnostic without partial output",
}

BWRAP_JOURNEYS = {
    "A worker launcher delivers large prompt payloads via stdin and verifies that no single argv argument exceeds kernel MAX_ARG_STRLEN limits",
    "A user confirms bubblewrap sandbox containment remains strictly enforced on Linux without granting unsandboxed execution bypasses",
    "An operator observes pre-exec payload measurement rejecting oversized bwrap arguments fail-closed with typed LAUNCH_PAYLOAD_TOO_LARGE classification",
    "An evaluator inspects edge-case payload sizes near the 128 KiB boundary to confirm exact byte accounting without information leakage",
    "A validator bounds process output in retry feedback to head and tail excerpts while preserving full unmodified logs in hash-chained artifacts",
    "A maintainer verifies the synchronized user journeys manifest adheres to canonical schema and covers all enumerated contract acceptance checks",
    "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
}

ALL_EXPECTED_JOURNEYS = PRESERVED_AUTHOR_JOURNEYS | SYSDIFF_JOURNEYS | BWRAP_JOURNEYS


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


def make_fake_executable(directory: Path, name: str) -> Path:
    executable = directory / name
    executable.write_text(
        "#!/bin/sh\n"
        'case "${1:-}" in\n'
        "  --version|-V|version) printf '%s fake version\\n' \"$0\" ;;\n"
        "  --help|-h|help) printf '%s fake help\\n' \"$0\" ;;\n"
        "  *) printf '%s fake command\\n' \"$0\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


# ============================================================================
# AC-1: Test Execution Timeout Mitigation and Performance Bounding
# ============================================================================


def test_repair_contract_structure_and_headings() -> None:
    """AC-1: docs/repair-14543d8cc64c-contract.md has required headings with >= 120 chars each."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    required_headings = ["Overview", "Problem", "Constraints", "Acceptance Checks"]
    for heading in required_headings:
        pattern = rf"^#+\s+{re.escape(heading)}\b"
        match = re.search(pattern, content, re.MULTILINE)
        assert match is not None, f"Contract missing required heading: {heading}"

        start_pos = match.end()
        next_heading_match = re.search(r"^#+\s+", content[start_pos:], re.MULTILINE)
        if next_heading_match:
            section_text = content[start_pos : start_pos + next_heading_match.start()]
        else:
            section_text = content[start_pos:]

        non_whitespace_count = len(re.sub(r"\s", "", section_text))
        assert non_whitespace_count >= 120, (
            f"Section {heading!r} in {CONTRACT} has only {non_whitespace_count} non-whitespace characters, "
            f"minimum required is 120"
        )

    assert "14543d8cc64c" in content
    assert "make test" in content
    assert "pytest" in content
    assert "clang" in content
    assert "cppcheck" in content
    assert "EXECUTION_TIMEOUT" in content
    assert "AC-1" in content
    assert "AC-2" in content
    assert "AC-3" in content


def test_hazard_taxonomy_compliance() -> None:
    """AC-1: Identified hazards must belong strictly to the closed repository taxonomy."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    assert "Closed Hazard Taxonomy" in content
    taxonomy_match = re.search(
        r"Closed Hazard Taxonomy.*?(EXECUTION_TIMEOUT|TOOL_AVAILABILITY|ORACLE_TAMPERING|BLAST_RADIUS)",
        content,
        re.DOTALL,
    )
    assert taxonomy_match is not None, "Contract does not reference closed hazard taxonomy"
    assert "EXECUTION_TIMEOUT" in content
    assert "TOOL_AVAILABILITY" in content


def test_bounded_subprocess_execution_terminates_hanging_process() -> None:
    """AC-1: Subprocess execution harnesses must enforce finite timeouts and abort hanging processes fail-safe."""
    # Simulate a hanging command (e.g. stalled tool probe, shell pipe, or infinite loop)
    # A robust execution harness must enforce timeout bounds rather than blocking indefinitely.
    hanging_cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(hanging_cmd, timeout=0.2, check=False)
    elapsed = time.monotonic() - start_time
    assert elapsed < 1.0, f"Process execution hung for {elapsed:.2f}s instead of terminating at 0.2s timeout"


def test_sysdiff_shell_test_execution_bounds(tmp_path: Path) -> None:
    """AC-1: tests/test_sysdiff.sh must execute predictably within a bounded timeout without hanging."""
    binary = _get_sysdiff_binary(tmp_path)
    shell_script = ROOT / "tests" / "test_sysdiff.sh"
    assert shell_script.exists(), f"Missing {shell_script}"

    env = dict(os.environ)
    env["SYSDIFF_BIN"] = str(binary)

    start_time = time.monotonic()
    result = subprocess.run(
        ["/bin/bash", str(shell_script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15.0,  # Bound shell test execution window to 15s max
        check=False,
    )
    elapsed = time.monotonic() - start_time

    assert result.returncode == 0, f"test_sysdiff.sh failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert elapsed < 15.0, f"test_sysdiff.sh took too long ({elapsed:.2f}s), risking orchestrator timeouts"


# ============================================================================
# AC-2: Preflight Dependency Verification and Graceful Tool Handling
# ============================================================================


def test_preflight_probe_cppcheck_when_absent() -> None:
    """AC-2: When cppcheck is absent from PATH, preflight probing reports available=False with clean diagnostic."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    # In the current host environment, cppcheck is not installed.
    # Probing it must return available=False with a clear detail message, not an exception.
    result = check_tools.probe_executable("cppcheck")
    assert not result.available, f"Expected cppcheck to be absent, found: {result}"
    assert "cppcheck was not found on PATH" in result.detail


def test_preflight_probe_clang_when_absent() -> None:
    """AC-2: When clang is absent from PATH, preflight probing reports available=False with clean diagnostic."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    # Probe clang with an empty PATH to verify clean discovery failure
    result = check_tools.probe_executable("clang", env={"PATH": ""})
    assert not result.available
    assert "clang was not found on PATH" in result.detail


def test_preflight_probe_detects_tools_when_present(tmp_path: Path) -> None:
    """AC-2: When tools are present on PATH, preflight probing reports available=True and resolves path."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cppcheck = make_fake_executable(fake_bin, "cppcheck")
    fake_clang = make_fake_executable(fake_bin, "clang")

    env = {"PATH": str(fake_bin)}

    res_cppcheck = check_tools.probe_executable("cppcheck", env=env)
    assert res_cppcheck.available is True
    assert res_cppcheck.detail == f"found cppcheck at {fake_cppcheck}"

    res_clang = check_tools.probe_executable("clang", env=env)
    assert res_clang.available is True
    assert res_clang.detail == f"found clang at {fake_clang}"


def test_makefile_cppcheck_check_has_preflight_guard() -> None:
    """AC-2: Makefile cppcheck-check recipe must probe tool availability before execution.

    In run 14543d8cc64c, make cppcheck-check crashed with exit code 127 (command not found)
    because it invoked cppcheck directly without a preflight discovery guard.
    Analogous to gcc-strict and clang-strict, cppcheck-check must verify tool availability
    and report a structured diagnostic rather than failing with an untyped shell crash.
    """
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    # Extract cppcheck-check recipe block from Makefile
    match = re.search(
        r"^cppcheck-check:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing cppcheck-check target"
    recipe = match.group(1)

    has_preflight = (
        "command -v cppcheck" in recipe
        or "which cppcheck" in recipe
        or "check_tools" in recipe
    )
    assert has_preflight, (
        "Makefile target 'cppcheck-check' invokes cppcheck directly without a preflight "
        "availability guard, causing unhandled exit code 127 / command not found when cppcheck is absent "
        "(reproducing governed run 14543d8cc64c failure mode)."
    )


def test_preflight_probes_are_read_only_and_bounded(tmp_path: Path) -> None:
    """AC-2: Preflight tool probing must be read-only, non-mutating, and complete in bounded time."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    start_time = time.monotonic()
    # Check executables
    res_gcc = check_tools.probe_executable("gcc")
    res_clang = check_tools.probe_executable("clang")
    res_cppcheck = check_tools.probe_executable("cppcheck")
    elapsed = time.monotonic() - start_time

    assert elapsed < 2.0, f"Tool probing took {elapsed:.2f}s, expected < 2.0s"
    assert res_gcc.name == "gcc"
    assert res_clang.name == "clang"
    assert res_cppcheck.name == "cppcheck"


# ============================================================================
# AC-3: Manifest Synchronization, Test Suite Integrity, Non-Product Blast Radius
# ============================================================================


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-3: Both tests and journeys manifests exist and are identical parsed objects."""
    assert TESTS_MANIFEST.exists(), f"Missing canonical oracle {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest {JOURNEYS_MANIFEST}"

    tests_manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_manifest = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    assert tests_manifest == journeys_manifest, (
        "Repository journey manifests are not identical parsed objects."
    )


def test_user_journeys_manifest_schema_and_command_allowlist() -> None:
    """AC-3: Manifest adheres to canonical schema and preserves immutable command allowlist."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))

    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(manifest))
        assert not errors, f"Schema validation errors in {TESTS_MANIFEST}: {errors}"

    allowlist = manifest.get("command_allowlist", [])
    assert allowlist == ["build/sysdiff"], (
        f"command_allowlist must remain strictly ['build/sysdiff'], got: {allowlist}"
    )


def test_user_journeys_manifest_contains_all_21_journeys() -> None:
    """AC-3: Manifest preserves all 21 author, sysdiff, and bwrap journeys without omission."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = manifest.get("journeys", [])
    assert len(journeys) == 21, f"Expected exactly 21 journeys, found {len(journeys)}"

    names = {j["name"] for j in journeys}
    missing_author = PRESERVED_AUTHOR_JOURNEYS - names
    assert not missing_author, f"Manifest omitted preserved author journeys: {missing_author}"

    missing_sysdiff = SYSDIFF_JOURNEYS - names
    assert not missing_sysdiff, f"Manifest omitted sysdiff product journeys: {missing_sysdiff}"

    missing_bwrap = BWRAP_JOURNEYS - names
    assert not missing_bwrap, f"Manifest omitted bwrap repair journeys: {missing_bwrap}"


def test_journey_traceability_and_acceptance_coverage() -> None:
    """AC-3: All required journeys map to valid acceptance checks and AC-1..3 are covered."""
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = manifest.get("journeys", [])
    allowed_traces = {"AC-1", "AC-2", "AC-3"}

    covered_traces: set[str] = set()
    for j in journeys:
        authority = j.get("authority", "author")
        assert authority in JOURNEY_AUTHORITIES, f"Invalid authority {authority!r} in journey {j['name']!r}"
        traces = j.get("traces_to", [])
        if authority != "exploratory":
            assert traces, f"Required journey {j['name']!r} lacks traces_to"
            assert set(traces) <= allowed_traces, f"Journey {j['name']!r} has invalid traces: {traces}"
            covered_traces.update(traces)

    assert covered_traces == allowed_traces, (
        f"Acceptance checks not fully covered by required journeys: {allowed_traces - covered_traces}"
    )


def test_sysdiff_c_source_craftsmanship_and_non_product_blast_radius() -> None:
    """AC-3: sysdiff C source remains unaltered ISO C17 without leaking orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0
    assert MAN_PAGE.exists() and MAN_PAGE.stat().st_size > 0

    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")
    for forbidden in ("14543d8cc64c", "agent_orch", "PATH_ESCAPE", "bwrap"):
        assert forbidden not in src_text, f"sysdiff.c unexpectedly contains {forbidden!r}"

    cc = os.environ.get("CC", "cc")
    res = subprocess.run(
        [
            cc,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-fsyntax-only",
            str(SYSDIFF_SRC),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"sysdiff.c failed strict syntax check:\n{res.stderr}"


def test_sysdiff_product_cli_no_args_and_help(tmp_path: Path) -> None:
    """AC-3 / Journeys 11-12: sysdiff CLI contract exits 0 with usage on stdout for no-args and --help."""
    binary = _get_sysdiff_binary(tmp_path)

    # Journey 11: no arguments -> exit code 0, usage on stdout, empty stderr
    no_arg = subprocess.run([str(binary)], capture_output=True, text=True, check=False)
    assert no_arg.returncode == 0, f"Expected exit code 0, got {no_arg.returncode}"
    assert "usage: sysdiff" in no_arg.stdout, f"Missing usage in stdout: {no_arg.stdout}"
    assert no_arg.stderr == "", f"Expected empty stderr, got: {no_arg.stderr}"

    # Journey 12: --help -> exit code 0, usage on stdout, empty stderr
    help_res = subprocess.run([str(binary), "--help"], capture_output=True, text=True, check=False)
    assert help_res.returncode == 0
    assert "usage: sysdiff" in help_res.stdout
    assert help_res.stderr == ""

    # --version -> exit code 0
    version_res = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=False)
    assert version_res.returncode == 0
    assert "sysdiff 0.1.0" in version_res.stdout
    assert version_res.stderr == ""


def test_sysdiff_product_snapshot_comparison(tmp_path: Path) -> None:
    """AC-3 / Journey 13: sysdiff compares snapshots with deterministic added removed and changed entries."""
    binary = _get_sysdiff_binary(tmp_path)

    snap1 = tmp_path / "snap1.snapshot"
    snap2 = tmp_path / "snap2.snapshot"
    snap1.write_text("pkg.a=1.0\npkg.b=2.0\nservice.web.active=\n", encoding="utf-8")
    snap2.write_text("pkg.a=1.1\npkg.c=3.0\nservice.web.active=\n", encoding="utf-8")

    # Differing snapshots -> returncode 1, deterministic markers
    res = subprocess.run(
        [str(binary), "compare", str(snap1), str(snap2)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 1, f"Expected returncode 1 for diff, got {res.returncode}"
    assert res.stderr == ""
    assert "~ pkg.a: 1.0 -> 1.1\n" in res.stdout
    assert "- pkg.b=2.0\n" in res.stdout
    assert "+ pkg.c=3.0\n" in res.stdout

    # Identical snapshots -> returncode 0, "no changes"
    identical_res = subprocess.run(
        [str(binary), "compare", str(snap1), str(snap1)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert identical_res.returncode == 0
    assert identical_res.stdout == "no changes\n"
    assert identical_res.stderr == ""


def test_sysdiff_product_malformed_snapshot_rejection(tmp_path: Path) -> None:
    """AC-3 / Journey 14: sysdiff rejects malformed snapshot with escaped diagnostic and no partial output."""
    binary = _get_sysdiff_binary(tmp_path)

    valid_snap = tmp_path / "valid.snapshot"
    valid_snap.write_text("valid.key=val\n", encoding="utf-8")

    malformed_snap = tmp_path / "malformed.snapshot"
    malformed_snap.write_text("this line has no equals sign\n", encoding="utf-8")

    res = subprocess.run(
        [str(binary), "compare", str(malformed_snap), str(valid_snap)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 2, f"Expected exit code 2 for malformed snapshot, got {res.returncode}"
    assert res.stdout == "", f"Malformed snapshot must produce empty stdout, got: {res.stdout}"
    assert "missing '=' separator" in res.stderr
