# Architecture

## Current architecture

- Primary language: C.
- Build system: `make`; the quality target surface includes `test`,
  `test-suite`, `check`, `sanitizer-test`, `valgrind-test`, `make-quality`, and
  `clean`.
- Default worker runtime: `codex_cli`.
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
- `parse_snapshot` owns snapshot resources until successful return. It uses
  typed line/append statuses and a centralized cleanup block for parse errors.
  The latest review found no memory-ownership defects in this structure.
- Diff values and untrusted path/command diagnostics render as printable ASCII;
  comparison remains byte-opaque. Stdout failures and closed pipes return `2`.
- `Makefile` keeps strict C17 warning-as-error builds. `make` builds, `test`
  runs functional coverage, and `check` delegates to `quality`. The full gate
  includes gating clang-tidy/cppcheck, ASan with leak detection, UBSan, and a
  clean GCC rebuild before Valgrind.
- `valgrind-test` always cleans and rebuilds a strict GCC binary, so it does
  not reuse sanitizer instrumentation. CRLF/LF line-limit equivalence and both
  resource-limit error paths are fixture-covered.

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
