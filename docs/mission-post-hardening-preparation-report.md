# Linux Utilities post-hardening commissioning preparation report

## Corrected Branch Posture

The interactive operator/preparation checkout is
`/home/lee/projects/linux-utilities` on branch `agent/public-utility-guides`
at `34e4a4ab9d226f169f5d4117d93170eede87054e`. The autonomous governed
workspace is `/home/lee/projects/linux-utilities-autonomous` on branch `main`
at `650ebebb4e06642397e5cc01a140fdb660a51c8c`. This is the intentional linked
worktree arrangement, and Agent-Orch's 19 repository-identity checks pass.

The prepared playbook remains in the interactive checkout and is supplied by
explicit path. It is not a mission-level launch input and is not copied into
the autonomous worktree. All ten producer inputs are present there.

Date: 2026-08-01  
Prior run: `e5e872615eed`  
Recommendation: **Ready after specific follow-up**

## Scope and control state

This session repaired the known baseline and prepared, but did not execute, the
next supervised commissioning cycle. No governed run was launched or resumed;
no re-arm, push, or production action occurred; no Agent-Orch route or timeout
was changed. The mission state remains halted/paused, but the host crontab
still contains an uncommented Linux Utilities loop line. Auto-orch's own
preflight rejects that mission with `value_exhausted: true`, so no cycle is
currently running; the residual active schedule is a governance blocker to
autonomous re-arm and was left unchanged under the user's no-cron-change rule.

## Governance follow-up

Before any autonomous re-arm, an authorized operator must either disable the
uncommented Linux Utilities cron line or explicitly reconcile why a halted
no-op schedule is retained. This session must not make that scheduling change.
The direct supervised commissioning packet is otherwise ready, but this
follow-up prevents the recommendation from claiming a cleanly disarmed
mission.

## Packet root cause and fix

The prior playbook declared `plans/mission-infrastructure-recovery-sprint.md`,
`docs/mission-infrastructure-recovery.md`,
`docs/repository-identity-protection.md`,
`scripts/check_repository_identity.py`, and
`scripts/prune-agent-orch-scratch.sh` as relative inputs. Those files existed
in the interactive hardening checkout but not in the configured autonomous
`main` worktree. The worker therefore spent its run recovering context and
reading unrelated history.

The next packet is now at
`/home/lee/projects/linux-utilities-autonomous/commissioning/`:

- `post-hardening-commissioning-packet.md` contains only the mission objective,
  repaired-baseline summary, acceptance criteria, allowed paths, outputs,
  validation commands, and referenced evidence.
- `post-hardening-commissioning-packet.json` declares ten exact inputs and the
  measured validation budgets.
- `check_packet.py` fails closed on a missing or unreadable packet input.
- `playbooks/post_hardening_commissioning_repaired.yaml` consumes this packet,
  retains explicit producer, independent `user_tester`, and read-only semantic
  judge routes, and keeps the worker ceiling at the existing 600 seconds.

Agent-Orch now performs the corresponding generic pre-worker check for every
declared input, while allowing a path that is the required output of an earlier
workflow step to be absent at launch. The regression test
`test_preflight_rejects_missing_declared_input_before_worker` passes. This is a
small reusable platform fix directly evidenced by the e5 failure; it does not
alter routing policy or filesystem access.

The packet checker, run from the autonomous worktree, reported:

```text
{"declared_inputs": 10, "missing": [], "ok": true, "unreadable": []}
```

The real configured orchestrator preflight for the prepared playbook returned
no findings without allocating a run or invoking a worker.

## Product repair slices

### Fixture expectation

The 15 direct failures shared `_zero_link_entry`'s hard-coded default
`size=3`, while callers supplied one-, two-, and four-byte link payloads and
expected the implementation's final `st_size` values. The source contract
defines `BYTES` as final `st_size`, so the source was not changed. The fixture
now derives its default size from `len(link)` and preserves explicit sizes for
boundary cases. The successful controls in the nine injector tests now reach
their intended injected failure paths.

### Documentation and contract

The two missing documentation/contract checks are complete without product
source changes. `docs/openunlink.md` and `man/openunlink.1` now document the
one-PID scope, final `st_nlink == 0` predicate, final `st_size` output, exact
`65536`/`65537` descriptor boundaries, statuses, and the NFS silly-rename
nonzero-link limitation. README and CHANGELOG identify the preview utility,
and the authority contract contains the exact numeric constants. The two new
product documentation files are included in the local preparation commit so
tracked-only distribution assembly includes them; the internal packet is
under `commissioning/`, outside the distribution pathspec.

## Validation evidence

Commands were run from `/home/lee/projects/linux-utilities-autonomous` unless
otherwise stated:

| Check | Result | Runtime |
| --- | --- | --- |
| `python3 -m pytest ... tests/test_openunlink.py -q` | 134 passed | 46.42s |
| `python3 -m pytest ... tests/ -q` | 548 passed, 18 skipped | 117.16s |
| isolated distribution extraction test | 1 passed | 60.12s |
| packet completeness checker | 10 inputs, no missing/unreadable | <0.1s |
| repository identity JSON | 19 checks passed | 0.058s |
| identity protection dry-run | six expected paths | 0.077s |
| scratch shell syntax and guarded dry-run | passed; one terminal old candidate listed, not removed | <0.01s |
| repaired playbook strict lint | no findings | 0.193s |
| `make man-check` | passed | 0.047s |
| Agent-Orch platform commissioning tests | 7 passed | 0.47s |
| `git diff --check` | passed | <0.01s |

The full suite's former distribution cascade disappeared after the new manual
and guide were included in the tracked archive input. No product source defect
was found, no test was weakened, and no failing test was suppressed.

## Repository status

At preparation closeout, autonomous `main` is clean at local commit
`650ebeb`, the manual-page lint closeout built on scheduler-blocker commit
`1fa6f03`, the earlier preparation commit `c829687`, and expected baseline
`15605e37312f7f7e710b12cd3eb3119793a21d92`. The
interactive
hardening checkout contains its intentional reports, shared-memory updates,
and prepared playbooks. The Agent-Orch checkout retains pre-existing local
hardening changes plus the small declared-input preflight patch and regression
test. No remote was contacted for publication.

## Recommendation

**Ready after specific follow-up.** The packet is complete in the autonomous
worktree; the repair baseline is green; the real configured preflight resolves
producer, independent `user_tester`, and semantic-judge availability; identity
and scratch checks pass; and the prepared playbook is strictly lint-clean. The
specific remaining blocker is the uncommented Linux Utilities cron entry,
which is currently prevented from starting by the halted mission state but is
not cleanly disarmed. Obtain authorized scheduling reconciliation before any
autonomous re-arm. This recommendation authorizes no execution; keep the
mission paused and do not restore cron, re-arm, or push.
