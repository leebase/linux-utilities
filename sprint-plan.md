# Sprint Plan

## pathaudit Vertical-Slice Bootstrap

Governed run `4dec475ef201` (playbook
`pathaudit_bootstrap_deterministic_scanner`) delivered the additive
`pathaudit` 0.1.0 vertical slice: contract, C17 scanner, man page,
26-test suite, Makefile wiring, and README/QUALITY/TESTING docs. Exact
verification: step-3 `pytest tests/test_pathaudit.py` → 26 passed in
0.38s; full `pytest tests/` → 158 passed in 14.98s (132 prior + 26);
GCC/Clang strict syntax, clang-format, clang-tidy, cppcheck, Clang
analyzer, ASan/Valgrind help probes exited 0. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `158 passed in 12.88s`). The
sysdiff smoke oracle does **not** directly exercise pathaudit. Review
`code-reviews/review-pathaudit-bootstrap.{md,verdict.json}` verdict
`pass` (0 Critical/High, 2 Medium PA-M1/PA-M2, 7 Low PA-L1–PA-L7). Do
**not** claim that `pathaudit` is released. Next: repair PA-M2 and
finish PA-M1 leftovers (CHANGELOG + architecture.md); keep Low visible.

## Prepared Unpublished sysdiff 0.1.0 Release Candidate

Governed run `580b0f6ff811` (playbook
`prepare_sysdiff_release_package_and_notes`) prepared an unpublished
`sysdiff` **0.1.0** release candidate via `make release`. Archive:
`sysdiff-release.tar.gz`; checksum: `sysdiff-release.tar.gz.sha256`
(digest
`9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f`).
RC-001 pass (`pytest -k rc_001` → 2 passed). Clean extraction `/tmp`
`make clean test` → 121 passed, 7 skipped. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `128 passed in 10.64s`).
Review `code-reviews/review-sysdiff-release.{md,verdict.json}` verdict
`pass` (0 Critical/High, 1 Low L1). Step-3 attempt 1 failed on High H1;
repair then attempt 2 passed. Do **not** claim that a release was
published. Next authorized action: await Lee-controlled release
authorization; keep L1 and prior Medium backlogs visible; do not modify
package inputs after the reviewed archive.

## First Independent sysdiff Release-Candidate Review

Governed run `6d0a6fbfe83d` (playbook
`template_repair_before_review_feature_delivery`) recorded the first
independent `sysdiff` release-candidate review. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`127 passed in 10.75s`). Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` → exit 0,
`127 passed in 10.89s` at HEAD `510fa2d`. Review
`code-reviews/review-first-sysdiff-release-candidate.{md,verdict.json}` verdict
`pass` with 0 Medium/High/Critical and 10 Low (L1–L10). Step-2 attempt 1
failed on Medium M1 (quality-floor provenance); attempt 2 held it at Low L1
and passed. Consecutive clean RC reviews in this required sequence: **1**.
The second consecutive clean review remains outstanding. Do not claim that
`sysdiff` is released; prior Medium backlogs remain open and continue to
prohibit new feature work while Medium-or-higher debt remains.

## Second Independent Release-Candidate Review Cycle

Governed run `c84986cf0c81` (playbook
`sysdiff_second_independent_release_candidate_review_cycle`) recorded a prior
independent release-candidate review cycle. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`127 passed in 10.84s`). Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` → exit 0,
`127 passed in 10.96s`. Review
`code-reviews/sysdiff-rc-second-independent-cycle.{md,verdict.json}` verdict
`pass` under Medium with 0 Medium/High/Critical and 9 Low (L1–L9). RC-001
strcasecmp-mutant kill re-verified. That earlier AgentFlow claim of consecutive
clean RC cycles = 2 is historical; the current mission sequence after run
`6d0a6fbfe83d` treats the required consecutive clean counter as 1 with the
second still outstanding. Do not claim that `sysdiff` is released from either
pass alone; prior Medium backlogs remain separately open.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` (playbook
`sysdiff_first_independent_rc_review_cycle`) recorded a prior first
independent release-candidate review cycle. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`127 passed in 10.58s`). Exact review check:
`python3 -m pytest tests/ -q` → exit 0, `127 passed in 11.06s`. Review
`code-reviews/sysdiff-rc-review-cycle-1.{md,verdict.json}` verdict `pass` with
0 Medium/High/Critical and 7 Low (F1–F7) preserved. Historical relative to the
current mission sequence anchored by run `6d0a6fbfe83d`. Do not claim that
`sysdiff` is released or that the mission is complete; a second consecutive
review cycle with no release-blocking findings is still required. Prior Medium
backlogs remain separately open.

## First Consecutive Release-Blocking Independent Review

Governed run `7eb4e29dee6e` (playbook
`complete_first_consecutive_release_blocking_independent_review`) recorded the
first consecutive clean release-blocking independent review. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`124 passed in 10.23s`). Exact full suite: `python3 -m pytest tests/ -q` →
exit 0, `124 passed in 10.71s`. Review
`code-reviews/sysdiff-independent-review-1.{md,verdict.json}` verdict `pass`
with 0 Medium/High/Critical and 5 Low (L-1–L-5) preserved. Do not claim a
second clean review, mission completion, or release readiness from this first
consecutive clean pass; prior Medium backlogs remain separately open.

## Reproducible Source Archive — Isolated Build Verification

Governed run `939ee21b0d76` (playbook
`verify_reproducible_source_archive_isolated_build`) completed isolated
`make dist` verification and extracted-tree quality exercise. Exact archive
identity at `SOURCE_DATE_EPOCH=946684800`: 89851 bytes; SHA-256
`5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544` (both
builds; basename-only checksum matching); 44 members; empty member diff.
Extracted-tree gates all exit 0 (including ASan/UBSan/Valgrind at 118
passed / 6 skipped); install/uninstall 2→0 files. Smoke passed
(`artifacts/user-smoke/result.json` start/check 0). Review verdict `pass`
with 0 High/Critical, 5 Medium (F1–F5), 4 Low (F6–F9); allowlisted
`python3 -m pytest tests/ -q` → 124 passed in 10.71 s. Closeout handoff
recorded; next is repair F1–F5. Do not claim `.deb`/`.rpm`, commit-identical
dirty-tree archives, or full release closure.

## Reproducible sysdiff Source Release (`make dist` / `make distcheck`)

Governed run `240bfcbc634e` delivered conventional reproducible source
packaging (`make dist` / `make distcheck`; artifacts
`dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256` with
digest `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a`;
six `test_dist_*` regressions; README "Source releases"). Exact verification:
`python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py -q` → 38 passed
in 5.80 s (impl) / ~5.8 s (review); `make clean && make test` → 0;
`make dist && make distcheck` → 0; Clang `-fsyntax-only` → 0. User smoke
passed (`artifacts/user-smoke/result.json` start/check 0). Review verdict
`pass` with 0 High/Critical, 5 Medium (F1–F5), 5 Low (F6–F10). Closeout
handoff recorded; next is repair F1–F5. Do not claim `.deb`/`.rpm`,
commit-identical dirty-tree archives, `make quality`, or release closure.
Prior run `b54d61531266` (`source-release` naming) is superseded by this
`dist`/`distcheck` workflow.

## Deterministic sysdiff Performance Benchmarks

Governed run `a0eda97cd039` delivered the Linux performance/resource harness
(`scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`,
`make benchmark`, README section, committed
`artifacts/performance/sysdiff-benchmark.json`). Exact evidence:
`startup_ms_median` 1.2422580039128661 <= 200.0;
`fixture_ms_median` 7.362931006355211 <= 100.0;
`peak_rss_kib` 2540.0 <= 32768.0; `baseline_ms_median` 1.3354689872357994;
8000-entry fixture; `passed: true`. Exact verification: pytest 25 passed in
1.73 s (repair) / 1.62 s (review); `make -n benchmark` → 0; harness
`--output` → 0. User smoke passed (`artifacts/user-smoke/result.json`
start/check 0). Review verdict `pass` with 0 High/Critical/Medium, 9 Low
(B1–B9). Closeout handoff recorded; optional Low B1–B9 polish remains. Do
not claim microbenchmarks, cross-host bit-stable timings, `make quality`, or
release closure.

## Deterministic Malformed-Snapshot Fuzz Regression Coverage

Governed run `feb8e707ea28` delivered the deterministic malformed-snapshot fuzz
regression contract and pytest corpus (`docs/malformed-snapshot-fuzz-regression-
contract.md`, `tests/test_sysdiff_malformed_fuzz.py`). Exact verification:
`python3 -m pytest tests/test_sysdiff_malformed_fuzz.py -q` → 40 passed in
0.18 s (impl) / 0.19 s (review); `clang -std=c17 -Wall -Wextra -Wpedantic
-Werror -fsyntax-only src/sysdiff.c` → exit 0. User smoke passed
(`artifacts/user-smoke/result.json` start/check 0). Review verdict `pass` at
High with 0 High/Critical, 4 Medium (F1–F4), 3 Low (F5–F7). Finish closeout,
then repair F1–F4; do not claim open-ended fuzzing, sanitizer product readiness,
or release closure from this slice.

## Current sprint

- [x] Deliver, smoke-test, independently review, and close out the additive
  `pathaudit` 0.1.0 vertical slice in run `4dec475ef201`,
  `pathaudit_bootstrap_deterministic_scanner`. Deliverables:
  `docs/pathaudit-contract.md`, `src/pathaudit.c`, `man/pathaudit.1`,
  `tests/test_pathaudit.py` (26 passed), Makefile quality/sanitizer/
  Valgrind wiring, README/QUALITY/TESTING docs. Exact evidence: step-3
  pathaudit pytest 26/0.38s; full pytest 158/14.98s; GCC/Clang strict
  syntax + format/tidy/cppcheck/analyzer + ASan/Valgrind help probes
  exit 0; smoke start/check 0 with empty `blocking_errors` (check.log
  pytest `158 passed in 12.88s`); review verdict `pass` with 0
  Critical/High, 2 Medium (PA-M1, PA-M2), 7 Low (PA-L1–PA-L7). Not a
  pathaudit release; sysdiff smoke oracle does not directly exercise
  pathaudit.
- [ ] Next after `4dec475ef201`: repair Medium PA-M2 (hostile-byte stderr
  diagnostic fixture) and finish PA-M1 leftovers (CHANGELOG Unreleased
  entry + architecture.md FindingBuffer ownership); keep Low PA-L1–PA-L7
  visible; do not claim that `pathaudit` is released or that
  `tests/smoke_manifest.json` covers pathaudit.
- [x] Prepare, verify, smoke-test, and independently review the unpublished
  `sysdiff` **0.1.0** release candidate in run `580b0f6ff811`,
  `prepare_sysdiff_release_package_and_notes`. Archive
  `sysdiff-release.tar.gz` + checksum `sysdiff-release.tar.gz.sha256`
  (digest
  `9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f`);
  RC-001 pass; clean extract 121 passed / 7 skipped; smoke start/check 0
  with empty `blocking_errors` (check.log pytest `128 passed in 10.64s`);
  review verdict `pass` with 0 Critical/High and 1 Low (L1). H1 packaging
  guard repaired between review attempts. This is a prepared but
  **unpublished** candidate—not a published release.
- [ ] Keep Lee-controlled release authorization as the gate for any
  external `sysdiff` publication or tag push; keep Low L1 visible; do not
  modify release-package inputs after the reviewed archive; prior Medium
  backlogs remain open. Do not claim that `sysdiff` is released.
- [x] Deliver and record the first independent `sysdiff` release-candidate
  review in run `6d0a6fbfe83d`,
  `template_repair_before_review_feature_delivery`. Exact smoke start/check 0
  with empty `blocking_errors` (check.log pytest `127 passed in 10.75s`);
  review check `python3 -m pytest -p no:cacheprovider tests/ -q` → 127 passed
  in 10.89 s at HEAD `510fa2d`; verdict `pass` with 0 Medium/High/Critical
  and 10 Low (L1–L10). Step-2 attempt 1 failed on Medium M1; attempt 2 passed.
  This is the first clean review in the required consecutive sequence only—
  not a release, not mission completion.
- [ ] Keep Low findings L1–L10 visible after run `6d0a6fbfe83d`; do not treat
  them as blocking. Consecutive clean RC counter for this required sequence
  is 1; a second consecutive clean independent RC review remains outstanding.
  Do not claim that `sysdiff` is released without Lee-controlled release
  authorization. Prior Medium-or-higher backlogs remain open and continue to
  prohibit new feature work while that debt remains.
- [x] Run a prior second independent release-candidate review cycle in run
  `c84986cf0c81`,
  `sysdiff_second_independent_release_candidate_review_cycle`. Exact smoke
  start/check 0 with empty `blocking_errors` (check.log pytest
  `127 passed in 10.84s`); review check
  `python3 -m pytest -p no:cacheprovider tests/ -q` → 127 passed in 10.96 s;
  verdict `pass` under Medium with 0 Medium/High/Critical and 9 Low (L1–L9);
  RC-001 strcasecmp-mutant kill re-verified. Historical relative to the
  current mission sequence; not a publication or Lee-authorized release claim.
- [ ] Keep historical Low findings L1–L9 from `c84986cf0c81` visible; do not
  treat them as blocking. Do not claim that `sysdiff` is released without
  Lee-controlled release authorization.
- [x] Deliver and record a prior first independent release-candidate review
  cycle in run `8a3470eff7d3`,
  `sysdiff_first_independent_rc_review_cycle`. Closed mixed-case ordering
  gap (RC-001) in tests/fixtures; exact smoke start/check 0 with empty
  `blocking_errors` (check.log pytest `127 passed in 10.58s`); review
  check `python3 -m pytest tests/ -q` → 127 passed in 11.06 s; verdict
  `pass` with 0 Medium/High/Critical and 7 Low (F1–F7). Historical relative
  to run `6d0a6fbfe83d`'s required sequence.
- [x] Keep Low findings F1–F7 visible after the prior first independent RC
  review cycle; do not treat them as blocking. Do not claim that `sysdiff`
  is released.
- [x] Deliver and record the first consecutive clean release-blocking
  independent review in run `7eb4e29dee6e`,
  `complete_first_consecutive_release_blocking_independent_review`. Exact
  smoke: start/check 0, no blocking errors. Exact full suite:
  `python3 -m pytest tests/ -q` → 124 passed in 10.71 s. Review verdict
  `pass` with 0 Medium/High/Critical and 5 Low (L-1–L-5). This is the
  first consecutive clean review only—not a second clean review, not
  mission completion, and not release readiness.
- [ ] Keep Low findings L-1–L-5 visible after the first consecutive clean
  review; do not treat them as blocking. A second consecutive clean
  release-blocking independent review has not been claimed or completed.
- [x] Deliver and review isolated source-archive verification in run
  `939ee21b0d76`, `verify_reproducible_source_archive_isolated_build`.
  Report `docs/reproducible-source-archive-isolated-build.md` records
  byte-identical archives (SHA-256
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`,
  89851 bytes, 44 members) and extracted-tree quality gates exit 0
  (including ASan/UBSan/Valgrind). User smoke passed; review verdict
  `pass` with 0 High/Critical, 5 Medium (F1–F5), and 4 Low (F6–F9).
- [x] Finish closeout for run `939ee21b0d76`. Recorded exact archive
  hashes, quality results, pytest provisioning recovery, smoke
  start/check 0, independent review `pass` with Medium F1–F5 still open,
  and that this is isolated verification evidence—not a `.deb`/`.rpm`,
  not commit-identical dirty-tree provenance, and not full release
  readiness.
- [ ] Repair isolated-archive / source-release Medium findings F1–F5 from
  `review-reproducible-source-archive-isolated-build.verdict.json`:
  clean-tree or committed-object packaging plus honest provenance; name
  (or split) the six git-gated `test_dist_*` skips in extracts; make
  `dist`/`distcheck` usable or honestly unavailable from the tarball; add
  `dist/` to `.gitignore`; allowlist user-facing docs instead of shipping
  all of `docs/`. Consider Low F6–F9 afterward. Prefer this Medium
  backlog next. Overlaps prior `240bfcbc634e` packaging Medium themes.
- [x] Deliver and review reproducible sysdiff source release in run
  `240bfcbc634e`, `build_verify_reproducible_sysdiff_source_release`. Added
  Makefile `dist` / `distcheck`, six `test_dist_*` regressions, README
  "Source releases", and artifacts `dist/sysdiff-source.tar.gz` +
  `dist/sysdiff-source.tar.gz.sha256` (digest
  `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a`).
  Implementation validation and user smoke passed; review verdict `pass`
  with 0 High/Critical, 5 Medium (F1–F5), and 5 Low (F6–F10).
- [x] Finish closeout for run `240bfcbc634e`. Recorded exact artifact/
  checksum paths, verification (`make dist && make distcheck`, pytest 38
  passed, smoke start/check 0), independent review `pass` with Medium
  F1–F5 still open, and that this is a bounded source-archive
  workflow—not a `.deb`/`.rpm`, not a fresh `make quality`, and not full
  release readiness.
- [x] Deliver and review deterministic sysdiff performance benchmarks in run
  `a0eda97cd039`, `sysdiff_deterministic_performance_benchmarks`. Added
  `scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`, Makefile
  `benchmark`, README "Performance Benchmarks", and
  `artifacts/performance/sysdiff-benchmark.json` (`passed: true`; thresholds
  startup 200.0 ms / fixture 100.0 ms / peak RSS 32768 KiB; measured
  ~1.24 ms / ~7.36 ms / 2540 KiB; baseline ~1.34 ms; 8000-entry fixture).
  Repair closed prior Medium B1/B2; implementation validation and user smoke
  passed; review verdict `pass` with 0 High/Critical/Medium and 9 Low
  (B1–B9).
- [x] Finish closeout for run `a0eda97cd039`. Recorded exact JSON
  measurements/thresholds, verification (pytest 25 passed, `make -n
  benchmark`, harness `--output`, smoke start/check 0), independent review
  `pass` with Low B1–B9 only, remaining host/scheduler/RSS variability, and
  that this is a conservative release guardrail—not a microbenchmark, not a
  fresh `make quality`, and not full release readiness.
- [ ] Optionally polish performance-benchmark Low findings B1–B9 (exit-status
  short-circuit in RSS fallback; `--output` test; tighter or relabeled
  startup gate; real build-isolation test; VmHWM race; `/bin/true`
  preflight; drop dead global; threshold-map extensibility; hard-fail if
  harness script missing). Non-blocking.
- [x] Deliver and review earlier source-release naming slice in run
  `b54d61531266`, `sysdiff_reproducible_source_release` (`source-release` /
  `source-release-verify`). Superseded by `240bfcbc634e` `dist`/`distcheck`.
- [x] Finish closeout for run `b54d61531266` (historical; current packaging
  surface is `make dist` / `make distcheck` from `240bfcbc634e`).
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
- [x] Create `leebase/linux-utilities`, push the clean seed, repair the stalled
  hosted install, upgrade checkout to immutable v6, and obtain a zero-annotation
  successful Ubuntu `make quality` run (`29119972847`).
- [x] Add and review `man/sysdiff.1`, integrate warning-gated groff rendering
  into `make quality`/Ubuntu CI, reconcile public docs, and pass the governed
  quality gate with 41 tests.
- [x] Complete the sysdiff release documentation set
- [x] Implement deterministic ASan, UBSan, and Valgrind regression targets in
  run `5665167f1c1d`; implementation validation passed both memory gates and
  the independent review verdict passed at the High threshold with no
  High/Critical findings.
- [ ] Finish closeout for run `5665167f1c1d`. Preserve the distinction between
  fresh governed smoke (`artifacts/user-smoke/result.json`) and review finding
  F1's stale legacy `.agent-orch/user-smoke/result.json`; do not claim a fresh
  release or full quality gate from this slice.
- [ ] Repair deterministic-memory-gate Medium findings F1-F4: refresh legacy
  smoke pins, declare the POSIX `SIGPIPE` dependency portably, route
  `/dev/full` and closed-pipe fixture helpers through Valgrind, and add
  negative controls that prove ASan/UBSan/Valgrind fail on injected defects.
- [ ] Consider the six Low findings from
  `review-deterministic-memory-gates.verdict.json` after the Medium repair;
  retain explicit Linux/Clang/GCC/Valgrind host prerequisites and loud
  preflight failures.
- [x] Deliver and review reproducible install/uninstall packaging checks in
  run `a2d750c92da3`, `sysdiff_reproducible_install_uninstall_packaging_checks`.
  Added Makefile `install`/`uninstall` with `DESTDIR`/`prefix` path variables,
  shell packaging assertions (exact manifest, modes, installed behavior,
  reinstall, uninstall), and README installation docs. Implementation
  validation and user smoke passed; review verdict `pass` with 0 High/Critical,
  1 Medium (F1), and 6 Low (F2–F7) findings.
- [ ] Finish closeout for run `a2d750c92da3`. Record smoke
  (`artifacts/user-smoke/result.json` start/check 0, no blocking errors) and
  that smoke covers fixtures while packaging is covered by `make test`/shell.
  Do not claim a release, complete packaging, or a zero-finding clean review.
- [ ] Repair packaging-slice Medium F1: guard or extract the packaging block so
  sanitizer/Valgrind gates do not ignore `SYSDIFF_BIN` and re-run uninstrumented
  staged install three extra times; optionally address Low F2–F7 afterward.
- [x] Deliver and review deterministic malformed-snapshot fuzz regression
  coverage in run `feb8e707ea28`. Added
  `docs/malformed-snapshot-fuzz-regression-contract.md` and
  `tests/test_sysdiff_malformed_fuzz.py`; no `src/sysdiff.c` edits required.
  Implementation validation and user smoke passed; review verdict `pass` with
  0 High/Critical, 4 Medium (F1–F4), and 3 Low (F5–F7) findings.
- [ ] Finish closeout for run `feb8e707ea28`. Record exact commands
  (`pytest …malformed_fuzz.py -q` → 40 passed; Clang `-fsyntax-only` → 0),
  smoke (`artifacts/user-smoke/result.json` start/check 0), and that this is a
  bounded deterministic corpus—not open-ended fuzzing, not a fresh sanitizer
  gate, and not a release.
- [ ] Repair malformed-fuzz Medium findings F1–F4: add a 16 MiB total-byte
  over-limit case; make the LINE_TOO_LONG case actually hit `read_line`'s
  guard; add a positive-control compare; honor `SYSDIFF_UNDER_VALGRIND` with
  scaled timeouts. Consider Low F5–F7 afterward.

## Complete the sysdiff release documentation set

Governed run `e7bbd28465b5` delivered the required root release documentation
(HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, STATUS), reconciled README,
CHANGELOG, architecture, and `man/sysdiff.1`, passed the pinned user smoke
gate on attempt 1 (`start_exit_code`/`check_exit_code` 0, no blocking errors),
and received review verdict `pass` in
`code-reviews/sysdiff-release-documentation-review.verdict.json`. Open follow-ups
are Low only: man-page NAME whatis separator (F1) and FILES directory
open-vs-read wording (F2). Do not treat this docs cycle as a fresh
`make quality` product gate; prior release evidence still stands separately.
