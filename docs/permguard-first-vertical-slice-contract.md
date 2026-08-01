# `permguard` First Vertical-Slice Contract

## Overview

`permguard` is a small, read-only ISO C17 command-line utility that inspects
only filesystem paths explicitly named by the operator. Its first vertical
slice answers one deliberately narrow question: does any named directory entry
describe a world-writable regular file? The ordinary invocation performs that
check directly; there is no `--scan`, `--enable`, policy-selection, or other
enabling flag. The process does not read the process `PATH`, search for
commands, or inspect directories merely because they participate in command
lookup. Those behaviors belong to `pathaudit`; `permguard` remains a separate
utility for metadata checks on explicit operands.

Each operand is classified from exactly one successful `lstat`-style metadata
lookup. The final symbolic link is therefore inspected as a link and is never
followed to its target. Intermediate pathname resolution retains the normal
operating-system semantics needed to reach the final directory entry. The
implementation records every successful classification in a bounded observation
array and emits no finding until every operand's `lstat` has completed, so a
later inspection failure discards earlier hazardous observations and leaves
stdout empty. Results are point-in-time observations: filesystem state can
change before or after the lookup, and a clean result is neither a lock nor a
general safety claim.

Inspection requires no special privilege and never changes file ownership,
mode, or contents. The UID and GID returned by `lstat` are outside the initial
hazard policy: a file is neither trusted nor distrusted because of its owner,
and the program does not compare ownership with the real or effective process
identity. Classification never calls `access`, never opens the inspected
object for I/O, and never executes it. In the C implementation, `argv` strings
remain borrowed storage owned by the C runtime; any observation array or
rendering buffer is owned by `permguard`, bounded before allocation, and
released on every normal error or success path. No pointer into temporary
storage may outlive that storage.

All parsing, classification, ordering, and path rendering are byte-oriented
and locale-independent. Hostile operand bytes must not become terminal control
sequences or create extra output records. Linux is the primary runtime; the
language contract is ISO C17, with the POSIX `lstat` interface and mode macros
as an explicit platform dependency.

## CLI Surface

The operational spelling is exactly:

```text
permguard [--] PATH...
```

At least one `PATH` is required. Before `--`, any argument beginning with `-`
is treated as an option; `--` ends option parsing and permits path operands
such as `-report`. After the terminator, every remaining argument is an
operand, including another literal `--`. The only informational forms are
`permguard --help` and `permguard --version`; each must be the sole argument,
write its result to stdout, leave stderr empty, and return `0`. No operands, a
bare terminator, an unknown option, or extra arguments accompanying an
informational option are usage errors. The utility never reads stdin,
configuration, locale policy, or environment variables to discover operands
or change the hazard rule.

Help output is exactly:

```text
usage: permguard [--] PATH...
Detect world-writable regular files without following symbolic links.
```

with one LF after each line. Version output is exactly
`permguard 0.1.0\n`. A finding is one stdout record in this exact form:

```text
WORLD_WRITABLE_FILE<TAB>"ESCAPED_PATH"<LF>
```

`<TAB>` means byte `0x09`. Inside the quotes, printable ASCII bytes `0x20`
through `0x7e` are copied literally except `"` and `\`, which become `\"` and
`\\`. Every other byte is rendered as uppercase `\xHH`. Rendering preserves
the original operand bytes: paths are not decoded as Unicode, normalized,
canonicalized, or replaced by link targets. The same escaping rule applies to
any path printed on stderr.

Findings are emitted in command-line operand order, including one record for
each hazardous duplicate operand. A given operand can emit at most one record.
No sorting, locale behavior, directory enumeration, or filesystem discovery
may change this order. A completed clean scan writes nothing; a completed
hazard scan writes findings only to stdout and leaves stderr empty.

Before metadata inspection, the implementation rejects more than 65,536
operands, an operand longer than 65,536 bytes excluding its terminating NUL,
or aggregate operand storage greater than 1 MiB including terminating NULs.
All additions and allocation multiplications must be checked before they are
performed. Linux argument strings cannot contain an embedded NUL; every other
byte accepted by the operating system is opaque hostile input and must be
handled without truncation, injection, undefined behavior, or unbounded
allocation.

Usage diagnostics are the fixed ASCII line `permguard: USAGE\n` followed by
`usage: permguard [--] PATH...\n`. An unknown option instead begins with
`permguard: UNKNOWN_OPTION: "ESCAPED_OPTION"\n` and is followed by that same
usage line. Non-usage failures use one stable line:
`permguard: PATH_COUNT_LIMIT\n`,
`permguard: PATH_LENGTH_LIMIT: "ESCAPED_PATH"\n`,
`permguard: PATH_BYTES_LIMIT\n`, `permguard: OUT_OF_MEMORY\n`,
`permguard: INSPECTION_ERROR_N: "ESCAPED_PATH"\n`, or
`permguard: STDOUT_WRITE\n`. In `INSPECTION_ERROR_N`, `N` is the unsigned
decimal `errno` captured immediately after the failed `lstat`; localized
`strerror` text is forbidden. Validation and inspection choose the first
failure in operand order, so the diagnostic selection is deterministic. The
process ignores `SIGPIPE` so a closed stdout becomes a checked stdio failure
that reports `STDOUT_WRITE` rather than asynchronous signal termination; a
`signal(3)` setup failure on that ignore path is ignored and must never be
mislabeled as `OUT_OF_MEMORY`.

## Closed Hazard Taxonomy

The initial taxonomy is closed and contains exactly one hazard:
`WORLD_WRITABLE_FILE`. It applies if and only if the single successful
`lstat` result satisfies both `S_ISREG(st_mode)` and
`(st_mode & S_IWOTH) != 0`. Owner-write or group-write permission without the
other-write bit is clean. Execute, read, set-user-ID, set-group-ID, and sticky
bits neither create nor suppress this finding. A world-writable regular file
that also carries execute or set-ID bits still emits exactly one
`WORLD_WRITABLE_FILE` record; no additional or historical hazard token is
emitted alongside it. The implementation must use the standard file-type and
mode-bit macros rather than infer the result from a filename, extension,
effective-access check, or attempt to open the object.

A world-writable directory, symbolic link, socket, FIFO, block device,
character device, or any other non-regular object is outside the taxonomy and
therefore emits no finding after successful inspection. A symbolic link to a
world-writable regular file is also clean for this invocation because the link
itself, not its target, is classified. Dangling final symbolic links are
successfully classifiable links rather than missing-target errors. Failure to
resolve an intermediate component remains an operational inspection failure.

No other code is reserved or implied. In particular, the slice does not emit
findings for unsafe ownership, group writability, world-writable directories,
missing sticky bits, set-ID executables, ACLs, extended attributes,
capabilities, immutable flags, mount policy, or file contents. Future taxonomy
expansion requires an explicit contract revision and matching tests; an
implementation must not silently add heuristics under the existing version or
reuse `pathaudit` findings merely because both utilities inspect permission
metadata.

## Exit Statuses

Exit status `0` means every explicitly supplied operand was successfully
inspected and none matched `WORLD_WRITABLE_FILE`. Successful `--help` and
`--version` also return `0`. For an operational scan, status `0` requires
empty stdout and stderr. Successfully inspecting a symlink, directory,
special file, owner-only writable regular file, or group-only writable regular
file can therefore contribute to a clean result.

Exit status `1` means all validation and inspection completed and at least one
world-writable regular-file finding was emitted. It is the hazard-found
outcome, not an operational error. One or many findings, including repeated
hazardous operands, all produce the single process status `1`; stderr remains
empty.

Exit status `2` combines usage and operational failures: invalid CLI grammar,
an input-limit violation, allocation failure, a failed `lstat`, or a failed
stdout write or flush. The utility validates all operands and completes all
metadata lookups before emitting the first finding, so usage, limit,
allocation, and inspection failures leave stdout empty even if an earlier
operand was hazardous. Inspection stops at the first failed operand.
Because `SIGPIPE` is ignored, a closed stdout pipe is reported through this
same status `2` / `STDOUT_WRITE` path instead of killing the process.
Output failure may leave a partial stdout record or earlier complete records,
because already-written bytes cannot be recalled, but it still returns `2`
and attempts the fixed `STDOUT_WRITE` diagnostic. A stderr write failure does
not invent another exit class. Statuses `0`, `1`, and `2` exhaust normal
returns; termination by a signal other than the ignored `SIGPIPE` case remains
an operating-system outcome.

## Non-Goals

This slice does not recurse into supplied directories, enumerate children,
walk ancestors, expand globs, follow final symbolic links, canonicalize paths,
or deduplicate operands. It does not read or analyze the process `PATH`,
resolve command names, detect command shadowing, or audit the writability or
ownership of PATH directories. Those PATH-oriented responsibilities remain
with `pathaudit`, and no shared name or permission vocabulary merges the two
products.

The utility does not remediate findings or call `chmod`, `chown`, unlink,
rename, or content-writing interfaces. It does not elevate or drop
privileges, execute inspected files, parse file contents, simulate access for
a user or group, recommend a replacement mode, or claim that a reported file
is exploitable. Ownership policy, directory policy, set-ID policy, ACLs,
Linux capabilities, extended attributes, mount flags, namespaces, MAC
frameworks, package provenance, and broad permission-policy engines are
outside the first slice.

There is no daemon mode, watch mode, scheduled service, networking, telemetry,
remote lookup, database, state file, cache, plugin system, configuration
language, or interactive prompt. Machine-readable formats beyond the fixed
line record, recursion controls, remediation flags, install/package wiring,
and release publication are also non-goals. The program is a bounded,
one-shot metadata observer and does not promise race-free authorization or
continuous enforcement.

Baseline persistence, package inventory, and service inspection are explicitly
outside this slice: `permguard` neither records a prior scan nor queries a
package manager or service manager. Additional permission hazard classes are
also non-goals; group writability, directory writability, set-ID bits,
ownership, ACLs, and capabilities must not be promoted to findings without a
future contract revision.

## Acceptance Checks

Every check below is normative. The delivery plan maps each identifier to
`tests/test_permguard.py` and to a deterministic command; a skipped
capability-dependent case is evidence of a skip, not a pass.

- **AC-01 — Strict C17 build and complete result capture.** GCC and Clang must
  compile with `-std=c17 -Wall -Wextra -Wpedantic -Werror`. Behavioral tests
  compare the complete stdout bytes, stderr bytes, and numeric exit status.
- **AC-02 — Closed predicate.** Private, owner-writable, and group-writable
  regular files are clean. A regular file with `S_IWOTH` produces exactly one
  `WORLD_WRITABLE_FILE` record, including when execute or set-ID bits are also
  present; no former or additional hazard code is emitted.
- **AC-03 — Non-regular objects.** World-writable directories, FIFOs, sockets,
  and live or dangling final symlinks are clean when `lstat` succeeds. A final
  symlink to a hazardous regular file remains clean, proving that the final
  component is not followed.
- **AC-04 — Exact CLI grammar.** Tests pin exact help, version, no-operand,
  bare-`--`, unknown-option, and informational-option-with-extra-argument
  results. They also cover the terminator, leading-dash operands, duplicate
  operands, ordinary invocation without an enabling flag, and operand-order
  rather than lexical-order emission.
- **AC-05 — Hostile path rendering.** Finding and diagnostic paths containing
  spaces, tabs, newlines, quotes, backslashes, DEL, and non-UTF-8 bytes where
  supported are escaped exactly. Each record remains one printable ASCII line,
  and no hostile byte can create a forged record or terminal control sequence.
- **AC-06 — Deterministic bounds.** Tests exercise the individual path length,
  aggregate argv bytes, and operand-count boundaries and one-past values when
  the host can construct them. Static seams confirm the constants and
  overflow-before-addition/allocation guards when `ARG_MAX` prevents a dynamic
  boundary case.
- **AC-07 — Operational failures.** A missing entry, an `ENOTDIR` intermediate
  component, an intermediate symlink loop, and a capability-gated inaccessible
  path produce status `2`, empty stdout, and the exact escaped
  `INSPECTION_ERROR_N` diagnostic using the immediately captured numeric errno.
- **AC-08 — Reject-closed inspection.** A hazardous operand followed by an
  operand whose `lstat` fails returns `2` with empty stdout. No finding is
  emitted until validation and inspection of every operand has succeeded.
- **AC-09 — Checked output.** A closed stdout pipe or equivalent deterministic
  fixture returns `2` and reports `STDOUT_WRITE`; this is the only failure
  class that may leave partial stdout because already-written bytes cannot be
  recalled.
- **AC-10 — Repeatability.** Repeated invocations against unchanged fixtures
  produce byte-identical status, stdout, and stderr. Duplicate operands remain
  duplicated, and findings retain command-line order without locale-dependent
  sorting.
- **AC-11 — Narrow filesystem surface.** Source and behavior checks establish
  one `lstat` per operand, no final-component following, no `stat`, `realpath`,
  target opening, `access`, or traversal, and no UID/GID influence on the
  hazard decision. The scan leaves inspected modes and contents unchanged.
- **AC-12 — Quality and contract integrity.** Formatting, clang-tidy,
  cppcheck, the Clang analyzer, AddressSanitizer, UndefinedBehaviorSanitizer,
  and Valgrind cover the slice when available; unavailable optional tools are
  recorded as not run. Mechanical checks confirm the sole finding code and
  the exact six required substantive headings, including
  `Closed Hazard Taxonomy`.
