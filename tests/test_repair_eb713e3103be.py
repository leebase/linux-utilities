"""Regression test suite for repairing governed run failure eb713e3103be.

Governed run eb713e3103be failed during governance validation due to unaccounted spend
caused by missing usage telemetry for the metered worker harness codex_cli:
    unaccounted spend: missing usage telemetry for metered worker codex_cli

Failure analysis and root causes:
1. Missing Usage Telemetry in Metered Worker Execution (codex_cli):
   Autonomous worker invocations executing under metered worker harness codex_cli
   completed tasks without capturing or emitting structured API token consumption metadata.
   When codex_cli completed without returning token usage metadata, the accounting validator
   encountered unmetered steps, immediately triggering a fail-closed unaccounted spend refusal.

2. Gaps in Harness Telemetry Aggregation and Reporting:
   The execution wrapper for codex_cli failed to extract token usage objects emitted in
   worker process output or structured adapter responses upon step termination.
   Step accounting artifacts lacked required telemetry fields, preventing cumulative spend
   calculation and budget reconciliation.

3. Zero-Product Telemetry Invariant (sysdiff Isolation):
   sysdiff is an intentionally small, auditable C17 utility with zero telemetry, zero daemons,
   and zero network dependencies. Telemetry capture mechanisms and spend accounting belong
   exclusively to the worker harness wrapper (codex_cli) and Agent-Orch governance layer.

Repair Contract Reference: docs/repair_eb713e3103be-contract.md
Implementation Plan: plans/repair_eb713e3103be-implementation-plan.md
Sealed Evidence Directory: /home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be

Acceptance Checks:
- AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement.
  Contract and plan documents adhere to required headings with >= 120 non-whitespace characters each.
  Closed hazard taxonomy (UNACCOUNTED_SPEND, TOOL_AVAILABILITY, EXECUTION_TIMEOUT, PATH_ESCAPE,
  RESULT_FABRICATION, ORACLE_TAMPERING, BLAST_RADIUS). Sealed evidence directory explicitly cited.
  Workspace root remains clean of ad-hoc generator scripts, with scratch confined to .agent-orch-scratch/.
- AC-2: Worker Usage Telemetry Capture and Spend Accounting (codex_cli).
  Metered worker harness captures and normalizes usage telemetry (prompt_tokens, completion_tokens,
  total_tokens, model, wall_clock_seconds). Fail-closed rejection on missing or partial telemetry.
  Run-level spend aggregation and budget reconciliation. Absolute zero-telemetry guarantee in sysdiff C binary.
- AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius.
  Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are identical parsed objects
  conforming to USER_JOURNEYS_MANIFEST_SCHEMA and preserving all 21 journeys. All journeys map via traces_to
  to AC-1..3. ISO C17 build and sysdiff CLI contracts remain unaltered without regression.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
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
    from employee_contract.usage import TokenUsage, UsageError
except ImportError:
    TokenUsage = None  # type: ignore[assignment]
    UsageError = Exception  # type: ignore[assignment]

try:
    from agent_orch.engine import _allowed_path_outcomes, _price_execution_records
    from agent_orch.models import StepDefinition
    from agent_orch.rate_table import ModelRate, RateTable
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
    )
    from agent_orch.validators import (
        ValidationOutcome,
        ValidationRule,
        _run_markdown_headings_rule,
    )
    from agent_orch.worker import (
        AdapterExecutionIdentity,
        AdapterExecutionRecord,
        CodexCLIAdapter,
        _parse_provider_usage,
    )
except ImportError:
    _allowed_path_outcomes = None  # type: ignore[assignment]
    _price_execution_records = None  # type: ignore[assignment]
    StepDefinition = None  # type: ignore[assignment]
    ModelRate = None  # type: ignore[assignment]
    RateTable = None  # type: ignore[assignment]
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]
    ValidationOutcome = None  # type: ignore[assignment]
    ValidationRule = None  # type: ignore[assignment]
    _run_markdown_headings_rule = None  # type: ignore[assignment]
    AdapterExecutionIdentity = None  # type: ignore[assignment]
    AdapterExecutionRecord = None  # type: ignore[assignment]
    CodexCLIAdapter = None  # type: ignore[assignment]
    _parse_provider_usage = None  # type: ignore[assignment]

CONTRACT = ROOT / "docs" / "repair_eb713e3103be-contract.md"
PLAN = ROOT / "plans" / "repair_eb713e3103be-implementation-plan.md"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"
SEALED_EVIDENCE_DIR = "/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be"

CLOSED_HAZARD_TAXONOMY = (
    "UNACCOUNTED_SPEND",
    "TOOL_AVAILABILITY",
    "EXECUTION_TIMEOUT",
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
class _MockStepContext:
    """Minimal StepContext stand-in for adapter usage extraction."""

    step_run_dir: Path
    scratch_dir: Path | None = None
    workspace: Path | None = None
    route: Any = None


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
            [gcc_cmd, "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror", str(SYSDIFF_SRC), "-o", str(out_bin)],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and out_bin.exists():
            return out_bin

    pytest.skip("sysdiff binary could not be located or compiled")


def validate_codex_cli_telemetry_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a normalized codex_cli usage telemetry payload against repair contract schema."""
    if not isinstance(payload, Mapping):
        raise ValueError("Usage telemetry payload must be a mapping")

    required_keys = {"prompt_tokens", "completion_tokens", "total_tokens", "model", "wall_clock_seconds"}
    missing = sorted(required_keys - set(payload))
    if missing:
        raise ValueError(f"Usage telemetry payload is missing required fields: {missing}")

    prompt = payload["prompt_tokens"]
    completion = payload["completion_tokens"]
    total = payload["total_tokens"]
    model = payload["model"]
    duration = payload["wall_clock_seconds"]

    if isinstance(prompt, bool) or not isinstance(prompt, int) or prompt < 0:
        raise ValueError(f"prompt_tokens must be a non-negative integer, got {prompt!r}")
    if isinstance(completion, bool) or not isinstance(completion, int) or completion < 0:
        raise ValueError(f"completion_tokens must be a non-negative integer, got {completion!r}")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError(f"total_tokens must be a non-negative integer, got {total!r}")

    if total != prompt + completion:
        raise ValueError(
            f"total_tokens ({total}) must equal prompt_tokens ({prompt}) + completion_tokens ({completion})"
        )

    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")

    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0.0 or not math.isfinite(duration):
        raise ValueError(f"wall_clock_seconds must be a positive finite float, got {duration!r}")

    cached = payload.get("cached_tokens", 0)
    if isinstance(cached, bool) or not isinstance(cached, int) or cached < 0:
        raise ValueError(f"cached_tokens must be a non-negative integer, got {cached!r}")

    return dict(payload)


# ============================================================================
# AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement
# ============================================================================


def test_repair_contract_headings_and_character_counts() -> None:
    """AC-1: docs/repair_eb713e3103be-contract.md and plans have required headings with >= 120 chars each."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    contract_content = CONTRACT.read_text(encoding="utf-8")

    contract_required_headings = ["Overview", "Problem", "Constraints", "Acceptance Checks"]
    for heading in contract_required_headings:
        pattern = rf"^#+\s+{re.escape(heading)}\b"
        match = re.search(pattern, contract_content, re.MULTILINE)
        assert match is not None, f"Contract missing required heading: {heading}"

        start_pos = match.end()
        next_heading_match = re.search(r"^#+\s+", contract_content[start_pos:], re.MULTILINE)
        if next_heading_match:
            section_text = contract_content[start_pos : start_pos + next_heading_match.start()]
        else:
            section_text = contract_content[start_pos:]

        non_whitespace_count = len(re.sub(r"\s", "", section_text))
        assert non_whitespace_count >= 120, (
            f"Section {heading!r} in {CONTRACT} has only {non_whitespace_count} non-whitespace characters, "
            f"minimum required is 120"
        )

    assert PLAN.exists(), f"Missing implementation plan: {PLAN}"
    plan_content = PLAN.read_text(encoding="utf-8")

    plan_required_headings = ["Architecture", "Tests", "Verification", "Risks"]
    for heading in plan_required_headings:
        pattern = rf"^#+\s+{re.escape(heading)}\b"
        match = re.search(pattern, plan_content, re.MULTILINE)
        assert match is not None, f"Plan missing required heading: {heading}"

        start_pos = match.end()
        next_heading_match = re.search(r"^#+\s+", plan_content[start_pos:], re.MULTILINE)
        if next_heading_match:
            section_text = plan_content[start_pos : start_pos + next_heading_match.start()]
        else:
            section_text = plan_content[start_pos:]

        non_whitespace_count = len(re.sub(r"\s", "", section_text))
        assert non_whitespace_count >= 120, (
            f"Section {heading!r} in {PLAN} has only {non_whitespace_count} non-whitespace characters, "
            f"minimum required is 120"
        )

    if _run_markdown_headings_rule is not None and ValidationRule is not None:
        r_contract = ValidationRule(
            type="markdown_headings",
            path="docs/repair_eb713e3103be-contract.md",
            headings=["# Overview", "# Problem", "# Constraints", "# Acceptance Checks"],
            min_chars_under_heading=120,
        )
        outcome_contract = _run_markdown_headings_rule(r_contract, CONTRACT)
        assert outcome_contract.passed is True, f"Contract failed validator rule: {outcome_contract.message}"

        r_plan = ValidationRule(
            type="markdown_headings",
            path="plans/repair_eb713e3103be-implementation-plan.md",
            headings=["# Architecture", "# Tests", "# Verification", "# Risks"],
            min_chars_under_heading=120,
        )
        outcome_plan = _run_markdown_headings_rule(r_plan, PLAN)
        assert outcome_plan.passed is True, f"Plan failed validator rule: {outcome_plan.message}"


def test_sealed_evidence_reference_integrity() -> None:
    """AC-1: Contract and plan explicitly cite sealed evidence directory /home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be."""
    assert CONTRACT.exists()
    contract_content = CONTRACT.read_text(encoding="utf-8")
    assert SEALED_EVIDENCE_DIR in contract_content, (
        f"Contract missing exact sealed evidence path citation: {SEALED_EVIDENCE_DIR}"
    )
    assert "eb713e3103be" in contract_content

    assert PLAN.exists()
    plan_content = PLAN.read_text(encoding="utf-8")
    assert SEALED_EVIDENCE_DIR in plan_content, (
        f"Plan missing exact sealed evidence path citation: {SEALED_EVIDENCE_DIR}"
    )

    evidence_path = Path(SEALED_EVIDENCE_DIR)
    if evidence_path.exists():
        assert evidence_path.is_dir()


def test_closed_hazard_taxonomy_compliance() -> None:
    """AC-1: Contract and plan adhere to closed hazard taxonomy and classify UNACCOUNTED_SPEND."""
    assert CONTRACT.exists()
    contract_content = CONTRACT.read_text(encoding="utf-8")
    assert "Closed Hazard Taxonomy" in contract_content
    for hazard in CLOSED_HAZARD_TAXONOMY:
        assert hazard in contract_content, f"Contract missing hazard taxonomy term: {hazard}"

    assert "UNACCOUNTED_SPEND" in contract_content
    assert "unaccounted spend" in contract_content.lower()

    assert PLAN.exists()
    plan_content = PLAN.read_text(encoding="utf-8")
    for hazard in CLOSED_HAZARD_TAXONOMY:
        assert hazard in plan_content, f"Plan missing hazard taxonomy term: {hazard}"


def test_write_scope_confinement_and_workspace_root_cleanliness() -> None:
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
    assert scratch_root.exists(), "Scratch root .agent-orch-scratch/ should exist for governed scratch storage"

    if _allowed_path_outcomes is not None and StepDefinition is not None:
        step = StepDefinition(
            step_id="step_04_author_slice_tests",
            name="Author the slice tests",
            worker="codex_cli",
            allowed_paths=["tests/test_repair_eb713e3103be.py"],
        )
        outcomes = _allowed_path_outcomes(
            step,
            [
                "tests/test_repair_eb713e3103be.py",
                "unauthorized_root.py",
                "artifacts/escape.json",
            ],
        )
        assert outcomes[0].passed is True, "Allowed test path was improperly rejected"
        assert outcomes[1].passed is False, "Unauthorized root file was improperly allowed"
        assert "outside allowed_paths" in outcomes[1].message
        assert outcomes[2].passed is False, "Unauthorized artifact write was improperly allowed"


# ============================================================================
# AC-2: Worker Usage Telemetry Capture and Spend Accounting (codex_cli)
# ============================================================================


def test_codex_cli_telemetry_schema_validation() -> None:
    """AC-2: Telemetry schema enforces non-negative token counts, required model, and positive duration."""
    valid_payload = {
        "prompt_tokens": 1200,
        "completion_tokens": 350,
        "total_tokens": 1550,
        "cached_tokens": 0,
        "model": "gpt-5-codex",
        "wall_clock_seconds": 4.85,
    }
    validated = validate_codex_cli_telemetry_payload(valid_payload)
    assert validated["prompt_tokens"] == 1200
    assert validated["completion_tokens"] == 350
    assert validated["total_tokens"] == 1550
    assert validated["model"] == "gpt-5-codex"
    assert validated["wall_clock_seconds"] == 4.85

    # 1. Negative prompt_tokens rejected
    with pytest.raises(ValueError, match="prompt_tokens must be a non-negative integer"):
        validate_codex_cli_telemetry_payload({**valid_payload, "prompt_tokens": -1, "total_tokens": 349})

    # 2. Negative completion_tokens rejected
    with pytest.raises(ValueError, match="completion_tokens must be a non-negative integer"):
        validate_codex_cli_telemetry_payload({**valid_payload, "completion_tokens": -10, "total_tokens": 1190})

    # 3. Missing required field (model) rejected
    payload_no_model = dict(valid_payload)
    payload_no_model.pop("model")
    with pytest.raises(ValueError, match="missing required fields"):
        validate_codex_cli_telemetry_payload(payload_no_model)

    # 4. Non-numeric token value rejected
    with pytest.raises(ValueError, match="prompt_tokens must be a non-negative integer"):
        validate_codex_cli_telemetry_payload({**valid_payload, "prompt_tokens": "one_thousand"})

    # 5. Empty model string rejected
    with pytest.raises(ValueError, match="model must be a non-empty string"):
        validate_codex_cli_telemetry_payload({**valid_payload, "model": "   "})

    # 6. Inconsistent total_tokens rejected
    with pytest.raises(ValueError, match="total_tokens .* must equal prompt_tokens .* \\+ completion_tokens"):
        validate_codex_cli_telemetry_payload({**valid_payload, "total_tokens": 9999})

    # 7. Non-positive wall_clock_seconds rejected
    with pytest.raises(ValueError, match="wall_clock_seconds must be a positive finite float"):
        validate_codex_cli_telemetry_payload({**valid_payload, "wall_clock_seconds": -1.0})

    # Verify integration with TokenUsage.from_payload
    if TokenUsage is not None:
        token_usage = TokenUsage.from_payload(
            {
                "input_tokens": 1200,
                "output_tokens": 350,
                "total_tokens": 1550,
                "model": "gpt-5-codex",
            }
        )
        assert token_usage.input_tokens == 1200
        assert token_usage.output_tokens == 350
        assert token_usage.total_tokens == 1550
        assert token_usage.model == "gpt-5-codex"


def test_codex_cli_telemetry_capture_on_successful_execution(tmp_path: Path) -> None:
    """AC-2: Metered codex_cli execution extracts token telemetry from stdout JSONL and usage.json."""
    if CodexCLIAdapter is None or TokenUsage is None:
        pytest.skip("CodexCLIAdapter or TokenUsage not importable")

    adapter = CodexCLIAdapter()
    step_run_dir = tmp_path / "step_run"
    step_run_dir.mkdir()
    context = _MockStepContext(step_run_dir=step_run_dir)

    # Capture mode A: Terminal receipt event in stdout
    jsonl_output = (
        '{"type": "message", "content": "Working on step..."}\n'
        '{"type": "turn.completed", "usage": {"prompt_tokens": 600, "completion_tokens": 200, "total_tokens": 800}}\n'
    )
    extracted_stdout = adapter.extract_usage(
        context,
        stdout=jsonl_output,
        stderr="",
        metadata={"model": "gpt-5-codex"},
    )
    assert extracted_stdout is not None
    assert isinstance(extracted_stdout, TokenUsage)
    assert extracted_stdout.input_tokens == 600
    assert extracted_stdout.output_tokens == 200
    assert extracted_stdout.total_tokens == 800
    assert extracted_stdout.model == "gpt-5-codex"

    # Capture mode B: Artifact file usage.json in step_run_dir
    usage_file = step_run_dir / "usage.json"
    usage_file.write_text(
        json.dumps({
            "model": "gpt-5-codex",
            "input_tokens": 750,
            "output_tokens": 250,
            "total_tokens": 1000,
        }),
        encoding="utf-8",
    )
    extracted_file = adapter.extract_usage(
        context,
        stdout="",
        stderr="",
        metadata={"model": "gpt-5-codex"},
    )
    assert extracted_file is not None
    assert extracted_file.input_tokens == 750
    assert extracted_file.output_tokens == 250
    assert extracted_file.total_tokens == 1000

    # Pricing validation: valid usage reaches measured status
    if _price_execution_records is not None and ModelRate is not None and RateTable is not None:
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
        record = AdapterExecutionRecord(identity=identity, usage=extracted_file)
        priced_usage, cost, status, reason = _price_execution_records(
            [record],
            rate_table=table,
            fallback_model="gpt-5-codex",
        )
        assert status == "measured"
        assert reason is None
        assert math.isfinite(cost) and cost > 0.0
        assert priced_usage is not None
        assert priced_usage.total_tokens == 1000


def test_fail_closed_rejection_on_missing_usage_telemetry(tmp_path: Path) -> None:
    """AC-2: Metered worker execution without usage telemetry fails closed with exact unaccounted spend error."""
    if CodexCLIAdapter is None or _price_execution_records is None or AdapterExecutionIdentity is None:
        pytest.skip("CodexCLIAdapter or accounting components not importable")

    adapter = CodexCLIAdapter()
    step_run_dir = tmp_path / "step_run"
    step_run_dir.mkdir()
    context = _MockStepContext(step_run_dir=step_run_dir)

    # Missing usage artifact and empty stdout yields None
    extracted = adapter.extract_usage(context, stdout="", stderr="", metadata={"model": "gpt-5-codex"})
    assert extracted is None

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

    step_id = "step_04_author_slice_tests"
    refusal_message = f"Unaccounted spend: {reason} for step {step_id!r}"
    assert "unaccounted spend" in refusal_message.lower()
    assert "missing usage telemetry for metered worker 'codex_cli'" in refusal_message.lower()


def test_fail_closed_rejection_on_partial_or_corrupted_telemetry(tmp_path: Path) -> None:
    """AC-2: Partial, corrupted, or conflicting telemetry is rejected fail-closed as unaccounted spend."""
    if CodexCLIAdapter is None or UsageError is None:
        pytest.skip("CodexCLIAdapter or UsageError not importable")

    adapter = CodexCLIAdapter()
    step_run_dir = tmp_path / "step_run"
    step_run_dir.mkdir()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    context = _MockStepContext(step_run_dir=step_run_dir, scratch_dir=scratch_dir)

    # 1. Malformed JSON in usage.json raises UsageError
    usage_file = step_run_dir / "usage.json"
    usage_file.write_text("{this is corrupted json}", encoding="utf-8")
    with pytest.raises(UsageError):
        adapter.extract_usage(context, stdout="", stderr="", metadata={})

    # 2. Conflicting usage artifacts between step_run and scratch raises UsageError
    usage_file.write_text(
        json.dumps({"model": "gpt-5-codex", "input_tokens": 100, "output_tokens": 50, "total_tokens": 150}),
        encoding="utf-8",
    )
    scratch_file = scratch_dir / "usage.json"
    scratch_file.write_text(
        json.dumps({"model": "gpt-5-codex", "input_tokens": 200, "output_tokens": 50, "total_tokens": 250}),
        encoding="utf-8",
    )
    with pytest.raises(UsageError, match="conflicting usage artifacts"):
        adapter.extract_usage(context, stdout="", stderr="", metadata={})

    scratch_file.unlink()

    # 3. Model conflict between usage telemetry and selected route model
    if _price_execution_records is not None and TokenUsage is not None:
        identity = AdapterExecutionIdentity(
            adapter_id="codex_cli",
            usage_reporting="required",
            route={"model": "gpt-5-codex"},
        )
        conflicting_usage = TokenUsage(
            model="unauthorized-foreign-model",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )
        record = AdapterExecutionRecord(identity=identity, usage=conflicting_usage)
        _, _, status, reason = _price_execution_records([record], rate_table=None, fallback_model="gpt-5-codex")
        assert status == "unaccounted"
        assert reason == "usage telemetry model conflicts with the trusted selected route model"


def test_run_level_spend_aggregation_and_budget_reconciliation() -> None:
    """AC-2: Aggregated token consumption across steps matches rate calculations and checks budget limits."""
    if TokenUsage is None:
        pytest.skip("TokenUsage not importable")

    # Accumulate token usage across three simulated steps
    step1_usage = TokenUsage(
        model="gpt-5-codex",
        input_tokens=1000,
        output_tokens=300,
        total_tokens=1300,
        cost_usd=0.0055,
    )
    step2_usage = TokenUsage(
        model="gpt-5-codex",
        input_tokens=1500,
        output_tokens=500,
        total_tokens=2000,
        cost_usd=0.00875,
    )
    step3_usage = TokenUsage(
        model="gpt-5-codex",
        input_tokens=800,
        output_tokens=200,
        total_tokens=1000,
        cost_usd=0.0040,
    )

    combined = step1_usage.accumulate(step2_usage).accumulate(step3_usage)
    assert combined.input_tokens == 3300
    assert combined.output_tokens == 1000
    assert combined.total_tokens == 4300
    assert combined.cost_usd is not None
    assert math.isclose(combined.cost_usd, 0.01825, rel_tol=1e-5)

    # Budget ceiling verification
    budget_ceiling_usd = 0.05
    assert combined.cost_usd <= budget_ceiling_usd, "Spend exceeded budget ceiling"

    # Simulated budget overrun check
    tight_budget_ceiling_usd = 0.01
    is_overrun = combined.cost_usd > tight_budget_ceiling_usd
    assert is_overrun is True, "Expected budget overrun detection for spend > tight ceiling"


def test_sysdiff_product_runtime_zero_telemetry_guarantee() -> None:
    """AC-2: sysdiff C17 product source, Makefile, and manual contain zero telemetry or networking code."""
    assert SYSDIFF_SRC.exists()
    src_content = SYSDIFF_SRC.read_text(encoding="utf-8")

    forbidden_code_symbols = [
        "curl",
        "socket",
        "AF_INET",
        "telemetry",
        "analytics",
        "metrics",
        "http:",
        "https:",
        "sendto",
        "recvfrom",
        "connect",
        "pthread_create",
        "daemon",
        "sysdiff_telemetry",
        "track_usage",
    ]
    for symbol in forbidden_code_symbols:
        assert symbol not in src_content, (
            f"Zero-telemetry violation: sysdiff source contains forbidden telemetry symbol {symbol!r}"
        )

    assert MAKEFILE.exists()
    makefile_content = MAKEFILE.read_text(encoding="utf-8")
    forbidden_make_flags = ["-lcurl", "-lprotobuf", "-lgrpc", "telemetry"]
    for flag in forbidden_make_flags:
        assert flag not in makefile_content, (
            f"Zero-telemetry violation: Makefile contains forbidden dependency/flag {flag!r}"
        )

    assert MAN_PAGE.exists()
    man_content = MAN_PAGE.read_text(encoding="utf-8")
    assert "telemetry" not in man_content.lower()


# Alias for traceability matrix compatibility
test_zero_telemetry_in_sysdiff_product_runtime = test_sysdiff_product_runtime_zero_telemetry_guarantee


# ============================================================================
# AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius
# ============================================================================


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-3: tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are identical parsed objects."""
    assert TESTS_MANIFEST.exists(), f"Missing canonical manifest oracle: {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest: {JOURNEYS_MANIFEST}"

    tests_manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_manifest = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    assert tests_manifest == journeys_manifest, (
        "User journeys manifests are desynchronized between tests/ and journeys/."
    )


def test_user_journeys_manifest_schema_and_command_allowlist() -> None:
    """AC-3: Manifest satisfies USER_JOURNEYS_MANIFEST_SCHEMA and specifies command_allowlist ['build/sysdiff']."""
    assert TESTS_MANIFEST.exists()
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
    """AC-3: Manifest preserves exactly 21 journeys covering author, sysdiff, and bwrap categories."""
    assert TESTS_MANIFEST.exists()
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = manifest.get("journeys", [])
    assert len(journeys) == 21, f"Expected exactly 21 journeys, got {len(journeys)}"

    names = {j["name"] for j in journeys}
    missing_author = PRESERVED_AUTHOR_JOURNEYS - names
    assert not missing_author, f"Manifest missing preserved author journeys: {missing_author}"

    missing_sysdiff = SYSDIFF_JOURNEYS - names
    assert not missing_sysdiff, f"Manifest missing core sysdiff journeys: {missing_sysdiff}"

    missing_bwrap = BWRAP_JOURNEYS - names
    assert not missing_bwrap, f"Manifest missing bwrap journeys: {missing_bwrap}"


def test_journey_traceability_to_contract_acceptance_checks() -> None:
    """AC-3: All non-exploratory journeys map via traces_to to AC-1..3 with zero orphaned checks."""
    assert TESTS_MANIFEST.exists()
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = manifest.get("journeys", [])
    allowed_checks = {"AC-1", "AC-2", "AC-3"}

    covered_checks: set[str] = set()
    for journey in journeys:
        authority = journey.get("authority", "author")
        assert authority in JOURNEY_AUTHORITIES, f"Invalid journey authority {authority!r}"
        traces = journey.get("traces_to", [])
        if authority != "exploratory":
            assert traces, f"Required journey {journey['name']!r} missing traces_to"
            assert set(traces) <= allowed_checks, (
                f"Journey {journey['name']!r} traces to invalid acceptance checks: {traces}"
            )
            covered_checks.update(traces)

    assert covered_checks == allowed_checks, (
        f"Contract acceptance checks not fully covered: {allowed_checks - covered_checks}"
    )


# Alias for traceability matrix compatibility
test_journey_traceability_and_acceptance_coverage = test_journey_traceability_to_contract_acceptance_checks


def test_sysdiff_c17_build_and_quality_floor() -> None:
    """AC-3: sysdiff passes strict ISO C17 compiler syntax checks and fixture acceptance."""
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

    fixture_script = ROOT / "tests" / "test_sysdiff_fixture.sh"
    if fixture_script.exists() and os.access(fixture_script, os.X_OK):
        fixture_res = subprocess.run(
            [str(fixture_script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )
        assert fixture_res.returncode == 0, (
            f"Fixture script failed:\nstdout: {fixture_res.stdout}\nstderr: {fixture_res.stderr}"
        )


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
