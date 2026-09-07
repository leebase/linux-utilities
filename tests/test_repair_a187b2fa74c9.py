"""Regression test suite for repairing governed run failure a187b2fa74c9.

Sealed Evidence Directory:
    /home/lee/projects/linux-utilities-agent-orch-runs/a187b2fa74c9

Lineage and Failure Analysis:
1. Origin Run Failure in a187b2fa74c9:
   Governed run a187b2fa74c9 failed during validation at step step_08b_user_simulation_gate (attempt 1).
   The trusted failure evidence recorded:
       User-test result artifacts/user-test/result.json violates the result schema:
       $.journeys[0].commands_run[0]: 'build/sysdiff --help' is not of type 'object'

2. Root Cause Analysis:
   - Schema Non-Conformance in User-Test Result Artifact (artifacts/user-test/result.json):
     Under Draft 2020-12 USER_JOURNEYS_RESULT_SCHEMA, each journey record within the 'journeys'
     array must contain 'commands_run' as an array of objects with required 'command' (string)
     and 'exit_code' (integer) properties.
     In run a187b2fa74c9, commands_run contained plain string entries ("build/sysdiff --help")
     rather than structured dictionary objects ({"command": "build/sysdiff --help", "exit_code": 0}),
     causing the user simulation gate validator to fail closed.
   - Downstream Type Errors and Validation Refusal:
     Iterating commands_run and performing claim.get("command") raises AttributeError when claims
     are plain strings. The orchestrator validator refuses to re-execute command claims from an
     invalid schema artifact.
   - Omission of Explicit Rule in TESTING.md:
     TESTING.md described user journey verification but did not explicitly state that commands_run
     in user-test result.json must be an array of objects and not strings.

3. Repair Acceptance Contract (docs/repair-a187b2fa74c9-contract.md):
   - AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement.
     Contract document adheres to required headings with >= 120 non-whitespace characters each.
     Closed hazard taxonomy (SCHEMA_VIOLATION, ORACLE_TAMPERING, RESULT_FABRICATION, BLAST_RADIUS,
     PATH_ESCAPE, TOOL_AVAILABILITY, EXECUTION_TIMEOUT). Sealed evidence directory explicitly cited.
     Workspace root remains clean of ad-hoc generator scripts; scratch confined to .agent-orch-scratch/.
   - AC-2: User-Test Result Artifact Schema Conformance, Command Claim Structure, Documentation,
     and Simulation Gate Passing.
     TESTING.md explicitly states that commands_run in user-test result.json must be an array of
     objects and not strings.
     artifacts/user-test/result.json conforms strictly to Draft 2020-12 USER_JOURNEYS_RESULT_SCHEMA.
     Root contains required properties 'journeys' and 'findings'.
     Every journey contains 'name', 'status', 'steps_taken', and structured 'commands_run'.
     Every claim in commands_run is an object with 'command' (str) and 'exit_code' (int), eliminating strings.
     Every allowlisted command claim re-executed from workspace root matches its claimed exit code.
     Both user_journeys_all_passed and user_journeys_execution_verified validator rules pass.
   - AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius.
     Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
     identical parsed objects adhering to canonical schema across all 21 journeys.
     Every required journey maps via traces_to to AC-1, AC-2, or AC-3.
     Command allowlist remains strictly ["build/sysdiff"].
     Baseline SHA-256 hash pins for src/sysdiff.c and Makefile remain intact.
     sysdiff compare preserves its 3-state exit status contract (0, 1, 2).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import site
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

import pytest

# Maintain clean sys.path without cross-project contamination
for _extra_path in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if Path(_extra_path).is_dir():
        if _extra_path.endswith("site-packages"):
            site.addsitedir(_extra_path)
        if _extra_path not in sys.path:
            sys.path.insert(0, _extra_path)

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        REQUIRED_JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
        USER_JOURNEYS_RESULT_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    REQUIRED_JOURNEY_AUTHORITIES = ("human", "mission", "author")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]
    USER_JOURNEYS_RESULT_SCHEMA = {}  # type: ignore[assignment]

try:
    import agent_orch.validators as validators
    from agent_orch.models import ValidationRule
except ImportError:
    validators = None  # type: ignore[assignment]
    ValidationRule = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
SEALED_EVIDENCE_DIR = Path("/home/lee/projects/linux-utilities-agent-orch-runs/a187b2fa74c9")
CONTRACT = ROOT / "docs" / "repair-a187b2fa74c9-contract.md"
TESTING_MD = ROOT / "TESTING.md"
USER_TEST_RESULT = ROOT / "artifacts" / "user-test" / "result.json"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"

# Baseline Smoke Oracle Hashes
BASELINE_SYSDIFF_SHA256 = "1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1"
BASELINE_MAKEFILE_SHA256 = "f0a00c8edce2a01787db570b53479d1d07ca3246c600c5bac0d493c21c8e5629"

# Closed Hazard Taxonomy
CLOSED_HAZARD_TAXONOMY = {
    "SCHEMA_VIOLATION",
    "ORACLE_TAMPERING",
    "RESULT_FABRICATION",
    "BLAST_RADIUS",
    "PATH_ESCAPE",
    "TOOL_AVAILABILITY",
    "EXECUTION_TIMEOUT",
}

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
EXPECTED_COMMAND_ALLOWLIST = ["build/sysdiff"]
ALLOWED_ACCEPTANCE_CHECKS = {"AC-1", "AC-2", "AC-3"}


def _read_disk_file(path: Path) -> str:
    """Read file content directly from disk file descriptor, bypassing in-process mocking."""
    assert path.exists(), f"File missing: {path}"
    fd = os.open(str(path), os.O_RDONLY)
    try:
        data = b""
        while True:
            chunk = os.read(fd, 8192)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8")
    finally:
        os.close(fd)


def _load_disk_result_dict() -> dict[str, Any]:
    """Load and parse the user test result JSON directly from disk."""
    raw = _read_disk_file(USER_TEST_RESULT)
    data = json.loads(raw)
    assert isinstance(data, dict), f"Result root must be an object, got {type(data).__name__}"
    return data


def _load_manifest_dict() -> dict[str, Any]:
    """Helper to load and return the parsed user journeys manifest JSON."""
    assert TESTS_MANIFEST.exists(), f"User journeys manifest missing: {TESTS_MANIFEST}"
    content = _read_disk_file(TESTS_MANIFEST)
    data = json.loads(content)
    assert isinstance(data, dict), f"Manifest root must be an object, got {type(data).__name__}"
    return data


def _get_sysdiff_binary() -> Path:
    """Return the sysdiff binary under test, building if necessary."""
    env_bin = os.environ.get("SYSDIFF_BIN")
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.is_file() and os.access(bin_path, os.X_OK):
            return bin_path

    build_bin = ROOT / "build" / "sysdiff"
    if build_bin.is_file() and os.access(build_bin, os.X_OK):
        return build_bin

    build_bin.parent.mkdir(parents=True, exist_ok=True)
    cc = os.environ.get("CC", "gcc")
    subprocess.run(
        [
            cc,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-O2",
            "-o",
            str(build_bin),
            str(SYSDIFF_SRC),
        ],
        check=True,
        capture_output=True,
    )
    return build_bin


def _run_sysdiff(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute sysdiff binary with given arguments, returning CompletedProcess."""
    binary = _get_sysdiff_binary()
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    return subprocess.run(
        [str(binary), *args],
        cwd=str(cwd) if cwd is not None else str(ROOT),
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


# ============================================================================
# AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement
# ============================================================================


def test_repair_contract_exists_and_has_required_headings() -> None:
    """AC-1: docs/repair-a187b2fa74c9-contract.md has required headings with >= 120 chars each."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    assert CONTRACT.is_file(), f"{CONTRACT} must be a regular file"
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


def test_repair_contract_cites_sealed_evidence_directory() -> None:
    """AC-1: Contract must explicitly cite sealed evidence directory for run a187b2fa74c9."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")
    expected_evidence_path = "/home/lee/projects/linux-utilities-agent-orch-runs/a187b2fa74c9"
    assert expected_evidence_path in content, (
        f"Contract must cite sealed evidence path {expected_evidence_path}"
    )


def test_repair_contract_closed_hazard_taxonomy() -> None:
    """AC-1: Contract must adhere strictly to the closed hazard taxonomy."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")
    assert "Closed Hazard Taxonomy" in content or "closed repository taxonomy" in content.lower() or "SCHEMA_VIOLATION" in content
    for hazard in ("SCHEMA_VIOLATION", "ORACLE_TAMPERING", "RESULT_FABRICATION", "BLAST_RADIUS"):
        assert hazard in content, f"Contract missing hazard classification {hazard}"


def test_workspace_root_clean_of_adhoc_scripts() -> None:
    """AC-1: Workspace root must remain clean of ad-hoc or untracked temporary scripts."""
    forbidden = ["generate_result.py", "make_result.py", "repair.py", "test.py", "run.py"]
    for script_name in forbidden:
        script_path = ROOT / script_name
        assert not script_path.exists(), (
            f"Ad-hoc script {script_name} must not exist in workspace root; use .agent-orch-scratch/"
        )


# ============================================================================
# AC-2: User-Test Result Artifact Schema Conformance, Command Claim Structure,
#       Documentation, and Simulation Gate Passing
# ============================================================================


def test_testing_md_explicitly_specifies_commands_run_as_array_of_objects_not_strings() -> None:
    """AC-2: TESTING.md explicitly states that commands_run in user-test result.json must be an array of objects and not strings."""
    assert TESTING_MD.exists(), f"TESTING.md missing at {TESTING_MD}"
    content = _read_disk_file(TESTING_MD)

    assert "commands_run" in content, "TESTING.md must mention 'commands_run'"
    assert "result.json" in content, "TESTING.md must mention 'result.json'"

    # Normalize backticks and quotes for robust pattern verification
    normalized = content.replace("`", "").replace('"', "").replace("'", "")

    pattern = re.compile(
        r"commands_run.*?(?:user-test\s+)?result\.json.*?must be an array of objects\s+(?:and\s+)?not\s+(?:plain\s+)?strings|"
        r"(?:user-test\s+)?result\.json.*?commands_run.*?must be an array of objects\s+(?:and\s+)?not\s+(?:plain\s+)?strings|"
        r"commands_run.*?must be an array of objects\s+(?:and\s+)?not\s+(?:plain\s+)?strings",
        re.IGNORECASE | re.DOTALL,
    )
    assert pattern.search(normalized) is not None, (
        "TESTING.md must explicitly state that commands_run in user-test result.json "
        "must be an array of objects and not strings."
    )


def test_user_test_result_file_exists_and_is_valid_json() -> None:
    """AC-2: artifacts/user-test/result.json must exist and parse cleanly as valid JSON."""
    assert USER_TEST_RESULT.exists(), f"User test result artifact missing: {USER_TEST_RESULT}"
    assert USER_TEST_RESULT.is_file(), f"{USER_TEST_RESULT} must be a regular file"
    assert USER_TEST_RESULT.stat().st_size > 0, f"{USER_TEST_RESULT} must not be empty"

    data = _load_disk_result_dict()
    assert isinstance(data, dict), f"Result root must be a dict, got {type(data).__name__}"


def test_user_test_result_root_keys_contain_journeys_and_findings() -> None:
    """AC-2: Root object must contain required properties 'journeys' and 'findings'."""
    data = _load_disk_result_dict()
    assert "journeys" in data, f"Missing required property 'journeys' in {USER_TEST_RESULT}"
    assert isinstance(data["journeys"], list), f"'journeys' must be a list, got {type(data['journeys']).__name__}"
    assert "findings" in data, f"Missing required property 'findings' in {USER_TEST_RESULT}"
    assert isinstance(data["findings"], list), f"'findings' must be a list, got {type(data['findings']).__name__}"


def test_user_test_result_journeys_structure() -> None:
    """AC-2: Every journey must contain 'name', 'status', 'steps_taken', and 'commands_run'."""
    data = _load_disk_result_dict()
    journeys = data.get("journeys", [])
    assert len(journeys) > 0, "No journeys found in result"

    for idx, j in enumerate(journeys):
        assert isinstance(j, dict), f"Journey [{idx}] must be a dict"
        assert "name" in j, f"Journey [{idx}] missing required property 'name'"
        assert isinstance(j["name"], str) and len(j["name"].strip()) > 0
        assert "journey" not in j, f"Journey [{idx}] contains forbidden deprecated key 'journey'"
        assert "status" in j, f"Journey [{idx}] missing 'status'"
        assert j["status"] in ("passed", "failed"), f"Journey [{idx}] status invalid: {j['status']}"
        assert "steps_taken" in j, f"Journey [{idx}] missing 'steps_taken'"
        assert "commands_run" in j, f"Journey [{idx}] missing 'commands_run'"
        assert isinstance(j["commands_run"], list), f"Journey [{idx}] commands_run must be a list"


def test_user_test_result_commands_run_are_objects_not_bare_strings() -> None:
    """AC-2: Every claim in commands_run must be a dict object with 'command' and 'exit_code', not a string.

    Direct regression test for run a187b2fa74c9:
        User-test result artifacts/user-test/result.json violates the result schema:
        $.journeys[0].commands_run[0]: 'build/sysdiff --help' is not of type 'object'
    """
    data = _load_disk_result_dict()
    journeys = data.get("journeys", [])
    assert len(journeys) > 0, "No journeys found in result"

    for idx, j in enumerate(journeys):
        j_name = j.get("name", f"journey[{idx}]")
        commands_run = j.get("commands_run")
        assert isinstance(commands_run, list), f"[{j_name}] commands_run must be a list"
        assert len(commands_run) >= 1, f"[{j_name}] commands_run cannot be empty"

        for c_idx, claim in enumerate(commands_run):
            assert isinstance(claim, dict), (
                f"[{j_name}] command claim [{c_idx}] must be a dict, got {type(claim).__name__} ({claim!r}). "
                "In run a187b2fa74c9, claims were strings rather than objects, breaking schema validation."
            )
            assert "command" in claim, f"[{j_name}] claim [{c_idx}] missing required 'command' property"
            assert isinstance(claim["command"], str) and len(claim["command"]) > 0, (
                f"[{j_name}] claim [{c_idx}] 'command' must be a non-empty string"
            )
            assert "exit_code" in claim, f"[{j_name}] claim [{c_idx}] missing required 'exit_code' property"
            assert isinstance(claim["exit_code"], int), (
                f"[{j_name}] claim [{c_idx}] 'exit_code' must be an integer, got {type(claim['exit_code']).__name__}"
            )


def test_user_test_result_command_claims_safe_dict_access_no_attribute_error() -> None:
    """AC-2: Iterating commands_run and calling .get('command') must not raise AttributeError."""
    data = _load_disk_result_dict()
    journeys = data.get("journeys", [])

    for j in journeys:
        commands_run = j.get("commands_run", [])
        for claim in commands_run:
            assert hasattr(claim, "get"), (
                f"Claim {claim!r} in journey {j.get('name', '')!r} has no .get attribute. "
                "Claims must be dictionary objects, not bare strings."
            )
            cmd_text = claim.get("command", "")
            exit_code = claim.get("exit_code")
            assert isinstance(cmd_text, str)
            assert isinstance(exit_code, int)


def test_user_test_result_satisfies_canonical_schema() -> None:
    """AC-2: artifacts/user-test/result.json strictly satisfies USER_JOURNEYS_RESULT_SCHEMA."""
    if jsonschema is None:
        pytest.skip("jsonschema not installed in current environment")

    data = _load_disk_result_dict()
    if not USER_JOURNEYS_RESULT_SCHEMA:
        pytest.skip("USER_JOURNEYS_RESULT_SCHEMA not defined")

    validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)
    errors = list(validator.iter_errors(data))
    assert not errors, (
        f"Schema validation failed on {USER_TEST_RESULT} with {len(errors)} error(s): "
        + "; ".join(f"{e.message} at {list(e.path)}" for e in errors[:5])
    )


def test_user_test_result_command_claims_confirmed_against_build_sysdiff() -> None:
    """AC-2: Every allowlisted command claim in artifacts/user-test/result.json matches actual exit code.

    Re-executes each command claim against build/sysdiff from the workspace root (cwd=ROOT).
    """
    data = _load_disk_result_dict()
    sysdiff_bin = _get_sysdiff_binary()
    allowlist_prefix = "build/sysdiff"

    mismatches: list[str] = []
    total_claims = 0

    for journey in data.get("journeys", []):
        journey_name = journey.get("name", "unknown")
        for claim in journey.get("commands_run", []):
            if not isinstance(claim, dict):
                mismatches.append(f"[{journey_name}] claim is not a dict: {claim!r}")
                continue

            cmd_text = claim.get("command", "")
            claimed_exit = claim.get("exit_code")

            if not cmd_text.startswith(allowlist_prefix):
                continue

            total_claims += 1

            try:
                tokens = shlex.split(cmd_text)
            except ValueError:
                mismatches.append(f"[{journey_name}] unparseable command: {cmd_text!r}")
                continue

            binary_rel = tokens[0]
            binary_path = ROOT / binary_rel
            if not (binary_path.is_file() and os.access(binary_path, os.X_OK)):
                binary_path = sysdiff_bin

            proc = subprocess.run(
                [str(binary_path), *tokens[1:]],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )

            if proc.returncode != claimed_exit:
                mismatches.append(
                    f"[{journey_name}] {cmd_text}: tester claimed exit "
                    f"{claimed_exit}, orchestrator observed exit {proc.returncode}"
                )

    assert not mismatches, (
        "Command claims in artifacts/user-test/result.json could not be confirmed: "
        + "; ".join(mismatches)
    )
    assert total_claims > 0, "No allowlisted build/sysdiff command claims found to verify"


def test_user_test_result_commands_strictly_within_allowlist() -> None:
    """AC-2: Every command in commands_run must adhere to the allowlist prefix without shell chaining."""
    data = _load_disk_result_dict()
    allowlist_prefix = "build/sysdiff"

    forbidden_patterns = [
        r"[;&|`$><]",
        r"\.\.",
        r"/bin/sh",
        r"/bin/bash",
    ]

    for journey in data.get("journeys", []):
        j_name = journey.get("name", "unknown")
        for claim in journey.get("commands_run", []):
            if isinstance(claim, dict):
                cmd_text = claim.get("command", "")
            else:
                cmd_text = str(claim)

            assert cmd_text.startswith(allowlist_prefix), (
                f"[{j_name}] command {cmd_text!r} does not start with allowlisted prefix {allowlist_prefix!r}"
            )

            for pat in forbidden_patterns:
                assert not re.search(pat, cmd_text), (
                    f"[{j_name}] command {cmd_text!r} contains forbidden pattern {pat!r}"
                )


def test_user_journeys_all_passed_validator_rule() -> None:
    """AC-2: agent_orch validator user_journeys_all_passed rule passes on artifacts/user-test/result.json."""
    script = (
        "import site, sys, pathlib; "
        "site.addsitedir('/home/lee/.local/lib/python3.12/site-packages'); "
        "sys.path.insert(0, '/home/lee/projects/agent-orch/src'); "
        "from agent_orch.validators import _run_user_journeys_rule; "
        "from agent_orch.models import ValidationRule; "
        "rule = ValidationRule(type='user_journeys_all_passed', path='artifacts/user-test/result.json', manifest_path='tests/user_journeys_manifest.json'); "
        "outcome = _run_user_journeys_rule(rule, pathlib.Path('.'), pathlib.Path('.')); "
        "assert outcome.passed is True, outcome.message; "
        "print('PASS')"
    )
    res = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"user_journeys_all_passed rule failed on result.json: {res.stderr or res.stdout}"


def test_user_journeys_execution_verified_validator_rule() -> None:
    """AC-2: agent_orch validator user_journeys_execution_verified rule passes on result.json."""
    script = (
        "import site, sys, pathlib; "
        "site.addsitedir('/home/lee/.local/lib/python3.12/site-packages'); "
        "sys.path.insert(0, '/home/lee/projects/agent-orch/src'); "
        "from agent_orch.validators import _run_user_journeys_execution_rule; "
        "from agent_orch.models import ValidationRule; "
        "rule = ValidationRule(type='user_journeys_execution_verified', path='artifacts/user-test/result.json', manifest_path='tests/user_journeys_manifest.json'); "
        "outcome = _run_user_journeys_execution_rule(rule, pathlib.Path('.'), None, None); "
        "assert outcome.passed is True, outcome.message; "
        "print('PASS')"
    )
    res = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, (
        f"user_journeys_execution_verified rule failed on result.json: {res.stderr or res.stdout}"
    )


def test_all_manifest_journeys_represented_in_result_with_status_passed() -> None:
    """AC-2: Every journey in tests/user_journeys_manifest.json is reported as 'passed' in result.json."""
    manifest = _load_manifest_dict()
    result = _load_disk_result_dict()

    manifest_names = {j["name"] for j in manifest.get("journeys", [])}
    result_journeys = {j["name"]: j.get("status") for j in result.get("journeys", []) if "name" in j}

    missing_from_result = manifest_names - set(result_journeys.keys())
    assert not missing_from_result, (
        f"Manifest journeys missing from user-test result: {missing_from_result}"
    )

    unpassed = {name: status for name, status in result_journeys.items() if status != "passed"}
    assert not unpassed, f"Journeys with non-passed status in result: {unpassed}"


def test_user_test_result_findings_structure_integrity() -> None:
    """AC-2: If findings are present in result.json, each must satisfy canonical schema properties."""
    data = _load_disk_result_dict()
    findings = data.get("findings", [])

    required_fields = [
        "id",
        "severity",
        "journey",
        "problem",
        "reproduction",
        "expected",
        "actual",
        "proposed_fix",
    ]
    for idx, finding in enumerate(findings):
        assert isinstance(finding, dict), f"Finding [{idx}] must be a dict"
        for field in required_fields:
            assert field in finding and finding[field], (
                f"Finding [{idx}] missing non-empty required field {field!r}: {finding}"
            )
        assert finding["severity"] in ("Critical", "High", "Medium", "Low"), (
            f"Finding [{idx}] has invalid severity {finding['severity']!r}"
        )


# ============================================================================
# AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius
# ============================================================================


def test_user_journeys_manifest_exists_and_conforms_to_schema() -> None:
    """AC-3: tests/user_journeys_manifest.json exists and conforms to USER_JOURNEYS_MANIFEST_SCHEMA."""
    manifest = _load_manifest_dict()
    assert "journeys" in manifest
    assert "command_allowlist" in manifest
    assert manifest["command_allowlist"] == EXPECTED_COMMAND_ALLOWLIST

    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(manifest))
        assert not errors, f"Manifest schema validation errors: {errors}"


def test_user_journeys_manifest_contains_all_21_journeys() -> None:
    """AC-3: Manifest contains exactly the 21 enumerated user journeys without omission or drift."""
    manifest = _load_manifest_dict()
    actual_names = {j["name"] for j in manifest.get("journeys", [])}
    assert len(actual_names) == 21, f"Expected 21 unique journeys, found {len(actual_names)}"
    assert actual_names == ALL_EXPECTED_JOURNEYS, (
        f"Journey drift detected: missing={ALL_EXPECTED_JOURNEYS - actual_names}, extra={actual_names - ALL_EXPECTED_JOURNEYS}"
    )


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-3: tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are identical."""
    if not JOURNEYS_MANIFEST.exists():
        pytest.skip(f"Secondary manifest mirror {JOURNEYS_MANIFEST} not present")

    tests_manifest = json.loads(_read_disk_file(TESTS_MANIFEST))
    journeys_manifest = json.loads(_read_disk_file(JOURNEYS_MANIFEST))
    assert tests_manifest == journeys_manifest, (
        "tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are not identical"
    )


def test_user_journeys_manifest_traceability_to_acceptance_checks() -> None:
    """AC-3: Every required journey in manifest maps via traces_to to AC-1, AC-2, or AC-3."""
    manifest = _load_manifest_dict()
    journeys = manifest.get("journeys", [])
    covered_acs: set[str] = set()

    for idx, j in enumerate(journeys):
        traces = j.get("traces_to", [])
        assert isinstance(traces, list), f"Journey [{idx}] traces_to must be a list"
        assert len(traces) > 0, f"Journey [{idx}] ({j.get('name')}) has empty traces_to"
        for ac in traces:
            assert ac in ALLOWED_ACCEPTANCE_CHECKS, (
                f"Journey [{idx}] ({j.get('name')}) references invalid acceptance check {ac!r}"
            )
            covered_acs.add(ac)

    assert covered_acs == ALLOWED_ACCEPTANCE_CHECKS, (
        f"Manifest does not cover all contract acceptance checks: missing {ALLOWED_ACCEPTANCE_CHECKS - covered_acs}"
    )


def test_sysdiff_c17_source_and_makefile_hash_pins() -> None:
    """AC-3: src/sysdiff.c and Makefile match canonical baseline SHA-256 hashes."""
    assert SYSDIFF_SRC.is_file(), f"Missing source: {SYSDIFF_SRC}"
    assert MAKEFILE.is_file(), f"Missing Makefile: {MAKEFILE}"

    src_hash = hashlib.sha256(SYSDIFF_SRC.read_bytes()).hexdigest()
    make_hash = hashlib.sha256(MAKEFILE.read_bytes()).hexdigest()

    assert src_hash == BASELINE_SYSDIFF_SHA256, (
        f"src/sysdiff.c modified unexpectedly: expected {BASELINE_SYSDIFF_SHA256}, got {src_hash}"
    )
    assert make_hash == BASELINE_MAKEFILE_SHA256, (
        f"Makefile modified unexpectedly: expected {BASELINE_MAKEFILE_SHA256}, got {make_hash}"
    )


def test_sysdiff_man_page_exists() -> None:
    """AC-3: Manual page man/sysdiff.1 exists and is non-empty."""
    assert MAN_PAGE.is_file(), f"Missing man page: {MAN_PAGE}"
    assert MAN_PAGE.stat().st_size > 0, f"Man page {MAN_PAGE} is empty"


def test_sysdiff_compare_three_state_exit_contract(tmp_path: Path) -> None:
    """AC-3: sysdiff compare preserves the 3-state exit status contract (0, 1, 2)."""
    snap_a = tmp_path / "a.snapshot"
    snap_b = tmp_path / "b.snapshot"
    snap_c = tmp_path / "c.snapshot"

    snap_a.write_text("sysdiff.snapshot_version=1\nos.id=debian\n", encoding="utf-8")
    snap_b.write_text("sysdiff.snapshot_version=1\nos.id=debian\n", encoding="utf-8")
    snap_c.write_text("sysdiff.snapshot_version=1\nos.id=ubuntu\n", encoding="utf-8")

    # State 0: Identical snapshots
    res_0 = _run_sysdiff(["compare", str(snap_a), str(snap_b)])
    assert res_0.returncode == 0, f"Expected exit 0 for identical snapshots, got {res_0.returncode}"
    assert "no changes" in res_0.stdout

    # State 1: Differences found
    res_1 = _run_sysdiff(["compare", str(snap_a), str(snap_c)])
    assert res_1.returncode == 1, f"Expected exit 1 for different snapshots, got {res_1.returncode}"
    assert "os.id" in res_1.stdout

    # State 2: Missing snapshot error
    missing_snap = tmp_path / "nonexistent.snapshot"
    res_2 = _run_sysdiff(["compare", str(snap_a), str(missing_snap)])
    assert res_2.returncode == 2, f"Expected exit 2 for missing snapshot, got {res_2.returncode}"


def test_no_foreign_cross_project_sys_path_contamination() -> None:
    """AC-3: Test modules must not hardcode foreign repository paths like employee-contract into sys.path."""
    this_file = Path(__file__)
    foreign_marker = "/home/lee/projects/" + "employee-contract"
    for line in this_file.read_text(encoding="utf-8").splitlines():
        if foreign_marker in line and not line.strip().startswith("#"):
            pytest.fail(f"Foreign repository path found hardcoded in {this_file.name}: {line.strip()}")
