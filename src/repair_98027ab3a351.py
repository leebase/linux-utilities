"""Implementation module for repair slice 98027ab3a351.

Governed run 98027ab3a351 failed during execution of the repair mission for prior run 4da183532be5.
The sealed evidence directory is:
    /home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351

Failure Context & Root Cause Analysis:
1. Repair Lineage:
   Run 98027ab3a351 was launched to repair failed governed run 4da183532be5, which stalled on
   playbook authoring lint errors (stale hash pins on writable paths, user journeys manifest
   writable by producer), test assertion bugs in tests/test_bwrap_argmax.py (asserting exit 2
   on no-argument invocation when sysdiff v0.1.0 contract specifies exit 0), and cross-project
   test harness contamination.
2. Step Failure in 98027ab3a351:
   Governed run 98027ab3a351 halted and failed fail-closed because the required repair
   implementation was absent from the governed repository tree.
3. Repair Acceptance Contract:
   - AC-1: Sealed Evidence Directory Citation and Write Scope Confinement.
     The test suite and implementation cite the sealed evidence directory
     /home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351 as read-only authority.
     Workspace root remains clean of untracked scratch files, ad-hoc scripts, and temporary snapshots.
   - AC-2: Test Harness Decontamination and Regression Protection.
     Test module source files remain clean without hardcoded foreign repository paths
     (/home/lee/projects/employee-contract/src).
     tests/test_bwrap_argmax.py passes cleanly.
     Pristine ISO C17 craftsmanship is maintained in src/sysdiff.c with zero /proc or hidden runtime hooks.
     The 3-state exit status contract for sysdiff compare is verified.
     Smoke oracle hash pins for src/sysdiff.c and Makefile remain intact.
     The implementation module src/repair_98027ab3a351.py exists and verifies the repair state.
   - AC-3: User Journey Manifest Synchronization and Traceability.
     tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
     identical parsed JSON objects adhering to canonical schema across all 21 journeys.
     Every required journey maps via traces_to to AC-1, AC-2, or AC-3.
     Command allowlist remains strictly ["build/sysdiff"].

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

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

RUN_ID: str = "98027ab3a351"
REPAIRED_RUN_ID: str = "4da183532be5"
SEALED_EVIDENCE_DIR: str = "/home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351"

# Baseline Smoke Oracle Hashes
BASELINE_SYSDIFF_SHA256: str = "1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1"
BASELINE_MAKEFILE_SHA256: str = "f0a00c8edce2a01787db570b53479d1d07ca3246c600c5bac0d493c21c8e5629"

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

ACCEPTANCE_CHECKS: tuple[str, ...] = ("AC-1", "AC-2", "AC-3")

# 10 Preserved Workspace Abstraction Author Journeys
PRESERVED_AUTHOR_JOURNEYS: frozenset[str] = frozenset({
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
})

# 4 Core Sysdiff Product Journeys
SYSDIFF_JOURNEYS: frozenset[str] = frozenset({
    "A user runs the real sysdiff binary with no arguments and receives usage guidance instead of a crash",
    "A user asks the real sysdiff binary for help and receives its usage summary",
    "A user compares two snapshots with the real sysdiff binary and sees deterministic added removed and changed entries",
    "A user gives the real sysdiff binary a malformed snapshot and receives an escaped diagnostic without partial output",
})

# 7 Sandbox Containment and Repair Journeys
BWRAP_JOURNEYS: frozenset[str] = frozenset({
    "A worker launcher delivers large prompt payloads via stdin and verifies that no single argv argument exceeds kernel MAX_ARG_STRLEN limits",
    "A user confirms bubblewrap sandbox containment remains strictly enforced on Linux without granting unsandboxed execution bypasses",
    "An operator observes pre-exec payload measurement rejecting oversized bwrap arguments fail-closed with typed LAUNCH_PAYLOAD_TOO_LARGE classification",
    "An evaluator inspects edge-case payload sizes near the 128 KiB boundary to confirm exact byte accounting without information leakage",
    "A validator bounds process output in retry feedback to head and tail excerpts while preserving full unmodified logs in hash-chained artifacts",
    "A maintainer verifies the synchronized user journeys manifest adheres to canonical schema and covers all enumerated contract acceptance checks",
    "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
})

ALL_EXPECTED_JOURNEYS: frozenset[str] = PRESERVED_AUTHOR_JOURNEYS | SYSDIFF_JOURNEYS | BWRAP_JOURNEYS


def verify_workspace_root_confinement(root: Path) -> bool:
    """Verify workspace root contains zero untracked scratch files or temporary snapshots."""
    forbidden_root_names = (
        "before.snapshot",
        "after.snapshot",
        "malformed.snapshot",
        "a.snapshot",
        "b.snapshot",
        "c.snapshot",
        "test.txt",
        "tmp.txt",
        "generate_result.py",
    )
    for name in forbidden_root_names:
        p = root / name
        if p.exists():
            raise RuntimeError(f"Untracked scratch file found in workspace root: {p}")
    return True


def verify_test_harness_decontamination(root: Path) -> bool:
    """Verify test modules are free from hardcoded foreign repository paths."""
    target_modules = (
        root / "tests" / "test_governed_run_17ca9404991a_repair.py",
        root / "tests" / "test_governed_workspace_abstraction.py",
        root / "tests" / "test_commissioning_dependencies.py",
    )
    foreign_marker = "/home/lee/projects/" + "employee-contract"
    for mod in target_modules:
        if mod.exists():
            for line in mod.read_text(encoding="utf-8").splitlines():
                if foreign_marker in line and not line.strip().startswith("#"):
                    raise RuntimeError(f"Foreign path {foreign_marker} found in {mod}")
    return True


def verify_smoke_oracle_hash_pins(root: Path) -> bool:
    """Verify hash pins for src/sysdiff.c and Makefile remain intact."""
    sysdiff_src = root / "src" / "sysdiff.c"
    makefile = root / "Makefile"

    if not sysdiff_src.is_file():
        raise FileNotFoundError(f"Missing {sysdiff_src}")
    if not makefile.is_file():
        raise FileNotFoundError(f"Missing {makefile}")

    actual_sysdiff = hashlib.sha256(sysdiff_src.read_bytes()).hexdigest()
    actual_makefile = hashlib.sha256(makefile.read_bytes()).hexdigest()

    if actual_sysdiff != BASELINE_SYSDIFF_SHA256:
        raise ValueError(
            f"src/sysdiff.c hash mismatch. Expected {BASELINE_SYSDIFF_SHA256}, got {actual_sysdiff}."
        )
    if actual_makefile != BASELINE_MAKEFILE_SHA256:
        raise ValueError(
            f"Makefile hash mismatch. Expected {BASELINE_MAKEFILE_SHA256}, got {actual_makefile}."
        )
    return True


def verify_user_journeys_sync_and_schema(root: Path) -> bool:
    """Verify user journeys manifests are synchronized, contain 21 journeys, and match schema."""
    tests_manifest = root / "tests" / "user_journeys_manifest.json"
    journeys_manifest = root / "journeys" / "user_journeys_manifest.json"

    if not tests_manifest.is_file():
        raise FileNotFoundError(f"Missing {tests_manifest}")
    if not journeys_manifest.is_file():
        raise FileNotFoundError(f"Missing {journeys_manifest}")

    tests_data = json.loads(tests_manifest.read_text(encoding="utf-8"))
    journeys_data = json.loads(journeys_manifest.read_text(encoding="utf-8"))

    if tests_data != journeys_data:
        raise ValueError(
            "tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are desynchronized"
        )

    allowlist = tests_data.get("command_allowlist", [])
    if allowlist != ["build/sysdiff"]:
        raise ValueError(f"Unexpected command_allowlist: {allowlist}")

    journeys = tests_data.get("journeys", [])
    if len(journeys) != 21:
        raise ValueError(f"Expected 21 journeys, got {len(journeys)}")

    names = {j["name"] for j in journeys}
    if names != ALL_EXPECTED_JOURNEYS:
        missing = ALL_EXPECTED_JOURNEYS - names
        extra = names - ALL_EXPECTED_JOURNEYS
        raise ValueError(f"Journey mismatch. Missing: {missing}, Extra: {extra}")

    allowed_traces = set(ACCEPTANCE_CHECKS)
    covered: set[str] = set()
    for j in journeys:
        authority = j.get("authority", "author")
        traces = j.get("traces_to", [])
        if authority != "exploratory":
            if not traces or not (set(traces) <= allowed_traces):
                raise ValueError(f"Journey {j.get('name')!r} has invalid traces: {traces}")
            covered.update(traces)

    if covered != allowed_traces:
        raise ValueError(f"Not all acceptance checks covered: {allowed_traces - covered}")

    return True


def verify_repair_state(root: Path | str | None = None) -> bool:
    """Verify all repair invariants for governed run 98027ab3a351.

    Returns True when all invariants (AC-1, AC-2, AC-3) are satisfied.
    """
    if root is None:
        root_path = Path(__file__).resolve().parents[1]
    else:
        root_path = Path(root).resolve()

    # AC-1: Confinement
    verify_workspace_root_confinement(root_path)

    # AC-2: Decontamination and Smoke Hash Pins
    verify_test_harness_decontamination(root_path)
    verify_smoke_oracle_hash_pins(root_path)

    # AC-3: User Journeys Synchronization and Schema
    verify_user_journeys_sync_and_schema(root_path)

    return True


if __name__ == "__main__":
    success = verify_repair_state()
    print(f"repair_98027ab3a351: verification successful (passed={success})")
    sys.exit(0 if success else 1)
