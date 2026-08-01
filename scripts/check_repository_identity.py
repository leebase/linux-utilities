#!/usr/bin/env python3
"""Verify and optionally protect the Linux Utilities governed worktree.

The autonomous checkout is a linked worktree. Its .git file and the three
files in the common repository's worktree-admin directory are identity
metadata, not worker output. This checker validates those paths directly
before consulting Git, so changed Git configuration cannot make the check look
at a different repository.

The --protect option applies the Linux immutable bit to the identity metadata.
It is an explicit operator action; ordinary workers must not be able to remove
the protection without the filesystem capability required by chattr -i. Git
refs, objects, the worktree index, and logs remain mutable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_WORKSPACE = Path("/home/lee/projects/linux-utilities-autonomous")
DEFAULT_REPOSITORY = Path("/home/lee/projects/linux-utilities")
DEFAULT_REMOTE = "git@github.com:leebase/linux-utilities.git"
DEFAULT_BRANCH = "refs/heads/main"
DEFAULT_HEAD_LINE = f"ref: {DEFAULT_BRANCH}"
REDIRECT_ENVIRONMENT = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_OBJECT_DIRECTORY_RELATIVE",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
)
DISPOSABLE_ROOTS = frozenset(
    {
        ".agent-orch",
        ".agent-orch-scratch",
        ".pytest_cache",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "tmp",
    }
)


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


class IdentityFailure(RuntimeError):
    """Raised when a repository identity invariant is not satisfied."""


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def _read_trimmed(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise IdentityFailure(f"cannot read {path}: {exc}") from exc


def _require_path(path: Path, kind: str) -> None:
    if path.is_symlink():
        raise IdentityFailure(f"{kind} must not be a symlink: {path}")
    if kind == "directory" and not path.is_dir():
        raise IdentityFailure(f"expected directory: {path}")
    if kind == "file" and not path.is_file():
        raise IdentityFailure(f"expected regular file: {path}")


def _expected_worktree_admin(repository: Path, workspace: Path) -> Path:
    return repository / ".git" / "worktrees" / workspace.name


def _static_checks(repository: Path, workspace: Path) -> list[Check]:
    repository = _resolved(repository)
    workspace = _resolved(workspace)
    checks: list[Check] = []

    def record(name: str, detail: str) -> None:
        checks.append(Check(name, True, detail))

    if not repository.is_dir():
        raise IdentityFailure(f"repository root is not a directory: {repository}")
    if not workspace.is_dir():
        raise IdentityFailure(f"governed workspace is not a directory: {workspace}")
    if repository == workspace:
        raise IdentityFailure("governed workspace must be a separate linked worktree")
    record("workspace-is-separate", f"workspace={workspace}")

    repository_git = repository / ".git"
    _require_path(repository_git, "directory")
    record("repository-git-directory", str(repository_git))

    workspace_git = workspace / ".git"
    _require_path(workspace_git, "file")
    admin = _expected_worktree_admin(repository, workspace)
    expected_gitfile = f"gitdir: {admin}\n"
    try:
        gitfile = workspace_git.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IdentityFailure(f"cannot read worktree .git file: {exc}") from exc
    if gitfile != expected_gitfile:
        raise IdentityFailure(
            f"worktree .git points to {gitfile!r}, expected {expected_gitfile!r}"
        )
    record("worktree-git-pointer", str(workspace_git))

    _require_path(admin, "directory")
    record("worktree-admin-directory", str(admin))
    commondir = admin / "commondir"
    gitdir = admin / "gitdir"
    head = admin / "HEAD"
    for path in (commondir, gitdir, head):
        _require_path(path, "file")

    if _read_trimmed(commondir) != "../..":
        raise IdentityFailure(f"unexpected worktree commondir: {commondir}")
    if _resolved(admin / "../..") != repository_git:
        raise IdentityFailure("worktree commondir does not resolve to repository .git")
    record("git-common-directory", str(repository_git))

    if _resolved(Path(_read_trimmed(gitdir))) != workspace_git:
        raise IdentityFailure("worktree gitdir does not resolve to workspace .git")
    record("worktree-gitdir", str(gitdir))

    head_value = _read_trimmed(head)
    if head_value != DEFAULT_HEAD_LINE:
        raise IdentityFailure(
            f"worktree HEAD is {head_value!r}, expected {DEFAULT_HEAD_LINE!r}"
        )
    record("worktree-head", DEFAULT_HEAD_LINE)

    repository_head = repository_git / "HEAD"
    _require_path(repository_head, "file")
    repository_head_value = _read_trimmed(repository_head)
    branch_prefix = "ref: refs/heads/"
    if not repository_head_value.startswith(branch_prefix):
        raise IdentityFailure(
            f"repository HEAD is not a local branch reference: {repository_head_value!r}"
        )
    branch_name = repository_head_value[len(branch_prefix) :]
    if not branch_name or branch_name.startswith("/") or ".." in branch_name:
        raise IdentityFailure("repository HEAD contains an unsafe branch reference")
    record("repository-head", repository_head_value)

    config = repository_git / "config"
    _require_path(config, "file")
    record("repository-config", str(config))
    return checks


def _sanitized_git_environment() -> dict[str, str]:
    redirected = sorted(name for name in REDIRECT_ENVIRONMENT if os.environ.get(name))
    if redirected:
        raise IdentityFailure(
            "Git redirect environment is set: " + ", ".join(redirected)
        )
    environment = os.environ.copy()
    for name in REDIRECT_ENVIRONMENT:
        environment.pop(name, None)
    return environment


def _git(workspace: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(workspace), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=_sanitized_git_environment(),
        )
    except OSError as exc:
        raise IdentityFailure(f"cannot execute git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise IdentityFailure(
            f"git {' '.join(arguments)} failed with {result.returncode}: {detail}"
        )
    return result.stdout.strip()


def _git_checks(repository: Path, workspace: Path) -> list[Check]:
    repository = _resolved(repository)
    workspace = _resolved(workspace)
    checks: list[Check] = []

    top_level = _resolved(Path(_git(workspace, "rev-parse", "--show-toplevel")))
    if top_level != workspace:
        raise IdentityFailure(f"Git top level is {top_level}, expected {workspace}")
    checks.append(Check("git-top-level", True, str(top_level)))

    git_dir = _resolved(Path(_git(workspace, "rev-parse", "--git-dir")))
    expected_admin = _expected_worktree_admin(repository, workspace)
    if git_dir != expected_admin:
        raise IdentityFailure(f"Git dir is {git_dir}, expected {expected_admin}")
    checks.append(Check("git-directory", True, str(git_dir)))

    common_dir = _resolved(Path(_git(workspace, "rev-parse", "--git-common-dir")))
    expected_common = repository / ".git"
    if common_dir != expected_common:
        raise IdentityFailure(
            f"Git common dir is {common_dir}, expected {expected_common}"
        )
    checks.append(Check("git-common-dir", True, str(common_dir)))

    git_head = _resolved(Path(_git(workspace, "rev-parse", "--git-path", "HEAD")))
    expected_head = expected_admin / "HEAD"
    if git_head != expected_head:
        raise IdentityFailure(f"Git HEAD path is {git_head}, expected {expected_head}")
    checks.append(Check("git-head-path", True, str(git_head)))

    if _git(workspace, "rev-parse", "--is-inside-work-tree") != "true":
        raise IdentityFailure("Git does not report a worktree")
    checks.append(Check("inside-worktree", True, "true"))

    branch = _git(workspace, "symbolic-ref", "HEAD")
    if branch != DEFAULT_BRANCH:
        raise IdentityFailure(
            f"symbolic HEAD is {branch!r}, expected {DEFAULT_BRANCH!r}"
        )
    checks.append(Check("symbolic-head", True, branch))

    remotes = _git(workspace, "remote").splitlines()
    if remotes != ["origin"]:
        raise IdentityFailure(f"unexpected Git remotes: {remotes!r}")
    remote_url = _git(workspace, "remote", "get-url", "origin")
    if remote_url != DEFAULT_REMOTE:
        raise IdentityFailure(
            f"origin URL is {remote_url!r}, expected {DEFAULT_REMOTE!r}"
        )
    checks.append(Check("origin-remote", True, remote_url))

    bare = _git(workspace, "config", "--local", "--get", "core.bare")
    if bare != "false":
        raise IdentityFailure(f"core.bare is {bare!r}, expected 'false'")
    checks.append(Check("non-bare-repository", True, bare))

    worktree = subprocess.run(
        [
            "git",
            "-C",
            os.fspath(workspace),
            "config",
            "--local",
            "--get",
            "core.worktree",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_sanitized_git_environment(),
    )
    if worktree.returncode == 0 and worktree.stdout.strip():
        raise IdentityFailure(
            f"unexpected core.worktree setting: {worktree.stdout.strip()!r}"
        )
    if worktree.returncode not in (0, 1):
        raise IdentityFailure(
            f"git config core.worktree failed with {worktree.returncode}: "
            f"{worktree.stderr.strip()}"
        )
    checks.append(Check("no-core-worktree-redirect", True, "unset"))
    return checks


def _nested_repository_checks(workspace: Path) -> list[Check]:
    workspace = _resolved(workspace)
    nested: list[Path] = []
    for directory, directories, files in os.walk(workspace, followlinks=False):
        current = Path(directory)
        if current != workspace and ".git" in directories:
            nested.append(current / ".git")
        if current == workspace:
            files = [name for name in files if name != ".git"]
        if ".git" in files:
            nested.append(current / ".git")
        directories[:] = [
            name
            for name in directories
            if name not in DISPOSABLE_ROOTS and name != ".git"
        ]
    if nested:
        raise IdentityFailure(
            "nested repository metadata found: "
            + ", ".join(os.fspath(path) for path in nested)
        )
    return [Check("no-nested-repository", True, "none in product tree")]


def verify(repository: Path, workspace: Path) -> list[Check]:
    """Return successful checks or raise IdentityFailure."""

    checks = _static_checks(repository, workspace)
    checks.extend(_git_checks(repository, workspace))
    checks.extend(_nested_repository_checks(workspace))
    return checks


def protected_paths(repository: Path, workspace: Path) -> tuple[Path, ...]:
    repository = _resolved(repository)
    workspace = _resolved(workspace)
    admin = _expected_worktree_admin(repository, workspace)
    return (
        workspace / ".git",
        repository / ".git" / "config",
        repository / ".git" / "HEAD",
        admin / "HEAD",
        admin / "commondir",
        admin / "gitdir",
    )


def _immutable(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["lsattr", "-d", "--", os.fspath(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    fields = result.stdout.split()
    return bool(fields) and "i" in fields[0]


def protect(repository: Path, workspace: Path, dry_run: bool = False) -> list[Path]:
    """Apply immutable protection to the exact identity metadata paths."""

    verify(repository, workspace)
    paths = protected_paths(repository, workspace)
    for path in paths:
        _require_path(path, "file")
    if dry_run:
        return list(paths)

    failures: list[str] = []
    for path in paths:
        result = subprocess.run(
            ["chattr", "+i", "--", os.fspath(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not _immutable(path):
            detail = result.stderr.strip() or "immutable bit not observed"
            failures.append(f"{path}: {detail}")
    if failures:
        raise IdentityFailure(
            "could not protect identity metadata: " + "; ".join(failures)
        )
    return list(paths)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=DEFAULT_REPOSITORY)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--protect", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --protect, list paths without changing attributes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.protect:
            paths = protect(arguments.repository, arguments.workspace, arguments.dry_run)
            checks = verify(arguments.repository, arguments.workspace)
            message = (
                "immutable protection verified"
                if not arguments.dry_run
                else "would protect"
            )
            payload = {
                "ok": True,
                "message": message,
                "paths": [os.fspath(path) for path in paths],
            }
        else:
            checks = verify(arguments.repository, arguments.workspace)
            payload = {"ok": True, "checks": [check.__dict__ for check in checks]}
        if arguments.as_json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print("repository identity: PASS")
            for check in checks:
                print(f"  {check.name}: {check.detail}")
            if arguments.protect:
                print(f"  {payload['message']}: {len(payload['paths'])} paths")
        return 0
    except IdentityFailure as exc:
        if arguments.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"repository identity: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
