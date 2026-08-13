"""Focused regressions for the repository-owned user-journey boundary.

These tests exercise the Agent-Orch validator against the slice contract.  The
fixtures are deliberately private temporary workspaces: a rejected command
claim must not be able to leave a file behind in the repository or in a caller
chosen directory.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path

import jsonschema
import pytest

import agent_orch.validators as validators
from agent_orch.models import ValidationRule
from agent_orch.paths import resolve_workspace_path
from agent_orch.user_journeys import (
    JOURNEY_AUTHORITIES,
    USER_JOURNEYS_MANIFEST_SCHEMA,
    authority_rank,
    journey_authority,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
CONTRACT = ROOT / "docs" / "repair-governed-run-17ca9404991a-contract.md"
SMOKE_MANIFEST = ROOT / "tests" / "smoke_manifest.json"
SMOKE_SCRIPT = ROOT / "scripts" / "smoke.sh"


def _schema_error(artifact: object) -> str | None:
    errors = sorted(
        jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA).iter_errors(
            artifact
        ),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return None
    return "; ".join(error.message for error in errors)


def _load_json(path: Path) -> object:
    return json.loads(
        path.read_bytes(), object_pairs_hook=validators._reject_duplicate_json_keys
    )


def _write_json(root: Path, relative: str, value: object | str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _manifest(
    names: list[str],
    *,
    command_allowlist: list[str] | None = None,
    journeys: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "journeys": journeys
        if journeys is not None
        else [
            {
                "name": name,
                "authority": "author",
                "traces_to": ["AC-1"],
            }
            for name in names
        ],
        "command_allowlist": command_allowlist
        if command_allowlist is not None
        else ["python3 -c"],
    }


def _passed_journey(
    name: str,
    *,
    status: str = "passed",
    commands_run: list[dict[str, object]] | None = None,
    steps_taken: str | list[str] = "Ran the command and observed its output.",
) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "steps_taken": steps_taken,
        "commands_run": commands_run
        if commands_run is not None
        else [
            {
                "command": "python3 -c 'print(\"ok\")'",
                "exit_code": 0,
                "stdout_contains": "ok",
            }
        ],
    }


def _finding(name: str, *, artifacts: list[str] | None = None) -> dict[str, object]:
    return {
        "id": "UJ-001",
        "severity": "Medium",
        "journey": name,
        "problem": "The user-visible operation did not meet its contract.",
        "reproduction": "Run the command from the journey steps.",
        "expected": "The documented result is displayed.",
        "actual": "The observed result differs from the documented result.",
        "proposed_fix": "Restore the documented behavior and retain the regression.",
        **({"artifacts": artifacts} if artifacts is not None else {}),
    }


def _structural_rule(
    root: Path,
    manifest: object,
    result: object,
    *,
    contract_path: str | None = None,
    seed_path: str | None = None,
) -> ValidationRule:
    _write_json(root, "tests/user_journeys_manifest.json", manifest)
    _write_json(root, "artifacts/user-test/result.json", result)
    return ValidationRule(
        type="user_journeys_all_passed",
        path="artifacts/user-test/result.json",
        manifest_path="tests/user_journeys_manifest.json",
        contract_path=contract_path,
        seed_path=seed_path,
    )


def _run_structural(root: Path, rule: ValidationRule):
    return validators._run_structural_rule(rule, root)


def _execution_rule(
    root: Path,
    manifest: object,
    result: object,
    *,
    command_allowlist: list[str],
) -> ValidationRule:
    manifest = dict(manifest)  # type: ignore[arg-type]
    manifest["command_allowlist"] = command_allowlist
    _write_json(root, "tests/user_journeys_manifest.json", manifest)
    _write_json(root, "artifacts/user-test/result.json", result)
    return ValidationRule(
        type="user_journeys_execution_verified",
        path="artifacts/user-test/result.json",
        manifest_path="tests/user_journeys_manifest.json",
    )


def _run_execution(root: Path, rule: ValidationRule):
    return validators._run_system_rule_with_scratch(rule, root, None)


def test_manifest_accepts_valid_schema_and_author_default() -> None:
    """AC-1: the committed manifest is a named, nonempty repository oracle."""

    manifest = _load_json(MANIFEST)
    assert isinstance(manifest, dict)
    assert _schema_error(manifest) is None
    assert manifest["command_allowlist"] == ["build/sysdiff"]
    assert shlex.split(manifest["command_allowlist"][0]) == [
        "build/sysdiff",
    ]

    journeys = manifest["journeys"]
    assert isinstance(journeys, list) and journeys
    assert all(isinstance(journey["name"], str) for journey in journeys)
    assert len({journey["name"] for journey in journeys}) == len(journeys)
    assert journey_authority({"name": "omitted authority"}) == "author"

    # Optional fields and inert compatibility properties do not grant any
    # authority or command permission.
    optional = {
        "journeys": [{"name": "author goal", "traces_to": ["AC-1"]}],
        "command_allowlist": ["python3 -c"],
        "future_metadata": {"does_not_grant": "authority"},
    }
    assert _schema_error(optional) is None
    assert journey_authority(optional["journeys"][0]) == "author"


@pytest.mark.parametrize(
    ("raw", "message_fragment"),
    [
        ("{", "Invalid JSON"),
        ('{"journeys": [], "command_allowlist": ["python3 -c"]}', "manifest"),
        (
            '{"journeys": [{"name": ""}], "command_allowlist": ["python3 -c"]}',
            "manifest",
        ),
        (
            '{"journeys": [{"name": "x"}], "command_allowlist": []}',
            "manifest",
        ),
        (
            '{"journeys": [{"name": "x", "authority": "producer"}], '
            '"command_allowlist": ["python3 -c"]}',
            "manifest",
        ),
        (
            '{"journeys": [{"name": "x", "traces_to": "AC-1"}], '
            '"command_allowlist": ["python3 -c"]}',
            "manifest",
        ),
        (
            '{"journeys": [{"name": "x"}], "command_allowlist": [""]}',
            "manifest",
        ),
    ],
)
def test_manifest_rejects_invalid_json_duplicate_keys_types_empty_fields_and_authority(
    tmp_path: Path, raw: str, message_fragment: str
) -> None:
    """AC-2: malformed input fails closed before any claimed command runs."""

    result = {"journeys": [_passed_journey("x")], "findings": []}
    _write_json(tmp_path, "tests/user_journeys_manifest.json", raw)
    _write_json(tmp_path, "artifacts/user-test/result.json", result)
    outcome = _run_structural(
        tmp_path,
        ValidationRule(
            type="user_journeys_all_passed",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        ),
    )
    assert outcome.passed is False
    assert message_fragment in outcome.message


def test_duplicate_manifest_keys_are_rejected_without_execution(tmp_path: Path) -> None:
    """AC-2: duplicate JSON keys cannot silently replace an allowlist."""

    sentinel = "python3 -c 'from pathlib import Path; Path(\"executed\").write_text(\"bad\")'"
    raw = (
        '{"journeys": [{"name": "x"}], '
        f'"command_allowlist": {json.dumps([sentinel])}, '
        '"command_allowlist": ["python3 -c"]}'
    )
    result = {
        "journeys": [
            _passed_journey(
                "x", commands_run=[{"command": sentinel, "exit_code": 0}]
            )
        ],
        "findings": [],
    }
    _write_json(tmp_path, "tests/user_journeys_manifest.json", raw)
    _write_json(tmp_path, "artifacts/user-test/result.json", result)
    outcome = _run_execution(
        tmp_path,
        ValidationRule(
            type="user_journeys_execution_verified",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        ),
    )
    assert outcome.passed is False
    assert "Invalid JSON" in outcome.message
    assert not (tmp_path / "executed").exists()


def test_workspace_paths_are_root_relative_and_symlink_contained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3: every governed path is resolved from the canonical workspace."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "nested").mkdir()
    (workspace / "nested" / "inside.txt").write_text("inside", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (workspace / "escape-link").symlink_to(outside, target_is_directory=True)

    for context in (
        "manifest_path",
        "seed_path",
        "contract_path",
        "result_path",
        "finding_artifact",
        "playbook_path",
    ):
        assert resolve_workspace_path(
            workspace, "nested//inside.txt", context
        ) == workspace / "nested" / "inside.txt"

    monkeypatch.chdir(outside)
    assert resolve_workspace_path(workspace, "nested/inside.txt", "cwd test") == (
        workspace / "nested" / "inside.txt"
    )

    for invalid in ("", " ", ".", "./", "/tmp/elsewhere", "../outside", "a/../../x"):
        with pytest.raises(ValueError, match="workspace|relative|empty|root"):
            resolve_workspace_path(workspace, invalid, "path")
    with pytest.raises(ValueError, match="inside the workspace"):
        resolve_workspace_path(workspace, "escape-link/secret.txt", "symlink path")


def test_workspace_rule_paths_fail_closed_for_symlink_escape(tmp_path: Path) -> None:
    """AC-3: result, contract, seed, and finding paths cannot follow out."""

    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "result.json").write_text("{}", encoding="utf-8")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "user-test").symlink_to(outside, target_is_directory=True)
    outcome = _run_structural(
        tmp_path,
        ValidationRule(
            type="user_journeys_all_passed",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        ),
    )
    assert outcome.passed is False
    assert "inside the workspace" in outcome.message


def test_commands_use_token_prefixes_and_direct_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-4: claims match argv tokens and execute with the workspace as cwd."""

    prefix = [["bash", "scripts/smoke.sh"]]
    argv, reason = validators._allowlisted_journey_command(
        "bash scripts/smoke.sh --diagnose", prefix
    )
    assert argv == ["bash", "scripts/smoke.sh", "--diagnose"]
    assert reason == ""

    rejected, reason = validators._allowlisted_journey_command(
        "bash scripts/smoke.sh.evil", prefix
    )
    assert rejected is None
    assert "argv prefix" in reason

    assigned, reason = validators._allowlisted_journey_command(
        "SMOKE_MODE=1 bash scripts/smoke.sh", prefix
    )
    assert assigned == ["SMOKE_MODE=1", "bash", "scripts/smoke.sh"]
    assert reason == ""

    payload = (
        "import sys\n"
        "from pathlib import Path\n"
        "Path('cwd-sentinel').write_text(str(Path.cwd()))\n"
        "Path('argv-sentinel').write_text(sys.argv[1])"
    )
    # Keep shell-operator-looking text inside one quoted claim word.  A shell
    # would interpret it; direct argv execution must pass the literal token.
    direct_command = (
        f"python3 -c {shlex.quote(payload)} {shlex.quote('literal && text')}"
    )
    manifest = _manifest(["direct argv"])
    result = {
        "journeys": [
            _passed_journey(
                "direct argv",
                commands_run=[{"command": direct_command, "exit_code": 0}],
            )
        ],
        "findings": [],
    }
    # The caller's current directory is intentionally unrelated to the
    # governed workspace.  The validator must pass tmp_path as cwd and must
    # invoke Python directly rather than through a shell.
    monkeypatch.chdir(tmp_path.parent)
    outcome = _run_execution(
        tmp_path,
        _execution_rule(tmp_path, manifest, result, command_allowlist=["python3 -c"]),
    )
    assert outcome.passed is True
    assert (tmp_path / "cwd-sentinel").read_text(encoding="utf-8") == str(tmp_path)
    assert (
        (tmp_path / "argv-sentinel").read_text(encoding="utf-8")
        == "literal && text"
    )


@pytest.mark.parametrize(
    ("claim", "expected_argv"),
    [
        (
            "python3 -m governed_tool extra",
            ["python3", "-m", "governed_tool", "extra"],
        ),
        ("python3 -m governed_tool_evil", None),
        ("python3 -m", None),
    ],
)
def test_allowlist_prefixes_are_matched_token_by_token(
    claim: str, expected_argv: list[str] | None
) -> None:
    """AC-4: a complete argv token prefix is not a textual substring."""

    argv, reason = validators._allowlisted_journey_command(
        claim, [["python3", "-m", "governed_tool"]]
    )
    assert argv == expected_argv
    if expected_argv is None:
        assert "argv prefix" in reason
    else:
        assert reason == ""


def test_shell_operators_and_malformed_claims_are_never_shelled(tmp_path: Path) -> None:
    """AC-4: pipelines, redirections, and parse failures are unverified."""

    sentinel = (
        "from pathlib import Path\n"
        "Path('shell-sentinel').write_text('bad')"
    )
    pipeline = shlex.join(["python3", "-c", sentinel]) + " && echo unsafe"
    malformed = "python3 -c 'unterminated"
    for claim in (pipeline, malformed):
        argv, reason = validators._allowlisted_journey_command(
            claim, [["python3", "-c"]]
        )
        assert argv is None
        assert reason

    result = {
        "journeys": [
            _passed_journey(
                "unsafe claim",
                commands_run=[{"command": pipeline, "exit_code": 0}],
            )
        ],
        "findings": [],
    }
    outcome = _run_execution(
        tmp_path,
        _execution_rule(
            tmp_path,
            _manifest(["unsafe claim"]),
            result,
            command_allowlist=["python3 -c"],
        ),
    )
    assert outcome.passed is False
    assert "zero verified re-executions" in outcome.message
    assert not (tmp_path / "shell-sentinel").exists()


def test_canonical_failed_journey_finding_is_actionable(tmp_path: Path) -> None:
    """AC-8: a failed journey reports every canonical finding field."""

    finding = _finding("failed journey")
    assert set(finding) == {
        "id",
        "severity",
        "journey",
        "problem",
        "reproduction",
        "expected",
        "actual",
        "proposed_fix",
    }
    result = {
        "journeys": [_passed_journey("failed journey", status="failed")],
        "findings": [finding],
    }
    outcome = _run_structural(
        tmp_path,
        _structural_rule(tmp_path, _manifest(["failed journey"]), result),
    )
    assert outcome.passed is False
    assert "not actionable evidence" not in outcome.message
    assert outcome.evidence is not None


def test_authority_order_and_seed_cannot_be_weakened(tmp_path: Path) -> None:
    """AC-5: seeded journeys survive at equal or stronger authority."""

    assert JOURNEY_AUTHORITIES == ("human", "mission", "author", "exploratory")
    assert [authority_rank(value) for value in JOURNEY_AUTHORITIES] == [0, 1, 2, 3]
    for authority in JOURNEY_AUTHORITIES:
        assert journey_authority({"name": "goal", "authority": authority}) == authority

    seed = {"journeys": [{"name": "seeded goal", "authority": "mission"}]}
    _write_json(tmp_path, "docs/seed.json", seed)

    preserved = _structural_rule(
        tmp_path,
        _manifest(
            ["seeded goal"],
            journeys=[
                {
                    "name": "seeded goal",
                    "authority": "human",
                    "traces_to": ["AC-1"],
                }
            ],
        ),
        {"journeys": [_passed_journey("seeded goal")], "findings": []},
        seed_path="docs/seed.json",
    )
    assert _run_structural(tmp_path, preserved).passed is True

    for weakened in (
        [],
        [{"name": "seeded goal", "authority": "author", "traces_to": ["AC-1"]}],
    ):
        manifest = _manifest(
            ["other goal"],
            journeys=weakened
            or [
                {
                    "name": "other goal",
                    "authority": "author",
                    "traces_to": ["AC-1"],
                }
            ],
        )
        result_name = "other goal" if weakened == [] else "seeded goal"
        outcome = _run_structural(
            tmp_path,
            _structural_rule(
                tmp_path,
                manifest,
                {"journeys": [_passed_journey(result_name)], "findings": []},
                seed_path="docs/seed.json",
            ),
        )
        assert outcome.passed is False
        assert "seeded" in outcome.message


def test_contract_traceability_covers_all_acceptance_ids() -> None:
    """AC-6: every contract AC is covered by a required journey."""

    manifest = _load_json(MANIFEST)
    assert isinstance(manifest, dict)
    contract_ids = {
        match.group(0).upper()
        for match in re.finditer(r"\bAC-\d+\b", CONTRACT.read_text(encoding="utf-8"), re.I)
    }
    assert contract_ids == {f"AC-{number}" for number in range(1, 4)}
    required_authorities = {"human", "mission", "author"}
    for contract_id in contract_ids:
        assert any(
            contract_id in {trace.upper() for trace in journey.get("traces_to", [])}
            and journey.get("authority", "author") in required_authorities
            for journey in manifest["journeys"]
        ), f"{contract_id} lacks a required journey in the committed manifest"
    assert validators._user_journeys_traceability_problems(
        ROOT, CONTRACT.relative_to(ROOT).as_posix(), manifest
    ) == []

def test_exploratory_journeys_do_not_satisfy_missing_contract_coverage(
    tmp_path: Path,
) -> None:
    """AC-6: exploration supplements required traceability; it cannot replace it."""

    _write_json(tmp_path, "tests/user_journeys_manifest.json", {})
    _write_json(tmp_path, "artifacts/user-test/result.json", {})
    _write_json(tmp_path, "docs/seed.json", {"journeys": []})
    _write_json(tmp_path, "docs/contract.md", "## Acceptance Checks\n- AC-1: one\n- AC-2: two\n")
    manifest = _manifest(
        ["required"],
        journeys=[
            {"name": "required", "authority": "author", "traces_to": ["AC-1"]},
            {"name": "exploration", "authority": "exploratory"},
        ],
    )
    result = {
        "journeys": [_passed_journey("required"), _passed_journey("exploration")],
        "findings": [],
    }
    outcome = _run_structural(
        tmp_path,
        _structural_rule(tmp_path, manifest, result, contract_path="docs/contract.md"),
    )
    assert outcome.passed is False
    assert "AC-2" in outcome.message
    assert "covered by no required journey" in outcome.message


def test_manifest_pin_rejects_hash_trace_and_allowlist_tampering(tmp_path: Path) -> None:
    """AC-7: a producer cannot narrow the pinned journey or command surface."""

    manifest = _manifest(["pinned goal"], command_allowlist=["bash scripts/smoke.sh"])
    path = _write_json(tmp_path, "tests/user_journeys_manifest.json", manifest)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pin_rule = ValidationRule(type="file_hash_matches", path="tests/user_journeys_manifest.json", sha256=digest)
    assert _run_structural(tmp_path, pin_rule).passed is True

    for mutation in (
        lambda data: data["journeys"][0]["traces_to"].pop(),
        lambda data: data.__setitem__("command_allowlist", ["bash"]),
        lambda data: data["journeys"].pop(),
    ):
        changed = json.loads(json.dumps(manifest))
        mutation(changed)
        path.write_text(json.dumps(changed), encoding="utf-8")
        outcome = _run_structural(tmp_path, pin_rule)
        assert outcome.passed is False
        assert "SHA-256 mismatch" in outcome.message
        path.write_bytes(json.dumps(manifest).encode("utf-8"))


def test_result_requires_all_journeys_steps_commands_findings_and_evidence(
    tmp_path: Path,
) -> None:
    """AC-8: results cannot omit work or turn an unevidenced failure green."""

    names = ["happy path", "hard path"]
    manifest = _manifest(names)
    complete = {
        "journeys": [_passed_journey(name) for name in names],
        "findings": [],
    }
    assert _run_structural(tmp_path, _structural_rule(tmp_path, manifest, complete)).passed

    omitted = {"journeys": [_passed_journey(names[0])], "findings": []}
    outcome = _run_structural(tmp_path, _structural_rule(tmp_path, manifest, omitted))
    assert outcome.passed is False
    assert "never attempted" in outcome.message

    for invalid in (
        {
            "journeys": [_passed_journey("happy path", steps_taken=[])],
            "findings": [],
        },
        {
            "journeys": [_passed_journey("happy path", commands_run=[])],
            "findings": [],
        },
    ):
        outcome = _run_structural(tmp_path, _structural_rule(tmp_path, manifest, invalid))
        assert outcome.passed is False
        assert "result schema" in outcome.message

    failed = {
        "journeys": [_passed_journey("happy path"), _passed_journey("hard path", status="failed")],
        "findings": [],
    }
    outcome = _run_structural(tmp_path, _structural_rule(tmp_path, manifest, failed))
    assert outcome.passed is False
    assert "produced no finding" in outcome.message

    finding = _finding("hard path", artifacts=["artifacts/user-test/hard.log"])
    failed["findings"] = [finding]
    outcome = _run_structural(tmp_path, _structural_rule(tmp_path, manifest, failed))
    assert outcome.passed is False
    assert "does not exist" in outcome.message

    evidence = tmp_path / "artifacts" / "user-test" / "hard.log"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("", encoding="utf-8")
    outcome = _run_structural(tmp_path, _structural_rule(tmp_path, manifest, failed))
    assert outcome.passed is False
    assert "is empty" in outcome.message

    evidence.write_text("reproduction evidence\n", encoding="utf-8")
    outcome = _run_structural(tmp_path, _structural_rule(tmp_path, manifest, failed))
    assert outcome.passed is False
    assert "not actionable evidence" not in outcome.message
    assert outcome.evidence is not None


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "severity",
        "journey",
        "problem",
        "reproduction",
        "expected",
        "actual",
        "proposed_fix",
    ],
)
def test_user_test_findings_require_canonical_actionable_fields(
    tmp_path: Path, missing_field: str
) -> None:
    """AC-8: every finding field needed by a repairer is mandatory."""

    finding = _finding("failed journey")
    finding.pop(missing_field)
    result = {
        "journeys": [_passed_journey("failed journey", status="failed")],
        "findings": [finding],
    }
    outcome = _run_structural(
        tmp_path,
        _structural_rule(tmp_path, _manifest(["failed journey"]), result),
    )
    assert outcome.passed is False
    assert "result schema" in outcome.message


def test_cited_finding_artifacts_must_be_workspace_relative_and_nonempty(
    tmp_path: Path,
) -> None:
    """AC-8: cited evidence must be real, contained, and nonempty."""

    manifest = _manifest(["failed journey"])
    result = {
        "journeys": [_passed_journey("failed journey", status="failed")],
        "findings": [_finding("failed journey", artifacts=["evidence.log"])],
    }
    _write_json(tmp_path, "tests/user_journeys_manifest.json", manifest)
    _write_json(tmp_path, "artifacts/user-test/result.json", result)

    (tmp_path / "evidence.log").write_text("evidence\n", encoding="utf-8")
    outcome = _run_structural(
        tmp_path,
        ValidationRule(
            type="user_journeys_all_passed",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        ),
    )
    assert outcome.passed is False
    assert "not actionable evidence" not in outcome.message

    result["findings"][0]["artifacts"] = ["../evidence.log"]
    _write_json(tmp_path, "artifacts/user-test/result.json", result)
    outcome = _run_structural(
        tmp_path,
        ValidationRule(
            type="user_journeys_all_passed",
            path="artifacts/user-test/result.json",
            manifest_path="tests/user_journeys_manifest.json",
        ),
    )
    assert outcome.passed is False
    assert "workspace" in outcome.message


def test_execution_evidence_requires_the_pinned_command_allowlist(
    tmp_path: Path,
) -> None:
    """AC-4: an unallowlisted claim is not execution evidence or permission."""

    payload = "__import__('pathlib').Path('unlisted-sentinel').write_text('bad')"
    command = shlex.join(["python3", "-c", payload])
    result = {
        "journeys": [
            _passed_journey(
                "pinned command",
                commands_run=[{"command": command, "exit_code": 0}],
            )
        ],
        "findings": [],
    }
    outcome = _run_execution(
        tmp_path,
        _execution_rule(
            tmp_path,
            _manifest(["pinned command"]),
            result,
            command_allowlist=["python3 -m pytest"],
        ),
    )
    assert outcome.passed is False
    assert "zero verified re-executions" in outcome.message
    assert not (tmp_path / "unlisted-sentinel").exists()


def test_execution_verified_rejects_mismatched_exit_output_and_zero_claims(
    tmp_path: Path,
) -> None:
    """AC-8: command claims must reproduce, including exit and output."""

    mismatch = {
        "journeys": [
            _passed_journey(
                "claim",
                commands_run=[
                    {"command": "python3 -c 'raise SystemExit(3)'", "exit_code": 0}
                ],
            )
        ],
        "findings": [],
    }
    outcome = _run_execution(
        tmp_path,
        _execution_rule(tmp_path, _manifest(["claim"]), mismatch, command_allowlist=["python3 -c"]),
    )
    assert outcome.passed is False
    assert "claimed exit 0" in outcome.message

    output_mismatch = {
        "journeys": [
            _passed_journey(
                "claim",
                commands_run=[
                    {
                        "command": "python3 -c 'print(\"actual\")'",
                        "exit_code": 0,
                        "stdout_contains": "missing",
                    }
                ],
            )
        ],
        "findings": [],
    }
    outcome = _run_execution(
        tmp_path,
        _execution_rule(tmp_path, _manifest(["claim"]), output_mismatch, command_allowlist=["python3 -c"]),
    )
    assert outcome.passed is False
    assert "did not produce it" in outcome.message

    no_claim = {
        "journeys": [_passed_journey("claim", commands_run=[{"command": "other-tool", "exit_code": 0}])],
        "findings": [],
    }
    outcome = _run_execution(
        tmp_path,
        _execution_rule(tmp_path, _manifest(["claim"]), no_claim, command_allowlist=["python3 -c"]),
    )
    assert outcome.passed is False
    assert "zero verified re-executions" in outcome.message


def test_smoke_manifest_and_helper_chain_remain_unchanged() -> None:
    """AC-9: the user abstraction is additive to deterministic smoke."""

    smoke = _load_json(SMOKE_MANIFEST)
    assert smoke["start_command"] == ["python3", "tests/smoke_start.py"]
    assert smoke["check_command"] == ["python3", "tests/check_sysdiff_smoke.py"]
    assert {
        tuple(step["command"])
        for step in smoke["steps"]
    } >= {
        ("bash", "scripts/smoke.sh"),
        ("bash", "tests/test_sysdiff_fixture.sh"),
        ("python3", "tests/smoke_start.py"),
        ("python3", "tests/check_sysdiff_smoke.py"),
    }
    assert SMOKE_SCRIPT.read_text(encoding="utf-8") == "#!/usr/bin/env bash\nset -euo pipefail\n\nmake test\n"
    assert "user_journeys_manifest" not in SMOKE_MANIFEST.read_text(encoding="utf-8")
    for module in (
        "tests/test_governed_run_9add44496178.py",
        "tests/test_governed_run_c847e01d15fe.py",
        "tests/test_commissioning_dependencies.py",
    ):
        assert (ROOT / module).is_file()


def test_blast_radius_is_additive_and_non_product() -> None:
    """AC-10: focused coverage names only the governed test/oracle boundary."""

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
    source = Path(__file__).read_text(encoding="utf-8")
    for forbidden in (
        "socket." + "create_connection",
        "urllib." + "request",
        "pip " + "install",
        "make " + "install",
        "git " + "tag",
    ):
        assert forbidden not in source
