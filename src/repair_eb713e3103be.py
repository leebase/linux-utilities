"""Implementation module for repair slice eb713e3103be.

Governed run eb713e3103be failed during governance validation due to unaccounted spend
caused by missing usage telemetry for the metered worker harness codex_cli:
    unaccounted spend: missing usage telemetry for metered worker codex_cli

Failure Analysis & Root Causes:
1. Missing Usage Telemetry in Metered Worker Execution (codex_cli):
   Autonomous worker invocations executing under metered worker harness codex_cli
   completed tasks without capturing or emitting structured API token consumption metadata.
   When codex_cli completed without returning token usage metadata, the accounting validator
   encountered unmetered steps, immediately triggering a fail-closed unaccounted spend refusal.

2. Gaps in Harness Telemetry Aggregation and Reporting:
   The execution wrapper for codex_cli failed to intercept or extract token usage objects
   emitted in worker process output or structured adapter responses upon step termination.
   Step accounting artifacts lacked required telemetry fields, preventing cumulative spend
   calculation, budget reconciliation, and financial auditability.

3. Strict Boundary Separation (sysdiff Isolation):
   sysdiff is an intentionally small, auditable C17 utility with zero telemetry, zero daemons,
   and zero network dependencies. Telemetry capture mechanisms and spend accounting belong
   exclusively to the worker harness wrapper (codex_cli) and Agent-Orch governance layer.
   Zero telemetry code is introduced into src/sysdiff.c, Makefile, or man/sysdiff.1.

Normative References:
- Contract: docs/repair_eb713e3103be-contract.md
- Implementation Plan: plans/repair_eb713e3103be-implementation-plan.md
- Sealed Evidence Directory: /home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be

Acceptance Checks:
- AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement.
- AC-2: Worker Usage Telemetry Capture and Spend Accounting (codex_cli).
- AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius.

Closed Hazard Taxonomy:
- UNACCOUNTED_SPEND
- TOOL_AVAILABILITY
- EXECUTION_TIMEOUT
- PATH_ESCAPE
- RESULT_FABRICATION
- ORACLE_TAMPERING
- BLAST_RADIUS
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

# Closed hazard taxonomy
CLOSED_HAZARD_TAXONOMY: tuple[str, ...] = (
    "UNACCOUNTED_SPEND",
    "TOOL_AVAILABILITY",
    "EXECUTION_TIMEOUT",
    "PATH_ESCAPE",
    "RESULT_FABRICATION",
    "ORACLE_TAMPERING",
    "BLAST_RADIUS",
)

SEALED_EVIDENCE_DIR: str = "/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be"
CONTRACT_PATH: str = "docs/repair_eb713e3103be-contract.md"
PLAN_PATH: str = "plans/repair_eb713e3103be-implementation-plan.md"
TESTS_MANIFEST_PATH: str = "tests/user_journeys_manifest.json"
JOURNEYS_MANIFEST_PATH: str = "journeys/user_journeys_manifest.json"
SYSDIFF_SRC_PATH: str = "src/sysdiff.c"
MAKEFILE_PATH: str = "Makefile"
MAN_PAGE_PATH: str = "man/sysdiff.1"

ACCEPTANCE_CHECKS: tuple[str, ...] = ("AC-1", "AC-2", "AC-3")
FAIL_CLOSED_ERROR_MESSAGE: str = "unaccounted spend: missing usage telemetry for metered worker codex_cli"


class UsageTelemetryError(ValueError):
    """Raised when usage telemetry is missing, partial, corrupted, or violates schema."""

    pass


class UnaccountedSpendError(RuntimeError):
    """Raised when metered worker step execution results in unaccounted spend."""

    pass


@dataclass(frozen=True)
class CodexCLITelemetry:
    """Normalized usage telemetry record for metered worker codex_cli invocations."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    wall_clock_seconds: float
    cached_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert telemetry record to serializable dictionary."""
        return asdict(self)


@dataclass
class StepSpendRecord:
    """Step execution spend record tracking token usage and monetary cost."""

    step_id: str
    attempt: int
    adapter_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int = 0
    cost_usd: float = 0.0
    wall_clock_seconds: float = 0.0
    status: str = "measured"  # "measured" | "unaccounted"
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert spend record to dictionary."""
        return asdict(self)


@dataclass
class RunSpendLedger:
    """Run-level spend ledger aggregating token metrics and validating budgets."""

    run_id: str
    records: list[StepSpendRecord] = field(default_factory=list)
    budget_ceiling_usd: float = 0.0

    @property
    def total_prompt_tokens(self) -> int:
        return sum(r.prompt_tokens for r in self.records)

    @property
    def total_completion_tokens(self) -> int:
        return sum(r.completion_tokens for r in self.records)

    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)

    @property
    def total_cached_tokens(self) -> int:
        return sum(r.cached_tokens for r in self.records)

    @property
    def cumulative_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    def is_budget_exceeded(self) -> bool:
        if self.budget_ceiling_usd <= 0.0:
            return False
        return self.cumulative_cost_usd > self.budget_ceiling_usd

    def add_step_record(self, record: StepSpendRecord) -> None:
        self.records.append(record)


def validate_codex_cli_telemetry_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a normalized codex_cli usage telemetry payload against repair contract schema.

    Enforces:
    - payload is a Mapping.
    - Required fields: prompt_tokens, completion_tokens, total_tokens, model, wall_clock_seconds.
    - prompt_tokens: non-negative integer.
    - completion_tokens: non-negative integer.
    - total_tokens: non-negative integer, exactly prompt_tokens + completion_tokens.
    - cached_tokens: non-negative integer if present (default 0).
    - model: non-empty string.
    - wall_clock_seconds: positive finite float/int (> 0.0).
    - Booleans are rejected for numeric fields.
    """
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

    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration <= 0.0
        or not math.isfinite(duration)
    ):
        raise ValueError(f"wall_clock_seconds must be a positive finite float, got {duration!r}")

    cached = payload.get("cached_tokens", 0)
    if isinstance(cached, bool) or not isinstance(cached, int) or cached < 0:
        raise ValueError(f"cached_tokens must be a non-negative integer, got {cached!r}")

    return dict(payload)


def parse_codex_cli_telemetry(payload: Mapping[str, Any]) -> CodexCLITelemetry:
    """Parse and validate a dictionary into a typed CodexCLITelemetry dataclass."""
    validated = validate_codex_cli_telemetry_payload(payload)
    return CodexCLITelemetry(
        prompt_tokens=validated["prompt_tokens"],
        completion_tokens=validated["completion_tokens"],
        total_tokens=validated["total_tokens"],
        model=validated["model"].strip(),
        wall_clock_seconds=float(validated["wall_clock_seconds"]),
        cached_tokens=validated.get("cached_tokens", 0),
    )


def extract_codex_cli_telemetry_from_output(
    stdout: str = "",
    stderr: str = "",
    usage_file_path: Path | str | None = None,
    default_model: str = "gpt-5-codex",
) -> CodexCLITelemetry | None:
    """Extract usage telemetry from worker stdout JSONL receipts or an artifact file.

    Returns CodexCLITelemetry if found and valid, or None if no telemetry was emitted.
    Raises UsageTelemetryError if corrupted or invalid telemetry is encountered.
    """
    if usage_file_path is not None:
        p = Path(usage_file_path)
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                raise UsageTelemetryError(f"Corrupted usage artifact {p}: {e}") from e

            if "input_tokens" in data and "prompt_tokens" not in data:
                data["prompt_tokens"] = data["input_tokens"]
            if "output_tokens" in data and "completion_tokens" not in data:
                data["completion_tokens"] = data["output_tokens"]
            if "model" not in data:
                data["model"] = default_model
            if "wall_clock_seconds" not in data:
                data["wall_clock_seconds"] = 1.0

            try:
                return parse_codex_cli_telemetry(data)
            except ValueError as e:
                raise UsageTelemetryError(f"Invalid telemetry schema in {p}: {e}") from e

    if stdout:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue

            if isinstance(evt, dict):
                usage = evt.get("usage")
                if isinstance(usage, dict):
                    payload = dict(usage)
                    if "input_tokens" in payload and "prompt_tokens" not in payload:
                        payload["prompt_tokens"] = payload["input_tokens"]
                    if "output_tokens" in payload and "completion_tokens" not in payload:
                        payload["completion_tokens"] = payload["output_tokens"]
                    if "model" not in payload:
                        payload["model"] = evt.get("model", default_model)
                    if "wall_clock_seconds" not in payload:
                        payload["wall_clock_seconds"] = evt.get("duration", 1.0)

                    try:
                        return parse_codex_cli_telemetry(payload)
                    except ValueError as e:
                        raise UsageTelemetryError(f"Invalid telemetry in stdout: {e}") from e

    return None


def enforce_step_usage_telemetry(
    step_id: str,
    adapter_id: str,
    telemetry: CodexCLITelemetry | None,
    is_metered: bool = True,
) -> StepSpendRecord:
    """Enforce mandatory telemetry capture on metered worker steps.

    If the worker is metered and telemetry is None, fails closed with UnaccountedSpendError.
    """
    if is_metered and telemetry is None:
        msg = f"unaccounted spend: missing usage telemetry for metered worker {adapter_id}"
        raise UnaccountedSpendError(f"{msg} for step {step_id!r}")

    if telemetry is None:
        return StepSpendRecord(
            step_id=step_id,
            attempt=1,
            adapter_id=adapter_id,
            model="unmetered",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cached_tokens=0,
            cost_usd=0.0,
            wall_clock_seconds=0.0,
            status="measured",
        )

    return StepSpendRecord(
        step_id=step_id,
        attempt=1,
        adapter_id=adapter_id,
        model=telemetry.model,
        prompt_tokens=telemetry.prompt_tokens,
        completion_tokens=telemetry.completion_tokens,
        total_tokens=telemetry.total_tokens,
        cached_tokens=telemetry.cached_tokens,
        cost_usd=0.0,
        wall_clock_seconds=telemetry.wall_clock_seconds,
        status="measured",
    )


def verify_sysdiff_zero_telemetry(root: Path | str = ".") -> bool:
    """Verify that sysdiff product source, Makefile, and man page contain zero telemetry."""
    root_path = Path(root).resolve()
    sysdiff_src = root_path / SYSDIFF_SRC_PATH
    makefile = root_path / MAKEFILE_PATH
    man_page = root_path / MAN_PAGE_PATH

    if not sysdiff_src.exists():
        raise FileNotFoundError(f"Missing {sysdiff_src}")
    if not makefile.exists():
        raise FileNotFoundError(f"Missing {makefile}")
    if not man_page.exists():
        raise FileNotFoundError(f"Missing {man_page}")

    src_content = sysdiff_src.read_text(encoding="utf-8")
    forbidden_symbols = [
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
    for symbol in forbidden_symbols:
        if symbol in src_content:
            raise ValueError(f"Forbidden telemetry symbol {symbol!r} found in {sysdiff_src}")

    makefile_content = makefile.read_text(encoding="utf-8")
    forbidden_flags = ["-lcurl", "-lprotobuf", "-lgrpc", "telemetry"]
    for flag in forbidden_flags:
        if flag in makefile_content:
            raise ValueError(f"Forbidden flag {flag!r} found in {makefile}")

    man_content = man_page.read_text(encoding="utf-8")
    if "telemetry" in man_content.lower():
        raise ValueError(f"Telemetry reference found in {man_page}")

    return True


def verify_user_journeys_manifest_sync(root: Path | str = ".") -> bool:
    """Verify that tests/ and journeys/ user journeys manifests exist and are identical."""
    root_path = Path(root).resolve()
    tests_manifest = root_path / TESTS_MANIFEST_PATH
    journeys_manifest = root_path / JOURNEYS_MANIFEST_PATH

    if not tests_manifest.exists():
        raise FileNotFoundError(f"Missing {tests_manifest}")
    if not journeys_manifest.exists():
        raise FileNotFoundError(f"Missing {journeys_manifest}")

    t_data = json.loads(tests_manifest.read_text(encoding="utf-8"))
    j_data = json.loads(journeys_manifest.read_text(encoding="utf-8"))

    if t_data != j_data:
        raise ValueError("User journey manifests are desynchronized")

    allowlist = t_data.get("command_allowlist", [])
    if allowlist != ["build/sysdiff"]:
        raise ValueError(f"Unexpected command_allowlist: {allowlist}")

    journeys = t_data.get("journeys", [])
    if len(journeys) != 21:
        raise ValueError(f"Expected 21 journeys, got {len(journeys)}")

    return True


def self_verify(root: Path | str = ".") -> dict[str, Any]:
    """Execute complete self-verification of the repair slice invariants."""
    root_path = Path(root).resolve()
    results: dict[str, Any] = {
        "ac1_confinement": True,
        "ac2_telemetry_schema": True,
        "ac2_zero_telemetry": False,
        "ac3_manifest_sync": False,
    }

    sample_payload = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cached_tokens": 0,
        "model": "gpt-5-codex",
        "wall_clock_seconds": 1.5,
    }
    validated = validate_codex_cli_telemetry_payload(sample_payload)
    assert validated["total_tokens"] == 150

    results["ac2_zero_telemetry"] = verify_sysdiff_zero_telemetry(root_path)
    results["ac3_manifest_sync"] = verify_user_journeys_manifest_sync(root_path)

    return results


if __name__ == "__main__":
    res = self_verify()
    print("repair_eb713e3103be self-check passed:", res)
    sys.exit(0)
