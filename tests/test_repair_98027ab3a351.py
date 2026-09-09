"""Regression test suite for repairing governed run failure 98027ab3a351.

Governed run 98027ab3a351 failed during execution of the repair mission for prior run 4da183532be5.
The sealed evidence directory is:
    /home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351

Failure context and root cause analysis:
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
     The test suite references the sealed evidence directory
     /home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351 as read-only authority.
     Workspace root remains clean of untracked scratch files, ad-hoc scripts, and temporary snapshots.
   - AC-2: Test Harness Decontamination and Regression Protection.
     Test module source files remain clean without hardcoded foreign repository paths
     (/home/lee/projects/employee-contract/src).
     tests/test_bwrap_argmax.py passes cleanly.
     Pristine ISO C17 craftsmanship is maintained in src/sysdiff.c with zero /proc or hidden runtime hooks.
     The 3-state exit status contract for sysdiff compare is verified.
     Smoke oracle hash pins for src/sysdiff.c and Makefile remain intact.
     The implementation module src/repair_98027ab3a351.py must exist and verify the repair state.
   - AC-3: User Journey Manifest Synchronization and Traceability.
     tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
     identical parsed JSON objects adhering to canonical schema across all 21 journeys.
     Every required journey maps via traces_to to AC-1, AC-2, or AC-3.
     Command allowlist remains strictly ["build/sysdiff"].
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import pytest

# Maintain clean sys.path without cross-project contamination
for _extra_path in (
    "/home/lee/projects/agent-orch/src",
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
    from agent_orch.models import ValidationRule
except ImportError:
    validators = None  # type: ignore[assignment]
    ValidationRule = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
SEALED_EVIDENCE_DIR = Path("/home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351")
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"
BWRAP_TEST = ROOT / "tests" / "test_bwrap_argmax.py"
REPAIR_IMPL_MODULE = ROOT / "src" / "repair_98027ab3a351.py"

# Baseline Smoke Oracle Hashes
BASELINE_SYSDIFF_SHA256 = "1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1"
BASELINE_MAKEFILE_SHA256 = "a4ea71c27b4a5f17db47a960a327e11d4fdebbe1a50123db7193682483c7d9f1"

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


def _get_sysdiff_binary() -> Path:
    """Return the sysdiff binary under test, compiling if necessary."""
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
# AC-1: Sealed Evidence Directory Citation and Write Scope Confinement
# ============================================================================


def test_sealed_evidence_reference_integrity() -> None:
    """AC-1: Test module explicitly cites the sealed evidence directory."""
    expected_path_str = "/home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351"
    assert str(SEALED_EVIDENCE_DIR) == expected_path_str


def test_write_scope_confinement_and_clean_workspace_root() -> None:
    """AC-1: Workspace root contains zero untracked scratch files or temporary snapshots."""
    forbidden_root_names = [
        "before.snapshot",
        "after.snapshot",
        "malformed.snapshot",
        "a.snapshot",
        "b.snapshot",
        "c.snapshot",
        "test.txt",
        "tmp.txt",
        "generate_result.py",
    ]
    for name in forbidden_root_names:
        path = ROOT / name
        assert not path.exists(), f"Untracked scratch file found in workspace root: {path}"


# ============================================================================
# AC-2: Test Harness Decontamination, Regression Protection, and Implementation
# ============================================================================


def test_python_test_harness_decontamination() -> None:
    """AC-2: Excises foreign repository path 'employee-contract' from test module sys.path."""
    target_modules = [
        ROOT / "tests" / "test_governed_run_17ca9404991a_repair.py",
        ROOT / "tests" / "test_governed_workspace_abstraction.py",
        ROOT / "tests" / "test_commissioning_dependencies.py",
    ]
    foreign_marker = "/home/lee/projects/" + "employee-contract"
    contaminated: list[str] = []
    for mod in target_modules:
        if mod.exists():
            for line in mod.read_text(encoding="utf-8").splitlines():
                if foreign_marker in line and not line.strip().startswith("#"):
                    contaminated.append(f"{mod.name}:{line.strip()}")
                    break

    assert not contaminated, (
        f"Foreign path found in test modules: {contaminated}. "
        "Test harness must be decontaminated."
    )


def test_bwrap_argmax_regression_suite_passes() -> None:
    """AC-2: Prior bwrap argmax test suite passes cleanly without failures."""
    assert BWRAP_TEST.exists(), f"Missing {BWRAP_TEST}"
    res = subprocess.run(
        [sys.executable, "-m", "pytest", str(BWRAP_TEST), "-v"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"tests/test_bwrap_argmax.py failed:\n{res.stdout}\n{res.stderr}"


def test_sysdiff_c17_compilation_and_strict_flags(tmp_path: Path) -> None:
    """AC-2: src/sysdiff.c compiles cleanly under strict ISO C17 compiler flags."""
    cc = os.environ.get("CC", "gcc")
    out_bin = tmp_path / "sysdiff_strict"
    res_gcc = subprocess.run(
        [
            cc,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-O2",
            "-o",
            str(out_bin),
            str(SYSDIFF_SRC),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_gcc.returncode == 0, f"Strict C17 compilation failed with {cc}:\n{res_gcc.stderr}"


def test_sysdiff_c17_source_has_no_proc_or_hidden_runtime_hooks() -> None:
    """AC-2: src/sysdiff.c must not contain process sniffing, /proc queries, or test-evasion hooks."""
    assert SYSDIFF_SRC.exists(), f"Missing {SYSDIFF_SRC}"
    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")

    forbidden_patterns = [
        "should_use_test_snapshots",
        "/proc",
        "cmdline",
        "getppid",
        "/tmp/.sysdiff_call",
        "pytest",
    ]
    found = [p for p in forbidden_patterns if p in src_text]
    assert not found, (
        f"src/sysdiff.c contains forbidden patterns: {found}. "
        "All hidden runtime behaviors and process inspection must be eliminated."
    )


def test_sysdiff_compare_three_state_exit_contract(tmp_path: Path) -> None:
    """AC-2: sysdiff compare strictly enforces the 3-state exit status contract."""
    # Status 0: Identical snapshots
    snap_a = tmp_path / "a.snapshot"
    snap_b = tmp_path / "b.snapshot"
    snap_a.write_text("pkg.k1=v1\npkg.k2=v2\n", encoding="utf-8")
    snap_b.write_text("pkg.k1=v1\npkg.k2=v2\n", encoding="utf-8")

    res_0 = _run_sysdiff(["compare", str(snap_a), str(snap_b)])
    assert res_0.returncode == 0, f"Expected exit 0 for identical snapshots, got {res_0.returncode}"
    assert res_0.stdout == "no changes\n"
    assert res_0.stderr == ""

    # Status 1: Differing snapshots
    snap_c = tmp_path / "c.snapshot"
    snap_c.write_text("pkg.k1=v1\npkg.k2=v2_mod\npkg.k3=v3_add\n", encoding="utf-8")

    res_1 = _run_sysdiff(["compare", str(snap_a), str(snap_c)])
    assert res_1.returncode == 1, f"Expected exit 1 for differing snapshots, got {res_1.returncode}"
    assert "~ pkg.k2: v2 -> v2_mod\n" in res_1.stdout
    assert "+ pkg.k3=v3_add\n" in res_1.stdout
    assert res_1.stderr == ""

    # Status 2: Missing snapshot files
    missing_a = tmp_path / "missing_a.snapshot"
    missing_b = tmp_path / "missing_b.snapshot"
    res_2_missing = _run_sysdiff(["compare", str(missing_a), str(missing_b)])
    assert res_2_missing.returncode == 2
    assert "cannot open" in res_2_missing.stderr

    # Status 2: Malformed snapshot
    malformed = tmp_path / "malformed.snapshot"
    malformed.write_text("invalid_line_without_equals\n", encoding="utf-8")
    res_2_malformed = _run_sysdiff(["compare", str(malformed), str(snap_a)])
    assert res_2_malformed.returncode == 2
    assert "missing '=' separator" in res_2_malformed.stderr


def test_sysdiff_compare_does_not_evade_missing_snapshots_from_workspace_root() -> None:
    """AC-2: build/sysdiff compare before.snapshot after.snapshot from ROOT exits 2 when files missing."""
    sysdiff = _get_sysdiff_binary()
    root_before = ROOT / "before.snapshot"
    root_after = ROOT / "after.snapshot"
    if root_before.exists() or root_after.exists():
        pytest.skip("before.snapshot or after.snapshot unexpectedly present in workspace root")

    proc = subprocess.run(
        [str(sysdiff), "compare", "before.snapshot", "after.snapshot"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, f"Expected exit 2, got {proc.returncode}"
    assert "cannot open" in proc.stderr


def test_smoke_oracle_hash_pin_integrity() -> None:
    """AC-2: Hash pins for src/sysdiff.c and Makefile remain intact."""
    assert SYSDIFF_SRC.exists()
    assert MAKEFILE.exists()

    actual_sysdiff_sha256 = hashlib.sha256(SYSDIFF_SRC.read_bytes()).hexdigest()
    actual_makefile_sha256 = hashlib.sha256(MAKEFILE.read_bytes()).hexdigest()

    assert actual_sysdiff_sha256 == BASELINE_SYSDIFF_SHA256, (
        f"src/sysdiff.c hash mismatch. Expected {BASELINE_SYSDIFF_SHA256}, got {actual_sysdiff_sha256}."
    )
    assert actual_makefile_sha256 == BASELINE_MAKEFILE_SHA256, (
        f"Makefile hash mismatch. Expected {BASELINE_MAKEFILE_SHA256}, got {actual_makefile_sha256}."
    )


def test_repair_98027ab3a351_implementation_state() -> None:
    """AC-2: Verify the repair implementation for governed run 98027ab3a351.

    Governed run 98027ab3a351 failed to complete its repair cycle for 4da183532be5.
    The repair requires an implementation module `src/repair_98027ab3a351.py`
    providing runtime verification of the repair state.

    Expected module properties:
    - RUN_ID: "98027ab3a351"
    - REPAIRED_RUN_ID: "4da183532be5"
    - SEALED_EVIDENCE_DIR: "/home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351"
    - verify_repair_state() -> bool returning True

    This test must fail until step_02_implement_repair authors `src/repair_98027ab3a351.py`.
    """
    assert REPAIR_IMPL_MODULE.exists(), (
        f"Missing required repair implementation module: {REPAIR_IMPL_MODULE}. "
        "Governed run 98027ab3a351 repair must be implemented in src/repair_98027ab3a351.py "
        "defining RUN_ID='98027ab3a351', REPAIRED_RUN_ID='4da183532be5', "
        "SEALED_EVIDENCE_DIR='/home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351', "
        "and verify_repair_state() -> bool."
    )

    spec = importlib.util.spec_from_file_location("repair_98027ab3a351", REPAIR_IMPL_MODULE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert getattr(mod, "RUN_ID", None) == "98027ab3a351"
    assert getattr(mod, "REPAIRED_RUN_ID", None) == "4da183532be5"
    assert getattr(mod, "SEALED_EVIDENCE_DIR", None) == "/home/lee/projects/linux-utilities-agent-orch-runs/98027ab3a351"
    assert callable(getattr(mod, "verify_repair_state", None))
    assert mod.verify_repair_state() is True


# ============================================================================
# AC-3: User Journey Manifest Synchronization and Traceability
# ============================================================================


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-3: Both tests and journeys manifests exist and are identical parsed objects."""
    assert TESTS_MANIFEST.exists(), f"Missing canonical oracle {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest {JOURNEYS_MANIFEST}"

    tests_data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_data = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    assert tests_data == journeys_data, (
        "tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are not identical parsed objects."
    )


def test_user_journeys_manifest_schema_conformance() -> None:
    """AC-3: Manifest conforms to USER_JOURNEYS_MANIFEST_SCHEMA without schema errors."""
    assert TESTS_MANIFEST.exists()
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))

    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(data))
        assert not errors, f"Schema validation errors in {TESTS_MANIFEST}: {errors}"


def test_user_journeys_manifest_preserves_all_21_journeys() -> None:
    """AC-3: Manifest preserves all 21 author, sysdiff, and bwrap journeys without omission."""
    assert TESTS_MANIFEST.exists()
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = data.get("journeys", [])
    assert len(journeys) == 21, f"Expected exactly 21 journeys, got {len(journeys)}"

    names = {j["name"] for j in journeys}
    assert names == ALL_EXPECTED_JOURNEYS, (
        f"Manifest journey mismatch. Missing: {ALL_EXPECTED_JOURNEYS - names}, Extra: {names - ALL_EXPECTED_JOURNEYS}"
    )


def test_user_journeys_command_allowlist() -> None:
    """AC-3: Manifest command allowlist is strictly ['build/sysdiff']."""
    assert TESTS_MANIFEST.exists()
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    allowlist = data.get("command_allowlist", [])
    assert allowlist == ["build/sysdiff"], (
        f"command_allowlist must remain strictly ['build/sysdiff'], got: {allowlist}"
    )


def test_journey_traceability_to_contract_acceptance_checks() -> None:
    """AC-3: Every required journey maps to AC-1, AC-2, or AC-3, and all ACs are covered."""
    assert TESTS_MANIFEST.exists()
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = data.get("journeys", [])
    allowed_traces = {"AC-1", "AC-2", "AC-3"}

    covered: set[str] = set()
    for j in journeys:
        authority = j.get("authority", "author")
        assert authority in JOURNEY_AUTHORITIES, f"Invalid authority {authority!r} in journey {j['name']!r}"
        traces = j.get("traces_to", [])
        if authority != "exploratory":
            assert traces, f"Required journey {j['name']!r} lacks traces_to"
            assert set(traces) <= allowed_traces, f"Journey {j['name']!r} has invalid traces: {traces}"
            covered.update(traces)

    assert covered == allowed_traces, f"Not all acceptance checks are covered: {allowed_traces - covered}"
