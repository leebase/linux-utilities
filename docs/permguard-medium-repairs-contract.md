# `permguard` Medium Repairs Contract

## Overview

This contract defines a closed maintenance slice for the five still-applicable
Medium findings from the reviewed `permguard` bootstrap: PG-DOC-501,
PG-DOC-502, PG-TEST-503, PG-PORT-505, and PG-DOC-512. It does not replace or
revise the product behavior in `docs/permguard-bootstrap-contract.md`; that
file remains the sole live product contract. This slice corrects inaccurate or
ambiguous repository guidance, pins the already-documented stdout-failure
behavior, and obtains the POSIX `lstat` declaration from the platform header
under an explicit feature-test build flag. Completion requires fresh
independent review after implementation and passing the complete repository
suite, not merely the new focused tests.

The repair remains observational and deliberately small. `permguard` continues
to inspect each explicit operand with one `lstat`, reject final symbolic links,
stream findings for successful operands, continue after operand errors, and
reduce the result to statuses 0, 1, or 2. The work introduces no new command,
finding, traversal, policy, package, installation path, or release claim.

## Problem

PG-DOC-501 is a live design-record contradiction: `architecture.md` describes
file-type-conditioned predicates, a sticky-bit exemption, buffer-until-complete
emission, allocation/resource-limit failures, and stop-before-partial-output
semantics that the bootstrap neither specifies nor implements. PG-DOC-502 is
authority residue: `docs/permguard-first-vertical-slice-contract.md` still
looks live, while `plans/permguard-first-vertical-slice-plan.md` falsely says
the now-authoritative bootstrap documents were removed. PG-TEST-503 leaves
`STDOUT_WRITE` and ignored-`SIGPIPE` behavior unprotected even though the
source, live contract, manual, and changelog promise it. PG-PORT-505 is the
hand-written `lstat` declaration in `src/permguard.c`, which can bypass libc
large-file/time redirection and mismatch `struct stat` on affected 32-bit
builds. PG-DOC-512 leaves `QUALITY.md` and `TESTING.md` silent about the third
utility despite its integration into strict, functional, sanitizer, and
Valgrind gates.

The old behavior and its claims have an explicit blast radius:
`src/permguard.c`, `Makefile`, `tests/test_permguard.py`,
`tests/smoke_manifest.json`, `scripts/smoke.sh`, `README.md`,
`man/permguard.1`, `CHANGELOG.md`, and relevant documentation. Relevant
documentation includes `architecture.md`, `QUALITY.md`, `TESTING.md`,
`docs/permguard-bootstrap-contract.md`, `docs/permguard.md`,
`docs/permguard-first-vertical-slice-contract.md`,
`plans/permguard-bootstrap-implementation-plan.md`, and
`plans/permguard-first-vertical-slice-plan.md`. A path being in the blast
radius does not require a textual edit: the smoke manifest and smoke script,
for example, should remain unchanged unless verification proves their existing
transitive `make test` route is broken. Every listed surface must nevertheless
be reviewed for consistency, and any intentional no-change decision must be
recorded in verification or review evidence.

## CLI Surface

The public CLI is preserved byte-for-byte: `permguard [--] PATH...`, plus
sole-argument `--help` and `--version`. At least one path is required; `--`
ends option parsing and permits leading-dash operands. Help remains the exact
two-line text currently specified by the bootstrap contract, and version
remains `permguard 0.1.0\n`. Unknown options, missing operands, a bare `--`,
or extra arguments beside an informational option remain usage status 2 with
the existing deterministic diagnostics.

Finding and diagnostic rendering also remains unchanged. Paths are borrowed
opaque `argv` byte strings, never normalized or canonicalized. Printable ASCII
is emitted literally except quote and backslash; all other bytes are rendered
as uppercase `\xHH`, preventing hostile tabs, newlines, control bytes,
terminal escapes, DEL, and non-UTF-8 bytes from forging records. Operands keep
command-line order, duplicate operands remain duplicated, and there is no
cross-stream ordering promise when callers merge stdout and stderr. No new
flag, environment-controlled policy, stdin behavior, output format, or
diagnostic token is authorized.

## Closed Hazard Taxonomy

The taxonomy remains exactly four independent mode-bit predicates evaluated
against the one successful `lstat` result for each non-symbolic operand, in
this fixed emission rank: `GROUP_WRITABLE` for `S_IWGRP`,
`OTHER_WRITABLE` for `S_IWOTH`, `SET_USER_ID` for `S_ISUID`, and
`SET_GROUP_ID` for `S_ISGID`. The predicates apply to files, directories, and
other accepted non-symbolic object types without file-type heuristics. A
single operand may emit all four findings.

Owner writability, read and execute bits, sticky bit, UID, GID, filename,
extension, and effective access neither create nor suppress a finding. A
final symbolic link is not classified and remains an operational
`SYMBOLIC_LINK` rejection. No `WORLD_WRITABLE_FILE`, sticky-directory rule,
ownership policy, ACL, capability, extended-attribute, content, mount, or
package-provenance finding may be added. Documentation repairs must describe
this shipped taxonomy rather than preserve the superseded one-code draft or
the inaccurate architecture predicates.

## Exit Statuses

Status 0 remains a successful informational invocation or a completed scan in
which every operand was inspected, no final symlink or operational error
occurred, and no taxonomy predicate matched. Status 1 remains a completed
hazard-only scan with deterministic findings on stdout and empty stderr.
Status 2 remains a usage or operational result, including missing,
inaccessible, symbolic-link, other `lstat`, and checked stdout write or flush
failures. These three values exhaust normal returns.

After valid parsing, an operand error does not stop inspection. Findings for
successfully inspected hazardous operands continue to stream in operand and
taxonomy order, diagnostics continue in operand order on stderr, and any
operational error takes precedence over simultaneous hazards in the final
status 2. There is no allocation or product-defined input-limit failure in
the current no-heap implementation. `SIGPIPE` remains ignored so a closed
stdout pipe reaches checked stdio handling, returns 2 rather than signal
termination or shell status 141, and attempts exactly
`permguard: STDOUT_WRITE\n`; a failed output operation may leave bytes already
written to stdout.

## Constraints

`src/permguard.c` must stop hand-declaring `lstat`. The build and test
surfaces must instead pass `_POSIX_C_SOURCE=200809L` as a compiler command-line
definition before system headers are processed, allowing `<sys/stat.h>` to
provide the ABI-correct prototype and any libc redirection. The flag must be
part of a non-accidentally-droppable permguard compile contract across the
ordinary Make recipe, strict GCC/Clang, syntax, tidy, analyzer, sanitizer,
Valgrind, pytest-owned compilation, and documented direct-build commands.
Avoid broad changes to unrelated source files merely because another utility
uses a similar declaration; this slice closes PG-PORT-505 for `permguard`.

Ownership must stay explicit and trivial: `argv` and its path strings remain
borrowed for process lifetime and are never freed or modified; each
`struct stat` and fixed diagnostic buffer has automatic storage and never
escapes its scope; the program introduces no heap ownership. `errno` is
captured immediately after failed `lstat`. All stdout writes and the final
flush remain checked, while stderr reporting remains best-effort and cannot
create a fourth exit class. Fixtures must be created below isolated temporary
directories, chmod applied after creation, actual `lstat`-visible bits read
back before forming the oracle, and modes and contents checked unchanged
after scanning. Host-capability skips must state the unavailable capability
and never be counted as a pass.

Only files needed to close the five Medium findings may change. Existing
unrelated worktree edits belong to the user and must be preserved. Smoke must
continue through the governed manifest and `scripts/smoke.sh`; passing focused
pytest alone is insufficient evidence.

## Non-Goals

This maintenance slice does not address the six Low findings PG-CRAFT-506,
PG-TEST-507, PG-CLI-508, PG-MAKE-509, PG-MAKE-510, or PG-MAKE-511. It does
not refactor helper duplication, add allocation or input limits, reinterpret
empty strings, revise CLI option position rules, expand standalone memory
recipes, or perform generic documentation polish. Similar feature-macro
patterns in `src/pathaudit.c` are outside this permguard repair and must not be
changed under PG-PORT-505 without separately governed scope.

There is no recursion, child enumeration, ancestor walk, final-symlink
following, `PATH` lookup, command resolution, ownership trust policy,
remediation, chmod/chown behavior, privilege change, content inspection,
configuration, persistence, daemon, monitoring, networking, telemetry,
installation, packaging, publication, or release work. The contract does not
authorize new hazard codes or claim race-free authorization. It also does not
replace the bootstrap product contract: the superseded draft receives a
prominent non-authority marker, while historical content may remain for
provenance.

## Acceptance Checks

- **AC-01 — Closed finding scope and authority.** Repository checks identify
  exactly PG-DOC-501, PG-DOC-502, PG-TEST-503, PG-PORT-505, and PG-DOC-512 as
  this slice's repair scope. The bootstrap contract remains the sole live
  product authority; the one-code contract and plan begin with conspicuous
  superseded pointers and contain no false removal claim. This maintenance
  contract is the bounded repair acceptance surface; recovery work must not
  invent a replacement product contract or claim that failed run
  `ba6dc2fdd199` already passed.
- **AC-02 — Accurate architecture and maintainer guidance.** Mechanical and
  human review confirm that `architecture.md`, `QUALITY.md`, and `TESTING.md`
  describe the four independent predicates, streaming/continue-after-error
  model, permguard gate membership, pytest override contract, fixture oracle,
  sanitizer/Valgrind routes, and honest capability skips without inventing
  allocation or resource-limit behavior.
- **AC-03 — Header-owned POSIX prototype.** `src/permguard.c` contains no
  hand-written `lstat` declaration. Every governed permguard compilation,
  including pytest's temporary build and documented direct compilation,
  supplies `_POSIX_C_SOURCE=200809L`; strict GCC and Clang compile and link
  through the system declaration with warnings as errors. README and
  `docs/permguard.md` direct-build examples must show the same flag.
- **AC-04 — Deterministic stdout device failure.** A hazardous temporary
  operand with stdout redirected to usable `/dev/full` returns 2 and writes
  exactly `permguard: STDOUT_WRITE\n` to stderr. If the device is absent or
  unsuitable, the test reports an explicit skip rather than a pass.
- **AC-05 — Closed-pipe and SIGPIPE behavior.** A deterministic pipe fixture
  closes the read end before the child flushes. The child returns 2—not a
  negative signal result and not shell status 141—and stderr is exactly
  `permguard: STDOUT_WRITE\n`. The test must fail if SIGPIPE ignore or final
  flush checking is removed.
- **AC-06 — Preserved product behavior and hostile paths.** Existing focused
  tests continue to pin exact CLI bytes, four-code taxonomy and rank,
  symlink rejection, one-`lstat` inspection, duplicate and mixed-operand
  behavior, statuses 0/1/2, read-only fixtures, and escaping of hostile path
  bytes. No public output or diagnostic changes outside the two output-failure
  regressions.
- **AC-07 — Blast-radius consistency and smoke route.** Review covers
  `src/permguard.c`, `Makefile`, `tests/test_permguard.py`,
  `tests/smoke_manifest.json`, `scripts/smoke.sh`, `README.md`,
  `docs/permguard.md`, `man/permguard.1`, `CHANGELOG.md`, and all relevant
  docs named in Problem. User-facing README/man/CHANGELOG/`docs/permguard.md`
  text must describe the shipped explicit-path CLI, four-code taxonomy,
  statuses, and non-goals without a release claim. The governed smoke
  manifest still reaches `make test`; intentional unchanged surfaces are
  explicitly recorded.
- **AC-08 — Complete definition of done.** Focused permguard pytest, strict
  compilers, format/static analysis, man lint, sanitizer and Valgrind routes,
  the complete repository pytest/shell suite, existing governed smoke, and
  fresh independent review all pass. Passing the new tests or focused module
  alone is not completion; passing the complete suite is the definition of
  done.
