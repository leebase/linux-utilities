"""Regression for governed run c847e01d15fe checksum-path failure.

Durable evidence (run.json / step_01 validation.json attempt-1/3/4):

    Command failed: sha256sum -c artifacts/release/SHA256SUMS
    sha256sum: sysdiff-source.tar.gz: No such file or directory

The playbook validated ``sha256sum -c`` from the workspace root while
``SHA256SUMS`` listed only the archive basename. The named path therefore
did not open. The durable producer fix is ``make release`` writing a
co-located basename checksum beside the archive so verification from the
archive directory succeeds.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ARCHIVE_REL = "sysdiff-release.tar.gz"
RELEASE_CHECKSUM_REL = "sysdiff-release.tar.gz.sha256"
RELEASE_ARCHIVE_DEFAULT = "artifacts/sysdiff-release.tar.gz"
RELEASE_CHECKSUM_DEFAULT = "artifacts/sysdiff-release.tar.gz.sha256"


def _temp_parent_outside_workspace() -> str:
    """Return a writable temp parent that is not under the governed workspace."""

    root = ROOT.resolve()
    candidates = []
    env_tmpdir = os.environ.get("TMPDIR")
    if env_tmpdir:
        candidates.append(env_tmpdir)
    default_tmp = tempfile.gettempdir()
    if default_tmp not in candidates:
        candidates.append(default_tmp)
    for fallback in ("/tmp", "/var/tmp"):
        if fallback not in candidates:
            candidates.append(fallback)

    for candidate in candidates:
        try:
            resolved = Path(candidate).resolve()
        except OSError:
            continue
        if resolved == root or resolved.is_relative_to(root):
            continue
        if resolved.is_dir() and os.access(resolved, os.W_OK | os.X_OK):
            return str(resolved)

    raise RuntimeError(
        "no writable temporary directory outside the governed workspace"
    )


def _require_git_worktree_root() -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != ROOT.resolve():
        pytest.skip(
            "make release regression requires the suite root to be a git work-tree root"
        )


def _run_make(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["make", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def test_c847e01d15fe_basename_only_checksum_fails_from_foreign_cwd(tmp_path):
    """Exact failure class: basename entry + verify from a different directory."""

    archive = tmp_path / "artifacts" / "release" / "sysdiff-source.tar.gz"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"sysdiff-release-payload\n")
    digest = subprocess.run(
        ["sha256sum", str(archive)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[0]

    # Reproduce the shipped SHA256SUMS shape from attempt-4 last_message:
    # "<digest>  sysdiff-source.tar.gz" (basename only).
    checksum = tmp_path / "artifacts" / "release" / "SHA256SUMS"
    checksum.write_text(f"{digest}  sysdiff-source.tar.gz\n", encoding="utf-8")

    # Playbook validation ran from the workspace-equivalent root, not from
    # artifacts/release/. The basename therefore does not open.
    foreign_root = tmp_path
    failed = subprocess.run(
        ["sha256sum", "-c", "artifacts/release/SHA256SUMS"],
        cwd=str(foreign_root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode != 0
    combined = failed.stderr + failed.stdout
    assert "sysdiff-source.tar.gz" in combined
    assert "No such file or directory" in combined or "FAILED" in combined

    # Same checksum verifies when cwd is the archive directory (co-location).
    ok = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS"],
        cwd=str(archive.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stderr + ok.stdout
    assert "sysdiff-source.tar.gz: OK" in ok.stdout


def test_c847e01d15fe_make_release_checksum_verifies_beside_archive():
    """Real producer seam: make release writes a basename checksum that verifies."""

    _require_git_worktree_root()
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert f"\nRELEASE_ARCHIVE := {RELEASE_ARCHIVE_DEFAULT}\n" in makefile
    assert f"\nRELEASE_CHECKSUM := {RELEASE_CHECKSUM_DEFAULT}\n" in makefile
    assert (
        '( CDPATH= cd -- "$$archive_dir" && sha256sum "$$archive_base" )' in makefile
    )

    outside = _temp_parent_outside_workspace()
    work = Path(tempfile.mkdtemp(prefix="sysdiff-c847-release.", dir=outside))
    archive = work / RELEASE_ARCHIVE_REL
    checksum = work / RELEASE_CHECKSUM_REL
    try:
        result = _run_make(
            f"RELEASE_ARCHIVE={archive}",
            f"RELEASE_CHECKSUM={checksum}",
            "release",
            check=False,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert archive.is_file(), result.stderr
        assert checksum.is_file(), result.stderr

        digest_line = checksum.read_text(encoding="utf-8").strip()
        assert digest_line.endswith(f"  {RELEASE_ARCHIVE_REL}"), digest_line
        named_path = digest_line.split(None, 1)[1]
        assert named_path == RELEASE_ARCHIVE_REL
        assert "/" not in named_path
        assert (work / named_path).is_file()

        # Co-located verification (the repaired contract).
        check = subprocess.run(
            ["sha256sum", "-c", RELEASE_CHECKSUM_REL],
            cwd=str(work),
            capture_output=True,
            text=True,
            check=False,
        )
        assert check.returncode == 0, check.stderr + check.stdout
        assert f"{RELEASE_ARCHIVE_REL}: OK" in check.stdout

        # Nested basename-only form still fails from a foreign cwd — the
        # original gate shape must not silently succeed against a missing path.
        foreign = Path(tempfile.mkdtemp(prefix="sysdiff-c847-foreign.", dir=outside))
        try:
            nested = foreign / "artifacts" / "release"
            nested.mkdir(parents=True)
            nested_checksum = nested / "SHA256SUMS"
            nested_checksum.write_text(
                f"{digest_line.split()[0]}  {RELEASE_ARCHIVE_REL}\n",
                encoding="utf-8",
            )
            bad = subprocess.run(
                ["sha256sum", "-c", "artifacts/release/SHA256SUMS"],
                cwd=str(foreign),
                capture_output=True,
                text=True,
                check=False,
            )
            assert bad.returncode != 0
            combined = bad.stderr + bad.stdout
            assert "No such file or directory" in combined or "FAILED" in combined
        finally:
            shutil.rmtree(foreign, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
