"""Regression suite for repairing the prior run failure 79731be2037a.

Governed run 79731be2037a failed at step_02_implement_and_verify when running:
    python3 -m pytest tests/test_governed_run_a5d017a2cfa1_repair.py

Failure breakdown from cycle report 20260904T080027Z:
1. tests/test_governed_run_a5d017a2cfa1_repair.py::test_bwrap_argmax_suite_passes_cleanly
   failed because child pytest execution of tests/test_bwrap_argmax.py failed:
   FAILED tests/test_bwrap_argmax.py::test_user_journey_contract_oracle_integrity
   AssertionError: USER_JOURNEYS_MANIFEST_SCHEMA must be available
   assert {}
   tests/test_bwrap_argmax.py:251: AssertionError

2. Root cause in tests/test_bwrap_argmax.py:
   When agent_orch is not installed or importable in the child environment,
   the module-level try/except sets USER_JOURNEYS_MANIFEST_SCHEMA = {}, but
   test_user_journey_contract_oracle_integrity asserted that the schema was truthy
   without an import guard or skip, causing an unhandled test failure while other
   tests properly skipped via _require_validators_module().

3. Root cause in tests/test_governed_run_a5d017a2cfa1_repair.py:
   - test_bwrap_argmax_suite_passes_cleanly invoked subprocess.run without passing
     an explicit environment (env=...), failing to propagate PYTHONPATH or parent
     interpreter module search paths to the child pytest process.
   - Top-level import 'from agent_orch.user_journeys import ...' was unguarded,
     causing collection failure when agent_orch is not pre-installed.

These tests reproduce the failure fail-closed before the implementation lands.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

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
BWRAP_TEST = ROOT / "tests" / "test_bwrap_argmax.py"
A5D_REPAIR_TEST = ROOT / "tests" / "test_governed_run_a5d017a2cfa1_repair.py"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"


def test_bwrap_argmax_user_journey_integrity_is_import_guarded_when_agent_orch_absent() -> None:
    """When agent_orch cannot be imported, test_user_journey_contract_oracle_integrity must not fail with AssertionError."""
    assert BWRAP_TEST.exists(), f"Missing {BWRAP_TEST}"

    # Execute test_user_journey_contract_oracle_integrity in an isolated subprocess
    # where agent_orch is explicitly masked out from sys.modules
    script = (
        "import sys; "
        "sys.modules['agent_orch'] = None; "
        "sys.modules['agent_orch.user_journeys'] = None; "
        "import pytest; "
        "sys.exit(pytest.main(["
        "    'tests/test_bwrap_argmax.py', "
        "    '-k', 'test_user_journey_contract_oracle_integrity', "
        "    '-q', '-p', 'no:cacheprovider'"
        "]))"
    )

    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )

    assert "AssertionError: USER_JOURNEYS_MANIFEST_SCHEMA must be available" not in proc.stdout, (
        f"test_bwrap_argmax.py crashed on unguarded USER_JOURNEYS_MANIFEST_SCHEMA assertion:\n{proc.stdout}"
    )
    assert proc.returncode == 0, (
        f"test_user_journey_contract_oracle_integrity failed when agent_orch is absent:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_bwrap_argmax_oracle_integrity_source_contains_import_guard_or_skip() -> None:
    """tests/test_bwrap_argmax.py must guard the schema assertion rather than asserting raw empty schema."""
    assert BWRAP_TEST.exists(), f"Missing {BWRAP_TEST}"
    content = BWRAP_TEST.read_text(encoding="utf-8")

    # In 79731be2037a, line 251 was:
    # assert USER_JOURNEYS_MANIFEST_SCHEMA, "USER_JOURNEYS_MANIFEST_SCHEMA must be available"
    # When agent_orch is not installed, USER_JOURNEYS_MANIFEST_SCHEMA is {}, causing AssertionError.
    unguarded_pattern = r"assert\s+USER_JOURNEYS_MANIFEST_SCHEMA,\s*[\"']USER_JOURNEYS_MANIFEST_SCHEMA must be available[\"']"
    assert not re.search(unguarded_pattern, content), (
        "tests/test_bwrap_argmax.py contains unguarded 'assert USER_JOURNEYS_MANIFEST_SCHEMA', "
        "which raises AssertionError when agent_orch is absent. "
        "It must use an import guard or pytest.skip."
    )


def test_bwrap_argmax_suite_passes_when_agent_orch_absent() -> None:
    """The full tests/test_bwrap_argmax.py suite must pass (or skip) cleanly without agent_orch."""
    assert BWRAP_TEST.exists(), f"Missing {BWRAP_TEST}"

    script = (
        "import sys; "
        "sys.modules['agent_orch'] = None; "
        "sys.modules['agent_orch.validators'] = None; "
        "sys.modules['agent_orch.worker'] = None; "
        "sys.modules['agent_orch.models'] = None; "
        "sys.modules['agent_orch.user_journeys'] = None; "
        "import pytest; "
        "sys.exit(pytest.main(["
        "    'tests/test_bwrap_argmax.py', "
        "    '-q', '-p', 'no:cacheprovider'"
        "]))"
    )

    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )

    assert proc.returncode == 0, (
        f"tests/test_bwrap_argmax.py failed when agent_orch is absent:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_governed_run_a5d017a2cfa1_repair_propagates_environment_to_child_pytest() -> None:
    """tests/test_governed_run_a5d017a2cfa1_repair.py must pass env to subprocess.run."""
    assert A5D_REPAIR_TEST.exists(), f"Missing {A5D_REPAIR_TEST}"
    content = A5D_REPAIR_TEST.read_text(encoding="utf-8")

    # test_bwrap_argmax_suite_passes_cleanly must pass an explicit env parameter
    # to subprocess.run so PYTHONPATH and module resolution are propagated to child pytest
    assert "env=" in content or "env =" in content, (
        "tests/test_governed_run_a5d017a2cfa1_repair.py does not pass env to subprocess.run in "
        "test_bwrap_argmax_suite_passes_cleanly, risking module import failures in child pytest."
    )


def test_governed_run_a5d017a2cfa1_repair_is_import_guarded() -> None:
    """tests/test_governed_run_a5d017a2cfa1_repair.py must be importable even when agent_orch is absent."""
    assert A5D_REPAIR_TEST.exists(), f"Missing {A5D_REPAIR_TEST}"

    script = (
        "import sys; "
        "sys.modules['agent_orch'] = None; "
        "sys.modules['agent_orch.user_journeys'] = None; "
        "import importlib; "
        "importlib.import_module('tests.test_governed_run_a5d017a2cfa1_repair')"
    )

    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )

    assert proc.returncode == 0, (
        f"tests/test_governed_run_a5d017a2cfa1_repair.py failed top-level import when agent_orch is absent:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
