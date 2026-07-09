# Where Am I

## Milestone state

- Repository is initialized and committed on `main`.
- AgentFlow docs are present and should be read at session start.
- Agent-Orch scaffold and templates are present.
- Product baseline is intentionally tiny: `sysdiff --help` and `--version` plus
  a strict C build and smoke test.
- Run `fa24bb888cc0` produced the durable documentation contract for the first
  release-oriented `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT` slice. The
  contract is explicit-snapshot-only and lives at
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
  Agent-Orch worker infrastructure. The implementation is
  `scripts/check_tools.py` with tests in `tests/test_check_tools.py`, contract
  and plan docs, operator docs, and README discoverability. The default checks
  are `codex_cli` for `implementation_worker` via `codex` and `claude_code` for
  `slice_reviewer` via `claude`. Closeout validation and two Low review
  findings remain open.
- Run `1a9f7726ff33`, `fix_smoke_manifest_and_rebuild_fixture_tests`, repaired
  the first smoke manifest and fixture suite version, passed smoke and review,
  but ended `FAILED` at closeout because semantic validation repeatedly
  selected unavailable or inaccessible GPT-5.4 routing. Future OpenAI/Codex
  routes should use `gpt-5.5`.
- Run `5ff82aa95e06`, `sysdiff_fixture_smoke_repair`, completed closeout. It
  fixed `tests/smoke_manifest.json` and `tests/test_sysdiff_fixture.sh`, passed
  the governed smoke gate on attempt 1, passed review with no findings, and
  resolved the prior smoke-fixture F-001 Medium and F-002 Low findings.
- The latest governed product slice is run `c02d741432d3`,
  `sysdiff_c_source_implementation`. It added
  `docs/sysdiff-c-source-contract.md` and
  `plans/sysdiff-c-source-implementation-plan.md`, hardened `src/sysdiff.c`,
  updated `Makefile`, documented limits in `README.md`, passed smoke, and
  passed review at the High severity threshold. Agent-Orch now records the run
  as `COMPLETED` after closeout handoff attempt 2.
- `c02d741432d3` defines resource limits of 65536 bytes per snapshot line and
  65536 entries per snapshot. It reports line and entry limit failures with
  exit status `2`, empty stdout, and contextual stderr. It also centralizes
  parse cleanup in `parse_snapshot` and exposes ASan/UBSan coverage through
  `make sanitizer-test` when `clang` is available.
- The latest review verdict is
  `code-reviews/review-sysdiff-c-source.verdict.json`. It is a pass at the
  High threshold, with no High or Critical findings. Open findings are F001
  Medium for missing CRLF and resource-limit tests, F002 Low for the one-byte
  CRLF/LF line-limit boundary discrepancy, and F003 Medium for standalone
  `make valgrind-test` being unreliable immediately after
  `make sanitizer-test`.
- Manual user-smoke replay requested by Agent-Orch note on 2026-07-09 passed
  against `tests/smoke_manifest.json`. Fresh attempt-2 evidence is under
  `artifacts/user-smoke/attempt-2-manifest-smoke-20260709T121723Z/` and
  `artifacts/user-smoke/attempt-2-manifest-steps-20260709T121723Z/`.
- Lee approved the current diff output format on 2026-07-09:
  `+ key=value`, `- key=value`, and `~ key: old -> new`. Future OpenAI/Codex
  routes should use `gpt-5.5`; do not add GPT-5.4 assignments.

## Next milestone

Run a C craftsmanship review before selecting more feature work. The review
must inspect `src/sysdiff.c`, `Makefile`, tests, smoke manifest, and docs for
C quality, ownership, undefined behavior, portability, diagnostics, and
maintainability. Start with F001: add tests for CRLF-vs-LF equivalence,
line-too-long failure, and too-many-entries failure. Then address F002 by
fixing or documenting the CRLF boundary discrepancy, and address F003 by making
`make valgrind-test` reliable after `make sanitizer-test` or documenting its
required clean non-sanitized build precondition.

After the current C-source follow-up is handled, return to infrastructure
cleanup for run `b6deb04a6055` and its two Low tool-availability findings.
Keep older review findings visible while planning follow-up work: the
snapshot-format decision summary still has a Low wording issue around key
syntax, and the previous minimal harness review flagged the changed-line format
`~ key: old -> new` as ambiguous when values contain ` -> `. The current
implementation still uses that changed-line format.

Do not enable the hourly mission or claim release readiness until remaining
governed closeout work is complete and the required quality gates have actually
run cleanly for the release candidate.
