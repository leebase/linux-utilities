"""Regression coverage for repairing governed run failure 6ffed16f4d17.

Governed run 6ffed16f4d17 failed during step_05_implement_slice with a path escape /
write scope confinement violation:
    Changed path outside allowed_paths: journeys/user_journeys_manifest.json

Failure analysis and root causes:
1. Root Cause (write scope confinement violation):
   In run 6ffed16f4d17, step_05 had an allowed_paths filter restricted to ["docs", "tests"].
   During that step, an attempt was made to write to journeys/user_journeys_manifest.json
   to satisfy user journey manifest synchronization requirements (from finding UJ-0191293D-001).
   Because journeys/ was not declared in step_05 allowed_paths, Agent-Orch enforced
   fail-closed path containment and halted execution with a PATH_ESCAPE / out-of-scope write error.

2. Repair Contract (docs/repair-6ffed16f4d17-contract.md):
   - AC-1: Write Scope Confinement and Path Policy Compliance.
     Repair contract document adheres to required headings with >= 120 non-whitespace
     characters each. Step mutations strictly adhere to declared allowed_paths; steps with
     write scopes restricted to docs/ and tests/ never touch journeys/.
     Path confinement enforcement rejects mutations outside declared allowed_paths fail-closed.
   - AC-2: User Journey Manifest Synchronization and Traceability.
     Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json must exist
     as identical parsed objects adhering to USER_JOURNEYS_MANIFEST_SCHEMA.
     All 21 journeys (10 author journeys, 4 sysdiff journeys, 7 bwrap journeys) are preserved.
     All non-exploratory journeys map to AC-1..3 with zero orphaned acceptance checks.
     The command allowlist remains strictly ["build/sysdiff"].
   - AC-3: Product Behavior Integrity and Non-Product Blast Radius.
     The repair introduces zero modifications to sysdiff C source, Makefile, or man pages.
     Real sysdiff CLI contracts (no-args, --help, --version, diffing, malformed snapshot rejection)
     and bubblewrap sandbox payload limits are verified with zero regressions.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

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
    from agent_orch.engine import _allowed_path_outcomes
    from agent_orch.models import StepDefinition
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
    )
    from agent_orch.validators import ValidationOutcome
except ImportError:
    _allowed_path_outcomes = None  # type: ignore[assignment]
    StepDefinition = None  # type: ignore[assignment]
    ValidationOutcome = None  # type: ignore[assignment]
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]

try:
    import sandbox_exec
except ImportError:
    sandbox_exec = None  # type: ignore[assignment]

TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
CONTRACT = ROOT / "docs" / "repair-6ffed16f4d17-contract.md"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"

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


# ============================================================================
# AC-1: Write Scope Confinement and Path Policy Compliance
# ============================================================================


def test_repair_contract_structure_and_headings() -> None:
    """AC-1: docs/repair-6ffed16f4d17-contract.md has required headings with >= 120 chars each."""
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

    assert "6ffed16f4d17" in content
    assert "allowed_paths" in content
    assert "journeys/user_journeys_manifest.json" in content
    assert "PATH_ESCAPE" in content


def test_step_write_scope_confinement_fails_closed_on_unauthorized_paths() -> None:
    """AC-1: Engine write scope enforcement rejects mutations outside declared allowed_paths fail-closed."""
    if _allowed_path_outcomes is None or StepDefinition is None:
        pytest.skip("agent_orch.engine._allowed_path_outcomes not importable")

    # Reproduce step_05 condition from 6ffed16f4d17: allowed_paths = ["docs", "tests"]
    step_05 = StepDefinition(
        step_id="step_05_implement_slice",
        name="Implement slice",
        worker="codex_cli",
        allowed_paths=["docs", "tests"],
    )

    # When step_05 modifies journeys/user_journeys_manifest.json, it must fail closed
    unauthorized_outcomes = _allowed_path_outcomes(
        step_05,
        ["journeys/user_journeys_manifest.json"],
    )
    assert len(unauthorized_outcomes) == 1
    assert unauthorized_outcomes[0].passed is False
    assert "outside allowed_paths" in unauthorized_outcomes[0].message
    assert "journeys/user_journeys_manifest.json" in unauthorized_outcomes[0].message

    # Contrast with step_01 where journeys was explicitly allowed
    step_01 = StepDefinition(
        step_id="step_01_define_repair_contract",
        name="Define repair contract",
        worker="codex_cli",
        allowed_paths=["docs", "tests", "journeys"],
    )
    authorized_outcomes = _allowed_path_outcomes(
        step_01,
        ["journeys/user_journeys_manifest.json"],
    )
    assert len(authorized_outcomes) == 1
    assert authorized_outcomes[0].passed is True
    assert "within scope" in authorized_outcomes[0].message

    # An empty allowed_paths specification must fail closed on any modified file
    empty_step = StepDefinition(
        step_id="step_unauthorized",
        name="Unauthorized",
        worker="codex_cli",
        allowed_paths=[],
    )
    empty_outcomes = _allowed_path_outcomes(
        empty_step,
        ["tests/some_test.py"],
    )
    assert len(empty_outcomes) == 1
    assert empty_outcomes[0].passed is False
    assert "with no allowed_paths declared" in empty_outcomes[0].message


# ============================================================================
# AC-2: User Journey Manifest Synchronization and Traceability
# ============================================================================


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-2: Both tests and journeys manifests exist and are identical parsed objects."""
    assert TESTS_MANIFEST.exists(), f"Missing canonical oracle {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest {JOURNEYS_MANIFEST}"

    tests_manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_manifest = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    assert tests_manifest == journeys_manifest, (
        "Repository journey manifests are not identical parsed objects."
    )


def test_user_journeys_manifest_schema_and_command_allowlist() -> None:
    """AC-2: Manifest adheres to canonical schema and preserves immutable command allowlist."""
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
    """AC-2: Manifest preserves all 21 author, sysdiff, and bwrap journeys without omission."""
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
    """AC-2: All required journeys map to valid acceptance checks and AC-1..3 are covered."""
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


# ============================================================================
# AC-3: Product Behavior Integrity and Non-Product Blast Radius
# ============================================================================


def test_sysdiff_c_source_craftsmanship_and_non_product_blast_radius() -> None:
    """AC-3: sysdiff C source remains unaltered ISO C17 without leaking orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0
    assert MAN_PAGE.exists() and MAN_PAGE.stat().st_size > 0

    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")
    for forbidden in ("bwrap", "agent_orch", "PATH_ESCAPE"):
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
    """AC-3 / Journey 13: sysdiff compares snapshots with deterministic added/removed/changed entries."""
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


def test_bubblewrap_sandbox_product_behavior() -> None:
    """AC-1 / AC-2: Bubblewrap sandbox execution harness enforces ARG_MAX boundaries fail-closed."""
    if sandbox_exec is None:
        pytest.skip("scripts/sandbox_exec.py is not available")

    assert sandbox_exec.max_single_launch_entry_bytes() == 131072
    assert sandbox_exec.max_total_launch_bytes() == 2097152

    # Oversized single argument rejected before exec with typed classification
    oversized_arg = "x" * 131073
    cmd = ["/bin/echo", oversized_arg]
    report = sandbox_exec.refuse_oversized_launch(cmd, {})
    assert isinstance(report, dict)
    assert report["failure_classification"] == "launch_payload_too_large"
    assert report["failure_evidence"]["reason"] == "single_entry_exceeds_max_arg_strlen"
    payload_info = report["failure_evidence"]["launch_payload"]
    assert payload_info["largest_argument_bytes"] > 131072
    assert payload_info["single_entry_limit_bytes"] == 131072

    # Output bounding
    long_output = "line\n" * 2000
    bounded = sandbox_exec.bounded_process_output(long_output)
    assert len(bounded) <= 10000
    assert "elided from this record" in bounded
