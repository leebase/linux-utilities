# Linux Utilities final commissioning packet

Packet ID: `linux-utilities-final-commissioning-2026-08-02-v1`.

## Objective

Answer whether Linux Utilities is ready for controlled autonomous re-arm after
the Agent-Orch `f065cf3` and Auto-Orch `9d4db4c` production baseline. This is a
read-only supervised commissioning report. Do not repair product files,
change routing, modify either platform repository, restore cron, re-arm the
mission, push, approve or resume run `77fc787b8e91`, or launch another run.

## Current authority

The mission is held by the audited Auto-Orch pause record in the declared
`state.md`, with `supervised_commissioning: authorized`. The host crontab's
Linux Utilities loop entry is commented and must remain disabled. The pause is
the authoritative scheduling control; `loop_state: idle` is not itself a
pause. The external operator record for `77fc787b8e91` records that its sealed
evidence was superseded for this commissioning decision without approval,
resume, or mutation of that run directory.

The mission's `mixed-economy` crew is the routing authority. It mandates
`codex_cli/gpt-5.6-luna` for the primary producer,
`claude_code/claude-sonnet-5` for the independent user tester/reviewer, and
`claude_code` for the semantic judge. The playbook must resolve to those
routes. A route mismatch is a governance failure even if the workers are
otherwise available.

## Acceptance criteria

The report may recommend readiness only when every criterion below is proven
by this run's authoritative validator and evidence artifacts:

1. The autonomous workspace is the expected linked `main` worktree and its
   repository identity is unchanged before and after producer and validation.
2. Git metadata does not point into disposable scratch, the canonical scratch
   root is retained, and the guarded scratch-pruner dry-run is safe.
3. The current mission routing mandate and actual playbook routes agree; the
   producer, user tester, and semantic judge providers are ready on those
   declared routes. Provider readiness does not substitute for judge
   execution.
4. The audited pause remains active for the commissioning cycle, authorizes
   supervised commissioning, and autonomous scheduling remains disabled.
5. The focused openunlink suite, complete suite, distribution extraction test,
   packet completeness, identity checks, scratch checks, and diff check pass
   with exact commands and preserved validator output.
6. Producer, independent user tester, semantic judge, validator authority,
   route selection, identity snapshots, and the sealed evidence chain are all
   present and verifiable without divergence.
7. No unapproved workspace or remote change occurs. Readiness must not imply
   re-arm, cron restoration, approval of the old run, or a push.

If any criterion is missing or contradicted, use one of the allowed final
recommendations and name only the evidence-backed blockers. Worker narratives
are supporting evidence; validator authority, routing authority, and evidence
chain verification are authoritative.

## Required local checks

The producer may use only bounded inspection and report writing. The governed
system validators execute these commands independently and their preserved
records are authoritative for product validation:

```text
PYTHONDONTWRITEBYTECODE=1 python3 commissioning/check_packet.py --workspace /home/lee/projects/linux-utilities-autonomous --manifest commissioning/final-commissioning-packet-2026-08-02.json --json
PYTHONDONTWRITEBYTECODE=1 python3 commissioning/check_repository_expectations.py --workspace /home/lee/projects/linux-utilities-autonomous --agent-orch /home/lee/projects/agent-orch/.venv/bin/agent-orch --json
/home/lee/projects/agent-orch/.venv/bin/agent-orch scratch-clean --workspace /home/lee/projects/linux-utilities-autonomous --runs-dir /home/lee/projects/linux-utilities-agent-orch-runs --retention-days 2 --json
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_openunlink.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py::test_dist_extracts_builds_and_tests_outside_workspace -q
git diff --check
```

## Outputs and recommendation vocabulary

The producer writes only `docs/mission-post-hardening-final-commissioning.md`
with substantive headings `Findings`, `Evidence`, `Local Verification`,
`Route And Provider Verification`, `Mission Pause`, `Failure Classification`,
and `Recommendation`. The independent user tester writes only
`artifacts/final-commissioning-evaluator/result.json` as the platform readiness
report. It must contain a `readiness` object with exactly the playbook's
criteria and one state per criterion: `verified_true`, `verified_false`,
`not_evidenced`, or `verification_failed`. Every state has evidence text;
`not_evidenced` additionally names only unavailable evidence classes from the
platform-supplied evaluator packet. Do not emit boolean replacements for
readiness claims.

The criteria are `identity`, `scratch_retention`, `routing_authority`,
`runtime_route_execution`, `user_tester_route`, `semantic_judge_execution`,
`validator_authority`, `mission_pause`, `evidence_chain_verification`, and
`commissioning_contract`. The final recommendation must be exactly one of:
`Ready for autonomous re-arm`, `Ready for controlled pilot`, `Ready after
specific follow-up`, or `Not ready`. Do not claim readiness when any
acceptance criterion is unproven.
