# Result Review

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
