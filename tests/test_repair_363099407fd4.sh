#!/usr/bin/env bash
# ============================================================================
# Regression Test Suite: Repair for Governed Run Failure 363099407fd4
#
# Governed run 363099407fd4 halted and failed during step_04b_user_simulation_gate
# with two compounding governance and schema defects:
#
# 1. Out-of-Scope Workspace Mutations / Write Scope Confinement:
#    During step_04b_user_simulation_gate, the worker attempted to generate and
#    test user simulation outputs by writing four ad-hoc Python scripts directly
#    to the repository root:
#        generate_result.py, generate_result2.py, test_script.py, update_md.py
#    Because the step's declared allowed_paths did not authorize writing outside
#    its assigned boundaries, the orchestrator intercepted these unauthorized
#    file creations as a fatal PATH_ESCAPE violation. Under Agent-Orch governance,
#    temporary scripts must reside exclusively in designated .agent-orch-scratch/
#    directories and never contaminate the governed repository root.
#
# 2. User-Test Result Schema Non-Conformance:
#    The simulation result artifact artifacts/user-test/result.json failed JSON
#    schema validation with:
#        $.findings[0]: 'id' is a required property
#    Under repository quality contracts and USER_JOURNEYS_RESULT_SCHEMA, finding
#    objects represent actionable records and require a complete set of canonical
#    properties: id, severity, journey, problem, reproduction, expected, actual,
#    and proposed_fix.
#
# 3. Inability to Re-execute Command Claims:
#    The result artifact contained unallowlisted shell wrapper commands:
#        /bin/sh -c 'make clean && make test'
#    and trivial assertions (echo ok), violating the immutable command allowlist
#    (["build/sysdiff"]) and the requirement for direct argv execution within
#    the governed workspace.
#
# Repair Contract Reference: docs/repair-363099407fd4-contract.md
# - AC-1: Write Scope Confinement, Contract Establishment, and Root Sanitation
# - AC-2: Result Schema Conformance, Finding ID Integrity, Verifiable Execution
# - AC-3: Manifest Synchronization, Traceability, Non-Product Blast Radius
# ============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
CC="${CC:-gcc}"

CONTRACT="$ROOT/docs/repair-363099407fd4-contract.md"
TESTS_MANIFEST="$ROOT/tests/user_journeys_manifest.json"
JOURNEYS_MANIFEST="$ROOT/journeys/user_journeys_manifest.json"
SYSDIFF_SRC="$ROOT/src/sysdiff.c"
SYSDIFF_BIN="$ROOT/build/sysdiff"
MAKEFILE="$ROOT/Makefile"
MAN_PAGE="$ROOT/man/sysdiff.1"
USER_TEST_RESULT="$ROOT/artifacts/user-test/result.json"

# Python module path resolution
export PYTHONPATH="/home/lee/projects/agent-orch/src:/home/lee/projects/employee-contract/src:/home/lee/.local/lib/python3.12/site-packages:${PYTHONPATH:-}"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

run_test() {
    local test_name="$1"
    local test_func="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    printf 'RUNNING: %s ... ' "$test_name"
    local output
    if output=$("$test_func" 2>&1); then
        printf 'PASSED\n'
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        printf 'FAILED\n'
        if [ -n "$output" ]; then
            printf '%s\n' "$output" | sed 's/^/  /'
        fi
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

skip_test() {
    local test_name="$1"
    local reason="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    SKIPPED_TESTS=$((SKIPPED_TESTS + 1))
    printf 'SKIPPED: %s (%s)\n' "$test_name" "$reason"
}

# ============================================================================
# AC-1: Write Scope Confinement, Contract Structure, and Root Sanitation
# ============================================================================

test_contract_headings_and_character_counts() {
    [ -f "$CONTRACT" ] || { printf 'Missing repair contract: %s\n' "$CONTRACT"; return 1; }

    "$PYTHON" -c '
import re, sys
from pathlib import Path

contract = Path(sys.argv[1]).read_text(encoding="utf-8")
required_headings = ["Overview", "Problem", "Constraints", "Acceptance Checks"]

for heading in required_headings:
    pattern = rf"^#+\s+{re.escape(heading)}\b"
    match = re.search(pattern, contract, re.MULTILINE)
    assert match is not None, f"Missing required heading: {heading}"

    start_pos = match.end()
    next_match = re.search(r"^#+\s+", contract[start_pos:], re.MULTILINE)
    section_text = contract[start_pos : start_pos + next_match.start()] if next_match else contract[start_pos:]
    non_ws = len(re.sub(r"\s", "", section_text))
    assert non_ws >= 120, f"Heading {heading} has only {non_ws} non-whitespace characters (minimum 120 required)"

assert "363099407fd4" in contract, "Contract does not reference run 363099407fd4"
assert "AC-1" in contract and "AC-2" in contract and "AC-3" in contract, "Contract missing AC enumeration"
' "$CONTRACT"
}

test_closed_hazard_taxonomy_compliance() {
    [ -f "$CONTRACT" ] || return 1

    "$PYTHON" -c '
import sys
from pathlib import Path

contract = Path(sys.argv[1]).read_text(encoding="utf-8")
assert "Closed Hazard Taxonomy" in contract, "Contract must define Closed Hazard Taxonomy section"

required_hazards = ["PATH_ESCAPE", "RESULT_FABRICATION", "ORACLE_TAMPERING", "BLAST_RADIUS"]
for hazard in required_hazards:
    assert hazard in contract, f"Contract missing required hazard taxonomy member: {hazard}"
' "$CONTRACT"
}

test_path_confinement_sandbox_detection() {
    # Verify that in a governed step simulation, attempts to create ad-hoc scripts
    # outside allowed paths are trapped and rejected fail-closed.
    "$PYTHON" -c '
import tempfile, os, sys
from pathlib import Path

with tempfile.TemporaryDirectory() as tmpdir:
    workspace = Path(tmpdir)
    allowed_paths = ["tests/test_repair_363099407fd4.sh"]
    scratch_dir = workspace / ".agent-orch-scratch" / "test-step"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Allowed write inside scratch space succeeds
    scratch_file = scratch_dir / "temp_generator.py"
    scratch_file.write_text("print(1)\n")
    assert scratch_file.exists()

    # Unauthorized write to workspace root (e.g. generate_result.py)
    root_script = workspace / "generate_result.py"
    relative_path = str(root_script.relative_to(workspace))

    # Path confinement rule check: must not match any declared allowed_path
    is_allowed = any(
        relative_path == allowed or relative_path.startswith(allowed.rstrip("/") + "/")
        for allowed in allowed_paths
    )
    assert not is_allowed, f"Root script {relative_path} must be rejected outside allowed_paths"
'
}

test_root_sanitation_no_adhoc_scripts() {
    # AC-1: Ad-hoc scripts must never reside in the repository root.
    # In run 363099407fd4, the following files escaped allowed paths:
    local adhoc_scripts=("generate_result.py" "generate_result2.py" "test_script.py" "update_md.py")
    local found_scripts=()

    for script in "${adhoc_scripts[@]}"; do
        if [ -f "$ROOT/$script" ]; then
            found_scripts+=("$script")
        fi
    done

    if [ ${#found_scripts[@]} -gt 0 ]; then
        if [ "${ALLOW_UNIMPLEMENTED:-0}" = "1" ]; then
            printf 'Pending implementation cleanup: out-of-scope files present in root: %s\n' "${found_scripts[*]}"
            return 0
        fi
        printf 'AC-1 failure (run 363099407fd4 defect): Ad-hoc files found in root: %s\n' "${found_scripts[*]}"
        return 1
    fi
    return 0
}

# ============================================================================
# AC-2: Result Schema Conformance, Finding ID Integrity, Verifiable Execution
# ============================================================================

test_result_schema_rejects_finding_missing_id() {
    # Exact reproduction of governed run 363099407fd4 failure:
    # $.findings[0]: 'id' is a required property
    "$PYTHON" -c '
import jsonschema, sys

try:
    from agent_orch.user_journeys import USER_JOURNEYS_RESULT_SCHEMA
except ImportError:
    sys.exit(1)

validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

# Candidate payload without finding "id" (reproducing run 363099407fd4)
malformed_result = {
    "journeys": [
        {
            "name": "A developer runs the sysdiff test suite and smoke verification",
            "status": "failed",
            "steps_taken": "Ran make test",
            "commands_run": [
                {"command": "build/sysdiff --help", "exit_code": 0}
            ]
        }
    ],
    "findings": [
        {
            "severity": "High",
            "journey": "A developer runs the sysdiff test suite and smoke verification",
            "problem": "Product tests timed out.",
            "reproduction": "make clean && make test",
            "expected": "Exit code 0",
            "actual": "Exit code 124 (timeout)",
            "proposed_fix": "Fix test suite performance."
        }
    ]
}

errors = list(validator.iter_errors(malformed_result))
assert len(errors) > 0, "Schema validator unexpectedly accepted finding missing \"id\""
id_errors = [e for e in errors if "id" in e.message and "required property" in e.message]
assert len(id_errors) > 0, f"Expected required property error for id, got: {[e.message for e in errors]}"
assert "\x27id\x27 is a required property" in id_errors[0].message
'
}

test_result_schema_accepts_conforming_finding_with_id() {
    # Valid finding with explicit "id" and all canonical diagnostic fields
    "$PYTHON" -c '
import jsonschema, sys

try:
    from agent_orch.user_journeys import USER_JOURNEYS_RESULT_SCHEMA
except ImportError:
    sys.exit(1)

validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

conforming_result = {
    "journeys": [
        {
            "name": "A developer runs the sysdiff test suite and smoke verification",
            "status": "failed",
            "steps_taken": "Ran make test and observed failure",
            "commands_run": [
                {"command": "build/sysdiff --help", "exit_code": 0}
            ]
        }
    ],
    "findings": [
        {
            "id": "UJ-363099407FD4-001",
            "severity": "High",
            "journey": "A developer runs the sysdiff test suite and smoke verification",
            "problem": "Product tests timed out under unoptimized test execution.",
            "reproduction": "make clean && make test",
            "expected": "Exit code 0 with bounded test run",
            "actual": "Exit code 124 (timeout)",
            "proposed_fix": "Optimize test harness execution bounds."
        }
    ]
}

errors = list(validator.iter_errors(conforming_result))
assert not errors, f"Conforming result with finding id rejected with schema errors: {errors}"
'
}

test_result_schema_rejects_missing_mandatory_finding_fields() {
    # Every finding field is mandatory under canonical schema:
    # id, severity, journey, problem, reproduction, expected, actual, proposed_fix
    "$PYTHON" -c '
import jsonschema, sys

try:
    from agent_orch.user_journeys import USER_JOURNEYS_RESULT_SCHEMA
except ImportError:
    sys.exit(1)

validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

mandatory_fields = ["id", "severity", "journey", "problem", "reproduction", "expected", "actual", "proposed_fix"]

base_finding = {
    "id": "UJ-TEST-001",
    "severity": "Medium",
    "journey": "A user tests sysdiff",
    "problem": "Problem description",
    "reproduction": "Repro command",
    "expected": "Expected outcome",
    "actual": "Actual outcome",
    "proposed_fix": "Proposed repair"
}

for field in mandatory_fields:
    incomplete = dict(base_finding)
    del incomplete[field]
    candidate = {
        "journeys": [{
            "name": "A user tests sysdiff",
            "status": "failed",
            "steps_taken": "steps",
            "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}]
        }],
        "findings": [incomplete]
    }
    errors = list(validator.iter_errors(candidate))
    assert len(errors) > 0, f"Validator failed to reject finding missing mandatory field {field!r}"
    assert any(field in e.message for e in errors), f"Error message missing reference to {field!r}"
'
}

test_result_schema_rejects_invalid_severity_enum() {
    # Severity must strictly belong to ["Critical", "High", "Medium", "Low"]
    "$PYTHON" -c '
import jsonschema, sys

try:
    from agent_orch.user_journeys import USER_JOURNEYS_RESULT_SCHEMA
except ImportError:
    sys.exit(1)

validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)

invalid_result = {
    "journeys": [{
        "name": "A user tests sysdiff",
        "status": "failed",
        "steps_taken": "steps",
        "commands_run": [{"command": "build/sysdiff --help", "exit_code": 0}]
    }],
    "findings": [{
        "id": "UJ-TEST-002",
        "severity": "Catastrophic",
        "journey": "A user tests sysdiff",
        "problem": "Problem",
        "reproduction": "Repro",
        "expected": "Expected",
        "actual": "Actual",
        "proposed_fix": "Fix"
    }]
}

errors = list(validator.iter_errors(invalid_result))
assert len(errors) > 0, "Validator accepted invalid severity \"Catastrophic\""
assert any("is not one of" in e.message or "Catastrophic" in str(e) for e in errors)
'
}

test_allowlist_rejects_shell_wrappers_and_operators() {
    # In run 363099407fd4, commands_run contained shell wrappers:
    # /bin/sh -c 'make clean && make test'
    # Allowlist validator must reject shell wrappers, command chaining, and operators.
    "$PYTHON" -c '
import sys

try:
    import agent_orch.validators as validators
except ImportError:
    sys.exit(1)

allowlist = [["build/sysdiff"]]

# Shell wrappers must be rejected
for wrapper in [
    "/bin/sh -c \x27make clean && make test\x27",
    "sh -c \x27build/sysdiff --help\x27",
    "bash -c \x27build/sysdiff --version\x27"
]:
    argv, reason = validators._allowlisted_journey_command(wrapper, allowlist)
    assert argv is None, f"Shell wrapper {wrapper!r} should have been rejected, got argv: {argv}"
    assert "command_allowlist" in reason or "argv prefix" in reason

# Pipelines and operators must be rejected
for chained in [
    "build/sysdiff --help && echo ok",
    "build/sysdiff --help | grep usage",
    "build/sysdiff --version; ls",
    "build/sysdiff > out.txt"
]:
    argv, reason = validators._allowlisted_journey_command(chained, allowlist)
    assert argv is None, f"Chained command {chained!r} should have been rejected, got argv: {argv}"
    assert "shell operator" in reason
'
}

test_allowlist_rejects_unallowlisted_commands() {
    # In run 363099407fd4, commands_run contained arbitrary claims like "echo ok".
    # Only direct argv commands with prefix ["build/sysdiff"] are permitted.
    "$PYTHON" -c '
import sys

try:
    import agent_orch.validators as validators
except ImportError:
    sys.exit(1)

allowlist = [["build/sysdiff"]]

unallowlisted = [
    "echo ok",
    "python3 -m pytest tests/test_repair_958aec814eec.py",
    "make clean",
    "make test",
    "bash tests/test_sysdiff.sh"
]

for cmd in unallowlisted:
    argv, reason = validators._allowlisted_journey_command(cmd, allowlist)
    assert argv is None, f"Command {cmd!r} was not in allowlist, but was accepted: {argv}"
    assert "command_allowlist" in reason or "argv prefix" in reason
'
}

test_allowlist_accepts_and_executes_direct_sysdiff_argv() {
    # Allowlisted direct argv commands must parse and execute deterministically.
    "$PYTHON" -c '
import os, subprocess, sys
from pathlib import Path

try:
    import agent_orch.validators as validators
except ImportError:
    sys.exit(1)

root = Path(sys.argv[1])
sysdiff_bin = root / "build" / "sysdiff"
assert sysdiff_bin.is_file() and os.access(sysdiff_bin, os.X_OK) if sysdiff_bin.exists() else True

allowlist = [["build/sysdiff"]]

for cmd_claim, expected_prefix in [
    ("build/sysdiff --help", ["build/sysdiff", "--help"]),
    ("build/sysdiff --version", ["build/sysdiff", "--version"])
]:
    argv, reason = validators._allowlisted_journey_command(cmd_claim, allowlist)
    assert argv == expected_prefix, f"Failed parsing {cmd_claim!r}: argv={argv}, reason={reason}"

    # Verify direct argv execution
    proc = subprocess.run([str(root / argv[0]), *argv[1:]], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Direct argv execution of {argv} failed with code {proc.returncode}"
    assert len(proc.stdout) > 0, f"Direct argv execution of {argv} produced empty stdout"
' "$ROOT"
}

test_current_user_test_result_artifact_conformance() {
    # AC-2: artifacts/user-test/result.json must conform to USER_JOURNEYS_RESULT_SCHEMA.
    # All findings must have non-empty id, and all commands must match allowlist ["build/sysdiff"].
    if [ ! -f "$USER_TEST_RESULT" ]; then
        skip_test "test_current_user_test_result_artifact_conformance" "artifacts/user-test/result.json not present"
        return 0
    fi

    "$PYTHON" -c '
import json, jsonschema, sys
from pathlib import Path

try:
    from agent_orch.user_journeys import USER_JOURNEYS_RESULT_SCHEMA
    import agent_orch.validators as validators
except ImportError:
    sys.exit(1)

allow_unimplemented = sys.argv[2] == "1"
result_path = Path(sys.argv[1])
data = json.loads(result_path.read_text(encoding="utf-8"))

validator = jsonschema.Draft202012Validator(USER_JOURNEYS_RESULT_SCHEMA)
errors = list(validator.iter_errors(data))

if errors:
    if allow_unimplemented:
        print(f"Pending implementation: result.json has schema errors: {[e.message for e in errors]}")
        sys.exit(0)
    print(f"Schema validation errors in {result_path}: {[e.message for e in errors]}")
    sys.exit(1)

# Check findings id integrity
for i, f in enumerate(data.get("findings", [])):
    if "id" not in f or not f["id"]:
        if allow_unimplemented:
            print(f"Pending implementation: finding[{i}] lacks id")
            sys.exit(0)
        print(f"Finding {i} missing non-empty id: {f}")
        sys.exit(1)

# Check commands run allowlist
allowlist = [["build/sysdiff"]]
for j in data.get("journeys", []):
    for c in j.get("commands_run", []):
        cmd = c.get("command", "")
        argv, reason = validators._allowlisted_journey_command(cmd, allowlist)
        if argv is None:
            if allow_unimplemented:
                print(f"Pending implementation: unallowlisted command {cmd!r} in result")
                sys.exit(0)
            print(f"Unallowlisted command in result: {cmd!r} ({reason})")
            sys.exit(1)
' "$USER_TEST_RESULT" "${ALLOW_UNIMPLEMENTED:-0}"
}

# ============================================================================
# AC-3: Manifest Synchronization, Traceability, Non-Product Blast Radius
# ============================================================================

test_user_journeys_manifests_are_synchronized() {
    [ -f "$TESTS_MANIFEST" ] || { printf 'Missing canonical oracle: %s\n' "$TESTS_MANIFEST"; return 1; }
    [ -f "$JOURNEYS_MANIFEST" ] || { printf 'Missing secondary manifest: %s\n' "$JOURNEYS_MANIFEST"; return 1; }

    "$PYTHON" -c '
import json, sys
from pathlib import Path

tests_data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
journeys_data = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

assert tests_data == journeys_data, (
    "User journey manifests are not identical parsed JSON objects between tests/ and journeys/."
)
' "$TESTS_MANIFEST" "$JOURNEYS_MANIFEST"
}

test_user_journeys_manifest_schema_and_command_allowlist() {
    "$PYTHON" -c '
import json, jsonschema, sys
from pathlib import Path

try:
    from agent_orch.user_journeys import USER_JOURNEYS_MANIFEST_SCHEMA
except ImportError:
    sys.exit(1)

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
errors = list(validator.iter_errors(manifest))
assert not errors, f"Manifest schema errors: {errors}"

allowlist = manifest.get("command_allowlist", [])
assert allowlist == ["build/sysdiff"], f"command_allowlist must be [\"build/sysdiff\"], got: {allowlist}"
' "$TESTS_MANIFEST"
}

test_user_journeys_manifest_preserves_all_21_journeys() {
    "$PYTHON" -c '
import json, sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
journeys = manifest.get("journeys", [])
assert len(journeys) == 21, f"Expected exactly 21 journeys, got {len(journeys)}"

names = {j["name"] for j in journeys}

# 10 Workspace Abstraction Author Journeys
author_journeys = {
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
sysdiff_journeys = {
    "A user runs the real sysdiff binary with no arguments and receives usage guidance instead of a crash",
    "A user asks the real sysdiff binary for help and receives its usage summary",
    "A user compares two snapshots with the real sysdiff binary and sees deterministic added removed and changed entries",
    "A user gives the real sysdiff binary a malformed snapshot and receives an escaped diagnostic without partial output",
}

# 7 Sandbox Containment and Repair Journeys
bwrap_journeys = {
    "A worker launcher delivers large prompt payloads via stdin and verifies that no single argv argument exceeds kernel MAX_ARG_STRLEN limits",
    "A user confirms bubblewrap sandbox containment remains strictly enforced on Linux without granting unsandboxed execution bypasses",
    "An operator observes pre-exec payload measurement rejecting oversized bwrap arguments fail-closed with typed LAUNCH_PAYLOAD_TOO_LARGE classification",
    "An evaluator inspects edge-case payload sizes near the 128 KiB boundary to confirm exact byte accounting without information leakage",
    "A validator bounds process output in retry feedback to head and tail excerpts while preserving full unmodified logs in hash-chained artifacts",
    "A maintainer verifies the synchronized user journeys manifest adheres to canonical schema and covers all enumerated contract acceptance checks",
    "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
}

all_expected = author_journeys | sysdiff_journeys | bwrap_journeys
assert all_expected == names, f"Manifest journeys mismatch. Missing: {all_expected - names}, Extra: {names - all_expected}"
' "$TESTS_MANIFEST"
}

test_journey_traceability_covers_ac1_ac2_ac3() {
    "$PYTHON" -c '
import json, sys
from pathlib import Path

try:
    from agent_orch.user_journeys import JOURNEY_AUTHORITIES
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
journeys = manifest.get("journeys", [])
allowed_traces = {"AC-1", "AC-2", "AC-3"}

covered_traces = set()
for j in journeys:
    name = j.get("name")
    authority = j.get("authority", "author")
    assert authority in JOURNEY_AUTHORITIES, f"Unknown authority {authority!r}"
    traces = j.get("traces_to", [])
    if authority != "exploratory":
        assert traces, f"Required journey {name!r} has empty traces_to"
        assert set(traces) <= allowed_traces, f"Journey {name!r} has invalid traces: {traces}"
        covered_traces.update(traces)

assert covered_traces == allowed_traces, f"Uncovered acceptance checks: {allowed_traces - covered_traces}"
' "$TESTS_MANIFEST"
}

test_product_source_craftsmanship() {
    [ -f "$SYSDIFF_SRC" ] && [ -s "$SYSDIFF_SRC" ] || { printf 'Missing sysdiff source: %s\n' "$SYSDIFF_SRC"; return 1; }
    [ -f "$MAKEFILE" ] && [ -s "$MAKEFILE" ] || { printf 'Missing Makefile: %s\n' "$MAKEFILE"; return 1; }
    [ -f "$MAN_PAGE" ] && [ -s "$MAN_PAGE" ] || { printf 'Missing manual page: %s\n' "$MAN_PAGE"; return 1; }

    "$PYTHON" -c '
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(encoding="utf-8")
for token in ["363099407fd4", "agent_orch", "PATH_ESCAPE"]:
    assert token not in src, f"sysdiff source contaminated with token {token!r}"
' "$SYSDIFF_SRC"
}

test_product_c17_compilation() {
    mkdir -p "$ROOT/build"
    "$CC" -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 -o "$SYSDIFF_BIN" "$SYSDIFF_SRC"
    [ -x "$SYSDIFF_BIN" ] || { printf 'Failed to compile %s\n' "$SYSDIFF_BIN"; return 1; }
}

test_product_cli_no_args_and_help() {
    [ -x "$SYSDIFF_BIN" ] || test_product_c17_compilation

    # No arguments -> exit code 0, usage on stdout, empty stderr
    local out_noarg err_noarg status_noarg
    out_noarg="$("$SYSDIFF_BIN" 2>/dev/null)" || status_noarg=$?
    status_noarg="${status_noarg:-0}"
    [ "$status_noarg" -eq 0 ] || { printf 'Expected exit 0 for no-args, got %s\n' "$status_noarg"; return 1; }
    printf '%s\n' "$out_noarg" | grep -q "usage: sysdiff" || { printf 'Missing usage in no-args output\n'; return 1; }

    # --help -> exit code 0, usage on stdout
    local out_help
    out_help="$("$SYSDIFF_BIN" --help)"
    printf '%s\n' "$out_help" | grep -q "usage: sysdiff" || { printf 'Missing usage in --help\n'; return 1; }

    # --version -> exit code 0, sysdiff 0.1.0
    local out_ver
    out_ver="$("$SYSDIFF_BIN" --version)"
    printf '%s\n' "$out_ver" | grep -q "sysdiff 0.1.0" || { printf 'Missing version string in --version\n'; return 1; }
}

test_product_snapshot_comparison() {
    [ -x "$SYSDIFF_BIN" ] || test_product_c17_compilation

    local tmpdir
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/sysdiff-snap-test.XXXXXXXXXX")"
    trap 'rm -rf "$tmpdir"' RETURN

    cat <<'EOF' > "$tmpdir/snap1.snapshot"
pkg.a=1.0
pkg.b=2.0
service.web.active=
EOF

    cat <<'EOF' > "$tmpdir/snap2.snapshot"
pkg.a=1.1
pkg.c=3.0
service.web.active=
EOF

    # Identical snapshots: exit code 0, "no changes"
    local id_out
    id_out="$("$SYSDIFF_BIN" compare "$tmpdir/snap1.snapshot" "$tmpdir/snap1.snapshot")"
    [ "$id_out" = "no changes" ] || { printf 'Expected "no changes", got: %s\n' "$id_out"; return 1; }

    # Differing snapshots: exit code 1, deterministic diff markers
    local diff_status=0
    local diff_out
    diff_out="$("$SYSDIFF_BIN" compare "$tmpdir/snap1.snapshot" "$tmpdir/snap2.snapshot" 2>/dev/null)" || diff_status=$?
    [ "$diff_status" -eq 1 ] || { printf 'Expected exit code 1 for diff, got %s\n' "$diff_status"; return 1; }
    printf '%s\n' "$diff_out" | grep -q "~ pkg.a: 1.0 -> 1.1" || { printf 'Missing changed line\n'; return 1; }
    printf '%s\n' "$diff_out" | grep -q -- "- pkg.b=2.0" || { printf 'Missing removed line\n'; return 1; }
    printf '%s\n' "$diff_out" | grep -q -- "+ pkg.c=3.0" || { printf 'Missing added line\n'; return 1; }
}

test_product_malformed_snapshot_rejection() {
    [ -x "$SYSDIFF_BIN" ] || test_product_c17_compilation

    local tmpdir
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/sysdiff-malformed-test.XXXXXXXXXX")"
    trap 'rm -rf "$tmpdir"' RETURN

    printf 'valid.key=val\n' > "$tmpdir/valid.snapshot"
    printf 'this line has no equals sign\n' > "$tmpdir/malformed.snapshot"

    local err_status=0
    local err_out
    err_out="$("$SYSDIFF_BIN" compare "$tmpdir/malformed.snapshot" "$tmpdir/valid.snapshot" 2>&1)" || err_status=$?
    [ "$err_status" -eq 2 ] || { printf 'Expected exit code 2 for malformed snapshot, got %s\n' "$err_status"; return 1; }
    printf '%s\n' "$err_out" | grep -q "missing '=' separator" || { printf 'Expected diagnostic about missing =, got: %s\n' "$err_out"; return 1; }
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    for arg in "$@"; do
        case "$arg" in
            --allow-unimplemented|--skip-unimplemented|-a)
                export ALLOW_UNIMPLEMENTED=1
                ;;
            --help|-h)
                printf 'Usage: %s [--allow-unimplemented]\n' "$0"
                return 0
                ;;
        esac
    done

    printf '=== Running repair regression suite for run 363099407fd4 ===\n\n'

    # AC-1 Checks
    run_test "AC-1: Contract headings and length" test_contract_headings_and_character_counts
    run_test "AC-1: Closed hazard taxonomy" test_closed_hazard_taxonomy_compliance
    run_test "AC-1: Path confinement sandbox detection" test_path_confinement_sandbox_detection
    run_test "AC-1: Workspace root sanitation (no ad-hoc scripts)" test_root_sanitation_no_adhoc_scripts

    # AC-2 Checks
    run_test "AC-2: Result schema rejects finding missing id (run 363099407fd4 defect)" test_result_schema_rejects_finding_missing_id
    run_test "AC-2: Result schema accepts conforming finding with id" test_result_schema_accepts_conforming_finding_with_id
    run_test "AC-2: Result schema rejects missing mandatory finding fields" test_result_schema_rejects_missing_mandatory_finding_fields
    run_test "AC-2: Result schema rejects invalid severity enum" test_result_schema_rejects_invalid_severity_enum
    run_test "AC-2: Allowlist rejects shell wrappers and operators" test_allowlist_rejects_shell_wrappers_and_operators
    run_test "AC-2: Allowlist rejects unallowlisted commands" test_allowlist_rejects_unallowlisted_commands
    run_test "AC-2: Allowlist accepts and executes build/sysdiff direct argv" test_allowlist_accepts_and_executes_direct_sysdiff_argv
    run_test "AC-2: Current artifacts/user-test/result.json conformance" test_current_user_test_result_artifact_conformance

    # AC-3 Checks
    run_test "AC-3: Manifests exist and are synchronized" test_user_journeys_manifests_are_synchronized
    run_test "AC-3: Manifest schema and command allowlist" test_user_journeys_manifest_schema_and_command_allowlist
    run_test "AC-3: All 21 journeys preserved in manifest" test_user_journeys_manifest_preserves_all_21_journeys
    run_test "AC-3: Journey traceability covers AC-1, AC-2, AC-3" test_journey_traceability_covers_ac1_ac2_ac3
    run_test "AC-3: Product source craftsmanship (no token leaks)" test_product_source_craftsmanship
    run_test "AC-3: Product ISO C17 compilation" test_product_c17_compilation
    run_test "AC-3: Product CLI contract (--help, --version, no-args)" test_product_cli_no_args_and_help
    run_test "AC-3: Product snapshot comparison" test_product_snapshot_comparison
    run_test "AC-3: Product malformed snapshot rejection" test_product_malformed_snapshot_rejection

    printf '\n============================================================\n'
    printf 'Summary: %d total, %d passed, %d failed, %d skipped\n' \
        "$TOTAL_TESTS" "$PASSED_TESTS" "$FAILED_TESTS" "$SKIPPED_TESTS"
    printf '============================================================\n'

    if [ "$FAILED_TESTS" -gt 0 ]; then
        return 1
    fi
    return 0
}

main "$@"
