"""Regression suite for repairing governed run failure 0191293dc09e.

Governed run 0191293dc09e failed at step_08b_user_simulation_gate (attempt 1) with:
    Unaccounted spend: Missing usage telemetry for metered worker 'codex_cli'
    for step 'step_08b_user_simulation_gate'

Failure analysis and root causes:
1. Root Cause 1 (telemetry accounting):
   Step 'step_08b_user_simulation_gate' ran with worker adapter 'codex_cli',
   an instance of CodexCLIAdapter inheriting from CommandWorkerAdapter.
   Metered worker adapters require token usage reporting (identity.is_metered == True,
   usage_reporting == "required"). When codex_cli executed, it did not emit
   a usage artifact (usage.json) into context.step_run_dir or context.scratch_dir,
   and CommandWorkerAdapter.extract_usage returned None.
   In engine._price_execution_records, an unpopulated usage on a metered worker
   marks accounting_status as "unaccounted" with error:
   "Missing usage telemetry for metered worker 'codex_cli'".
   The engine then halted execution fail-closed with budget refusal:
   "Unaccounted spend: Missing usage telemetry for metered worker 'codex_cli' for step 'step_08b_user_simulation_gate'".

2. Root Cause 2 (manifest desynchronization - finding UJ-0191293D-001):
   In the same attempt 1 of step_08b_user_simulation_gate, the evaluator inspected
   the user journey manifests and logged finding UJ-0191293D-001:
   tests/user_journeys_manifest.json contains 21 journeys covering AC-1 through AC-3,
   whereas journeys/user_journeys_manifest.json contained only 13 journeys,
   omitting eight preserved workspace-abstraction author journeys. Journey 20:
   "A maintainer verifies the synchronized user journeys manifest adheres to
   canonical schema and covers all enumerated contract acceptance checks"
   failed because the secondary copy was not synchronized with the canonical tests oracle.

3. Repair Contract:
   - Metered worker executions without usage telemetry must fail closed with
     "Missing usage telemetry for metered worker '<adapter_id>'".
   - Metered worker executions with valid TokenUsage telemetry must reach
     "measured" accounting status and finite priced cost without unaccounted spend.
   - Evaluator or validation-only executions with usage_reporting == "not_applicable"
     must resolve to "not_applicable" status and never trigger spend refusals.
   - CommandWorkerAdapter / CodexCLIAdapter must extract usage from step_run_dir
     and scratch_dir, rejecting invalid or conflicting usage payloads.
   - Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json
     must be synchronized identical parsed objects containing all 21 journeys.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

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
    from employee_contract.usage import TokenUsage, UsageError
except ImportError:
    TokenUsage = None  # type: ignore[assignment]
    UsageError = Exception  # type: ignore[assignment]

try:
    from agent_orch.engine import _price_execution_records
    from agent_orch.rate_table import ModelRate, RateTable
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
    )
    from agent_orch.worker import (
        AdapterExecutionIdentity,
        AdapterExecutionRecord,
        CodexCLIAdapter,
        CommandWorkerAdapter,
    )
except ImportError:
    _price_execution_records = None  # type: ignore[assignment]
    ModelRate = None  # type: ignore[assignment]
    RateTable = None  # type: ignore[assignment]
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]
    AdapterExecutionIdentity = None  # type: ignore[assignment]
    AdapterExecutionRecord = None  # type: ignore[assignment]
    CodexCLIAdapter = None  # type: ignore[assignment]
    CommandWorkerAdapter = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
PLAYBOOK_FILE = ROOT / "playbooks" / "governed-workspace-abstraction.yaml"

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
class _MockStepContext:
    """Minimal StepContext stand-in for testing adapter usage extraction."""

    step_run_dir: Path
    scratch_dir: Path | None = None


def test_metered_codex_cli_missing_usage_telemetry_fails_with_unaccounted_spend() -> None:
    """A metered codex_cli execution record without TokenUsage fails with exact unaccounted spend error."""
    if _price_execution_records is None or AdapterExecutionIdentity is None:
        pytest.skip("agent_orch components not importable in this environment")

    identity = AdapterExecutionIdentity(
        adapter_id="codex_cli",
        usage_reporting="required",
        route={"model": "gpt-5-codex"},
    )
    assert identity.is_metered is True

    record = AdapterExecutionRecord(identity=identity, usage=None)
    usage, cost, status, reason = _price_execution_records(
        [record],
        rate_table=None,
        fallback_model="gpt-5-codex",
    )

    assert status == "unaccounted"
    assert reason == "Missing usage telemetry for metered worker 'codex_cli'"
    assert usage is None
    assert cost == 0.0

    step_id = "step_08b_user_simulation_gate"
    budget_refusal_error = f"Unaccounted spend: {reason} for step {step_id!r}"
    expected_error = (
        "Unaccounted spend: Missing usage telemetry for metered worker 'codex_cli' "
        "for step 'step_08b_user_simulation_gate'"
    )
    assert budget_refusal_error == expected_error


def test_metered_codex_cli_with_valid_usage_telemetry_reaches_measured_status() -> None:
    """When valid TokenUsage telemetry is provided for codex_cli, accounting reaches measured status."""
    if _price_execution_records is None or TokenUsage is None or RateTable is None or ModelRate is None:
        pytest.skip("agent_orch or employee_contract components not importable in this environment")

    rate = ModelRate(
        model="gpt-5-codex",
        source_url="https://example.com/rates",
        as_of="2026-09-01",
        input_usd_per_1m=2.5,
        output_usd_per_1m=10.0,
    )
    table = RateTable(rates={"gpt-5-codex": rate})

    identity = AdapterExecutionIdentity(
        adapter_id="codex_cli",
        usage_reporting="required",
        route={"model": "gpt-5-codex"},
    )

    token_usage = TokenUsage(
        model="gpt-5-codex",
        input_tokens=1200,
        output_tokens=350,
        total_tokens=1550,
    )
    record = AdapterExecutionRecord(identity=identity, usage=token_usage)

    priced_usage, cost, status, reason = _price_execution_records(
        [record],
        rate_table=table,
        fallback_model="gpt-5-codex",
    )

    assert status == "measured"
    assert reason is None
    assert math.isfinite(cost)
    assert cost > 0.0
    assert priced_usage is not None
    assert priced_usage.input_tokens == 1200
    assert priced_usage.output_tokens == 350
    assert priced_usage.total_tokens == 1550


def test_unmetered_evaluator_route_bypasses_spend_gate() -> None:
    """An unmetered evaluator or validation-only route produces not_applicable status without spend errors."""
    if _price_execution_records is None or AdapterExecutionIdentity is None:
        pytest.skip("agent_orch components not importable in this environment")

    identity = AdapterExecutionIdentity(
        adapter_id="deterministic_evaluator",
        usage_reporting="not_applicable",
        route={},
    )
    assert identity.is_metered is False

    record = AdapterExecutionRecord(identity=identity, usage=None)
    usage, cost, status, reason = _price_execution_records(
        [record],
        rate_table=None,
        fallback_model=None,
    )

    assert status == "not_applicable"
    assert reason is None
    assert cost == 0.0


def test_codex_cli_usage_extraction_contract(tmp_path: Path) -> None:
    """CommandWorkerAdapter / CodexCLIAdapter extracts valid usage and rejects missing or conflicting files."""
    if CodexCLIAdapter is None or TokenUsage is None or UsageError is None:
        pytest.skip("CodexCLIAdapter or TokenUsage not importable in this environment")

    adapter = CodexCLIAdapter()
    step_run_dir = tmp_path / "step_run"
    step_run_dir.mkdir()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    context = _MockStepContext(step_run_dir=step_run_dir, scratch_dir=scratch_dir)

    # 1. Missing usage artifact returns None (reproducing the condition that caused unaccounted spend)
    extracted = adapter.extract_usage(context, stdout="", stderr="", metadata={})  # type: ignore[arg-type]
    assert extracted is None

    # 2. Valid usage.json in step_run_dir is parsed correctly
    usage_file = step_run_dir / "usage.json"
    usage_file.write_text(
        json.dumps({
            "model": "gpt-5-codex",
            "input_tokens": 500,
            "output_tokens": 150,
            "total_tokens": 650,
        }),
        encoding="utf-8",
    )
    extracted = adapter.extract_usage(context, stdout="", stderr="", metadata={})  # type: ignore[arg-type]
    assert isinstance(extracted, TokenUsage)
    assert extracted.model == "gpt-5-codex"
    assert extracted.input_tokens == 500
    assert extracted.output_tokens == 150
    assert extracted.total_tokens == 650

    # 3. Conflicting usage.json in scratch_dir raises UsageError fail-closed
    scratch_usage_file = scratch_dir / "usage.json"
    scratch_usage_file.write_text(
        json.dumps({
            "model": "gpt-5-codex",
            "input_tokens": 999,
            "output_tokens": 1,
            "total_tokens": 1000,
        }),
        encoding="utf-8",
    )
    with pytest.raises(UsageError, match="conflicting usage artifacts"):
        adapter.extract_usage(context, stdout="", stderr="", metadata={})  # type: ignore[arg-type]

    # 4. Malformed JSON raises UsageError
    scratch_usage_file.unlink()
    usage_file.write_text("not valid json", encoding="utf-8")
    with pytest.raises(UsageError, match="invalid usage artifact"):
        adapter.extract_usage(context, stdout="", stderr="", metadata={})  # type: ignore[arg-type]


def test_step_08b_user_simulation_gate_playbook_specification() -> None:
    """The playbook step_08b_user_simulation_gate must specify required inputs, outputs, and validators."""
    assert PLAYBOOK_FILE.exists(), f"Missing playbook: {PLAYBOOK_FILE}"
    content = PLAYBOOK_FILE.read_text(encoding="utf-8")

    # In governed-workspace-abstraction.yaml, steps are YAML/JSON objects
    assert "step_08b_user_simulation_gate" in content, (
        "playbooks/governed-workspace-abstraction.yaml missing step_08b_user_simulation_gate"
    )
    assert "artifacts/user-test/result.json" in content
    assert "artifacts/user-test/findings-log.md" in content
    assert "tests/user_journeys_manifest.json" in content
    assert "user_journeys_all_passed" in content
    assert "user_journeys_execution_verified" in content


def test_tests_user_journeys_manifest_integrity_and_schema() -> None:
    """tests/user_journeys_manifest.json must exist, parse, have 21 journeys, and satisfy the schema."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))

    journeys = manifest.get("journeys", [])
    assert len(journeys) == 21, f"Expected 21 journeys in tests/ manifest, got {len(journeys)}"

    names = {j["name"] for j in journeys}
    missing_expected = ALL_EXPECTED_JOURNEYS - names
    assert not missing_expected, f"tests/ manifest missing expected journeys: {missing_expected}"

    allowlist = manifest.get("command_allowlist", [])
    assert allowlist == ["build/sysdiff"], f"Unexpected command_allowlist: {allowlist}"

    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(manifest))
        assert not errors, f"Schema validation errors in {TESTS_MANIFEST}: {errors}"


def test_user_journeys_manifests_are_synchronized() -> None:
    """Both repository manifests must describe the same 21 journeys, authorities, traces, and allowlist.

    In governed run 0191293dc09e, step_08b_user_simulation_gate attempt 1 filed finding
    UJ-0191293D-001 because journeys/user_journeys_manifest.json contained only 13 journeys
    and omitted eight preserved workspace-abstraction journeys.
    This test reproduces that finding fail-closed until implementation synchronizes
    journeys/user_journeys_manifest.json from the canonical tests/user_journeys_manifest.json oracle.
    """
    assert TESTS_MANIFEST.exists(), f"Missing canonical oracle {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest {JOURNEYS_MANIFEST}"

    tests_manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_manifest = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    tests_journeys = tests_manifest.get("journeys", [])
    journeys_journeys = journeys_manifest.get("journeys", [])

    tests_names = {j["name"] for j in tests_journeys}
    journeys_names = {j["name"] for j in journeys_journeys}

    missing_in_secondary = tests_names - journeys_names
    assert not missing_in_secondary, (
        f"journeys/user_journeys_manifest.json is unsynchronized and missing {len(missing_in_secondary)} "
        f"journeys from tests/user_journeys_manifest.json (finding UJ-0191293D-001): {sorted(missing_in_secondary)}"
    )

    extra_in_secondary = journeys_names - tests_names
    assert not extra_in_secondary, (
        f"journeys/user_journeys_manifest.json contains extra journeys not in tests/: {sorted(extra_in_secondary)}"
    )

    assert tests_manifest.get("command_allowlist") == journeys_manifest.get("command_allowlist"), (
        f"command_allowlist mismatch: {tests_manifest.get('command_allowlist')} vs {journeys_manifest.get('command_allowlist')}"
    )

    assert tests_manifest == journeys_manifest, (
        "Repository journey manifests are not identical parsed objects."
    )
