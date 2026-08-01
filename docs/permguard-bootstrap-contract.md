# `permguard` Bootstrap Contract

## Authority

This file is the sole live product contract for `permguard` in this
repository. The closed taxonomy, CLI, diagnostics, emission model, and exit
statuses below are normative for `src/permguard.c`, `tests/test_permguard.py`,
`man/permguard.1`, and the README/CHANGELOG `permguard` sections.

Any other `docs/permguard*.md` or `plans/permguard*.md` file is superseded and
non-authoritative, including
`docs/permguard-first-vertical-slice-contract.md` and
`plans/permguard-first-vertical-slice-plan.md`. Those drafts describe a
different one-code taxonomy (`WORLD_WRITABLE_FILE` only), different help text,
symlink-as-clean behavior, reject-closed buffering, and input limits that this
bootstrap does not implement. Do not treat them as current product authority,
and do not mix their predicates or diagnostics into this slice.

## Overview

`permguard` is a small, read-only ISO C17 command-line utility for inspecting
the permission bits of explicitly named filesystem objects. The bootstrap
slice accepts one or more path operands and obtains each operand's own metadata
with POSIX `lstat`. It never replaces an operand with a canonical path, opens
an operand for content access, or follows a final symbolic link. Normal
intermediate-component resolution performed by the operating system is
unavoidable, but the final directory entry is always the object classified.

The utility reports a closed four-member permission-hazard taxonomy:
group-writable, other-writable, set-user-ID, and set-group-ID. These are
point-in-time observations of `st_mode`, not conclusions about exploitability,
ownership trust, effective access, ACLs, or a user's ability to modify an
object. A successful scan does not lock the filesystem against later changes.
The process is strictly observational: it does not alter modes, ownership,
contents, timestamps, names, links, or directory entries. At startup it
ignores `SIGPIPE` so a closed stdout pipe becomes a checked stdio failure
rather than asynchronous signal termination.

## CLI Surface

The operational command is:

```text
permguard [--] PATH...
```

At least one `PATH` operand is required. Before `--`, an argument beginning
with `-` is an option; `--` ends option parsing and permits leading-dash
paths. The only informational forms are `permguard --help` and
`permguard --version`; each must be the sole argument, write its result to
stdout, leave stderr empty, and return `0`. `--help` writes exactly:

```text
usage: permguard [--] PATH...
Inspect explicitly supplied paths without following symbolic links.
```

with one LF after each line. `--version` writes exactly `permguard 0.1.0\n`.
A bare `--`, no arguments, an unknown option, or extra arguments accompanying
an informational option returns status `2`, writes no stdout, and writes a
stable ASCII diagnostic plus `usage: permguard [--] PATH...\n` to stderr.
No-operand and bare-`--` failures use `permguard: USAGE\n`. Unsupported
options use `permguard: UNKNOWN_OPTION: "ESCAPED_OPTION"\n` with the same
quoted-byte escaping as findings. No other options are defined.

For every successfully inspected non-symbolic operand, each present hazard is
written to stdout as:

```text
HAZARD<TAB>PATH<LF>
```

`HAZARD` is one taxonomy token defined below. `PATH` is a double-quoted,
byte-preserving representation of the original operand: printable ASCII
bytes are literal except `"` and `\`, which are escaped as `\"` and `\\`;
all other bytes use uppercase `\xHH`. Findings are ordered first by original
operand position and then by the fixed taxonomy order `GROUP_WRITABLE`,
`OTHER_WRITABLE`, `SET_USER_ID`, `SET_GROUP_ID`. Duplicate operands are
inspected and reported independently; paths are never sorted or deduplicated.
Findings for a successful operand may be emitted as soon as that operand is
classified; the implementation need not buffer all findings until every
`lstat` completes.

Operational diagnostics use the same quoted-path escaping and one record per
rejected operand, in operand order:
`permguard: MISSING: "PATH"\n` when `lstat` reports `ENOENT` for a non-empty
path, `permguard: INACCESSIBLE: "PATH"\n` when it reports `EACCES`,
`permguard: SYMBOLIC_LINK: "PATH"\n` when `lstat` identifies a final symlink,
and `permguard: INSPECTION_ERROR_N: "PATH"\n` for any other `lstat` failure,
where `N` is the captured decimal `errno`. An empty-string operand is always
reported as `INSPECTION_ERROR_N` even when the host `lstat` returns `ENOENT`,
so it stays distinct from a non-empty missing path. Checked stdout write or
flush failure reports `permguard: STDOUT_WRITE\n` and status `2`. Diagnostics
go only to stderr. The utility attempts every operand after valid CLI parsing,
even after an operational error, so a mixed run reports all independently
observable findings and errors. Ordering is deterministic within each output
stream; no ordering between stdout and stderr is promised after shell stream
merging.

## Hazard Taxonomy

The taxonomy is closed and contains exactly four independent predicates, all
evaluated directly against the successful `lstat` result for a non-symbolic
operand. `GROUP_WRITABLE` is present when `(st_mode & S_IWGRP) != 0`.
`OTHER_WRITABLE` is present when `(st_mode & S_IWOTH) != 0`.
`SET_USER_ID` is present when `(st_mode & S_ISUID) != 0`.
`SET_GROUP_ID` is present when `(st_mode & S_ISGID) != 0`. The standard mode
macros must be used; numeric literals must not substitute for them.

The four predicates apply to the named object's own mode bits without
file-type heuristics. Thus a file or directory may report any applicable
combination, and one operand may produce up to four lines in the fixed rank
above. Owner writability, read bits, execute bits, the sticky bit, UID, GID,
filename, extension, and effective access neither create nor suppress a
finding. A final symbolic link is never classified: it is an operational
rejection with status `2`, whether its target is safe, hazardous, missing, or
inaccessible. No `stat`, `realpath`, target open, or access check may be used
to obtain or infer target metadata.

No additional finding code is reserved or implied. In particular, the
bootstrap does not classify ownership, sticky-bit policy, Linux capabilities,
ACL entries, extended attributes, file contents, mount options, or package
provenance. Expanding or changing the four predicates requires an explicit
contract revision and matching implementation and test work.

## Exit Statuses

Status `0` means either a successful sole-argument `--help` / `--version`, or
CLI parsing succeeded, every operand was inspected by `lstat`, no operand was
a symbolic link, and none of the four defined hazards was present. For an
operational scan both stdout and stderr are empty; informational forms write
their fixed stdout and leave stderr empty. Status `1` means parsing and
all operand inspections succeeded, no operand was a symbolic link, and at
least one defined hazard was found. In that case stdout contains all findings
in deterministic order and stderr is empty.

Status `2` means either a usage error or at least one operational operand
error. Missing paths, inaccessible paths, final symbolic links, and all other
`lstat` failures are operational errors. For a valid mixed invocation,
`permguard` continues inspecting later operands, emits findings for every
successfully inspected hazardous operand, emits one stderr diagnostic for
each failed or symbolic-link operand, and ultimately returns `2`. Operational
error precedence therefore overrides a simultaneous hazard that would
otherwise yield status `1`. A usage error prevents all inspection and leaves
stdout empty.

Statuses `0`, `1`, and `2` exhaust normal program returns. Internal failures
such as allocation or checked-output failure are also operational status `2`
with a stable stderr diagnostic; they never become a clean or hazard-only
result. Tests must compare the numeric status and complete stdout and stderr
bytes, because a mixed status `2` may intentionally contain valid findings as
well as diagnostics.

## Constraints

The implementation must remain small and auditable C17, use strict
warning-as-error builds, and depend only on the C library plus the required
POSIX/Linux metadata interface. It is a one-shot, read-only process: no call
may repair permissions, change ownership, write inspected content, rename or
unlink entries, create persistent state, execute an operand, elevate
privileges, or launch a service. Operand bytes are treated as hostile and
must not inject terminal controls or extra output records.

Explicit non-goals are recursion, permission repair, configuration files,
privilege escalation, package integration, ACL interpretation, and
extended-attribute interpretation. The slice also does not enumerate
directory children, traverse ancestors, read `PATH`, search commands, expand
globs, canonicalize or deduplicate operands, monitor changes, provide a
daemon, use networking or telemetry, or claim race-free authorization. Shell
glob expansion, if any, occurs before `permguard` and is not utility behavior.

The utility must perform one `lstat` attempt per operand after successful CLI
parsing and must not follow final symbolic links under any condition. Tests
and implementation should keep ownership and cleanup explicit, check all
output operations, capture `errno` immediately after a failed `lstat`, avoid
locale-dependent error text, and leave fixture modes and contents unchanged.

## Acceptance Checks

- **AC-01 — CLI and read-only boundary.** Build under strict C17 with GCC and
  Clang. Verify no operands, bare `--`, and unknown options produce exact
  usage failures, while `--` permits a leading-dash operand. Snapshot fixture
  modes and contents before and after every scan to prove the utility is
  read-only.
- **AC-02 — Temporary file and directory fixtures.** Create files and
  directories beneath an isolated temporary directory, apply explicit modes
  after creation so umask cannot define the oracle, and verify clean and
  hazardous results from each object's own metadata.
- **AC-03 — Every mode bit and combinations.** Independently exercise
  `S_IWGRP`, `S_IWOTH`, `S_ISUID`, and `S_ISGID`, then exercise two-, three-,
  and four-bit combinations. Assert exactly one line per present bit in the
  fixed hazard order and no line for absent bits.
- **AC-04 — Multiple operands and stable output.** Mix clean and hazardous
  files and directories in deliberately non-lexical command-line order,
  include a duplicate, and verify byte-identical repeated stdout in operand
  order and taxonomy order without sorting or deduplication.
- **AC-05 — Missing and inaccessible paths.** Verify a missing operand and a
  capability-gated inaccessible operand receive escaped, stable stderr
  diagnostics and status `2`. A skipped inaccessible case must state why the
  host cannot produce `EACCES`; it must not be reported as a pass.
- **AC-06 — Symbolic links never followed.** Create a link to a safe target
  and a link to a hazardous target. Each link must yield the same
  `SYMBOLIC_LINK` diagnostic and status `2`, with no finding derived from
  either target. Include a dangling link as an additional regression fixture.
- **AC-07 — Mixed-success behavior.** Invoke with hazardous, missing, clean,
  symbolic-link, and hazardous operands. Verify all operands are attempted,
  successful findings remain in operand/taxonomy order, errors remain in
  operand order on stderr, and the final status is `2`.
- **AC-08 — All three statuses and diagnostics.** Pin complete stdout,
  stderr, and status for a clean run (`0`), a hazard-only run (`1`), usage
  failures (`2`), and operational or mixed failures (`2`). Repeated runs over
  unchanged fixtures must be byte-identical.
- **AC-09 — Narrow inspection surface.** Source and behavioral checks confirm
  one `lstat` attempt per valid operand, no `stat`, `realpath`, `access`,
  target opening, recursion, or mutation, and no taxonomy beyond the four
  named tokens.
