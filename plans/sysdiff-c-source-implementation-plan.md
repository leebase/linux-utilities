# sysdiff C Source Implementation Plan

## Scope

Implement the hardening slice described by
`docs/sysdiff-c-source-contract.md` while preserving the explicit snapshot-only
contract in `docs/sysdiff-snapshot-format-and-scope.md`.

The slice remains centered on `src/sysdiff.c`. It may update `Makefile`,
`README.md`, and tests in their governed steps, but must not add runtime
dependencies, background behavior, persistence, networking, live system
capture, package/service probing, or additional executables.

## Architecture

1. **Define deterministic resource limits in `src/sysdiff.c`.**
   Add compile-time constants near the data structures:
   `SYSDIFF_MAX_LINE_BYTES = 65536` and
   `SYSDIFF_MAX_SNAPSHOT_ENTRIES = 65536`.
   The line limit applies to one logical snapshot line before line-ending
   removal. No input may be silently truncated.

2. **Make line-reading failures typed.**
   Extend `enum LineStatus` with separate statuses for embedded NUL, line too
   long, file/read error, and allocation error. Keep `read_line` responsible
   only for reading one line, enforcing `SYSDIFF_MAX_LINE_BYTES`, and returning
   enough status for `parse_snapshot` to print contextual diagnostics.

3. **Enforce entry-count limits before growth.**
   Update snapshot append logic so a snapshot with more than
   `SYSDIFF_MAX_SNAPSHOT_ENTRIES` accepted records fails before appending the
   extra entry. Keep allocation overflow and `realloc` checks intact.

4. **Keep full validation before output.**
   Preserve `compare_snapshots` behavior: parse and validate both snapshots,
   sort and duplicate-check both maps, and only then call `emit_diff`.
   Resource-limit, malformed-input, duplicate-key, file I/O, close, allocation,
   and NUL failures must all return before stdout is written.

5. **Make cleanup ownership explicit.**
   Replace hidden `fail_parse` ownership semantics with either:
   `parse_fail_and_return_consuming(FILE *file, struct Snapshot *snapshot, ...)`
   plus a short ownership comment, or a single-exit cleanup block inside
   `parse_snapshot`. Prefer the single-exit cleanup block if it keeps the code
   smaller and makes ownership easier to audit.

6. **Preserve output and command surface.**
   Do not change `--help`, `--version`, `compare` argument validation, sorted
   diff output, `+ key=value`, `- key=value`, `~ key: old -> new`, or
   `no changes`. The older changed-line ambiguity remains out of scope for this
   hardening slice unless a later contract changes the output format.

7. **Expose sanitizer verification without weakening strict builds.**
   Keep default `CFLAGS` at strict C17 warning-as-error coverage. Validate the
   existing `sanitizer-test` target or adjust it so ASan/UBSan coverage is
   available through `make sanitizer-test`, with an explicit diagnostic if the
   local compiler cannot provide the sanitizer flags.

8. **Document user-visible limits.**
   Update `README.md` in the documentation step to name the exact line and
   entry limits, the exit status `2` behavior, empty stdout on compare errors,
   and the continued explicit-snapshot-only scope.

## Tests

1. **Preserve existing behavior tests.**
   Keep the current pytest and shell fixture coverage for added, removed,
   changed, no-change, empty values, spaces and `#` in values, extra `=` in
   values, sorted output, missing files, directory paths, usage errors,
   malformed lines, invalid keys, duplicate keys, embedded NUL bytes, and no
   partial stdout on parse errors.

2. **Add line-limit acceptance tests.**
   Add tests that build a valid snapshot with a logical line exactly
   `SYSDIFF_MAX_LINE_BYTES` bytes long and confirm it is accepted, then a
   snapshot whose next line exceeds the limit and confirm exit status `2`,
   empty stdout, and stderr naming the line limit and path or line context.

3. **Add entry-limit acceptance tests.**
   Add tests that generate exactly `SYSDIFF_MAX_SNAPSHOT_ENTRIES` valid unique
   records and confirm comparison succeeds, then add one more valid unique
   record and confirm exit status `2`, empty stdout, and stderr naming the
   entry limit and affected snapshot.

4. **Strengthen partial-output error tests.**
   Add or extend tests so allocation/read-style errors where practical,
   malformed input, duplicate keys, embedded NUL bytes, line-limit failures,
   and entry-limit failures all assert stdout is empty. For true allocation
   failure, keep coverage to code review/static analysis unless a portable test
   mechanism exists.

5. **Add CRLF-vs-LF fixture coverage.**
   Add a pytest fixture that writes equivalent snapshots with `\r\n` and `\n`
   line endings, runs the same comparison, and asserts identical stdout,
   stderr, and exit status.

6. **Add sanitizer-path coverage.**
   Ensure either pytest can build/run with ASan+UBSan when requested or
   `make sanitizer-test` is the documented sanitizer path. The test step should
   record a clear skip/diagnostic when the selected compiler lacks sanitizer
   support.

7. **Update shell smoke only when needed.**
   Keep `make test` and `scripts/smoke.sh` as the stable smoke entrypoints.
   Extend `tests/test_sysdiff_fixture.sh` only if shell-level coverage is
   needed for resource-limit or CRLF behavior beyond pytest.

## Verification

Run and record these commands after implementation:

1. `make clean`
2. `make`
3. `make test`
4. `./scripts/smoke.sh`
5. `python3 -m pytest tests/ -x -q`
6. `make sanitizer-test`
7. `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 -o /tmp/sysdiff-clang src/sysdiff.c`
   when `clang` is available; otherwise record that `clang` is unavailable.
8. `make clean && make CC=gcc CFLAGS="-std=c17 -Wall -Wextra -Wpedantic -Werror -O2"`

Optional release-quality checks to run when tools are available:

1. `make valgrind-test`
2. `cppcheck --enable=warning,style,performance,portability --std=c17 src/sysdiff.c`
3. `scan-build make clean all`
4. `clang-tidy src/sysdiff.c -- -std=c17`

Unavailable optional tools should be recorded as environment limitations, not
as product behavior changes.

## Acceptance Mapping

| ID | Contract acceptance check | Concrete plan item |
| --- | --- | --- |
| AC-01 | `sysdiff compare` still reports added, removed, changed, and no-change snapshots with documented stdout formats and exit statuses `0`, `1`, and `2`. | Architecture 4 and 6 preserve parse-before-output and existing formats; Tests 1 preserves current behavior fixtures; Verification 2-5 run build, smoke, and pytest. |
| AC-02 | Valid snapshots at or below the documented line-length and entry-count limits are accepted. | Architecture 1 defines exact limits; Tests 2 and 3 include at-limit accepted fixtures; Verification 5 runs them. |
| AC-03 | A snapshot line longer than the defined maximum fails with exit status `2`, empty stdout, and stderr naming the exceeded line limit or affected snapshot. | Architecture 2 adds typed line-too-long handling; Tests 2 asserts status, stdout, and diagnostic; Verification 5 runs it. |
| AC-04 | A snapshot with more than the defined maximum entries fails with exit status `2`, empty stdout, and stderr naming the exceeded entry limit or affected snapshot. | Architecture 3 enforces the append limit before growth; Tests 3 asserts status, stdout, and diagnostic; Verification 5 runs it. |
| AC-05 | Allocation, file I/O, malformed input, duplicate keys, embedded NUL bytes, and resource-limit failures all avoid partial diff output. | Architecture 4 keeps output after full validation only; Tests 1 and 4 assert empty stdout across these failure classes; Verification 3-5 run smoke and pytest. |
| AC-06 | Parse-error cleanup ownership is obvious and no caller uses resources after cleanup ownership transfer. | Architecture 5 refactors cleanup to explicit ownership; code review checks this structurally after implementation. |
| AC-07 | Tests or smoke coverage confirm CRLF-terminated snapshots compare the same as equivalent LF-terminated snapshots. | Tests 5 adds CRLF-vs-LF fixture; Verification 5 runs it. |
| AC-08 | ASan/UBSan coverage is available through the test build or documented Makefile target, with clear skip or diagnostic path if unavailable. | Architecture 7 validates or adjusts `make sanitizer-test`; Tests 6 covers the sanitizer path; Verification 6 runs it. |
| AC-09 | `make clean`, `make`, `make test`, and `./scripts/smoke.sh` pass after implementation. | Verification 1-4 are the required commands. |
| AC-10 | A strict Clang build is run when `clang` is available, or unavailability is recorded. | Verification 7 runs strict Clang or records the missing tool. |
| AC-11 | Documentation names any new resource limits and continues to state explicit snapshot-only scope. | Architecture 8 updates README with limits and scope; code review confirms wording. |

## Risks

1. **Boundary ambiguity.**
   Line-limit tests must match the implementation definition exactly. The
   implementation should document whether the limit counts bytes before or
   after line-ending removal and keep diagnostics consistent with that wording.

2. **Large generated fixtures.**
   At-limit entry tests with 65,536 records are large enough to slow tests if
   repeated. Generate them in one focused pytest case and avoid duplicating the
   same fixture in shell smoke unless necessary.

3. **Sanitizer environment instability.**
   ASan leak detection can fail under ptrace-based harnesses. Keep
   `ASAN_OPTIONS=detect_leaks=0:abort_on_error=1` and
   `UBSAN_OPTIONS=halt_on_error=1` for the smokeable sanitizer target, and
   record missing compiler/runtime support explicitly.

4. **Cleanup refactor regressions.**
   Moving from hidden helper cleanup to explicit cleanup can introduce leaks or
   double frees if ownership is not centralized. Keep `snapshot_free`
   idempotent, make each return path obvious, and use sanitizer and Valgrind
   checks where available.

5. **Scope creep.**
   Do not use this slice to fix the older changed-line ambiguity, add new
   snapshot formats, interpret resource prefixes, read `file.` paths, or start
   live collection. Those require separate contracts.
