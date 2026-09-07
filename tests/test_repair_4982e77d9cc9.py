"""Regression test suite for repairing governed run failure 4982e77d9cc9.

Governed run 4982e77d9cc9 failed due to a path escape and write scope confinement
violation: the step made changes to paths outside its declared allowed_paths boundary,
specifically creating unauthorized files including artifacts/user-test/result.json and
ad-hoc generator scripts such as generate_result.py directly in the workspace root.

Failure analysis and root causes:
1. Path Escape via Ad-Hoc Scripts in Workspace Root:
   The worker attempted to generate and evaluate user simulation outputs by authoring
   ad-hoc Python scripts directly in the repository root (including generate_result.py).
   Under Agent-Orch governance, creating files in the workspace root outside declared
   allowed_paths represents a fatal PATH_ESCAPE violation. Temporary utilities, test
   generators, and exploratory scripts must reside exclusively in designated
   .agent-orch-scratch/ directories and never pollute the governed repository tree.

2. Unauthorized Mutation of Artifact Paths:
   The workflow attempted to write artifacts/user-test/result.json during a step whose
   declared allowed_paths did not include the artifacts directory. Agent-Orch enforces
   write scope as a fundamental boundary: any write outside declared allowed_paths
   triggers an immediate fail-closed termination of the step.

3. User-Test Result Schema Conformance and Finding ID Integrity:
   User journey testing results must conform strictly to USER_JOURNEYS_RESULT_SCHEMA.
   Every finding object in findings must contain a non-empty string id property
   alongside severity, journey, problem, reproduction, expected, actual, and proposed_fix.
   Commands recorded in commands_run must execute as direct argv arrays conforming to
   the manifest's command_allowlist (["build/sysdiff"]) without shell wrapper escapes
   (/bin/sh -c) or command chaining.

4. User Journey Manifest Synchronization and Preservation:
   Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json must
   exist as identical parsed objects conforming to USER_JOURNEYS_MANIFEST_SCHEMA and
   preserving all 21 required author, sysdiff, and bwrap journeys.

Repair Contract Reference: docs/repair-4982e77d9cc9-contract.md
- AC-1: Write Scope Confinement, Contract Establishment, and Scratch Isolation
- AC-2: Result Schema Conformance, Finding ID Integrity, and Verifiable Execution Claims
- AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import pytest

for _extra_path in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/projects/employee-contract/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if _extra_path not in sys.path and Path(_extra_path).is_dir():
        sys.path.insert(0, _extra_path)

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
        USER_JOURNEYS_RESULT_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]
    USER_JOURNEYS_RESULT_SCHEMA = {}  # type: ignore[assignment]

try:
    import agent_orch.validators as validators
except ImportError:
    validators = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "repair-4982e77d9cc9-contract.md"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"
USER_TEST_RESULT = ROOT / "artifacts" / "user-test" / "result.json"

# 10 Preserved Workspace Abstraction Author Journeys
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

# 4 Core Sysdiff Product Journeys
SYSDIFF_JOURNEYS = {
    "A user runs the real sysdiff binary with no arguments and receives usage guidance instead of a crash",
    "A user asks the real sysdiff binary for help and receives its usage summary",
    "A user compares two snapshots with the real sysdiff binary and sees deterministic added removed and changed entries",
    "A user gives the real sysdiff binary a malformed snapshot and receives an escaped diagnostic without partial output",
}

# 7 Sandbox Containment and Repair Journeys
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

# Canonical finding diagnostic fields required by USER_JOURNEYS_RESULT_SCHEMA
MANDATORY_FINDING_FIELDS = (
    "id",
    "severity",
    "journey",
    "problem",
    "reproduction",
    "expected",
    "actual",
    "proposed_fix",
)


def _get_sysdiff_binary(tmp_path: Path) -> Path:
    """Obtain or compile an executable sysdiff binary for testing."""
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


def _check_scope_confinement(changed_paths: Sequence[str], allowed_paths: Sequence[str]) -> list[tuple[str, bool, str]]:
    """Simulate Agent-Orch write scope confinement policy checking."""
    allowed_prefixes = tuple(p.rstrip("/") for p in allowed_paths)
    outcomes: list[tuple[str, bool, str]] = []
    for path in changed_paths:
        allowed = any(
            path == prefix or path.startswith(f"{prefix}/")
            for prefix in allowed_prefixes
        )
        msg = (
            f"Changed path within scope: {path}"
            if allowed
            else f"Changed path outside allowed_paths: {path}"
        )
        outcomes.append((path, allowed, msg))
    return outcomes


# ============================================================================
# AC-1: Write Scope Confinement, Contract Establishment, and Scratch Isolation
# ============================================================================


def test_repair_contract_headings_and_character_counts() -> None:
    """AC-1: docs/repair-4982e77d9cc9-contract.md has required headings with >= 120 chars each."""
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

    assert "4982e77d9cc9" in content, "Contract does not reference run 4982e77d9cc9"
    assert "/home/lee/projects/linux-utilities-agent-orch-runs/4982e77d9cc9" in content, (
        "Contract does not reference the sealed evidence directory"
    )
    assert "AC-1" in content and "AC-2" in content and "AC-3" in content, (
        "Contract missing enumerated acceptance checks (AC-1, AC-2, AC-3)"
    )


def test_closed_hazard_taxonomy_compliance() -> None:
    """AC-1: Identified hazards must strictly belong to the closed repository taxonomy."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    assert "Closed Hazard Taxonomy" in content, (
        "Contract does not reference Closed Hazard Taxonomy"
    )
    required_hazards = ["PATH_ESCAPE", "RESULT_FABRICATION", "ORACLE_TAMPERING", "BLAST_RADIUS"]
    for hazard in required_hazards:
        assert hazard in content, f"Contract missing required hazard taxonomy member: {hazard}"


def test_workspace_root_clean_of_adhoc_scripts() -> None:
    """AC-1: Ad-hoc scripts (generate_result.py, etc.) must never exist in the workspace root."""
    adhoc_scripts = [
        "generate_result.py",
        "generate_result2.py",
        "test_script.py",
        "update_md.py",
        "temp_test.py",
        "eval_test.py",
    ]
    found = [script for script in adhoc_scripts if (ROOT / script).exists()]
    assert not found, (
        f"AC-1 violation: Ad-hoc generator/test scripts found in workspace root: {found}. "
        f"Temporary scripts must reside exclusively in designated .agent-orch-scratch/ directories."
    )


def test_write_scope_confinement_rejects_unauthorized_root_writes() -> None:
    """AC-1: Step execution must reject unauthorized mutations outside declared allowed_paths."""
    # Simulation 1: Step with allowed_paths = ["tests/"] (e.g. test authoring step)
    tests_allowed = ["tests/"]
    outcomes = _check_scope_confinement(
        [
            "tests/test_repair_4982e77d9cc9.py",
            "generate_result.py",
            "artifacts/user-test/result.json",
        ],
        tests_allowed,
    )
    assert outcomes[0][1] is True, "Allowed test path was rejected"
    assert outcomes[1][1] is False, "Unauthorized root file generate_result.py was allowed"
    assert "outside allowed_paths" in outcomes[1][2]
    assert outcomes[2][1] is False, "Unauthorized artifact write was allowed"
    assert "outside allowed_paths" in outcomes[2][2]

    # Simulation 2: Step with allowed_paths = ["docs/"] (e.g. contract definition step)
    docs_allowed = ["docs/"]
    outcomes_docs = _check_scope_confinement(
        [
            "docs/repair-4982e77d9cc9-contract.md",
            "generate_result.py",
            "artifacts/user-test/result.json",
        ],
        docs_allowed,
    )
    assert outcomes_docs[0][1] is True
    assert outcomes_docs[1][1] is False
    assert outcomes_docs[2][1] is False

    # Simulation 3: Step with allowed_paths = ["artifacts/user-test", "tmp"] (e.g. simulation gate)
    sim_allowed = ["artifacts/user-test", "tmp"]
    outcomes_sim = _check_scope_confinement(
        [
            "artifacts/user-test/result.json",
            "artifacts/user-test/findings-log.md",
            "generate_result.py",
            "src/sysdiff.c",
        ],
        sim_allowed,
    )
    assert outcomes_sim[0][1] is True
    assert outcomes_sim[1][1] is True
    assert outcomes_sim[2][1] is False, "generate_result.py in root must be rejected during simulation gate"
    assert outcomes_sim[3][1] is False, "src/sysdiff.c modification must be rejected during simulation gate"


def test_scratch_space_isolation_and_containment(tmp_path: Path) -> None:
    """AC-1: Scratch files reside strictly under .agent-orch-scratch/ without repository pollution."""
    scratch_dir = tmp_path / ".agent-orch-scratch" / "ba39f236f2b4" / "step_test" / "attempt-1"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Writing temporary scripts inside scratch space is permitted
    scratch_script = scratch_dir / "temp_generator.py"
    scratch_script.write_text("print('scratch experiment')\n", encoding="utf-8")
    assert scratch_script.exists()

    # Scratch files are isolated from governed workspace root
    assert not (tmp_path / "temp_generator.py").exists()


# ============================================================================
# AC-2: Result Schema Conformance, Finding ID Integrity, and Verifiable Claims
# ============================================================================


def test_result_schema_rejects_finding_missing_id() -> None:
    """AC-2: USER_JOURNEYS_RESULT_SCHEMA must fail-closed if a finding is missing the 'id' property."""
    if jsonschema is None or not USER_JOURNEYS_RESULT_SCHEMA:
        pytest.skip("jsonschema or USER_JOURNEYS_RESULT_SCHEMA not available")

    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

    malformed_result = {
        "journeys": [
            {
                "name": "A developer runs the sysdiff test suite and smoke verification",
                "status": "failed",
                "steps_taken": "Ran make test",
                "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}],
            }
        ],
        "findings": [
            {
                # Missing "id" property (reproducing failure mode)
                "severity": "High",
                "journey": "A developer runs the sysdiff test suite and smoke verification",
                "problem": "Product tests timed out.",
                "reproduction": "make clean && make test",
                "expected": "Exit code 0",
                "actual": "Exit code 124 (timeout)",
                "proposed_fix": "Optimize test execution bounds.",
            }
        ],
    }

    errors = list(validator.iter_errors(malformed_result))
    assert len(errors) > 0, "Schema validator unexpectedly accepted finding missing 'id'"
    id_errors = [e for e in errors if "id" in e.message and "required property" in e.message]
    assert len(id_errors) > 0, f"Expected required property error for 'id', got: {[e.message for e in errors]}"
    assert "'id' is a required property" in id_errors[0].message


def test_result_schema_rejects_finding_empty_id() -> None:
    """AC-2: USER_JOURNEYS_RESULT_SCHEMA must reject findings with an empty string id."""
    if jsonschema is None or not USER_JOURNEYS_RESULT_SCHEMA:
        pytest.skip("jsonschema or USER_JOURNEYS_RESULT_SCHEMA not available")

    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

    empty_id_result = {
        "journeys": [
            {
                "name": "A developer runs the sysdiff test suite and smoke verification",
                "status": "failed",
                "steps_taken": "Ran make test",
                "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}],
            }
        ],
        "findings": [
            {
                "id": "",  # Empty id violates minLength: 1
                "severity": "High",
                "journey": "A developer runs the sysdiff test suite and smoke verification",
                "problem": "Problem",
                "reproduction": "Reproduction",
                "expected": "Expected",
                "actual": "Actual",
                "proposed_fix": "Fix",
            }
        ],
    }

    errors = list(validator.iter_errors(empty_id_result))
    assert len(errors) > 0, "Schema validator unexpectedly accepted finding with empty string 'id'"
    assert any("too short" in e.message or "minLength" in str(e.schema) for e in errors)


def test_result_schema_rejects_missing_mandatory_finding_fields() -> None:
    """AC-2: Every finding must include all mandatory properties."""
    if jsonschema is None or not USER_JOURNEYS_RESULT_SCHEMA:
        pytest.skip("jsonschema or USER_JOURNEYS_RESULT_SCHEMA not available")

    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

    base_finding = {
        "id": "UJ-4982E77D-001",
        "severity": "Medium",
        "journey": "A user tests sysdiff",
        "problem": "Problem description",
        "reproduction": "Reproduction step",
        "expected": "Expected output",
        "actual": "Actual output",
        "proposed_fix": "Fix description",
    }

    for field in MANDATORY_FINDING_FIELDS:
        incomplete = dict(base_finding)
        del incomplete[field]
        candidate = {
            "journeys": [
                {
                    "name": "A user tests sysdiff",
                    "status": "failed",
                    "steps_taken": "Executed journey steps",
                    "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}],
                }
            ],
            "findings": [incomplete],
        }
        errors = list(validator.iter_errors(candidate))
        assert len(errors) > 0, f"Validator failed to reject finding missing mandatory field {field!r}"
        assert any(field in e.message for e in errors), f"Error message missing reference to {field!r}"


def test_result_schema_rejects_invalid_severity_enum() -> None:
    """AC-2: Severity must strictly belong to ['Critical', 'High', 'Medium', 'Low']."""
    if jsonschema is None or not USER_JOURNEYS_RESULT_SCHEMA:
        pytest.skip("jsonschema or USER_JOURNEYS_RESULT_SCHEMA not available")

    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

    invalid_result = {
        "journeys": [
            {
                "name": "A user tests sysdiff",
                "status": "failed",
                "steps_taken": "steps",
                "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}],
            }
        ],
        "findings": [
            {
                "id": "UJ-TEST-002",
                "severity": "Fatal",  # Invalid severity enum
                "journey": "A user tests sysdiff",
                "problem": "Problem",
                "reproduction": "Reproduction",
                "expected": "Expected",
                "actual": "Actual",
                "proposed_fix": "Fix",
            }
        ],
    }

    errors = list(validator.iter_errors(invalid_result))
    assert len(errors) > 0, "Validator accepted invalid severity 'Fatal'"
    assert any("is not one of" in e.message or "Fatal" in str(e) for e in errors)


def test_result_schema_accepts_conforming_finding() -> None:
    """AC-2: A well-formed finding with valid id and canonical fields passes schema validation."""
    if jsonschema is None or not USER_JOURNEYS_RESULT_SCHEMA:
        pytest.skip("jsonschema or USER_JOURNEYS_RESULT_SCHEMA not available")

    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

    conforming_result = {
        "journeys": [
            {
                "name": "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
                "status": "failed",
                "steps_taken": "Ran make test and observed timeout failure",
                "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}],
            }
        ],
        "findings": [
            {
                "id": "UJ-4982E77D-001",
                "severity": "High",
                "journey": "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
                "problem": "Product tests timed out under unoptimized execution.",
                "reproduction": "make clean && make test",
                "expected": "Exit code 0 within bounded test window",
                "actual": "Exit code 124 (timeout)",
                "proposed_fix": "Optimize test execution bounds.",
            }
        ],
    }

    errors = list(validator.iter_errors(conforming_result))
    assert not errors, f"Conforming result rejected with schema errors: {errors}"


def test_commands_run_rejects_shell_wrappers() -> None:
    """AC-2: Shell wrapper commands (/bin/sh -c, sh -c, bash -c) must be rejected."""
    if validators is None:
        pytest.skip("agent_orch.validators not importable")

    allowlist = [["build/sysdiff"]]
    shell_wrappers = [
        "/bin/sh -c 'make clean && make test'",
        "sh -c 'build/sysdiff --help'",
        "bash -c 'build/sysdiff --version'",
    ]

    for cmd in shell_wrappers:
        argv, reason = validators._allowlisted_journey_command(cmd, allowlist)
        assert argv is None, f"Shell wrapper {cmd!r} was accepted as: {argv}"
        assert "command_allowlist" in reason or "argv prefix" in reason


def test_commands_run_rejects_shell_operators_and_chaining() -> None:
    """AC-2: Commands carrying shell operators (&&, ||, ;, |, >, <) must be rejected."""
    if validators is None:
        pytest.skip("agent_orch.validators not importable")

    allowlist = [["build/sysdiff"]]
    chained_commands = [
        "build/sysdiff --help && echo ok",
        "build/sysdiff --help | grep usage",
        "build/sysdiff --version; ls",
        "build/sysdiff > /tmp/out.txt",
        "build/sysdiff < /dev/null",
    ]

    for cmd in chained_commands:
        argv, reason = validators._allowlisted_journey_command(cmd, allowlist)
        assert argv is None, f"Chained command {cmd!r} was accepted as: {argv}"
        assert "shell operator" in reason


def test_commands_run_rejects_unallowlisted_binaries() -> None:
    """AC-2: Commands not starting with allowlisted ['build/sysdiff'] prefix must be rejected."""
    if validators is None:
        pytest.skip("agent_orch.validators not importable")

    allowlist = [["build/sysdiff"]]
    unallowlisted = [
        "echo ok",
        "python3 -c 'print(1)'",
        "make test",
        "bash tests/test_sysdiff.sh",
        "generate_result.py",
    ]

    for cmd in unallowlisted:
        argv, reason = validators._allowlisted_journey_command(cmd, allowlist)
        assert argv is None, f"Unallowlisted command {cmd!r} was accepted: {argv}"
        assert "command_allowlist" in reason or "argv prefix" in reason


def test_commands_run_accepts_direct_sysdiff_argv() -> None:
    """AC-2: Direct argv commands matching ['build/sysdiff'] prefix are accepted and parse cleanly."""
    if validators is None:
        pytest.skip("agent_orch.validators not importable")

    allowlist = [["build/sysdiff"]]
    claims = [
        ("build/sysdiff --help", ["build/sysdiff", "--help"]),
        ("build/sysdiff --version", ["build/sysdiff", "--version"]),
    ]

    for cmd_claim, expected_argv in claims:
        argv, reason = validators._allowlisted_journey_command(cmd_claim, allowlist)
        assert argv == expected_argv, f"Failed parsing {cmd_claim!r}: argv={argv}, reason={reason}"
        assert reason == ""


def test_current_user_test_result_conformance() -> None:
    """AC-2: If artifacts/user-test/result.json exists, it must satisfy schema and finding id requirements."""
    if not USER_TEST_RESULT.exists():
        pytest.skip(f"{USER_TEST_RESULT} does not exist in the current workspace")

    data = json.loads(USER_TEST_RESULT.read_text(encoding="utf-8"))

    if jsonschema is not None and USER_JOURNEYS_RESULT_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)
        errors = list(validator.iter_errors(data))
        assert not errors, f"Schema validation errors in {USER_TEST_RESULT}: {errors}"

    findings = data.get("findings", [])
    for i, finding in enumerate(findings):
        assert "id" in finding and finding["id"], (
            f"Finding [{i}] missing non-empty 'id' property in {USER_TEST_RESULT}: {finding}"
        )
        # Check artifact citations if present
        for artifact_rel in finding.get("artifacts", []):
            artifact_path = ROOT / artifact_rel
            assert artifact_path.is_file(), (
                f"Finding [{i}] cites missing artifact: {artifact_rel}"
            )
            assert artifact_path.stat().st_size > 0, (
                f"Finding [{i}] cites empty artifact: {artifact_rel}"
            )


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
        "Repository journey manifests are not identical parsed objects between tests/ and journeys/."
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


def test_user_journeys_manifest_preserves_all_21_journeys() -> None:
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
    for forbidden in ("4982e77d9cc9", "agent_orch", "PATH_ESCAPE", "RESULT_FABRICATION", "generate_result"):
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
