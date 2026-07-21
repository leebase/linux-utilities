# Result Review

## First Independent sysdiff Release-Candidate Review

Governed run `6d0a6fbfe83d` (playbook
`template_repair_before_review_feature_delivery`) completed user smoke, the
first independent `sysdiff` release-candidate review, and this handoff record.
This is the first clean review in the required consecutive clean-review
sequence. Do not claim that `sysdiff` is released, that the mission is
complete, or that a second consecutive clean RC review has occurred. Exact
smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`. `artifacts/user-smoke/check.log` confirms DESTDIR
install/uninstall staging, fixture acceptance ok, and smoke-bound pytest
`127 passed in 10.75s`. Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.89s` (reviewed at HEAD `510fa2d`). Independent review
artifacts: `code-reviews/review-first-sysdiff-release-candidate.md` and
`code-reviews/review-first-sysdiff-release-candidate.verdict.json`. Verdict:
`pass` with no Medium, High, or Critical findings, and ten Low findings
(L1–L10) preserved: L1 unreproducible complete-floor provenance in
`docs/sysdiff-quality-floor-clean-checkout.md`; L2 STATUS.md stale "no install
target"; L3 quality-floor doc still labels resolved packaging risk as known
Medium; L4 no-op `tests/smoke_start.py`; L5 dead `read_line` overflow
disjuncts in `src/sysdiff.c`; L6 stale-errno stdout diagnostic in
`complete_stdout`/`emit_write_error`; L7 undeclared POSIX SIGPIPE under
`-std=c17`; L8 pytest `test_dist_*` regenerates workspace `dist/`; L9
TESTING.md wrong SYSDIFF_BIN reuse claim; L10 STATUS.md unanchored
clean-review counter conflicting with this sequence position. Step-2 attempt 1
failed the verdict gate on Medium M1 (same provenance issue); attempt 2 held
it at Low and passed. Remaining risks stay visible (Low L1–L10 plus prior-slice
Medium backlogs). Prior Medium-or-higher debt continues to prohibit new
feature work until repaired. A second consecutive clean independent RC review
is still required before the two-clean-review requirement is satisfied.

## Second Independent Release-Candidate Review Cycle

Governed run `c84986cf0c81` (playbook
`sysdiff_second_independent_release_candidate_review_cycle`) completed user
smoke, the second independent release-candidate review, and this handoff
record. Verdict `code-reviews/sysdiff-rc-second-independent-cycle.verdict.json`
is `pass` under the Medium threshold: 0 Medium/High/Critical, 9 Low (L1–L9).
Exact smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`. `artifacts/user-smoke/check.log` confirms DESTDIR
install/uninstall staging, fixture acceptance ok, and smoke-bound pytest
`127 passed in 10.84s`. Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.96s`. RC-001 strcasecmp-mutant result: independently
reconstructed (`strcmp` → `strcasecmp` in `compare_entries_by_key`); kill is
behavioral and robust to qsort Alpha/alpha tie-breaking; full suite with
`SYSDIFF_BIN` on the mutant reports `1 failed, 126 passed` on the mixed-case
bytewise ordering test. Consecutive clean RC review cycles now stand at 2
(prior: `sysdiff-rc-review-cycle-1.verdict.json` pass). Fresh quality evidence
this cycle: step-1 non-writing gates (pytest 127; gcc/clang `-fsyntax-only`;
cppcheck; shell `bash -n`; `check_tools.py`) plus smoke/review pytest—not a
fresh full `make quality`. Remaining Low L1–L9 stay visible. This records the
second consecutive clean RC cycle; it does not declare `sysdiff` released.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` (playbook `sysdiff_first_independent_rc_review_cycle`)
completed user smoke, the independent release-candidate review, and this
handoff record. This is the first independent release-candidate review cycle.
Do not claim that `sysdiff` is released, that the mission is complete, or that
a second consecutive clean RC review has occurred. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`. `artifacts/user-smoke/check.log` confirms assembled-product
`make install`/`make uninstall` staging, fixture acceptance ok, and smoke-bound
pytest `127 passed in 10.58s`. Exact review check: `python3 -m pytest tests/ -q`
exited 0 with `127 passed in 11.06s` (no skips). Independent review artifacts:
`code-reviews/sysdiff-rc-review-cycle-1.md` and
`code-reviews/sysdiff-rc-review-cycle-1.verdict.json`. Verdict: `pass` with no
Medium, High, or Critical findings, and seven Low findings (F1–F7) preserved:
STATUS/ROADMAP install-target wording; TESTING.md SYSDIFF_BIN reuse claim;
mutant-test hardcoded `/tmp`; unused scratch Makefile copy; `finally`-block
assertions/`rm -rf`; mutant oracle not tied to shell golden. Remaining risks
stay visible (Low F1–F7 plus prior-slice Medium backlogs). A second consecutive
review cycle with no release-blocking findings is still required before mission
completion.

## First Consecutive Release-Blocking Independent Review

- Governed run `7eb4e29dee6e` (playbook
  `complete_first_consecutive_release_blocking_independent_review`) completed
  user smoke, the independent release-blocking review, and this handoff record.
  This is the first consecutive clean release-blocking independent review. Do
  not claim a second clean review, mission completion, or release readiness.
- Exact smoke outcome (`artifacts/user-smoke/result.json`): `app_started:
  true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, empty `blocking_errors`. `artifacts/user-smoke/check.log`
  confirms assembled-product `make install`/`make uninstall` staging (modes
  755/644), fixture acceptance ok, and smoke-bound pytest `124 passed in
  10.23s`.
- Exact full-suite outcome (review allowlisted check): `python3 -m pytest
  tests/ -q` exited 0 with `124 passed in 10.71s` (non-vacuous compile under
  `-std=c17 -Wall -Wextra -Wpedantic -Werror` when `SYSDIFF_BIN` unset).
- Independent review artifacts:
  `code-reviews/sysdiff-independent-review-1.md` and
  `code-reviews/sysdiff-independent-review-1.verdict.json`. Verdict: `pass`
  with no Medium, High, or Critical findings, and five Low findings (L-1–L-5)
  preserved: man `--help`/`--version` arity diagnostic; architecture Valgrind
  clean/rebuild wording; accepted ` -> ` irreversibility; DESIGN quality-sequence
  wording; SIGPIPE Linux-conditional docs vs unconditional POSIX ignore.
- Remaining risks stay visible (Low L-1–L-5 plus prior-slice Medium backlogs).
  This handoff records the first consecutive clean gate only; it does not
  assert full product-release closure.

## Reproducible Source Archive — Isolated Build Verification

- Governed run `939ee21b0d76` (playbook
  `verify_reproducible_source_archive_isolated_build`) completed isolated
  verification of `make dist` reproducibility and the extracted-tree quality
  surface. Report:
  `docs/reproducible-source-archive-isolated-build.md`. Exact archive
  identity at `SOURCE_DATE_EPOCH=946684800`: size 89851 bytes; SHA-256
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544` for
  both independent external builds; checksum file contents
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544  sysdiff-source.tar.gz`
  (`sha256sum -c` → OK); 44 members under `sysdiff/`; `cmp` and member-list
  `diff` empty. Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Quality results from the extracted tree (report Overall Result PASS;
  independently re-executed in review): gcc-strict, clang-strict,
  format-check, clang-tidy-check, cppcheck-check, clang-analyzer-check,
  man-check, `make clean all`, test-suite, `./tests/test_sysdiff.sh`,
  `bash tests/test_sysdiff_fixture.sh`, malformed-fuzz pytest,
  benchmark-check, `make test-asan`, `make test-ubsan`, and
  `make test-valgrind` all exited 0. Extracted-tree pytest counts: 118
  passed, 6 skipped (test-suite / ASan / UBSan / Valgrind). Malformed-fuzz:
  41 passed in 0.18 s. Staged install produced exactly two files
  (`usr/local/bin/sysdiff` mode 755 size 21384;
  `usr/local/share/man/man1/sysdiff.1` mode 644 size 7191); uninstall took
  staged file count from 2 to 0.
- Failed experiment then recovered: first `make test-suite` under
  `PATH=/usr/bin:/bin` alone failed with `No module named pytest`; after
  provisioning an isolated venv with `pytest==8.4.2` under the external
  verify root, the same gates exited 0 (tool provisioning, not a silent
  skip of a required gate).
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; archive/quality evidence is
  the isolated verification and review path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-reproducible-source-archive-isolated-build.md` and
  `.verdict.json`. Verdict: `pass` with no High or Critical findings, five
  Medium findings (F1–F5), and four Low findings (F6–F9). Allowlisted check
  only: `python3 -m pytest tests/ -q` exited 0 (124 passed in 10.71 s; 0
  skipped in the git workspace). Review confirmed every quantitative claim
  in the report (digest, size, member count, gate exits, install modes/
  sizes, 2→0 residue) and found no Critical/High C craftsmanship, ownership,
  UB, diagnostics, or sanitizer issues.
- Non-blocking risks remain: F1 Medium — Artifact Identity labels revision
  `a69423e2a1cfa4b30c199797aaa10cead4879370` while `make dist` packages
  dirty working-tree bytes; F2 Medium — the six extracted-tree skips are the
  git-gated `test_dist_*` regressions, so dist coverage is not exercised in
  the non-git extract; F3 Medium — `make dist` / `make distcheck` exit 2
  from the extracted tarball; F4 Medium — `dist/` not in `.gitignore`; F5
  Medium — whole-directory `docs/` ships internal review/plan material; Low
  F6 extension-based exec bits; F7 undisclosed gzip implementation
  sensitivity; F8 README untracked-vs-dirty wording; F9 `distcheck`
  overwrites workspace `dist/`.
- Recommended next action: bound a governed repair for Medium F1–F5
  (clean-tree or committed-object packaging plus honest provenance; name the
  six dist skips / split git-free coverage; make dist usable or honestly
  unavailable in source distributions; add `dist/` to `.gitignore`;
  allowlist user-facing docs). Keep Low F6–F9 visible. Do not infer a
  packaged `.deb`/`.rpm`, commit-identical archives from dirty trees, or
  full release closure from this verification pass.

## Reproducible sysdiff Source Release (`make dist` / `make distcheck`)

- Governed run `240bfcbc634e` (playbook
  `build_verify_reproducible_sysdiff_source_release`) delivered Makefile
  `dist` and `distcheck`, six `test_dist_*` regressions in
  `tests/test_sysdiff.py`, and README "Source releases". Exact artifacts:
  `dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256`
  (basename-only digest
  `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a  sysdiff-source.tar.gz`).
  `make dist` selects tracked `DIST_PATHSPECS` via `git ls-files`, stages under
  `sysdiff/`, and writes a normalized ustar+gzip archive (`SOURCE_DATE_EPOCH`
  default 0, owner/group 0, sorted members, `gzip -n -9`). `make distcheck`
  rebuilds twice, compares digests/raw bytes/checksum files, extracts under
  `/tmp` outside the workspace, and runs `make` plus `make test` on the clean
  tree. Explicit non-goal: not a `.deb`/`.rpm`, and not a change to `sysdiff`
  compare behavior. Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Step-1 validation passed exactly:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py -q` exited 0
  with 38 passed in 5.80 s; `make clean && make test` exited 0;
  `make dist && make distcheck` exited 0 (`distcheck: ok`); and
  `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c`
  exited 0. Changed files were `Makefile`, `README.md`, and
  `tests/test_sysdiff.py`.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; source-release coverage is
  the Make/pytest/`distcheck` path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-sysdiff-source-release.md` and `.verdict.json`.
  Verdict: `pass` with no High or Critical findings, five Medium findings
  (F1–F5), and five Low findings (F6–F10). Allowlisted check only:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py -q`
  exited 0 (38 passed in about 5.8 s). Manual inspection confirmed
  reproducibility mechanics and out-of-tree extract-build-test; the review
  did not freshly rerun `make quality` or claim full release readiness.
- Non-blocking risks remain: F1 Medium — `git ls-files` + working-tree `cp`
  packages dirty tracked bytes with no commit stamp; F2 Medium — shipped
  README Documentation links omit root STATUS/QUALITY/TESTING/HISTORY/
  DECISIONS/ROADMAP/architecture from `DIST_PATHSPECS`; F3 Medium — dist
  tests overwrite repository `dist/` at epoch `946684800` vs default 0;
  F4 Medium — `dist/` is generated but not in `.gitignore`; F5 Medium —
  recorded `.agent-orch/user-smoke` pins predate dist work and do not
  exercise `distcheck`; Low F6 sanitizer/Valgrind re-run expensive dist
  nested builds; F7 decoy-file interrupt residue; F8 unanchored exclusion
  globs; F9 triplicated `0.1.0` version string; F10 undocumented bash/git/
  tar/gzip/sha256sum prerequisites for dist.
- Recommended next action: bound a governed repair for Medium F1–F5
  (clean-tree or committed-object packaging plus provenance; archive/docs
  self-consistency; isolate dist tests from repo `dist/`; add `dist/` to
  `.gitignore`; refresh smoke evidence to cover `distcheck`). Keep Low
  F6–F10 visible. Do not infer a packaged `.deb`/`.rpm`, commit-identical
  archives from dirty trees, a fresh `make quality`, or full release
  closure from this review pass.

## Deterministic sysdiff Performance Benchmarks

- Governed run `a0eda97cd039` (playbook
  `sysdiff_deterministic_performance_benchmarks`) delivered
  `scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`, Makefile
  `benchmark`, README "Performance Benchmarks", and committed
  `artifacts/performance/sysdiff-benchmark.json`. Exact report evidence
  (`schema_version` 1, `passed: true`): measurements
  `startup_ms_median` 1.2422580039128661,
  `fixture_ms_median` 7.362931006355211, `peak_rss_kib` 2540.0,
  `baseline_ms_median` 1.3354689872357994; thresholds
  `startup_ms_median` 200.0, `fixture_ms_median` 100.0,
  `peak_rss_kib` 32768.0; metadata fixture_entry_count 8000, warmups 1,
  sample_count 5, `work_dir_kind` tempdir, baseline_command `/bin/true`.
  Repair closed prior Medium B1 (unchecked child exit status) and B2
  (spawn-floor / tiny fixture). Explicit non-goal: not a microbenchmark
  claim, not a change to `sysdiff` compare behavior, not `make quality`.
  Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Step-4 repair/verify passed exactly:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff_benchmark.py -q`
  exited 0 with 25 passed in 1.73 s; `make -n benchmark` exited 0; and
  `python3 scripts/benchmark_sysdiff.py --output
  artifacts/performance/sysdiff-benchmark.json` exited 0 with
  `passed: true`.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; benchmark coverage is the
  Make/pytest/harness path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-sysdiff-performance-benchmarks.md` and
  `.verdict.json`. Verdict: `pass` with no High, Critical, or Medium
  findings, and nine Low findings (B1–B9). Allowlisted check only:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff_benchmark.py -q`
  exited 0 (25 passed in 1.62 s). Review read the committed JSON and smoke
  result; it did not freshly rerun `make benchmark` or `make quality`.
- Non-blocking risks remain (all Low): B1 RSS fallback masks exit-status
  failures; B2 CLI `--output` write path untested; B3 startup gate ~160x
  loose / spawn-dominated; B4 temp-isolation test does not exercise
  `build_sysdiff_in_temp`; B5 `/proc` VmHWM races short-lived children; B6
  hardcoded `/bin/true` without preflight; B7 unused `_RSS_WRAPPER_WORK`;
  B8 `build_report` hardcodes three threshold keys; B9 suite still skips
  green if the harness script is absent.
- Remaining environmental variability: Linux-only; scheduler noise; spawn
  floor vs product work; RSS backend availability order; minimal images
  without `/bin/true`. Recommended next action: resume Medium backlog
  (source-release F-001–F-003 first) while keeping Low B1–B9 visible for
  optional harness polish. Do not infer microbenchmark claims, cross-host
  bit-stable timings, a fresh `make quality`, or release closure.

## Reproducible sysdiff Source Release

- Governed run `b54d61531266` (playbook
  `sysdiff_reproducible_source_release`) delivered `make source-release` and
  `make source-release-verify` in the Makefile, seven pytest release tests in
  `tests/test_sysdiff.py`, README "Source Releases" docs, and CHANGELOG
  Unreleased notes. Exact artifacts:
  `dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256`
  (basename-only digest
  `1646e8465cdb9365c5ad90d2107a795fde762d3a68d46c69b61502f6531c1128  sysdiff-source.tar.gz`).
  Archive members are the six product paths under `sysdiff/` (Makefile,
  LICENSE, README.md, CHANGELOG.md, src/sysdiff.c, man/sysdiff.1). Explicit
  non-goal: not a `.deb`/`.rpm`, and not a change to `sysdiff` compare
  behavior. Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Step-2 validation passed exactly: `make clean && make test`;
  `bash tests/test_sysdiff.sh`; `bash tests/test_sysdiff_fixture.sh`;
  `python3 -m pytest tests/test_sysdiff.py -q` exited 0 with 40 passed in
  2.05 s; `make source-release-verify` exited 0; and
  `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c`
  exited 0. Step-1 also confirmed artifact existence and
  `make source-release-verify` plus pytest (40 passed in 2.14 s).
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; source-release coverage is
  the Make/pytest path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-sysdiff-reproducible-source-release.md` and
  `.verdict.json`. Verdict: `pass` with no High or Critical findings, three
  Medium findings (F-001–F-003), and three Low findings (F-004–F-006).
  Allowlisted check only: `python3 -m pytest tests/test_sysdiff.py -q`
  exited 0 (40 passed in 2.13 s). Manual inspection confirmed checksum OK,
  normalized member metadata, and out-of-tree default `make` build success;
  the review did not freshly rerun `make quality` or claim full release
  readiness.
- Non-blocking risks remain: F-001 Medium — shipped README/Makefile document
  tests, quality gates, scripts, and docs that are not archive members, so
  `make test`/`quality`/`check` fail in a clean extract while default `make`
  succeeds; F-002 Medium — release tests write into repository `dist/` and
  pin epoch `946684800` vs default `SOURCE_DATE_EPOCH=0`; F-003 Medium —
  `dist/` is generated but not in `.gitignore`; Low F-004 unpinned gzip
  compression level across environments; F-005 over-broad `*../*` verify
  glob; F-006 CHANGELOG still lists “source-first packaging without an
  install target” despite install/uninstall targets.
- Recommended next action: bound a governed repair for Medium F-001–F-003
  (archive/docs self-consistency first; then isolate release tests from repo
  `dist/` and add `dist/` to `.gitignore` or pin a committed-artifact
  decision). Keep Low F-004–F-006 visible. Do not infer a packaged
  `.deb`/`.rpm`, cross-distro bit-identical gzip digests, a fresh
  `make quality`, or full release closure from this review pass.

## Deterministic Malformed-Snapshot Fuzz Regression Coverage

- Governed run `feb8e707ea28` (playbook
  `template_repair_before_review_feature_delivery`) delivered the malformed-
  snapshot fuzz regression contract at
  `docs/malformed-snapshot-fuzz-regression-contract.md` and the deterministic
  pytest corpus `tests/test_sysdiff_malformed_fuzz.py` (fixed-byte cases plus
  seeded mutations under `CORPUS_SEED = 0x5FED1FF5`). No `src/sysdiff.c` changes
  were required; the existing parser already reject-closes every corpus case
  with exit status 2 and empty stdout. Explicit non-goal: this is not open-
  ended fuzzing, not a new CLI surface, and not a release gate.
- Step-3 validation passed exactly: `python3 -m pytest
  tests/test_sysdiff_malformed_fuzz.py -q` exited 0 with 40 passed in 0.18 s
  (38 parametrized rejection cases plus two structural corpus tests); and
  `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c`
  exited 0. Changed deliverables were the contract, the fuzz test module, and
  the two review artifacts.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; the malformed corpus is covered
  by the pytest module, not by that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-malformed-snapshot-fuzz-regression.md` and
  `.verdict.json`. Verdict: `pass` at the High threshold with no High or
  Critical findings, four Medium findings (F1–F4), and three Low findings
  (F5–F7). Allowlisted check only: `python3 -m pytest
  tests/test_sysdiff_malformed_fuzz.py -q` exited 0 (40 passed in 0.19 s). The
  review did not freshly rerun ASan, UBSan, Valgrind, or `make quality`.
- Non-blocking risks remain: F1 Medium — no corpus case exceeds the 16 MiB
  total-byte limit; F2 Medium — the claimed `read_line` LINE_TOO_LONG case is
  behaviorally identical to the post-strip 65537-byte guard; F3 Medium —
  rejection-only suite lacks a positive-control compare; F4 Medium — harness
  ignores `SYSDIFF_UNDER_VALGRIND` so Valgrind never sees hostile inputs
  (ASan/UBSan via `SYSDIFF_BIN` is noted as the carry path, not newly proven
  here); Low F5 duplicate seeded mutations; F6 silent valid-mutation drops;
  F7 hardcoded fallback compile flags vs project `CFLAGS`.
- Recommended next action: finish closeout for `feb8e707ea28`, then bound a
  repair for Medium F1–F4. Do not infer open-ended fuzzing coverage, a fresh
  sanitizer/Valgrind product gate, a release, or a complete `make quality`
  from this threshold-High review pass.

## Add reproducible install and uninstall packaging checks

- Governed run `a2d750c92da3`, playbook
  `sysdiff_reproducible_install_uninstall_packaging_checks`, delivered Makefile
  `install`/`uninstall` using `DESTDIR` plus `prefix`/`bindir`/`mandir`/`man1dir`,
  a packaging block in `tests/test_sysdiff.sh` that stages into a workspace
  `DESTDIR`, asserts an exact two-file manifest and modes 755/644, runs the
  installed binary for `--help`/`--version`/`compare`, checks byte-identical
  reinstall, and asserts leftover-free file/symlink uninstall, plus README
  installation wording that matches those targets. Explicit non-goal: no
  `.deb`/`.rpm` generation.
- Step-1 validation passed: `bash -n tests/test_sysdiff.sh`;
  `make clean && make test`; `bash tests/test_sysdiff.sh`; and
  `bash tests/test_sysdiff_fixture.sh`. Changed files were `Makefile`,
  `README.md`, and `tests/test_sysdiff.sh`.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; packaging is covered by the
  shell/`make test` path, not by that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-install-uninstall-packaging.md` and
  `.verdict.json`. Verdict: `pass` with no High or Critical findings, one
  Medium finding (F1), and six Low findings (F2–F7). Allowlisted check only:
  `python3 -m pytest tests/test_sysdiff.py tests/test_check_tools.py -q -p
  no:cacheprovider` exited 0 (50 passed in 2.24 s).
- Non-blocking risks remain: F1 Medium — packaging ignores `SYSDIFF_BIN` and
  repeats uninstrumented staged install under sanitizer/Valgrind gates; Low
  F2 empty-directory residue unasserted; F3 no whitespace/`metachar` DESTDIR
  coverage in-suite; F4 bare `make` / jobserver warning; F5 undocumented
  `bindir`/`mandir`/`man1dir`; F6 undeclared GNU find/stat/install dependency;
  F7 bare permission-denied install diagnostics.
- Recommended next action: finish closeout for `a2d750c92da3`, then bound a
  repair for F1 (skip or isolate packaging under instrumented gates). Do not
  infer a release, complete packaging/product gate, clean review with zero
  findings, or a fresh `make quality` from this threshold pass.

## 2026-07-18 — Deterministic sanitizer and Valgrind regression coverage

- Governed run `5665167f1c1d`,
  `deterministic_sanitizer_valgrind_regression_coverage`, added explicit
  sanitizer/Valgrind preflight, per-target `mktemp` binaries, `SYSDIFF_BIN`
  routing through shell and pytest coverage, leak-fatal ASan policy,
  halt-on-error UBSan policy, and Valgrind status-99/error-log enforcement. Normal
  `build/sysdiff` is not replaced by an instrumented binary.
- Step-1 validation passed exactly: both shell syntax checks (`bash -n` on
  `tests/test_sysdiff.sh` and `tests/test_sysdiff_fixture.sh`); 18 tests passed
  in 0.59 s for
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
  tests/test_check_tools.py -q`; `make test-sanitize` exited 0; and `make
  test-valgrind` exited 0.
- Governed user smoke passed its pinned manifest-oracle validation;
  `artifacts/user-smoke/result.json` records both flows true, start/check exit
  codes 0, and no blocking errors. This is distinct from the stale historical
  `.agent-orch/user-smoke/result.json` identified by review finding F1.
- Independent review artifacts are
  `code-reviews/review-deterministic-memory-gates.md` and `.verdict.json`.
  Verdict: `pass` at the High threshold, with no High/Critical findings, four
  Medium findings, and six Low findings. The review's only allowlisted command
  was `python3 -m pytest -p no:cacheprovider tests/test_check_tools.py -q`,
  which exited 0 with 18 passed in 0.57 s; it did not freshly rerun the
  sanitizer or Valgrind targets.
- Medium risks remain: stale legacy smoke hashes (F1); implicit POSIX
  `SIGPIPE` exposure that is not portable from glibc to musl under the current
  strict-C flags (F2); shell `/dev/full` and closed-pipe helpers that bypass
  Valgrind, although pytest covers closed-pipe (F3); and no detector negative
  control (F4). Six Low findings cover unused/duplicated Valgrind command
  construction, stale routed-harness defaults, ordinary pytest cache hygiene,
  overstated smoke-layer independence, missing `man-check` temp cleanup trap,
  and a preflight probe that links but does not execute.
- Host availability remains a real boundary: gates require Linux, Clang with
  usable ASan/UBSan runtimes, and GCC plus Valgrind. The current host passed
  compile/link preflights and full implementation validation; unsupported or
  incomplete hosts fail loudly rather than silently skip.
- Recommended next action: regenerate the stale legacy smoke evidence against
  the current tree, then use a bounded governed repair slice for F2-F4. Do not
  infer a release, a fresh `make quality`, or broader platform support from
  this threshold-High review pass.

## Sysdiff Release Documentation Set

- Governed run `e7bbd28465b5`, playbook
  `sysdiff_complete_release_documentation_set`, authored and repaired the root
  release docs (HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, STATUS) and
  reconciled README, CHANGELOG, architecture, and `man/sysdiff.1` without
  executing compilers, builds, or the full quality gate in those write steps.
- User smoke gate (`step_03_user_smoke_gate` attempt 1) passed:
  `artifacts/user-smoke/result.json` reports `app_started: true`,
  `core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, and
  empty `blocking_errors`, with pinned smoke-manifest hashes validated.
- Independent review
  `code-reviews/sysdiff-release-documentation-review.verdict.json` is `pass`
  (High/Critical threshold). Allowlisted check
  `python3 -m compileall tests/test_check_tools.py` exited 0. Two Low findings
  remain: F1 NAME uses `\(em` instead of ` \- ` for whatis/apropos; F2 FILES
  directory wording is imprecise about open-vs-read failure on Linux.
- This slice confirms documentation fidelity and smoke continuity; it does not
  claim a fresh `make quality` or a new product-release gate beyond prior
  recorded evidence.

## 2026-07-10 — Section-1 manual page ready for publication

- Added `man/sysdiff.1` with exact CLI, format, escaping, limits, security,
  output, exit-status, example, copyright, and version documentation.
- Added `make man-check`; it captures groff diagnostics and fails on either a
  nonzero render or any warning. `make quality` and Ubuntu CI include this gate;
  CI installs groff.
- Reconciled README, changelog, decisions, design, specification, and release
  review. The key grammar now says exactly that consecutive dots (`..`) are
  rejected.
- Final governed `make quality` exited `0`: groff lint, strict compilers,
  static analysis, 41 tests, leak-enabled ASan, UBSan, and Valgrind passed.
- GitHub authentication is active as `leebase`; no remote existed before this
  publication step.
- Created and pushed `https://github.com/leebase/linux-utilities` from the clean
  seed. Public commits are `255bdde` (man page), `8abf062` (noninteractive CI
  install), and `fbdf071` (checkout v6).
- Initial CI run `29119319248` was cancelled after hosted apt stalled for over
  six minutes. The bounded repair added noninteractive apt/needrestart handling
  and a 15-minute job timeout.
- CI run `29119799430` passed but exposed a Node 20 deprecation annotation from
  checkout v4. The official immutable checkout-v6 pin removed it.
- Final CI run `29119972847` passed the Ubuntu `make quality` job in full with
  zero annotations on commit `fbdf071`.

## 2026-07-10 — Adversarial public-release remediation

- Final evaluator rejected the first seed with five Medium findings: raw
  terminal-control output, successful exit on stdout loss, multi-gigabyte
  aggregate input exposure, non-gating Valgrind/cppcheck behavior, and stale
  public docs.
- Cursor `agent` using `grok-4.5-high` wrote tests and implementation through
  eight bounded review iterations. The planner independently reviewed every
  diff and returned C/POSIX/static-analysis findings until clean.
- Added printable-ASCII byte escaping for values and untrusted diagnostics,
  checked stdout/flush/EPIPE handling, a 16 MiB per-snapshot total-byte limit,
  byte-limit/NUL precedence, Valgrind status 99 with error-log enforcement,
  gating cppcheck, a normal default build, leak-enabled ASan, immutable CI
  action pinning, and adversarial fixtures.
- Governed pytest now reports 41 passing tests. Final post-documentation
  `make quality` completed with exit status `0`, including the final Valgrind
  fixture success line.
- Public docs now record the rejected findings and repairs. Remaining Low
  limitations are explicit and do not block making the repository public; the
  GitHub release itself must wait for first-remote CI success.

## 2026-07-10 — v0.1.0 release candidate prepared

- Verified the governing run `eab8bbd05f50` is `COMPLETED`; its prior smoke
  result is historical rather than release evidence.
- Resolved its F001–F004 follow-ups: portable pytest compiler selection,
  immediate smoke start, whitespace-only blank-line handling with shell and
  pytest coverage, and removal of the unreachable `copy_range` `SIZE_MAX`
  guard.
- Added Ubuntu CI that installs the tools required by `make quality` and runs
  that exact command. Added public release documentation, contribution guide,
  MIT placeholder license, changelog, AI-development safeguards, and a fresh
  release review.
- Historical first-pass verification: `make quality`; pytest reported 26 passed.
  The quality gate includes GCC/Clang strict builds, formatting, clang-tidy,
  cppcheck, fixtures, pytest, ASan, UBSan, and Valgrind.
- Accepted Low limitation: changed output is human-readable and not reversible
  when opaque values contain ` -> `. No Medium-or-higher findings remain.

## 2026-07-10 — Fixture acceptance-test slice delivered

- Completed Agent-Orch run `eab8bbd05f50`,
  `sysdiff_fixture_diff_acceptance_tests`, through review and into closeout
  handoff. Steps authored fixture acceptance tests, verified fixture compare
  behavior, passed the pinned user smoke gate, and wrote the review artifacts.
- Review files:
  `code-reviews/review-sysdiff-fixture-acceptance-tests.md` and
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`.
- Verdict is `pass` at the High severity threshold, with no High or Critical
  findings. Review check `python3 -m pytest tests/ -q` exited `0` (26 tests
  collected and passed in 0.40 s across `tests/test_sysdiff.py` and
  `tests/test_check_tools.py`).
- Smoke evidence in `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `check_exit_code: 0`, empty
  `blocking_errors`, and `start_exit_code: -15` (SIGTERM from the start-helper
  timeout mismatch).
- Delivered acceptance coverage includes status 0/1/2, exact sorted stdout for
  mixed add/remove/change, ordering independence, comments/blank lines, CRLF
  and mixed-ending equivalence, line/entry resource limits, empty stdout on
  error paths including malformed after-path cases, and pytest coverage for
  help/version, comparisons, malformed input, and opaque `file.` keys.
- The review notes `main` now guards `argc < 1` before `argv[1]` use, and that
  `Makefile` `valgrind-test` cleans and rebuilds with strict GCC flags before
  Valgrind.
- Historical findings from this verdict, resolved by the 2026-07-10 release
  preparation: F001 Medium (`tests/test_sysdiff.py`
  hardcodes `gcc`); F002 Medium (`tests/smoke_start.py` 30 s sleep vs 10 s
  startup timeout); F003 Low (whitespace-only lines rejected vs contract blank
  wording); F004 Low (unreachable `copy_range` `SIZE_MAX` guard).

## 2026-07-09 — Output format approved and C craftsmanship gate set

- Lee approved the current `sysdiff` format-1 diff output:
  `+ key=value`, `- key=value`, and `~ key: old -> new`.
- Lee approved keeping and committing the current overnight sysdiff work on
  `main`.
- Before additional sysdiff feature work, run a C craftsmanship review covering
  `src/sysdiff.c`, `Makefile`, tests, smoke manifest, and user-facing docs.
  Medium-or-higher craftsmanship findings should block new feature slices.
- Future OpenAI/Codex routes should use `gpt-5.5`; do not add GPT-5.4
  assignments.

## Previous completed work

- Completed the C craftsmanship review in Agent-Orch run `c434e00a3772`,
  `craftsmanship_review_closeout`. Verdict
  `code-reviews/craftsmanship-review.verdict.json` was `pass` at the
  High/Critical threshold. Several of its findings overlap the current fixture
  acceptance verdict (portable pytest compiler choice; smoke-start timeout).
  Fixture acceptance coverage and the `argc < 1` guard supersede the earlier
  missing CRLF/resource-limit test and `argc == 0` concerns for planning
  purposes; treat the latest fixture-acceptance verdict as current.
- Applied the narrow Makefile quality-gate action: `Makefile` includes `check`
  in `.PHONY` and adds `check: test-suite`. Follow-up review
  `code-reviews/review-makefile-quality-gates.verdict.json` passed at the High
  threshold; the fixture-acceptance review now reports that standalone
  `valgrind-test` cleans/rebuilds before Valgrind.
- Advanced Agent-Orch run `c02d741432d3`,
  `sysdiff_c_source_implementation`, through review and closeout. It added
  `docs/sysdiff-c-source-contract.md` and
  `plans/sysdiff-c-source-implementation-plan.md`, hardened `src/sysdiff.c`,
  updated `Makefile`, documented limits in `README.md`, passed smoke, and
  passed review at the High threshold.
- The previous governed run `5ff82aa95e06`,
  `sysdiff_fixture_smoke_repair`, completed closeout. It changed only
  `tests/smoke_manifest.json` and `tests/test_sysdiff_fixture.sh`, passed
  smoke and review, and resolved prior smoke-fixture findings F-001 Medium and
  F-002 Low by enforcing exact diff order and stronger diff-line checks.
- The previous routed tool-availability run `b6deb04a6055` added
  `scripts/check_tools.py`, tests, docs, and README discoverability for the
  default `codex_cli` and `claude_code` harness checks. Its review verdict
  `code-reviews/review-tool-availability-check.verdict.json` reports `pass` at
  a High severity threshold with two Low findings still open.
- Earlier `sysdiff` core history remains relevant: the changed-line ambiguity
  finding for values containing ` -> ` remains outside the fixture acceptance
  slice and is still visible for future output-format work.

## Verification

- Final post-documentation `make quality` — exit `0`; strict GCC/Clang,
  clang-format, clang-tidy, gating cppcheck, 41 pytest tests, shell fixtures,
  leak-enabled ASan, UBSan, and Valgrind all passed.
- Official `actions/checkout` lookup — pinned SHA
  `34e114876b0b11c390a56381ad16ebd13914f8d5` matches `refs/tags/v4`.
- Post-man-page `make quality` — exit `0`; includes warning-gated groff render,
  41 governed tests, sanitizers, and Valgrind.

- `python3 -m pytest tests/ -q` — exit `0`; 26 tests passed (fixture-acceptance
  review check)
- Agent-Orch `SmokeTestAdapter` / user smoke gate for `eab8bbd05f50`
  `step_04_user_smoke_gate` attempt 1 against `tests/smoke_manifest.json`;
  evidence: `artifacts/user-smoke/result.json` (`check_exit_code: 0`,
  `start_exit_code: -15`, no blocking errors)
- Prior craftsmanship checks from run `c434e00a3772` remain historical evidence
  only; current open findings are those in
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`
