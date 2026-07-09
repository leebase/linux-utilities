# Code Review: sysdiff Fixture Slice

**Branch / commit under review:** `main` (post-fixture-slice implementation)
**Reviewer:** Agent-Orch step_08_review_verified_slice
**Date:** 2026-07-07
**Verdict:** FAIL — one High finding (smoke oracle gap)

---

## Checks Run

`python3 -m compileall scripts` — exit 0. The `scripts/` directory contains only shell scripts; no Python source files are present, so the check finds nothing to compile and exits cleanly.

**Prior build and smoke evidence (discussed here, not in checks_run):**
`artifacts/user-smoke/result.json` records `./scripts/smoke.sh` at exit status 0 (pass, attempt-2-user-smoke-oracle). The oracle confirmed its own sha256 digests for `scripts/smoke.sh`, `Makefile`, `tests/test_sysdiff.sh`, and `tests/test_sysdiff_fixture.sh` matched before and after the run. However, as Finding F001 below explains, the smoke oracle's "pass" is misleading: `./scripts/smoke.sh` delegates to `make test`, `make test` runs only `tests/test_sysdiff.sh`, and `tests/test_sysdiff.sh` never invokes `tests/test_sysdiff_fixture.sh`. The smoke gate passed without exercising any fixture comparison logic.

---

## Lens Notes

### Correctness

**Finding F001 (High):** `make test` and the smoke oracle never run the fixture tests. See [Test Adequacy](#test-adequacy) for detail; the correctness impact is that no automated gate validates the compare command, the diff output format, error exits, partial-output prevention, or duplicate-key detection.

All other correctness points pass review:

- **Exit codes** — `main` returns 0 for informational commands and identical snapshots, 1 for found differences, 2 for all error paths. This matches the three-class contract exactly.
- **Diff output format** — `emit_diff` uses `"- %s=%s\n"`, `"+ %s=%s\n"`, and `"~ %s: %s -> %s\n"`. Each matches the contract's exact prefix and punctuation.
- **"no changes" path** — `puts("no changes")` fires only when `changed` is false after the merge walk. `puts` appends a newline, so stdout is exactly `"no changes\n"` as required.
- **CRLF handling** — after stripping `\n`, the code strips a trailing `\r` in a separate check. Both `\n`-only and `\r\n` line endings are handled.
- **Sorted output** — `qsort` with `compare_entries_by_key` (which delegates to `strcmp`, which uses unsigned-char byte order per C17 7.24.4.2) sorts each snapshot before the merge walk, making output order independent of fixture input order.
- **Partial output prevention** — `compare_snapshots` calls `parse_snapshot` for both files before calling `emit_diff`, and returns early on the first parse failure. No diff output can precede a parse error.
- **NUL byte rejection** — `read_line` returns `LINE_INVALID` on `ch == '\0'`, preventing embedded NUL bytes from silently truncating key or value strings.
- **Empty value** — `copy_range(separator + 1, 0)` returns a one-byte allocation containing `'\0'`, correctly representing an empty value. Empty keys are rejected by `separator == line`.
- **Duplicate-key detection** — adjacent-key comparison after sort correctly identifies all duplicates and reports the offending key and path to stderr.
- **Line number reporting** — `LINE_INVALID` and `LINE_ERROR` are detected before `line_no++` so the message uses `line_no + 1`; the separator-missing case is detected after `line_no++` so it uses `line_no` directly. Both are correct.

### Security

No vulnerabilities found.

- All `fprintf`/`printf` calls use fixed format strings; user-controlled strings are always passed as `%s` arguments, not as format arguments.
- `fopen(path, "rb")` opens in binary mode, avoiding any platform line-ending translation that could corrupt key/value byte content.
- NUL byte rejection at the `read_line` layer prevents a class of input that could confuse C-string operations on keys and values.
- Dynamic line growth uses `realloc` with overflow guards; no fixed-size stack buffer is used for line content.
- The `snapshot_append` overflow guard checks both `new_cap <= cap` (wrap-around) and `new_cap > SIZE_MAX / sizeof(items[0])` (element-count overflow) before `realloc`.

### Memory Ownership

All allocation paths are paired with free calls; no leaks or double-frees were found.

- `parse_snapshot` calls `snapshot_free` on every early-return path: `LINE_INVALID`, `LINE_ERROR`, malformed separator, `copy_range` failure, `snapshot_append` failure, duplicate-key detection, and `fclose` failure.
- When `copy_range` returns `NULL` for key or value, both `key` and `value` are freed before returning. When `snapshot_append` returns false, ownership of `key` and `value` has not transferred (the comment at line 132 makes this explicit) so the caller frees them.
- `compare_snapshots` calls `snapshot_free(&before)` when the second `parse_snapshot` fails, and calls both `snapshot_free` calls when `emit_diff` returns.
- `read_line` frees the accumulation buffer on `LINE_ERROR`, `LINE_INVALID`, and (the `len == 0`) `LINE_EOF` paths, and transfers ownership to the caller only on `LINE_OK`.

**Finding F002 (Low):** The `copy_range` guard `if (len == (size_t)-1) return NULL` at line 38 is unreachable dead code. Both call sites pass derived sizes (`key_len` and `value_len`) that are bounded by the dynamically allocated line buffer, which itself cannot reach `SIZE_MAX` bytes due to the overflow guards in `read_line`. The guard does not cause incorrect behavior, but it implies to a reader that callers may pass `SIZE_MAX` as a sentinel, which they do not, and it makes allocation-failure `NULL` indistinguishable from sentinel-triggered `NULL`. It should be removed.

### Undefined Behavior

No undefined behavior was found.

- `(char)ch` at line 92: `ch` is confirmed to be in [1, 255] by the prior `EOF` and `'\0'` checks. On platforms where `char` is signed, bytes 128–255 become negative `char` values, but these are stored and later compared via `strcmp`, which is defined to treat characters as `unsigned char` (C17 7.24.4.2). Sort order is therefore correct unsigned-byte order regardless of whether `char` is signed.
- `(size_t)(separator - line)` at line 210: `separator > line` is guaranteed by the `separator == line` rejection at line 202, so the `ptrdiff_t` is positive and the cast to `size_t` is safe.
- `cap - len` at line 76: `cap` and `len` are both `size_t`. When `cap == 0` and `len == 0`, the subtraction is `0`, which is `<= 1`, triggering correct growth before the first write. `len` can only be non-zero after at least one successful `realloc`, so `len <= cap` is maintained as an invariant.
- `cap * 2` at line 77: overflow is caught by `new_cap <= cap` immediately after.
- `new_cap * sizeof(*new_items)` at line 122 in `snapshot_append`: overflow is caught by `new_cap > (size_t)-1 / sizeof(snapshot->items[0])` immediately before.

### CLI Behavior

Exit codes and argument dispatch match the contract for all documented forms.

- `argc == 1`: prints usage to stdout, returns 0. Contract: "No arguments keeps the current non-error help behavior." ✓
- `sysdiff --help`: prints usage to stdout (mentions `compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`), returns 0. ✓
- `sysdiff --version`: prints `sysdiff 0.1.0` to stdout, returns 0. ✓
- `sysdiff compare BEFORE AFTER`: full dispatch path. ✓
- `sysdiff compare` (missing both paths) / `sysdiff compare BEFORE` (missing one): caught by `argc != 4`, stderr diagnostic, returns 2. ✓
- `sysdiff unknown-command`: falls to unknown-command handler, stderr includes the argument, returns 2. ✓

Minor behavioral note (no contract violation): `sysdiff --help extra-arg` (argc=3) reaches the unknown-command handler because the `--help` check requires `argc == 2`. The user sees `"unknown command: --help"`, which is confusing. The contract does not specify behavior for `--help` with extra arguments, so this is not a defect but is worth noting for future polish.

### Maintainability

The static-helper boundaries (`parse_snapshot`, `emit_diff`, `compare_snapshots`) match the separability direction in `architecture.md`. Each boundary has a single responsibility and a clear ownership contract.

**Finding F002 (Low):** The dead SIZE_MAX guard in `copy_range` (described under Memory Ownership) lightly obscures the function's contract. Removing it would make the function's actual invariants clearer.

Otherwise: no unnecessary abstractions, no global mutable state, no heap-allocated objects outlive their enclosing function frame except snapshot entries explicitly owned by `Snapshot`. The `print_usage` function serves both `--help` and error diagnostic paths, avoiding duplication. Enum `LineStatus` names are clear. Comments appear only where ownership transfer is non-obvious (line 132).

### Test Adequacy

**Finding F001 (High):** The fixture test suite (`tests/test_sysdiff_fixture.sh`) is not invoked by `make test` or by `./scripts/smoke.sh`.

The `Makefile` `test` target runs only `./tests/test_sysdiff.sh` (Makefile line 13). `tests/test_sysdiff.sh` runs only two `--help` and `--version` checks and does not invoke `tests/test_sysdiff_fixture.sh`. The smoke oracle delegates to `make test`. The result is that the smoke gate can report "pass" even if the entire compare path, the diff output format, all error exits, partial-output prevention, and duplicate-key detection are completely broken.

The plan and contract both state explicitly: "Update `tests/test_sysdiff.sh` to keep the existing informational command checks and invoke `tests/test_sysdiff_fixture.sh`, so `make test` and the unchanged smoke script cover the new slice." This step was not completed.

The README acknowledges the gap indirectly by listing `bash tests/test_sysdiff_fixture.sh` as a separate manual command outside `make test`.

**Fix:** Add `"$ROOT/tests/test_sysdiff_fixture.sh"` at the end of `tests/test_sysdiff.sh`.

Within `test_sysdiff_fixture.sh` itself (assuming it is ever reached), the coverage is solid:
- Changed comparison with all four key states (unchanged, added, removed, changed) and exact stdout match. ✓
- Identical comparison with exact `"no changes\n"` stdout. ✓
- Missing file: exit 2, empty stdout, stderr contains path. ✓
- Wrong argument count (too few): exit 2, empty stdout, non-empty stderr. ✓
- Unknown command: exit 2, non-empty stderr containing the command. ✓
- Malformed fixture (missing separator): exit 2, empty stdout, stderr contains path. ✓
- Duplicate key: exit 2, empty stdout, stderr contains path and key. ✓
- Comments and blank lines: covered in before/after fixtures. ✓
- Empty value (added and removed): `added.empty=` and `removed.empty=` in fixtures. ✓
- Input-order independence: before/after fixtures are intentionally not sorted; expected output is sorted. ✓

**Finding F003 (Low):** Only the too-few-arguments case is tested (`sysdiff compare "$before"`, argc=3). The too-many-arguments case (`sysdiff compare a b c d`, argc=5) is not tested. The same `argc != 4` branch covers both, so the gap is minor. A one-line addition would close it.

---

## Summary

The implementation logic is correct, secure, memory-safe, and free of undefined behavior. The diff algorithm, output format, exit codes, CRLF handling, NUL rejection, empty-value handling, duplicate detection, and partial-output prevention all match the contract.

The single blocking issue is that `tests/test_sysdiff.sh` does not invoke `tests/test_sysdiff_fixture.sh`, so `make test` and `./scripts/smoke.sh` never exercise the fixture comparison feature. The smoke gate's "pass" result is therefore not evidence that the new slice works. This must be fixed before the slice can be considered governed-quality.
