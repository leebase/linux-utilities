# Commissioning readiness report contract

The final commissioning evaluator emits the platform-defined readiness report
object. The report is the artifact the human gate decides on.

## Shape

```json
{
  "recommendation": "Not ready",
  "readiness": {
    "identity": {
      "state": "verified_true",
      "evidence": "repository identity snapshots and comparison passed"
    },
    "routing_authority": {
      "state": "not_evidenced",
      "evidence": "the route-selection record was not supplied",
      "required_evidence": ["route_selection"]
    }
  }
}
```

The playbook's structural `readiness_report` rule requires these criteria:

`identity`, `scratch_retention`, `routing_authority`,
`runtime_route_execution`, `user_tester_route`, `semantic_judge_execution`,
`validator_authority`, `mission_pause`, `evidence_chain_verification`, and
`commissioning_contract`.

Each criterion must occur exactly once in `readiness`. Each entry must contain
a non-empty `evidence` statement and exactly one of the platform states:

- `verified_true`: supplied evidence proves the criterion;
- `verified_false`: supplied evidence contradicts the criterion;
- `not_evidenced`: the required evidence was not supplied, with unavailable
  evidence classes named in `required_evidence`; or
- `verification_failed`: the check was attempted but could not complete.

Missing evidence is not a failure. Contradictory evidence is not a gap. An
attempted check that cannot complete is not a contradiction. Keep these states
separate so the repair and approval decision remain auditable.

The recommendation must be exactly one of:

- `Ready for autonomous re-arm`
- `Ready for controlled pilot`
- `Ready after specific follow-up`
- `Not ready`

Only the first two recommendations are approvable without an explicit
override, and approval additionally requires every gate criterion to be
`verified_true`. The conditional and negative recommendations block the human
gate by default.

The report must not contain boolean replacements such as
`routing_verified: false`. The `readiness_report` validator and the
`readiness_gate` enforce this contract at runtime; a successful evaluator step
means only that this report was well-formed and truthfully evaluated.
