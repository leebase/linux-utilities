"""Regression coverage for the failed governed run a5d017a2cfa1.

Governed run a5d017a2cfa1 failed due to test assertion bugs and manifest omissions
in the bwrap ARG_MAX repair workstream:
1. False-positive CLI assertion in tests/test_bwrap_argmax.py:
   test_sysdiff_cli_behavior_unaltered asserted that invoking sysdiff with no
   arguments returned exit code 2 with usage on stderr, but sysdiff v0.1.0 is a
   frozen contract that exits 0 with usage on stdout and empty stderr.
2. Manifest tampering / omission in tests/user_journeys_manifest.json:
   When bwrap journeys were added, the 10 PRESERVED_AUTHOR_JOURNEYS from run
   17ca9404991a were dropped, breaking test_governed_run_17ca9404991a_repair.py.
3. tests/test_bwrap_argmax.py boundary test failures:
   Pre-exec single-argument boundary rejection, total ARG_MAX rejection, and typed
   E2BIG classification failed because test_bwrap_argmax.py tested unpatched
   external modules instead of the local scripts/sandbox_exec.py harness.

These tests reproduce the failures fail-closed until implementation is updated.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
BWRAP_TEST = ROOT / "tests" / "test_bwrap_argmax.py"
SANDBOX_EXEC = ROOT / "scripts" / "sandbox_exec.py"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"

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


def test_sysdiff_no_arg_cli_contract_and_bwrap_test_assertion(tmp_path: Path) -> None:
    """The sysdiff binary exits 0 on no-arg invocation, and test_bwrap_argmax.py must not assert exit 2."""
    binary = _get_sysdiff_binary(tmp_path)

    # 1. Verify frozen sysdiff CLI behavior: exit code 0, usage on stdout, empty stderr
    proc = subprocess.run([str(binary)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"sysdiff no-arg invocation returned {proc.returncode}, expected 0"
    assert "usage: sysdiff" in proc.stdout, f"sysdiff usage missing from stdout: {proc.stdout}"
    assert proc.stderr == "", f"sysdiff stderr unexpectedly non-empty: {proc.stderr}"

    # 2. Verify test_bwrap_argmax.py does not assert exit 2 for no-arg invocation
    bwrap_test_code = BWRAP_TEST.read_text(encoding="utf-8")
    assert "assert no_arg.returncode == 2" not in bwrap_test_code, (
        "test_bwrap_argmax.py incorrectly asserts sysdiff exits with code 2 on no-arg invocation; "
        "sysdiff v0.1.0 contract specifies exit code 0"
    )
    assert "assert no_arg.returncode == 0" in bwrap_test_code, (
        "test_bwrap_argmax.py must assert sysdiff exits with code 0 on no-arg invocation"
    )


def test_user_journeys_manifest_contains_complete_lineage_and_schema() -> None:
    """The manifest must satisfy the schema, preserve author journeys, and contain all journeys."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"

    tests_bytes = TESTS_MANIFEST.read_bytes()
    manifest = json.loads(tests_bytes)
    assert isinstance(manifest, dict)
    assert not list(
        jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA).iter_errors(
            manifest
        )
    )

    journeys = manifest["journeys"]
    names = {journey["name"] for journey in journeys}

    # Lineage verification: all previous author journeys must be preserved
    missing_preserved = PRESERVED_AUTHOR_JOURNEYS - names
    assert not missing_preserved, (
        f"tests/user_journeys_manifest.json omitted preserved author journeys: {missing_preserved}"
    )

    # Product journeys must be present
    missing_sysdiff = SYSDIFF_JOURNEYS - names
    assert not missing_sysdiff, (
        f"tests/user_journeys_manifest.json omitted sysdiff journeys: {missing_sysdiff}"
    )

    # bwrap repair journeys must be present
    missing_bwrap = BWRAP_JOURNEYS - names
    assert not missing_bwrap, (
        f"tests/user_journeys_manifest.json omitted bwrap repair journeys: {missing_bwrap}"
    )

    # Traceability: every non-exploratory journey must trace to AC-1, AC-2, or AC-3
    allowed_traces = {"AC-1", "AC-2", "AC-3"}
    required_journeys = [
        j for j in journeys if j.get("authority", "author") != "exploratory"
    ]
    for journey in required_journeys:
        traces = journey.get("traces_to", [])
        assert traces, f"Journey {journey['name']!r} lacks traces_to"
        assert set(traces) <= allowed_traces, (
            f"Journey {journey['name']!r} has invalid traces: {traces}"
        )


def test_bwrap_argmax_suite_passes_cleanly() -> None:
    """The targeted bwrap ARG_MAX test suite must pass all test cases without failures."""
    assert BWRAP_TEST.exists(), f"Missing test suite: {BWRAP_TEST}"
    env = os.environ.copy()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            str(BWRAP_TEST),
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
        check=False,
    )
    assert result.returncode == 0, (
        f"tests/test_bwrap_argmax.py failed under pytest:\n{result.stdout}\n{result.stderr}"
    )


def test_bwrap_argmax_uses_repaired_sandbox_harness() -> None:
    """tests/test_bwrap_argmax.py must test the repaired sandbox_exec implementation."""
    content = BWRAP_TEST.read_text(encoding="utf-8")
    assert "sandbox_exec" in content, (
        "tests/test_bwrap_argmax.py must reference scripts/sandbox_exec.py harness "
        "to test the repaired ARG_MAX and environment boundary logic"
    )
