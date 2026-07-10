# Review: sysdiff Fixture Acceptance Tests

Scope: `src/sysdiff.c`, `Makefile`, `tests/test_sysdiff.sh`,
`tests/test_sysdiff_fixture.sh`, `tests/test_sysdiff.py`,
`tests/smoke_manifest.json`, `tests/smoke_start.py`,
`tests/check_sysdiff_smoke.py`, `scripts/smoke.sh`, `README.md`, and
`artifacts/user-smoke/result.json`.

Contract baseline: `docs/sysdiff-fixture-slice-contract.md` and
`docs/sysdiff-fixture-slice-plan.md`, with durable key syntax from
`docs/sysdiff-snapshot-format-and-scope.md`.

## Checks Run

`python3 -m pytest tests/ -q` — observed exit code **0**. All 26 tests
collected and passed in 0.40 s across `tests/test_sysdiff.py` (help/version,
changed/identical/ordering comparisons, nine parametrized malformed-input
cases, after-path partial-diff prevention, embedded NUL, missing-file and
directory errors, and `file.` keys treated as opaque data) and
`tests/test_check_tools.py`. Zero failures, errors, or skips.

User-smoke evidence under `artifacts/user-smoke/result.json` records
`app_started: true`, `core_flow_completed: true`, `check_exit_code: 0`, and
empty `blocking_errors`, with `start_exit_code: -15` (SIGTERM) consistent with
the start-helper timeout mismatch noted under Lens Notes. The latest
`artifacts/user-smoke/check.log` shows the smoke path exercising `make test`
through the full quality aggregate, including shell fixture acceptance and the
same pytest suite.

## Lens Notes

### C quality, ownership, and undefined behavior

`src/sysdiff.c` remains a single auditable translation unit with separable
`read_line`, `parse_snapshot`, `emit_diff`, and `compare_snapshots` helpers.
Ownership is explicit: every key/value is heap-owned inside `struct Snapshot`,
`snapshot_free` nulls fields after free, and `parse_snapshot` routes all
failure paths through one `goto cleanup` that closes the FILE and frees the
partial snapshot. Diff output is emitted only after both snapshots parse and
sort successfully, so error paths leave stdout empty.

No undefined behavior was identified on the reviewed paths. `main` guards
`argc < 1` before any `argv[1]` use. Embedded NUL is rejected before bytes are
stored as C strings. Capacity growth checks reject wraparound before
`realloc`. The `(char)ch` store is reached only for non-NUL, non-EOF bytes.
`qsort` + adjacent duplicate detection gives deterministic key order.

One Low finding: `copy_range` still carries an unreachable
`len > SIZE_MAX - 1` guard even though both call sites are bounded by
`SYSDIFF_MAX_LINE_BYTES` (F004).

### Portability and diagnostics

The reader uses `fgetc` rather than POSIX `getline`, opens fixtures in binary
mode (`"rb"`), and strips a single trailing CR after LF removal, matching the
CRLF contract. Only C17 library calls appear. Fixture tests force `LC_ALL=C`
so byte-order expectations stay locale-stable.

Diagnostics go to stderr with enough context for every status-2 class covered
by the harness: path + `strerror` on open/close failure, path + 1-based line
for parse/NUL/limit failures, path + key for duplicates, and the offending
token for unknown commands / compare arity errors. Shell and pytest suites
assert empty stdout plus contextual stderr fragments rather than brittle full
message equality, which matches the plan.

### Deterministic fixture coverage and test quality

`tests/test_sysdiff_fixture.sh` covers the contract acceptance matrix:
status 0/1/2, exact sorted stdout for mixed add/remove/change (including
spaces, empty values, inline `#`, and `=` inside values), ordering
independence across differently ordered fixtures, comments/blank lines, CRLF
and mixed-ending equivalence, line/entry resource limits (entry-limit skipped
under Valgrind for runtime), and empty stdout on every error path including
malformed after-path cases. `tests/test_sysdiff.sh` keeps informational
command checks, asserts no-argument help success (exit 0 + usage), and
invokes the fixture suite so `make test` / smoke inherit coverage.

Medium gap: `tests/test_sysdiff.py` hardcodes `gcc` in the session fixture, so
pytest fails at setup on gcc-absent hosts even when `cc`/`clang` and the
Makefile path work (F001). Low gap: whitespace-only lines are rejected as
malformed (`missing '='`) while the fixture-slice contract says blank lines
are ignored; tests currently encode the reject behavior (F003).

### Smoke integrity and maintainability

`scripts/smoke.sh` remains the unchanged oracle (`make test`). Because
`test` aliases `quality`, smoke fails closed when any compiler, format,
static-analysis, shell, pytest, sanitizer, or Valgrind stage fails.
`tests/check_sysdiff_smoke.py` re-invokes that oracle. Manifest step
`tests/test_sysdiff_fixture.sh` adds a direct fixture replay.

Medium finding: `tests/smoke_start.py` sleeps 30 s while
`startup_timeout_seconds` is 10, so the governed start helper is SIGTERM'd
(`start_exit_code: -15` in user-smoke evidence) even though the later check
path still completed in recorded runs (F002).

Maintainability is otherwise strong: named limits, typed status enums, no
global mutable state, and README documents compare usage, fixture format, and
exit statuses without promising live capture. `Makefile` `valgrind-test` now
cleans and rebuilds with strict GCC flags before Valgrind, closing the older
sanitizer-binary reuse hazard for standalone invocation.
