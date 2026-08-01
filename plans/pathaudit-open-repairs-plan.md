# `pathaudit` PA-W1 Open-Repair Plan

## Architecture

The implementation is a local refactor of `symlink_is_self_basename` and its
three `ELOOP` call sites in `try_command_match`; it does not change command
dispatch, PATH loading, finding buffers, winner/shadow indexes, output, or the
Makefile surface.

- **I-1 — bounded discriminator:** replace the 65,537-byte automatic
  `target` array with helper-owned temporary storage sized from
  `strlen(command) + 1`. The extra byte is a truncation detector. Compare only
  when `readlink` returns exactly the command byte length; require byte
  equality and no slash, without relying on NUL termination of link payload.
- **I-2 — explicit result and failure propagation:** return operational status
  separately from the boolean self-basename result. Initialize the result to
  false, propagate allocation failure as the existing `OUT_OF_MEMORY`/status-2
  path, and let all three callers free their owned `candidate` exactly once.
  Preserve the caller’s captured `ELOOP` for the existing inspection
  diagnostic.
- **I-3 — ownership closure:** the helper borrows `candidate` and `command`,
  owns only its bounded link buffer, frees it after match, mismatch, and
  `readlink` failure, and exposes no interior pointer. Keep `lstat`/`readlink`
  read-only and never execute or open target content.
- **I-4 — compatibility boundary:** keep a bare `tool -> tool` link
  reject-closed, while slash-bearing, longer, shorter, or different payloads
  remain non-self cases under the current best-effort loop policy. Do not
  touch hazard ranking, directory/executable ownership, PATH precedence,
  shadow uniqueness, diagnostics, help/version bytes, or exit meanings.

The command-length-derived allocation is safe for both command sources:
`--command` already rejects empty and slash-containing names, while `readdir`
never supplies an empty entry after the scanner filters `.` and `..`.
Candidate construction already bounds joined path bytes. The implementation
must still guard size addition in ordinary project style so no arithmetic wrap
can become an undersized `readlink` buffer.

## Tests

Tests are added only to `tests/test_pathaudit.py`, using deterministic
temporary symlinks and source inspection. The structural regression is
required because ordinary self-loop behavior already passes with the
oversized stack array and therefore cannot, by itself, kill a PA-W1 revert.
Functional regressions ensure the storage refactor does not change the
security decision.

| Acceptance check | Regression test task | Implementation task |
| --- | --- | --- |
| AC-1 | **T-1:** add `test_paw1_self_basename_buffer_is_command_bounded_and_owned`, extracting the helper body and rejecting a `PATHAUDIT_MAX_ROOT_LENGTH` automatic target array while requiring command-length sizing and cleanup. | I-1, I-2, I-3 |
| AC-2 | **T-2:** retain and run `test_path_mode_symlink_loop_executable_candidate_is_inspection_error`, asserting status `2`, empty stdout, and the exact escaped ELOOP diagnostic. | I-2, I-4 |
| AC-3 | **T-3:** retain and run `test_command_mode_symlink_loop_executable_is_inspection_error` with the same exact byte/status assertions. | I-2, I-4 |
| AC-4 | **T-4:** add paired `--path` and `--command` cases for `tool -> ./tool` and a byte-different mutual-loop target; assert no false bare-self diagnostic, `MATCH`, `SHADOWED`, or execution side effect. | I-1, I-4 |
| AC-5 | **T-5:** run the focused module through its normal, ASan+UBSan, and Valgrind routes so T-2/T-4 exercise allocation/free paths; retain the closed-stdout and hostile-byte regressions as compatibility coverage. | I-1, I-2, I-3, I-4 |

T-1 must check the semantic storage property, not pin an entire function
verbatim or require one variable name. T-4 must use exact stdout, stderr, and
exit assertions and must not inspect the ambient PATH. No test may require
root, depend on wall-clock timing as its oracle, execute a planted target, or
silently skip merely because the pre-repair implementation fails.

## Verification

Run the focused regression first:
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/test_pathaudit.py -q`. Then run strict GCC and Clang C17
warning-as-error syntax/link checks for `src/pathaudit.c`,
`clang-format --dry-run --Werror`, the configured clang-tidy checks with
warnings as errors, cppcheck with a nonzero error exit, and the Clang static
analyzer. The focused test output must report only honest host-capability
skips already present in the suite.

Exercise ownership and failure cleanup with the repository’s established
`make pathaudit-sanitize`, `make pathaudit-valgrind`, `make test-sanitize`,
and `make test-valgrind` routes, followed by `make test` and the complete
`make quality` surface when the host prerequisites are available. ASan must
retain leak detection; UBSan must halt on error; Valgrind must use the
non-sanitized debug binary, full leak checking, and nonzero error exit. Record
real commands, exit codes, pass/skip totals, and any environmental omission
rather than converting an unavailable gate into success.

Finally, compare `--help`, `--version`, explicit-root, `--path`, and
`--command` regression bytes against the existing contract. Verify exact
ELOOP, `OUT_OF_MEMORY`, `STDOUT_WRITE`, and hostile-path escaping behavior;
status `0`/`1`/`2`; shared findings before `SHADOWED`; and `MATCH` ordering.
The governed user smoke should run through its pinned manifest, with the
result described as transitive suite evidence rather than a dedicated PA-W1
user flow.

## Risks

The chief implementation risk is an off-by-one `readlink` comparison.
`readlink` does not append NUL, so the new code must treat the returned byte
count as authoritative: exactly `command_len` may be compared, while
`command_len + 1` proves truncation or a longer payload. A shorter return,
slash-bearing payload, byte mismatch, or read failure is not the bare
self-basename case. Arithmetic overflow must be rejected before allocation.

The next risk is ownership drift across the three `ELOOP` branches. Refactoring
the helper to report allocation failure can accidentally leak or double-free
`candidate`, overwrite the captured errno, or soften `OUT_OF_MEMORY` into a
silent non-match. I-2 and I-3 require one clear owner at every return, while
T-2/T-3, sanitizers, the analyzer, and Valgrind cover the executable paths.
The source-structure assertion in T-1 is intentionally narrow so harmless
renaming does not make the test brittle.

Filesystem mutation can race `stat`, `lstat`, `readlink`, image probing, and
`realpath`; that pre-existing best-effort limitation is not solved here.
Slash-bearing self loops and mutual loops must retain current non-candidate
handling even though different policy might be conceivable. Expanding this
repair into executable-image policy, ownership deduplication, signal
diagnostics, index abstraction, packaging, or release work would obscure
PA-W1 closure and is therefore a scope failure.
