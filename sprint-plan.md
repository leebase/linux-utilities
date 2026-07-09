# Sprint Plan

## Current sprint

- [x] Bootstrap a smokeable `sysdiff` workspace for auto-orch Author grounding.
- [x] Embed AgentFlow and Agent-Orch onboarding scaffold.
- [x] Run Agent-Orch doctor and resolve readiness findings.
- [ ] Finish closeout validation for Agent-Orch run `fa24bb888cc0` before
  installing hourly cron. Handoff docs record the completed snapshot-format
  contract, user smoke pass, review pass verdict, open findings, and next
  implementation step, but the Agent-Orch run ended `FAILED` at closeout due
  to the missing read-only judge adapter for `claude_code`.
- [x] Define and review the `sysdiff` snapshot-format and initial-scope
  contract for explicit `key=value` snapshot comparison.
- [ ] Resolve or encode snapshot-contract review findings F-001 through F-004.
- [x] Expand `sysdiff` with the smallest useful fixture-backed comparison slice
  against `docs/sysdiff-snapshot-format-and-scope.md`.
- [ ] Finish closeout validation for Agent-Orch run `3a9e56296af6`. Handoff
  docs record the minimal C quality-gate harness result, smoke pass, review
  pass verdict, and open findings F-01 through F-03; leave this open until
  Agent-Orch records the closeout step as passed.
- [ ] Resolve minimal C harness review findings F-01 through F-03 where still
  relevant. The changed-line ambiguity in F-01 remains open; the old dead
  `copy_range` guard and missing sanitizer target concerns have been reworked
  by later slices but should be reconciled against their original verdicts.
- [x] Deliver and review the sysdiff core parser/comparer slice. Resumed run
  `b14e0191e257` inherited implementation from `aa1eaef577cd`, passed the
  user smoke gate, and received a `pass` verdict at the High-severity threshold
  in `code-reviews/review-sysdiff-core.verdict.json`.
- [ ] Finish closeout validation for Agent-Orch run `b14e0191e257`. Handoff
  docs recorded the implemented core behavior, smoke evidence, review pass
  verdict, and open findings F001 through F004; leave this open until
  Agent-Orch records the closeout step as passed.
- [x] Resolve the implementation side of sysdiff core F001 by adding
  deterministic line-length and entry-count limits in run `c02d741432d3`.
  Follow-up tests are still required by the latest C-source review F001 before
  treating the acceptance coverage as complete.
- [x] Resolve the latest C-source memory-ownership and sanitizer availability
  concerns: `parse_snapshot` now uses explicit centralized cleanup, and
  `make sanitizer-test` provides ASan/UBSan coverage when `clang` is present.
  These are not open findings in
  `code-reviews/review-sysdiff-c-source.verdict.json`.
- [x] Deliver and review the routed tool-availability preflight. Run
  `b6deb04a6055`, `add-routed-tool-availability-check`, added
  `scripts/check_tools.py`, `tests/test_check_tools.py`, contract/plan/docs,
  and README discoverability for checking the default `codex_cli` and
  `claude_code` harness executables before governed work depends on those
  routes.
- [ ] Finish closeout validation for Agent-Orch run `b6deb04a6055`. Handoff
  docs record the implemented preflight behavior, review pass verdict,
  `flake8` environment limitation, and open Low findings F001 and F002; leave
  this open until Agent-Orch records the closeout step as passed.
- [ ] Resolve tool-availability review findings F001 and F002: guard or
  type-enforce available results before `_print_success` formats executable
  paths, and add explicit empty-stdout assertions to both per-harness
  partial-failure tests.
- [x] Deliver and review Agent-Orch run `1a9f7726ff33`,
  `fix_smoke_manifest_and_rebuild_fixture_tests`. Step 1 fixed
  `tests/smoke_manifest.json` and `tests/test_sysdiff_fixture.sh`; governed
  smoke passed on `step_02_run_smoke_gate` attempt 2 after attempt 1 retried for
  out-of-step AgentFlow doc edits; review verdict
  `code-reviews/review-smoke-fixture-fix.verdict.json` reports `pass` with no
  High or Critical findings.
- [x] Record closeout failure for Agent-Orch run `1a9f7726ff33`. Closeout
  attempts selected unavailable or inaccessible GPT-5.4 routing for semantic
  validation, so the run ended `FAILED` at `step_04_closeout_handoff_docs` and
  was superseded by follow-up run `5ff82aa95e06`. Future OpenAI/Codex routes
  should use `gpt-5.5`.
- [x] Resolve smoke-fixture review findings F-001 and F-002. Follow-up run
  `5ff82aa95e06` replaced the primary sorted diff comparison with an exact
  order-preserving comparison and strengthened `assert_diff_prefixes` to
  validate full diff line shapes.
- [x] Deliver, review, and close out Agent-Orch run `5ff82aa95e06`,
  `sysdiff_fixture_smoke_repair`. The user smoke gate passed on attempt 1 with
  four manifest steps completed; review verdict
  `code-reviews/review-fixture-smoke-repair.verdict.json` reports `pass` with
  no findings; closeout evidence records `COMPLETED`.
- [x] Deliver and review Agent-Orch run `c02d741432d3`,
  `sysdiff_c_source_implementation`. The run added the C-source contract and
  plan, implemented deterministic resource limits and explicit parse cleanup,
  added Makefile quality targets, documented user-visible limits, passed smoke,
  and received a `pass` verdict at the High threshold in
  `code-reviews/review-sysdiff-c-source.verdict.json`.
- [x] Finish closeout validation for Agent-Orch run `c02d741432d3`. Attempt 1
  of `step_09_closeout_handoff_docs` retried because the handoff did not match
  the current review verdict; attempt 2 preserved the current verdict details
  and Agent-Orch now records the run as `COMPLETED`.
- [ ] Resolve current C-source review finding F001 by adding tests for
  CRLF-vs-LF equivalence, line-too-long failure, and too-many-entries failure,
  with exit status `2`, empty stdout, and contextual diagnostics for the limit
  paths.
- [ ] Resolve current C-source review finding F002 by fixing or explicitly
  documenting the one-byte CRLF line-limit boundary discrepancy.
- [ ] Resolve current C-source review finding F003 by making standalone
  `make valgrind-test` robust after `make sanitizer-test`, or by documenting
  the invocation constraint clearly enough for the review gate.
- [ ] Complete a C craftsmanship review before selecting additional sysdiff
  feature work. Lee approved this as the next quality gate on 2026-07-09; the
  review must cover `src/sysdiff.c`, `Makefile`, tests, smoke manifest, and
  user-facing docs, with Medium-or-higher findings blocking new features.
