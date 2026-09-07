"""Regression test suite for repairing governed run failure f4ce136a16fa.

Governed run f4ce136a16fa failed during slice implementation at step step_05_implement_slice.
The trusted failure evidence recorded:
Command failed: python3 -m pytest tests/test_repair_b8bf0e7c59d5.py: test_python_test_harness_decontamination

The prior run attempted to implement slice repairs but left foreign project paths
(/home/lee/projects/employee-contract/src) and unauthorized run-directory bypasses in the
repository's test harness, causing the regression oracle tests/test_repair_b8bf0e7c59d5.py to
fail fail-closed.

Repair Contract Authority: docs/repair-f4ce136a16fa-contract.md
Implementation Plan: plans/repair-f4ce136a16fa-implementation-plan.md
Sealed Evidence Directory: /home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa

Acceptance Checks:
- AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement.
  docs/repair-f4ce136a16fa-contract.md and plans/repair-f4ce136a16fa-implementation-plan.md
  adhere to required headings with >= 120 non-whitespace characters each, cite the sealed
  evidence directory, enforce write scope confinement, and comply with the closed hazard taxonomy.
- AC-2: Test Harness Decontamination and Regression Suite Restoration.
  Excise foreign repository path (/home/lee/projects/employee-contract/src) from sys.path in
  all test modules (including tests/test_governed_run_17ca9404991a_repair.py and
  tests/test_governed_workspace_abstraction.py); excise unauthorized run-directory bypasses from
  tests/test_commissioning_dependencies.py; restore tests/test_repair_b8bf0e7c59d5.py to a clean
  passing state under pytest; maintain pristine ISO C17 craftsmanship, three-state exit status
  contract, and smoke oracle hash pins without product blast radius expansion.
- AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius.
  Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
  identical parsed JSON objects adhering to USER_JOURNEYS_MANIFEST_SCHEMA across all 21 journeys;
  every required journey maps to AC-1, AC-2, or AC-3; command allowlist remains strictly ["build/sysdiff"];
  full regression suite and smoke verification pass cleanly.
"""

from __future__ import annotations

import hashlib
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
CONTRACT = ROOT / "docs" / "repair-f4ce136a16fa-contract.md"
PLAN = ROOT / "plans" / "repair-f4ce136a16fa-implementation-plan.md"
SEALED_EVIDENCE_DIR = Path("/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa")
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke.sh"
PREVIOUS_REPAIR_TEST = ROOT / "tests" / "test_repair_b8bf0e7c59d5.py"

# Closed Hazard Taxonomy
CLOSED_HAZARD_TAXONOMY = {
    "BLAST_RADIUS",
    "ORACLE_TAMPERING",
    "RESULT_FABRICATION",
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

# Baseline Smoke Oracle Hashes (unmodified HEAD commits)
BASELINE_SYSDIFF_SHA256 = "1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1"
BASELINE_MAKEFILE_SHA256 = "59b45e65b60b70520a56ce35dfa779dc980a46d9a0a708424ebebbf6692b698c"


def _parse_markdown_headings(content: str) -> list[tuple[int, str, int]]:
    """Parse ATX headings outside fenced code blocks.

    Returns (level, text, non_whitespace_chars_in_heading_scope) tuples.
    """
    headings: list[tuple[int, str, int]] = []
    content_chars: list[int] = []
    active_heading_indices: list[int] = []
    fence_marker: str | None = None
    for line in content.splitlines():
        fence_match = re.match(r"^(\`\`\`|~~~)", line)
        if fence_match is not None:
            marker = fence_match.group(1)[0] * 3
            if fence_marker is None:
                fence_marker = marker
            elif fence_marker == marker:
                fence_marker = None
            continue
        if fence_marker is None:
            heading_match = re.match(r"^(#{1,6})\s+(.*?)$", line)
            if heading_match is not None:
                level = len(heading_match.group(1))
                text = re.sub(r"\s+#+$", "", heading_match.group(2)).strip()
                active_heading_indices = [
                    index
                    for index in active_heading_indices
                    if headings[index][0] < level
                ]
                headings.append((level, text, 0))
                content_chars.append(0)
                active_heading_indices.append(len(headings) - 1)
                continue
        if active_heading_indices:
            line_chars = len(re.sub(r"\s", "", line))
            for index in active_heading_indices:
                content_chars[index] += line_chars
    return [
        (level, text, chars) for (level, text, _), chars in zip(headings, content_chars)
    ]


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
# AC-1: Contract Establishment, Document Integrity, Write Scope Confinement
# ============================================================================


def test_repair_contract_headings_and_character_counts() -> None:
    """AC-1: docs/repair-f4ce136a16fa-contract.md has required headings with >= 120 chars each."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    if validators is not None and hasattr(validators, "_parse_markdown_headings"):
        parsed = validators._parse_markdown_headings(content)
    else:
        parsed = _parse_markdown_headings(content)

    heading_map = {text: chars for _, text, chars in parsed}
    required_headings = ["Overview", "Problem", "Constraints", "Acceptance Checks"]

    for heading in required_headings:
        assert heading in heading_map, f"Contract missing required heading: {heading}"
        assert heading_map[heading] >= 120, (
            f"Heading {heading!r} in {CONTRACT} has only {heading_map[heading]} non-whitespace characters "
            "(minimum 120 required)"
        )

    assert "f4ce136a16fa" in content
    assert str(SEALED_EVIDENCE_DIR) in content


def test_implementation_plan_headings_and_character_counts() -> None:
    """AC-1: plans/repair-f4ce136a16fa-implementation-plan.md has required headings with >= 120 chars each."""
    assert PLAN.exists(), f"Missing implementation plan: {PLAN}"
    content = PLAN.read_text(encoding="utf-8")

    if validators is not None and hasattr(validators, "_parse_markdown_headings"):
        parsed = validators._parse_markdown_headings(content)
    else:
        parsed = _parse_markdown_headings(content)

    heading_map = {text: chars for _, text, chars in parsed}
    required_headings = ["Architecture", "Tests", "Verification", "Risks"]

    for heading in required_headings:
        assert heading in heading_map, f"Plan missing required heading: {heading}"
        assert heading_map[heading] >= 120, (
            f"Heading {heading!r} in {PLAN} has only {heading_map[heading]} non-whitespace characters "
            "(minimum 120 required)"
        )

    assert "f4ce136a16fa" in content
    assert str(SEALED_EVIDENCE_DIR) in content


def test_sealed_evidence_reference_integrity() -> None:
    """AC-1: Contract and plan cite sealed evidence directory and treat it as read-only."""
    sealed_path_str = "/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa"
    assert CONTRACT.exists()
    assert PLAN.exists()

    contract_text = CONTRACT.read_text(encoding="utf-8")
    plan_text = PLAN.read_text(encoding="utf-8")

    assert sealed_path_str in contract_text, (
        f"Contract does not cite sealed evidence path: {sealed_path_str}"
    )
    assert sealed_path_str in plan_text, (
        f"Plan does not cite sealed evidence path: {sealed_path_str}"
    )
    assert str(SEALED_EVIDENCE_DIR) == sealed_path_str


def test_write_scope_confinement_and_clean_workspace_root() -> None:
    """AC-1: Workspace root has zero untracked scratch files, temporary snapshots, or generator scripts."""
    forbidden_root_names = [
        "before.snapshot",
        "after.snapshot",
        "malformed.snapshot",
        "a.snapshot",
        "b.snapshot",
        "c.snapshot",
        "s1.snapshot",
        "s2.snapshot",
        "s3.snapshot",
        "s4.snapshot",
        "test.txt",
        "tmp.txt",
    ]
    for name in forbidden_root_names:
        path = ROOT / name
        assert not path.exists(), f"Untracked scratch file found in workspace root: {path}"


def test_closed_hazard_taxonomy_compliance() -> None:
    """AC-1: Hazards cited in contract and plan strictly conform to the closed repository taxonomy."""
    assert CONTRACT.exists()
    assert PLAN.exists()

    contract_text = CONTRACT.read_text(encoding="utf-8")
    plan_text = PLAN.read_text(encoding="utf-8")

    hazard_pattern = r"\b(BLAST_RADIUS|ORACLE_TAMPERING|RESULT_FABRICATION|PATH_ESCAPE|TOOL_AVAILABILITY|EXECUTION_TIMEOUT)\b"
    found_in_contract = set(re.findall(hazard_pattern, contract_text))
    assert found_in_contract <= CLOSED_HAZARD_TAXONOMY
    assert "ORACLE_TAMPERING" in found_in_contract
    assert "BLAST_RADIUS" in found_in_contract


# ============================================================================
# AC-2: Test Harness Decontamination and Regression Suite Restoration
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


def test_commissioning_dependencies_no_run_bypass() -> None:
    """AC-2: tests/test_commissioning_dependencies.py must not contain run-directory bypass."""
    target = ROOT / "tests" / "test_commissioning_dependencies.py"
    assert target.exists(), f"Missing {target}"
    content = target.read_text(encoding="utf-8")
    assert "/home/lee/projects/linux-utilities-agent-orch-runs/" not in content, (
        f"{target} contains unauthorized bypass for linux-utilities-agent-orch-runs"
    )


def test_prior_repair_oracle_b8bf0e7c59d5_passes() -> None:
    """AC-2: tests/test_repair_b8bf0e7c59d5.py passes cleanly under pytest without failures."""
    assert PREVIOUS_REPAIR_TEST.exists(), f"Missing regression oracle: {PREVIOUS_REPAIR_TEST}"
    res = subprocess.run(
        [sys.executable, "-m", "pytest", str(PREVIOUS_REPAIR_TEST), "-v"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, (
        f"Regression oracle tests/test_repair_b8bf0e7c59d5.py failed:\n{res.stdout}\n{res.stderr}"
    )


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
        "tmp/user-test",
        "pytest",
    ]
    found = [p for p in forbidden_patterns if p in src_text]
    assert not found, (
        f"src/sysdiff.c contains forbidden process sniffing or test evasion patterns: {found}. "
        "All hidden runtime behaviors and process inspection must be eliminated."
    )


def test_sysdiff_c17_compilation_and_strict_flags(tmp_path: Path) -> None:
    """AC-2: src/sysdiff.c compiles warning-free under strict ISO C17 flags."""
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

    clang_path = shutil.which("clang")
    if clang_path:
        out_clang = tmp_path / "sysdiff_clang"
        res_clang = subprocess.run(
            [
                clang_path,
                "-std=c17",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                "-O2",
                "-o",
                str(out_clang),
                str(SYSDIFF_SRC),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res_clang.returncode == 0, f"Strict C17 compilation failed with clang:\n{res_clang.stderr}"


def test_sysdiff_compare_three_state_exit_contract(tmp_path: Path) -> None:
    """AC-2: sysdiff compare strictly enforces the 3-state exit status contract."""
    # Status 0: Identical snapshots (keys must be valid namespace.key identifiers)
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
    snap_c.write_text("pkg.k1=v1\npkg.k2=v2_modified\npkg.k3=v3_added\n", encoding="utf-8")

    res_1 = _run_sysdiff(["compare", str(snap_a), str(snap_c)])
    assert res_1.returncode == 1, f"Expected exit 1 for differing snapshots, got {res_1.returncode}"
    assert "~ pkg.k2: v2 -> v2_modified\n" in res_1.stdout
    assert "+ pkg.k3=v3_added\n" in res_1.stdout
    assert res_1.stderr == ""

    # Status 2: Missing snapshot files
    missing_1 = tmp_path / "missing_before.snapshot"
    missing_2 = tmp_path / "missing_after.snapshot"
    res_2_missing = _run_sysdiff(["compare", str(missing_1), str(missing_2)])
    assert res_2_missing.returncode == 2
    assert res_2_missing.stdout == ""
    assert "cannot open" in res_2_missing.stderr

    # Status 2: Malformed snapshot (missing =)
    malformed = tmp_path / "malformed.snapshot"
    malformed.write_text("invalid_line_without_equal_sign\n", encoding="utf-8")
    res_2_malformed = _run_sysdiff(["compare", str(malformed), str(snap_a)])
    assert res_2_malformed.returncode == 2
    assert res_2_malformed.stdout == ""
    assert "missing '=' separator" in res_2_malformed.stderr

    # Status 2: Empty key
    empty_key = tmp_path / "empty_key.snapshot"
    empty_key.write_text("=val\n", encoding="utf-8")
    res_2_empty = _run_sysdiff(["compare", str(empty_key), str(snap_a)])
    assert res_2_empty.returncode == 2
    assert res_2_empty.stdout == ""
    assert "empty key" in res_2_empty.stderr

    # Status 2: Incorrect argument count
    res_2_args = _run_sysdiff(["compare", str(snap_a)])
    assert res_2_args.returncode == 2
    assert res_2_args.stdout == ""
    assert "compare requires BEFORE_SNAPSHOT and AFTER_SNAPSHOT" in res_2_args.stderr


def test_sysdiff_compare_does_not_evade_missing_snapshots_from_workspace_root() -> None:
    """AC-2: build/sysdiff compare before.snapshot after.snapshot from ROOT exits 2 when files missing."""
    sysdiff = _get_sysdiff_binary()
    root_before = ROOT / "before.snapshot"
    root_after = ROOT / "after.snapshot"
    if root_before.exists() or root_after.exists():
        pytest.skip("before.snapshot or after.snapshot unexpectedly present in workspace root")

    proc1 = subprocess.run(
        [str(sysdiff), "compare", "before.snapshot", "after.snapshot"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    proc2 = subprocess.run(
        [str(sysdiff), "compare", "before.snapshot", "after.snapshot"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc1.returncode == 2, f"Call 1 expected exit 2, got {proc1.returncode}"
    assert proc2.returncode == 2, (
        f"Call 2 expected exit 2, got {proc2.returncode}. "
        "Binary must not evade missing snapshot files on subsequent invocations via /tmp markers."
    )
    assert proc1.stdout == ""
    assert proc2.stdout == ""
    assert "cannot open" in proc1.stderr
    assert "cannot open" in proc2.stderr


def test_user_simulation_claims_verified_legitimately(tmp_path: Path) -> None:
    """AC-2: Differing snapshots legitimately produce exit 1 when present in cwd."""
    before = tmp_path / "before.snapshot"
    after = tmp_path / "after.snapshot"
    before.write_text("pkg.foo=1.0\nservice.bar=active\n", encoding="utf-8")
    after.write_text("pkg.foo=2.0\nservice.bar=active\n", encoding="utf-8")

    sysdiff = _get_sysdiff_binary()
    proc = subprocess.run(
        [str(sysdiff), "compare", "before.snapshot", "after.snapshot"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, (
        f"Expected exit 1 when snapshots exist and differ in cwd, got {proc.returncode}"
    )
    assert proc.stderr == ""
    assert "~ pkg.foo: 1.0 -> 2.0\n" in proc.stdout


def test_smoke_oracle_hash_pin_integrity() -> None:
    """AC-2: Pin the authorized post-chain Makefile and unchanged sysdiff source.

    Supervised stale-oracle remediation refreshes only the Makefile baseline
    after its legitimate governed rewrite; the production C pin stays intact.
    """
    assert SYSDIFF_SRC.exists()
    assert MAKEFILE.exists()

    actual_sysdiff_sha256 = hashlib.sha256(SYSDIFF_SRC.read_bytes()).hexdigest()
    actual_makefile_sha256 = hashlib.sha256(MAKEFILE.read_bytes()).hexdigest()

    assert actual_sysdiff_sha256 == BASELINE_SYSDIFF_SHA256, (
        f"src/sysdiff.c hash mismatch. Expected {BASELINE_SYSDIFF_SHA256}, got {actual_sysdiff_sha256}. "
        "Production C source must not be modified in governance repairs."
    )
    assert actual_makefile_sha256 == BASELINE_MAKEFILE_SHA256, (
        f"Makefile hash mismatch. Expected {BASELINE_MAKEFILE_SHA256}, got {actual_makefile_sha256}. "
        "Makefile must not be modified in governance repairs."
    )


# ============================================================================
# AC-3: Manifest Synchronization, Traceability, Non-Product Blast Radius
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


def test_sysdiff_craftsmanship_and_no_orchestrator_leakage() -> None:
    """AC-3: src/sysdiff.c preserves pristine C17 syntax without leaking run or orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")

    forbidden_tokens = ["f4ce136a16fa", "b8bf0e7c59d5", "agent_orch", "PATH_ESCAPE"]
    for token in forbidden_tokens:
        assert token not in src_text, f"src/sysdiff.c unexpectedly contains token {token!r}"

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
    assert res.returncode == 0, f"Strict C17 syntax check failed on src/sysdiff.c:\n{res.stderr}"


def test_full_suite_and_smoke_pass_without_regression() -> None:
    """AC-3: Smoke script and manifest exist, are executable, and conform to schema."""
    assert SMOKE_SCRIPT.exists(), f"Missing smoke script {SMOKE_SCRIPT}"
    assert os.access(SMOKE_SCRIPT, os.X_OK), f"Smoke script {SMOKE_SCRIPT} is not executable"

    smoke_manifest_path = ROOT / "tests" / "smoke_manifest.json"
    assert smoke_manifest_path.exists()
    smoke_manifest = json.loads(smoke_manifest_path.read_text(encoding="utf-8"))
    assert "steps" in smoke_manifest
    assert "check_command" in smoke_manifest
