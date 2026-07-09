# Review: sysdiff C Source Slice (Hardening)

**Subject:** `src/sysdiff.c`, `Makefile`, `tests/test_sysdiff.py`, `tests/test_sysdiff_fixture.sh`
**Contract:** `docs/sysdiff-c-source-contract.md`
**Verdict:** pass (severity threshold: High — no High or Critical findings)

---

## Checks Run

| Check | Command | Exit code | Outcome |
|---|---|---|---|
| Python compile | `python3 -m compileall src/ tests/` | 0 | Pass — all .py files byte-compiled clean |
| GCC strict build | `make clean && make CC=gcc` | 0 | Pass — zero warnings at `-Wall -Wextra -Wpedantic -Werror` |
| Clang strict build | `make clean && make CC=clang` | 0 | Pass — zero warnings |
| make test | `make test` | 0 | Pass — shell fixture passed |
| pytest suite | `python3 -m pytest tests/test_sysdiff.py -v` | 0 | 17/17 passed |
| sanitizer-test | `make sanitizer-test` | 0 | Pass — ASan+UBSan clean under clang |
| valgrind-test | `make clean && make CC=gcc && make valgrind-test` | 0 | Pass — no memory errors (clean non-sanitized binary required; see F003) |

---

## Lens Notes

### Correctness

All contract acceptance checks on observable behavior pass:

- **Exit codes and stdout** — `compare` still emits `+ k=v`, `- k=v`, `~ k: old -> new`, `no changes\n` with exit codes 0/1/2 exactly as before. No regression.
- **Limit enforcement** — `SYSDIFF_MAX_LINE_BYTES` (65536) and `SYSDIFF_MAX_SNAPSHOT_ENTRIES` (65536) are defined as compile-time constants. Exceeding either returns exit 2 with empty stdout and a diagnostic naming the limit and the affected path/line number.
- **No partial output on errors** — all error paths in `parse_snapshot` use `goto cleanup` which calls `snapshot_free` and returns 2 before `emit_diff` is ever called. The after-file error isolation path in `compare_snapshots` (lines 395–398) correctly frees `before` before returning.
- **CRLF stripping** — lines 248–253 strip `\r\n` and `\n` endings before parsing. The logic is correct. No test verifies this (see F001).

### Memory Ownership

The `goto cleanup` refactor makes ownership clear: `parse_snapshot` owns snapshot resources until it returns 0, at which point ownership transfers to `compare_snapshots`. Error helpers are gone; all cleanup is at the single `cleanup:` label. No hidden side-effect functions remain. No double-frees or leaks found.

- `snapshot_free` zeros `items`, `len`, and `cap` so a second call is a safe no-op.
- `copy_range` guards `len + 1` overflow at line 51 before `malloc`.
- `read_line` frees its buffer on every error path before returning.
- After `fclose` failure (lines 306–310), `file` is set to `NULL` before `goto cleanup` so the cleanup label does not attempt a second close.

### Security

- All `fprintf`/`fputs` format strings are compile-time literals. No user-supplied data reaches a format-string position.
- `fopen` uses `"rb"` mode.
- Embedded NUL bytes are detected in `read_line` before `strchr` or `strcmp` are ever called on the buffer.
- `file.` key namespace is treated as opaque data — the path is never opened as a filesystem path.
- The line buffer cap growth check at line 96 guards `new_cap <= cap` (overflow) and `new_cap > SIZE_MAX / sizeof(line[0])` (allocation overflow).

### Resource Limits

Both limits are defined, enforced, and produce contextual diagnostics:

```c
#define SYSDIFF_MAX_LINE_BYTES      ((size_t)65536)
#define SYSDIFF_MAX_SNAPSHOT_ENTRIES ((size_t)65536)
```

Diagnostics include the snapshot path, line number, limit name, and limit value. This satisfies the contract's "contextual diagnostic" requirement.

One low-severity off-by-one exists at the boundary: CRLF-terminated lines can have at most `SYSDIFF_MAX_LINE_BYTES - 1` data bytes, while LF-terminated lines can have exactly `SYSDIFF_MAX_LINE_BYTES`. The check `ch != '\n' && len >= SYSDIFF_MAX_LINE_BYTES` allows the `\n` through unconditionally at len==65536, but `\r` is not treated the same way. In practice this 1-byte discrepancy matters only at the extreme edge of a 65536-byte line (see F002).

### Test Adequacy

**Present:** All 17 pytest tests pass. Shell fixture covers added/removed/changed/no-change, missing file, wrong arg count, malformed input, duplicate key, and unknown command. The pytest fixture compiles the binary from source with strict flags before any test runs.

**Absent:** Two acceptance checks from the contract are not covered by any test:

1. CRLF-terminated snapshots must compare the same as LF-terminated snapshots (contract §Acceptance Checks). The stripping code exists and appears correct but has no fixture (see F001).
2. A snapshot line exceeding `SYSDIFF_MAX_LINE_BYTES` and a snapshot exceeding `SYSDIFF_MAX_SNAPSHOT_ENTRIES` must each return exit 2 with empty stdout and a diagnostic naming the limit. No test exercises either limit path (see F001).

### Sanitizer Coverage

`make sanitizer-test` builds with `clang -fsanitize=address,undefined` and runs the shell test suite clean. The target gracefully skips when clang is absent. This satisfies the contract requirement.

### Valgrind Coverage

`make valgrind-test` runs cleanly when the binary is built without sanitizers. However, if `make sanitizer-test` is run immediately before `make valgrind-test`, the ASan binary left in `build/sysdiff` causes valgrind to abort with a shadow-memory conflict (see F003). The `make-quality` aggregate target works around this correctly by inserting a clean GCC rebuild between the two, but standalone `make valgrind-test` after `make sanitizer-test` is broken.

### CLI Behavior

`--help`, `--version`, no-args, `compare` with correct/wrong arg count, unknown command — all produce the specified exit code, stdout content, and stderr content. No regressions.

---

## Findings

| ID | Severity | File | Location | Problem |
|---|---|---|---|---|
| F001 | Medium | `tests/test_sysdiff.py`, `tests/test_sysdiff_fixture.sh` | (missing tests) | Contract acceptance checks for CRLF equivalence and both resource-limit error paths have no test coverage. |
| F002 | Low | `src/sysdiff.c` | `read_line`, line 89 | CRLF lines are limited to `SYSDIFF_MAX_LINE_BYTES - 1` data bytes; LF lines allow `SYSDIFF_MAX_LINE_BYTES`. The `\r` before `\n` is not exempt from the `ch != '\n'` check. |
| F003 | Medium | `Makefile` | `valgrind-test` target | Running `make valgrind-test` after `make sanitizer-test` uses the ASan-instrumented binary and valgrind aborts. The `make-quality` aggregate target avoids this via an explicit `clean` + GCC rebuild, but standalone invocation is unreliable. |
