# `pathaudit` Maintenance Repair Contract

## Overview

This contract bounds the maintenance-only repair of three defects recorded by
the executable-shadowing review. First, every executable accepted by
`try_command_match` used to retain a `PATHAUDIT_MAX_ROOT_LENGTH + 1`
allocation (65,537 bytes) as winner or shadow state even when the canonical
path was short (`pathaudit-shadow-1`). Second, `record_executable_hit`
linearly scanned every prior winner for every hit, making a directory set with
many distinct executable basenames quadratic (`pathaudit-shadow-2`). Third,
after one distinct later realpath had been reported, repeating that same
non-winner PATH directory appended the identical `SHADOWED` tuple again
because the code compared only with the winner (`pathaudit-shadow-3`). The
pre-repair workspace fixture `PATH=early:late:late` exited `1` and printed the
same `SHADOWED` winner/late tuple twice with empty stderr.

The repaired implementation right-sizes retained canonical paths, replaces the
repeated linear winner search with a bounded basename index, and suppresses
only exact duplicate shadow tuples. The first PATH-order executable realpath
remains the winner. Every later *distinct* realpath for the same basename
remains one shadow, regardless of how many PATH components resolve to that
same later realpath. This is not a new detector, mode, hazard, output format,
or release project. Existing explicit-root, `--path`, and `--command` behavior
outside these defects remains the compatibility baseline.

## CLI Surface

The public command surface is unchanged: `pathaudit [--] ROOT...`,
`pathaudit --path`, `pathaudit --command NAME`, sole-argument
`pathaudit --help`, and sole-argument `pathaudit --version`. `--` ends option
processing only for explicit roots. The three inspection modes are mutually
exclusive; `--path` accepts no operand, while `--command` requires exactly one
nonempty basename containing no slash. Unset `PATH`, invalid command names,
unknown options, missing operands, extra operands, and mixed modes retain
their existing reject-closed behavior.

Only `--path` emits `SHADOWED` rows. Their byte shape remains
`SHADOWED<TAB>"COMMAND"<TAB>"WINNER_REALPATH"<TAB>"SHADOW_REALPATH"<LF>`.
Shared-taxonomy findings precede all shadow rows; shadow rows sort by raw
command-basename bytes and then PATH position. The uniqueness rule is by
`(command, winner realpath, shadow realpath)`: an exact tuple is emitted
once, while two genuinely distinct later realpaths still produce two rows.
`--command` continues to express multiple matches as PATH-ordered `MATCH`
rows, not `SHADOWED` rows, and explicit-root mode continues not to enumerate
executables. Escaping, locale independence, resource limits, stdout failure
handling, help text, version text, and diagnostic shapes do not change.

## Closed Hazard Taxonomy

The closed shared hazard-code set remains exactly `EMPTY_ROOT`,
`RELATIVE_ROOT`, `MISSING_ROOT`, `NON_DIRECTORY_ROOT`, `GROUP_WRITABLE`,
`WORLD_WRITABLE`, and `UNSAFE_OWNER`, in that rank order for an otherwise
equal finding. `EMPTY_ROOT` marks a zero-byte root or PATH component;
`RELATIVE_ROOT` marks a nonempty non-absolute input; `MISSING_ROOT` covers
`ENOENT`; and `NON_DIRECTORY_ROOT` covers a final non-directory or
`ENOTDIR`. `GROUP_WRITABLE` and `WORLD_WRITABLE` reflect `S_IWGRP` and
`S_IWOTH` on applicable directory or resolved-executable targets.

`UNSAFE_OWNER` retains the implemented trust rule: UID 0 and the invoking real
UID from `getuid()` are trusted. Under `--path`, usable PATH directories and
their canonical ancestor chain, plus resolved executable targets, may emit
`UNSAFE_OWNER`; under `--command`, directory-chain findings remain subject to
the existing command-applicability rule and matched executables use the same
trust rule. Shared canonical ancestors deduplicate to their lowest applicable
PATH index. Explicit-root mode remains ownership-blind. User documentation
(`man/pathaudit.1`, README.md, CHANGELOG.md, and this contract) must describe
that directory/ancestor ownership behavior and the repaired shadow uniqueness
rule; older text that denied ancestor checks or claimed directory ownership
is not classified is stale relative to `src/pathaudit.c` and
`tests/test_pathaudit.py`.

`SHADOWED` is a completed-hazard output class but is not an eighth member of
the shared root hazard-code enum. `MATCH` is informational and is not a
hazard. No other word may be introduced as a finding code by this repair.
Operational reasons such as `USAGE`, `UNKNOWN_OPTION`, `PATH_UNSET`,
`INVALID_COMMAND`, limit reasons, `OUT_OF_MEMORY`, `INSPECTION_ERROR_N`, and
`STDOUT_WRITE` remain stderr diagnostics rather than hazard codes.

## Exit Statuses

Exit status meanings remain exactly `0`, `1`, and `2`. Status `0` means the
requested inspection or informational command completed successfully and no
hazard was found; in `--command` mode, one or more clean `MATCH` rows alone do
not change that result. Status `1` means inspection completed and at least one
shared-taxonomy finding or `SHADOWED` row was emitted. After duplicate
suppression, one unique shadow tuple still produces status `1`; removing a
duplicate copy must never turn a genuinely hazardous run into status `0`.

Status `2` remains reserved for usage and environment rejection, invalid
command names, resource-limit failure, operational metadata failure,
allocation failure, and stdout write or flush failure. Operational failures
remain reject-closed with empty stdout when they occur before emission;
stdout failure may leave partial output. Allocation-failure cleanup and
diagnostic precedence are preserved. No new status, signal-based success path,
performance-warning status, or partial success code is authorized. Successful
hazard paths keep stderr empty.

## Non-Goals

This repair does not add recursion, writable-ancestor detection, a new
ownership policy, a new executable-image policy, package or process
inspection, ACL/capability/mount checks, remediation, PATH editing, command
execution, networking, persistence, monitoring, or a daemon. It does not
change the trust set, follow a different symlink target, reinterpret empty or
relative PATH components, collapse duplicate root findings, or suppress
distinct shadow realpaths. It does not address unrelated Low findings such as
the large `readlink` stack buffer (PA-W1), executable-image scope (PA-W2),
directory-ownership dedup complexity (`path-dir-ownership-1`), or other
historical pathaudit and sysdiff backlogs.

The work does not add installation, distribution, publication, or release
claims for `pathaudit`; it remains a preview source utility. It does not alter
`sysdiff` or `permguard` behavior, packaging membership, version numbers, or
their tests. It does not replace deterministic functional assertions with a
timing-only benchmark, treat a sanitizer as a functional oracle, or redefine
the Agent-Orch smoke manifest as direct pathaudit product coverage when it
still reaches pathaudit through `scripts/smoke.sh` and `make test`.

## Delivery Plan

1. Regressions in `tests/test_pathaudit.py` pin `winner:shadow:shadow` to
   exactly one `SHADOWED` row, pin two different later realpaths to two rows,
   and retain first-PATH winner, byte ordering, status `1`, and empty stderr.
   A bounded many-basename fixture exercises the winner index and retained-path
   ownership without relying on wall-clock timing as its sole assertion.

2. `src/pathaudit.c` uses the large buffer only while `realpath` requires it,
   copies successful canonical text to exact `strlen + 1` storage before
   retention, indexes winners without scanning all distinct basenames on every
   hit, and tracks already-recorded shadow realpaths per command so only exact
   duplicate tuples disappear. Allocation, growth-overflow, and early-error
   paths free owned strings exactly once. Finding order, PATH precedence,
   escaping, diagnostics, limits, and all three modes are preserved.

3. User-facing documentation records the repaired behavior without widening
   the product surface: `man/pathaudit.1` documents one tuple for repeated
   non-winner components that resolve to the same shadow realpath and the
   live PATH-directory/ancestor ownership checks; README.md and CHANGELOG.md
   carry a `pathaudit Maintenance Repairs` section covering diagnostics, exit
   statuses, compatibility, and non-goals; this contract remains the
   maintenance authority for those three closed findings.

4. Build and smoke wiring stay compatibility blast radius. The Makefile already
   compiles `src/pathaudit.c` under strict GCC/Clang, runs
   `tests/test_pathaudit.py` through `test-suite`, lints `man/pathaudit.1`, and
   carries pathaudit through sanitizer and Valgrind targets. `scripts/smoke.sh`
   currently runs `make test`, and `tests/smoke_manifest.json` invokes that
   script as a governed smoke step. Those routes continue to reach the repaired
   regressions; the sysdiff-oriented manifest is not a dedicated pathaudit
   end-to-end oracle. The eight artifacts—`tests/test_pathaudit.py`,
   `src/pathaudit.c`, `man/pathaudit.1`, README.md, CHANGELOG.md, Makefile,
   `scripts/smoke.sh`, and `tests/smoke_manifest.json`—are the explicit blast
   radius of the old behavior even when a reviewed file needs no textual edit.

## Acceptance Checks

The focused functional gate must compile the repaired source with strict C17
warnings and run `python3 -m pytest -p no:cacheprovider
tests/test_pathaudit.py -q`. Exact-output regressions must prove: repeated
winner realpaths do not self-shadow; repeated identical non-winner realpaths
produce one row; distinct non-winner realpaths each produce one row; the first
PATH hit remains the winner; shared hazards precede shadows; shadow ordering is
deterministic; explicit-root emits no `SHADOWED`; `--command` keeps its
PATH-ordered `MATCH` behavior; and all applicable runs retain their exact
stdout, stderr, and `0`/`1`/`2` status semantics.

Static and dynamic checks must show that retained winner and shadow strings are
right-sized, winner lookup no longer rescans all distinct winners per hit,
duplicate suppression does not leak, double-free, or use freed storage, and
allocation failures still return `2` with cleanup. Run the existing strict
GCC and Clang gates, clang-format, clang-tidy, cppcheck, Clang analyzer,
man-page lint, pathaudit sanitizer coverage, and Valgrind coverage through the
Makefile surface. Verify README.md, CHANGELOG.md, `man/pathaudit.1`, and this
contract agree with the live directory-ownership and shadow semantics. Run the
governed smoke route from `tests/smoke_manifest.json` through
`scripts/smoke.sh`, recording its actual scope rather than upgrading the claim.

The full test suite passing, rather than only a new regression test passing,
is the definition of done, with no pre-existing sysdiff, pathaudit, or
permguard regression: run `make test` (or its exact full-suite pytest and shell
equivalents) after the focused checks, and then the complete applicable
quality surface. Skips must remain honest host-capability skips, not newly
introduced evasions. Completion also requires review evidence that
`pathaudit-shadow-1`, `pathaudit-shadow-2`, and `pathaudit-shadow-3` are closed
without claiming unrelated backlog closure, installation, packaging,
publication, or pathaudit release readiness.

## Quality-Gate Inheritance For This Slice

This maintenance-repair verify step runs only non-writing compiler and analysis
commands plus the full pytest suite. Fresh executable evidence for the slice:

- `gcc` / `clang` `-std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only` on
  `src/sysdiff.c`, `src/pathaudit.c`, and `src/permguard.c`
- `clang-format --dry-run --Werror` on those three sources
- `clang-tidy` with the Makefile check set and `--warnings-as-errors='*'`
- `cppcheck --enable=all --error-exitcode=1` on those three sources
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`

Clang static analyzer (`clang --analyze`), AddressSanitizer, UndefinedBehaviorSanitizer,
Valgrind, and any full link/`make` quality target are **inherited only where the
existing pytest harness already exercises them** (temporary compile of
`src/pathaudit.c` under the pathaudit fixture, unit/integration/regression/fixture
coverage inside `tests/`). Those write-producing gates are **explicitly omitted**
for this slice because the trusted workspace summary does not declare their
generated output paths (`build/`, mktemp link products under Makefile recipes,
sanitizer/Valgrind instrumented binaries, coverage artifacts, or clang-format
write mode). Smallest follow-up to make the omitted surface executable: declare
those generated-output paths in the governed workspace summary (or run them
under an already-allowlisted mktemp-only recipe that records no workspace
writes), then execute `make clang-analyzer-check`, `make test-sanitize`, and
`make test-valgrind` (or the equivalent non-workspace-writing probes) as a
bounded follow-up step. `tests/smoke_manifest.json` and `scripts/smoke.sh`
remain byte-for-byte unchanged; the smoke gate continues to reach pathaudit only
transitively through `make test`.
