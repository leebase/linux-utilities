# sysdiff Design

## Architecture Overview

`sysdiff` is a small C command-line utility for comparing two explicit system
snapshot files. The current product surface is intentionally narrow:

```sh
sysdiff --help
sysdiff --version
sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT
```

The compare command reads only the two paths supplied on the command line. It
does not inspect the running host, scan directories, call package or service
managers, persist snapshots, contact the network, or run background work.

The executable is built from `src/sysdiff.c` by `make`. The implementation is
kept as a single small C17 translation unit for now so parsing, validation,
comparison, output, and cleanup remain easy to audit. The durable behavior
contracts are:

- `docs/sysdiff-snapshot-format-and-scope.md` for snapshot syntax, comparison
  behavior, output, exit status, security constraints, and non-goals.
- `docs/sysdiff-c-source-contract.md` for C-source hardening requirements,
  resource limits, ownership, and quality gates.

The current implementation defines deterministic limits of 65536 bytes per
snapshot line and 65536 records per snapshot. Inputs that exceed these limits
fail closed with exit status `2`, empty stdout, and contextual stderr.

## Component Design

### Command Dispatch

Command dispatch recognizes informational commands and the `compare` subcommand.
Usage errors return exit status `2`. Informational commands return `0` and do
not require snapshot files.

### Snapshot Reader

The reader opens each named snapshot in binary mode and reads one logical line
at a time. It rejects embedded NUL bytes, read errors, allocation failures, and
lines that exceed `SYSDIFF_MAX_LINE_BYTES`. It removes `\n` and a single
trailing `\r` before `\n`, accepts a final line without a trailing newline, and
never silently truncates input.

### Parser and Validator

The parser converts each non-empty, non-comment line into a `KEY=VALUE` record.
Whole-line comments are recognized when the first byte after leading spaces or
tabs is `#`; inline comments are data. Keys and values are otherwise not
trimmed.

Validation rejects missing separators, empty keys, invalid key bytes, keys
without a dot separator, keys beginning with `/`, keys ending with `.`, `..`
segments, duplicate keys, embedded NUL bytes, and resource-limit violations.
Values remain opaque byte strings after line-ending removal.

### Snapshot Map

Parsed records are stored as owned key/value strings in a growable array capped
by `SYSDIFF_MAX_SNAPSHOT_ENTRIES`. After parsing, records are sorted by key with
bytewise `strcmp` ordering. Duplicate detection runs after sorting so it is
independent of input order.

### Comparator

The comparator walks the two sorted snapshots as maps. For each key in the
union of both snapshots, it identifies removed, added, changed, or unchanged
records. Unchanged records are suppressed.

### Output Formatter

All diff output goes to stdout. Diagnostics go to stderr. Output is stable and
line-oriented:

```text
+ key=new value
- key=old value
~ key: old value -> new value
```

For identical snapshots stdout is exactly:

```text
no changes
```

Each output line ends in `\n`. Compare errors must leave stdout empty.

### Ownership and Cleanup

`parse_snapshot` owns partially built snapshot resources until it returns
success. On errors it uses a centralized cleanup path to close the file and
free allocated records. `snapshot_free` is idempotent for initialized snapshots,
which keeps caller cleanup simple.

## Data Flow

1. Dispatch validates the command line.
2. `compare` initializes two empty snapshot structures.
3. The before snapshot is opened, read, parsed, validated, sorted, and checked
   for duplicates.
4. The after snapshot goes through the same validation path.
5. Only after both snapshots are valid, the comparator walks the sorted maps.
6. The formatter emits deterministic diff lines or `no changes`.
7. Both snapshots are freed before exit.

This ordering is deliberate: malformed input, duplicate keys, I/O errors,
allocation failures, and limit failures are all detected before any diff output
is produced.

## Build and Test

The default build is:

```sh
make
```

The build emits `build/sysdiff` and uses strict C17 warning flags by default:
`-std=c17 -Wall -Wextra -Wpedantic -Werror`.

The primary test paths are:

```sh
make test
python3 -m pytest tests/ -q
./scripts/smoke.sh
```

Broader local quality coverage is exposed through:

```sh
make make-quality
```

That target performs clean GCC and Clang builds, runs the shell and Python test
suites, runs ASan/UBSan coverage through `make sanitizer-test` when `clang` is
available, then performs a clean GCC rebuild before `make valgrind-test`.

Current open test and quality caveats from the latest C-source review are:

- CRLF-vs-LF equivalence and both resource-limit failure paths need focused
  tests.
- CRLF-terminated lines currently allow one fewer data byte than LF-terminated
  lines at the line-length boundary.
- Standalone `make valgrind-test` can be unreliable immediately after
  `make sanitizer-test` because it may reuse an ASan-instrumented binary;
  `make make-quality` avoids this by rebuilding with GCC first.
