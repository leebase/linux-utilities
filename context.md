# Context

## Snapshot

Mode: 2. This repository uses AgentFlow memory plus governed Agent-Orch
execution launched by the `linux-utilities` auto-orch mission. The current
product focus is a small, auditable C utility suite; the first utility is
`sysdiff`.

The latest governed slice is Agent-Orch run `c02d741432d3`,
`sysdiff_c_source_implementation`. It hardens the current
`sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT` C implementation while
preserving the explicit snapshot-only scope. The run has passed contract,
planning, existing-test validation, implementation, documentation, repair and
verification, user smoke, review, and closeout. It is now `COMPLETED` in
Agent-Orch evidence after `step_09_closeout_handoff_docs` attempt 2 fixed the
attempt 1 handoff mismatch.

The slice added the contract `docs/sysdiff-c-source-contract.md` and delivery
plan `plans/sysdiff-c-source-implementation-plan.md`. Implementation changed
`src/sysdiff.c` and `Makefile`; documentation changed `README.md`. The C source
now defines deterministic resource limits:
`SYSDIFF_MAX_LINE_BYTES == 65536` and
`SYSDIFF_MAX_SNAPSHOT_ENTRIES == 65536`. It rejects over-limit lines and
over-limit snapshots with exit status `2`, empty stdout, and contextual stderr.
Parsing now uses typed line and append statuses plus a single cleanup block in
`parse_snapshot`; review found no memory-ownership defects. `Makefile` now has
`sysdiff`, `test-suite`, `sanitizer-test`, `valgrind-test`, and
`make-quality` targets. ASan/UBSan coverage is available through
`make sanitizer-test` when `clang` is present.

The latest review verdict is
`code-reviews/review-sysdiff-c-source.verdict.json`. It reports `pass` at a
High severity threshold, with no High or Critical findings. Three findings
remain open and must be carried forward honestly:

- F001, Medium: missing tests for CRLF-vs-LF equivalence and the line-length
  and entry-count limit error paths.
- F002, Low: CRLF-terminated lines effectively allow one fewer data byte than
  LF-terminated lines at the `SYSDIFF_MAX_LINE_BYTES` boundary.
- F003, Medium: standalone `make valgrind-test` is unreliable immediately after
  `make sanitizer-test` because the sanitizer target leaves an ASan-instrumented
  binary in `build/`; `make-quality` avoids this with a clean GCC rebuild.

Review checks passed: `python3 -m compileall src/ tests/`,
`make clean && make CC=gcc`, `make clean && make CC=clang`, `make test`,
`python3 -m pytest tests/test_sysdiff.py -v`, `make sanitizer-test`, and
`make clean && make CC=gcc && make valgrind-test`.

The governed user smoke gate for run `c02d741432d3`,
`step_07_user_smoke_gate`, passed on attempt 1. The canonical
`artifacts/user-smoke/result.json` records `app_started: true`,
`core_flow_completed: true`, `check_exit_code: 0`, and no blocking errors. The
explicit manifest-steps replay also passed with `steps_completed: 4`,
`steps_total: 4`, and no blocking errors. Evidence paths are
`artifacts/user-smoke/attempt-1-manifest-smoke-20260709T113203Z/` and
`artifacts/user-smoke/attempt-1-manifest-steps-20260709T113236Z/`.

Manual user-smoke replays requested by Agent-Orch notes on 2026-07-09 also
passed against `tests/smoke_manifest.json`. Fresh attempt-2 evidence is under
`artifacts/user-smoke/attempt-2-manifest-smoke-20260709T121723Z/` and
`artifacts/user-smoke/attempt-2-manifest-steps-20260709T121723Z/`. The latest
`artifacts/user-smoke/result.json` records `app_started: true`,
`core_flow_completed: true`, `check_exit_code: 0`, and no blocking errors; the
latest `artifacts/user-smoke/manifest-steps-result.json` records
`steps_completed: 4`, `steps_total: 4`, `core_flow_completed: true`, and no
blocking errors.

The previous completed governed slice is run `5ff82aa95e06`,
`sysdiff_fixture_smoke_repair`. It completed closeout and resolved the prior
smoke-fixture findings by making fixture diff order exact and strengthening
diff-line shape checks. Older runs remain relevant for history and open
findings, but `c02d741432d3` is now the latest reviewed product slice.

Lee approved the current diff output format on 2026-07-09:
`+ key=value`, `- key=value`, and `~ key: old -> new`. Treat that as the
format-1 contract unless Lee explicitly changes it later. Lee also approved
keeping and committing the current overnight work on `main`, and required a C
craftsmanship review before selecting any more feature work.

## What's Happening Now

Run `c02d741432d3` is `COMPLETED` in Agent-Orch evidence. Closeout attempt 1
changed only `context.md`, `result-review.md`, `sprint-plan.md`, and
`WHERE_AM_I.md`, but semantic validation retried because `context.md`
summarized the older `review-sysdiff-core.verdict.json` instead of the current
`review-sysdiff-c-source.verdict.json`, omitted F002 and F003, and incorrectly
implied that memory ownership and sanitizer coverage remained open issues in
the current verdict. Attempt 2 corrected the handoff and passed.

Do not claim release readiness from this slice. The code-producing work passed
the High-severity review gate, smoke passed, and sanitizer/Valgrind checks ran
successfully in the reviewed sequences, but Medium findings F001 and F003 and
Low finding F002 remain open.

The next governed action must be a C craftsmanship review before any new
feature slice. That review should inspect `src/sysdiff.c`, `Makefile`, tests,
smoke manifest, and docs for C quality, ownership, undefined behavior,
portability, diagnostics, and maintainability. It should at minimum address the
current C-source review findings in this order:

1. Add focused tests for CRLF-vs-LF equivalence, line-too-long failure, and
   too-many-entries failure to resolve F001.
2. Decide whether to fix or explicitly document the CRLF line-limit boundary
   discrepancy from F002.
3. Make standalone `make valgrind-test` robust after `make sanitizer-test`, or
   document the invocation constraint clearly enough to resolve F003.

After the current slice is closed out or repaired, return to infrastructure
cleanup: complete Agent-Orch closeout validation for run `b6deb04a6055` or
resolve its two Low tool-availability findings. Older documentation findings
also remain visible: the snapshot-format decision review F001 says
`docs/snapshot-format-decision.md` understates the allowed key byte set, and
the earlier minimal harness review F-01 says the `~ key: old -> new` format is
ambiguous when values contain ` -> `. Preserve explicit-snapshot-only scope and
do not add live system capture, package-manager integration, service probing,
persistence, networking, or background behavior in the next `sysdiff` slice.

Runs root: `/home/lee/projects/linux-utilities-agent-orch-runs`.
