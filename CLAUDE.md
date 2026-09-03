# Claude Code entry point

@AGENTS.md

`AGENTS.md` above is the shared operating doctrine for every harness and model that
works in this repo. This file adds only what Claude Code needs; it never overrides
`AGENTS.md`.

## AgentFlow, stated as outcomes

- **Before changing anything, know the current state** well enough to say what the next
  action is and why. That means `context.md` (state and autonomy mode), `result-review.md`
  (what just landed), `sprint-plan.md` (what is queued), and the guardrails in `AGENTS.md`.
  Load a file under `skills/` when its trigger applies, not up front.
- **Take whole sprint items, not fragments.** Plan the path yourself, verify as you go
  (tests, a real run, a diff read), and report what you verified rather than what you
  intended. Never claim a step passed without evidence.
- **Honor the autonomy mode set in `context.md`.** Mode 2 is the default: decisions get a
  check-in, routine code does not. Mode 3 means finish and report; ask only when blocked.
- **Leave the repo handoff-ready.** A different model or harness may pick up next. The
  session is not done until `context.md`, `sprint-plan.md`, and `result-review.md` (newest
  first), plus `WHERE_AM_I.md` at milestones, are accurate enough that the next agent starts
  with no blind spots.
- **Backlog items go to `backlog/candidates/` only.** Humans curate the other folders.
