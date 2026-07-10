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
- [ ] Resolve minimal C harness review finding F-01 where still relevant. The
  changed-line ambiguity for values containing ` -> ` remains open; later
  slices reworked sanitizer/target concerns and should be reconciled against
  their original verdicts only as historical context.
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
- [x] Deliver fixture acceptance coverage for CRLF equivalence and
  line/entry resource-limit failures in run `eab8bbd05f50`. The latest
  fixture-acceptance review confirms those paths are exercised by
  `tests/test_sysdiff_fixture.sh` (entry-limit skipped under Valgrind for
  runtime).
- [x] Resolve the latest C-source memory-ownership and sanitizer availability
  concerns: `parse_snapshot` now uses explicit centralized cleanup, and
  `make sanitizer-test` provides ASan/UBSan coverage when `clang` is present.
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
- [x] Complete a C craftsmanship review before selecting additional sysdiff
  feature work. Agent-Orch run `c434e00a3772` wrote
  `code-reviews/craftsmanship-review.md` and
  `code-reviews/craftsmanship-review.verdict.json`; the verdict is `pass` at
  the High/Critical threshold with no High or Critical findings.
- [x] Add the Makefile `check` alias required by the quality-gate surface.
  `Makefile` now includes `check` in `.PHONY`, and `check` delegates to
  `test-suite`; `code-reviews/review-makefile-quality-gates.verdict.json`
  passed this narrow repair at the High threshold.
- [x] Deliver and review Agent-Orch run `eab8bbd05f50`,
  `sysdiff_fixture_diff_acceptance_tests`. Authored fixture acceptance tests,
  verified fixture compare behavior, passed its then-current user smoke (whose
  start helper timed out), and received a `pass`
  verdict at the High threshold in
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`.
- [x] Finish closeout validation for Agent-Orch run `eab8bbd05f50`; Agent-Orch
  records the run as `COMPLETED`.
- [x] Resolve fixture-acceptance review F001 by making the pytest `sysdiff_bin`
  fixture portable instead of hardcoding `gcc`; prefer `$CC`, `cc`, or
  `clang`, keeping the same strict C17 warning flags.
- [x] Resolve fixture-acceptance review F002 by making `tests/smoke_start.py`
  exit immediately with status 0, or by keeping any intentional delay strictly
  below `tests/smoke_manifest.json`'s 10-second `startup_timeout_seconds`.
- [x] Resolve fixture-acceptance review F003 by treating whitespace-only
  lines as blank (ignore them) to match the fixture-slice contract, or updating
  the contract and README to state that whitespace-only lines are parse errors.
- [x] Resolve fixture-acceptance review F004 by removing the unreachable
  `copy_range` `SIZE_MAX` guard or replacing it with a comment/static assertion
  that documents the call-site bound.
- [x] Confirm `argc < 1` guard is present in `main` before `argv[1]` access
  (noted by the fixture-acceptance review; supersedes craftsmanship F005 as
  current evidence).
- [x] Confirm standalone `make valgrind-test` cleans and rebuilds before
  Valgrind (noted by the fixture-acceptance review; supersedes the earlier
  Makefile/C-source Valgrind-after-sanitizer Medium as current evidence).
- [x] Prepare and verify the `sysdiff` v0.1.0 public release candidate: fresh
  Linux `make quality` pass, CI, curated release docs, and release review.
- [x] Perform an adversarial last-stop release audit; reject the first candidate
  and repair all five Medium findings with Cursor `grok-4.5-high` under
  independent planner review.
- [x] Add terminal-safe rendering, checked stdout/EPIPE behavior, a 16 MiB
  aggregate snapshot limit, honest Valgrind/cppcheck gates, leak-enabled ASan,
  immutable CI action pinning, and regression coverage.
- [ ] Create the public remote and require the first Ubuntu `make quality` CI
  run to pass before tagging or publishing v0.1.0.
- [x] Add and review `man/sysdiff.1`, integrate warning-gated groff rendering
  into `make quality`/Ubuntu CI, reconcile public docs, and pass the governed
  quality gate with 41 tests.
