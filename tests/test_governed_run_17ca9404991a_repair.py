"""Regression coverage for the failed governed run 17ca9404991a.

The origin run exposed three compatibility failures: an escaping symlink was
opened before containment was reported, quoted command data was mistaken for a
shell operator, and a blast-radius oracle matched the forbidden-token list it
was asserting.  These tests keep those failures independent and use private
temporary workspaces for every validator fixture.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import jsonschema
import pytest

import agent_orch.validators as validators
from agent_orch.models import ValidationRule
from agent_orch.user_journeys import USER_JOURNEYS_MANIFEST_SCHEMA


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"

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


def _write_json(root: Path, relative: str, value: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _manifest(name: str = "journey") -> dict[str, object]:
    return {
        "journeys": [
            {
                "name": name,
                "authority": "author",
                "traces_to": ["AC-1"],
            }
        ],
        "command_allowlist": ["python3 -c"],
    }


def _result(
    name: str = "journey",
    *,
    status: str = "passed",
    commands: list[dict[str, object]] | None = None,
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "journeys": [
            {
                "name": name,
                "status": status,
                "steps_taken": "Ran the claimed command and recorded its result.",
                "commands_run": commands
                if commands is not None
                else [{"command": "python3 -c 'print(\"ok\")'", "exit_code": 0}],
            }
        ],
        "findings": findings if findings is not None else [],
    }


def _finding(name: str, artifact: str) -> dict[str, object]:
    return {
        "id": "REPAIR-001",
        "severity": "Medium",
        "journey": name,
        "problem": "The user-visible operation did not meet its contract.",
        "reproduction": "Run the command recorded in the journey.",
        "expected": "The documented result is displayed.",
        "actual": "The observed result differs from the documented result.",
        "proposed_fix": "Restore the documented behavior and retain this regression.",
        "artifacts": [artifact],
    }


def _structural_rule(
    root: Path,
    manifest: dict[str, object],
    result: dict[str, object],
    *,
    manifest_path: str = "tests/user_journeys_manifest.json",
    contract_path: str | None = None,
    seed_path: str | None = None,
) -> ValidationRule:
    _write_json(root, "tests/user_journeys_manifest.json", manifest)
    _write_json(root, "artifacts/user-test/result.json", result)
    return ValidationRule(
        type="user_journeys_all_passed",
        path="artifacts/user-test/result.json",
        manifest_path=manifest_path,
        contract_path=contract_path,
        seed_path=seed_path,
    )


def _run_structural(root: Path, rule: ValidationRule):
    return validators._run_structural_rule(rule, root)


@pytest.mark.parametrize("role", ["result", "manifest", "contract", "seed", "finding"])
def test_symlink_escaping_governed_paths_fail_before_schema_or_artifact_use(
    tmp_path: Path, role: str
) -> None:
    """PATH_ESCAPE is reported before an outside file can affect validation."""

    outside = tmp_path.parent / f"{tmp_path.name}-outside-{role}"
    outside.mkdir()
    manifest = _manifest()
    result = _result()
    rule_kwargs: dict[str, str] = {}

    if role == "result":
        outside_file = outside / "result.json"
        outside_file.write_text("{}", encoding="utf-8")
        (tmp_path / "artifacts" / "user-test").mkdir(parents=True)
        (tmp_path / "artifacts" / "user-test").rmdir()
        (tmp_path / "artifacts" / "user-test").symlink_to(
            outside, target_is_directory=True
        )
        _write_json(tmp_path, "tests/user_journeys_manifest.json", manifest)
        rule = ValidationRule(
            type="user_journeys_all_passed",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        )
    elif role == "manifest":
        outside_file = outside / "manifest.json"
        outside_file.write_text(json.dumps(manifest), encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "user_journeys_manifest.json").symlink_to(outside_file)
        _write_json(tmp_path, "artifacts/user-test/result.json", result)
        rule = ValidationRule(
            type="user_journeys_all_passed",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        )
    elif role == "contract":
        outside_file = outside / "contract.md"
        outside_file.write_text("# Acceptance Checks\n\n- AC-1: one\n", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "contract.md").symlink_to(outside_file)
        rule_kwargs["contract_path"] = "docs/contract.md"
        rule = _structural_rule(tmp_path, manifest, result, **rule_kwargs)
    elif role == "seed":
        seeded = {"journeys": [{"name": "journey", "authority": "mission"}]}
        manifest["journeys"] = [
            {"name": "journey", "authority": "human", "traces_to": ["AC-1"]}
        ]
        outside_file = outside / "seed.json"
        outside_file.write_text(json.dumps(seeded), encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "seed.json").symlink_to(outside_file)
        rule_kwargs["seed_path"] = "docs/seed.json"
        rule = _structural_rule(tmp_path, manifest, result, **rule_kwargs)
    else:
        artifact = "evidence/escape.log"
        outside_file = outside / "evidence.log"
        outside_file.write_text("outside evidence\n", encoding="utf-8")
        (tmp_path / "evidence").mkdir()
        (tmp_path / artifact).symlink_to(outside_file)
        result = _result(
            status="failed",
            findings=[_finding("journey", artifact)],
        )
        rule = _structural_rule(tmp_path, manifest, result)

    outcome = _run_structural(tmp_path, rule)

    assert outcome.passed is False
    assert "inside the workspace" in outcome.message
    assert "schema" not in outcome.message.lower()


def _execution_rule(root: Path, result: dict[str, object]) -> ValidationRule:
    _write_json(root, "tests/user_journeys_manifest.json", _manifest())
    _write_json(root, "artifacts/user-test/result.json", result)
    return ValidationRule(
        type="user_journeys_execution_verified",
        path="artifacts/user-test/result.json",
        manifest_path="tests/user_journeys_manifest.json",
    )


def _run_execution(root: Path, rule: ValidationRule):
    return validators._run_system_rule_with_scratch(rule, root, None)


def test_quoted_operator_data_runs_as_direct_argv_with_governed_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """COMMAND_INJECTION parsing is quote-aware but execution remains direct."""

    payload = (
        "import sys\n"
        "from pathlib import Path\n"
        "Path('cwd-sentinel').write_text(str(Path.cwd()))\n"
        "Path('argv-sentinel').write_text(sys.argv[1])"
    )
    command = shlex.join(["python3", "-c", payload, "literal && text"])

    argv, reason = validators._allowlisted_journey_command(
        command, [["python3", "-c"]]
    )
    assert argv == ["python3", "-c", payload, "literal && text"]
    assert reason == ""

    monkeypatch.chdir(tmp_path.parent)
    outcome = _run_execution(
        tmp_path,
        _execution_rule(
            tmp_path,
            _result(commands=[{"command": command, "exit_code": 0}]),
        ),
    )

    assert outcome.passed is True
    assert (tmp_path / "cwd-sentinel").read_text(encoding="utf-8") == str(tmp_path)
    assert (
        (tmp_path / "argv-sentinel").read_text(encoding="utf-8")
        == "literal && text"
    )


def test_rejected_shell_claims_never_execute_or_create_sentinels(tmp_path: Path) -> None:
    """Pipelines, redirections, malformed words, and prefix misses stay rejected."""

    payload = "from pathlib import Path; Path('rejected-sentinel').write_text('bad')"
    bare = shlex.join(["python3", "-c", payload])
    claims = (
        bare + " && echo unsafe",
        bare + " > rejected-output",
        "python3 -c 'unterminated",
        "python3 -m not-the-allowlisted-program",
    )
    for claim in claims:
        argv, reason = validators._allowlisted_journey_command(
            claim, [["python3", "-c"]]
        )
        assert argv is None
        assert reason

    outcome = _run_execution(
        tmp_path,
        _execution_rule(
            tmp_path,
            _result(
                commands=[
                    {"command": bare + " && echo unsafe", "exit_code": 0}
                ]
            ),
        ),
    )
    assert outcome.passed is False
    assert "zero verified" in outcome.message
    assert not (tmp_path / "rejected-sentinel").exists()
    assert not (tmp_path / "rejected-output").exists()


def _forbidden_scope_tokens() -> tuple[str, ...]:
    """Build forbidden operation spellings without embedding them verbatim."""

    return (
        "socket." + "create_connection",
        "urllib." + "request",
        "pip " + "install",
        "make " + "install",
        "git " + "tag",
    )


def test_blast_radius_scope_oracle_does_not_match_its_forbidden_inventory() -> None:
    """BLAST_RADIUS scanning must inspect the target, not its own inventory."""

    focused = {
        MANIFEST.relative_to(ROOT).as_posix(),
        Path(__file__).relative_to(ROOT).as_posix(),
        "tests/test_governed_run_9add44496178.py",
        "tests/test_governed_run_c847e01d15fe.py",
        "tests/test_commissioning_dependencies.py",
        "tests/smoke_manifest.json",
        "scripts/smoke.sh",
    }
    assert "src/sysdiff.c" not in focused
    assert all(path.startswith(("tests/", "scripts/")) for path in focused)

    source = (ROOT / "tests/test_governed_workspace_abstraction.py").read_text(
        encoding="utf-8"
    )
    violations = [token for token in _forbidden_scope_tokens() if token in source]
    assert violations == [], (
        "scope oracle self-matched its forbidden inventory: "
        + ", ".join(violations)
    )


def test_manifest_contains_real_sysdiff_goals_and_repair_traceability() -> None:
    """The committed journey oracle targets the built application and AC-1..3."""

    manifest = json.loads(MANIFEST.read_bytes())
    assert isinstance(manifest, dict)
    assert not list(
        jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA).iter_errors(
            manifest
        )
    )

    journeys = manifest["journeys"]
    names = {journey["name"] for journey in journeys}
    assert PRESERVED_AUTHOR_JOURNEYS <= names
    assert SYSDIFF_JOURNEYS <= names

    allowlist = manifest["command_allowlist"]
    assert "build/sysdiff" in allowlist
    assert all(shlex.split(prefix)[0] == "build/sysdiff" for prefix in allowlist)

    allowed_traces = {"AC-1", "AC-2", "AC-3"}
    required_journeys = [
        journey
        for journey in journeys
        if journey.get("authority", "author") != "exploratory"
    ]
    assert all(journey.get("traces_to") for journey in required_journeys)
    assert all(
        set(journey["traces_to"]) <= allowed_traces
        for journey in required_journeys
    )
    assert {
        trace
        for journey in required_journeys
        for trace in journey["traces_to"]
    } == allowed_traces
