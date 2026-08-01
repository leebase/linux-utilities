# `permguard` Medium Repairs Delivery Plan

## Architecture

Keep `docs/permguard-bootstrap-contract.md` as the sole live product authority
and treat `docs/permguard-medium-repairs-contract.md` as the bounded
maintenance acceptance contract. Implement only PG-DOC-501, PG-DOC-502,
PG-TEST-503, PG-PORT-505, and PG-DOC-512. First add the two output-failure
regressions. Then remove the hand declaration from `src/permguard.c` and add a
permguard-specific, command-line `_POSIX_C_SOURCE=200809L` definition to every
Make and pytest compilation path. Use a dedicated non-overridable internal
Make variable for this source rather than depending solely on caller-replaced
`CFLAGS`; do not edit `src/pathaudit.c` or change another utility's runtime
behavior.

Correct `architecture.md` to the four independent mode predicates and
streaming continue-after-error model. Mark
`docs/permguard-first-vertical-slice-contract.md` and
`plans/permguard-first-vertical-slice-plan.md` as superseded at their starts,
point them to the bootstrap contract, and remove the false claim that the
bootstrap files were deleted. Extend `QUALITY.md` and `TESTING.md` with
permguard's actual strict/static/manual/test/sanitizer/Valgrind membership,
`PERMGUARD_BIN` and `PERMGUARD_UNDER_VALGRIND` behavior, chmod-then-lstat
fixture oracle, and capability-skip policy. Reconcile direct compilation and
maintenance claims in `README.md`, `docs/permguard.md`,
`man/permguard.1`, and `CHANGELOG.md` without changing CLI behavior.

The explicit old-behavior blast radius is `src/permguard.c`, `Makefile`,
`tests/test_permguard.py`, `tests/smoke_manifest.json`, `scripts/smoke.sh`,
`README.md`, `man/permguard.1`, `CHANGELOG.md`, plus the relevant documents
listed above and `docs/permguard-bootstrap-contract.md` and
`plans/permguard-bootstrap-implementation-plan.md`. Review every surface;
leave `tests/smoke_manifest.json`, `scripts/smoke.sh`, and other already-correct
files byte-unchanged unless a concrete acceptance failure requires an edit.
The current governed playbook's later write allowlists do not include
`architecture.md`, `QUALITY.md`, `TESTING.md`, the superseded draft/plan, or
`docs/permguard.md`; reconcile those allowlists before their repair step.
Otherwise the run cannot honestly close PG-DOC-501, PG-DOC-502, or
PG-DOC-512.

## Tests

Add regressions to `tests/test_permguard.py` before changing source. A
`test_stdout_write_failure_on_dev_full`-style case opens `/dev/full` for the
child's stdout, scans a hazardous chmod-verified temporary operand, and
asserts numeric status 2 plus exact stderr
`b"permguard: STDOUT_WRITE\n"`; it skips with a specific reason only when the
host cannot provide a suitable device. A
`test_closed_stdout_pipe_is_status_two_not_sigpipe`-style case passes the
write end of a pipe whose read end is closed, then asserts status 2, the same
stderr, and explicitly excludes `-signal.SIGPIPE` and 141. Ensure descriptor
ownership is clear in the harness and all parent descriptors close on success
or failure.

Add or extend source/document contract regressions so the header owns the
`lstat` declaration, the pytest compiler flags include
`-D_POSIX_C_SOURCE=200809L`, the stale contract and plan advertise
supersession, architecture no longer contains the obsolete predicates or
buffering claims, and quality/testing guidance names the real permguard
routes. Preserve every existing behavioral oracle, including hostile
byte-rendering, final-symlink rejection, one `lstat` per operand, mode and
content immutability, taxonomy combinations, mixed status-2 streaming, and
decoy override protection.

Every contract check maps to tests and an executable verification:

| Acceptance check | Test mapping | Verification mapping |
| --- | --- | --- |
| AC-01 | Contract-integrity test reads live and superseded contract/plan markers and asserts the closed five-ID repair scope. | Focused pytest plus an `rg` review for authority and false-removal language. |
| AC-02 | Documentation regression reads `architecture.md`, `QUALITY.md`, and `TESTING.md` for required permguard semantics and gate names while rejecting obsolete claims. | Focused pytest, manual diff review, and Make target inventory comparison. |
| AC-03 | Source/build regression rejects a hand-declared `lstat` and requires the POSIX flag in pytest and every Make permguard compile route. | Strict GCC/Clang link and syntax checks, clang-tidy, cppcheck, and analyzer. |
| AC-04 | `/dev/full` subprocess regression asserts status 2 and exact `STDOUT_WRITE`, with an explicit capability skip. | Focused pytest normally, then under ASan/UBSan and Valgrind where supported. |
| AC-05 | Closed-reader pipe regression asserts status 2, exact stderr, and no SIGPIPE/141 termination. | Focused pytest normally, then sanitizer and Valgrind test routes. |
| AC-06 | Existing CLI, taxonomy, symlink, hostile-path, mixed-run, read-only, and source-surface tests remain collected and passing. | Focused pytest and complete repository suite; compare collection/counts for accidental loss. |
| AC-07 | Blast-radius regression/document checks cover all named surfaces; smoke files are inspected even when unchanged. | Governed smoke result, manifest/script inspection, and independent review diff audit. |
| AC-08 | No focused-only test can satisfy this item; it is an aggregate gate assertion. | `make quality`, complete suite, governed smoke, and fresh independent pass verdict. |

## Verification

Run focused feedback first:
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/test_permguard.py -q`. Record pass, fail, and skip totals; any
`/dev/full`, set-ID, inaccessible-path, or hostile-filename skip must retain
its explicit host-capability reason. Confirm the two new tests are collected
and actually execute on capable Linux hosts. Run an isolated strict prototype
probe with both GCC and Clang using
`-D_POSIX_C_SOURCE=200809L -std=c17 -Wall -Wextra -Wpedantic -Werror`, and
inspect compiler command lines to prove the platform header—not a source
declaration—owns `lstat`.

Run the static and documentation floor:
`make gcc-strict`, `make clang-strict`, `make clang-syntax`,
`make format-check`, `make clang-tidy-check`, `make cppcheck-check`,
`make clang-analyzer-check`, and `make man-check`. Run the memory paths
`make test-asan`, `make test-ubsan`, `make test-valgrind`,
`make permguard-sanitize`, and `make permguard-valgrind` when their required
tools are available; unavailable optional tooling must be reported as not run,
never implied to pass. Inspect all blast-radius diffs, verify the four taxonomy
tokens and 0/1/2 exits remain stable, and verify the superseded files cannot
reasonably be mistaken for live authority.

Finally run the complete repository definition of done, preferably through
`make quality`, which includes the shell suite, complete pytest tree, benchmark
check, sanitizers, and Valgrind. Also run the existing governed user smoke
through `tests/smoke_manifest.json`; `scripts/smoke.sh` must still transitively
execute `make test`, and the resulting artifact must show successful start and
check exits with no blocking errors. AC-01 and AC-02 are satisfied by focused
document tests plus review; AC-03 by strict/static commands; AC-04 and AC-05
by normal and memory-wrapped regressions; AC-06 by focused and complete
behavioral suites; AC-07 by smoke and blast-radius audit; AC-08 only by the
complete aggregate evidence and a fresh independent review verdict. Passing
the complete suite, not merely the new tests, is the definition of done.

## Risks

The immediate governance risk is under-scoping by allowlist: later playbook
steps currently cannot write several documents required to close three of the
five Mediums. Repair the playbook permissions before implementation; do not
declare partial documentation edits a closure. A second risk is feature-flag
drift: adding `_POSIX_C_SOURCE` only to pytest, only to default `CFLAGS`, or
only to strict builds would leave another compile route exposed. Conversely,
putting it indiscriminately into all utilities could broaden this repair and
disturb unrelated declarations, so keep it explicitly attached to every
permguard compile command and mirror it in documented direct builds.

Output-failure fixtures have host and harness hazards. `/dev/full` may be
absent or unsuitable, so its skip must be honest; the pipe test must close the
reader before the child's checked flush, retain no accidental reader copy,
avoid deadlock, and distinguish Python's negative signal return from shell
141. Valgrind may alter timing but must not alter the expected product status.
Documentation has an authority hazard: editing the superseded draft's body
without an unmistakable first-screen marker can perpetuate the ambiguity even
if the live contract is correct.

Preserve unrelated dirty worktree paths (`project-plan.md` and the untracked
fifth-utility planning files observed at framing time). Do not fold the open
Low findings, pathaudit prototype work, generic Make cleanup, new security
policy, packaging, or release work into this slice. Smoke remains
sysdiff-named and transitive rather than permguard-specific, so report exactly
what it proves: complete `make test` reachability and repository integration,
not a dedicated end-to-end permguard scenario.
