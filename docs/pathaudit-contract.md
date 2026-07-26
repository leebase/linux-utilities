# `pathaudit` Vertical-Slice Contract

## Overview

`pathaudit` is a small ISO C17 command-line scanner for risks in PATH directory
entries. It supports three exclusive invocation modes: explicit-root
(`pathaudit [--] ROOT...`), where every inspection root is a command-line
operand and the process `PATH` is ignored; opt-in `pathaudit --path`, which
reads `PATH` once, splits on ASCII `:`, classifies each component, and scans
top-level regular executables for shadowing plus the shared executable trust
model; and opt-in `pathaudit --command NAME`, which walks `PATH` for one
basename, emits `MATCH` lines, then applicable hazards including that same
executable trust model. Explicit-root mode never searches executables and
remains ownership-blind. None of the modes examine ancestor directories or
remediate anything. One root or one PATH component represents one inspection
input; duplicate inputs remain distinct. This slice reports only the hazards
listed below. It does not inspect packages, running processes, services,
capabilities, ACLs, or mount options. The only ownership rule in scope is the
narrow `UNSAFE_OWNER` check on executable targets resolved by `--path` and
`--command` (final-target owner must be UID 0 or the invoking real UID). It
performs no privilege escalation, networking, persistence, monitoring, or
daemon work.

Inspection is read-only and requires no special privilege. Directory
classification uses the root bytes and one `stat`-equivalent lookup of the
final directory target. Executable trust checks use followed-target metadata
for resolved regular executables. All ordering and escaping are byte-oriented
and locale-independent. Filesystem state can change concurrently, so a result
describes the metadata observed during that invocation and is not a security
lock or a promise about later execution. Existing explicit-root CLI behavior,
finding taxonomy, output escaping, ordering, resource limits, and exit-status
meanings remain compatibility requirements. Help text, tests, README, the
manual page, and changelog entries must describe the exclusive forms and must
name `UNSAFE_OWNER` where ownership is documented; this contract is the source
of truth. This document does not claim that `pathaudit` is released.

## CLI Contract

Two exclusive command forms are defined. The preserved explicit-root form is
`pathaudit [--] ROOT...`, with at least one root required. `--` ends option
processing and permits roots beginning with `-`. The additive form is
`pathaudit --path`, which accepts no root operands and no other options.
`--path` is exclusive: combining it with any `ROOT` operand, with another
non-informational option, or with a second `--path` is a usage error. The
informational forms `pathaudit --help` and `pathaudit --version` remain the
only informational forms and return `0`; they accept no additional operands.
Unknown options, missing roots on the explicit form, extra operands on
informational forms, and any mixture of `--path` with roots are usage errors.

`--path` reads the `PATH` environment variable exactly once via the ordinary
process environment. It does not reread `PATH` and does not consult configuration
files or stdin. After classifying components it may scan top-level regular
executables for shadowing and for the shared writability / `UNSAFE_OWNER` trust
model; it does not recurse into nested directories.
If `PATH` is unset (`getenv` returns a null pointer), the mode is reject-closed:
stdout remains empty, stderr reports the fixed reason `PATH_UNSET`, and the
exit status is `2`. If `PATH` is set to an empty string, the mode treats that
value as exactly one empty component, which classifies as `EMPTY_ROOT` under
the shared taxonomy and therefore exits with status `1` when inspection
completes. A nonempty `PATH` value is split on ASCII colon (`:`) only; empty
components created by leading, trailing, or consecutive colons are retained,
and duplicate components are retained in their original positions. Every
resulting component is passed through the same hazard classification,
ordering, escaping, and limit accounting used for explicit roots.

`--help` writes exactly `usage: pathaudit [--] ROOT...\n   or: pathaudit
--path\nScan PATH directory roots for hazards.\n` to stdout; `--version`
writes exactly `pathaudit 0.1.0\n`. Both leave stderr empty on success. Usage
diagnostics that print a usage summary use the two-line synopsis
`usage: pathaudit [--] ROOT...\n   or: pathaudit --path\n` (without the scan
description line). The process does not consult locale settings for parsing or
output.

Each finding is exactly one stdout line:

```text
CODE<TAB>"ESCAPED_ROOT"<LF>
```

`<TAB>` is one byte `0x09`, not the displayed word. Inside the quotes,
printable ASCII bytes `0x20` through `0x7e` are emitted literally except `"`
and `\`, which become `\"` and `\\`; every other byte is uppercase `\xHH`.
Thus an empty operand or empty PATH component is rendered as `""`. Roots and
PATH components are compared as unsigned byte strings, not as Unicode and not
after normalization. Findings are ordered by raw root bytes, then original
input position for byte-identical duplicate roots or components, then this
fixed code rank: `EMPTY_ROOT`, `RELATIVE_ROOT`, `MISSING_ROOT`,
`NON_DIRECTORY_ROOT`, `GROUP_WRITABLE`, `WORLD_WRITABLE`, `UNSAFE_OWNER`.
Every applicable code is emitted once per input. `UNSAFE_OWNER` applies only
to resolved executable targets under `--path` / `--command` (never to
directory roots and never under explicit-root mode). Under `--path`, shared-
taxonomy findings (including executable permission and `UNSAFE_OWNER` lines)
precede all `SHADOWED` lines. Input order, locale, directory enumeration
order, and libc sort stability therefore cannot alter the result.

Exit status `0` means every root or PATH component was inspected and no hazard
was found. Status `1` means inspection completed and at least one hazard was
emitted. Status `2` means usage failure, unset `PATH` in `--path` mode, an
input-limit violation, a metadata error not classified as a hazard, allocation
failure, or an output write/flush failure. Before inspection, the program
rejects more than 65,536 roots or PATH components, any root or component
longer than 65,536 bytes excluding its terminating NUL, or more than 1 MiB of
root/component bytes including terminating NULs. In `--path` mode those limits
apply to the components after colon splitting; the raw `PATH` string is not a
separate limit class beyond producing those components. Linux argument strings
and environment values cannot contain NUL; all other byte sequences, including
invalid UTF-8 and control bytes, are opaque. Limit and inspection failures are
reject-closed: buffered findings are discarded and stdout remains empty. A
stdout failure may leave a partial line.

Diagnostics go only to stderr and use fixed ASCII reason tokens. Their first
line is `pathaudit: REASON\n`, or `pathaudit: REASON: "ESCAPED_ROOT"\n` when
one operand or component caused the error. The reasons are `USAGE`,
`UNKNOWN_OPTION`, `PATH_UNSET`, `ROOT_COUNT_LIMIT`, `ROOT_LENGTH_LIMIT`,
`ROOT_BYTES_LIMIT`, `OUT_OF_MEMORY`, `INSPECTION_ERROR_N`, and `STDOUT_WRITE`;
`N` is the decimal `errno` from the failed metadata lookup. `UNKNOWN_OPTION`
and every `USAGE` error are followed by the two-line usage synopsis above; the
usage lines are not duplicated when the first reason is already `USAGE`.
`PATH_UNSET` is reject-closed with status `2`, empty stdout, and no usage
synopsis. Operand and component diagnostics use the same quoted escaping as
stdout and never reproduce raw control bytes. Roots and PATH components are
inspected in the same sorted order used for output. Inspection stops at the
first operational failure in that order, so the selected diagnostic is
deterministic. No diagnostic is written merely because hazards were found.

## Hazard Taxonomy

The taxonomy is closed for this slice. Directory codes are shared by the
explicit-root form and by every PATH component under `--path` / `--command`.
`EMPTY_ROOT` applies when the operand or PATH component has zero bytes. An
empty entry is not silently translated to the current directory and receives
no filesystem lookup. An explicitly empty `PATH` therefore yields exactly one
`EMPTY_ROOT` finding and exit status `1` after successful classification; it
is not an operational error and must not be confused with unset `PATH`
(`PATH_UNSET`, status `2`). `RELATIVE_ROOT` applies to every nonempty input
whose first byte is not `/`, including `.` and `..`; the input is still looked
up relative to the process's initial working directory, so it may also receive
a resolution or permission finding.

For a nonempty root or PATH component, lookup follows symbolic links in the
same manner as `stat(2)`. A symlink is not itself a hazard in this narrow
taxonomy. `MISSING_ROOT` applies when target lookup reports `ENOENT`,
including a dangling final symlink. `NON_DIRECTORY_ROOT` applies when lookup
succeeds but the final target is not a directory; it also applies when lookup
reports `ENOTDIR` because an operand component prevents directory resolution.
These two resolution findings are mutually exclusive. Symlink loops,
permission denials, I/O errors, and other lookup failures are operational
errors with status `2`, not new hazard classes.

Directory permission findings use only the final directory target's `st_mode`
bits from that successful lookup. `GROUP_WRITABLE` applies when `S_IWGRP` is
set, and `WORLD_WRITABLE` applies when `S_IWOTH` is set. A directory with both
bits produces both findings; sticky, set-ID, execute, read, owner, ACL,
effective credential, and mount-policy state neither suppresses nor creates a
finding. Missing and non-directory roots receive no permission finding. The
scanner makes no claim that an unreported directory is safe.

Under `--path` and `--command`, the same writability bits applied to a
resolved regular executable target reuse `GROUP_WRITABLE` / `WORLD_WRITABLE`
with the executable `realpath` as the finding root (owner-only write stays
silent). Separately, those modes apply the narrow ownership rule:
`UNSAFE_OWNER` is emitted when the final followed-target `st_uid` is neither
UID 0 nor the invoking real UID from `getuid()`. Trusted owners are root and
the invoking user only; every other final-target owner is unsafe. Symlink
resolution for ownership follows the final target (same `stat`-followed
metadata that accepted the regular executable); the finding names that
executable `realpath`, not the symlink path and not the PATH directory
component. Output shape is the shared finding line
`UNSAFE_OWNER<TAB>"ESCAPED_REALPATH"<LF>`. `UNSAFE_OWNER` ranks after
`GROUP_WRITABLE` and `WORLD_WRITABLE` for the same root; under `--path` those
shared-taxonomy lines (directory and executable) precede all `SHADOWED`
lines. Emitting `UNSAFE_OWNER` completes inspection with exit status `1` and
empty stderr on the successful hazard path. Explicit-root mode remains
ownership-blind: it does not search executables and never emits
`UNSAFE_OWNER`. Non-image same-basename decoys are not executable candidates
and do not receive `UNSAFE_OWNER`. Directory ownership is not classified.
Remediation is operator-side (replace foreign-owned PATH executables with
root-owned or self-owned trusted binaries, or remove untrusted PATH entries);
`pathaudit` does not `chown`, edit `PATH`, or claim release readiness.

## Acceptance Checks

Tests build a temporary directory tree and exercise explicit-root, `--path`,
and `--command` modes. Explicit-root fixtures continue to pass every root on
the command line and must remain ownership-blind even when a foreign-owned
regular executable sits inside a supplied root. Deterministic fixtures
include: a private absolute directory; absolute directories with group-write,
world-write, and both bits; an absent root; a regular file; a dangling
symlink; symlinks to a private directory, writable directories, and a regular
file; empty, `.`, `..`, and other relative operands; duplicate roots; and
roots supplied in multiple orders. Tests set exact modes after creation, use
a fixed fixture working directory, and compare complete stdout bytes, stderr
bytes, and exit status. Repeated and permuted invocations must prove the
specified bytewise root/code ordering and duplicate behavior.

`--path` acceptance must pin unset versus empty `PATH` distinctly: an unset
`PATH` yields reject-closed `PATH_UNSET` on stderr, empty stdout, and status
`2`; an explicitly empty `PATH` yields exactly one `EMPTY_ROOT` finding for
`""`, empty stderr for the successful hazard path, and status `1`. Split
fixtures must retain empty and duplicate components from values such as
`:`, `::`, `/a:/a`, `/a:`, `:/a`, and `/a::/b`, proving that colon splitting
discards nothing and that each component is classified independently under the
shared taxonomy. `--path` arity fixtures must reject extra operands and any
mixture with explicit roots as usage errors. Nested-directory recursion must
not invent findings; fixtures that would only fail if nested traversal
occurred must remain clean.

Executable-ownership acceptance for `--path` and `--command` must name
`UNSAFE_OWNER` exactly and pin: invoking-UID and root-UID 0 targets stay
silent; a foreign final-target owner emits
`UNSAFE_OWNER<TAB>"ESCAPED_REALPATH"` with status `1` and empty stderr; a
symlink candidate reports the final target's owner and realpath; combined
group/world-writable plus foreign ownership orders
`GROUP_WRITABLE` then `WORLD_WRITABLE` then `UNSAFE_OWNER` for that realpath;
under `--path`, `UNSAFE_OWNER` lines precede `SHADOWED`; foreign-owned
non-executable same-basename decoys stay silent; explicit-root never emits
`UNSAFE_OWNER`. Foreign-owner fixtures may `chown` only files created inside
the test tree and must skip honestly when the host cannot establish a
distinct owner.

Malformed and hostile-input cases cover no operands on the explicit form,
unknown options, informational-command arity, a leading-dash root with and
without `--`, empty arguments, control bytes, quotes, backslashes, non-UTF-8
bytes where the host permits them, overlong roots or PATH components, too many
roots or components, aggregate-byte overflow, a symlink loop, and an
unreadable path when the fixture can reliably provoke `EACCES`. They verify
ASCII-safe diagnostics, status `2`, and empty stdout on reject-closed
failures. A closed stdout pipe or equivalent write-failure fixture verifies
status `2` without requiring complete stdout. Help and usage fixtures must
pin the synopsis for the exclusive modes.

Both GCC and Clang must compile and link `src/pathaudit.c` as C17 with
`-Wall -Wextra -Wpedantic -Werror` and no warnings. Formatting checks,
clang-tidy with warnings treated as errors, cppcheck with a nonzero error exit,
and the Clang static analyzer must pass. AddressSanitizer with leak detection
and UndefinedBehaviorSanitizer with halt-on-error must execute the functional
and hostile-input cases. Valgrind should cover the same paths when available;
an unavailable optional host tool must be reported rather than represented as
a pass.

Regression coverage pins the complete CLI, taxonomy (including
`UNSAFE_OWNER`), symlink final-target semantics, permission, escaping,
ordering relative to permission and `SHADOWED` findings, diagnostic, limit,
and exit-status contract above, including the `PATH_UNSET` versus empty-`PATH`
distinction. Repository README text, `man/pathaudit.1`, and changelog entries
must describe the modes, must name `UNSAFE_OWNER` for the ownership rule, and
must not claim that pathaudit never reads `PATH` or that ownership policy is
universally ignored. Repository-wide acceptance also runs all pre-existing
`sysdiff` shell, pytest, fixture, malformed-input, benchmark, sanitizer, and
Valgrind gates required by the existing quality surface. The new build and
test wiring must preserve every existing `sysdiff` command, output byte,
diagnostic, exit status, artifact, install behavior, and test result; this
slice authorizes no change to `sysdiff` and does not claim a `pathaudit`
release.
