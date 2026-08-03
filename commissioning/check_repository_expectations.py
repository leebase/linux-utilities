#!/usr/bin/env python3
"""Assert Linux Utilities repository expectations over Agent-Orch identity facts.

Agent-Orch owns repository identity. Its ``capture_repository_identity()``
classifies the workspace, detects nested metadata, sanitizes the Git
environment, and compares snapshots before and after every worker attempt as
the ``repository_identity_unchanged`` runtime rule. None of that is
reimplemented here.

What the platform deliberately leaves to a mission is *which* repository the
governed workspace is supposed to be. The platform records the origin remote
and the checked-out branch as evidence; it asserts only that the workspace is a
structurally valid, stable repository. This checker supplies the missing
mission policy: the governed workspace must be the ``linux-utilities`` linked
worktree, on ``refs/heads/main``, with the expected origin remote.

Facts come from the documented Agent-Orch ``commission --json`` contract, so
this stays a policy assertion over platform evidence rather than a second
identity implementation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_WORKSPACE = Path("/home/lee/projects/linux-utilities-autonomous")
DEFAULT_REMOTE = "git@github.com:leebase/linux-utilities.git"
DEFAULT_BRANCH = "refs/heads/main"
VALID_LINKED_WORKTREE = "valid_root_linked_worktree_git_file"
REPOSITORY_CHECK = "repository readiness"
FALLBACK_CLI = Path("/home/lee/projects/agent-orch/.venv/bin/agent-orch")


class ExpectationFailure(RuntimeError):
    """Raised when a mission repository expectation is not satisfied."""


def resolve_cli(explicit: str | None) -> str:
    """Return the Agent-Orch CLI to trust for identity facts."""

    for candidate in (explicit, os.environ.get("AGENT_ORCH_CLI")):
        if candidate:
            return candidate
    discovered = shutil.which("agent-orch")
    if discovered:
        return discovered
    if FALLBACK_CLI.is_file() and os.access(FALLBACK_CLI, os.X_OK):
        return os.fspath(FALLBACK_CLI)
    raise ExpectationFailure(
        "cannot locate the Agent-Orch CLI; set AGENT_ORCH_CLI or pass --agent-orch"
    )


def capture(cli: str, workspace: Path, timeout: int) -> dict:
    """Run the platform commissioning check and return its report."""

    command = [cli, "commission", "--workspace", os.fspath(workspace), "--json"]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExpectationFailure(f"cannot execute {cli}: {exc}") from exc
    if not completed.stdout.strip():
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise ExpectationFailure(f"Agent-Orch produced no commissioning JSON: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExpectationFailure(f"unparsable commissioning JSON: {exc}") from exc


def _repository_evidence(report: dict) -> dict:
    checks = report.get("checks")
    if not isinstance(checks, list):
        raise ExpectationFailure("commissioning report has no checks list")
    for check in checks:
        if isinstance(check, dict) and check.get("name") == REPOSITORY_CHECK:
            if check.get("status") != "ready":
                raise ExpectationFailure(
                    "Agent-Orch repository readiness is "
                    f"{check.get('status')!r}: {check.get('message')}"
                )
            evidence = check.get("evidence")
            if not isinstance(evidence, dict):
                raise ExpectationFailure("repository readiness carries no evidence")
            return evidence
    raise ExpectationFailure(f"commissioning report lacks a {REPOSITORY_CHECK!r} check")


def evaluate(
    evidence: dict, workspace: Path, remote: str, branch: str
) -> list[dict[str, str]]:
    """Return satisfied expectations or raise ExpectationFailure."""

    satisfied: list[dict[str, str]] = []

    classification = evidence.get("repository_classification")
    if classification != VALID_LINKED_WORKTREE:
        raise ExpectationFailure(
            f"repository classification is {classification!r}, "
            f"expected {VALID_LINKED_WORKTREE!r}"
        )
    satisfied.append({"name": "linked-worktree", "detail": classification})

    recorded_root = evidence.get("workspace_root")
    if recorded_root != os.fspath(workspace):
        raise ExpectationFailure(
            f"platform inspected {recorded_root!r}, expected {os.fspath(workspace)!r}"
        )
    satisfied.append({"name": "workspace-root", "detail": str(recorded_root)})

    nested = evidence.get("nested_git_paths") or []
    if nested:
        raise ExpectationFailure(f"nested Git metadata present: {nested}")
    satisfied.append({"name": "no-nested-metadata", "detail": "none"})

    remotes = evidence.get("remotes")
    if not isinstance(remotes, dict):
        raise ExpectationFailure("platform evidence carries no remote map")
    if sorted(remotes) != ["origin"]:
        raise ExpectationFailure(f"unexpected Git remotes: {sorted(remotes)!r}")
    urls = sorted({url for kind in remotes["origin"].values() for url in kind})
    if urls != [remote]:
        raise ExpectationFailure(f"origin URLs are {urls!r}, expected {[remote]!r}")
    satisfied.append({"name": "origin-remote", "detail": remote})

    worktrees = (evidence.get("worktree_identity") or {}).get("worktrees")
    if not isinstance(worktrees, list):
        raise ExpectationFailure("platform evidence carries no worktree set")
    governed = [
        entry
        for entry in worktrees
        if isinstance(entry, dict) and entry.get("path") == os.fspath(workspace)
    ]
    if len(governed) != 1:
        raise ExpectationFailure(
            f"expected exactly one worktree record for {os.fspath(workspace)}, "
            f"found {len(governed)}"
        )
    entry = governed[0]
    if entry.get("detached"):
        raise ExpectationFailure("governed worktree HEAD is detached")
    if entry.get("prunable"):
        raise ExpectationFailure("governed worktree record is prunable")
    if entry.get("branch") != branch:
        raise ExpectationFailure(
            f"governed worktree is on {entry.get('branch')!r}, expected {branch!r}"
        )
    satisfied.append({"name": "governed-branch", "detail": branch})
    return satisfied


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument(
        "--agent-orch",
        dest="agent_orch",
        help="Agent-Orch CLI providing the authoritative identity facts.",
    )
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    workspace = arguments.workspace.resolve()
    try:
        cli = resolve_cli(arguments.agent_orch)
        report = capture(cli, workspace, arguments.timeout)
        evidence = _repository_evidence(report)
        satisfied = evaluate(evidence, workspace, arguments.remote, arguments.branch)
    except ExpectationFailure as exc:
        if arguments.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"repository expectations: FAIL: {exc}", file=sys.stderr)
        return 1

    payload = {
        "ok": True,
        "workspace": os.fspath(workspace),
        "identity_source": "agent-orch commission --json",
        "expectations": satisfied,
    }
    if arguments.as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"repository expectations: PASS ({len(satisfied)} checks)")
        for check in satisfied:
            print(f"  {check['name']}: {check['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
