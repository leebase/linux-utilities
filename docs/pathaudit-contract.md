# `pathaudit` Vertical-Slice Contract

## Overview

`pathaudit` is a small ISO C17 command-line scanner for risks in explicitly
supplied PATH directory entries. It inspects only the operands named by the
caller; it never reads the `PATH` environment variable, searches for
executables, walks directory contents, or examines ancestor directories. One
operand represents one inspection root, and duplicate operands remain distinct
inputs. This narrow slice reports only the hazards listed below. It does not
inspect packages, running processes, services, capabilities, ACLs, mount
options, or ownership policy, and it performs no remediation, privilege
escalation, networking, persistence, monitoring, or daemon work.

Inspection is read-only and requires no special privilege. Classification is
based on the operand bytes and one `stat`-equivalent lookup of its final target.
All ordering and escaping are byte-oriented and locale-independent. Filesystem
state can change concurrently, so a result describes the metadata observed
during that invocation and is not a security lock or a promise about later
execution.

## CLI Contract

The command form is `pathaudit [--] ROOT...`, with at least one root required.
`--` ends option processing and permits roots beginning with `-`.
`pathaudit --help` and `pathaudit --version` are the only informational forms
and return `0`; they accept no additional operands. Unknown options, missing
roots, or extra operands on informational forms are usage errors. The process
does not consult `PATH`, configuration files, stdin, or locale settings.
`--help` writes exactly `usage: pathaudit [--] ROOT...\nScan explicitly
supplied PATH directory roots.\n` to stdout; `--version` writes exactly
`pathaudit 0.1.0\n`. Both leave stderr empty.

Each finding is exactly one stdout line:

```text
CODE<TAB>"ESCAPED_ROOT"<LF>
```

`<TAB>` is one byte `0x09`, not the displayed word. Inside the quotes,
printable ASCII bytes `0x20` through `0x7e` are emitted literally except `"`
and `\`, which become `\"` and `\\`; every other byte is uppercase `\xHH`.
Thus an empty operand is rendered as `""`. Roots are compared as unsigned byte
strings, not as Unicode and not after normalization. Findings are ordered by
raw root bytes, then original operand position for byte-identical duplicate
roots, then this fixed code rank: `EMPTY_ROOT`, `RELATIVE_ROOT`,
`MISSING_ROOT`, `NON_DIRECTORY_ROOT`, `GROUP_WRITABLE`, `WORLD_WRITABLE`.
Every applicable code is emitted once per operand. Input order, locale,
directory enumeration order, and libc sort stability therefore cannot alter
the result.

Exit status `0` means every root was inspected and no hazard was found.
Status `1` means inspection completed and at least one hazard was emitted.
Status `2` means usage failure, an input-limit violation, a metadata error not
classified as a hazard, allocation failure, or an output write/flush failure.
Before inspection, the program rejects more than 65,536 roots, any root longer
than 65,536 bytes excluding its terminating NUL, or more than 1 MiB of root
bytes including terminating NULs. Linux argument strings cannot contain NUL;
all other byte sequences, including invalid UTF-8 and control bytes, are
opaque. Limit and inspection failures are reject-closed: buffered findings are
discarded and stdout remains empty. A stdout failure may leave a partial line.

Diagnostics go only to stderr and use fixed ASCII reason tokens. Their first
line is `pathaudit: REASON\n`, or `pathaudit: REASON: "ESCAPED_ROOT"\n` when
one operand caused the error. The reasons are `USAGE`, `UNKNOWN_OPTION`,
`ROOT_COUNT_LIMIT`, `ROOT_LENGTH_LIMIT`, `ROOT_BYTES_LIMIT`, `OUT_OF_MEMORY`,
`INSPECTION_ERROR_N`, and `STDOUT_WRITE`; `N` is the decimal `errno` from the
failed metadata lookup. `UNKNOWN_OPTION` and every `USAGE` error are followed
by `usage: pathaudit [--] ROOT...\n`; the usage line is not duplicated when
the first reason is already `USAGE`. Operand diagnostics use the same quoted
escaping as stdout and never reproduce raw control bytes. Roots are inspected
in the same sorted order used for output. Inspection stops at the first
operational failure in that order, so the selected diagnostic is
deterministic. No diagnostic is written merely because hazards were found.

## Hazard Taxonomy

The taxonomy is closed for this slice. `EMPTY_ROOT` applies when the operand
has zero bytes. An empty entry is not silently translated to the current
directory and receives no filesystem lookup. `RELATIVE_ROOT` applies to every
nonempty operand whose first byte is not `/`, including `.` and `..`; the
operand is still looked up relative to the process's initial working directory,
so it may also receive a resolution or permission finding.

For a nonempty root, lookup follows symbolic links in the same manner as
`stat(2)`. A symlink is not itself a hazard in this narrow taxonomy.
`MISSING_ROOT` applies when target lookup reports `ENOENT`, including a
dangling final symlink. `NON_DIRECTORY_ROOT` applies when lookup succeeds but
the final target is not a directory; it also applies when lookup reports
`ENOTDIR` because an operand component prevents directory resolution. These
two resolution findings are mutually exclusive. Symlink loops, permission
denials, I/O errors, and other lookup failures are operational errors with
status `2`, not new hazard classes.

Permission findings use only the final directory target's `st_mode` bits from
that successful lookup. `GROUP_WRITABLE` applies when `S_IWGRP` is set, and
`WORLD_WRITABLE` applies when `S_IWOTH` is set. A directory with both bits
produces both findings; sticky, set-ID, execute, read, owner, ACL, effective
credential, and mount-policy state neither suppresses nor creates a finding.
Missing and non-directory roots receive no permission finding. The scanner
does not open, enumerate, mutate, canonicalize, or recursively inspect a
directory, and it makes no claim that an unreported directory is safe.

## Acceptance Checks

Tests build a temporary directory tree without privilege changes and pass
every root explicitly. Deterministic fixtures include: a private absolute
directory; absolute directories with group-write, world-write, and both bits;
an absent root; a regular file; a dangling symlink; symlinks to a private
directory, writable directories, and a regular file; empty, `.`, `..`, and
other relative operands; duplicate roots; and roots supplied in multiple
orders. Tests set exact modes after creation, use a fixed fixture working
directory, and compare complete stdout bytes, stderr bytes, and exit status.
Repeated and permuted invocations must prove the specified bytewise root/code
ordering and duplicate behavior.

Malformed and hostile-input cases cover no operands, unknown options,
informational-command arity, a leading-dash root with and without `--`, empty
arguments, control bytes, quotes, backslashes, non-UTF-8 bytes where the host
permits them, overlong roots, too many roots, aggregate-byte overflow, a
symlink loop, and an unreadable path when the fixture can reliably provoke
`EACCES`. They verify ASCII-safe diagnostics, status `2`, and empty stdout on
reject-closed failures. A closed stdout pipe or equivalent write-failure
fixture verifies status `2` without requiring complete stdout.

Both GCC and Clang must compile and link `src/pathaudit.c` as C17 with
`-Wall -Wextra -Wpedantic -Werror` and no warnings. Formatting checks,
clang-tidy with warnings treated as errors, cppcheck with a nonzero error exit,
and the Clang static analyzer must pass. AddressSanitizer with leak detection
and UndefinedBehaviorSanitizer with halt-on-error must execute the functional
and hostile-input cases. Valgrind should cover the same paths when available;
an unavailable optional host tool must be reported rather than represented as
a pass.

Regression coverage pins the complete CLI, taxonomy, symlink, permission,
escaping, ordering, diagnostic, limit, and exit-status contract above.
Repository-wide acceptance also runs all pre-existing `sysdiff` shell,
pytest, fixture, malformed-input, benchmark, sanitizer, and Valgrind gates
required by the existing quality surface. The new build and test wiring must
preserve every existing `sysdiff` command, output byte, diagnostic, exit
status, artifact, install behavior, and test result; this slice authorizes no
change to `sysdiff`.
