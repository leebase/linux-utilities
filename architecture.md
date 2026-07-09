# Architecture

## Current architecture

- Primary language: C.
- Build system: `make`.
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
  `SYSDIFF_MAX_SNAPSHOT_ENTRIES == 65536`.
- Inputs that exceed the line or entry limits are rejected. They are not
  truncated. `compare` returns exit status `2`, leaves stdout empty, and emits
  contextual stderr naming the limit and affected location.
- `parse_snapshot` owns snapshot resources until successful return. It uses
  typed line/append statuses and a centralized cleanup block for parse errors.
  The latest review found no memory-ownership defects in this structure.
- `Makefile` keeps strict C17 warning-as-error builds and exposes
  `sanitizer-test` for ASan/UBSan coverage when `clang` is present. The
  aggregate `make-quality` target performs a clean GCC rebuild before
  Valgrind.
- Current caveat: standalone `make valgrind-test` depends on `build/sysdiff`
  and does not force a non-sanitized rebuild. Running it immediately after
  `make sanitizer-test` can reuse an ASan-instrumented binary and make
  Valgrind abort. This is open review finding F003 in
  `code-reviews/review-sysdiff-c-source.verdict.json`.
- Current caveat: at the line limit boundary, CRLF-terminated lines effectively
  allow one fewer data byte than LF-terminated lines. This is open review
  finding F002.
- Current test gap: CRLF-vs-LF equivalence and both resource-limit error paths
  are not covered by tests. This is open review finding F001.

## Direction

- Keep parsing, comparison, and output formatting separable as `sysdiff` grows.
- Keep tests fixture-backed and runnable without special privileges.
- Do not add runtime dependencies without explicit justification.
- Keep routed worker availability checks advisory. They may report missing
  local harness executables before governed work depends on those routes, but
  they must not launch Agent-Orch, start model sessions, choose fallback routes,
  mutate playbooks, install packages, or expand `sysdiff` product behavior.
