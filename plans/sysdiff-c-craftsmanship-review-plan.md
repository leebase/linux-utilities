# sysdiff C craftsmanship review and repair plan

This plan is for a bounded review and the smallest repair supported by a
reproduced finding or a testable safety proof. It is not permission to expand
the product. The repair must preserve existing observable behavior: the CLI,
format-1 grammar, bytewise ordering, output bytes, diagnostics, stdout/stderr
rules, and exit statuses remain unchanged unless a concrete correctness or
security defect makes a change necessary. A new focused test is evidence for
one seam only; a passing full suite is the definition of done.

## Architecture

Start by recording the immutable baseline: the repository-owned journey
manifest must remain parseable, named, authority-preserving, traceable to
AC-1 through AC-10, and pinned to
`0d21f5624b734e7b4ff58e02a42190bde9818cc2ae02e272ae964a72564bfbcc`, with the
exact allowlist `command_allowlist: ["bash scripts/smoke.sh"]`. The adversarial
inspection matrix names every required surface: `src/sysdiff.c`, `Makefile`,
`tests/test_sysdiff.py`, `tests/test_sysdiff.sh`,
`tests/test_sysdiff_fixture.sh`, `tests/test_sysdiff_benchmark.py`,
`tests/test_sysdiff_malformed_fuzz.py`,
`tests/test_sysdiff_c_craftsmanship.py`, `tests/smoke_manifest.json`,
`README.md`, `man/sysdiff.1`, `CHANGELOG.md`, `QUALITY.md`, and `TESTING.md`.
For each, record the relevant ownership, hostile-input, portability,
diagnostic, maintainability, or quality-floor invariant before any repair. Do
not edit the journey oracle, smoke inputs, or unrelated utilities.

The source inspection matrix covers every function in `src/sysdiff.c`:
`fputc_checked`, `fputs_checked`, `put_escaped_bytes`, `put_escaped_value`,
`emit_write_error`, `complete_stdout`, `print_usage`,
`ignore_sigpipe_for_stdout`, `diag_puts_escaped`, `snapshot_free`,
`copy_range`, `read_line`, `is_comment_line`, `is_blank_line`, `is_key_byte`,
`is_valid_key`, `snapshot_append`, `compare_entries_by_key`,
`validate_no_duplicates`, `parse_snapshot`, `emit_added`, `emit_removed`,
`emit_changed`, `emit_diff`, `compare_snapshots`, and `main`. Review checked
`size_t` additions and multiplications, capacity growth, terminators, pointer
differences, `fgetc`/EOF and error classification, `errno`, `fclose`, qsort
comparison, NUL handling, and checked writes before changing code.

Resource ownership and lifetime must be explicit at each transfer point:
`argc`/`argv` and their strings are borrowed for process lifetime; the paths
passed to `parse_snapshot` remain borrowed; `parse_snapshot` owns its opened
`FILE *file`, `total_bytes` accounting, current heap `line`, and all partially
appended `Entry` key/value allocations until success or cleanup. `read_line`
returns ownership of a completed line to `parse_snapshot`; `copy_range`
returns independent NUL-terminated strings; successful `snapshot_append`
transfers `key` and `value` to `Snapshot.items`, while every failed append
frees them exactly once. `realloc` preserves the old allocation on failure.
`snapshot_free` owns each entry string and the item array, resets initialized
empty state, and is safe on every comparison completion path. Successful
`parse_snapshot` closes the file before transferring the initialized snapshot;
failure closes any still-owned file and frees partial state exactly once.
`compare_snapshots` frees the first snapshot when parsing the second fails and
frees both after `emit_diff`, including output-error returns.

The repair review must keep the one-file C17 design and current Linux/POSIX
posture. It must retain the 65,536-byte line ceiling, 65,536-entry ceiling,
and 16 MiB consumed-byte ceiling, including ignored records, and must not add
shell execution, live capture, recursion, persistence, networking, telemetry,
background work, or a new snapshot format. Any proposed source change gets a
before/after observable-behavior comparison against the existing callers and
is rejected if it is merely stylistic.

## Tests

The existing callers, fixtures, and focused craftsmanship oracle that encode
the behavior are exactly `tests/test_sysdiff.py`, `tests/test_sysdiff.sh`,
`tests/test_sysdiff_fixture.sh`, `tests/test_sysdiff_benchmark.py`,
`tests/test_sysdiff_malformed_fuzz.py`, and
`tests/test_sysdiff_c_craftsmanship.py`. Preserve their current oracles and
use them as the compatibility boundary. `tests/test_sysdiff.py` supplies
pytest-level unit/contract coverage for help/version, sorted bytewise diffs,
malformed-before and malformed-after atomicity, embedded NULs, duplicate and
invalid keys, CR/LF and final-line handling, escaping and delimiter shielding,
path/argument diagnostics, `/dev/full`, closed-pipe EPIPE, resource limits,
and distribution/worktree regressions. Its temporary scratch compilation and
mutation-kill checks must continue to prove the source, not a stale binary.

`tests/test_sysdiff.sh` is the integration and packaging caller: exercise
no-argument/help/version behavior, installed-binary compare output, exact
status 0/1/2 classes, and its delegation to the fixture suite. Keep
`tests/test_sysdiff_fixture.sh` as the deterministic fixture/regression
oracle for exact stdout, empty stdout on errors, ordering independence,
comments/blanks, duplicate keys, embedded NULs, CRLF/LF normalization,
line/entry/byte limits, escaped values and diagnostics, delimiter shielding,
`/dev/full`, closed stdout pipes, and Valgrind wrapping. The shell fixture's
large entry-limit case may remain capability/time-gated only where its
existing contract explicitly permits it; any skip records why. The
craftsmanship module itself must remain an explicit review target: its
temporary strict build, CRLF boundary, malformed-after atomicity, hostile-path
escaping, directory read failure, injected second-`fclose` failure, fake-
Valgrind forwarding, and Makefile quality-route assertions must all be
reviewed for false positives, cleanup, and honest capability handling.

Use `tests/test_sysdiff_malformed_fuzz.py` as the bounded deterministic fuzz
and hostile-input corpus. Run its fixed seed and hand-authored categories for
truncation, missing separators, invalid key bytes, duplicates, embedded NUL,
line and entry limits, and seeded mutations; require timeout-free status 2,
empty compare stdout, contextual diagnostics, and no ASan/UBSan/crash signal.
Close its current evidence seam by ensuring the direct subprocess runner also
honors `SYSDIFF_UNDER_VALGRIND=1`, or by adding an equivalently explicit
Valgrind hostile-corpus route in the later allowlisted test/build surface.
Do not call the aggregate Valgrind gate proof of this corpus until the direct
hostile cases are actually instrumented.

Treat `tests/test_sysdiff_benchmark.py` as benchmark-harness unit and
regression coverage, not product correctness proof: retain deterministic
median aggregation, fixed warmup/sample counts, monotonic startup timing,
controlled fixture timing, Linux peak-RSS units, wrapper stdout isolation,
strict-C17 wrapper compilation, threshold pass/fail, stable JSON, temporary
directory isolation, child cleanup, malformed CLI/output-path rejection, and
expected child-status handling. The benchmark must continue using a real
controlled fixture and must not let a changed implementation hide setup cost.

The test matrix is: unit/contract checks through pytest and shell assertions;
integration checks through the built and installed binary and `make test`;
regressions for every existing exact-output/status oracle and the mixed-case
bytewise-order mutant; fixture checks through the shell corpus; fuzz checks
through the deterministic malformed corpus; benchmark checks through
`tests/test_sysdiff_benchmark.py` and `make benchmark-check`; and smoke checks
through the unchanged smoke manifest chain. Run the complete repository test
suite after any focused repair. A new test can demonstrate a fix, but cannot
replace the full existing caller/fixture suite.

## Verification

First capture a clean working-tree/path audit, source and Makefile baseline,
manifest hash/semantic validation, and the current test status. For the
repair, compile `src/sysdiff.c` with the repository-selected `$CC` and strict
ISO C17 `-std=c17 -Wall -Wextra -Wpedantic -Werror`; then run the Makefile's
strict GCC and Clang builds, `clang-format --dry-run --Werror`, `clang-tidy`
with warnings as errors, `cppcheck --enable=all --error-exitcode=1`, Clang
static analyzer, and `man-check`. Preserve the existing `Makefile` temporary
build-directory cleanup and do not create an untracked top-level binary.

Exercise ordinary unit, integration, regression, fixture, malformed-fuzz,
and benchmark tests separately enough that their commands and actual integer
exit codes can be recorded, then run the deterministic smoke route as
`bash scripts/smoke.sh` from the canonical workspace root through its
unchanged manifest/helper chain. Run independent user simulation separately:
resolve paths from the canonical root, launch from an unrelated temporary
current directory, validate the immutable manifest and exact allowlisted
argv, execute only the directly matched smoke command, and record smoke
evidence separately from user-journey evidence. Invalid manifest JSON, wrong
types, duplicate keys, malformed traces/claims, shell operators, wrong cwd,
path escapes, or zero verifiable claims must fail before command execution.

Run the complete `make test`/`make test-suite` path and then the complete
`make quality` floor, including `make benchmark-check`, ordinary tests,
ASan with `ASAN_OPTIONS=detect_leaks=1:abort_on_error=1`, UBSan with
`UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`, and a non-sanitized GCC
Valgrind rebuild with `--error-exitcode=99 --leak-check=full`. Ensure the
Valgrind invocation covers the direct malformed-fuzz corpus, not only the
aggregate shell/pytest route. Missing required tools are failures, not green
skips; a capability-gated skip is recorded with its capability reason and
does not satisfy a required gate. Inspect sanitizer and Valgrind output for
leaks, invalid reads/writes, use-after-free, double-free, overflow, and
unclosed `FILE` resources.

The acceptance traceability matrix is concrete:

| Check | Activity and evidence required |
| --- | --- |
| AC-1 | Before repair, hash and semantically inspect the pinned journey manifest, record its authorities, names, traces, exact allowlist, and baseline matrix for `src/sysdiff.c`, `Makefile`, all five named tests, smoke route, README, and manual. |
| AC-2 | Run fail-closed journey-data validation before execution and run the malformed corpus plus focused NUL, invalid-key, duplicate, truncation, line/entry/byte-limit, I/O, and stdout-failure cases; require status 2 and empty compare stdout. |
| AC-3 | Repeat governed checks from an unrelated cwd and verify canonical-root path resolution; run path/temporary-file tests and confirm lexical, absolute, parent, symlink, and wrong-cwd claims fail closed without changing sysdiff behavior. |
| AC-4 | Verify the unchanged smoke manifest chain and execute only the complete tokenized argv prefix `bash scripts/smoke.sh` directly from the canonical root; record that wrappers, substring matches, extra commands, and shell interpretation are rejected. |
| AC-5 | Compare the pre/post manifest hash and semantic snapshot, including every journey authority/name/trace; reject any omission, demotion, narrowing, or manifest edit and keep the manifest outside producer write scope. |
| AC-6 | Maintain a trace table with every non-exploratory journey linked to a real AC-1..AC-10 ID and confirm all ten IDs are covered by source inspection, tests, smoke, documentation, and evidence activities. |
| AC-7 | Mutate disposable manifest copies, authorities, traces, names, and allowlist and demonstrate SHA-256 plus semantic rejection before command execution; never update the trusted pin or accept changed smoke helpers as evidence. |
| AC-8 | Produce canonical evidence with `journeys` and `findings`, concrete steps, direct commands, observed output only when observed, actual exit codes, actionable failure fields, and explicit static/sanitizer/Valgrind/fuzz/quality results or real capability skips. |
| AC-9 | Report deterministic smoke, focused tests, full suite, benchmark, sanitizers, Valgrind, and independent simulation as distinct evidence records; specifically call out malformed-fuzz Valgrind coverage and never use green smoke or one new test as a substitute. |
| AC-10 | Audit changed paths and documentation, prove no release/install/package/network/telemetry/service/live-probe/CLI-format expansion, reconcile README, `man/sysdiff.1`, `QUALITY.md`, and `TESTING.md` claims, and require green full suite plus full `make quality` before completion. |

After verification, review `git diff --check`, the changed-path list, source
ownership comments, test route environment variables, and evidence claims.
The final decision is pass only when the full suite and complete quality floor
are green and the independent review can reproduce the source-to-test matrix;
otherwise record the exact failed or unavailable gate and leave the repair
incomplete.

## Risks

The primary risk is accidental observable-behavior drift while simplifying
ownership: changing the first `=` rule, line-ending removal, bytewise sort,
escaping, delimiter shielding, diagnostics, stdout atomicity, SIGPIPE/EPIPE
handling, or status 0/1/2 would break existing callers. Compare golden bytes
and streams before and after every source change, and retain the rule that
both snapshots are fully validated before diff output. A cleanup refactor can
also create a double-free, leak, use-after-free, stale `FILE *`, or use of a
transferred key/value; review every `goto cleanup`, successful close, append
transfer, second-snapshot failure, and output-error return under ASan, UBSan,
Valgrind, and the malformed corpus.

Boundary arithmetic is risky at the exact 65,536-byte line, 65,536-entry,
and 16 MiB consumed-byte limits, especially for ignored comments, CRLF,
terminators, realloc growth, `len + 1`, `cap * 2`, and entry-array byte
counts. Keep tests at, just below, and just above each limit and preserve the
contract's diagnostic precedence for an overflowing NUL. Hostile paths,
argv bytes, values, embedded NULs, control bytes, failed opens/reads/closes,
`/dev/full`, and closed pipes must remain escaped and terminal-safe; no shell
or path interpretation may be introduced.

The direct malformed-fuzz Valgrind seam is a known evidence risk: a green
aggregate `make valgrind-test` or `make quality` result is insufficient if
`tests/test_sysdiff_malformed_fuzz.py` launches the binary without its
Valgrind wrapper. Make the route explicit and retain finite per-case timeouts;
do not weaken the corpus or silently convert missing Valgrind into a pass.
Tool-version or host differences can affect clang diagnostics, groff, Linux
`/dev/full`, Valgrind, RSS, and benchmark timing. Use the existing capability
gates and temporary directories, record real skip reasons, keep benchmark
thresholds deterministic, and treat an unavailable required tool as failed
evidence rather than a successful result.

Documentation can drift if the repair changes an invariant, limit,
diagnostic, portability qualification, or test route. If behavior is
unchanged, document that no user-facing update is required; if a supported
change is proven necessary, update README, `man/sysdiff.1`, QUALITY.md, and
TESTING.md together as applicable and verify man lint and full tests. Finally,
the changed-path audit must show only the separately allowlisted source,
build/test/documentation surfaces needed for the repair and review artifacts;
there must be no release, publication, installation, package, tag,
deployment, network, telemetry, background-service, live-system-probe, new
CLI, new snapshot format, or unrelated-utility work.
