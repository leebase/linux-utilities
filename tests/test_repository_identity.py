import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_repository_identity.py"


def load_module():
    spec = importlib.util.spec_from_file_location("repository_identity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_guard(*arguments, env=None):
    command = [sys.executable, os.fspath(SCRIPT), *map(os.fspath, arguments)]
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_live_autonomous_worktree_passes_json_identity_check():
    if not (
        (Path("/home/lee/projects/linux-utilities-autonomous").is_dir())
        and Path("/home/lee/projects/linux-utilities/.git").is_dir()
    ):
        pytest.skip("host does not have the mission's linked autonomous worktree")
    result = run_guard("--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    names = {entry["name"] for entry in payload["checks"]}
    assert {
        "worktree-git-pointer",
        "git-common-dir",
        "git-head-path",
        "origin-remote",
        "no-nested-repository",
    } <= names


def test_redirect_environment_fails_closed(monkeypatch):
    module = load_module()
    monkeypatch.setenv("GIT_DIR", "/tmp/disposable-git")

    try:
        module.verify(module.DEFAULT_REPOSITORY, module.DEFAULT_WORKSPACE)
    except module.IdentityFailure as exc:
        assert "GIT_DIR" in str(exc)
    else:
        raise AssertionError("redirected Git environment was accepted")


def test_nested_repository_marker_is_rejected(tmp_path):
    module = load_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    nested = workspace / "product" / ".git"
    nested.parent.mkdir()
    nested.write_text("gitdir: /tmp/disposable\n", encoding="utf-8")

    try:
        module._nested_repository_checks(workspace)
    except module.IdentityFailure as exc:
        assert str(nested) in str(exc)
    else:
        raise AssertionError("nested repository marker was accepted")


def test_disposable_roots_are_not_product_nested_repository_scope(tmp_path):
    module = load_module()
    workspace = tmp_path / "workspace"
    disposable = workspace / ".agent-orch-scratch" / "attempt" / ".git"
    disposable.parent.mkdir(parents=True)
    disposable.write_text("gitdir: /tmp/disposable\n", encoding="utf-8")

    assert module._nested_repository_checks(workspace)[0].passed is True


def test_protect_dry_run_is_explicit_and_lists_only_identity_metadata(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "verify", lambda repository, workspace: [])

    paths = module.protect(module.DEFAULT_REPOSITORY, module.DEFAULT_WORKSPACE, True)
    assert paths == list(
        module.protected_paths(module.DEFAULT_REPOSITORY, module.DEFAULT_WORKSPACE)
    )
    assert all(
        path.name in {".git", "config", "HEAD", "commondir", "gitdir"}
        for path in paths
    )
