# Project Plan

## Current direction

- Keep the utility suite small and auditable.
- Build `sysdiff` first, starting with deterministic fixture comparison before
  any broad system probing.
- Use auto-orch for ongoing discovery and Agent-Orch for governed delivery
  slices with smoke and review-verdict gates.
- Prefer standard C and POSIX-adjacent shell test harnesses unless a stronger
  need is proven.

## Sixth Utility Mission

The exact committed sixth-utility title is **Bootstrap `openunlink` explicit-process zero-link regular-file descriptor reporting**.
Its one purpose is to inspect one explicitly supplied Linux PID and report each
open descriptor whose followed target is a regular file with `st_nlink == 0`;
procfs link text is escaped display context only, never the deletion predicate.
The mission does not scan all PIDs, open target content, group descriptors by
inode, estimate physical or reclaimable storage, signal or alter the process,
monitor, persist, use the network, install, package, publish, or release
anything.

The reviewed first vertical slice is planning-only: accept exactly
`openunlink --help`, `openunlink --version`, or `openunlink PID`; enumerate a
bounded set of canonical decimal entries from fixed `/proc/PID/fd`; inspect
them in numeric order with repeated directory-relative metadata; emit stable
zero-link regular-file findings as deterministic escaped `OPEN_UNLINKED`
stdout lines; preserve stable findings when per-descriptor advisories occur;
and use a closed finding, advisory, operational, and three-status model. A
future normative contract must settle the reviewed boundary questions before
code is accepted.

Governed discovery run `787b9bb3d830`
(`discover_and_evaluate_sixth_linux_utility`) produced
`plans/sixth-utility-mission-evaluation.md`. Independent artifacts
`plans/review-sixth-utility-mission.md` and
`plans/review-sixth-utility-mission.verdict.json` record `pass`, no Critical
or High findings, Medium `SIXTH2-M1`/`SIXTH2-M2`/`SIXTH2-M3`, and Low
`SIXTH2-L1`/`SIXTH2-L2`/`SIXTH2-L3`. The review allowlisted only Python
byte-compilation of the three existing pytest modules; the separate current
smoke is sysdiff-centered aggregate evidence (`351 passed, 18 skipped`), not
an `openunlink` build, test, sanitizer, Valgrind, smoke, ship, or release
claim.

Next executable action for this selected mission: keep implementation blocked
until the live repair-before-expansion gate is cleared by repair or explicit
reclassification plus independent review, then generate a separate governed
`openunlink` implementation playbook beginning with a normative contract that
resolves all three Medium findings before CODE. In particular, the contract
must settle partial evidence at the 65,536/65,537 descriptor boundary
(`SIXTH2-M1`), disclose filesystems whose unlink behavior retains nonzero link
count (`SIXTH2-M2`), and make status-1 finding-versus-advisory discrimination
normative (`SIXTH2-M3`), while retaining the three Low notes. This discovery
does not supersede the earlier planning-only `inodealias` and `shebangcheck`
missions or authorize implementation out of sequence.

## Mission Contract

The fifth-utility mission is `shebangcheck`: a read-only preflight utility for
one purpose—given explicit script paths, determine whether each first line is
in a deliberately small direct-absolute-interpreter shebang subset and whether
the named interpreter is present, a regular file, and executable at inspection
time. This contract supersedes planning-level behavioral details in
`plans/fifth-utility-mission-evaluation.md` where they conflict and supersedes
the deferral of CLI, output, taxonomy, limits, signals, and exit-status
decisions in `plans/fifth-utility-mission-contract.md`. This section is the
contract of record for a later implementation playbook: that playbook must
inherit it unless a separately approved contract revision changes it
explicitly. It does not rely on the evaluation's inconsistent score matrix.
Practical value is explicitly bounded: common argument-bearing forms such as
`#!/usr/bin/env python` are reported as unsupported, never treated as clean,
and a status-0 result means only that the admitted direct form passed these
checks. It is not a promise that a script will run, remain unchanged, or be
safe.

The implementation target is one small ISO C17 translation unit using libc and
narrow Linux/POSIX file, metadata, access, and signal interfaces. It inspects
only caller-named files, reads at most the capped first-line prefix, performs
metadata-only checks on the content-derived interpreter path, and neither
opens that path for execution nor launches a subprocess. The content-derived
lookup is therefore recognized as additional security exposure, bounded by
the header limit, absolute-path grammar, terminal-safe escaping, read-only
operations, and an explicit point-in-time claim. There is no recursion,
directory enumeration, PATH lookup, persistence, network access, privilege
helper, service, plugin system, shared parsing library, or framework.
System-call declarations must come from standard headers under
`_POSIX_C_SOURCE=200809L`; hand-declared prototypes are forbidden, and
`_FILE_OFFSET_BITS=64` is required for interfaces carrying `off_t`.

`shebangcheck` is distinct from `sysdiff`, which compares two caller-supplied
snapshot maps without interpreting script content; from `pathaudit`, which
analyzes directory and executable trust in PATH resolution rather than a
named script's interpreter declaration; and from `permguard`, which reports
mode-bit hazards on named filesystem objects without parsing their bytes.
It also avoids the planning-only `inodealias` mission's device/inode identity
grouping. One capped line, one closed grammar, one interpreter metadata
relation, and one result per operand keep the mission small, useful,
dependency-light, auditable, and maintainable.

## CLI Surface

The complete initial command surface is:

```
shebangcheck --help
shebangcheck --version
shebangcheck [--] SCRIPT...
```

`--help` and `--version` are informational only when they are the sole
argument. Otherwise option parsing accepts only an optional `--` followed by
one or more script operands. Unknown options, missing operands, and
informational options combined with other arguments produce `USAGE`. More
than 1,024 operands or an operand-byte sum greater than 1 MiB, excluding
terminating NULs, produces `RESOURCE_LIMIT`. An operand beginning with `-`
therefore requires `--`. Duplicate operands are inspected and reported
independently in their original argv order; no canonicalization or
deduplication occurs. Successful informational output is exactly
`shebangcheck 0.1.0\n` for `--version`; the eventual man page and changelog
must use the same identifier without implying that this planning slice is a
release.

For each operand, the implementation first calls `lstat`, classifies a final
symlink as `OPERAND_SYMLINK`, and classifies every non-regular type as
`OPERAND_NOT_REGULAR`; no non-regular operand is opened. It then opens the
regular object using `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`, maps an open
failure to `OPERAND_OPEN`, and uses `fstat` to require the same `st_dev` and
`st_ino` and a regular `st_mode` file type. Any mismatch is `OPERAND_RACE`.
An undetectable replace-and-restore race remains outside the guarantee.

`SHEBANGCHECK_MAX_HEADER_BYTES` is exactly 4,096 bytes before LF. LF may occupy
zero-based offset 4,096, so inspection reads at most 4,097 bytes. A line with
4,096 bytes followed by LF is within the ceiling; a line with 4,097 bytes
before LF is `HEADER_TOO_LONG`. EOF after at most 4,096 bytes and before LF is
`UNTERMINATED_HEADER` once `#!` has been recognized. No read call is issued
after a buffer containing the first LF has been processed, and no byte beyond
the capped 4,097-byte prefix is read.

The sole accepted header grammar is the byte sequence `#!` immediately
followed by one absolute interpreter path beginning `/`, followed immediately
by LF. `SHEBANGCHECK_MAX_INTERPRETER_BYTES` is 4,094, derived from the header
ceiling minus the two `#!` bytes; on Linux this also keeps the token below the
4,096-byte pathname-copy ceiling. The path token may contain printable ASCII
bytes `0x21` through `0x7e`, with no tab, CR, NUL, escape processing, or
additional token. Space or tab immediately after `#!` is unsupported leading
spacing, not a relative path. Space or tab after a nonempty token introduces
unsupported arguments. This explicitly classifies both
`#!/usr/bin/env python` and `#!/bin/sh -x` as `UNSUPPORTED_ARGUMENTS`.
A missing `#!`, relative interpreter, empty interpreter, forbidden byte, and
other grammar failures have the specific taxonomy results below. The path `/`
satisfies the grammar but classifies as `INTERPRETER_NOT_REGULAR`.

Successful inspection produces either no stdout for a clean operand or
exactly one finding line:

```
CODE script=ESCAPED_SCRIPT [interpreter=ESCAPED_INTERPRETER]
```

Fields are separated by one ASCII space and terminated by LF. Safe display
bytes are `0x21` through `0x7e` except backslash; backslash renders as `\\`,
and space plus every other byte renders as uppercase `\xNN`, matching the
suite convention. Findings retain argv order, with at most one finding per
operand. The optional interpreter field appears only for
`INTERPRETER_MISSING`, `INTERPRETER_UNRESOLVABLE`,
`INTERPRETER_NOT_REGULAR`, and `INTERPRETER_NOT_EXECUTABLE`; all other finding
lines end after the script field. All findings are buffered until every
operand has been inspected. If any operational error occurs, stdout remains
empty and stderr contains diagnostics of the exact form
`shebangcheck: CODE: operand=ESCAPED_SCRIPT\n` in argv order. A global
`USAGE`, `RESOURCE_LIMIT`, `MEMORY`, or `STDOUT_WRITE` diagnostic omits the
operand field when no single operand owns the failure. Only a stdout write or
final flush failure may leave partial stdout.

## Hazard Taxonomy

The initial taxonomy is closed: implementations and tests may not invent
additional finding or operational codes without first revising this contract.
Exactly one of the first applicable finding codes is selected for each
successfully read operand, in the order the conditions are listed:

1. `NO_SHEBANG`: the first two bytes are not exactly `#!`.
2. `HEADER_TOO_LONG`: more than 4,096 bytes occur before the first LF,
   including EOF after at least 4,097 non-LF bytes.
3. `UNTERMINATED_HEADER`: after recognized `#!`, EOF occurs without LF after
   at most 4,096 total header bytes.
4. `EMPTY_INTERPRETER`: `#!` is followed immediately by LF.
5. `UNSUPPORTED_SPACING`: one or more space or tab bytes occur immediately
   after `#!`; thus `#! /bin/sh`, `#!  /bin/sh`, and `#!\t/bin/sh` receive
   this truthful code rather than `RELATIVE_INTERPRETER`.
6. `RELATIVE_INTERPRETER`: the first byte after `#!` is a printable,
   non-whitespace ASCII byte other than `/`.
7. `UNSUPPORTED_ARGUMENTS`: after a nonempty interpreter token, space or tab
   introduces whitespace, arguments, or an env-launcher command; the utility
   does not parse or resolve them.
8. `MALFORMED_HEADER`: the header contains NUL, CR, a control byte other than
   space or tab, DEL, or a byte in `0x80` through `0xff`.
9. `INTERPRETER_MISSING`: `stat` of the admitted absolute path returns
   `ENOENT` or `ENOTDIR`.
10. `INTERPRETER_UNRESOLVABLE`: interpreter lookup returns `ENAMETOOLONG` or
    `ELOOP`, including an overlong component or symlink cycle attributable to
    the content-derived path.
11. `INTERPRETER_NOT_REGULAR`: the followed interpreter target exists but is
   not a regular file.
12. `INTERPRETER_NOT_EXECUTABLE`: the target fails `access(path, X_OK)` for
    the invoking process at inspection time.

These are status-1 findings, including hostile but fully classifiable header
bytes and ordinary unusable-interpreter states. Interpreter symlinks are
permitted because `stat` and `access` deliberately follow them; this is not an
ownership, symlink-trust, mount-policy, ACL, or future-execution guarantee.
`access` uses the invoking process's real UID and real GID. On Linux, real UID
0 passes `X_OK` when any execute bit is set; this is an explicit limitation of
the point-in-time result. Failure of `stat` outside
`ENOENT`/`ENOTDIR`/`ENAMETOOLONG`/`ELOOP`, or failure of `access` for a reason
other than permission denial, is operational rather than a finding.

The closed operational taxonomy is `USAGE`, `RESOURCE_LIMIT`,
`OPERAND_SYMLINK`, `OPERAND_NOT_REGULAR`, `OPERAND_OPEN`, `OPERAND_RACE`,
`OPERAND_READ`, `INTERPRETER_INSPECT`, `MEMORY`, and `STDOUT_WRITE`.
`USAGE` covers only command-grammar misuse, while `RESOURCE_LIMIT` covers the
1,025th operand and a byte sum exceeding 1 MiB. The remaining codes cover
blocking or redirecting operand types, the specified identity mismatch, OS
inspection failures not attributable to header bytes, allocation failure, and
output loss. Operational diagnostics name exactly one code and the escaped
operand when applicable. The utility makes no stronger TOCTOU claim: either
object can change after its point-in-time check.

## Exit Statuses

Exit statuses are deterministic and limited to three values. Status `0`
means `--help` or `--version` completed, or every operand matched the admitted
direct shebang grammar and its interpreter passed the narrow regular-file and
`X_OK` checks. Status `1` means all operands were inspected without an
operational failure and at least one closed finding was emitted. Status `2`
means usage, resource-limit, operand, allocation, interpreter-inspection, or
output failure.

Operational status `2` has precedence over findings regardless of operand
order. Before output begins, findings and operational diagnostics are retained
in bounded storage; if inspection finishes with any operational error, no
finding stdout is emitted, all collected operational diagnostics are written
to stderr in argv order, and the process returns `2`. Findings do not appear
on stderr. If writing or flushing stdout fails after a successful inspection,
the process reports `STDOUT_WRITE` on stderr when possible and returns `2`;
stdout may then contain a proper prefix of complete finding lines. The program
ignores `SIGPIPE` so a closed pipe follows this status-2 path instead of
terminating with a signal-dependent shell status. Failure to write the
best-effort stderr diagnostic does not change the numeric result.

## Explicit Non-Goals

The mission does not emulate the Linux kernel's complete script-loader
behavior. It excludes optional interpreter arguments, `/usr/bin/env` command
or `-S` resolution, PATH lookup, shell quoting, encoding detection, script
language validation, interpreter execution, script execution, and predictions
about later launch success. Unsupported forms remain visible status-1
findings; they are not silently accepted and are not a promise of eventual
support.

It also excludes recursive discovery, directory walking, stdin operands,
globbing, canonical-path output, interpreter ownership or writability policy,
ancestor trust, mount-option analysis, ACL or capability interpretation,
hashing, content comparison, inode grouping, remediation, chmod/chown,
monitoring, caching, persistence, telemetry, networking, daemons, plugins,
configuration files, structured output variants, localization, and runtime
dependencies beyond libc/POSIX. No source installation, package, archive,
tag, publication, or release claim belongs to the bootstrap. Shared-library
extraction and a generic filesystem-audit framework are prohibited unless a
future independently reviewed mission proves a need.

This repair defines the mission only. TEST and CODE implementation phases are
intentionally omitted from this slice: no C source, tests, fixtures, manuals,
Make recipes, smoke artifacts, or quality evidence are created or changed.
Implementation remains gated by the existing repair-before-expansion policy
and a separately governed playbook beginning with review of this contract of
record. Because this slice permits writes only to `project-plan.md`,
`ROADMAP.md`, `STATUS.md`, `architecture.md`, `DECISIONS.md`, the two planning
documents, and a conventional `docs/shebangcheck-contract.md` are knowingly
unreconciled; a later documentation-only slice must mirror the authority and
selection without changing this contract silently.

## Acceptance Checks

A later governed implementation is acceptable only when the following checks
are encoded as exact oracles rather than prose-only assertions:

- Unit checks cover option parsing; require `RESOURCE_LIMIT` for exactly 1,025
  operands and for an operand-byte sum of 1 MiB plus one; cover header
  precedence, every display byte, doubled-backslash and uppercase-hex
  escaping, grammar byte boundaries, result ordering, and exit reduction.
- Fixture checks cover a valid direct interpreter; missing, directory, and
  non-executable interpreters (all three execute bits clear); final script
  symlinks and special files, including a device node that must not be opened;
  all twelve finding codes; all applicable operational codes; LF after 4,095
  and 4,096 bytes as within the ceiling; LF after 4,097 bytes as
  `HEADER_TOO_LONG`; EOF without LF after 4,095 or 4,096 bytes as
  `UNTERMINATED_HEADER` and after 4,097 bytes as `HEADER_TOO_LONG`; NUL, CRLF,
  DEL, non-ASCII bytes, empty input as `NO_SHEBANG`, duplicate operands, and
  leading-dash paths via `--`. Each length-boundary header begins with `#!`.
  They also require `UNSUPPORTED_SPACING` for `#! /bin/sh`,
  `#!\t/bin/sh`, and `#!  /bin/sh`; `UNSUPPORTED_ARGUMENTS` for
  `#!/usr/bin/env name`, `#!/usr/bin/env -S name`, and `#!/bin/sh -x`; and
  `INTERPRETER_UNRESOLVABLE` for an over-`NAME_MAX` component and a symlink
  cycle, without suppressing other operands' findings.
- Integration checks use only temporary ordinary files and controlled mode
  bits, require no installed interpreter to run, and instrument `read` through
  a test-only link wrapper or syscall trace to prove that no read follows the
  buffer containing LF and that no byte beyond the 4,097-byte prefix is read.
  A fixture interpreter that would create a marker if invoked must leave no
  marker, and a symbol or syscall trace must show no fork/exec call. Checks
  exercise mixed clean/finding/error batches, verify status-2 precedence and
  empty pre-output stdout, and verify deterministic argv-order output under
  `LC_ALL=C`.
- Regression checks distinguish this utility from sysdiff map comparison,
  pathaudit PATH trust/shadow analysis, and permguard mode-bit reporting; they
  also pin the honest claim that clean means only the direct subset passed,
  never that an env-launcher or arbitrary script is launchable.
- Strict GCC and Clang C17 builds use
  `-Wall -Wextra -Wpedantic -Werror`; clang-format, clang-tidy, cppcheck, and
  the Clang static analyzer pass; ASan and UBSan cover the focused fixtures;
  Valgrind reports no leaks or invalid access; closed stdout and ignored
  `SIGPIPE` produce `STDOUT_WRITE` and status `2`.
- A dedicated user-smoke flow builds the standalone binary in a temporary
  location, checks one clean direct shebang, one unsupported env shebang, and
  one missing interpreter, validates exact escaped lines and statuses, and
  records `app_started`, `core_flow_completed`, exit codes, and empty blocking
  errors. Aggregate `make test` or the sysdiff smoke oracle is regression
  evidence only, never dedicated `shebangcheck` smoke.

Independent review must confirm the closed CLI, taxonomy, output grammar,
limits, exit precedence, read-only/no-execution behavior, bounded ownership,
and distinction from the other utilities, with no unresolved
Medium-or-higher mission finding. These checks map directly to unit,
integration, regression, fixture, sanitizer, Valgrind, and user-smoke work,
but none is executed or implemented during this mission-definition repair.
