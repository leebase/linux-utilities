# Architecture

`sysdiff` is a single-file C17 command-line utility that compares two explicit
plain-text snapshot files and emits a deterministic, key-sorted map diff. The
executable is built from `src/sysdiff.c` into `build/sysdiff` by `make`. The
product surface is intentionally narrow: informational `--help` / `--version`
(and no-argument usage), plus `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`.
The compare path opens only those two paths, validates both snapshots fully
before any diff output, then walks sorted key/value maps. There is no live
system capture, directory scan, package or service probing, persistence,
networking, or background work in this architecture.

## Current architecture

- Primary language: C (ISO C17 via `-std=c17`).
- Build system: `make`; the quality target surface includes `test`,
  `test-suite`, `check`, `gcc-strict`, `clang-strict`, `clang-analyzer-check`,
  `benchmark-check`, `sanitizer-test`, `valgrind-test`, `make-quality`,
  `man-check`, and `clean`. The ordered aggregate contract is
  `docs/sysdiff-quality-floor-clean-checkout.md` (mirrors `make quality`).
- Default worker runtime for governed work: `codex_cli` (infrastructure only;
  not part of the `sysdiff` runtime).
- Smoke surface: `scripts/smoke.sh` runs `make test`.
- Smoke manifest surface: `tests/smoke_manifest.json` is the Agent-Orch
  manifest for user smoke. It points at `tests/smoke_start.py`,
  `scripts/smoke.sh`, `tests/test_sysdiff_fixture.sh`, and
  `tests/check_sysdiff_smoke.py`.
- First executable: `build/sysdiff` from `src/sysdiff.c`.
- Current `sysdiff` command surface: `sysdiff`, `sysdiff --help`,
  `sysdiff --version`, and
  `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`.
- Agent-Orch routed worker preflight: `scripts/check_tools.py` checks the
  default required harness executables for `codex_cli` and `claude_code` using
  read-only `PATH` discovery.

## Snapshot Format

- The initial `sysdiff` vertical slice is governed by
  `docs/sysdiff-snapshot-format-and-scope.md`; that document remains the
  implementation source of truth for the snapshot format, output contract, exit
  statuses, resource scope, non-goals, compatibility rules, security
  constraints, and acceptance checks.
- The architectural decision for format `1` is recorded in
  `docs/snapshot-format-decision.md`: use explicit deterministic plain-text
  snapshot files with one `key=value` resource record per line, treat values as
  opaque bytes after line-ending removal, validate both snapshots before
  producing output, compare records as key/value maps, and emit differences in
  bytewise key order. That decision record is a summary; exact key syntax and
  edge-case behavior still come from
  `docs/sysdiff-snapshot-format-and-scope.md`.
- The current release-oriented contract covers explicit `key=value` snapshot
  files only. Architecture and implementation work for this slice should be
  checked against that contract before relying on README summaries or local
  assumptions.

## Runtime pipeline

1. Command dispatch recognizes no-arg usage, `--help`, `--version`, and
   `compare` with exactly two path operands. Unknown commands and bad arity
   return status `2` with stderr diagnostics (paths/commands escaped).
2. At startup, `SIGPIPE` is ignored (POSIX, unconditional in `src/sysdiff.c`)
   so a closed stdout pipe surfaces as stdio `EPIPE` rather than process
   termination. Product support and CI remain Linux (Ubuntu) focused.
3. Each snapshot is opened with `fopen` mode `rb` (binary; no separate
   regular-file check), read line-by-line with total-byte accounting, stripped
   of LF or CRLF endings, filtered for blanks/comments, split on the first
   `=`, key-validated, and appended into a growable array. Byte-limit rejection
   precedes embedded-NUL when the overflowing byte is NUL.
4. Records are sorted with bytewise `strcmp` ordering (locale-independent);
   duplicate keys fail closed. Resource limits reject oversized lines, entry
   counts, or total bytes without truncation.
5. Only after both snapshots validate does the comparator emit `+` / `-` / `~`
   lines or `no changes`. Diff values and untrusted diagnostic text use
   printable-ASCII escaping; comparison remains raw and opaque.
6. Stdout write/flush failures return status `2` and may leave partial stdout;
   validation failures leave stdout empty.

## C Source Hardening

- The current hardening slice is governed by
  `docs/sysdiff-c-source-contract.md`.
- `src/sysdiff.c` defines deterministic compile-time limits:
  `SYSDIFF_MAX_LINE_BYTES == 65536` and
  `SYSDIFF_MAX_SNAPSHOT_ENTRIES == 65536`, plus a 16 MiB total-byte limit per
  snapshot including ignored input.
- Inputs that exceed line, entry, or total-byte limits are rejected. They are not
  truncated. `compare` returns exit status `2`, leaves stdout empty, and emits
  contextual stderr naming the limit and affected location.
- Ownership: `parse_snapshot` owns the open `FILE` and all heap entries until
  it returns success (then the caller owns the `Snapshot` until
  `snapshot_free`). On any parse error it uses a single `cleanup:` path to
  close the file and free partial state; `snapshot_free` is idempotent for
  initialized snapshots. The latest review found no memory-ownership defects
  in this structure.
- Diff values and untrusted path/command diagnostics render as printable ASCII;
  comparison remains byte-opaque. Stdout failures and closed pipes return `2`.
- `Makefile` keeps strict C17 warning-as-error builds. `make` builds, `test`
  runs functional coverage, and `check` delegates to `quality`. The full gate
  includes strict GCC and Clang links, clang-format, clang-tidy, cppcheck, the
  Clang static analyzer, man-check, shell/pytest coverage (including malformed
  fuzz and benchmark contracts), temp-dir benchmark validation, ASan with leak
  detection, UBSan, and a clean GCC rebuild before Valgrind.
- `valgrind-test` always cleans and rebuilds a strict GCC binary, so it does
  not reuse sanitizer instrumentation. Fixture entry-count and 16 MiB total-byte
  limit cases skip under `SYSDIFF_UNDER_VALGRIND=1` for runtime; CRLF/LF
  line-limit equivalence and both resource-limit error paths remain covered on
  normal and sanitizer paths.

## Craftsmanship Review State

- Agent-Orch run `c434e00a3772` completed the required C craftsmanship review
  before new feature selection. The verdict file is
  `code-reviews/craftsmanship-review.verdict.json`; it reports `pass` at the
  High/Critical threshold, with no High or Critical findings.
- No product architecture expansion was approved during the craftsmanship
  review. The explicit snapshot-only `sysdiff compare BEFORE_SNAPSHOT
  AFTER_SNAPSHOT` scope remains in force.
- Release preparation and the adversarial last-stop audit resolved the test,
  smoke, terminal-output, resource-bound, and quality-gate follow-ups:
  pytest uses `$CC` with `cc` fallback and the smoke start helper exits
  immediately. The remaining accepted Low limitation is presentation-only:
  changed values containing ` -> ` are not reversibly delimited in format-1
  output.

## Direction

- Keep parsing, comparison, and output formatting separable as `sysdiff` grows.
- Keep tests fixture-backed and runnable without special privileges.
- Do not add runtime dependencies without explicit justification.
- Keep routed worker availability checks advisory. They may report missing
  local harness executables before governed work depends on those routes, but
  they must not launch Agent-Orch, start model sessions, choose fallback routes,
  mutate playbooks, install packages, or expand `sysdiff` product behavior.

## 2026-07-25 — pathaudit `--path` executable shadowing

**Decision:** Opt-in `pathaudit --path` additionally scans each PATH
directory's top-level entries for regular `X_OK` executables. The first
PATH-order hit for a basename is the winner; every later distinct
`realpath` hit emits one `SHADOWED` line naming the command, winner
realpath, and shadowed realpath. Shared-taxonomy directory hazard lines
still precede all `SHADOWED` lines. Explicit-root mode never searches
executables and never emits `SHADOWED`. Empty, missing, non-directory,
and unreadable components are skipped for the scan; nested directories
are not recursed.

**Rationale:** Operators auditing `PATH` need to see when the same
basename is plantable or already present in multiple directories, not
only whether individual directories are writable. Reporting shadows as
an additive stdout class keeps the existing hazard taxonomy intact
while making winner-vs-later collisions auditable and deterministic.

**Alternatives rejected:** Folding shadows into `--command` only
(misses multi-basename PATH audits); inventing a new exclusive mode
(arity and docs cost); treating identical realpaths as shadows (would
false-positive on repeated PATH components); recursing into nested
directories (noisy and out of scope for PATH lookup).

**Consequences:** `--path` now has two coordinated stdout families
(directory hazards, then `SHADOWED`). Peak memory and lookup cost on
large real PATH scans remain open Medium/Low review findings
(pathaudit-shadow-1/2/3). This slice does not add an install target or
claim a `pathaudit` release.

## 2026-07-25 — pathaudit `--command` single-basename inspection

**Decision:** Exclusive opt-in `pathaudit --command NAME` walks the process
`PATH` once in resolution order for a single basename. It emits `MATCH`
lines (`realpath` of regular files with `X_OK`) in PATH order, then
applicable shared-taxonomy hazard lines with plant-risk-before-winner
applicability (`permission_applicable = has_match || !seen_match`). Empty
or `/`-containing names reject-close as `INVALID_COMMAND`; unset `PATH`
reject-closes as `PATH_UNSET`. Unrelated basenames in the same directories
are never enumerated.

**Rationale:** Operators often care whether a named command is plantable or
shadowed, not about every PATH directory in isolation. Scoping to one
basename keeps output auditable and avoids collision flooding while reusing
the existing PATH split, hazard taxonomy, and escape rules.

**Alternatives rejected:** Extending `--path` with optional name filtering
(mixed mode semantics and harder arity rules); enumerating all same-directory
basenames (noisy and out of scope); rewriting empty PATH fields to `.`
before lookup (would hide cwd-dependent plant risk already classified by
`--path`).

**Consequences:** `pathaudit` now has three exclusive modes (explicit roots,
`--path`, `--command`). Classification for `--command` currently near-
duplicates `--path` root classification with applicability gating
(Low pathaudit-cmd-1). This slice does not add an install target or claim a
`pathaudit` release.

## 2026-07-26 — pathaudit executable ownership trust (`UNSAFE_OWNER`)

**Decision:** Opt-in `pathaudit --path` and `pathaudit --command` apply a
narrow ownership-trust rule to each resolved regular executable target: emit
`UNSAFE_OWNER` naming the executable `realpath` when the final followed-target
`st_uid` is neither UID 0 nor the invoking real UID from `getuid()`. Root and
invoking-user ownership are trusted; every other final-target owner is unsafe.
Symlink candidates follow the final target for ownership metadata.
`UNSAFE_OWNER` ranks after `GROUP_WRITABLE` / `WORLD_WRITABLE` for the same
root and sorts with other shared-taxonomy findings ahead of `SHADOWED` under
`--path`. Explicit-root mode remains ownership-blind and never searches
executables. Directory ownership is not classified. Emitting `UNSAFE_OWNER`
exits status `1` with empty stderr on the successful hazard path.

**Rationale:** PATH audits that only inspect directory writability miss
planted or residual executables owned by another unprivileged UID. Trusting
only root and the invoking real user keeps the rule auditable and aligned with
how operators reason about “my PATH should not run someone else’s binary,”
without inventing a broad ownership policy for directories or explicit roots.

**Alternatives rejected:** Checking directory ownership (noisy and outside
PATH executable trust); trusting additional system UIDs by name (host-
dependent and hard to pin); applying ownership under explicit-root mode
(would invent executable search there); folding ownership into `SHADOWED`
(collapses distinct hazard classes).

**Consequences:** User-facing docs must name `UNSAFE_OWNER` exactly and must
not claim that pathaudit ignores ownership policy wholesale. Foreign-owner
fixtures may be host-limited. This decision does not add an install target or
claim a `pathaudit` release.

## 2026-07-28 — permguard explicit-path bootstrap

**Decision:** The shipped `permguard` bootstrap is a small ISO C17,
explicit-path-only scanner with the interface `permguard [--] PATH...` plus
sole-argument `--help` and `--version`. It performs exactly one `lstat` for
each operand. A successful non-symbolic inspection independently evaluates,
in fixed order, `GROUP_WRITABLE` (`S_IWGRP`), `OTHER_WRITABLE` (`S_IWOTH`),
`SET_USER_ID` (`S_ISUID`), and `SET_GROUP_ID` (`S_ISGID`), without
file-type or sticky-bit conditions. Findings stream on stdout in operand and
taxonomy order; processing continues after operand errors, while any
operational error or rejected final symbolic link makes the final status 2
and takes precedence over hazards. Status 0 is clean, status 1 is
hazard-only, and checked stdout write or flush failure is operational.
`argv` and its path strings are borrowed for the process lifetime and are
neither modified nor freed. Each `struct stat` and fixed diagnostic buffer
has automatic storage and does not escape its scope; the scanner owns no
heap allocation. `errno` is captured immediately after a failed `lstat`.
Stderr reporting is best-effort, and streamed stdout bytes cannot be recalled
if a later operand or output operation fails.

**Rationale:** Operators need a small, auditable preflight for named paths
whose group/other write bits or set-ID bits are hazards, without inventing
directory recursion, PATH search, or ownership policy. Streaming findings
per operand keeps partial results visible when a later operand fails, while
operational-error precedence preserves a single status-2 exit class.

**Alternatives rejected:** File-type-conditioned or sticky-bit predicates
(misstate the shipped four-code taxonomy); buffer-until-complete emission
with allocation/resource-limit exits (the no-heap bootstrap has neither);
following final symbolic links (hides the link itself and invents target
policy); treating a prior one-code world-writable-file draft as live
authority (superseded by the four-code bootstrap contract).

**Consequences:** User-facing docs and `architecture.md` must describe the
four independent predicates and streaming continue-after-error model exactly.
Gate membership, pytest overrides, and sanitizer/Valgrind routes are recorded
in QUALITY.md and TESTING.md. The bootstrap does not recurse, enumerate
directory children, walk ancestors, follow final symbolic links, read or
search `PATH`, resolve commands, apply ownership, ACL, capability, content,
or sticky-bit policy, remediate permissions, change privileges, persist
state, monitor, network, install, package, publish, or claim race-free
authorization or release readiness.

## 2026-07-30 — permguard POSIX `lstat` feature-test macro

**Decision:** Obtain the ABI-correct `lstat` prototype from `<sys/stat.h>`
under an explicit `_POSIX_C_SOURCE=200809L` feature-test macro supplied on
every governed permguard compile, syntax, analyzer, sanitizer, and Valgrind
route via the dedicated Make variable `PERMGUARD_POSIX_CFLAGS` (and pytest
`POSIX_C_SOURCE_FLAG`). Callers who replace `CFLAGS` cannot drop that flag;
command-line overrides of `PERMGUARD_POSIX_CFLAGS` itself remain possible and
are outside the intended CFLAGS-replacement protection. Do not hand-declare
`lstat` in `src/permguard.c`. Keep a guarded in-source `#ifndef
_POSIX_C_SOURCE` fallback so accidental flag omission still sees a declared
symbol; that fallback does not replace the Make/pytest flag contract.

**Rationale:** A hand-written prototype can bypass libc large-file/time
redirection and mismatch `struct stat` on affected builds. A dedicated
permguard Make variable prevents callers who replace `CFLAGS` from silently
dropping the feature-test flag.

**Alternatives rejected:** Keeping the hand-declared prototype; relying only
on overridable `CFLAGS` for the flag; editing `src/pathaudit.c` under this
permguard Medium-repair slice; treating the in-source fallback as sufficient
evidence that Make routes still pass the flag.

**Consequences:** Makefile and pytest oracles must require the literal flag or
a `PERMGUARD_*CFLAGS`/`PERMGUARD_*FLAGS` reference whose definition carries
`-D_POSIX_C_SOURCE=200809L`; `$(PERMGUARD_SRC)` alone must not satisfy those
oracles. `make cppcheck-check` continues to parse `$(ALL_SRCS)` without the
flag and relies on the guarded fallback. This decision does not change
runtime finding taxonomy, CLI bytes, or release posture.
