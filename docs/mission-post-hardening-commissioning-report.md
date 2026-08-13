# Linux Utilities Post-Hardening Commissioning Report

## Corrected Branch Posture

The earlier read-only commissioning note reversed the branch labels. The
authoritative linked-worktree arrangement is the interactive operator and
preparation checkout at `/home/lee/projects/linux-utilities`, branch
`agent/public-utility-guides`, HEAD `34e4a4ab9d226f169f5d4117d93170eede87054e`,
and the autonomous governed workspace at
`/home/lee/projects/linux-utilities-autonomous`, branch `main`, HEAD
`650ebebb4e06642397e5cc01a140fdb660a51c8c`.

Agent-Orch's 19 repository-identity checks consider this linked-worktree
arrangement valid. The prepared commissioning playbook is intentionally
supplied explicitly from the interactive checkout; it is not a mission-level
`launch_inputs` declaration and is not copied into the autonomous worktree.
The autonomous workspace contains all ten producer inputs.

Date: 2026-08-01  
Recommendation: **Not ready**

## Scope And Run

Exactly one supervised governed run was launched through the real
`launch-workflow --detach` path using the configured mission worktree
`/home/lee/projects/linux-utilities-autonomous`. No GitHub push, cron re-arm,
mission re-arm, routing change, or Agent-Orch redesign was performed.

Run ID: `e5e872615eed`  
Status: `FAILED`  
Playbook: `playbooks/post_hardening_commissioning.yaml`  
Evidence root: `/home/lee/projects/linux-utilities-agent-orch-runs/e5e872615eed`

The run reached a real terminal result after one allowed attempt. Step
`step_01_commission_platform` halted. The independent `user_tester` step and
human approval step were not reached; this run was not resumed.

## Repository Identity

The interactive checkout was clean before commissioning at commit
`34e4a4ab9d226f169f5d4117d93170eede87054e` on
`agent/public-utility-guides` (ahead of its remote by one commit). The actual
mission worktree was clean before launch at
`15605e37312f7f7e710b12cd3eb3119793a21d92` on `main` (ahead of `origin/main`
by four commits). Its configured origin remained
`git@github.com:leebase/linux-utilities.git`.

The repository-specific verifier passed all 19 checks for the linked worktree:
the expected `.git` pointer, common Git directory, worktree administration,
HEADs, remote, sanitized Git environment, and absence of product-tree nested
repositories. The generic commissioning report marks the linked worktree's
root `.git` pointer as nested metadata; that is a tool limitation for this
linked-worktree layout, not a detected identity drift. The verifier's
protection dry-run listed the six expected identity paths. No immutable bit was
claimed; the host limitation recorded by the recovery evidence remains open.

The governed attempt preserved all five identity artifacts:

- `repository-identity-before.json`
- `repository-identity-after-worker.json`
- `repository-identity-after-worker-check.json`
- `repository-identity-after-step.json`
- `repository-identity-check.json`

Both identity comparisons report `passed: true` with an empty differences list.
The worker reported `changed_files: []`; no Git metadata pointed into the
disposable scratch root, and no repository-identity failure occurred.

## Scratch And Retention

The canonical live scratch root is
`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch`. The
guarded two-day pruner removed exactly one old, terminal, evidence-backed spill
root (`5035933ac7b4`) and retained the sibling run evidence. A post-clean dry
run selected zero candidates. During this commissioning run scratch grew by
approximately 135 MB to 1,624,592,044 bytes, remaining below the platform's
10 GiB commissioning ceiling; the final guarded retention dry-run selected zero
candidates. Scratch/runtime lifecycle therefore passed, with the new run spill
retained as active commissioning evidence.

## Route And Provider Verification

The strict playbook lint passed with no findings. The platform's deterministic
routing authority was recorded as:

`step.role` → `step.routing` → `playbook.defaults.routing` →
`step.execution.routing_hints` → `playbook.defaults.execution.routing_hints` →
`step.worker` → `playbook.defaults.worker` → `platform.router`.

Mandatory conflicts are rejected rather than resolved by load order. The
commissioning playbook's producing route resolved to `codex_cli` with model
`gpt-5.6-sol`. Its top-level `user_tester` role has an explicit independent
`claude_code` / `claude-opus-5` route. The read-only semantic judge route is
explicitly `pi_cli`; preflight found its provider adapter and executable
available. These preflight checks passed, and the route-selection artifact
records the selected route and authority.

The semantic judge was not reached at runtime because the producing worker
timed out before its report artifact existed. Therefore provider preflight is
positive evidence of registration and executable availability, not evidence of
a completed semantic-judge response. Separately, the real Auto-Orch mission
configuration still contains the documented charter-versus-`mixed-flagship`
governed-route conflict, and that crew definition still omits `user_tester`.
That mission-level authority decision remains a governance blocker even though
this explicit commissioning playbook resolved its own routes deterministically.

## Mission Pause And Change Control

The Linux Utilities autonomous loop remains paused: its crontab loop entry is
commented, mission state is idle/halted, and only the guarded scratch-pruner
entry is active. No scheduling or re-arm command was run. The autonomous
worktree remained clean after the run; the only intentional interactive
checkout additions are this report and the generated commissioning playbook.
The remote was not contacted for a push.

## Failure Classification

The primary governed failure is a **provider/runtime failure**: the selected
Codex worker route started, then exceeded the 600-second worker timeout and
returned exit code 124 without creating the required report. Worker metadata
also recorded a `worker_binary_resolution` classification after matching a
`no such file or directory` signature; because the configured Codex process did
start and run, that metadata is retained as diagnostic evidence rather than
reclassified as a routing failure. Follow-up should make the Codex binary and
provider path reliably complete a bounded commissioning prompt.

The full pytest validator independently recorded a **product failure**:
18 failed, 529 passed, and 19 skipped. The failures are concentrated in the
known red, test-first `openunlink` slice and its missing documentation/contract
artifacts, including the distribution extraction test. They are not evidence
that the Linux Utilities identity guard or Agent-Orch evidence chain failed.

There was no evidenced routing failure, repository-identity failure,
scratch-retention failure, or evidence-chain divergence. Governance is still
not ready at the mission level because the real charter/crew route authority is
unresolved and the run did not reach its user-tester or semantic-judge gates.

## Evidence Chain

`agent-orch verify-run-evidence` verified the run with 3 manifest entries and
17 artifacts, with no first divergence. The preserved run directory contains
the launch report, playbook snapshot, route request/response and selection,
worker envelope, policy decision, all identity snapshots/checks, validation
evidence, progress/dashboard artifacts, and sealed manifest. The final
commissioning JSON reports are preserved under
`/home/lee/projects/linux-utilities-agent-orch-runs/commissioning-20260801T185539Z/`.

## Recommendation

**Not ready.** The post-hardening identity snapshots, fail-closed comparisons,
deterministic playbook routing, provider preflight, scratch retention, paused
mission state, and evidence-chain verification all behaved as intended. The
mission nevertheless lacks the required successful governed commissioning
result: the producing provider timed out, the semantic judge was not exercised,
the mission's real charter/crew routing authority remains unresolved, and the
configured mission baseline is product-red. Reconsider supervised re-arm only
after the Codex/provider timeout is resolved, the real mission route authority
includes an explicit independent `user_tester`, the semantic judge completes
once, and the autonomous baseline is either repaired and reviewed or explicitly
replaced with an approved clean commit.
