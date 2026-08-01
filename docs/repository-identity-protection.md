# Repository Identity Protection

## Purpose

The Linux Utilities mission uses `/home/lee/projects/linux-utilities-autonomous`
as its worker-facing checkout. It is a linked Git worktree whose
`.git` file and common Git directory are under
`/home/lee/projects/linux-utilities/.git`; the sibling
`linux-utilities-agent-orch-runs` directory contains evidence and is not a Git
object store. A worker may change product files and Git refs, but it must not
silently change which repository those operations govern.

## Implemented protection

`scripts/check_repository_identity.py` first checks the filesystem metadata
directly and only then runs Git with redirecting `GIT_*` variables rejected. It
requires the expected linked-worktree `.git` pointer, `commondir`, `gitdir`,
worktree `HEAD`, repository common directory, local branch, `origin` URL, and
absence of nested `.git` metadata in the product tree. Disposable Agent-Orch
spill roots are excluded from the nested-repository scan because they are
explicitly outside the product tree.

An operator may run
`python3 scripts/check_repository_identity.py --protect`. After a successful
verification it applies the Linux immutable bit to only the identity metadata:
the worker `.git` pointer, repository `config` and `HEAD`, and worktree
`HEAD`, `commondir`, and `gitdir`. Git refs, objects, the index, and logs
remain writable for ordinary governed commits. Removing this protection
requires an explicit operator action with `chattr -i`; the script does not
offer an unprotect mode. Filesystems without a working immutable bit fail
closed rather than claiming protection.

This is intentionally tied to the current host layout and `main` worker
branch. Moving the worktree, changing the repository remote, or changing the
branch requires a new explicit identity policy and a fresh protection pass.

## Scratch cleanup

`scripts/prune-agent-orch-scratch.sh` is an exact-target, two-day-retention
pruner for
`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch`. It never
touches the sibling evidence root. It removes only old, 12-hex-digit run
directories whose evidence has a terminal status; missing or
active/approval-pending evidence is retained. Non-run names are retained and
reported. Use `--dry-run` before an operator-approved cleanup.

The live cron entry was corrected to invoke this script. Autonomous scheduling
itself remains paused; this cleanup does not launch or re-arm the mission.

## Limits and integration requirement

The verifier is a repository-local enforcement primitive, not a substitute for
the Agent-Orch platform's worker sandbox. A future re-arm should run it from a
trusted control context before launching a worker and again after each worker
attempt, with a failed result halting the run. The verifier and its tests live
in this checkout, so the control plane must pin or otherwise protect the
verifier itself; a worker must not be allowed to rewrite the verifier and then
ask the same workspace to trust it. No changes were made to agent-orch or
auto-orch for this reason.
