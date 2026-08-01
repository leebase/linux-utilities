# `permguard` Hostile Filesystem Fixtures Contract and Delivery Plan

## Overview

This contract defines a focused fixture and regression slice for exercising
the existing `permguard` bootstrap against hostile, unusual, and changing
filesystem entries. It is subordinate to
`docs/permguard-bootstrap-contract.md`, which remains the sole live product
contract. This file does not replace that authority or create a second public
taxonomy. It defines test scenarios, deterministic oracles, isolation rules,
and the delivery sequence needed to prove that the shipped one-`lstat`
explicit-operand behavior survives real filesystem edge cases.

The slice covers exactly eight fixture-hazard classes: dangling symbolic
links, symbolic-link loops, unreadable entries, permission changes, unusual
filenames, deep paths, FIFOs or other special files, and replacement races.
The tests remain byte-oriented and compare complete stdout, stderr, and
numeric status. They exercise actual temporary directory entries wherever
the kernel interface can provide a deterministic oracle, and use a
test-binary-only metadata-call seam for the otherwise timing-dependent
replacement boundary. No fixture may require privilege escalation or touch a
pre-existing operator path.

Compatibility is a hard requirement. The operational CLI remains
`permguard [--] PATH...`; final symbolic links remain operational rejections;
successful non-symbolic entries remain classified only by their own
`S_IWGRP`, `S_IWOTH`, `S_ISUID`, and `S_ISGID` bits; findings continue to
stream in operand and taxonomy order; and normal returns remain limited to
statuses 0, 1, and 2. Completion requires the entire existing repository test
suite and quality floor to pass, not merely the new hostile-fixture tests.

## Problem

The current suite already has strong coverage for ordinary mode combinations,
final safe/hazardous/dangling links, missing and inaccessible paths, hostile
path escaping, mixed-success streaming, and checked stdout failures. It does
not yet organize hostile real-filesystem behavior as one closed fixture
contract, and several important boundaries remain missing or only incidentally
covered: a final link that participates in a loop versus an intermediate
component loop; metadata access to a mode-000 entry versus search denial in
its parent; observed results across explicit permission transitions; a
genuinely deep existing pathname; mode classification for a FIFO or socket;
and deterministic replacement immediately before or after the single
metadata observation.

Those gaps are easy to test incorrectly. Following a final link would turn a
dangling link or loop into target-resolution policy that `permguard` does not
have. Opening an unreadable file or FIFO would widen the scanner and can block.
Hard-coding one host's path limit or `errno` would make deep-path tests
non-portable. Sleeping while another process renames or chmods an entry would
make a scheduler lottery rather than a regression. Running permission-denial
tests as root can silently bypass the intended `EACCES`. Creating fixtures in
the repository or under shared system paths can mutate user data or leave
dangerous residue.

This delivery therefore needs explicit distinctions between public findings,
operational diagnostics, deterministic rootless fixture cases, capability
gates, and inherently concurrent observations. It must prove the current
point-in-time semantics without claiming that a single `lstat` locks a path,
detects every replacement, or authorizes later use. It must also preserve
every existing CLI byte, output record, diagnostic token, status rule,
ordering rule, source boundary, and non-release posture while extending
coverage.

## Authority and Compatibility

`docs/permguard-bootstrap-contract.md` remains the sole live authority for
product behavior. This hostile-fixture contract is an additive test and
delivery contract. If the two files appear to conflict, the bootstrap
contract governs and this file must be repaired before implementation
continues.

The following behavior is frozen for this slice:

- The CLI, help text, version text, usage diagnostics, and option parsing are
  byte-for-byte unchanged.
- Each valid operand causes exactly one `lstat` attempt. The final component
  is never followed, opened, canonicalized, or checked with `access`.
- The public finding taxonomy remains exactly `GROUP_WRITABLE`,
  `OTHER_WRITABLE`, `SET_USER_ID`, and `SET_GROUP_ID`, in that order, using
  the named object's successful `lstat` result without file-type heuristics.
- Final symbolic links report `SYMBOLIC_LINK`; non-empty `ENOENT` reports
  `MISSING`; `EACCES` reports `INACCESSIBLE`; other lookup failures report
  `INSPECTION_ERROR_N` with the captured decimal `errno`.
- Findings continue to stream for successful operands, inspection continues
  after operand errors, and any operational error takes precedence in the
  final status 2.
- Original operand bytes, operand order, duplicate behavior, escaping,
  checked stdout handling, best-effort stderr handling, and the absence of a
  heap/input-limit failure class remain unchanged.

No fixture-hazard identifier defined below may appear in product stdout or
stderr. They are test-plan labels only.

## CLI Surface

The operational surface remains exactly:

```text
permguard [--] PATH...
```

At least one path is required. Before `--`, a leading-dash argument is an
option; after `--`, every remaining argument is an operand. The only
informational invocations remain sole-argument `--help` and `--version`.
There is no `--hostile`, `--race`, `--follow`, `--recursive`, `--special`,
fixture-directory, retry, timeout, or test-seam option. Tests select fixtures
only by passing their ordinary pathnames as operands.

A separately compiled test binary may interpose the metadata call at link
time to establish a deterministic replacement boundary. That seam must not
add a production option, environment variable, exported API, source-build
default, or behavior to the ordinary `permguard` binary. The seam exists
only in a pytest-owned temporary build and must prove that it was invoked;
silently falling back to an uninterposed binary is a test failure.

## Exit Statuses

The existing status model is exhaustive and unchanged:

- Status `0` means a successful informational invocation, or every operand
  was inspected successfully, no operand was a final symbolic link, and no
  public mode-bit hazard matched.
- Status `1` means every operand was inspected successfully, no operand was a
  final symbolic link, and at least one of the four public hazards matched.
- Status `2` means usage failure or at least one operational failure,
  including missing, inaccessible, final-symbolic-link, other `lstat`, or
  checked stdout failure. Valid mixed invocations retain successful findings
  and return 2.

The hostile fixture classes do not introduce statuses. In particular, there
is no `RACE`, `DEEP_PATH`, `SPECIAL_FILE`, `PERMISSION_CHANGED`, or
`UNREADABLE` exit value. A replacement observed successfully is classified
from the one captured `struct stat`; a replacement that makes `lstat` fail is
reported through the existing diagnostic mapping. A FIFO is classified from
its own mode bits without being opened. A mode-000 final object is inspectable
when its parent path is searchable, while a child below a non-searchable
parent may produce the existing `INACCESSIBLE` status-2 result.

## Closed Fixture-Hazard Taxonomy

The fixture-hazard taxonomy is closed at exactly the following eight members.
These names organize tests and review evidence; they are not public finding or
diagnostic tokens.

1. `PGH_DANGLING_SYMBOLIC_LINK`: a final symbolic link whose target does not
   exist. `lstat` must classify the link itself, yielding exact
   `SYMBOLIC_LINK`, empty stdout, and status 2 rather than `MISSING`.
2. `PGH_SYMBOLIC_LINK_LOOP`: both a final component participating in a
   self-loop or two-link loop, and a loop in an intermediate component. A
   final link remains `SYMBOLIC_LINK` because its target is not followed. An
   intermediate loop makes `lstat` fail and therefore yields exact
   `INSPECTION_ERROR_<ELOOP decimal>`, empty stdout for a single operand, and
   status 2.
3. `PGH_UNREADABLE_ENTRY`: a mode-000 final regular file or directory in a
   searchable parent, plus a child below a non-searchable directory. The
   former is metadata-inspectable and is classified solely from its mode
   bits without opening content. The latter is `INACCESSIBLE` only when an
   unprivileged preflight actually obtains `EACCES`.
4. `PGH_PERMISSION_CHANGE`: one stable entry is scanned after explicit,
   verified transitions between clean, group-writable, other-writable, and
   clean modes. Each invocation observes only the mode present for its single
   `lstat`; `permguard` itself must leave every mode and file byte unchanged.
5. `PGH_UNUSUAL_FILENAME`: operands containing spaces, leading dash after
   `--`, quotes, backslashes, tab, newline, ESC, DEL, and supported non-UTF-8
   bytes. Output uses the existing quoted-byte escaping and remains exactly
   one printable ASCII record per finding or diagnostic.
6. `PGH_DEEP_PATH`: a real, existing multi-component pathname created below a
   short private temporary root, with its total size kept inside the host's
   measured representable limit, plus an over-limit lookup when the host can
   construct the argv. Existing deep entries classify normally. A failing
   deep lookup uses the numeric `errno` observed by a same-path preflight
   rather than a cross-host hard-coded error name.
7. `PGH_FIFO_OR_SPECIAL_FILE`: a FIFO is the mandatory special-file fixture;
   an AF_UNIX socket pathname is additive when supported. Neither is opened
   by the product. Each successful non-symbolic special entry is subject to
   the same four independent mode-bit predicates as a regular file or
   directory, and the scan must not block.
8. `PGH_REPLACEMENT_RACE`: replacement immediately before the metadata call,
   replacement immediately after a successful metadata call but before
   classification, and an optional unsynchronized atomic-replacement stress
   probe. The deterministic cases use a test-binary-only seam and pin which
   complete `struct stat` is classified. A real concurrent stress probe may
   produce only the closed set of old-object classification, new-object
   classification, or an existing operational diagnostic; its exact
   distribution is not a byte-repeatability claim.

Adding a ninth fixture-hazard class, changing one of these oracles, or turning
one of these labels into product output requires a separately approved
contract revision.

## Rootless Determinism

No required fixture invokes `sudo`, changes identity, calls `chown`, creates a
device node, mounts a filesystem, changes namespaces, or otherwise requires
root. On an ordinary Linux account, the following are mandatory,
deterministic cases: dangling final links; final self/two-link loops;
intermediate two-link loops; mode-000 final-entry metadata inspection;
sequential verified permission transitions; ASCII/control unusual names;
the within-limit existing deep path; FIFO classification; and both
test-seam-controlled replacement boundaries. Their complete status, stdout,
and stderr bytes must be asserted.

The inaccessible-child subcase is capability-gated because root and some
filesystems can bypass directory search restrictions. It passes only when a
preflight `lstat` fails with `EACCES`; otherwise it is an explicit skip with
the reason, never a pass. AF_UNIX socket pathnames, non-UTF-8 names, set-ID
preservation on special files, and a process-level over-limit path are also
capability-gated additions. The FIFO, ordinary unusual-name set, and
within-limit deep path remain mandatory even if those additions skip.

An unsynchronized replacement stress loop is not deterministic in which
object wins and is not required to produce identical counts across runs. If
included, its deterministic oracle is limited to safety and the closed set of
per-invocation outcomes. It cannot replace the two mandatory controlled-seam
tests.

## Temporary Fixture Isolation

Every fixture lives below a unique pytest temporary directory or a named
`/tmp/permguard-hostile-*` directory created with mode 0700. Deep-path tests
use a deliberately short `/tmp` root so the harness, not an unexpectedly long
workspace path, controls the available pathname budget. Tests pass absolute
paths except when a leading-dash basename specifically requires `cwd` plus
`--`.

Creation is followed by explicit `chmod` and `lstat` readback so umask and
filesystem behavior cannot silently define the oracle. Before each scan,
tests snapshot relevant entry type, mode, and regular-file content; after the
scan they verify that `permguard` changed none of them. Permission-denial
fixtures restore searchable owner permissions in `finally`. FIFO tests never
open either end. Socket fixtures close their owning socket before cleanup.
Race fixtures rename only entries within their private root and retain enough
private names to clean either completion state.

Child processes use the existing sealed locale-stable environment and capture
stdout and stderr separately. Temporary compilers, wrapper sources, test
binaries, coordination files, sockets, Valgrind logs, and deep trees remain
under the test's private temporary root and are removed by pytest cleanup or a
targeted trap. Cleanup must never use the workspace root, `$HOME`, an
unvalidated glob, or a pre-existing system directory as a recursive target.
Repository files, `/etc`, `/usr`, shared `/tmp` names, and operator-supplied
paths are never fixtures.

## Implementation Plan

1. Extend `tests/test_permguard.py` first. Reuse the existing escape,
   diagnostic, mode-readback, subprocess, sealed-environment, and Valgrind
   helpers. Add narrowly named helpers for private deep trees, FIFOs/sockets,
   loop construction, mode restoration, and deterministic replacement
   interposition. Every new behavioral test captures the complete numeric
   status and complete stdout/stderr bytes.
2. Add one group of tests for each of the eight taxonomy members. Keep final
   link loops separate from intermediate loops; keep mode-000 final metadata
   separate from `EACCES`; keep a mandatory FIFO separate from optional
   sockets; and keep controlled replacement boundaries separate from any
   scheduler-dependent stress.
3. Implement deterministic replacement coverage with a pytest-owned test
   binary whose `lstat` is interposed at link time, for example with a small
   wrapper object and the linker wrap facility. One mode replaces the entry
   before calling the real `lstat`; another calls the real `lstat`, replaces
   the entry, and then returns the already captured `struct stat`. The harness
   must verify one wrapped call and exact expected output. If that linker
   mechanism is unavailable, use an equivalently deterministic compile-time
   test seam; do not substitute sleeps or weaken the case to a skip.
4. Run the new tests against the current `src/permguard.c`. Change production
   source only if a test exposes a violation of the live bootstrap contract.
   Any repair must remain small, preserve exactly one `lstat` per operand and
   the no-open/no-follow surface, and add no runtime seam. If all tests pass,
   leave the production source byte-unchanged and record that this slice added
   missing evidence rather than new product behavior.
5. Change the Makefile only if required to keep the new focused and aggregate
   routes hermetic. Do not add a public binary, install target, package target,
   public fixture command, or privilege-dependent gate. Test-only compilation
   stays under pytest temporary storage and retains the existing
   `_POSIX_C_SOURCE=200809L` contract.
6. Reconcile the hostile-filesystem limitations and verified behavior in
   README, CHANGELOG, `docs/permguard.md`, and `man/permguard.1` without
   changing the public CLI or claiming a release. The bootstrap contract
   remains product authority; this file remains fixture-slice acceptance
   authority. User-facing docs must use the exact Markdown heading
   `Permguard Hostile Filesystem Fixtures` in README and CHANGELOG, keep at
   least eighty non-whitespace characters under each heading, and keep the
   section-1 manual explicit about hostile path escaping, symbolic-link
   rejection versus intermediate-loop inspection errors, permission
   point-in-time semantics, and FIFO/special-file classification without
   opening. Docs must not claim race-free authorization, device-node
   coverage, install wiring, packaging, or release.
7. Run focused tests, strict/static/manual checks, sanitizer and Valgrind
   routes, the complete repository suite, governed smoke, and independent
   review. Preserve exact pass/skip counts and capability reasons in evidence.

## Documented Behavior Summary

Maintainers and operators should treat the following as the documented
hostile-fixture posture once step 6 is complete:

- **Public surface unchanged.** CLI remains `permguard [--] PATH...`. Public
  findings remain exactly `GROUP_WRITABLE`, `OTHER_WRITABLE`, `SET_USER_ID`,
  and `SET_GROUP_ID`. Fixture-hazard labels `PGH_*` never appear in product
  stdout or stderr.
- **Diagnostics and exits.** Final symbolic links (dangling or looping) are
  `SYMBOLIC_LINK` with status 2. Intermediate loops map to
  `INSPECTION_ERROR_N` with the captured decimal `errno`. Missing paths are
  `MISSING`; unprivileged search denial is `INACCESSIBLE` when `EACCES` is
  observed. Successful scans still exit 0 (clean) or 1 (hazard-only); any
  operational failure yields status 2 with operational precedence.
- **Portability honesty.** Mode-000 final objects under searchable parents
  are metadata-inspectable without content I/O. The inaccessible-child case,
  AF_UNIX sockets, non-UTF-8 names, set-ID preservation on special files, and
  process-level over-limit deep paths may skip with an explicit capability
  reason. Deep-path expectations are host-measured, not a fixed `PATH_MAX`.
- **Special files and races.** FIFOs are mandatory and must not block;
  sockets are additive when supported. Classification uses own mode bits
  only. Replacement is point-in-time: the single captured `struct stat` wins.
  Docs and fixtures must not promise detection of an undetectable
  replace-and-restore race, a post-`lstat` lock, or later-use authorization.
- **Evidence location.** Behavioral pins live in `tests/test_permguard.py`.
  README, CHANGELOG, `docs/permguard.md`, and `man/permguard.1` summarize
  limitations for humans; this file remains fixture acceptance authority and
  does not supersede `docs/permguard-bootstrap-contract.md`.

## Constraints

The production implementation remains small ISO C17 with the current POSIX
`lstat` dependency and no new runtime dependency. Tests may use Python,
ordinary unprivileged filesystem operations, AF_UNIX where supported, and a
test-only compiler/linker seam. They must not use timing sleeps as the oracle,
read or write through a FIFO, rely on locale text from `strerror`, follow a
final symbolic link, or infer behavior from `Path.exists()` when `lstat`
semantics are what matter.

All expected permission bits come from post-creation `chmod` followed by
`os.lstat` verification. Deep-path expectations are derived from the actual
temporary root and host path limits; no fixed `/tmp` length or universal
`PATH_MAX` is assumed. Error tests capture the preflight `errno` immediately,
and capability-dependent cases report an explicit skip rather than silently
reducing coverage. Tests run under bounded timeouts so an accidental FIFO open,
loop follow, or deadlock fails instead of hanging the suite.

The slice is tests-first and compatibility-preserving. Existing dirty worktree
content belongs to its governing work and must not be overwritten. Generated
binaries, wrapper sources, caches, logs, sockets, coordination files, and
fixture trees stay outside governed outputs. The existing four-code finding
taxonomy, status precedence, streaming model, byte escaping, checked output,
one-`lstat` source surface, preview posture, and absence from install/package
targets are mandatory invariants.

Passing a focused `-k hostile` selection is feedback, not completion. The
definition of done includes the full existing test suite, existing shell
fixtures, all applicable static and dynamic gates, the canonical smoke route,
and independent review. A skip is never described as a pass, and an optional
stress run is never used to replace a deterministic acceptance check.

## Non-Goals

This slice does not add recursion, directory enumeration, ancestor walking,
final-link following, target content reads, FIFO I/O, canonicalization,
deduplication, retries, monitoring, watch mode, a daemon, persistent state,
networking, telemetry, ACL/capability/extended-attribute inspection,
ownership trust, effective-access simulation, mount policy, package
provenance, remediation, `chmod`/`chown` behavior in the product, or a
race-free authorization claim.

It does not add a public race finding, special-file finding, unreadable
finding, deep-path finding, or any fifth public hazard code. It does not
promise detection of an undetectable replace-and-restore race, stable output
counts during uncontrolled concurrent mutation, or a filesystem lock after
the metadata call. Character and block device fixtures are excluded because
creating them commonly needs elevated privilege; the mandatory FIFO and
optional unprivileged socket cover special-file classification.

The work does not install, package, tag, publish, or release `permguard`; add
Linux capabilities or setuid test helpers; modify unrelated utilities; close
unrelated review findings; or treat the existing sysdiff-centered smoke as a
dedicated hostile-`permguard` user flow. It also does not rewrite the
superseded one-code contract or revive its buffering, limits, or
`WORLD_WRITABLE_FILE` taxonomy.

## Acceptance Checks

- **AC-01 — Authority and compatibility.** Mechanical and human review
  confirm that `docs/permguard-bootstrap-contract.md` remains sole live
  product authority, this file is additive fixture authority, the public
  four-code taxonomy and exact CLI/status/output behavior are unchanged, and
  no `PGH_*` token occurs in product stdout or stderr.
- **AC-02 — Dangling links and loops.** Rootless real fixtures pin exact
  status 2 and `SYMBOLIC_LINK` for dangling, self-loop, and two-link-loop final
  operands. A two-link loop in an intermediate component pins status 2,
  empty stdout, and `INSPECTION_ERROR_<ELOOP decimal>`. Tests prove no target
  mode finding is invented.
- **AC-03 — Unreadable versus inaccessible.** A mode-000 final file and
  directory in a searchable parent are inspected without content I/O and
  classified from their own mode bits. The non-searchable-parent child case
  asserts exact `INACCESSIBLE` only after an unprivileged `EACCES` preflight,
  otherwise records an explicit capability skip and restores permissions.
- **AC-04 — Permission transitions are point-in-time.** One fixture is
  explicitly changed clean to group-writable to other-writable to clean, with
  mode readback before each invocation. Results are exact 0/1/1/0 with the
  corresponding complete finding bytes, and post-scan snapshots prove
  `permguard` performed no mutation.
- **AC-05 — Unusual filename safety.** Mandatory rootless cases cover spaces,
  leading dash, quote, backslash, tab, newline, ESC, and DEL; supported
  non-UTF-8 bytes are additional. Findings and diagnostics match the existing
  uppercase quoted-byte escaping, contain no raw control/non-ASCII bytes, and
  cannot forge records.
- **AC-06 — Deep paths.** A private existing path with at least 64
  components and at least 1,024 pathname bytes, while remaining below the
  measured host limit, is scanned successfully and reports the exact expected
  mode result. When a process-level over-limit operand can be passed, product
  status and numeric diagnostic match an immediate same-path `lstat`
  preflight; otherwise that addition skips explicitly.
- **AC-07 — FIFO and special-file behavior.** A chmod-verified FIFO runs
  without blocking and emits exactly the hazards present in its own mode in
  fixed rank. An AF_UNIX pathname receives the same check when supported.
  Source checks continue to prohibit opening operands and file-type
  suppression of the four predicates.
- **AC-08 — Replacement boundary.** Test-only interposition deterministically
  replaces an entry immediately before `lstat` and immediately after the real
  `lstat` returns. Each case proves one metadata call and exact classification
  of the intended complete snapshot. No production option, runtime hook, or
  new diagnostic is present. Optional concurrent stress accepts only the
  closed old/new/existing-error result set.
- **AC-09 — Isolation and cleanup.** All created paths are below private
  temporary roots; modes are verified after creation; blocked directories are
  restored; FIFO/socket/wrapper resources are closed; before/after snapshots
  show no product mutation; and no binary, cache, socket, log, or fixture
  residue appears in governed workspace outputs.
- **AC-10 — Rootless and capability honesty.** Mandatory cases listed in
  Rootless Determinism run without privilege escalation. Only the explicitly
  named host-dependent additions may skip, every skip states the missing
  capability, and review does not count skips or uncontrolled race outcome
  distributions as passes.
- **AC-11 — Narrow source surface.** Existing structural and behavioral
  checks still prove one `lstat` attempt per operand and no `stat`,
  `realpath`, `readlink`, `access`, operand open, recursion, mutation, or
  additional product taxonomy. Any production repair is traceable to a
  failing acceptance case and retains explicit ownership and captured-`errno`
  handling.
- **AC-12 — Complete definition of done.** Focused
  `tests/test_permguard.py`, strict GCC/Clang, formatting, clang-tidy,
  cppcheck, Clang analyzer, man lint, ASan, UBSan, Valgrind, existing shell
  fixtures, the complete repository pytest suite, canonical governed smoke,
  and fresh independent review all pass as applicable. Completion requires
  the entire existing test suite to pass, not merely the new tests or a
  hostile-fixture subset.
- **AC-13 — User-facing documentation.** README.md and CHANGELOG.md each
  contain a Markdown heading with the exact text
  `Permguard Hostile Filesystem Fixtures` and at least eighty non-whitespace
  characters under that heading. `man/permguard.1` explicitly discusses
  hostile path escaping, symbolic links (final versus intermediate),
  permission point-in-time semantics, and special files (FIFO/socket without
  open). `docs/permguard.md` and this contract summarize the same limits.
  None of those documents claim race-free authorization, device-node
  coverage, install wiring, packaging, or release.
