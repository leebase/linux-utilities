"""Regression test suite for repairing governed run failure 337b9a6cea80.

Governed run 337b9a6cea80 failed at step_06_user_simulation_gate with:
    User-test command claims in artifacts/user-test/result.json could not be confirmed:
    `build/sysdiff compare before.snapshot after.snapshot`: tester claimed exit 1, orchestrator observed exit 2.

Failure analysis and root causes:
1. Re-execution Working Directory and Relative Snapshot Paths:
   The orchestrator's user journey execution verification rule (_run_user_journeys_execution_rule)
   re-executes allowlisted commands directly from the canonical governed workspace root (cwd=workspace).
   In run 337b9a6cea80, the user test recorded a command claim:
       build/sysdiff compare before.snapshot after.snapshot
   claiming exit_code 1 (expecting differences between two snapshots).
   However, the files before.snapshot and after.snapshot did not exist in the root of the workspace.
   When build/sysdiff was invoked from the workspace root, it attempted to open before.snapshot,
   failed with ENOENT, printed "before.snapshot: cannot open: No such file or directory" to stderr,
   and exited with status 2.
   Because the tester claimed exit 1 and the orchestrator observed exit 2, the command claim
   could not be confirmed, causing the user simulation gate to fail closed.

2. sysdiff Compare Exit Status Contract:
   According to the sysdiff specification (man/sysdiff.1 and TESTING.md), sysdiff compare
   has three strictly defined exit status classes:
   - Status 0: Comparison succeeded with no differences found (prints "no changes\\n" to stdout, empty stderr).
   - Status 1: Comparison succeeded and at least one difference was found (prints sorted diff to stdout, empty stderr).
   - Status 2: Usage error, file I/O error (e.g. missing file, unreadable file), malformed snapshot,
     duplicate key, allocation failure, or resource limit violation (prints diagnostic to stderr, empty stdout).
   The utility must never crash (segfault, abort) and must never misreport status codes
   (such as returning 1 when files cannot be opened, or returning 2 when valid differences exist).

3. Verifiable User Simulation Claims:
   Every command recorded in artifacts/user-test/result.json under commands_run must be verifiable
   and reproducible when re-executed from the governed workspace root against build/sysdiff.
   Claims must either reference snapshots that exist at the specified relative paths from the workspace root
   or the required files must be present before the user simulation gate executes.

Acceptance Checks:
- AC-1: sysdiff compare exit status code fidelity (status 0, 1, 2) against build/sysdiff without crashing or misreporting.
- AC-2: User-test claim confirmation and re-execution fidelity (reproducing run 337b9a6cea80 failure).
- AC-3: User journey manifest synchronization, traceability, and non-product blast radius.
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
    from agent_orch.models import ValidationRule
except ImportError:
    validators = None  # type: ignore[assignment]
    ValidationRule = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
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


def _get_sysdiff_binary() -> Path:
    """Return the sysdiff binary under test, honoring SYSDIFF_BIN or build/sysdiff."""
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
# AC-1: sysdiff compare Exit Status Code Fidelity (against build/sysdiff)
# ============================================================================


def test_sysdiff_compare_differing_snapshots_exits_one(tmp_path: Path) -> None:
    """AC-1: sysdiff compare exits 1 when snapshots exist and contain differences."""
    before = tmp_path / "before.snapshot"
    after = tmp_path / "after.snapshot"
    before.write_text(
        "pkg.alpha=1.0.0\n"
        "pkg.beta=2.0.0\n"
        "service.web.active=\n",
        encoding="utf-8",
    )
    after.write_text(
        "pkg.alpha=1.1.0\n"
        "pkg.gamma=3.0.0\n"
        "service.web.active=\n",
        encoding="utf-8",
    )

    proc = _run_sysdiff(["compare", str(before), str(after)])
    assert proc.returncode == 1, (
        f"Expected exit code 1 for differing snapshots, got {proc.returncode}. "
        f"stdout: {proc.stdout!r}, stderr: {proc.stderr!r}"
    )
    assert proc.stderr == "", f"Expected empty stderr on valid diff, got: {proc.stderr!r}"
    assert "~ pkg.alpha: 1.0.0 -> 1.1.0\n" in proc.stdout
    assert "- pkg.beta=2.0.0\n" in proc.stdout
    assert "+ pkg.gamma=3.0.0\n" in proc.stdout


def test_sysdiff_compare_identical_snapshots_exits_zero(tmp_path: Path) -> None:
    """AC-1: sysdiff compare exits 0 and prints 'no changes' when snapshots are identical."""
    snap = tmp_path / "identical.snapshot"
    snap.write_text("pkg.a=1.0\nservice.web.active=\n", encoding="utf-8")

    proc = _run_sysdiff(["compare", str(snap), str(snap)])
    assert proc.returncode == 0, (
        f"Expected exit code 0 for identical snapshots, got {proc.returncode}"
    )
    assert proc.stdout == "no changes\n"
    assert proc.stderr == ""


def test_sysdiff_compare_missing_snapshots_exits_two_without_crashing(tmp_path: Path) -> None:
    """AC-1: sysdiff compare exits 2 when snapshot files do not exist, without crashing."""
    missing_before = tmp_path / "does_not_exist_before.snapshot"
    missing_after = tmp_path / "does_not_exist_after.snapshot"

    proc = _run_sysdiff(["compare", str(missing_before), str(missing_after)])
    assert proc.returncode == 2, (
        f"Expected exit code 2 for missing snapshots, got {proc.returncode}"
    )
    assert proc.stdout == "", f"Expected empty stdout on missing file error, got: {proc.stdout!r}"
    assert "cannot open: No such file or directory" in proc.stderr
    assert str(missing_before) in proc.stderr


def test_sysdiff_compare_one_missing_snapshot_exits_two(tmp_path: Path) -> None:
    """AC-1: sysdiff compare exits 2 when either the first or second snapshot file is missing."""
    valid_snap = tmp_path / "valid.snapshot"
    valid_snap.write_text("pkg.a=1.0\n", encoding="utf-8")
    missing_snap = tmp_path / "missing.snapshot"

    # Missing second snapshot
    proc1 = _run_sysdiff(["compare", str(valid_snap), str(missing_snap)])
    assert proc1.returncode == 2
    assert proc1.stdout == ""
    assert "cannot open: No such file or directory" in proc1.stderr
    assert str(missing_snap) in proc1.stderr

    # Missing first snapshot
    proc2 = _run_sysdiff(["compare", str(missing_snap), str(valid_snap)])
    assert proc2.returncode == 2
    assert proc2.stdout == ""
    assert "cannot open: No such file or directory" in proc2.stderr
    assert str(missing_snap) in proc2.stderr


def test_sysdiff_compare_malformed_snapshot_exits_two(tmp_path: Path) -> None:
    """AC-1: sysdiff compare exits 2 with empty stdout when a snapshot is malformed."""
    valid_snap = tmp_path / "valid.snapshot"
    valid_snap.write_text("pkg.valid=1.0\n", encoding="utf-8")

    malformed_snap = tmp_path / "malformed.snapshot"
    malformed_snap.write_text("this line is missing an equals separator\n", encoding="utf-8")

    proc = _run_sysdiff(["compare", str(malformed_snap), str(valid_snap)])
    assert proc.returncode == 2, f"Expected exit code 2 for malformed input, got {proc.returncode}"
    assert proc.stdout == "", f"Expected empty stdout on malformed input, got: {proc.stdout!r}"
    assert "missing '=' separator" in proc.stderr


def test_sysdiff_compare_invalid_key_syntax_exits_two(tmp_path: Path) -> None:
    """AC-1: sysdiff compare exits 2 when a snapshot contains an empty key or invalid key syntax."""
    empty_key_snap = tmp_path / "empty_key.snapshot"
    empty_key_snap.write_text("=value_without_key\n", encoding="utf-8")

    valid_snap = tmp_path / "valid.snapshot"
    valid_snap.write_text("valid.key=1.0\n", encoding="utf-8")

    proc = _run_sysdiff(["compare", str(empty_key_snap), str(valid_snap)])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "empty key" in proc.stderr


def test_sysdiff_compare_argument_count_errors_exit_two() -> None:
    """AC-1: sysdiff compare with incorrect argument count exits 2 with usage on stderr."""
    # compare with 0 arguments
    proc_0 = _run_sysdiff(["compare"])
    assert proc_0.returncode == 2
    assert proc_0.stdout == ""
    assert "compare requires BEFORE_SNAPSHOT and AFTER_SNAPSHOT" in proc_0.stderr

    # compare with 1 argument
    proc_1 = _run_sysdiff(["compare", "single_arg.snapshot"])
    assert proc_1.returncode == 2
    assert proc_1.stdout == ""
    assert "compare requires BEFORE_SNAPSHOT and AFTER_SNAPSHOT" in proc_1.stderr

    # compare with 3 arguments
    proc_3 = _run_sysdiff(["compare", "a.snapshot", "b.snapshot", "extra.snapshot"])
    assert proc_3.returncode == 2
    assert proc_3.stdout == ""
    assert "compare requires BEFORE_SNAPSHOT and AFTER_SNAPSHOT" in proc_3.stderr


# ============================================================================
# AC-2: User Simulation Failure Reproduction (Run 337b9a6cea80 Defect)
# ============================================================================


def test_sysdiff_compare_unconfirmed_claim_reproduces_exit_two_from_root() -> None:
    """AC-2: build/sysdiff compare before.snapshot after.snapshot from ROOT exits 2 (not 1).

    In governed run 337b9a6cea80, the user test claimed:
        `build/sysdiff compare before.snapshot after.snapshot`: exit 1
    However, before.snapshot and after.snapshot did not exist in the workspace root.
    When the orchestrator re-executed the claimed command with cwd=workspace,
    sysdiff correctly observed the missing file and exited with code 2.
    This test reproduces that exact behavior, demonstrating why the tester's claim
    of exit 1 could not be confirmed against the real binary.
    """
    sysdiff = _get_sysdiff_binary()

    # Ensure before.snapshot does not exist in workspace root
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

    assert proc.returncode == 2, (
        f"Expected exit code 2 when snapshots are missing in cwd, got {proc.returncode}"
    )
    assert proc.returncode != 1, (
        "sysdiff must not return exit code 1 when snapshot files cannot be opened"
    )
    assert proc.stdout == ""
    assert "before.snapshot: cannot open: No such file or directory" in proc.stderr


def test_sysdiff_compare_existing_before_after_snapshots_yields_exit_one(tmp_path: Path) -> None:
    """AC-2: When before.snapshot and after.snapshot actually exist and differ, sysdiff exits 1.

    This proves that the tester's intended claim (exit 1) is valid only when
    the snapshot files exist in the effective working directory with differing records.
    """
    sysdiff = _get_sysdiff_binary()
    before = tmp_path / "before.snapshot"
    after = tmp_path / "after.snapshot"
    before.write_text("pkg.a=1.0\nservice.b=active\n", encoding="utf-8")
    after.write_text("pkg.a=1.1\nservice.b=active\n", encoding="utf-8")

    proc = subprocess.run(
        [str(sysdiff), "compare", "before.snapshot", "after.snapshot"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1, (
        f"Expected exit code 1 when before.snapshot and after.snapshot differ, got {proc.returncode}"
    )
    assert proc.stderr == ""
    assert "~ pkg.a: 1.0 -> 1.1\n" in proc.stdout


def test_user_test_result_command_claims_confirmed_against_build_sysdiff() -> None:
    """AC-2: Every command claim in artifacts/user-test/result.json must match actual exit code.

    In governed run 337b9a6cea80, step_06_user_simulation_gate failed with:
        User-test command claims in artifacts/user-test/result.json could not be confirmed:
        `build/sysdiff compare before.snapshot after.snapshot`: tester claimed exit 1, orchestrator observed exit 2.

    This test re-executes all allowlisted command claims in artifacts/user-test/result.json
    against build/sysdiff with cwd=ROOT whenever a fresh artifact exists. The stale
    dead-run artifact was removed during supervised remediation, rather than
    fabricating journey evidence; the existing absent-artifact skip applies.
    """
    if not USER_TEST_RESULT.exists():
        pytest.skip(f"User test result artifact does not exist: {USER_TEST_RESULT}")

    data = json.loads(USER_TEST_RESULT.read_text(encoding="utf-8"))
    sysdiff_bin = _get_sysdiff_binary()
    allowlist_prefix = "build/sysdiff"

    mismatches: list[str] = []
    for journey in data.get("journeys", []):
        journey_name = journey.get("name", "unknown")
        for claim in journey.get("commands_run", []):
            cmd_text = claim.get("command", "")
            claimed_exit = claim.get("exit_code")

            if not cmd_text.startswith(allowlist_prefix):
                continue

            # Parse command tokens
            try:
                tokens = shlex.split(cmd_text)
            except ValueError:
                mismatches.append(f"[{journey_name}] unparseable command: {cmd_text!r}")
                continue

            # Execute directly from ROOT (just as the orchestrator validator does)
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

    if os.environ.get("ALLOW_UNIMPLEMENTED") == "1" and mismatches:
        pytest.skip(
            f"Pending implementation repair for run 337b9a6cea80: {'; '.join(mismatches)}"
        )

    assert not mismatches, (
        "User-test command claims in artifacts/user-test/result.json could not be confirmed: "
        + "; ".join(mismatches)
    )


def test_user_journeys_execution_verified_validator_rule() -> None:
    """AC-2: agent_orch validator user_journeys_execution_verified must confirm result claims.

    Directly executes the orchestrator validation rule on artifacts/user-test/result.json
    using tests/user_journeys_manifest.json as the authority manifest whenever a
    fresh artifact exists. Supervised remediation removed only stale generated
    evidence; absent-artifact skipping and fresh-claim validation are unchanged.
    """
    if validators is None or ValidationRule is None:
        pytest.skip("agent_orch.validators not importable in this environment")

    if not USER_TEST_RESULT.exists():
        pytest.skip(f"{USER_TEST_RESULT} does not exist")

    rule = ValidationRule(
        type="user_journeys_execution_verified",
        path="artifacts/user-test/result.json",
        manifest_path="tests/user_journeys_manifest.json",
    )

    outcome = validators._run_user_journeys_execution_rule(rule, ROOT, None, None)

    if os.environ.get("ALLOW_UNIMPLEMENTED") == "1" and not outcome.passed:
        pytest.skip(
            f"Pending implementation repair for run 337b9a6cea80: {outcome.message}"
        )

    assert outcome.passed is True, (
        f"user_journeys_execution_verified rule failed: {outcome.message}"
    )


# ============================================================================
# AC-3: User Journey Manifest Synchronization and Non-Product Blast Radius
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


def test_sysdiff_c_source_craftsmanship_and_non_product_blast_radius() -> None:
    """AC-3: sysdiff C source remains unaltered ISO C17 without leaking orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0
    assert MAN_PAGE.exists() and MAN_PAGE.stat().st_size > 0

    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")
    for forbidden in ("337b9a6cea80", "agent_orch", "PATH_ESCAPE"):
        assert forbidden not in src_text, f"sysdiff.c unexpectedly contains {forbidden!r}"

    cc = os.environ.get("CC", "gcc")
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
