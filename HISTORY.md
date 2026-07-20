# Project History

`sysdiff` began as the first utility in the `linux-utilities` suite: a small,
auditable C program for comparing explicit system snapshot files rather than
probing a live host. Early governed slices established the format-1
`key=value` contract, fixture-backed `compare` behavior, strict Makefile
quality targets, and AgentFlow memory for orchestration. Core parser and
comparer work landed through Agent-Orch runs that enforced validate-before-
output semantics, duplicate-key detection, opaque values, and deterministic
bytewise key ordering. Subsequent hardening added explicit line, entry, and
16 MiB total-byte limits, centralized parse cleanup, portable pytest compiler
selection, and an immediate smoke start helper. An adversarial last-stop audit
rejected the first public candidate, then drove terminal-safe escaping,
checked stdout/EPIPE handling, honest Valgrind/cppcheck failure semantics, and
leak-enabled ASan. A section-1 man page and warning-gated groff check joined
the gate before the curated seed was published. This history is product
evidence: append new cycles; do not erase prior engineering record.

## Engineering Timeline

- Snapshot-format and initial-scope contract authored for explicit
  `key=value` comparison only (`docs/sysdiff-snapshot-format-and-scope.md`).
- Minimal C quality-gate harness and fixture-backed comparison smoke path.
- Core parser/comparer slice: sorted map diff, empty stdout on validation
  errors, opaque values, CRLF/LF handling.
- Resource-limit and ownership hardening in `src/sysdiff.c` with Makefile
  sanitizer and Valgrind targets that clean/rebuild as required.
- Fixture acceptance coverage for status 0/1/2, ordering independence,
  comments/blanks, limits, and malformed after-path cases.
- C craftsmanship review passed at High/Critical before further features.
- 2026-07-10 release preparation: F001–F004 follow-ups resolved; Ubuntu CI
  wired to `make quality`; public docs and MIT license curated.
- Adversarial remediation of five Medium findings; governed suite expanded
  (41 tests in the private tree; curated public seed omits internal harness
  checks).
- Man page `man/sysdiff.1` plus `make man-check`; public repo
  `leebase/linux-utilities` pushed; CI run `29119972847` green on `fbdf071`.
- 2026-07-17: GitHub `v0.1.0` tag/release pointed at curated public commit
  `fbdf071` (public and private histories diverge by design).
- 2026-07-17/18 — Governed run `e7bbd28465b5`
  (`sysdiff_complete_release_documentation_set`) completed the root release
  documentation set: authored HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP,
  and STATUS; reconciled README, CHANGELOG, architecture, and `man/sysdiff.1`
  against implemented behavior without running compilers or the full quality
  gate in the documentation-writing steps. Repair step corrected FILES
  open-mode wording, SIGPIPE/Linux support distinction, ownership notes,
  Valgrind-skip/`/dev/full`/`LC_ALL=C`/`SYSDIFF_BIN` portability notes, and
  quality-tool prerequisites. User smoke gate passed attempt 1
  (`artifacts/user-smoke/result.json`: `app_started` true,
  `core_flow_completed` true, `start_exit_code` 0, `check_exit_code` 0, empty
  `blocking_errors`). Independent review
  `code-reviews/sysdiff-release-documentation-review.verdict.json` is `pass`
  at the High/Critical threshold with two Low man-page findings (F1 NAME
  `\(em` vs ` \- `; F2 FILES directory open-vs-read wording). Allowlisted
  review check `python3 -m compileall tests/test_check_tools.py` exited 0.
  This cycle verifies documentation accuracy and smoke continuity; it does
  not itself re-execute `make quality` or assert a new product release gate.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` (`sysdiff_first_independent_rc_review_cycle`)
recorded the first independent release-candidate review cycle for `sysdiff`
after closing the mixed-case ordering regression gap (RC-001) in tests and
fixtures. User smoke passed with start/check exit 0 and empty blocking errors;
smoke-bound pytest reported `127 passed in 10.58s`. Independent review
`code-reviews/sysdiff-rc-review-cycle-1.verdict.json` is `pass` (0
Medium/High/Critical, 7 Low F1–F7); allowlisted `python3 -m pytest tests/ -q`
exited 0 with `127 passed in 11.06s`. This cycle does not claim that `sysdiff`
is released or that the mission is complete. A second consecutive review cycle
with no release-blocking findings is still required before mission completion.
