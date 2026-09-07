"""Regression test suite for repairing governed run failure 97e798a99010.

Governed run 97e798a99010 failed during worker initialization because the smoke check
failed to pass before the startup timeout elapsed:
    Worker exited with non-zero code 1: Smoke check did not pass before startup timeout.

Failure analysis and root causes:
1. Smoke Check Startup Window vs. Heavy Execution Workloads:
   The Agent-Orch smoke runner relies on tests/smoke_manifest.json to manage worker
   process startup and health verification. The manifest declares startup and check
   parameters, including start_command (["python3", "tests/smoke_start.py"]),
   check_command (["python3", "tests/check_sysdiff_smoke.py"]),
   startup_timeout_seconds: 10, poll_interval_seconds: 0.25, and check_timeout_seconds: 300.
   In run 97e798a99010, the orchestrator launched a worker process and polled for smoke
   readiness. The smoke check did not complete and report success within the 10-second
   startup_timeout_seconds window, causing the orchestrator watchdog to abort the worker
   fail-closed with exit code 1.

2. Coupling of Smoke Verification to Full Test Suite Execution:
   In the pre-remediation architecture, tests/check_sysdiff_smoke.py invokes
   bash scripts/smoke.sh, which executes make test. In the Makefile, the test target
   delegates directly to test-suite, which rebuilds the C binary build/sysdiff, runs
   shell fixture tests (tests/test_sysdiff.sh), and then executes the full pytest suite
   across hundreds of test cases. Executing compilation, shell fixtures, and full pytest
   routinely exceeds the 10-second startup_timeout_seconds limit, causing the smoke check
   to fail to report success before the startup timeout expires.

3. Need for Startup Timeout Hardening and Bounded Execution:
   To resolve this failure, smoke verification must adhere strictly to startup timeout
   constraints. Initial startup verification must confirm basic worker readiness and
   binary functionality rapidly (well within the 10-second startup timeout budget),
   while allowing comprehensive quality and regression suites to execute under their
   separate make test and release quality gates. Supervised remediation now uses
   tiny status-0/1/2 compare fixtures with ten-second startup and check budgets.

Repair Contract Reference: docs/repair-97e798a99010-contract.md
Sealed Evidence Directory: /home/lee/projects/linux-utilities-agent-orch-runs/97e798a99010

Acceptance Checks:
- AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement.
  Contract document adheres to required headings with >= 120 non-whitespace characters each.
  Closed hazard taxonomy (EXECUTION_TIMEOUT, TOOL_AVAILABILITY, PATH_ESCAPE,
  RESULT_FABRICATION, ORACLE_TAMPERING, BLAST_RADIUS). Sealed evidence directory explicitly cited.
  Workspace root remains clean of ad-hoc scripts, with scratch confined to .agent-orch-scratch/.
- AC-2: Smoke Check Startup Timeout Compliance and Bounded Verification.
  The smoke check and worker startup pipeline execute reliably within allocated startup timeout
  limits, eliminating the 'Smoke check did not pass before startup timeout.' failure mode.
  Startup helper and smoke check scripts initialize, verify binary readiness, and pass within
  the designated startup_timeout_seconds budget without unmonitored hangs or timeout aborts.
- AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius.
  Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
  identical parsed objects adhering to canonical schema and containing all 21 journeys.
  Every required journey maps to AC-1, AC-2, or AC-3 with zero orphaned acceptance checks.
  Command allowlist remains strictly ["build/sysdiff"]. Zero modifications or regressions to
  src/sysdiff.c, Makefile binary targets, or man/sysdiff.1.
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

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
    from agent_orch.worker import SmokeTestAdapter, WorkerResult
except ImportError:
    SmokeTestAdapter = None  # type: ignore[assignment]
    WorkerResult = None  # type: ignore[assignment]

try:
    from agent_orch.validators import (
        ValidationOutcome,
        ValidationRule,
        _run_markdown_headings_rule,
    )
except ImportError:
    ValidationOutcome = None  # type: ignore[assignment]
    ValidationRule = None  # type: ignore[assignment]
    _run_markdown_headings_rule = None  # type: ignore[assignment]

try:
    from agent_orch.models import StepDefinition
    from agent_orch.engine import _allowed_path_outcomes
except ImportError:
    StepDefinition = None  # type: ignore[assignment]
    _allowed_path_outcomes = None  # type: ignore[assignment]

CONTRACT = ROOT / "docs" / "repair-97e798a99010-contract.md"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SMOKE_MANIFEST = ROOT / "tests" / "smoke_manifest.json"
SMOKE_START = ROOT / "tests" / "smoke_start.py"
SMOKE_CHECK = ROOT / "tests" / "check_sysdiff_smoke.py"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke.sh"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"
SEALED_EVIDENCE_DIR = "/home/lee/projects/linux-utilities-agent-orch-runs/97e798a99010"

CLOSED_HAZARD_TAXONOMY = (
    "EXECUTION_TIMEOUT",
    "TOOL_AVAILABILITY",
    "PATH_ESCAPE",
    "RESULT_FABRICATION",
    "ORACLE_TAMPERING",
    "BLAST_RADIUS",
)

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


@dataclass
class _MockStepDefinition:
    inputs: list[str] = field(default_factory=list)
    structural_validations: list[Any] = field(default_factory=list)
    system_validations: list[Any] = field(default_factory=list)


@dataclass
class _MockStepContext:
    workspace: Path
    step: _MockStepDefinition = field(default_factory=_MockStepDefinition)
    auth_home: Path | None = None
    step_run_dir: Path | None = None
    scratch_dir: Path | None = None


def _get_sysdiff_binary(tmp_path: Path | None = None) -> Path:
    """Return the sysdiff binary, compiling via make or gcc if necessary."""
    binary = ROOT / "build" / "sysdiff"
    if binary.exists() and os.access(binary, os.X_OK):
        return binary

    make_cmd = shutil.which("make")
    if make_cmd is not None:
        res = subprocess.run(
            [make_cmd, "build/sysdiff"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and binary.exists():
            return binary

    gcc_cmd = shutil.which("gcc")
    if gcc_cmd is not None:
        out_dir = tmp_path if tmp_path is not None else ROOT / "build"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_bin = out_dir / "sysdiff"
        res = subprocess.run(
            [
                gcc_cmd,
                "-std=c17",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                str(SYSDIFF_SRC),
                "-o",
                str(out_bin),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and out_bin.exists():
            return out_bin

    pytest.skip("sysdiff binary could not be located or compiled")


# ============================================================================
# AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement
# ============================================================================


def test_repair_contract_structure_and_headings() -> None:
    """AC-1: docs/repair-97e798a99010-contract.md has required headings with >= 120 chars each."""
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

    assert "97e798a99010" in content
    assert "startup timeout" in content.lower()
    assert "EXECUTION_TIMEOUT" in content
    assert "AC-1" in content
    assert "AC-2" in content
    assert "AC-3" in content

    if _run_markdown_headings_rule is not None and ValidationRule is not None:
        r_contract = ValidationRule(
            type="markdown_headings",
            path="docs/repair-97e798a99010-contract.md",
            headings=["# Overview", "# Problem", "# Constraints", "# Acceptance Checks"],
            min_chars_under_heading=120,
        )
        outcome_contract = _run_markdown_headings_rule(r_contract, CONTRACT)
        assert outcome_contract.passed is True, f"Contract failed validator rule: {outcome_contract.message}"


def test_sealed_evidence_reference_integrity() -> None:
    """AC-1: Contract explicitly cites sealed evidence directory /home/lee/projects/linux-utilities-agent-orch-runs/97e798a99010."""
    assert CONTRACT.exists()
    content = CONTRACT.read_text(encoding="utf-8")
    assert SEALED_EVIDENCE_DIR in content, (
        f"Contract missing exact sealed evidence path citation: {SEALED_EVIDENCE_DIR}"
    )
    assert "97e798a99010" in content


def test_closed_hazard_taxonomy_compliance() -> None:
    """AC-1: Identified hazards must belong strictly to the closed repository taxonomy."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    assert "Closed Hazard Taxonomy" in content
    for hazard in CLOSED_HAZARD_TAXONOMY:
        assert hazard in content, f"Contract missing hazard taxonomy term: {hazard}"

    assert "EXECUTION_TIMEOUT" in content


def test_write_scope_confinement_and_workspace_cleanliness() -> None:
    """AC-1: Workspace root has zero unauthorized ad-hoc scripts; scratch is isolated in .agent-orch-scratch/."""
    adhoc_scripts = [
        "generate_result.py",
        "generate_result2.py",
        "test_script.py",
        "update_md.py",
        "temp_test.py",
        "eval_test.py",
        "scratch.py",
    ]
    found = [script for script in adhoc_scripts if (ROOT / script).exists()]
    assert not found, (
        f"AC-1 violation: Ad-hoc scripts detected in workspace root: {found}. "
        f"All scratch files must be confined to .agent-orch-scratch/."
    )

    scratch_root = ROOT / ".agent-orch-scratch"
    assert scratch_root.exists(), "Scratch root .agent-orch-scratch/ must exist for governed scratch storage"

    if _allowed_path_outcomes is not None and StepDefinition is not None:
        step = StepDefinition(
            step_id="step_02_author_repair_tests",
            name="Author the repair tests",
            worker="codex_cli",
            allowed_paths=["tests"],
        )
        outcomes = _allowed_path_outcomes(
            step,
            [
                "tests/test_repair_97e798a99010.py",
                "unauthorized_root.py",
                "artifacts/escape.json",
            ],
        )
        assert outcomes[0].passed is True, "Allowed test path was improperly rejected"
        assert outcomes[1].passed is False, "Unauthorized root file was improperly allowed"
        assert "outside allowed_paths" in outcomes[1].message
        assert outcomes[2].passed is False, "Unauthorized artifact write was improperly allowed"


# ============================================================================
# AC-2: Smoke Check Startup Timeout Compliance and Bounded Verification
# ============================================================================


def test_smoke_manifest_structure_and_parameters() -> None:
    """AC-2: tests/smoke_manifest.json exists, is valid JSON, and defines required parameters."""
    assert SMOKE_MANIFEST.exists(), f"Missing smoke manifest: {SMOKE_MANIFEST}"
    manifest = json.loads(SMOKE_MANIFEST.read_text(encoding="utf-8"))

    required_keys = {
        "start_command",
        "check_command",
        "startup_timeout_seconds",
        "poll_interval_seconds",
        "check_timeout_seconds",
        "steps",
    }
    missing_keys = required_keys - set(manifest.keys())
    assert not missing_keys, f"Smoke manifest missing required keys: {missing_keys}"

    start_cmd = manifest["start_command"]
    check_cmd = manifest["check_command"]
    assert isinstance(start_cmd, list) and len(start_cmd) >= 2, f"Invalid start_command: {start_cmd}"
    assert isinstance(check_cmd, list) and len(check_cmd) >= 2, f"Invalid check_command: {check_cmd}"

    startup_timeout = manifest["startup_timeout_seconds"]
    check_timeout = manifest["check_timeout_seconds"]
    poll_interval = manifest["poll_interval_seconds"]

    assert isinstance(startup_timeout, (int, float)) and startup_timeout >= 1.0, (
        f"startup_timeout_seconds must be a number >= 1.0, got: {startup_timeout}"
    )
    assert isinstance(check_timeout, (int, float)) and check_timeout >= startup_timeout, (
        f"check_timeout_seconds ({check_timeout}) must be >= startup_timeout_seconds ({startup_timeout})"
    )
    assert isinstance(poll_interval, (int, float)) and 0 < poll_interval <= 1.0, (
        f"poll_interval_seconds must be positive and <= 1.0, got: {poll_interval}"
    )

    steps = manifest["steps"]
    assert isinstance(steps, list) and len(steps) >= 1, "steps in smoke manifest must be a non-empty list"


def test_smoke_start_helper_initialization() -> None:
    """AC-2: tests/smoke_start.py compiles cleanly and can be invoked as a helper process."""
    assert SMOKE_START.exists(), f"Missing start helper: {SMOKE_START}"

    # Verify python syntax
    py_compile.compile(str(SMOKE_START), doraise=True)

    # Run the start helper; it must execute without unhandled exception
    res = subprocess.run(
        [sys.executable, str(SMOKE_START)],
        capture_output=True,
        text=True,
        check=False,
        timeout=5.0,
    )
    assert res.returncode == 0, f"smoke_start.py failed with exit {res.returncode}:\nstderr: {res.stderr}"


def test_smoke_check_script_syntax_and_executability() -> None:
    """AC-2: tests/check_sysdiff_smoke.py and scripts/smoke.sh are syntactically valid."""
    assert SMOKE_CHECK.exists(), f"Missing smoke check script: {SMOKE_CHECK}"
    py_compile.compile(str(SMOKE_CHECK), doraise=True)

    assert SMOKE_SCRIPT.exists(), f"Missing smoke script: {SMOKE_SCRIPT}"
    res = subprocess.run(["bash", "-n", str(SMOKE_SCRIPT)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"scripts/smoke.sh has bash syntax errors:\n{res.stderr}"


def test_smoke_check_completes_within_startup_timeout_budget() -> None:
    """AC-2: Smoke check execution must complete and pass within startup_timeout_seconds.

    In governed run 97e798a99010, the worker failed with:
        'Worker exited with non-zero code 1: Smoke check did not pass before startup timeout.'
    because the smoke check exceeded the 10-second startup timeout.
    This test verifies that the smoke check command finishes cleanly (exit code 0)
    strictly within the startup_timeout_seconds threshold defined in tests/smoke_manifest.json.
    Supervised remediation replaces recursive full-suite execution with bounded
    status-0/1/2 fixture comparisons; both manifest budgets remain ten seconds.
    """
    assert SMOKE_MANIFEST.exists(), f"Missing {SMOKE_MANIFEST}"
    manifest = json.loads(SMOKE_MANIFEST.read_text(encoding="utf-8"))
    startup_timeout = float(manifest["startup_timeout_seconds"])
    assert startup_timeout == manifest["check_timeout_seconds"] == 10
    check_command = manifest["check_command"]

    start_time = time.monotonic()
    try:
        res = subprocess.run(
            check_command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=startup_timeout,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start_time
        pytest.fail(
            f"Smoke check timed out after {elapsed:.2f}s, exceeding startup timeout limit of {startup_timeout}s. "
            f"(Reproducing governed run 97e798a99010 failure: Smoke check did not pass before startup timeout)."
        )

    elapsed = time.monotonic() - start_time
    assert res.returncode == 0, (
        f"Smoke check failed with exit code {res.returncode} in {elapsed:.2f}s:\n"
        f"stdout: {res.stdout}\nstderr: {res.stderr}"
    )
    assert elapsed < startup_timeout, (
        f"Smoke check took {elapsed:.2f}s, which exceeds startup timeout limit of {startup_timeout}s."
    )


def test_smoke_check_verifies_sysdiff_binary_functionality(tmp_path: Path) -> None:
    """AC-2: sysdiff binary is operational and executable directly without shell escapes."""
    binary = _get_sysdiff_binary(tmp_path)
    assert binary.exists() and os.access(binary, os.X_OK)

    # Basic binary sanity check
    res_help = subprocess.run([str(binary), "--help"], capture_output=True, text=True, check=False)
    assert res_help.returncode == 0
    assert "usage: sysdiff" in res_help.stdout

    res_version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=False)
    assert res_version.returncode == 0
    assert "sysdiff 0.1.0" in res_version.stdout


def test_smoke_runner_adapter_reproduces_failure_mode_on_timeout() -> None:
    """AC-2: SmokeTestAdapter reports exact 'Smoke check did not pass before startup timeout.' on timeout."""
    if SmokeTestAdapter is None:
        pytest.skip("SmokeTestAdapter not importable from agent_orch.worker")

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        tests_dir = ws / "tests"
        tests_dir.mkdir()

        (tests_dir / "start.py").write_text("import time; time.sleep(5)\n", encoding="utf-8")
        (tests_dir / "check.py").write_text("import sys; sys.exit(1)\n", encoding="utf-8")

        manifest = {
            "start_command": ["python3", "tests/start.py"],
            "check_command": ["python3", "tests/check.py"],
            "startup_delay_seconds": 0,
            "startup_timeout_seconds": 0.25,
            "poll_interval_seconds": 0.05,
            "check_timeout_seconds": 1.0,
        }
        (tests_dir / "smoke_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        ctx = _MockStepContext(workspace=ws)
        adapter = SmokeTestAdapter()
        res = adapter.run(ctx)

        assert res.success is False
        assert res.exit_code == 1
        assert "Smoke check did not pass before startup timeout." in res.stderr

        result_json_path = ws / "artifacts" / "user-smoke" / "result.json"
        assert result_json_path.exists()
        result_data = json.loads(result_json_path.read_text(encoding="utf-8"))
        assert result_data["core_flow_completed"] is False
        assert "Smoke check did not pass before startup timeout." in result_data["blocking_errors"]


def test_smoke_runner_adapter_passes_with_bounded_smoke_check() -> None:
    """AC-2: SmokeTestAdapter completes cleanly when smoke check passes within startup timeout."""
    if SmokeTestAdapter is None:
        pytest.skip("SmokeTestAdapter not importable from agent_orch.worker")

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        tests_dir = ws / "tests"
        tests_dir.mkdir()

        (tests_dir / "start.py").write_text("import time; time.sleep(5)\n", encoding="utf-8")
        (tests_dir / "check.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")

        manifest = {
            "start_command": ["python3", "tests/start.py"],
            "check_command": ["python3", "tests/check.py"],
            "startup_delay_seconds": 0,
            "startup_timeout_seconds": 0.5,
            "poll_interval_seconds": 0.05,
            "check_timeout_seconds": 1.0,
        }
        (tests_dir / "smoke_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        ctx = _MockStepContext(workspace=ws)
        adapter = SmokeTestAdapter()
        res = adapter.run(ctx)

        assert res.success is True
        assert res.exit_code == 0
        assert res.stderr == ""

        result_json_path = ws / "artifacts" / "user-smoke" / "result.json"
        assert result_json_path.exists()
        result_data = json.loads(result_json_path.read_text(encoding="utf-8"))
        assert result_data["app_started"] is True
        assert result_data["core_flow_completed"] is True
        assert result_data["blocking_errors"] == []


def test_quality_floor_preservation_separate_from_startup_smoke() -> None:
    """AC-2: Bounding startup smoke must not remove or degrade release quality Makefile targets."""
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    makefile_content = MAKEFILE.read_text(encoding="utf-8")

    # Makefile must preserve full quality and test-suite targets
    for target in ("test:", "test-suite:", "quality:", "gcc-strict:"):
        assert target in makefile_content, f"Makefile missing required target: {target}"

    # Fixture test script must remain intact
    fixture_script = ROOT / "tests" / "test_sysdiff_fixture.sh"
    assert fixture_script.exists() and os.access(fixture_script, os.X_OK)


# ============================================================================
# AC-3: Manifest Synchronization, Traceability, and Non-Product Blast Radius
# ============================================================================


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-3: Both tests and journeys manifests exist and are identical parsed objects."""
    assert TESTS_MANIFEST.exists(), f"Missing canonical oracle {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest {JOURNEYS_MANIFEST}"

    tests_manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_manifest = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    assert tests_manifest == journeys_manifest, (
        "Repository user journeys manifests are not identical parsed objects."
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


def test_journey_traceability_to_contract_acceptance_checks() -> None:
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


# Compatibility alias
test_journey_traceability_and_acceptance_coverage = test_journey_traceability_to_contract_acceptance_checks


def test_sysdiff_c17_baseline_and_non_product_blast_radius() -> None:
    """AC-3: sysdiff C source remains unaltered ISO C17 without leaking orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0
    assert MAN_PAGE.exists() and MAN_PAGE.stat().st_size > 0

    gcc_bin = shutil.which("gcc")
    assert gcc_bin is not None, "gcc is required as the baseline ISO C17 compiler"

    res = subprocess.run(
        [
            gcc_bin,
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
    assert res.returncode == 0, f"gcc syntax check failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"

    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")
    for forbidden in ("97e798a99010", "agent_orch", "EXECUTION_TIMEOUT", "startup_timeout"):
        assert forbidden not in src_text, f"sysdiff source contaminated with {forbidden}"


# Compatibility alias
test_sysdiff_c_source_and_non_product_blast_radius = test_sysdiff_c17_baseline_and_non_product_blast_radius


def test_sysdiff_cli_behavior_unaltered(tmp_path: Path) -> None:
    """AC-3: sysdiff CLI contract (--help, --version, diffing, malformed input) remains unaltered."""
    binary = _get_sysdiff_binary(tmp_path)

    # 1. No arguments: prints usage guidance without crash
    no_args = subprocess.run([str(binary)], capture_output=True, text=True, check=False)
    assert no_args.returncode in (0, 2), f"Unexpected exit code for no arguments: {no_args.returncode}"
    combined_no_args = no_args.stdout + no_args.stderr
    assert "usage: sysdiff" in combined_no_args

    # 2. --help: exits 0 with usage on stdout
    help_res = subprocess.run([str(binary), "--help"], capture_output=True, text=True, check=False)
    assert help_res.returncode == 0
    assert "usage: sysdiff" in help_res.stdout
    assert help_res.stderr == ""

    # 3. --version: exits 0 with version string
    version_res = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=False)
    assert version_res.returncode == 0
    assert "sysdiff 0.1.0" in version_res.stdout
    assert version_res.stderr == ""

    # 4. Compare differing snapshots
    snap1 = tmp_path / "snap1.snapshot"
    snap2 = tmp_path / "snap2.snapshot"
    snap1.write_text("pkg.a=1.0\npkg.b=2.0\n", encoding="utf-8")
    snap2.write_text("pkg.a=1.1\npkg.c=3.0\n", encoding="utf-8")

    diff_res = subprocess.run(
        [str(binary), "compare", str(snap1), str(snap2)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert diff_res.returncode == 1
    assert diff_res.stderr == ""
    assert "~ pkg.a: 1.0 -> 1.1\n" in diff_res.stdout
    assert "- pkg.b=2.0\n" in diff_res.stdout
    assert "+ pkg.c=3.0\n" in diff_res.stdout

    # 5. Compare identical snapshots
    identical_res = subprocess.run(
        [str(binary), "compare", str(snap1), str(snap1)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert identical_res.returncode == 0
    assert identical_res.stdout == "no changes\n"
    assert identical_res.stderr == ""

    # 6. Reject malformed snapshot with exit 2 and empty stdout
    malformed = tmp_path / "malformed.snapshot"
    malformed.write_text("no_equals_separator_here\n", encoding="utf-8")
    malformed_res = subprocess.run(
        [str(binary), "compare", str(malformed), str(snap1)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert malformed_res.returncode == 2
    assert malformed_res.stdout == ""
    assert "missing '=' separator" in malformed_res.stderr
