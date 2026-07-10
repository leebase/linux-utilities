# Where Am I

## Milestone state

- Repository is initialized and committed on `main`.
- AgentFlow docs are present and should be read at session start.
- Agent-Orch scaffold and templates are present.
- Product baseline is intentionally tiny: `sysdiff --help` and `--version` plus
  a strict C build and smoke test, now with fixture-backed
  `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`.
- Run `fa24bb888cc0` produced the durable documentation contract for the first
  release-oriented `sysdiff compare` slice. The contract is
  explicit-snapshot-only and lives at
  `docs/sysdiff-snapshot-format-and-scope.md`.
- Run `3a9e56296af6` implemented the minimal C quality-gate harness and wired
  fixture-backed comparison tests into the smoke path.
- Run `b14e0191e257` delivered the core parser/comparer slice, resumed from
  source run `aa1eaef577cd`. It compares explicit snapshot files as
  bytewise-key-sorted `key=value` maps, keeps values opaque, validates key
  syntax, detects duplicate keys, rejects embedded NUL bytes, avoids partial
  stdout on parse errors, and reports deterministic added, removed, changed,
  and no-change output.
- Run `b6deb04a6055` delivered the routed tool-availability preflight for
  Agent-Orch worker infrastructure. Closeout validation and two Low review
  findings remain open.
- Run `5ff82aa95e06`, `sysdiff_fixture_smoke_repair`, completed closeout and
  resolved prior smoke-fixture F-001 Medium and F-002 Low findings.
- Run `c02d741432d3`, `sysdiff_c_source_implementation`, hardened resource
  limits and parse cleanup, passed smoke/review, and completed closeout.
- Run `c434e00a3772`, `craftsmanship_review_closeout`, completed the required C
  craftsmanship gate before further feature selection; verdict `pass` at
  High/Critical with Medium test/smoke findings that overlap the current
  fixture-acceptance backlog.
- The latest governed product slice is run `eab8bbd05f50`,
  `sysdiff_fixture_diff_acceptance_tests`. It authored fixture acceptance
  tests, verified fixture compare behavior in `src/sysdiff.c`, passed the
  pinned user smoke gate on attempt 1, and received a `pass` verdict at the
  High threshold in
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`.
- Fixture acceptance coverage now includes status 0/1/2, exact sorted stdout,
  ordering independence, comments/blank lines, CRLF equivalence, resource
  limits, and empty stdout on errors. Review also notes `argc < 1` is guarded
  and `make valgrind-test` cleans/rebuilds before Valgrind.
- The release-preparation verification on 2026-07-10 resolved the former
  F001–F004 findings and passed fresh Linux `make quality`. This is the release
  evidence, not the earlier smoke artifact with `start_exit_code: -15`.
- A later adversarial last-stop audit rejected that first candidate, found five
  additional Medium issues, and repaired them through Cursor/Grok coding plus
  independent planner review. Current protections include safe byte rendering,
  checked stdout/EPIPE behavior, a 16 MiB total snapshot cap, honest static and
  dynamic analysis failure semantics, and 41 governed tests.
- `sysdiff` v0.1.0 has Ubuntu CI and curated public release material. See
  `docs/RELEASE_REVIEW.md` for scope, evidence, and the accepted Low
  limitation.
- The publication follow-up adds a reviewed section-1 manual page at
  `man/sysdiff.1`. `make man-check` treats groff warnings as failures and is
  included in the canonical gate; post-integration `make quality` exited `0`.
- Lee approved the current diff output format on 2026-07-09:
  `+ key=value`, `- key=value`, and `~ key: old -> new`. Future OpenAI/Codex
  routes should use `gpt-5.5`; do not add GPT-5.4 assignments.

## Next milestone

The v0.1.0 local candidate is ready to be reseeded and pushed to the newly
authorized public repository. Require its first Ubuntu CI run to pass before
tagging or publishing the release. Keep every accepted Low limitation visible.
Internal Agent-Orch tool-availability findings remain outside the public seed.
