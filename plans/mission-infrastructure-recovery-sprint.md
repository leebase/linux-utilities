# Mission Infrastructure Recovery Sprint

Date: 2026-08-01

Status: Active, with a deliberate not-ready outcome until the external
governance blockers are closed.

## Sprint goal

Leave Linux Utilities safe to re-arm only after repository identity is
structurally protected, the live scratch root is bounded, routing is
deterministic, and the autonomous smoke path has a successful governed run.
This sprint does not add a Linux utility, enable scheduling, re-arm the
mission, push changes, or modify agent-orch or auto-orch.

## Work tracks

### A. Repository identity protection — local evidence complete; platform closure blocked

Use `scripts/check_repository_identity.py` as the fail-closed preflight. It
checks the real checkout, linked-worktree metadata, Git environment redirects,
common directory, HEAD, remotes, and nested repositories while excluding
declared disposable roots. Keep `--protect` opt-in and report failure to
install immutable flags; a verifier alone cannot stop a worker that can rewrite
the metadata it verifies.

Acceptance: the preflight passes for the real and autonomous worktrees; a
redirected `GIT_DIR`, nested repository, unexpected remote, or changed common
directory fails; and the trusted launcher/control plane invokes the preflight
before worker execution. The last item requires platform ownership or explicit
operator authority and is not implemented locally.

### B. Scratch management — complete locally

Keep the exact live root at
`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch`, retain
terminal evidence for two days, skip active or unknown runs, and prune only
old, terminal, recognized run directories. The installed user cron must call
`scripts/prune-agent-orch-scratch.sh`; the autonomous mission loop remains
commented out.

Acceptance: the cron target names the live root, a dry run selects no current
artifacts after cleanup, and the removed directories have matching terminal
evidence under the sibling runs root. Do not broaden deletion or remove useful
evidence to reduce disk usage.

### C. Routing policy — blocked pending policy decision

Record the disagreement between mission.md's local role map and the
`mixed-flagship` crew definition. The current runtime gives config-level
workers/stages precedence for execution, while the crew mandate is separately
rendered into the author prompt; this is not a deterministic authority rule.
The crew definition also omits `user_tester`, while mission.md declares it.

Acceptance: an owner explicitly chooses the authoritative source and defines
precedence, then the chosen source is updated so primary, implementation,
review, and user_tester routes agree. Until that decision exists, do not edit
either routing source and do not claim readiness.

### D. Autonomous smoke and branch health — blocked on platform follow-up

Investigate the latest governed run's repeated `step_08_user_smoke_gate`
startup timeout (`app_started: true`, `core_flow_completed: false`,
`check_exit_code: -1`) in agent-orch/auto-orch ownership. Linux Utilities may
only preserve the evidence and avoid local workarounds. The autonomous branch
also contains a knowingly red openunlink test-first slice; it is not a release
baseline and must not be used as evidence for re-arm.

Acceptance: a fresh governed run completes smoke with exit 0 and a clean
review verdict, or the platform owner documents and fixes the root cause. No
schedule is enabled as part of this sprint.

### E. Closeout and clean checkout — execute last

Run the identity verifier, full local tests, shell syntax checks, playbook lint,
and `git diff --check`. Update the AgentFlow shared-memory files with the
evidence and blockers. Commit the intentional Linux Utilities recovery changes
as one bounded recovery commit so the checkout ends clean; do not discard
pre-existing user work or rewrite history.

## AgentFlow execution slice

The executable slice is a one-off, docs-only readiness validation generated
from the supported `docs_only` template and specialized as
`playbooks/mission_infrastructure_recovery_validation.yaml`. It may update
only the declared durable docs and must leave scripts, tests, source, mission
routing, and scheduling unchanged. It carries a human approval gate and a
read-only semantic closeout gate. The playbook is launched only after strict
lint passes; any parked approval remains a human decision.

## Exit gates

The sprint may be marked locally complete only when all local checks pass and
the checkout is clean. The mission remains `Not ready` if any of these are
unresolved: immutable identity enforcement at the trusted boundary,
deterministic routing with `user_tester`, or a successful current smoke run.
Those are platform/governance gates, not reasons to invent a local workaround.

## Recommendation

Not ready. Local identity detection and scratch cleanup are implemented and
verified, but detection is not structural enforcement, routing has no
unambiguous authority, and the latest autonomous smoke run failed twice. Re-arm
only after tracks A, C, and D have the acceptance evidence above.
