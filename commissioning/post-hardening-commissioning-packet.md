# Linux Utilities post-hardening commissioning packet

Packet ID: `linux-utilities-post-hardening-commissioning-2026-08-01-v2`

This is the complete task context for one future supervised commissioning
worker. Read this packet, `AGENTS.md`, the declared verifier inputs, and the
mission authority files listed in the manifest. Do not reconstruct context by
reading the repository's historical shared-memory files or Agent-Orch source.

## Mission objective

Verify that Linux Utilities is ready for one supervised post-hardening
commissioning cycle after the e5e872615eed timeout diagnosis and the bounded
openunlink baseline repairs. The mission must remain paused. This cycle is a
read-only commissioning report: do not repair product files, change routing,
change Agent-Orch, restore cron, re-arm the mission, push, or perform a
production action.

## Baseline and repair provenance

The configured autonomous worktree started at commit `15605e37312f7f7e710b12cd3eb3119793a21d92`.
The prior supervised run `e5e872615eed` reached `FAILED` after the Codex
worker exceeded 600 seconds. Its preserved evidence showed no worker edits,
passed repository identity snapshots, passed routing/provider preflight, a
verified evidence chain, and a paused mission. The worker's missing relative
inputs were `plans/mission-infrastructure-recovery-sprint.md`,
`docs/mission-infrastructure-recovery.md`,
`docs/repository-identity-protection.md`,
`scripts/check_repository_identity.py`, and
`scripts/prune-agent-orch-scratch.sh`; those recovery documents and scripts
belonged to the interactive hardening checkout, not this autonomous worktree.

Before this packet was prepared, the openunlink baseline was repaired in two
separate slices. The seam fixture now defaults its expected size to the link
payload length, which matches the implementation's final `st_size` output;
explicit sizes remain available for boundary cases. The documentation and
contract slice now includes the guide, section-1 manual, exact `65536` and
`65537` constants, and the required `st_nlink`/NFS silly-rename limitation.
No source behavior was changed to make the tests pass.

## Acceptance criteria

The report may recommend readiness only when all of the following are
evidenced in this run:

1. The autonomous worktree is the expected linked worktree, has trusted
   repository identity before and after the worker, and has no identity drift.
2. No Git metadata points into disposable scratch, the scratch root is the
   canonical root, and the guarded retention dry-run is safe.
3. Routing resolves deterministically; the producer, independent `user_tester`,
   and read-only semantic judge providers are available on their declared
   routes. Do not infer judge completion from preflight alone.
4. The mission remains paused for the entire commissioning cycle.
5. The focused openunlink suite, complete suite, distribution extraction test,
   and repository identity checks pass with exact commands and runtimes recorded.
6. The worker report, independent evaluator evidence, semantic review, identity
   snapshots, route decisions, validator outputs, and final evidence manifest
   form a verifiable chain with no divergence.
7. No unapproved workspace or remote change occurs. Do not push, restore cron,
   re-arm, or resume any prior run.

If any criterion is not proven, classify the failure precisely and recommend
`Not ready` or `Ready after specific follow-up` rather than inferring success.

The current operator evidence says the mission loop state is `idle` and the
mission is halted with `value_exhausted: true`; auto-orch preflight therefore
refuses to start a cycle. The host crontab still contains an uncommented
Linux Utilities loop line, even though its own preflight no-ops on the halted
state. Do not edit that schedule in this packet or run: record the discrepancy
as a governance blocker to autonomous re-arm and never describe the scheduler
as cleanly disarmed unless a separate authorized operator action proves it.

## Allowed paths and required outputs

The producing worker may write only `docs/mission-post-hardening-commissioning.md`.
The independent evaluator may write only
`artifacts/commissioning-evaluator/result.json`. Temporary notes belong in the
Agent-Orch scratch directory. The producing report must contain substantive
headings `Findings`, `Evidence`, `Local Verification`, `Route And Provider
Verification`, `Mission Pause`, `Failure Classification`, and
`Recommendation`, and must preserve the distinction between product defects,
provider/runtime failures, routing failures, governance failures, identity
failures, and scratch/runtime failures.

## Required validation commands

Run these commands from the autonomous workspace and record their real exit
codes and wall-clock runtimes. The timeout values in the prepared playbook are
based on the measured 117.75-second full-suite baseline and the bounded
distribution test; they do not raise the 600-second worker ceiling.

```text
PYTHONDONTWRITEBYTECODE=1 python3 commissioning/check_packet.py --workspace /home/lee/projects/linux-utilities-autonomous --manifest commissioning/post-hardening-commissioning-packet.json --json
PYTHONDONTWRITEBYTECODE=1 python3 /home/lee/projects/linux-utilities/scripts/check_repository_identity.py --workspace /home/lee/projects/linux-utilities-autonomous --json
PYTHONDONTWRITEBYTECODE=1 python3 /home/lee/projects/linux-utilities/scripts/check_repository_identity.py --workspace /home/lee/projects/linux-utilities-autonomous --protect --dry-run --json
bash -n /home/lee/projects/linux-utilities/scripts/prune-agent-orch-scratch.sh
/home/lee/projects/linux-utilities/scripts/prune-agent-orch-scratch.sh --dry-run
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_openunlink.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py::test_dist_extracts_builds_and_tests_outside_workspace -q
git diff --check
```

The playbook's system validators repeat the authoritative checks after the
worker. The first `launch-workflow` preflight must reject the run before worker
invocation if any declared input in the manifest is absent or unreadable.

## Referenced prior evidence

Prior commissioning evidence remains outside the workspace under
`/home/lee/projects/linux-utilities-agent-orch-runs/e5e872615eed/`; it is
historical context only and must not be treated as a current pass. The current
run must preserve its own identity snapshots, worker envelope, route decision,
validator evidence, independent evaluation, semantic-judge evidence, and final
manifest under the sibling runs root.

## Recommendation rule

Use exactly one recommendation: `Ready for supervised re-arm`, `Ready after
specific follow-up`, or `Not ready`. A green product baseline alone is not
enough. A product defect must remain distinct from a platform defect, and no
recommendation may authorize re-arm, cron restoration, or a push.
