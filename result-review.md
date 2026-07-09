# Result Review

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

## Latest completed work

- Advanced Agent-Orch run `c02d741432d3`,
  `sysdiff_c_source_implementation`, through review and into closeout handoff.
  The run created `docs/sysdiff-c-source-contract.md` and
  `plans/sysdiff-c-source-implementation-plan.md`, then hardened
  `src/sysdiff.c`, `Makefile`, and `README.md` for the C-source slice.
- The implementation now defines deterministic resource limits in
  `src/sysdiff.c`: `SYSDIFF_MAX_LINE_BYTES == 65536` and
  `SYSDIFF_MAX_SNAPSHOT_ENTRIES == 65536`. Over-limit lines and over-limit
  snapshots return exit status `2`, leave stdout empty, and write contextual
  diagnostics to stderr. Blank/comment handling, key validation, duplicate-key
  detection, embedded-NUL rejection, bytewise sorted comparison, and existing
  diff formats remain in place.
- The parser now uses typed `LineStatus` and `AppendStatus` results plus a
  single `parse_snapshot` cleanup block. The current review found no
  memory-ownership findings: snapshot ownership is explicit, cleanup frees
  resources correctly, `snapshot_free` is idempotent, and no partial diff output
  occurs on parse errors.
- `Makefile` now exposes `sysdiff`, `test-suite`, `sanitizer-test`,
  `valgrind-test`, and `make-quality`. `make sanitizer-test` provides
  ASan/UBSan coverage with `clang` when available. `make-quality` runs a clean
  GCC rebuild before Valgrind so the aggregate sequence avoids the sanitizer
  binary conflict described in review finding F003.
- Completed governed smoke for run `c02d741432d3` at
  `step_07_user_smoke_gate`, attempt 1. The canonical
  `artifacts/user-smoke/result.json` records `app_started: true`,
  `core_flow_completed: true`, `check_exit_code: 0`, and no blocking errors.
  The copied smoke evidence lives under
  `artifacts/user-smoke/attempt-1-manifest-smoke-20260709T113203Z/`.
  The explicit manifest-steps replay also passed:
  `artifacts/user-smoke/manifest-steps-result.json` records
  `steps_completed: 4`, `steps_total: 4`, `core_flow_completed: true`, and no
  blocking errors, with detailed per-step logs under
  `artifacts/user-smoke/attempt-1-manifest-steps-20260709T113236Z/`.
- Completed review for the C-source hardening slice. Verdict file
  `code-reviews/review-sysdiff-c-source.verdict.json` reports `pass` at a High
  severity threshold, with no High or Critical findings.
- The C-source review left three open findings: F001 Medium for missing tests
  covering CRLF-vs-LF equivalence plus line-length and entry-count limit
  failures; F002 Low for a one-byte CRLF/LF discrepancy at the line-length
  boundary; and F003 Medium for standalone `make valgrind-test` being
  unreliable immediately after `make sanitizer-test`.
- Review checks for `c02d741432d3` were `python3 -m compileall src/ tests/`,
  `make clean && make CC=gcc`, `make clean && make CC=clang`, `make test`,
  `python3 -m pytest tests/test_sysdiff.py -v`, `make sanitizer-test`, and
  `make clean && make CC=gcc && make valgrind-test`; all exited `0`.
- Closeout handoff for run `c02d741432d3` is complete. Attempt 1 of
  `step_09_closeout_handoff_docs` retried because the handoff summarized the
  older `review-sysdiff-core.verdict.json`, omitted current findings F002 and
  F003, and described memory-ownership and sanitizer issues that the current
  verdict does not report. Attempt 2 corrected the handoff and Agent-Orch now
  records the run as `COMPLETED`.
- Re-ran the canonical user smoke manifest manually on 2026-07-09 per
  Agent-Orch note. Fresh attempt-2 evidence under
  `artifacts/user-smoke/attempt-2-manifest-smoke-20260709T121723Z/` records
  `app_started: true`, `core_flow_completed: true`, `check_exit_code: 0`, and
  no blocking errors. Fresh explicit step replay evidence under
  `artifacts/user-smoke/attempt-2-manifest-steps-20260709T121723Z/` records
  `steps_completed: 4`, `steps_total: 4`, `core_flow_completed: true`, and no
  blocking errors.
- The previous governed run `5ff82aa95e06`,
  `sysdiff_fixture_smoke_repair`, completed closeout. It changed only
  `tests/smoke_manifest.json` and `tests/test_sysdiff_fixture.sh`, passed
  smoke and review, and resolved prior smoke-fixture findings F-001 Medium and
  F-002 Low by enforcing exact diff order and stronger diff-line checks.
- The previous routed tool-availability run `b6deb04a6055` added
  `scripts/check_tools.py`, tests, docs, and README discoverability for the
  default `codex_cli` and `claude_code` harness checks. Its review verdict
  `code-reviews/review-tool-availability-check.verdict.json` reports `pass` at
  a High severity threshold with two Low findings still open; `flake8` was not
  installed in that review environment and `ruff` passed as equivalent lint
  coverage.
- Earlier `sysdiff` core history remains relevant but is partially superseded
  by `c02d741432d3`: the old hidden `fail_parse` ownership issue is no longer
  an open finding in the latest C-source review, and sanitizer coverage is now
  available through `make sanitizer-test`. The older changed-line ambiguity
  finding for values containing ` -> ` remains outside the hardening slice and
  is still visible for future output-format work.

## Verification

- `python3 -m compileall src/ tests/`
- `make clean && make CC=gcc`
- `make clean && make CC=clang`
- `make test`
- `python3 -m pytest tests/test_sysdiff.py -v`
- `make sanitizer-test`
- `make clean && make CC=gcc && make valgrind-test`
- Agent-Orch `SmokeTestAdapter` governed run for
  `step_07_user_smoke_gate` attempt 1 against `tests/smoke_manifest.json`;
  evidence: `artifacts/user-smoke/result.json` and
  `artifacts/user-smoke/attempt-1-manifest-smoke-20260709T113203Z/`
- Explicit replay of all four `tests/smoke_manifest.json` `steps` entries;
  evidence: `artifacts/user-smoke/manifest-steps-result.json` and
  `artifacts/user-smoke/attempt-1-manifest-steps-20260709T113236Z/`
- Manual replay of `tests/smoke_manifest.json` on 2026-07-09:
  `artifacts/user-smoke/result.json`,
  `artifacts/user-smoke/attempt-2-manifest-smoke-20260709T121723Z/`,
  `artifacts/user-smoke/manifest-steps-result.json`, and
  `artifacts/user-smoke/attempt-2-manifest-steps-20260709T121723Z/`
- Prior fixture-smoke repair verification from run `5ff82aa95e06`:
  `python3 -m pytest tests/ -x -q`, `python3 -m compileall tests/`, and
  `BLACK_NUM_WORKERS=1 python3 -m black --check --workers 1
  tests/check_sysdiff_smoke.py tests/smoke_start.py`
