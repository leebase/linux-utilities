# Linux Utilities Mission Infrastructure Recovery

## Findings

The real checkout is currently a normal Git repository at
`/home/lee/projects/linux-utilities`, with `origin` set to
`git@github.com:leebase/linux-utilities.git`. The worker-facing checkout is a
linked worktree at `/home/lee/projects/linux-utilities-autonomous`; its
`.git` file resolves to the real repository's
`.git/worktrees/linux-utilities-autonomous`, and Git reports the expected
common directory. The new verifier passes 19 checks against this live layout.

The scratch-pruner was targeting
`/home/lee/projects/linux-utilities/.agent-orch-scratch`, which does not hold
the live worker spill. The live root was
`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch` and was
4.1 GB before cleanup. All six directories selected by the exact two-day
pruner had terminal run evidence in
`/home/lee/projects/linux-utilities-agent-orch-runs`; they were removed
without touching evidence. The live scratch root is now 2.2 GB and contains
only newer terminal run roots. The crontab now invokes the guarded pruner
against the autonomous root and logs its result; the autonomous loop entry
remains commented and paused.

Routing is not resolved. `config.yaml` selects the
`mixed-flagship` crew, whose governed mandate says Opus 5 produces and Sol
reviews. The mission charter separately mandates cursor/grok for production
and Claude/Opus 5 for review, and explicitly records the conflict. Recent
playbooks demonstrate both outcomes. The crew mandate emits primary, reviewer,
and judge instructions but no `user_tester` instruction, even though the
mission and AgentFlow require an independent `user_tester` on code-producing
playbooks. No routing policy was changed.

## Root causes

1. Repository identity was implicit in a writable linked-worktree pointer and
   shared Git administration files. A worker could potentially replace
   `.git`, alter worktree metadata, redirect Git environment variables, or
   change local remotes before a later Git-based check observed the result.
   The current checkout is not presently redirected; the risk is missing
   enforcement, not a current identity mismatch.

2. Scratch ownership changed when auto-orch moved to its split repository and
   the worker workspace moved to the autonomous linked worktree. The cron
   entry retained the old product-root path. Its `-mtime +2` policy also
   waited about three days in practice rather than enforcing an exact
   two-day boundary.

3. Routing has two natural-language mandatory sources and no deterministic
   authority for the governed role map. Auto-orch has a real precedence rule
   for config-level crew stage overrides, but its governed crew mandate is
   rendered into the author prompt alongside the mission text; that is not a
   precedence mechanism. The conflict therefore remains an author-prompt
   contradiction, and `user_tester` is absent from the crew mandate.

4. The latest run `9849a238752a` failed at the user smoke gate after the
   pinned smoke check timed out. Its evidence and the in-repository failure
   audit identify a shared smoke-budget problem: the smoke command runs the
   growing full suite under a 30-second check window. This is an
   agent-orch/auto-orch workflow issue, not a Linux utility defect to repair
   in this session.

## Code changes

- Added `scripts/check_repository_identity.py`, a fail-closed direct
  filesystem and sanitized-Git verifier for the linked worktree, common
  directory, HEAD paths, branch, remote, redirect environment, and nested
  repositories.
- Added its explicit operator `--protect` mode, which attempts immutable
  protection only for identity metadata and never offers an unprotect path.
  On this host `chattr +i` is not permitted, so no protection was claimed or
  left partially installed.
- Added `scripts/prune-agent-orch-scratch.sh`, with exact canonical paths,
  exact two-day retention, terminal-evidence checks, active/unknown retention,
  run-name validation, and a dry-run mode.
- Added focused tests and this recovery record. Updated `AGENTS.md` to the
  actual post-split auto-orch mission path.
- Corrected the user crontab's Linux Utilities pruner command only. No
  agent-orch or auto-orch repository files were changed, and autonomous
  scheduling was not enabled.

## Tests

- `python3 -m py_compile scripts/check_repository_identity.py
  tests/test_repository_identity.py`: passed.
- `python3 -m pytest -p no:cacheprovider
  tests/test_repository_identity.py -q`: 5 passed.
- `python3 scripts/check_repository_identity.py --json`: passed all 19 live
  identity checks.
- `python3 scripts/check_repository_identity.py --protect --dry-run --json`:
  passed and listed exactly six identity metadata paths.
- `bash -n scripts/prune-agent-orch-scratch.sh`: passed.
- `scripts/prune-agent-orch-scratch.sh --dry-run`: selected exactly the six
  terminal roots that were then removed; a post-cleanup dry run selected zero.
- The real smoke gate was not rerun because this recovery does not re-arm or
  launch autonomous work.

## Remaining risks

- The host does not grant the immutable filesystem capability, so structural
  metadata protection is not active. A trusted control-plane integration must
  either run with suitable filesystem protection or provide an equivalent
  worker-external guard before and after every attempt. A worker must not be
  allowed to rewrite the verifier and then use that same copy as authority.
- Routing still requires Lee's policy decision: choose the charter role map or
  the crew governed map, define precedence, and add an independent
  `user_tester` route to the authoritative representation. Until then,
  auto-orch author prompts can remain contradictory.
- The latest autonomous worktree is `main` four commits ahead of
  `origin/main`; its HEAD commit is an intentionally red, test-first
  openunlink slice with 17 known failures and missing documentation. It must
  not be treated as release-ready or as a clean re-arm baseline.
- The latest governed run failed the smoke gate, and the shared smoke budget
  remains an external workflow concern. The mission backlog still has eight
  active items, including a selected repair for `9849a238752a`; no new
  product work was manufactured here.
- The autonomous workspace is a linked worktree sharing common Git metadata.
  The verifier documents the current host paths and `main` branch as
  assumptions; a deliberate worktree or branch change requires a new
  identity policy.

## Recommendation

**Not ready.** Scratch cleanup is corrected and verified, and the repository
identity mismatch is currently absent, but identity protection could not be
installed on this host, routing authority is explicitly unresolved, the latest
governed run failed its smoke gate, and the live autonomous branch contains a
known-red test-first commit. Re-arm only after a trusted control-plane
identity guard/protection is in place, Lee selects one routing authority and
pins an independent `user_tester` route, and the autonomous workspace is
reset or otherwise explicitly accepted as the next governed baseline.
