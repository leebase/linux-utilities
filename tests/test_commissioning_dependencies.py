"""Commissioning validator dependencies must resolve from committed baselines.

The final supervised commissioning playbook once invoked two scripts through
the separate interactive checkout at ``/home/lee/projects/linux-utilities``.
Those scripts are tracked only on the ``agent/public-utility-guides`` branch and
are absent from that checkout's ``main``, so a reproducible commissioning run
silently depended on a mutable external checkout staying on one branch.

These tests pin the repaired contract: no commissioning artifact may reference
the interactive checkout, every workspace-relative validator must exist in the
governed worktree, and the mission-owned repository expectation checker must
fail closed on each expectation it asserts.

See ``docs/commissioning-validator-ownership.md``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "playbooks" / "final_supervised_commissioning_20260802.yaml"
PACKET_JSON = ROOT / "commissioning" / "final-commissioning-packet-2026-08-02.json"
PACKET_MD = ROOT / "commissioning" / "final-commissioning-packet-2026-08-02.md"
CHECKER = ROOT / "commissioning" / "check_repository_expectations.py"

# The interactive checkout. Matching must not accidentally catch the governed
# worktree or the sibling runs root, both of which share this prefix.
INTERACTIVE = "/home/lee/projects/linux-utilities/"

WORKSPACE = "/home/lee/projects/linux-utilities-autonomous"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_repository_expectations", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _evidence() -> dict:
    """Platform identity evidence for a correctly governed workspace."""

    return {
        "repository_classification": "valid_root_linked_worktree_git_file",
        "workspace_root": WORKSPACE,
        "nested_git_paths": [],
        "remotes": {"origin": {"url": ["git@github.com:leebase/linux-utilities.git"]}},
        "worktree_identity": {
            "worktrees": [
                {
                    "path": "/home/lee/projects/linux-utilities",
                    "branch": "refs/heads/agent/public-utility-guides",
                    "detached": False,
                    "prunable": False,
                },
                {
                    "path": WORKSPACE,
                    "branch": "refs/heads/main",
                    "detached": False,
                    "prunable": False,
                },
            ]
        },
    }


def _evaluate(evidence: dict):
    return checker.evaluate(
        evidence,
        Path(WORKSPACE),
        "git@github.com:leebase/linux-utilities.git",
        "refs/heads/main",
    )


# --- dependency hygiene -------------------------------------------------


@pytest.mark.parametrize("path", [PLAYBOOK, PACKET_JSON, PACKET_MD])
def test_commissioning_artifacts_do_not_reference_the_interactive_checkout(path):
    offending = [
        f"{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if INTERACTIVE in line
    ]
    assert not offending, "interactive-checkout dependency reintroduced:\n" + "\n".join(
        offending
    )


def test_declared_packet_inputs_all_exist_in_committed_baselines():
    declared = json.loads(PACKET_JSON.read_text(encoding="utf-8"))["declared_inputs"]
    missing = []
    for value in declared:
        candidate = Path(value) if Path(value).is_absolute() else ROOT / value
        if not candidate.exists():
            missing.append(value)
    assert not missing, f"declared inputs missing from committed baselines: {missing}"


def test_workspace_relative_playbook_validators_exist():
    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    referenced = set()
    for step in playbook["steps"]:
        for rule in step.get("validation", {}).get("system", []):
            for token in rule.get("command", "").split():
                if token.startswith("commissioning/") or token.startswith("tests/"):
                    # pytest node IDs carry a ``::name`` selector after the path.
                    referenced.add(token.split("::", 1)[0])
    assert referenced, "expected the playbook to invoke workspace-relative validators"
    missing = sorted(token for token in referenced if not (ROOT / token).exists())
    assert not missing, f"playbook references absent workspace files: {missing}"


def test_scratch_retention_is_delegated_to_the_platform_cli():
    """Scratch retention is an Agent-Orch concern, not duplicated mission logic."""

    playbook = json.loads(PLAYBOOK.read_text(encoding="utf-8"))
    commands = [
        rule.get("command", "")
        for step in playbook["steps"]
        for rule in step.get("validation", {}).get("system", [])
    ]
    scratch = [command for command in commands if "scratch" in command]
    assert len(scratch) == 1, f"expected one scratch validator, found {scratch}"
    assert "agent-orch scratch-clean" in scratch[0]
    # A dry run plans cleanup; --apply would delete evidence during commissioning.
    assert "--apply" not in scratch[0]
    # The mission keeps its tighter window rather than the 30-day platform default.
    assert "--retention-days 2" in scratch[0]
    assert "--runs-dir" in scratch[0]


# --- mission expectation checker ---------------------------------------


def test_expectations_pass_for_a_correctly_governed_workspace():
    names = [check["name"] for check in _evaluate(_evidence())]
    assert names == [
        "linked-worktree",
        "workspace-root",
        "no-nested-metadata",
        "origin-remote",
        "governed-branch",
    ]


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (
            lambda e: e.update(repository_classification="valid_root_git_directory"),
            "classification",
        ),
        (lambda e: e.update(workspace_root="/home/lee/projects/elsewhere"), "inspected"),
        (lambda e: e.update(nested_git_paths=["/nested/.git"]), "nested"),
        (
            lambda e: e.update(
                remotes={"origin": {"url": ["git@github.com:someone/else.git"]}}
            ),
            "origin URLs",
        ),
        (
            lambda e: e.update(
                remotes={
                    "origin": {"url": ["git@github.com:leebase/linux-utilities.git"]},
                    "mirror": {"url": ["git@github.com:someone/else.git"]},
                }
            ),
            "unexpected Git remotes",
        ),
        (
            lambda e: e["worktree_identity"]["worktrees"][1].update(
                branch="refs/heads/agent/public-utility-guides"
            ),
            "governed worktree is on",
        ),
        (
            lambda e: e["worktree_identity"]["worktrees"][1].update(detached=True),
            "detached",
        ),
        (
            lambda e: e["worktree_identity"]["worktrees"][1].update(prunable=True),
            "prunable",
        ),
        (lambda e: e.update(worktree_identity={"worktrees": []}), "exactly one worktree"),
    ],
)
def test_expectations_fail_closed(mutate, expected):
    evidence = copy.deepcopy(_evidence())
    mutate(evidence)
    with pytest.raises(checker.ExpectationFailure) as failure:
        _evaluate(evidence)
    assert expected in str(failure.value)


def test_platform_not_ready_blocks_the_mission_expectation_check():
    report = {
        "checks": [
            {
                "name": "repository readiness",
                "status": "not_ready",
                "message": "nested Git metadata exists inside the workspace",
                "evidence": {},
            }
        ]
    }
    with pytest.raises(checker.ExpectationFailure) as failure:
        checker._repository_evidence(report)
    assert "not_ready" in str(failure.value)


def test_missing_repository_check_is_a_failure():
    with pytest.raises(checker.ExpectationFailure):
        checker._repository_evidence({"checks": [{"name": "platform readiness"}]})


def test_unlocatable_platform_cli_fails_closed(monkeypatch):
    monkeypatch.delenv("AGENT_ORCH_CLI", raising=False)
    monkeypatch.setattr(checker.shutil, "which", lambda _name: None)
    monkeypatch.setattr(checker, "FALLBACK_CLI", Path("/nonexistent/agent-orch"))
    with pytest.raises(checker.ExpectationFailure) as failure:
        checker.resolve_cli(None)
    assert "Agent-Orch CLI" in str(failure.value)
