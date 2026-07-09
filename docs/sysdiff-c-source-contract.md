# sysdiff C Source Slice Contract

## Overview

This slice hardens the existing `sysdiff compare BEFORE_SNAPSHOT
AFTER_SNAPSHOT` C implementation while preserving the explicit snapshot-only
scope defined in `docs/sysdiff-snapshot-format-and-scope.md`.

The implementation remains centered on the single executable built from
`src/sysdiff.c`. The slice may update `Makefile` only when needed to expose or
verify C quality gates for this implementation. It must not add new runtime
libraries, helper daemons, generated executables, persistence, networking, live
system probing, or package/service manager integration.

Required outputs for the governed delivery are:

- `src/sysdiff.c` keeps implementing the documented command, parser, map
  comparison, output formatting, diagnostics, and exit statuses.
- If build or sanitizer coverage changes are needed, `Makefile` exposes them
  through reviewable targets or flags without weakening the default strict
  warning policy.
- `README.md` documents any user-visible resource limits or diagnostics added
  by the slice.
- Existing tests and smoke entrypoints continue to run through `make test` and
  `scripts/smoke.sh`; follow-up test changes should verify the behavior listed
  below when their step allows writes outside this contract.

## Problem

The current `sysdiff` core correctly parses and compares explicit
`key=value` snapshots, but review of the C source left hardening work open.
The most important gap is unbounded memory growth: line buffers and snapshot
entry arrays can grow until allocation failure when given hostile input. That
failure path exits without partial diff output, but it relies on system memory
pressure instead of deterministic, documented limits.

The implementation also has maintainability and verification gaps that should
be addressed while the C source is still small: parse-error cleanup ownership
is hidden behind a helper with side effects, sanitizer coverage is not yet
part of the regular test build path, and CRLF-versus-LF behavior needs an
explicit fixture assertion. This slice should make those properties clear and
testable without changing the snapshot format or adding broader product scope.

## Constraints

- Keep the command surface limited to `sysdiff`, `sysdiff --help`,
  `sysdiff --version`, and `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`.
- Preserve the snapshot contract for format `1`: explicit plain-text
  `key=value` records, opaque values, documented key validation, duplicate-key
  rejection, embedded-NUL rejection, bytewise sorted comparison, and no partial
  stdout on `compare` errors.
- Define deterministic compile-time resource limits for at least maximum line
  bytes and maximum snapshot entry count. Exceeding a limit must return exit
  status `2`, leave stdout empty, and produce a contextual diagnostic.
- Avoid silent truncation. Inputs that exceed a limit are errors, not shortened
  records.
- Keep memory ownership explicit. Error helpers may clean up resources only
  when the function name, local structure, or nearby comment makes the
  ownership transfer clear to future maintainers.
- Keep the implementation small and auditable in ISO C17-compatible style.
- Preserve strict compiler coverage with `-Wall -Wextra -Wpedantic -Werror`.
- Do not weaken existing tests, smoke manifest behavior, or deterministic
  fixture output order.
- Do not introduce network access, background behavior, hidden runtime state,
  system capture, recursive filesystem scans, package manager calls, service
  probing, SQLite, JSON/YAML snapshot formats, or telemetry.

## Acceptance Checks

- `sysdiff compare` still reports added, removed, changed, and no-change
  snapshots with the documented stdout formats and exit statuses `0`, `1`, and
  `2`.
- Valid snapshots at or below the documented line-length and entry-count
  limits are accepted.
- A snapshot line longer than the defined maximum fails with exit status `2`,
  empty stdout, and stderr naming the exceeded line limit or affected snapshot.
- A snapshot with more than the defined maximum entries fails with exit status
  `2`, empty stdout, and stderr naming the exceeded entry limit or affected
  snapshot.
- Allocation, file I/O, malformed input, duplicate keys, embedded NUL bytes,
  and resource-limit failures all avoid partial diff output.
- Parse-error cleanup ownership is obvious from the C source structure or
  helper naming, and no caller continues to use resources after ownership has
  been transferred for cleanup.
- Tests or smoke coverage confirm that CRLF-terminated snapshots compare the
  same as equivalent LF-terminated snapshots.
- Sanitizer coverage for AddressSanitizer and UndefinedBehaviorSanitizer is
  available through the test build or a documented Makefile target, with a
  clear skip or diagnostic path if the local toolchain cannot provide it.
- `make clean`, `make`, `make test`, and `./scripts/smoke.sh` pass after the
  slice is implemented.
- A strict Clang build is run when `clang` is available; if it is unavailable,
  the run records that fact without treating it as a product behavior change.
- Documentation names any new resource limits and continues to state that this
  slice compares only explicit snapshot files.
