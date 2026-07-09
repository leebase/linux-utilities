# sysdiff Fixture Slice Contract

## Overview

Define the smallest useful `sysdiff` comparison slice that can be implemented
and tested against deterministic fixtures. This slice extends the existing
single executable built by `Makefile` from `src/sysdiff.c`; it does not add
runtime dependencies, background behavior, live system probing, persistence, or
additional binaries.

## Problem

`sysdiff` currently proves only that the executable builds and responds to
informational commands. The next useful slice needs a deterministic comparison
surface that can be reviewed without privileged system access or broad system
probing. Fixture-backed snapshots provide that surface: they let the project
define parsing, comparison, output, and failure behavior before adding any live
snapshot collection.

## Constraints

- Build on the existing `Makefile`, `src/sysdiff.c`, `tests/test_sysdiff.sh`,
  and `scripts/smoke.sh`.
- Keep `build/sysdiff` as the only executable for this utility.
- Avoid new runtime dependencies, services, networking, telemetry, persistence,
  and hidden background behavior.
- Keep behavior deterministic across fixture input ordering.
- Keep parsing, comparison, and output formatting separable enough to remain
  auditable as the single C source grows.
- Treat unsafe input handling, silent truncation, partial output on errors, and
  unclear ownership as defects.

## Scope

The slice compares two explicit snapshot fixture files and reports how named
snapshot entries changed.

In scope:

- Keep `build/sysdiff` as the only executable.
- Keep the existing `Makefile` as the build entrypoint.
- Extend `src/sysdiff.c` with fixture parsing, comparison, and output
  formatting.
- Extend `tests/test_sysdiff.sh` or add fixture-backed tests invoked by
  `make test`.
- Keep `scripts/smoke.sh` as the top-level smoke command and ensure it still
  runs the project test suite.
- Document the user-visible comparison command in `README.md` during the
  documentation step.

Out of scope:

- Live system snapshot collection.
- Recursive filesystem scans.
- SQLite or other persistence.
- New runtime libraries, services, networking, telemetry, or generated helper
  executables.
- Broad diff algorithms for arbitrary text files.

## Command Contract

The fixture comparison command is:

```sh
sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT
```

Existing commands remain supported:

```sh
sysdiff --help
sysdiff --version
```

`--help` must mention the compare form. No arguments keeps the current
non-error help behavior. Unknown commands, wrong argument counts, and file or
parse failures are errors.

## Snapshot Fixture Format

Snapshot fixtures are plain UTF-8-compatible text files treated as bytes by the
C program. The accepted format is intentionally narrow:

```text
# optional comment
entry.name=value
another.entry=some value
```

Rules:

- One entry per line.
- Blank lines and lines whose first non-space character is `#` are ignored.
- Each entry line must contain exactly one non-empty key before the first `=`.
- Values may be empty and may contain spaces after the `=`.
- Keys must be compared byte-for-byte and must not be trimmed.
- Values must be compared byte-for-byte after removing the trailing line ending.
- Duplicate keys in the same snapshot are parse errors.
- Lines that cannot be represented safely in fixed or dynamically allocated
  buffers are errors, not truncation opportunities.

Tests may keep fixtures under `tests/fixtures/`. The implementation may use
temporary files from the shell test harness when that keeps the fixture small
and readable.

## Diff Output Contract

Output is deterministic and line oriented. Entries are sorted by key in byte
order before comparison so fixture input order does not affect output.

For changed snapshots, write one line per difference to stdout:

```text
- removed.key=old value
+ added.key=new value
~ changed.key: old value -> new value
```

Ordering is by key across the union of keys. For a key present in both files
with different values, emit only the `~` line. For a key present only in the
before file, emit `-`. For a key present only in the after file, emit `+`.

For identical snapshots, stdout is exactly:

```text
no changes
```

All diagnostic messages go to stderr and must include enough context to identify
the failed path or argument.

## Exit Status Contract

- `0`: Command succeeded and no differences were found, or informational
  commands such as `--help` and `--version` succeeded.
- `1`: `compare` succeeded and at least one difference was found.
- `2`: Usage, file I/O, parse, allocation, duplicate-key, or other runtime
  error.

The test harness must assert all three status classes.

## Acceptance Checks

Snapshot fixture input:

- A test compares two valid fixture files containing unchanged, added, removed,
  and changed keys.
- A test proves input order does not affect output order.
- A test covers comments, blank lines, and a value containing spaces.
- A test covers an empty value.

Diff output:

- Expected stdout is checked exactly for a changed comparison.
- Expected stdout is checked exactly for identical snapshots.
- Diff lines use only the specified `-`, `+`, and `~` prefixes.
- Output order is deterministic by key.

Error handling:

- Missing file returns exit status `2` and writes a diagnostic to stderr.
- Wrong argument count returns exit status `2`.
- Unknown command returns exit status `2`.
- Malformed fixture line returns exit status `2`.
- Duplicate key returns exit status `2`.
- Error cases do not write partial diff output to stdout.

Build and test commands:

- `make clean`
- `make`
- `make test`
- `./scripts/smoke.sh`
- At least one strict compiler build using the existing warning policy:
  `CC=clang make clean test` when Clang is available, otherwise record that it
  was unavailable.

Smoke evidence:

- The governed smoke step records the command run, exit status, and result path
  for `./scripts/smoke.sh`.
- The smoke gate must fail if `make test` fails.
- Smoke evidence must be stored outside source-controlled code unless the
  playbook explicitly allows an artifacts path.

Documentation:

- `README.md` documents `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`.
- `README.md` documents the fixture format with one minimal example.
- `architecture.md` continues to state that parsing, comparison, and formatting
  should remain separable as the program grows.
- Documentation does not promise live system capture in this slice.

## Non-Goals For This Slice

Do not implement a general-purpose replacement for `diff(1)`. The accepted
input is a constrained sysdiff snapshot fixture format whose purpose is to make
the first comparison behavior auditable, deterministic, and easy to review.
