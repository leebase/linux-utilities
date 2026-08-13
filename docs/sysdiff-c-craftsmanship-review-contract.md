# Overview

This FRAME contract and delivery plan closes the remaining craftsmanship review
debt around the small C17 implementation in `src/sysdiff.c`. It treats the
source, its tests, the Makefile quality floor, the smoke manifests, and the
user-facing documentation as one auditable boundary. The repair is allowed to
correct a demonstrated ownership, lifetime, undefined-behavior, hostile-input,
portability, diagnostic, or maintainability defect, but it preserves the
existing `sysdiff` CLI, format-1 snapshot grammar, output bytes, and exit
statuses unless a concrete correctness or security finding proves that a change
is necessary. The current step authors only this contract; later implementation
and evidence steps must declare their own write scopes and retain the
repository-owned journey oracle outside those scopes.

The review scope is exactly `src/sysdiff.c`, `Makefile`, `tests/` (including
the sysdiff shell, pytest, malformed-input, benchmark, and fixture tests),
`tests/smoke_manifest.json`, and user-facing or maintainer documentation such
as `README.md`, `man/sysdiff.1`, `QUALITY.md`, `TESTING.md`, and the applicable
`docs/` contracts. This is debt closure before any new feature work: no new
sysdiff behavior is authorized by this document.

# Problem

The source is intentionally compact, but compact C still needs an explicit
review trail. `parse_snapshot` grows line and entry storage, transfers a fully
validated `Snapshot`, and cleans up partial state on malformed input, allocation
failure, I/O failure, duplicate keys, and resource-limit rejection. Those
transfers must be inspectable and exercised, not inferred from a passing happy
path. The deterministic hostile corpus in
`tests/test_sysdiff_malformed_fuzz.py` proves reject-closed behavior, yet its
direct subprocess runner does not currently honor `SYSDIFF_UNDER_VALGRIND=1`;
therefore the aggregate Valgrind gate is not by itself evidence for every
hostile parse/free path. The repair must close that evidence seam, examine
overflow and lifetime assumptions, and reconcile source, tests, Makefile,
README, `man/sysdiff.1`, `QUALITY.md`, and `TESTING.md` without turning a
focused test into a substitute for the complete quality floor. Governance is
part of the problem: the immutable journey manifest must remain the evaluator
oracle, malformed journey data must fail before command execution, and smoke,
user simulation, and review evidence must remain distinct.

# Constraints

- **Source ownership and lifetime:** `argv` and its strings are borrowed for
  process lifetime. `parse_snapshot` owns its opened `FILE`, line buffer, and
  partially appended key/value allocations until success or cleanup; success
  transfers the initialized `Snapshot` to its caller, while failure closes the
  file and frees every partial entry exactly once. `snapshot_free` owns the
  entry strings and array, is safe for initialized empty state, and is called
  for both snapshots on every comparison completion path. Any repair must make
  transfer points, cleanup labels, and post-transfer non-use obvious in the
  source.

- **Allocation and undefined behavior:** retain deterministic per-snapshot
  ceilings of 65,536 bytes per line, 65,536 entries, and 16 MiB of consumed
  bytes, including ignored records. Check additions, multiplications, capacity
  growth, and string terminators before allocation or indexing; never silently
  truncate or rely on memory pressure. Review pointer differences, `size_t`
  arithmetic, `qsort` comparison, `fgetc` classification, NUL termination,
  `errno` use, `fclose`, signal setup, and checked stdio for overflow,
  use-after-free, double-free, invalid reads, signedness mistakes, or other
  undefined behavior. A change is justified only by a reproduced defect or a
  testable safety proof, not by stylistic expansion.

- **Hostile input and diagnostics:** treat snapshot bytes, values, paths,
  command arguments, duplicate records, embedded NULs, invalid key bytes,
  missing separators, CR/LF variants, over-limit lines/entries/bytes, failed
  opens/reads/closes, and broken stdout pipes as untrusted. Reject malformed
  or operationally unsafe input with status 2 and empty compare stdout before
  diff emission; preserve status 1 only for a successful comparison with
  differences and status 0 for no changes or informational usage. Preserve
  printable-ASCII escaping for values and untrusted diagnostics, contextual
  line/path/limit messages, and the `SIGPIPE`/EPIPE status-2 behavior. Never
  invoke a shell, inspect `file.` keys as paths, or let hostile bytes forge
  terminal records.

- **CLI and format compatibility:** retain no-argument usage, `--help`,
  `--version`, and `compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`; retain bytewise,
  locale-independent key ordering; first-`=` parsing; opaque values after
  line-ending removal; comments/blanks; duplicate-key rejection; key syntax;
  exact added/removed/changed/no-change forms; delimiter shielding already
  covered by the fixtures; and the documented stdout/error-stream rules. Do
  not add live capture, directory recursion, package or service probing,
  persistence, SQLite, telemetry, background work, or a new snapshot format.

- **Closed craftsmanship hazard taxonomy:** the C review recognizes exactly
  six classes: `OWNERSHIP_LIFETIME` for borrowed/owned resource transfer and
  cleanup defects; `ARITHMETIC_UNDEFINED_BEHAVIOR` for bounds, overflow,
  signedness, invalid-access, and lifetime-adjacent C defects;
  `HOSTILE_INPUT_RESOURCE` for malformed bytes, limits, I/O, and reject-closed
  failures; `DIAGNOSTIC_OUTPUT` for escaping, stream, pipe, and status-report
  safety; `PORTABILITY_BUILD` for ISO C17, compiler, Linux/POSIX, or quality
  route assumptions; and `MAINTAINABILITY_SCOPE` for hidden ownership,
  duplicated invariants, contract drift, or unauthorized surface growth. A
  finding must use one of these classes. The existing workspace abstraction's
  governance hazard classes remain its separate pinned oracle taxonomy and are
  not silently renamed or expanded here.

- **Portability:** use ISO C17 and the existing narrow Linux/POSIX support
  posture. The intended build matrix is strict GCC and Clang with
  `-std=c17 -Wall -Wextra -Wpedantic -Werror`; `SIGPIPE` behavior and
  `/dev/full`/Valgrind assumptions must remain explicitly documented rather
  than generalized into an unsupported cross-platform promise. Honor the
  repository's `$CC` selection, `LC_ALL=C` fixture determinism, temporary
  build directories, and capability-gated skips. Missing required quality
  tools are not passing evidence; a skip must state the capability reason.

- **Maintainability and documentation:** keep the one-file implementation
  small, reviewable, and dependency-light. Prefer named helpers and a single
  visible cleanup strategy over clever ownership or duplicated error paths;
  comments must describe actual invariants. Any behavior, limit, diagnostic,
  portability qualification, or test-route change requires synchronized
  updates to `README.md`, `man/sysdiff.1`, `QUALITY.md`, or `TESTING.md` as
  applicable. Documentation-only claims must not be presented as executed
  evidence, and an independent review must be able to map each obligation to a
  source inspection, test, or recorded command.

- **Build and quality floor:** preserve the Makefile's strict GCC/Clang
  builds, `clang-format`, `clang-tidy`, `cppcheck`, Clang static analyzer,
  man-page lint, benchmark threshold check, ordinary tests, ASan with leak
  detection, UBSan with halt-on-error, and non-sanitized GCC Valgrind rebuild.
  The delivery sequence is inspect and baseline; make the smallest repair;
  add or strengthen focused hostile/lifetime evidence; run the focused checks;
  run deterministic smoke; run independent user simulation; run the complete
  suite and quality floor; then review changed paths and evidence. No green
  focused test can waive a failed, unavailable, or unexecuted required gate.

- **Governed evidence boundary:**
  `tests/user_journeys_manifest.json` is the repository-owned immutable
  evaluator oracle. Its verified pin is
  `0d21f5624b734e7b4ff58e02a42190bde9818cc2ae02e272ae964a72564bfbcc`; a hash,
  journey, authority, trace, or allowlist mismatch fails closed and never
  updates the pin. The exact manifest allowlist remains
  `command_allowlist: ["bash scripts/smoke.sh"]`. Resolve governed paths from
  the canonical workspace root, run claims with that root as `cwd`, parse
  shell words into argv, match complete tokens as an allowlisted argv prefix,
  and execute the matched argv directly. Reject malformed words, shell
  operators, prefix misses, wrong-cwd claims, and zero verifiable claims before
  execution or acceptance.

- **Non-goals and blast radius:** this contract does not authorize release,
  installation, packaging, tagging, publication, deployment, networking,
  telemetry, service work, or changes to unrelated utilities. It does not
  authorize edits to the journey manifest, smoke inputs, or evidence that
  would make a claim look green. The bounded repair may touch only separately
  allowlisted source/build/test/documentation surfaces needed to close a
  demonstrated craftsmanship defect; this current step writes only this
  contract file. A passing user simulation proves workflow evidence only and
  does not prove product release readiness or who ran a command.

# Acceptance Checks

- **AC-1 — Repository-owned journey oracle and source baseline.** The pinned
  manifest is present, parseable, named, and unchanged; its authority values,
  journey names, traces, and exact `bash scripts/smoke.sh` allowlist are
  recorded before repair. The implementation plan also records an inspection
  matrix for `src/sysdiff.c`, `Makefile`, all named sysdiff tests, smoke
  manifest, README, and manual. Craftsmanship mapping: source ownership,
  allocation lifetime, diagnostics, and maintainability begin as explicit
  review obligations rather than undocumented assumptions.

- **AC-2 — Fail-closed malformed journey and hostile-input data.** Invalid JSON,
  duplicate journey keys, wrong types, missing fields, invalid authorities,
  malformed traces, malformed command claims, shell operators, and empty
  verifiable claims fail with a specific validation result before execution.
  The C repair evidence separately proves malformed snapshots, NULs, invalid
  keys, duplicates, truncation, limits, I/O errors, and stdout failures reject
  safely with the preserved status and stream rules. Craftsmanship mapping:
  hostile-input handling, allocation cleanup, terminal-safe diagnostics, and
  undefined-behavior checks must cover both parser boundaries.

- **AC-3 — Unrelated-working-directory behavior.** A governed check launched
  from an unrelated current directory resolves the canonical workspace,
  manifest, contract, result, finding artifacts, and playbook paths without
  changing their meaning; lexical, absolute, parent-escaping, symlink-escaping,
  and wrong-cwd claims fail closed. The sysdiff tests and smoke route retain
  their root-derived paths and do not depend on an incidental `cwd`.
  Craftsmanship mapping: portability, path ownership, bounded temporary-file
  lifetime, and escaped path diagnostics are demonstrated from a hostile cwd.

- **AC-4 — Exact allowlisted smoke execution.** Only the complete argv prefix
  represented by `bash scripts/smoke.sh` may be re-executed for the journey
  claim; matching is token-by-token, direct, and shell-free, with the governed
  workspace as `cwd`. The unchanged smoke manifest chain remains the explicit
  start/helper/check/fixture route and no wrapper, replacement, extra command,
  or substring match is accepted. Craftsmanship mapping: build/smoke
  maintainability, command-argument ownership, no-shell behavior, and
  diagnostics for rejected claims are inspectable and testable.

- **AC-5 — Retained journey authority.** Every repository-owned journey stays
  present with the same intent and no weaker authority; only the closed
  authority set is accepted, and omitted authority keeps its documented
  default. Producer repair scopes exclude the manifest, and a source or test
  worker cannot remove, demote, narrow, or rewrite a required journey while
  claiming to repair C craftsmanship. Craftsmanship mapping: ownership means
  both heap ownership in the C source and authority ownership of the evaluator
  oracle; review must verify both without conflating them.

- **AC-6 — Complete acceptance traceability.** Every non-exploratory journey
  has a nonempty trace to a real AC-1 through AC-10 identifier, all ten IDs are
  covered, and exploratory journeys remain supplementary. The trace matrix
  maps source ownership/lifetime to AC-1/2/5, allocation and UB to AC-2/8,
  hostile input and diagnostics to AC-2/3/4, portability to AC-3/8/9,
  maintainability to AC-1/6/10, build/test obligations to AC-4/8/9,
  documentation to AC-1/6/10, and non-goals to AC-7/9/10. Craftsmanship
  inspection and repair therefore cannot disappear behind a single focused
  regression.

- **AC-7 — Pin-based tamper rejection.** A producer-side narrowing or mutation
  of the pinned journey manifest, an authority, trace, journey name, or
  allowlist is detected by SHA-256 and semantic checks and rejected before
  user evidence is accepted; the verifier never repairs the pin. Smoke helper
  and manifest changes are likewise treated as compatibility tampering.
  Craftsmanship mapping: the same immutable evidence rule protects source,
  test, build, and review claims from being weakened after a lifetime or UB
  finding is discovered.

- **AC-8 — Concrete user-test evidence.** The canonical result contains
  `journeys` and `findings`, reports every manifest journey with concrete
  `steps_taken` and direct `commands_run`, records actual integer exit codes
  and observed output only when observed, and supplies actionable finding
  fields for every failed journey. The evidence names the focused tests, C
  inspection, static tools, sanitizers, Valgrind hostile corpus coverage, and
  quality-floor commands actually run, including real skips and failures.
  Craftsmanship mapping: allocation/lifetime, UB, hostile input, diagnostics,
  portability, and maintainability claims require reproducible evidence, not
  prose or inferred success.

- **AC-9 — Separate deterministic smoke from user simulation.** The existing
  deterministic smoke route remains aggregate compatibility evidence from
  `tests/smoke_manifest.json` through its helpers and `scripts/smoke.sh` to
  `make test`; it is reported separately from direct journey attempts and
  cannot satisfy missing journey traces or prove personal user execution.
  The delivery records smoke, focused tests, full suite, sanitizers, Valgrind,
  benchmark, and independent simulation as distinct evidence types.
  Craftsmanship mapping: build/test/smoke obligations and the malformed-fuzz
  Valgrind gap are visible as separate claims, preventing a green smoke run
  from hiding an untested cleanup path.

- **AC-10 — Bounded no-release/no-network blast radius and completion.** The
  changed-path audit shows only declared craftsmanship surfaces and this
  contract; no network, telemetry, background service, live-system probe,
  install, package, tag, publication, deployment, release artifact, CLI
  expansion, snapshot-format change, or unrelated utility behavior appears.
  README, manual, QUALITY, and TESTING statements match the repaired behavior.
  Completion requires a green complete repository test suite and the complete
  `make quality` floor, plus the required smoke, journey, evidence, and
  independent-review checks; a new focused test alone is explicitly
  insufficient. Craftsmanship mapping: documentation, non-goals, portability,
  maintainability, build, and final source review all close together.
