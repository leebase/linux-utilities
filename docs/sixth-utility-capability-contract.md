# `openunlink` Initial Vertical-Slice Implementation Contract

## Utility Identity

The sixth utility is exactly one executable named `openunlink`. Its one purpose
is to inspect one explicitly supplied Linux process ID and report that
process's open file descriptors whose followed targets are observed as stable
regular files with final `st_nlink == 0`. It is not a process browser, storage
estimator, file-recovery tool, or process-control tool.

This identity is already unique in the repository's mission state. Governed run
`787b9bb3d830`, `project-plan.md`, `ROADMAP.md`, `STATUS.md`, `DECISIONS.md`,
`context.md`, `sprint-plan.md`, `WHERE_AM_I.md`, and `result-review.md` all
commit **Bootstrap `openunlink` explicit-process zero-link regular-file
descriptor reporting** as the sixth mission. No new candidate selection is
made here. `inodealias` remains the fourth planning mission, `shebangcheck`
remains the fifth, and the reviewed `sparsemap` evidence concerns only a later
mission.

This document is the authoritative implementation and acceptance contract for
the initial `openunlink` vertical slice. Source, tests, fixtures, Make targets,
the section-1 manual, user documentation, smoke evidence, and independent
review produced by the governed implementation run must conform to it. Where
`plans/sixth-utility-mission-evaluation.md`, its review, or any portfolio
summary conflicts with this document, this document controls. A behavioral
change requires an explicit contract revision before code or tests adopt it.
The rules and acceptance oracles below close the design questions recorded as
`SIXTH2-M1`, `SIXTH2-M2`, and `SIXTH2-M3`; they are not optional guidance.

Those closures are fixed and mechanically gated: `SIXTH2-M1` retains and
inspects the first 65,536 (`65536`) valid entries in observed enumeration
order, reports their findings, and makes the 65,537th (`65537`) valid entry one `FD_COUNT_LIMIT`
advisory; `SIXTH2-M2` limits the claim to `st_nlink == 0` and requires the
nonzero-link/NFS-silly-rename boundary in fixtures and user documentation; and
`SIXTH2-M3` makes stdout emptiness the status-1 caller discriminator. The
**Acceptance Checks** section contains a named anti-regression oracle for each
closure. An implementation that suppresses retained cap-boundary evidence,
claims that status 0 excludes every deleted file, or makes advisory-only status
1 indistinguishable from a finding-bearing result does not satisfy this
contract.

## Overview

`openunlink` is a finite, read-only, Linux/procfs-specific command. It accepts
one canonical decimal PID, opens only the fixed `/proc/PID/fd` directory,
retains a bounded descriptor-number set, orders that set numerically, and uses
directory-relative metadata and link-text inspection. A finding depends only
on repeated followed-target metadata: the same device, inode, and regular-file
type must be observed around the link-text read, and the final observation must
have zero links. Procfs link text, including a cosmetic ` (deleted)` suffix,
is escaped display context and never the finding predicate or a path to open.

The implementation is one small ISO C17 translation unit using libc and narrow
Linux/POSIX directory, metadata, link, allocation, signal, and stdio
interfaces. System declarations must come from their platform headers under
`_POSIX_C_SOURCE=200809L` and `_FILE_OFFSET_BITS=64`; hand-written system-call
declarations and unchecked narrowing are forbidden. The runtime has no
service, helper daemon, configuration, persistence, network, telemetry,
plugin, or non-libc library dependency.

The result is point-in-time and deliberately narrow. A status-0 scan means
only that no retained, successfully inspected descriptor had a stable
zero-link regular-file target. It does not prove that the process holds no
object a user would call deleted: NFS silly-rename and other filesystem or
stacking behavior can keep a nonzero link count after unlink. It also does not
prove physical allocation, reclaimable byte count, future stability, or the
reason a link count became zero.

## Problem

An unlinked regular file can remain alive while a process holds an open
descriptor, which can make storage and file-lifetime behavior difficult to
diagnose. Manually correlating `/proc/PID/fd` link text with file metadata is
specialized and race-prone, while matching the display suffix ` (deleted)` is
not a reliable deletion test. The utility gives an operator one auditable
answer for one process they are already permitted to inspect: which retained
descriptors were observed to reference stable regular targets whose final
`st_nlink` was zero.

The contract intentionally reports descriptors, not unique files. Two
descriptors for the same `(st_dev, st_ino)` produce two lines, because grouping
would overlap the planned `inodealias` identity mission and would hide the
process-descriptor relation being diagnosed. The reported `st_size` and
escaped link target are observation context only. Neither is interpreted as
physical storage, reclaimability, pathname authority, ownership, safety, or a
recommendation to terminate or modify the process.

Procfs visibility is an explicit environmental assumption, not a silent
success case. The PID is interpreted in the caller's current PID and mount
namespaces, `/proc` must be mounted at its fixed conventional location, and
ordinary credential and `hidepid` policy apply. An observed `ENOENT` cannot
distinguish an exited PID, a hidden PID, or absent procfs; the diagnostic
truthfully reports the observed class without claiming which cause occurred.

## Constraints

The initial capability list is closed and complete:

1. Recognize only the three command forms defined under **CLI Surface** and
   parse one canonical ASCII-decimal PID in `1..INT_MAX`.
2. Construct only the fixed byte path `/proc/PID/fd` in checked fixed storage,
   then call `open` with `O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW`.
   Duplicate that directory descriptor for `fdopendir` and keep the original
   descriptor as the distinct owner used for later directory-relative
   inspection. No environment value or caller-controlled path component is
   accepted.
3. Ignore only `.` and `..`; accept descriptor entry names only as canonical
   ASCII decimal in `0..INT_MAX`, where zero is exactly `0` and every positive
   value begins with `1..9`; retain the first 65,536 valid entries returned by
   the observed enumeration; and, on a 65,537th valid entry, stop enumeration
   and record one `FD_COUNT_LIMIT` advisory instead of discarding the retained
   partial evidence. The retained subset is explicitly the first observed
   subset, not a promise that the numerically lowest descriptors were
   selected. Retained values are sorted numerically before inspection.
4. Reconstruct each retained descriptor as canonical decimal text and inspect
   it with `fstatat(directory_fd, name, ..., 0)`, bounded `readlinkat`, and a
   second `fstatat(directory_fd, name, ..., 0)`, all relative to the retained
   process-fd directory. Flags `0` deliberately follow the procfs magic link.
   Require equal `st_dev`, `st_ino`, and regular-file type around the
   link-text read before considering the final `st_nlink`.
5. Emit the sole finding `OPEN_UNLINKED`, or one applicable per-descriptor
   advisory, in ascending retained-FD order. Stable findings survive other
   descriptors' churn, unreadability, range failures, target-length failures,
   and the descriptor-count advisory.
6. Escape every procfs-supplied display byte, check all allocation arithmetic
   and stream completion, ignore `SIGPIPE`, and reduce the run to the three
   statuses defined under **Exit Statuses**.

These six items are the entire product capability. Enumeration must set
`errno = 0` before each `readdir`, distinguish end-of-directory from error,
and finish `closedir` on the duplicate before descriptor inspection begins.
Every failing system or stdio call has its error state captured immediately,
before cleanup, allocation, formatting, or another library call can replace
it; classification uses only that captured value.
The first 65,536 valid entries are the first in observed `readdir` order, not
the numerically lowest 65,536. Detection of the 65,537th valid entry ends
enumeration immediately, records one advisory, and intentionally leaves all
later entries unobserved. Malformed, out-of-range, or duplicate retained names
encountered before that boundary are `PROCESS_SCAN`; they are never ignored or
interpreted with locale-sensitive character predicates.

### Ownership and allocation

`argv` and its strings are borrowed for the process lifetime and are neither
modified nor freed. The original process-directory descriptor is owned by the
scanner and closed exactly once. Before a successful `fdopendir`, the scanner
owns the duplicate; after success, the `DIR *` exclusively owns it and
`closedir` is its only close. A failed `fdopendir` leaves the duplicate with
the scanner for cleanup. Each `readdir` name is borrowed only until the next
directory operation, so the implementation parses and copies only its numeric
value and never retains a `dirent` pointer. No descriptor target is opened and
therefore the scanner never owns a target-content descriptor.

On the scan path, all heap allocation completes before any finding or advisory
is attempted. The scanner owns exactly one 65,536-element descriptor-number
array, one 65,537-byte reusable link-text buffer, and one reusable worst-case
finding-line buffer. Each successful allocation has one owner and one cleanup
site; partial initialization, `fdopendir` transfer, and every operational exit
must be safe against leaks, double free, and double close. No per-finding
allocation, result list, inode table, or capacity growth is permitted.
Allocation failure selects `MEMORY` before descriptor output. Informational
and rejected CLI forms need not allocate these scan buffers.

The fixed path and line bounds must be mechanically derived with checked
`size_t` arithmetic, not guessed. With the required eight-bit bytes,
`INT_DECIMAL_BOUND` is `3 * sizeof(int)` and `UINTMAX_DECIMAL_BOUND` is
`3 * sizeof(uintmax_t)`; each safely bounds the corresponding unsigned decimal
digit count without a terminator. The process-path capacity is the bytes in
`"/proc//fd"` plus `INT_DECIMAL_BOUND` digits plus one NUL, and the descriptor
name capacity is `INT_DECIMAL_BOUND + 1`. The finding-line capacity is the
bytes in `"OPEN_UNLINKED\tpid=\tfd=\tsize=\ttarget=\"\"\n"`, plus two
`INT_DECIMAL_BOUND` fields, one `UINTMAX_DECIMAL_BOUND` field, four output
bytes for each of 65,536 target bytes, and one terminating NUL. The target
length returned by `readlinkat` is authoritative even if a test seam supplies
embedded NUL; escaping and output use that length, never `strlen`.

For a retained descriptor, classification follows this exact first-applicable
sequence. The first `fstatat` failure is `FD_UNSTABLE` only for `ENOENT`,
`ENOTDIR`, or `ESTALE`; every other failure is `FD_UNREADABLE`. A non-regular
first target is silent and no `readlinkat` is issued. For a regular first
target, `readlinkat` failure is `FD_UNSTABLE` only for `ENOENT`, `ENOTDIR`,
`ESTALE`, or link-type `EINVAL`; every other failure is `FD_UNREADABLE`. A
65,537-byte result is immediately `TARGET_LENGTH_LIMIT`. Only a link result of
at most 65,536 bytes proceeds to the second `fstatat`: `ENOENT`, `ENOTDIR`, or
`ESTALE` is `FD_UNSTABLE`; every other failure is `FD_UNREADABLE`; unequal
device, inode, or file type is `FD_UNSTABLE`; a stable nonzero-link target is
silent; a stable zero-link target with a negative `st_size` or one not
losslessly representable as `uintmax_t` is `FD_SIZE_RANGE`; otherwise the
descriptor is `OPEN_UNLINKED`. Classification then ends for that descriptor.

## CLI Surface

The complete command surface is:

```text
openunlink --help
openunlink --version
openunlink PID
```

`--help` and `--version` are options only when each is the sole argument.
There is no short option, `--` separator, option combination, default PID,
second operand, stdin mode, proc-root option, environment option, or
configuration file. `PID` consists only of bytes `0x30..0x39`, has no leading
zero, and represents a value in the inclusive range `1..INT_MAX`. Signs,
whitespace, empty text, overflow, suffixes, unknown options, missing PID,
extra operands, and informational options combined with anything else are
`USAGE`.

Successful `--help` stdout is exactly the following bytes, including the final
LF and with no trailing spaces:

```text
Usage: openunlink PID
       openunlink --help
       openunlink --version
Report zero-link regular-file descriptors for one Linux process.
```

Successful `--version` stdout is exactly `openunlink 0.1.0\n`. Both
informational forms leave stderr empty and return `0`. A usage failure leaves
stdout empty, writes exactly `openunlink: USAGE\n` to stderr on a best-effort
basis, and returns `2`.

Finding stdout consists of zero or more complete lines in ascending retained
descriptor order:

```text
OPEN_UNLINKED<TAB>pid=PID<TAB>fd=FD<TAB>size=BYTES<TAB>target="ESCAPED_TARGET"<LF>
```

`PID`, `FD`, and `BYTES` are canonical unsigned decimal text with no leading
zero except the value zero. `BYTES` is the lossless `uintmax_t` conversion of
the nonnegative final `st_size`, rendered with the matching `<inttypes.h>`
format macro; it is not a reclaim estimate. Inside the quotes, printable
ASCII `0x20..0x7e` is literal except `"` and `\`, which become `\"` and
`\\`; every other byte becomes uppercase `\xNN`. A `readlinkat` result of at
most 65,536 bytes is accepted and program-terminated; filling the 65,537-byte
sentinel buffer produces `TARGET_LENGTH_LIMIT` and no finding for that
descriptor.

Per-descriptor advisories are exact stderr lines
`openunlink: CODE: pid=PID fd=FD\n`. The count advisory is exactly
`openunlink: FD_COUNT_LIMIT: pid=PID\n`. PID-owned operational diagnostics
are `openunlink: CODE: pid=PID\n`; global operational diagnostics are
`openunlink: CODE\n`. The PID-owned set is exactly `PROCESS_NOT_FOUND`,
`PROCESS_ACCESS`, and `PROCESS_SCAN`; the global set is exactly `USAGE`,
`MEMORY`, and `STDOUT_WRITE`. When present, `FD_COUNT_LIMIT` is attempted
once before retained-descriptor inspection; other advisories follow ascending
retained-FD order. Each stream preserves that defined order, but no
cross-stream order is promised after a caller merges independently buffered
stdout and stderr. Stderr is best-effort: failure to write an advisory or
diagnostic does not change the already determined numeric status, and there
is no `STDERR_WRITE` result.

## Hazard Taxonomy

The initial taxonomy is closed and exhaustive. The implementation, tests, and
documentation may not invent another code without an explicit contract
revision. Exactly one finding code exists:

- `OPEN_UNLINKED`: both followed metadata observations identify the same
  device, inode, and regular-file type; the final `st_nlink` is zero; the final
  `st_size` is representable; and bounded link text is available for escaped
  display.

Exactly five status-1 advisory codes exist:

- `FD_COUNT_LIMIT`: a 65,537th valid descriptor entry was observed. The first
  65,536 observed entries remain inspectable and their findings remain
  reportable; later entries are outside this intentionally partial scan.
- `FD_UNSTABLE`: a retained entry vanishes, becomes stale, ceases to be a
  readable procfs link, or changes followed device, inode, or file type during
  bounded inspection. The errno mapping is closed: `ENOENT`, `ENOTDIR`, and
  `ESTALE` from either metadata call or `readlinkat`, plus `EINVAL` from
  `readlinkat` only, belong here.
- `FD_UNREADABLE`: another per-descriptor metadata or link-text operation
  fails, including permission, overflow, or I/O failure that does not establish
  the defined churn condition.
- `FD_SIZE_RANGE`: a stable zero-link regular target has a negative `st_size`
  or a size that cannot be converted losslessly to `uintmax_t`.
  This is defensive and has no expected production trigger under the mandated
  64-bit `off_t` configuration; the deterministic test seam must still cover
  it.
- `TARGET_LENGTH_LIMIT`: `readlinkat` fills the 65,537-byte sentinel buffer,
  so exact fit and truncation cannot be distinguished within the accepted
  65,536-byte display ceiling.

Exactly six status-2 operational codes exist:

- `USAGE`: command arity, option, PID grammar, or PID range is invalid.
- `PROCESS_NOT_FOUND`: opening fixed `/proc/PID/fd` reports `ENOENT` or
  `ENOTDIR`; this does not claim to distinguish exit, `hidepid`, namespace
  visibility, or absent procfs.
- `PROCESS_ACCESS`: opening fixed `/proc/PID/fd` reports `EACCES` or `EPERM`.
- `PROCESS_SCAN`: another process-directory open, duplication, `fdopendir`,
  entry-grammar, retained-duplicate, `readdir`, `closedir`, or final
  inspection-directory close failure occurs.
- `MEMORY`: a checked allocation for the fixed descriptor or reusable output
  storage fails before descriptor output begins.
- `STDOUT_WRITE`: any help, version, or finding stdout write, or the final
  stdout flush, fails. `SIGPIPE` is ignored so a closed pipe reaches this code
  instead of a signal-derived shell status.

At most one status-2 operational diagnostic is attempted per invocation. The
first operational failure reached in the defined execution order selects the
code; descriptor inspection and product output then stop, while required
cleanup continues. A cleanup failure selects `PROCESS_SCAN` only when no
operational code was already selected, and it never replaces an earlier code.
After a completed descriptor loop, final stdout flush precedes closing the
retained inspection descriptor, so output loss selects `STDOUT_WRITE`; only a
subsequent first failure of that close selects `PROCESS_SCAN`.

Silent successful per-descriptor outcomes are also closed: a first-observed
non-regular target, or a stable regular target whose final link count is
nonzero, emits neither finding nor advisory. A literal ` (deleted)` suffix
does not override those rules. If several faults could be imagined, the first
one reached by the operation and classification order in **Constraints**
controls that descriptor; no descriptor receives multiple advisory
lines.

## Exit Statuses

The stable exit-status set is exactly `0`, `1`, and `2`. Status `0` means
successful help or version output, or completion of the bounded scan with no
finding and no advisory. For a scan it means only “no retained, successfully
inspected descriptor had a stable zero-link regular target”; it must never be
described as proof that the process holds no deleted file, because some
filesystems retain a nonzero link count after unlink.

Status `1` means the scan completed without an operational code and classified
at least one finding or advisory. Every finding write necessarily completed,
because a failed finding write would instead select `STDOUT_WRITE` and status
`2`; advisory writes remain best-effort. The caller-facing discriminator is
normative: status `1` with byte-nonempty stdout means at least one complete
`OPEN_UNLINKED` finding line was emitted, while status `1` with byte-empty
stdout means no finding was classified and the result is advisory-only. In the
latter case the incompleteness explanation was attempted on stderr and might
itself be lost without changing status. Advisories use status `1`, rather than
operational status `2`, because retained descriptors remain valid bounded
evidence and the process directory was scanned to the declared boundary.

Status `2` means an operational code occurred and has precedence over statuses
`0` and `1`. `USAGE`, process-directory opening/enumeration, and `MEMORY`
failures occur before descriptor output and leave stdout empty. A final close
failure returns `PROCESS_SCAN` only after complete finding lines have been
flushed and advisories have already been attempted. `STDOUT_WRITE` may leave
any stdout byte prefix, including a partial final line. Output already written
is never retracted. Failure of best-effort stderr output neither creates a new
code nor changes the numeric result.

## Non-Goals

The initial slice does not scan all PIDs, infer a PID, inspect any PID other
than the single explicit operand, enter another PID or mount namespace, accept
a procfs root, read process names, users, cgroups, maps, `map_files`,
environment, command lines, or executable images, or acquire privilege. It
does not bypass `hidepid`, distinguish every cause of `ENOENT`, continuously
monitor, watch, cache, persist, compare scans, run a daemon, use telemetry,
contact a network, or integrate with cloud, container, service-manager, or
orchestration APIs.

It does not open, read, write, execute, recover, copy, hash, canonicalize,
rename, unlink, chmod, chown, or otherwise mutate a descriptor target. It does
not send a signal, close another process's descriptor, kill or restart a
process, or recommend remediation. Procfs target text is never traversed or
passed to a shell. The slice performs no PATH lookup and has no subprocess,
plugin, localization, structured-output, JSON, or configuration surface.

It does not group descriptors by inode, suppress duplicate descriptors,
estimate physical allocation or reclaimable storage, interpret `st_blocks`,
classify memfd/tmpfs/reflink/compression behavior, inspect mount policy, or
claim that zero link count is a complete definition of “deleted.” In
particular, a nonzero-link target retained through NFS silly-rename or similar
filesystem behavior is outside the finding predicate and can yield a narrow
status-0 result.

The governed delivery may create only the bounded `openunlink` source, focused
tests and fixtures, additive Make wiring, a section-1 manual, matching user and
quality documentation, and dedicated smoke/review evidence authorized by its
playbook. It may not alter the runtime behavior or contract of `sysdiff`,
`pathaudit`, or `permguard`, and it may not implement or modify the planned
`inodealias`, `shebangcheck`, or `sparsemap` utilities. Shared Make and
portfolio documentation changes must be additive and limited to truthful
`openunlink` integration.

Release-quality verification is a quality standard, not permission to install,
package, archive, tag, publish, or release `openunlink`. No install or
uninstall target, distribution member, package metadata, external write, or
release claim belongs to this vertical slice. The contract revision itself is
FRAME authority, not evidence that the subsequent source, tests, manual,
smoke, or quality gates already exist or pass; those claims require their own
governed steps and recorded results.

## Acceptance Checks

These checks are binding acceptance requirements for the implementation
governed by this contract. The FRAME edit does not satisfy them by itself;
the delivery must produce exact, independently reviewable evidence for every
applicable check before the vertical slice is accepted.

### Test seams

A test-only compile route must deterministically control process-directory
open and duplication, `fdopendir`/`readdir`/`closedir`, both `fstatat` calls,
`readlinkat`, the final descriptor close, allocation, stdout writes and flush,
and best-effort stderr writes. The production build must exclude the injected
state and must call the real interfaces through platform declarations. The
seam must model arbitrary ordered directory entries and arbitrary link bytes,
so descriptor-count, errno, identity, target-length, embedded-NUL, cleanup,
and output failures do not depend on timing, privileges, host limits, NFS, or
mount reconfiguration. Every failure injector needs a positive control that
would fail if the intended call or branch were bypassed.

### Fixture expectations

The integration fixture is a handshake-controlled same-UID child that reports
its PID and descriptor numbers only after it holds the requested objects, then
waits until the test explicitly releases it. It uses a private temporary
directory and ordinary local resources: a still-linked regular file, an
open-then-unlinked regular file, duplicated descriptors for the same unlinked
object, a filename literally ending in ` (deleted)`, and pipe/socket
non-regular descriptors. Tests requiring synthetic procfs names, very large
target text, NFS silly-rename behavior, impossible size ranges, or syscall
failures use the deterministic seam, not host privilege or flaky races.

- CLI oracles compare the exact help, version, finding, advisory, operational,
  and usage bytes defined above. They reject PID `0`, leading zero, signs,
  whitespace, empty and overflowing values, missing PID, extra operands,
  unknown options, and combined informational options with status `2`, empty
  stdout, and exact best-effort `USAGE` stderr.
- A handshake-controlled same-UID helper holds linked ordinary files, an
  unlinked regular file, two duplicated descriptors for one unlinked object,
  and non-regular pipe/socket descriptors. Linked-only input is byte-empty on
  both streams with status `0`; the unlinked file produces exact
  `OPEN_UNLINKED` output; duplicates produce separate numerically ordered
  lines; non-regular targets are silent; and repeat runs over a frozen fixture
  are byte-identical.
- Fixture or seam metadata proves a linked filename literally ending in
  ` (deleted)` remains silent when `st_nlink != 0`. A simulated
  silly-rename/nonzero-link case remains outside the finding predicate, and
  documentation tests require the narrow status-0 filesystem disclaimer in
  user-facing material.
- A deterministic directory seam supplies exactly 65,536 valid names without
  an advisory, then 65,537 names with a known finding among the retained first
  65,536. The latter must preserve that exact finding, emit exactly one
  `FD_COUNT_LIMIT`, omit later entries, and return `1`. Tests pin the
  first-observed subset rule and numeric ordering within that subset. This is
  the mechanical closure oracle for `SIXTH2-M1`; reverting to empty-stdout
  whole-scan failure at the cap must fail the suite.
- Seam-controlled disappearance, stale identity, descriptor reuse,
  unreadability, negative/unrepresentable size, and 65,537-byte target results
  produce the exact corresponding advisory. Each case returns `1`; an
  advisory-only case has byte-empty stdout and nonempty stderr, while mixed
  advisory/finding cases preserve complete stable finding lines. A dedicated
  shell-style caller oracle branches on status and stdout length to prove the
  status-1 discriminator required by `SIXTH2-M3`: nonempty stdout is a
  finding-bearing result; empty stdout is advisory-only.
- Link-text boundary oracles accept exactly 65,536 bytes using a 65,537-byte
  sentinel and classify a full 65,537-byte return as
  `TARGET_LENGTH_LIMIT`. Exhaustive byte fixtures cover space, quote,
  backslash, tab, LF, CR, NUL, other controls, DEL, and `0x80..0xff`, proving
  uppercase terminal-safe escaping and checked worst-case line capacity.
- Error fixtures inject opening `ENOENT`/`ENOTDIR`, `EACCES`/`EPERM`, and
  another errno to pin `PROCESS_NOT_FOUND`, `PROCESS_ACCESS`, and
  `PROCESS_SCAN`. Malformed or out-of-range observed entries, observed
  duplicates, directory read/close failure, and allocation failure produce
  their exact status-2 diagnostics before descriptor stdout. A final retained
  directory-close failure preserves earlier flushed complete findings but
  returns `2`. Compound fault injections prove that the first operational
  failure controls, cleanup does not replace it, and at most one operational
  diagnostic is attempted.
- Allocation oracles fail each of the three scan allocations in turn and
  require exact `MEMORY`, status `2`, empty stdout, and leak-free cleanup of
  every earlier resource. Counters prove that a successful 65,536-entry scan
  performs no `realloc` and no descriptor-loop allocation. Descriptor-transfer
  oracles cover duplicate failure, `fdopendir` failure, successful `DIR *`
  ownership transfer, `closedir` failure, and final original-descriptor close
  without a leak or double close.
- Closed stdout during help, version, or finding output and final-flush
  injection produce `STDOUT_WRITE` and status `2`, never a signal-derived
  shell status. A closed stderr or injected stderr failure confirms that
  advisory/diagnostic loss creates no `STDERR_WRITE` and does not alter the
  status already selected.
- Source and runtime audits prove that the product opens only fixed
  `/proc/PID/fd`; no target-content open/read, fork/exec, network, unlink,
  rename, chmod/chown, process-signal, or remediation call is reachable.
  Before/after fixture metadata and content hashes remain unchanged, and the
  helper observes no control action.
- Portability oracles build through platform headers with
  `_POSIX_C_SOURCE=200809L` and `_FILE_OFFSET_BITS=64`, require an at-least
  64-bit `off_t` and `CHAR_BIT == 8`, require lossless nonnegative-`off_t`
  conversion to `uintmax_t`, use the matching `<inttypes.h>` format macro, and
  reject hand-declared system prototypes or signed-character classification.
  Support is explicitly Linux with procfs; absent or restricted procfs must
  fail by the defined observed-error mapping rather than silently pass.
- The required Linux C quality floor passes strict GCC and Clang C17 builds
  with `-Wall -Wextra -Wpedantic -Werror`, clang-format, clang-tidy, cppcheck,
  and the Clang static analyzer. Unit, integration, regression, hostile-input,
  and fixture suites pass; ASan and UBSan exercise the focused taxonomy and
  cleanup paths; Valgrind reports no leaks, invalid access, descriptor leaks,
  or double close. Allocation and syscall seams include positive controls
  proving they can fail a defective implementation.
- Additive Make targets build and exercise `openunlink` without installing it;
  focused ordinary, ASan+UBSan, and Valgrind routes run the complete
  `tests/test_openunlink.py` contract surface. From a clean build state, the
  repository's complete `make quality` gate must exit `0` and include both
  the focused utility coverage and the pre-existing portfolio suite. Required
  compiler, analyzer, sanitizer, procfs, groff, or Valgrind unavailability is
  a loud gate failure, never a silent pass or release-quality skip.
- `man/openunlink.1` passes warning-gated groff rendering and states the exact
  synopsis, bytes, taxonomy, ordering, bounds, ownership-neutral read-only
  behavior, Linux/procfs and `hidepid` limits, point-in-time race boundary,
  target-text privacy exposure, and all non-goals. README, CHANGELOG,
  `docs/openunlink.md`, QUALITY, TESTING, and architecture summaries must agree
  with this contract. A documentation oracle requires the narrow status-0
  disclaimer, including NFS silly-rename as the concrete nonzero-link example;
  this is the mechanical closure oracle for `SIXTH2-M2`.
- A dedicated TEST AS USER baseline builds a temporary standalone
  `openunlink`, coordinates one linked and one unlinked same-UID fixture,
  validates exact output and statuses, and records successful start and core
  flow with empty blocking errors. Existing sysdiff-centered smoke counts only
  as aggregate regression evidence. Independent REVIEW must verify this
  contract, code ownership, all bounds and taxonomies, the no-content/no-control
  posture, filesystem honesty, and no unresolved Medium-or-higher mission
  finding before any implementation is accepted.

## AgentFlow Phase Applicability

FRAME is delivered by this authoritative contract: it fixes the sixth
utility's identity, one purpose, capability boundary, exact CLI and streams,
closed taxonomy, stable statuses, ownership, allocation, exclusions, and
acceptance criteria. TEST must encode those criteria before CODE is accepted;
CODE must remain one bounded C17 translation unit; DOCUMENT must mirror the
contract; and TEST + FIX must repair failures without silently widening the
surface. A change to any normative byte, predicate, code, limit, status, or
non-goal returns to FRAME through an explicit revision.

TEST AS USER must exercise the dedicated same-UID `openunlink` flow rather
than rely on the sysdiff-centered portfolio smoke. REVIEW must independently
judge the contract, implementation, tests, documentation, complete quality
evidence, and dedicated smoke, and must reject unresolved Medium-or-higher
mission findings. These phases authorize delivery of this bounded vertical
slice only; they do not authorize installation, packaging, tagging,
publication, or release.
