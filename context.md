# Context

## Snapshot

Mode: 2. This repository uses AgentFlow memory plus governed Agent-Orch
execution launched by the `linux-utilities` auto-orch mission. The current
product focus is a small, auditable C utility suite; the first utility is
`sysdiff`.

Release preparation completed on 2026-07-10. The governed fixture-acceptance
run `eab8bbd05f50` is `COMPLETED`, and its historical F001–F004 findings were
verified resolved in the release work: pytest selects `$CC` with `cc` fallback;
the smoke start helper exits immediately; whitespace-only space/tab lines are
ignored as blank; and the unreachable `copy_range` `SIZE_MAX` guard is gone.

The 2026-07-10 last-stop audit initially rejected publication with five Medium
findings: terminal injection, ignored stdout failures, an impractical aggregate
resource bound, dishonest Valgrind/cppcheck failure semantics, and stale public
documentation. Cursor `agent` with `grok-4.5-high` implemented bounded repairs
under independent planner review. The resulting Linux gate covers strict GCC
and Clang, clang-format, clang-tidy, gating cppcheck, 41 governed tests, ASan
with leak detection, UBSan, and Valgrind with a non-colliding error status.

The local public release candidate remains version `0.1.0`. Its current verdict,
repair record, evidence, and accepted Low limitations are in
`docs/RELEASE_REVIEW.md`.

Lee then authorized publication and requested a man page. Cursor
`grok-4.5-high` authored `man/sysdiff.1` under a bounded contract; planner review
added conventional OPTIONS/COMMANDS sections, exact consecutive-dot wording,
and a gate-bearing groff warning check. Governed `make quality` exited `0` with
41 tests after the man-page integration. The curated seed was pushed to the new
public repository `https://github.com/leebase/linux-utilities`. The first run
was cancelled after apt stalled; noninteractive installation fixed it. Run
`29119972847` then passed on commit `fbdf071` with checkout v6 and zero check-run
annotations.

Lee approved the current diff output format on 2026-07-09:
`+ key=value`, `- key=value`, and `~ key: old -> new`. Treat that as the
format-1 contract unless Lee explicitly changes it later. Preserve
explicit-snapshot-only scope and do not add live system capture,
package-manager integration, service probing, persistence, networking, or
background behavior in the next `sysdiff` slice.

## What's Happening Now

The public repository and Ubuntu CI are now live and green. No v0.1.0 tag or
GitHub release has been created; that remains a separate publication action.
Accepted
Low limitations are the changed-line delimiter ambiguity, Ubuntu-only CI,
source-first packaging without install/man targets, and explicit-snapshot-only
scope. Tool-availability follow-ups remain internal and outside the public seed.

Runs root: `/home/lee/projects/linux-utilities-agent-orch-runs`.
