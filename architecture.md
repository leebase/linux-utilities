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
