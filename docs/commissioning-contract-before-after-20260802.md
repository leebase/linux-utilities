# Commissioning contract migration: before and after

## Before

The final Linux Utilities playbook had an independent `user_tester` step, but
its evaluator contract used top-level booleans such as
`routing_verified` and `evidence_chain_verified`. The human approval step had
no readiness binding. The platform checker therefore refused the playbook
with two findings:

- the evaluator had no structural `readiness_report` rule; and
- the human gate had no `readiness_gate` binding.

Those omissions made a green evaluator step look like readiness and collapsed
missing evidence, contradictory evidence, and failed verification into the
same boolean value.

## After

The playbook now:

- declares the evaluator as `role: user_tester`;
- declares the mission, repository, routing, provider, packet, and platform
  contract inputs needed for its claims;
- consumes the platform-supplied seven-class evaluator evidence packet;
- requires a structural `readiness_report` with ten named criteria and the
  four platform readiness states;
- forbids boolean readiness fields in the evaluator instructions; and
- binds the human approval step's `readiness_gate` to the same report and the
  exact same ten criteria.

The migration changes only commissioning governance artifacts. It does not
change Linux Utilities product code, routing policy, providers, validator
authority, repository identity protection, scheduling, or remote state. No
governed run is launched as part of this migration.

## Validation record

The platform command used for the migration is:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/lee/projects/auto-orch/src \
python3 -m auto_orch.main check-commissioning \
  playbooks/final_supervised_commissioning_20260802.yaml
```

The command exited `0` with the platform message
`[OK] This playbook can produce an independently evidenced verdict.` The
prepared autonomous packet checker also exited `0`, reporting 16 declared
inputs and no missing or unreadable paths. YAML parsing, readiness/gate
criteria parity, and fail-closed negative checks for absent `readiness_report`
and `readiness_gate` passed. `git diff --check` passed. No governed run was
launched.
