# Migration notes for autonomous missions

Use this as the template when migrating an existing autonomous mission to the
platform commissioning contract.

## 1. Identify the independent judgement

Find the step whose output is a readiness, review, tester, or evaluator
verdict. Give it an explicit independent role, normally `role: user_tester`,
and provide a registered route under `roles:`. Keep its write scope limited to
the verdict artifact.

## 2. Declare every workspace input

List the report or artifact being judged, the mission charter/configuration and
state, routing authority, provider/crew authority, repository-identity and
scratch authority, packet/completeness checks, supersession records, and the
platform commissioning-contract documents that the evaluator actually reads.
Do not tell the evaluator to forage through a run directory.

The platform-generated `evaluator-evidence-packet.json` is the exception in
form but not in authority: it is explicitly handed to every independent
judgement step at runtime. Do not invent a pre-run workspace path for it or
declare a path that cannot exist before the attempt.

## 3. Replace booleans with the readiness report

Add one structural rule to the evaluator step:

```yaml
validation:
  structural:
    - type: readiness_report
      path: artifacts/evaluator/result.json
      criteria:
        - identity
        - routing_authority
        - runtime_route_execution
        - semantic_judge_execution
        - validator_authority
        - evidence_chain_verification
        - commissioning_contract
```

The criteria list is owned by the playbook, not by the evaluator. Every report
entry uses exactly `verified_true`, `verified_false`, `not_evidenced`, or
`verification_failed`, and every entry has evidence text. A `not_evidenced`
entry names only evidence classes that the supplied packet marks unavailable.

## 4. Cover the evidence classes

Use the platform names exactly: `route_selection`, `route_execution`,
`semantic_judge_execution`, `repository_identity`, `evidence_chain`,
`validator_authority`, and `commissioning_recommendation_contract`. Map each
readiness criterion to the classes that prove it. Do not treat provider
registration as proof that a semantic judge executed.

## 5. Bind human approval to the report

Add a gate after the evaluator and repeat the exact same path and criteria:

```yaml
type: human_approval
inputs:
  - artifacts/evaluator/result.json
readiness_gate:
  path: artifacts/evaluator/result.json
  criteria: [identity, routing_authority, runtime_route_execution]
```

The gate approves only an approvable recommendation with every criterion
`verified_true`. It must block `verified_false`, `not_evidenced`,
`verification_failed`, missing/unreadable reports, and conditional
recommendations unless the platform's explicit override path is used and
audited.

## 6. Validate before any launch

Run `check-commissioning` against the exact playbook path. It must exit zero.
Then run the mission's ordinary strict lint and packet/completeness checks as
appropriate. Do not use a green prior worker status as a readiness substitute.

## 7. Preserve the operating boundary

This migration does not alter product code, route policy, providers, validator
authority, repository identity controls, schedules, or remote state. It does
not launch, resume, approve, re-arm, or push. A later supervised commissioning
run is a separate authorization and must produce fresh evidence.

## Completion checklist

- [ ] independent evaluator role and route are explicit;
- [ ] every workspace input is declared;
- [ ] platform evidence packet is consumed as a governed handoff;
- [ ] booleans are replaced by the four readiness states;
- [ ] all readiness criteria are listed by the playbook;
- [ ] `readiness_report` is present and structurally validated;
- [ ] `readiness_gate` is present and repeats the same criteria;
- [ ] missing evidence remains `not_evidenced`, not failure;
- [ ] `check-commissioning` exits zero; and
- [ ] no governed run is launched during migration.
