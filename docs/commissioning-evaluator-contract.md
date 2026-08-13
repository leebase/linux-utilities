# Linux Utilities commissioning evaluator contract

This document defines the evaluator boundary for the Linux Utilities
commissioning playbook. The evaluator is an independent `user_tester`; it is
not a second producer and its green step status means only that its artifact
passed structural validation.

## Declared workspace inputs

The evaluator step explicitly declares the facts it is allowed to use:

- the producer's commissioning report and the final commissioning packet;
- packet completeness and repository-identity/pruner authority scripts;
- the Linux Utilities mission configuration, mission charter, state, and
  selected crew configuration;
- the preserved supersession record for the historical run; and
- the platform and Auto-Orch commissioning-contract documents.

The platform also hands the evaluator an
`evaluator-evidence-packet.json`. This is a governed step handoff, not an
implicit filesystem artifact: the evaluator reads the packet path supplied in
its step context and must not search the run directory for substitutes. The
platform deliberately does not require this generated packet to be listed as a
workspace `inputs` path because it does not exist until the evaluator attempt
is built. The playbook's explicit authority inputs and the platform handoff
together are the complete evaluator contract.

## Evidence classes

The packet contains every class below, with `provided`, `not_available`, or
`not_applicable` and a reason:

| Class | Governing question |
| --- | --- |
| `route_selection` | Which route did the routing authority select? |
| `route_execution` | Which route actually executed each attempt? |
| `semantic_judge_execution` | Did the semantic judge execute and what did it return? |
| `repository_identity` | Did repository identity remain unchanged? |
| `evidence_chain` | Does the sealed evidence chain verify without divergence? |
| `validator_authority` | Which independent validator records are authoritative? |
| `commissioning_recommendation_contract` | Which readiness states and recommendations are legal? |

Every readiness entry carries an evidence statement. A
`not_evidenced` entry also names `required_evidence`; each named class must be
unavailable in the supplied packet. A supplied class must be read and cannot
be reported as missing merely because its artifact is inconvenient to find.

## Authority rules

Validator records are authoritative for commands they independently ran.
Route-selection and route-execution records are authoritative for route facts.
Repository identity and evidence-chain records are authoritative for their
respective integrity claims. Worker prose can explain those records but cannot
replace them. Provider registration is not semantic-judge execution, and a
passed evaluator validator is not a readiness decision.

The evaluator writes only
`artifacts/final-commissioning-evaluator/result.json`. It does not modify
product files, tests, scripts, packets, routing, schedules, either platform,
or remote state.
