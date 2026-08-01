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

**Decision:** Governed run `a8341dfae9f2` adds `permguard` as the suite's
third small C17 utility with an explicit-operand-only interface:
`permguard [--] PATH...`, plus informational `--help` and `--version`. The
scanner performs exactly one `lstat` per operand and never follows symlinks.
It classifies world-writable regular files, world-writable directories without
the sticky bit, and executable regular files carrying set-user-ID or
set-group-ID. Findings are retained until all operands have been inspected,
then emitted in operand order and fixed hazard rank with printable-ASCII
escaping. Exit status is 0 for a clean or informational run, 1 for completed
hazard findings, and 2 for usage, resource limit, allocation, inspection, or
stdout failure.

**Rationale:** The first slice needs to prove a useful permission-audit
contract without inheriting pathaudit's PATH traversal or expanding into a
general filesystem crawler. One metadata lookup per explicit operand keeps the
runtime and ownership model auditable. Validate-before-output sequencing
prevents a later inspection failure from leaving apparently complete partial
findings.

**Alternatives rejected:** Recursion (unbounded traversal and policy
questions); reading PATH (belongs to pathaudit); following or resolving
symlinks (would change the named-object contract); ACL/capability/owner policy
(outside the closed first-slice taxonomy); chmod/chown remediation (violates
the read-only mission); install, release, or dist membership (not authorized
for this bootstrap).

**Consequences:** `src/permguard.c`, `tests/test_permguard.py`, and
`man/permguard.1` join the strict compiler, formatting, static-analysis,
manual, pytest, sanitizer, and Valgrind surfaces through additive Makefile
wiring; dedicated build/memory recipes use temporary binaries. Existing
sysdiff install/release/dist membership remains unchanged. Independent review
`code-reviews/review-permguard-bootstrap.verdict.json` passed with Medium
PG-DOC-001 and PG-TEST-002 plus three Low findings. This record addresses the
architecture omission noted inside PG-DOC-001 only as a closeout edit; the
finding remains open until stale QUALITY.md/TESTING.md are repaired and the
combined change is independently reviewed.
