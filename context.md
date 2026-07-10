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

The Linux release gate `make quality` passed after those repairs. It ran strict
GCC and Clang checks, clang-format, clang-tidy, cppcheck, shell fixtures,
pytest (26 passed), ASan, UBSan, and Valgrind. The public release candidate is
version `0.1.0`; its reviewed evidence and accepted Low limitation are in
`docs/RELEASE_REVIEW.md`.

Lee approved the current diff output format on 2026-07-09:
`+ key=value`, `- key=value`, and `~ key: old -> new`. Treat that as the
format-1 contract unless Lee explicitly changes it later. Preserve
explicit-snapshot-only scope and do not add live system capture,
package-manager integration, service probing, persistence, networking, or
background behavior in the next `sysdiff` slice.

## What's Happening Now

Do not claim that a GitHub release has been published: this work prepares only
the local v0.1.0 release candidate and a separate clean seed repository. The
remaining accepted product limitation is changed-line display ambiguity when a
value itself contains ` -> `; values are opaque and changed lines are not a
reversible data interchange format. Tool-availability follow-ups remain
internal infrastructure work and are not part of the public seed.

Runs root: `/home/lee/projects/linux-utilities-agent-orch-runs`.
