# Review: sysdiff Core Implementation

**Subject:** `src/sysdiff.c`, `tests/test_sysdiff.py`, `tests/test_sysdiff_fixture.sh`, `tests/test_sysdiff.sh`
**Spec:** `docs/sysdiff-snapshot-format-and-scope.md`
**Verdict:** pass (severity threshold: High — no High findings)

---

## Checks Run

| Check | Command | Exit code | Outcome |
|---|---|---|---|
| Python compile | `python3 -m compileall tests/test_sysdiff.py` | 0 | Pass |
| pytest suite | `python3 -m pytest tests/test_sysdiff.py -x` | 0 | 17/17 passed |

The pytest fixture compiles `src/sysdiff.c` with `-std=c17 -Wall -Wextra -Wpedantic -Werror` before
running any test, so a compiler-rejected change fails immediately in the first test.
`test_sysdiff.sh` now delegates to `test_sysdiff_fixture.sh` (line 9), closing the integration gap
noted in the previous slice review.

---

## Lens Notes

### Correctness

All specified behaviors are implemented correctly and confirmed by the test suite:

- **Exit codes** — `0` (no diff), `1` (diff found), `2` (all error paths) match the spec exactly.
  `emit_diff` returns 0 or 1 and those codes flow through `compare_snapshots` to `main` unmodified.
- **Output format** — `+ key=value`, `- key=value`, `~ key: old -> new`, and `no changes\n` all
  match the spec exactly. Values containing `=` or `#` are preserved opaquely (confirmed by
  `test_compare_reports_sorted_resource_diffs` which uses `old=hash` as a value).
- **Sorted merge walk** — `parse_snapshot` sorts entries with `qsort` after reading so `emit_diff`
  can do a single linear merge. Different input orderings produce identical output
  (`test_input_order_does_not_affect_diff_output`).
- **Partial output prevention** — both snapshots are fully parsed and validated before any stdout
  is written. The after-file parse failure test (`test_malformed_after_snapshot_fails_without_partial_diff`)
  confirms no stdout leaks on a second-file error.
- **Empty values** — `service.ssh.active=` round-trips as `- service.ssh.active=` / `+ service.ssh.active=`
  with no special handling needed.
- **CRLF stripping** — `\r` before `\n` is stripped at `src/sysdiff.c:228-230`. Tested implicitly
  by `test_identical_snapshots_report_no_changes_and_accept_final_line_without_newline`.

**One gap (Low):** There is no test asserting that a CRLF-terminated snapshot produces the same
diff output as an LF-terminated snapshot with identical content. The code path exists and appears
correct, but no fixture exercises it end-to-end.

### Security

No vulnerabilities found.

- All `fprintf`/`printf` format strings are compile-time literals; user-controlled strings are
  always `%s` arguments. No format-string injection surface.
- `fopen` uses `"rb"` binary mode, preventing platform line-ending translation from silently
  altering content.
- Embedded NUL bytes are rejected in `read_line` (`LINE_INVALID`) before any key/value parsing.
  Without this check, `strchr(line, '=')` would terminate early on a NUL inside a key,
  potentially accepting a malformed key.
- The `file.` key namespace is treated as opaque data; no code opens paths derived from key bytes
  (`test_file_keys_are_compared_as_data` confirms this).
- `copy_range` guards against `len > SIZE_MAX - 1` before calling `malloc(len + 1)`, preventing
  the allocation size from wrapping to a small value.
- Duplicate-key validation runs after `qsort`, so O(n) adjacent comparison is sufficient and
  correct; no quadratic scan or hash table needed.

### Memory Ownership

No leaks or double-frees found.

- `parse_snapshot` owns `key` and `value` allocations from the point `copy_range` returns them.
  If `snapshot_append` fails, both are freed before calling `fail_parse`. If only one of
  `copy_range` calls fails (NULL), the `if (key == NULL || value == NULL)` branch calls
  `free(key)` and `free(value)` — `free(NULL)` is defined safe by C17 7.22.3.3.
- `snapshot_free` sets `items = NULL` and `len = 0` after freeing, so a double-call is safe.
  All error exits from `parse_snapshot` go through `fail_parse` (which calls `snapshot_free`)
  or the inline `fclose` error path (which also calls `snapshot_free`). `compare_snapshots`
  does not call `snapshot_free` after a failed `parse_snapshot` since the callee already cleaned
  up — safe because `items` is NULL.
- `read_line` frees the buffer on `LINE_INVALID`, `LINE_ERROR`, and `LINE_EOF` (len==0). On
  success it transfers ownership to the caller; `parse_snapshot` either transfers further to
  `snapshot_append` (via `key`/`value`) or frees via `free(line)` for comments/blank lines.

**One fragility (Low):** `fail_parse` closes `file` and frees `snapshot` as side effects —
resources that the caller (`parse_snapshot`) still holds a reference to. All current callers
immediately `return fail_parse(...)`, so there is no use-after-free. But the function's
signature gives no indication of these side effects; a future maintenance change that adds a
code path after a `fail_parse` call would introduce a double-close or double-free without any
obvious warning.

### Undefined Behavior

No undefined behavior found.

- `(char)ch` cast: `ch` is checked against EOF before casting; values in `[1, 255]` are all
  valid `unsigned char` values that can be safely narrowed to `char`.
- `separator - line` produces a non-negative `ptrdiff_t` (guaranteed because `separator ==
  line` is rejected as "empty key" before this arithmetic), cast safely to `size_t`.
- `cap - len` unsigned subtraction: the loop invariant `len <= cap` is maintained because we
  grow before `len` can reach `cap`; the growth check `cap - len <= 1` cannot underflow.
- Overflow guards before every `realloc` call (`new_cap <= cap` catches wrapping; the
  `SIZE_MAX / sizeof(...)` guard catches element-count overflow).
- `qsort` comparator `compare_entries_by_key` passes `const struct Entry *` pointers. The
  implicit `const void *` → `const struct Entry *` cast is well-defined (C17 6.3.2.3p7).

### Resource Limits

**One gap (Medium):** The spec permits but does not require documented resource limits. The
implementation imposes none: `read_line` grows arbitrarily large, and `snapshot_append` grows
its array without bound. A hostile snapshot file can exhaust available memory. On OOM, the
path is `realloc → NULL → LINE_ERROR → fail_parse → exit 2` — correct (no partial output, no
undefined behavior), but the diagnostic is "read or allocation error" rather than a
quota-exceeded message, and other processes sharing the host are affected by the memory
pressure. This is a robustness gap, not a spec violation, but worth addressing if `sysdiff`
will run on shared systems.

### Test Adequacy

The test suite is comprehensive for the specified acceptance checks:

- All key-syntax rejection cases in the spec are parametrized in
  `test_malformed_before_snapshot_fails_without_stdout` (9 cases).
- All output format variants are exercised with exact string assertions.
- CRLF and no-trailing-newline behavior are covered.
- Determinism across input orders is verified with two distinct orderings.
- Error isolation (no stdout on parse failure) is tested for both the before and after files.

**Build gap (Low):** The test binary is compiled without `-fsanitize=address,undefined`.
Memory-safety or undefined-behavior bugs that the current fixture inputs don't happen to
trigger would pass undetected. Adding sanitizer flags to the session build would catch a
broader class of latent errors.

**Missing CRLF fixture (Low):** No test confirms that a CRLF snapshot compares identically to
the equivalent LF snapshot. The stripping code exists and appears correct, but the contract
is unverified by the suite.

### CLI Behavior

All documented CLI forms behave correctly:

- `sysdiff` (no args) → stdout usage, exit 0.
- `sysdiff --help` → stdout usage, exit 0.
- `sysdiff --version` → `sysdiff 0.1.0\n`, exit 0.
- `sysdiff compare A B` with valid files → correct diff/no-changes, exit 1/0.
- `sysdiff compare A` (wrong arg count) → stderr, empty stdout, exit 2.
- `sysdiff unknown-command` → stderr including the bad token, exit 2.
- `sysdiff compare A /missing` → stderr including the path, exit 2.
- `sysdiff compare A /directory` → stderr including the path, exit 2.
