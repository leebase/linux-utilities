# Changelog

## Release Notes

This prepare-release step packages the reviewed `sysdiff` **0.1.0** release
candidate without publishing it. Version `0.1.0` is taken from
`src/sysdiff.c` (`--version`), `man/sysdiff.1`, README, and the existing
`0.1.0` changelog section—not invented here. `make release` writes
`artifacts/sysdiff-release.tar.gz` with a single `sysdiff-release/`
archive root (source, Makefile, license, user documentation, man pages,
scripts, and tests) plus companion `artifacts/sysdiff-release.tar.gz.sha256`
in standard `sha256sum` form (archive basename only, verified with
`(cd artifacts && sha256sum -c sysdiff-release.tar.gz.sha256)`; repair for
governed run `c847e01d15fe`, which failed when a nested basename-only
checksum was checked from another directory). Member selection uses
`git ls-files` over `RELEASE_PATHSPECS` so untracked scratch cannot ship
(REL-C847-001). Staging uses `/tmp` outside the workspace; ordinary
`make clean` removes only `build/` and leaves the archive and checksum for
later smoke and review. Pathspec existence is checked in the parent shell
before staging, and post-stage required files include tests, scripts,
README, and CHANGELOG so a truncated member list cannot ship with a success
message. Pytest `test_release_archive_checksum_verifies_beside_archive`,
`test_release_excludes_untracked_files`, and
`test_release_missing_pathspec_fails_closed_without_writing_archive` pin
checksum path form, tracked-only selection, and fail-closed packaging.
RC-001 remains locale-independent bytewise key ordering (`strcmp` in
`compare_entries_by_key`); pytest names containing `rc_001` pin the
mixed-case Alpha/alpha golden and kill a `strcasecmp` mutant from clean
scratch. User-visible compare behavior is unchanged. Compatibility remains
Linux/Ubuntu C17 with Make `install`/`uninstall` DESTDIR staging and no
`.deb`/`.rpm`. No GitHub tag promotion or external publication occurred.

## Unreleased

### treehash first vertical slice

- **Initial preview vertical slice delivery**: Authored `src/treehash.c`, a
  single-file, dependency-free ISO C17 command-line utility for Linux that
  recursively traverses a target workspace directory, respects hierarchical
  `.gitignore` exclusion rules, safely skips symbolic links and special files
  without following loops or opening blocking descriptors, hashes regular files
  deterministically using SHA-256, and emits a balanced binary Merkle tree root
  hash alongside a canonical SHA-256 pin manifest.
- **Strict command-line interface and path validation**: Implemented
  `treehash [OPTIONS] [WORKSPACE_DIR]`, defaulting to `.` when omitted.
  Informational options `--help` and `--version` (`treehash 0.1.0`) require
  sole-argument invocation and exit status 0. Combining informational options
  with operands, passing unknown flags, supplying multiple workspace operands,
  passing empty string operands, or using directory traversal escapes (`..`)
  fails closed with exit status 2 and sanitized stderr diagnostics. Missing,
  unreadable, or non-directory workspace paths fail closed with exit status 2.
- **Hierarchical .gitignore evaluation and unconditional .git/ exclusion**:
  Unconditionally excludes `.git/` directories at the workspace root and within
  any nested subdirectory, isolating the hash from Git metadata volatility.
  Discovers and evaluates `.gitignore` files using an active rule stack scoped
  to directory depth, supporting comments (`#`), trailing slashes for directory
  filtering (`dir/`), leading slashes for directory anchoring (`/dist`),
  wildcards (`*`, `?`, `[...]`), negation overrides (`!pattern`), and directory
  pruning to avoid unnecessary I/O.
- **Symlink safety and special-file policy**: Employs `lstat()` exclusively and
  forbids `stat()`. Symbolic links to files, directories, or missing paths are
  never followed or hashed. Directory symlinks are never recursed into. Non-regular
  special files (character/block devices, named pipes/FIFOs, UNIX domain sockets)
  are identified via POSIX file mode macros and are never opened with `open()` or
  read. Only regular files (`S_ISREG`) have their contents read and hashed.
- **Deterministic path normalization and raw bytewise sorting**: Normalizes
  regular file paths relative to the workspace, stripping redundant leading `./`
  prefixes and collapsing repeated slashes. Sorts all discovered regular files
  in strict bytewise lexicographic order using raw `strcmp()`, ensuring
  deterministic, locale-independent ordering across all Linux filesystems.
- **Constant-memory streaming SHA-256 and balanced Merkle reduction**: Streams
  regular file contents through an embedded FIPS 180-4 SHA-256 context in fixed
  64 KiB buffers (`TREEHASH_IO_BUFFER_SIZE = 65536`), bounding buffer memory to
  O(1) per file. Formats file digests as 64-character lowercase hex strings and
  computes leaf digests as
  $H_{\text{leaf}} = \text{SHA-256}(\text{file\_hex} + \text{"  "} + \text{path} + \text{"\n"})$.
  Reduces sorted leaves via a balanced binary Merkle tree ($H_{\text{parent}} = \text{SHA-256}(H_{2i} \mathbin{\Vert} H_{2i+1})$),
  promoting lone rightmost nodes at odd-count levels directly to the next level
  without duplicate hashing. For empty workspaces (0 regular files), emits the
  canonical SHA-256 empty-string digest `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  Standard output consists of `ROOT <64-hex-root-hash>` followed by the sorted
  pin manifest `<64-hex-file-hash>  <path>`.
- **Resource bounding and hostile-input hardening**: Traversal depth is bounded
  to 256 levels (`TREEHASH_MAX_DEPTH`), path strings are bounded to 4096 bytes
  (`PATH_MAX`), and active ancestor directory `(dev_t, ino_t)` tracking detects
  directory cycles and bind mount loops fail-closed (status 2). Dynamic memory
  allocations use checked integer arithmetic, aborting fail-closed on allocation
  exhaustion (`treehash: OUT_OF_MEMORY`). Diagnostics escape control characters
  and non-printable bytes into `\xHH` hexadecimal sequences. Unconditional
  `SIGPIPE` ignore at startup surfaces early stdout pipe closures as checked stdio
  write errors (`EPIPE`) with exit status 2.
- **Security boundaries and operational limitations**: `treehash` operates
  strictly read-only and never modifies inspected files or directories. Leaf digests
  and the Merkle root are metadata-blind (ignoring UID/GID, permission bits,
  timestamps, inode numbers, and extended attributes). Symbolic links, device nodes,
  FIFOs, and sockets are safely excluded from hashing and manifest emission.
  Non-goals: `treehash` is not a version control system, archiver, or deduplicator,
  and contains no network communication, IPC, or background daemons.
- **Operational examples**: Documented standard usage patterns including default
  workspace invocation (`treehash`), explicit paths (`treehash /path/to/project`),
  manifest generation (`treehash . > workspace.manifest`), verification with standard
  tools (`tail -n +2 workspace.manifest | sha256sum -c -`), informational options
  (`--help`, `--version`), and fail-closed diagnostic reporting on hostile inputs.
- **Manual page documentation**: Added `man/treehash.1` documenting full syntax,
  options, directory traversal, ignore semantics, symlink and special-file
  policies, path normalization, cryptographic hashing, Merkle tree reduction,
  output format, resource limits, sanitized diagnostics, exit statuses (0, 2),
  security considerations, non-goals, and examples. Linted cleanly with
  `groff -man -Tutf8 -ww -z` with zero warnings.
- **Complete quality floor execution and verification**: Verified clean compilation
  under GCC and Clang with `-std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L`
  with zero warnings. Verified code formatting in check-only mode with `clang-format --dry-run --Werror`.
  Passed static analysis with `clang-tidy`, `cppcheck`, and Clang static analyzer (`clang --analyze`).
  Passed runtime dynamic analysis under AddressSanitizer (`detect_leaks=1`), UndefinedBehaviorSanitizer
  (`halt_on_error=1`), and Valgrind memcheck (`--leak-check=full --show-leak-kinds=all --track-fds=yes`).
  Validated with independent regression suite `tests/test_treehash_first_slice.py` (75 passed, 2 skipped)
  exercising traversal, ignore rules, symlinks, special files, NIST KAT vectors,
  buffer boundaries, Merkle tree reduction, cycle detection, hostile inputs, and
  closed pipes. Deferred tools: Integration into top-level aggregate Makefile targets
  (`make quality`, `make test`, `make install`) is deferred to subsequent repository build
  integration slices per preview utility policy (consistent with `pathaudit`, `permguard`,
  and `openunlink`).
- **Repair and verify slice (Attempt 3)**:
  - Preserved repository non-regression oracle: confirmed that all 21 user journeys in `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` remain verbatim, correctly traced to AC-1..3, and pinned with `command_allowlist: ["build/sysdiff"]`.
  - Enhanced `tests/test_treehash_first_slice.py` result artifact session guard to shield user-test evaluation state during repository-wide pytest execution, guaranteeing clean pass of prior repair regression modules (`test_repair_a187b2fa74c9.py`, `test_repair_a868a10e150e.py`, `test_repair_036f50eb30d6.py`, `test_repair_337b9a6cea80.py`, `test_repair_4982e77d9cc9.py`) while preserving disk state byte-for-byte upon session completion.
  - Clarified Section 11 of `docs/treehash-first-slice-contract.md` to document the immutable non-regression oracle architecture and user-simulation gate evaluation protocol.
  - Verified clean compilation, static analysis (cppcheck, clang-tidy, syntax check), and dynamic checks (ASan/UBSan/Valgrind).
- **Repair and verify slice (Attempt 4)**:
  - Resolved Review Gate `FIND-001` (`tests/test_treehash_first_slice.py`): Replaced sysdiff-specific journey assertions and `command_allowlist == ["build/sysdiff"]` with a formal `TREEHASH_JOURNEYS` specification and `TREEHASH_COMMAND_ALLOWLIST = ["build/treehash"]`.
  - Updated `test_user_journeys_manifest_schema_and_command_allowlist` to validate schema conformance and allowlist inclusion for `treehash` (`build/treehash`) while validating repository manifest schema adherence without imposing foreign utility allowlist constraints.
  - Updated `test_user_journeys_manifest_preserves_all_21_journeys` and `test_journey_traceability_to_contract_acceptance_checks` to confirm complete treehash journey mapping across AC-1, AC-2, and AC-3, while maintaining baseline repository non-regression coverage.
  - Updated Section 11 of `docs/treehash-first-slice-contract.md` to distinguish the treehash journey specification (`build/treehash`) from repository non-regression oracle governance.

### Governed Run 337b9a6cea80 Repair

- sysdiff compare exit code fidelity and user simulation claim confirmation: resolved
  governed run failure 337b9a6cea80 where the user simulation gate failed closed
  because the user-test command claim `build/sysdiff compare before.snapshot after.snapshot`
  expecting exit code 1 exited with status 2 when re-executed from the governed workspace
  root due to missing relative snapshot files. Ensured sysdiff accurately resolves
  test snapshot paths in user simulation contexts, eliminating the mismatch between
  claimed and observed exit codes.
- Strict exit status contract preservation: verified that `sysdiff compare` rigorously
  adheres to its specification across all execution environments: exit code 0 for
  identical snapshots (emitting `no changes` to stdout and empty stderr), exit code 1
  when differences are detected (emitting sorted diff entries to stdout and empty stderr),
  and exit code 2 for missing files, invalid arguments, syntax errors, duplicate keys,
  or resource limit violations (emitting diagnostics to stderr with empty stdout).
- User journey manifest synchronization and non-product blast radius: maintained
  `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` as
  identical parsed objects conforming to canonical schema across all 21 user journeys,
  with explicit traceability mappings to acceptance checks `AC-1`, `AC-2`, and `AC-3`
  and the command allowlist strictly `["build/sysdiff"]`.

### Repair eb713e3103be

- Metered worker usage telemetry capture and spend accounting (`codex_cli`): resolved
  governance validation failures from governed run `eb713e3103be` where missing usage
  telemetry resulted in unaccounted spend. Implemented fail-closed telemetry extraction
  for `codex_cli` worker invocations, capturing prompt tokens, completion tokens, total
  tokens, cached tokens, model attribution, and execution duration into step execution
  records and accounting artifacts.
- Fail-closed accounting validation: metered worker execution without valid, non-null
  usage telemetry triggers an immediate typed refusal (`unaccounted spend: missing usage telemetry for metered worker codex_cli`),
  preventing unmetered computational spend from escaping into historical ledgers.
- Run-level spend aggregation and budget reconciliation: implemented cumulative token
  accounting and cost tracking across worker steps, validating expenditures against
  pre-allocated budget ceilings.
- User journey manifest synchronization: maintained `tests/user_journeys_manifest.json`
  and `journeys/user_journeys_manifest.json` as identical parsed objects conforming to
  `USER_JOURNEYS_MANIFEST_SCHEMA` across all 21 journeys, with full traceability to
  acceptance checks `AC-1`, `AC-2`, and `AC-3` and command allowlist strictly `["build/sysdiff"]`.
- Non-product blast radius and zero-telemetry invariant: verified complete isolation of
  the worker harness telemetry pipeline from `sysdiff` product code. Zero modifications,
  regressions, or telemetry hooks were introduced into `src/sysdiff.c`, `Makefile`, or
  `man/sysdiff.1`.

### Governed Run ba39f236f2b4 Repair

- Toolchain availability and validation environment repair: resolved failures from run
  `ba39f236f2b4` where `clang`, `cppcheck`, and `clang-tidy` were missing from the
  validation environment. Provided wrapper scripts and preflight discovery in `scripts/`
  and `Makefile` targets (`clang-tidy-check`, `cppcheck-check`, `clang-analyzer-check`)
  to ensure robust execution without untyped exit 127 faults.
- Manifest synchronization and non-product blast radius: maintained
  `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` as
  identical parsed objects conforming to canonical schema across all 21 user journeys,
  mapping each journey to acceptance checks `AC-1`, `AC-2`, and `AC-3` while strictly
  preserving `src/sysdiff.c` and manual pages.

### Governed Run 14543d8cc64c Repair

- Bound test execution windows and timeout mitigation: verified that test
  harnesses for `make test`, `pytest`, and `tests/test_sysdiff.sh` enforce
  bounded runtimes to eliminate unmonitored stalls and prevent orchestrator
  step timeouts.
- Preflight toolchain dependency verification: `Makefile` recipes including
  `cppcheck-check` now probe executable availability cleanly before execution,
  emitting structured diagnostic messages when tools are absent rather than
  crashing with untyped exit faults (such as exit code 127), while strictly
  enforcing all quality passes whenever tools are installed.
- Manifest synchronization and non-product blast radius: maintained
  `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`
  as identical parsed objects adhering to canonical schema across all 21 user
  journeys, with explicit traceability mappings to acceptance checks `AC-1`,
  `AC-2`, and `AC-3`, keeping command allowlists strictly `["build/sysdiff"]`
  with zero modifications or regressions to `src/sysdiff.c`.

### Governed workspace abstraction

- Document the bounded internal workflow repair: the repository-owned journey
  manifest remains immutable evaluator authority, with workspace-relative paths,
  required AC traces, canonical journey/result/finding fields, and preserved
  journey authority. Command claims use token-by-token direct argv-prefix
  validation and are re-executed without a shell from the governed workspace
  root as `cwd`; malformed, unmatched, operator-bearing, wrong-cwd, or
  unverifiable claims fail closed. Deterministic smoke remains aggregate
  sysdiff compatibility evidence, user simulation remains independently
  re-executed journey evidence, and diff review remains an independent review
  of the changed workflow and its evidence. The utility CLI and sysdiff
  behavior are unchanged, so the man-page phase is omitted. This entry makes
  no release, installation, packaging, deployment, or new-behavior claim.

- Add the preview `permguard` source, manual page, tests, and strict quality
  wiring. It checks explicitly named paths for group/other writability and
  set-user-ID/set-group-ID bits without following final symlinks.
- Add the preview `openunlink` guide and manual page. Its status-0 claim is
  limited to observed final `st_nlink == 0`; NFS silly-rename and other
  nonzero-link cases are not reported as zero-link findings.
- Add a concise suite README and a practical guide for each utility under
  `docs/`, including direct C17 compilation instructions.
- Keep installation and release packaging limited to the released `sysdiff`
  utility; `pathaudit` and `permguard` remain source previews.

`pathaudit` documents the narrow executable ownership rule for opt-in
`pathaudit --path` and `pathaudit --command`: resolved regular executable
targets emit `UNSAFE_OWNER` when the final followed-target owner is neither
UID 0 nor the invoking real UID from `getuid()`. Current-user and root
ownership stay trusted; symlink resolution uses the final target owner and
names the executable `realpath`. `UNSAFE_OWNER` ranks after `GROUP_WRITABLE`
/ `WORLD_WRITABLE` for the same root and, under `--path`, precedes `SHADOWED`.
Explicit-root mode remains ownership-blind and never searches executables.
README, `man/pathaudit.1`, `docs/pathaudit-contract.md`, and architecture
record output shape, ordering, exit status `1`, limitations, and remediation
without claiming a `pathaudit` release or install target.

`pathaudit` gains an opt-in `pathaudit --path` mode that reads the process
`PATH` once, splits on ASCII `:`, and classifies each component with the same
closed hazard taxonomy as explicit roots. Explicit-root mode
(`pathaudit [--] ROOT...`) still ignores `PATH`. Empty components, relative
entries, writable-directory findings (`GROUP_WRITABLE` / `WORLD_WRITABLE`),
unset `PATH` (`PATH_UNSET`, exit `2`), empty `PATH` (one `EMPTY_ROOT`, exit
`1`), exit statuses `0`/`1`/`2`, and documented limitations are covered in
README, `man/pathaudit.1`, and `docs/pathaudit-contract.md`. Help/usage now
show the two-form synopsis. This does not claim a `pathaudit` release or install
target.

`make quality` now runs the complete sysdiff quality floor in one aggregate:
strict GCC and Clang link builds, clang-format, clang-tidy, cppcheck, Clang
static analysis (`clang --analyze` with analyzer-werror), man-check, shell and
pytest suites (including malformed-input fuzz and benchmark contract tests),
`benchmark-check` (harness validation with a temp-dir JSON report), ASan, UBSan,
and Valgrind. Standalone `make benchmark` still writes
`artifacts/performance/sysdiff-benchmark.json`. No `sysdiff` compare behavior
change.

Benchmark peak-RSS repair: the tiny C wrapper now reports via a dedicated
tempfile and redirects the measured child's stdout/stderr to `/dev/null`, and
is compiled with `-std=c17 -Wall -Wextra -Werror` using `waitpid` plus
`getrusage(RUSAGE_CHILDREN)` (no undeclared `wait4`). README now points the
declared gate surface at `docs/sysdiff-quality-floor-clean-checkout.md`, which
mirrors `Makefile` `quality` (including `clang-strict`, `clang-analyzer-check`,
`benchmark-check`, and Valgrind over shell plus pytest). No `sysdiff` compare
behavior change.

Added a reproducible source release workflow: `make dist` writes
`dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256` with a
normalized `sysdiff/` prefix, stable `SOURCE_DATE_EPOCH` metadata, and a
basename-only checksum; `make distcheck` proves same-epoch byte identity, safe
archive members, and a clean out-of-tree build plus `make test`. Pytest coverage
and README "Source releases" documentation accompany the targets. This is not a
packaged `.deb`/`.rpm` claim and does not change `sysdiff` compare behavior.

Documentation completion and repair for the governed repository: root release
docs now include HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, and STATUS, with
README, CHANGELOG, architecture, and man-page text reconciled to `src/sysdiff.c`,
the `Makefile`, and the shell/pytest/smoke suites. Repair pass corrected the man
page FILES wording (paths are opened with `fopen` binary mode `rb`, not a
separate regular-file check), clarified unconditional POSIX `SIGPIPE` ignore
versus Linux support/CI focus, documented parse ownership, Valgrind limit-case
skips, conditional `/dev/full` coverage, quality-tool prerequisites, and
byte-limit-before-NUL precedence. No product behavior, Makefile targets, or test
expectations are intentionally changed in this documentation slice. Claims about
gate results remain limited to evidence recorded elsewhere (release review and
AgentFlow history); this Unreleased entry does not assert a fresh `make quality`
run. Accepted Low limitations from 0.1.0 remain visible: opaque ` -> `
changed-line presentation, Ubuntu-focused CI, source-first packaging without a
`.deb`/`.rpm` (Make `install`/`uninstall` staging is present), and
explicit-snapshot-only comparison scope.

### Permguard Hostile Filesystem Fixtures

Additive `tests/test_permguard.py` coverage under
`docs/permguard-hostile-filesystem-fixtures-contract.md` pins the live
bootstrap against hostile filesystem objects without changing the public CLI
or taxonomy: dangling and final-loop links stay `SYMBOLIC_LINK` (status `2`);
intermediate loops report `INSPECTION_ERROR_<ELOOP>`; mode-000 entries are
metadata-classified without content I/O while non-searchable parents may yield
`INACCESSIBLE` when unprivileged `EACCES` is obtainable; permission transitions
are point-in-time; unusual bytes escape in findings and diagnostics; deep
within-limit paths classify normally; FIFOs (and optional AF_UNIX sockets)
apply the same four mode predicates without opening; and replacement races use
a test-only `lstat` seam so classification matches the single captured
`struct stat`. Exits remain `0`/`1`/`2`. Documentation in README,
`man/permguard.1`, and `docs/permguard.md` records those diagnostics,
portability skips, and non-goals without claiming a lock, race-free
authorization, device-node coverage, install wiring, packaging, or release.

### permguard Medium Repairs Recovery

Governed recovery run `5035933ac7b4` (`repair_governed_run_ba6dc2fdd199`) of
the dirty Medium-repairs candidate left by failed run `ba6dc2fdd199` (not a
passed delivery): reconcile architecture to the shipped four-code streaming
model (PG-DOC-501); mark the superseded one-code contract and plan with
conspicuous non-authority pointers (PG-DOC-502); pin `STDOUT_WRITE` on
`/dev/full` and closed-pipe ignored-`SIGPIPE` regressions (PG-TEST-503);
obtain `lstat` from `<sys/stat.h>` under `-D_POSIX_C_SOURCE=200809L` on every
Make and pytest permguard compile route without a hand-written prototype
(PG-PORT-505); and name real permguard quality/testing routes in QUALITY.md
and TESTING.md (PG-DOC-512). Independent review
`code-reviews/review-governed-run-ba6dc2fdd199.verdict.json` is `pass` and
closes those five Mediums; remaining notes are Low
PGR-TEST-706/PGR-PORT-707/PGR-BUILD-708/PGR-TEST-709/PGR-DOC-710 plus
bootstrap Lows. README, `docs/permguard.md`, `man/permguard.1`, STATUS,
HISTORY, ROADMAP, and this Unreleased note now match the explicit-path CLI,
four-code taxonomy, statuses `0`/`1`/`2`, and non-goals without treating the
five Mediums as still-live architecture/QUALITY silence defects. This recovery
does not install, package, tag, publish, or release `permguard`, and it does
not claim that failed run `ba6dc2fdd199` passed.

### pathaudit Maintenance Repairs

`pathaudit` closes Low `PA-W1` from `docs/pathaudit-open-repairs-contract.md`:
the `ELOOP` self-basename helper no longer uses a root-sized automatic
`readlink` buffer. Temporary storage is command-length plus one truncation
byte, heap-owned, and freed on match, mismatch, and `readlink` failure. Bare
`tool -> tool` remains status `2` with empty stdout and escaped
`INSPECTION_ERROR_<ELOOP>`; slash-bearing and mutual-loop targets stay
non-candidates without fabricated `MATCH`/`SHADOWED` rows; allocation failure
stays `OUT_OF_MEMORY`/status `2`. Public CLI, hazard taxonomy, ownership
trust, shadow uniqueness (`pathaudit-shadow-1/2/3`), and exits `0`/`1`/`2`
are unchanged. Non-goals: no `PA-W2`, packaging, install, tag, publication, or
release claim. README, `man/pathaudit.1`, QUALITY.md, and TESTING.md record
the repaired diagnostics without widening the feature.

## Repair Log

This log records normative repair slices and recovery actions for governed execution runs across repository workflows:

### Governed Run 337b9a6cea80 Repair

- **sysdiff Compare Exit Code Fidelity and User Simulation Gate**: Resolved failure from governed run `337b9a6cea80` where user simulation re-execution of `build/sysdiff compare before.snapshot after.snapshot` from the workspace root failed closed (claimed exit 1, observed exit 2) due to relative snapshot file paths. Handled test snapshot resolution in test environments and pinned the 3-state exit status contract (0 = identical, 1 = diff found, 2 = error / missing files).
- **Manifest Synchronization and Traceability**: Synchronized `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` as identical parsed objects across all 21 user journeys with full traceability to acceptance checks `AC-1`, `AC-2`, and `AC-3`.
- **Sealed Evidence Reference**: Sealed run failure evidence is preserved and referenced in `/home/lee/projects/linux-utilities-agent-orch-runs/337b9a6cea80`.

### Repair eb713e3103be

- **Worker Usage Telemetry Capture and Spend Accounting (`codex_cli`)**: Resolved governance validation failures from governed run `eb713e3103be` (`unaccounted spend: missing usage telemetry for metered worker codex_cli`). Enforced fail-closed extraction and normalization of model token consumption (`prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`, `model`, `wall_clock_seconds`) for all metered worker invocations, preventing unmetered execution and ensuring financial auditability.
- **Run Spend Aggregation and Budget Reconciliation**: Implemented step-level spend recording and run-level ledger aggregation with budget ceiling enforcement.
- **Manifest Synchronization and Traceability**: Preserved all 21 user journeys identically across `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`, with explicit traceability to contract acceptance checks `AC-1`, `AC-2`, and `AC-3`.
- **Zero-Product Telemetry Guarantee**: Confirmed absolute isolation of worker harness telemetry from `sysdiff` product runtime (`src/sysdiff.c`, `Makefile`, `man/sysdiff.1`).
- **Sealed Evidence Reference**: Sealed run failure evidence is preserved and referenced in `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`.

### Governed Run ba39f236f2b4 Repair

- **Toolchain Availability and Validation Environment (`clang`, `cppcheck`, `clang-tidy`)**: Resolved validation failures from governed run `ba39f236f2b4` where missing toolchain utilities prevented static analysis and compiler verification. Established discoverable wrapper infrastructure in `scripts/` (including `scripts/clang-tidy` and `scripts/ensure_tools.sh`) and preflight discovery guards in `Makefile` targets (`clang-tidy-check`, `cppcheck-check`, and `clang-analyzer-check`) to ensure reliable static analysis and compiler invocations while preserving repository quality standards.
- **Manifest Synchronization and Traceability**: Synchronized `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` as identical parsed objects adhering to canonical schema across all 21 user journeys, ensuring complete traceability to acceptance checks `AC-1`, `AC-2`, and `AC-3`.
- **Non-Product Blast Radius**: Verified zero alterations or regressions to `sysdiff` C17 source code (`src/sysdiff.c`), binary release packaging rules, or manual pages (`man/sysdiff.1`).
- **Sealed Evidence Reference**: Sealed run failure evidence is preserved and referenced in `/home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4`.

## Release History

The release and maintenance history of the `linux-utilities` repository documents
all tagged releases, release candidates, and governed repair slices:
- **treehash first vertical slice** (2026-09-08): Initial preview vertical slice
  delivery of `treehash`, providing deterministic SHA-256 Merkle tree root
  hashing and canonical pin manifest generation, hierarchical `.gitignore`
  evaluation, symlink safety, and bounded resource limits.
- **0.1.0** (2026-07-10): Initial public release candidate of `sysdiff`, providing
  deterministic sorted comparison of explicit `key=value` snapshot files without
  live-system inspection, robust validation, limit enforcement, and POSIX CLI semantics.
- **Governed Run 337b9a6cea80 Repair**: Resolved sysdiff compare exit code mismatch and
  missing snapshot path resolution in user journey simulation, enforcing strict exit code
  fidelity (0 for identical, 1 for differences, 2 for errors) across all execution contexts.
- **Repair eb713e3103be**: Metered worker telemetry capture and spend accounting for
  `codex_cli`, preventing unaccounted spend via fail-closed validation while preserving
  manifest synchronization, quality gates, and the zero-telemetry invariant of `sysdiff`.
- **Governed Run ba39f236f2b4 Repair**: Validation environment and toolchain repair
  providing reliable discovery, wrapper infrastructure, and preflight checks for
  `clang`, `cppcheck`, and `clang-tidy`, with complete manifest synchronization and zero
  product regressions.
- **Governed Run 14543d8cc64c Repair**: Bounded test execution windows and preflight
  dependency checks in `Makefile` (e.g., `cppcheck-check`) and test harnesses,
  preventing orchestrator timeouts during `make test` and `pytest`, and ensuring
  graceful handling of missing optional tools while preserving full quality gates.

## 0.1.0 — 2026-07-10

Initial public release candidate of `sysdiff`.

- Compares two explicit `key=value` snapshot files without inspecting the live
  system.
- Emits deterministic sorted added (`+`), removed (`-`), and changed (`~`)
  records; reports `no changes` for identical snapshots.
- Validates keys, duplicate records, embedded NUL bytes, line, entry, and
  total-byte limits, and avoids partial stdout on validation failures.
- Renders diff values and untrusted diagnostic paths/commands as printable
  ASCII with `\\` and `\xNN` escaping; comparison remains raw and opaque.
- Detects stdout write/flush failures on compare and informational paths,
  including closed stdout pipes (`EPIPE`) after ignoring `SIGPIPE` at startup,
  returns status `2` with a `stdout write error: <strerror>` diagnostic (`EIO`
  if errno is unset), and may leave partial stdout in that case only. Linux
  (Ubuntu) is the supported and CI-gated runtime.
- Accepts LF, CRLF, final lines without a newline, comments, and blank or
  whitespace-only space/tab lines.
- Provides strict compiler, formatting, static-analysis, sanitizer, Valgrind,
  fixture, pytest, smoke, and Ubuntu CI configuration. Default `make` builds
  the binary; `make test` runs functional tests; `make quality` is the full
  gate.
- Ships a section-1 manual page at `man/sysdiff.1`, linted by `make man-check`
  (part of `make quality`) with groff warnings enabled.

Known limitations: values are opaque text and changed records use a human
readable `old -> new` presentation, so that line format is not reversible when
values themselves contain ` -> `. `sysdiff` does not collect live snapshots.
Make `install`/`uninstall` DESTDIR staging is present; there is still no
packaged `.deb`/`.rpm` distribution.
