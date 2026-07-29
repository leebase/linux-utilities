# `pathaudit` Governed Run `6ca4cebc8527` Repair Contract

## Purpose and Authority

This document is the bounded delivery contract for recovering the workspace
changes attributable to failed Agent-Orch run `6ca4cebc8527`
(`pathaudit_maintenance_repairs`). That run passed its first four steps, failed
step 5 after an out-of-policy edit attempt and a 1,500-second worker timeout,
and never reached user smoke, independent review, or closeout. Its changes are
therefore dirty, unreviewed candidate work: they are not evidence that the
three maintenance findings are closed and must not be described as delivered,
verified, released, or ready to publish.

The exact run-attributable paths are:

- `docs/pathaudit-maintenance-repair-contract.md`
- `tests/test_pathaudit.py`
- `src/pathaudit.c`
- `README.md`
- `CHANGELOG.md`
- `man/pathaudit.1`
- `docs/pathaudit.md`, changed during failed step 5 outside that step's
  allowlist but still relevant to pathaudit documentation
- `tests/test_sysdiff.py`, changed during failed step 5 outside that step's
  allowlist and unrelated to the pathaudit repair

The first seven paths form the candidate pathaudit reconciliation set.
The run-attributable `tests/test_sysdiff.py` hunk is contamination and must be
removed from this repair rather than rationalized as pathaudit work. `Makefile`,
`scripts/smoke.sh`, and `tests/smoke_manifest.json` are verification blast
radius only; run evidence does not attribute a textual change to them.
This document,
`docs/pathaudit-governed-run-6ca4cebc8527-contract.md`, is the sole new
governance output for the recovery cycle; it was not created by the failed run
and is not one of the seven candidate product/documentation changes.

Later fifth-utility planning in `plans/fifth-utility-mission-contract.md` and
`plans/fifth-utility-mission-evaluation.md`, and later AgentFlow state in
`context.md`, `result-review.md`, `sprint-plan.md`, and `WHERE_AM_I.md`, are not
attributable to run `6ca4cebc8527`. They must remain byte-for-byte outside this
repair. Permguard, sysdiff, inodealias, and shebangcheck implementation or
planning work is likewise separate even when the complete suite exercises
those utilities.

## CLI Surface

The repair preserves the existing public forms exactly:
`pathaudit [--] ROOT...`, `pathaudit --path`,
`pathaudit --command NAME`, sole-argument `pathaudit --help`, and
sole-argument `pathaudit --version`. Explicit-root mode requires at least one
root and ignores `PATH`; `--` only ends option parsing for explicit roots.
`--path` accepts no operands and reads `PATH` once. `--command` requires
exactly one nonempty basename containing no slash, walks `PATH` in lookup
order, emits PATH-ordered `MATCH` rows for accepted executable candidates,
and never executes them. Inspection modes remain mutually exclusive. Unknown
options, bad arity, mixed modes, unset `PATH`, and invalid command names retain
their existing reject-closed diagnostics and status behavior.

Only `--path` emits executable-shadow rows, with the byte shape
`SHADOWED<TAB>"COMMAND"<TAB>"WINNER_REALPATH"<TAB>"SHADOW_REALPATH"<LF>`.
The first PATH-order executable realpath for a basename remains the winner.
Every distinct later realpath emits one row, while an exact
`(command, winner realpath, shadow realpath)` tuple emits at most once even
when a PATH component repeats or aliases the same directory. Shared findings
precede all `SHADOWED` rows; shadow rows retain raw-byte command ordering and
PATH-position tie-breaking. Explicit-root mode does not enumerate
executables, and `--command` continues to use `MATCH`, never `SHADOWED`.
Help/version bytes, printable-ASCII escaping, locale-independent comparisons,
resource limits, diagnostic precedence, signal handling, and stdout
write/flush behavior must remain stable.

## Closed Hazard Taxonomy

The repair addresses exactly this closed maintenance list and no fourth
finding: `pathaudit-shadow-1`, oversized retained canonical-path allocations
caused by keeping the 65,537-byte `realpath` scratch buffer instead of an
exact `strlen + 1` copy; `pathaudit-shadow-2`, repeated linear winner scans
that make many distinct executable basenames quadratic (closure also requires
that duplicate-tuple checks not reintroduce an O(shadow count) scan per
non-winner hit — a bounded `(command, shadow)` index satisfies that); and
`pathaudit-shadow-3`, duplicate identical `SHADOWED` rows when the same
non-winner realpath is encountered more than once. Closure requires both
behavioral evidence and ownership/complexity review; merely renaming or
documenting a defect does not close it.

The product's existing output taxonomy is compatibility scope, not additional
repair scope. Its shared finding codes remain exactly `EMPTY_ROOT`,
`RELATIVE_ROOT`, `MISSING_ROOT`, `NON_DIRECTORY_ROOT`, `GROUP_WRITABLE`,
`WORLD_WRITABLE`, and `UNSAFE_OWNER`. `SHADOWED` remains a completed-hazard
output class outside that shared enum, and `MATCH` remains informational.
Under `--path` and `--command`, usable PATH directories and canonical
ancestors through `/`, plus resolved executables, retain the implemented
`UNSAFE_OWNER` trust rule: UID 0 and the invoking real UID from `getuid()` are
trusted. Explicit-root mode remains ownership-blind. No finding code, trust
rule, ordering rank, applicability rule, or diagnostic reason may be added or
removed by this repair.

## Exit Statuses

Numeric meanings remain exactly `0`, `1`, and `2`. Status `0` means an
informational request succeeded or inspection completed without a hazard;
clean `MATCH` rows alone do not make `--command` hazardous. Status `1` means
inspection completed and at least one shared finding or unique `SHADOWED`
tuple was emitted. Suppressing a duplicate shadow copy must not change a run
with a genuine unique shadow from `1` to `0`, and a successful hazard path
continues to leave stderr empty.

Status `2` remains the sole operational/usage failure result, including
invalid invocation, unset `PATH`, invalid command name, resource-limit
failure, metadata or allocation failure, and stdout write or flush failure.
Pre-emission operational failures remain reject-closed with empty stdout;
stdout failure may leave partial output. The repair must not introduce another
numeric code, convert allocation failure into a hazard, treat timeout as
product success, or allow signal termination to masquerade as status `0` or
`1`. Tests must continue to distinguish process exit from signal death,
including the existing ignored-`SIGPIPE`/`STDOUT_WRITE` contract where
applicable.

## Explicit Non-Goals

This repair does not add a detector, mode, option, recursion, writable-ancestor
policy, new ownership or executable-image policy, package/process/service
inspection, ACL/capability/mount analysis, remediation, PATH editing, command
execution, networking, persistence, monitoring, or daemon behavior. It does
not close PA-W1, PA-W2, `path-dir-ownership-1`, PA-M1, PA-M2, or any other
historical pathaudit or sysdiff backlog. It does not change versions, install
or distribution membership, publication state, or make a pathaudit release
claim.

The repair does not adopt the `tests/test_sysdiff.py` writable-git-common-dir
skip created by failed step 5, because that is unrelated sysdiff test-policy
work even though it is attributable to the failed run. It does not edit or
revert later fifth-utility planning or the later shared-memory closeout files
listed in Purpose and Authority. It does not reinterpret the existing
sysdiff-oriented smoke manifest as a dedicated pathaudit end-to-end oracle,
and it does not count inherited historical test results, a focused regression,
a timeout, a skip, or a worker's success message as fresh verification.

## Delivery Plan

1. Capture a path-level and hunk-level inventory against the pre-run Git
   baseline and the run's `progress.json`, attempt policies, and validation
   records. Preserve later planning/shared-memory changes. Remove only the
   run-attributable `tests/test_sysdiff.py` contamination, then constrain all
   recovered product/documentation edits to the seven-file pathaudit
   reconciliation set named above. This contract is the only additional
   governed output. If another path proves necessary, stop and amend this
   contract before editing it.

2. Preserve test-first provenance. Review the step-2 additions in
   `tests/test_pathaudit.py`, then demonstrate against the pre-repair source
   that at least the repeated-non-winner regression fails for the intended
   reason. Pin one row for `winner:shadow:shadow`, one row per genuinely
   distinct later realpath, first-PATH winner selection, deterministic bytes,
   status `1`, empty stderr, symlink aliases resolving to the same shadow, and
   unchanged `--command` `MATCH` behavior. A bounded many-basename fixture may
   establish functional indexing behavior, but elapsed time alone is not an
   acceptance oracle.

3. Audit and repair `src/pathaudit.c`: use the large allocation only as
   transient `realpath` scratch, retain exact-size owned strings, use a
   bounded basename lookup instead of rescanning all winners per hit, and
   suppress only exact duplicate shadow tuples via a bounded
   `(command, shadow)` index rather than a linear scan of recorded shadows.
   Check hash/index growth, overflow guards, collision probing, allocation
   failure, ownership transfer, cleanup, double-free, leak, and use-after-free
   paths. Preserve all CLI, output, ordering, limit, trust, and exit contracts
   above.

4. Reconcile `docs/pathaudit-maintenance-repair-contract.md`, README.md,
   CHANGELOG.md, `man/pathaudit.1`, and `docs/pathaudit.md` to the verified
   behavior. Documentation must describe the already-delivered
   directory/ancestor ownership rule and exact shadow-tuple uniqueness without
   claiming that failed run `6ca4cebc8527` passed. CHANGELOG language may
   state closure only after fresh verification and independent review; before
   then it must describe candidate repairs or remain unstated.

5. Verify in bounded, serial stages. Every subprocess gets an explicit
   wall-clock timeout, termination grace period, captured exit status, and log;
   no stage is allowed to consume the entire worker budget. Use explicit C
   filenames—`src/sysdiff.c`, `src/pathaudit.c`, and `src/permguard.c`—rather
   than a quoted or non-shell-expanded `src/*.c`. Stop on a timeout, record it
   as failure, terminate descendants, and diagnose the smallest failing stage
   before retrying. Do not run competing Make/sanitizer/Valgrind jobs against
   shared build outputs.

6. After focused and complete verification pass, run the governed user-smoke
   gate without modifying `scripts/smoke.sh` or
   `tests/smoke_manifest.json`, then obtain a fresh independent review of the
   exact reconciled diff. Only that review may close
   `pathaudit-shadow-1/2/3`. Closeout may then update AgentFlow shared memory
   in a separately allowlisted step, preserving later mission planning and
   recording actual commands, durations, skips, smoke scope, and verdict.

## Timeout-Safe Verification

The delivery playbook must allocate writable outputs such as `build/` and
smoke artifacts before invoking their existing gates. Representative GNU
`timeout` ceilings are: 180 seconds for focused pathaudit pytest, 600 seconds
for the complete pytest suite, 120 seconds for each strict/static tool, 300
seconds for man and shell fixture checks, 600 seconds each for sanitizer and
Valgrind routes, and 900 seconds for the governed smoke gate. Each invocation
uses `timeout --signal=TERM --kill-after=10s DURATION COMMAND...`; exit `124`,
`137`, or any signal termination is a failed check, never a skip or pass.
Ceilings may be raised only in a reviewed playbook amendment supported by a
measured successful baseline, not interactively after a hang.

Run the focused regression first, then explicit GCC and Clang C17 strict
checks, clang-format dry-run, clang-tidy, cppcheck, and the repository's Clang
analyzer route. Next run
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
under its full-suite timeout, followed by the existing shell fixture,
man-page, ASan, UBSan, and Valgrind routes with their own ceilings. A
successful `make test` may be recorded in addition, but its log must show the
complete intended suite rather than an early or filtered subset. Finally run
the declared smoke manifest through Agent-Orch and record that it reaches
pathaudit transitively through `scripts/smoke.sh` and `make test`, not through
a dedicated pathaudit product flow.

## Acceptance Checks

Acceptance requires an attribution audit showing that the reconciled product
diff contains only the seven pathaudit files listed in Purpose and Authority,
that the unrelated run-attributable `tests/test_sysdiff.py` hunk is absent,
and that later `plans/fifth-utility-*`, `context.md`, `result-review.md`,
`sprint-plan.md`, and `WHERE_AM_I.md` changes were neither folded into nor
discarded by this repair. The recovery cycle may additionally add only this
contract document. `git diff --check` must pass. The Makefile and smoke
manifest/script must be unchanged unless a separately approved contract
amendment identifies a necessary pathaudit-specific correction.

Exact-output tests must prove one `SHADOWED` row for repeated identical
non-winner realpaths, separate rows for distinct later realpaths, unchanged
first-PATH precedence and byte ordering, shared findings before shadows,
explicit-root absence of executable enumeration, unchanged `--command`
PATH-ordered `MATCH` rows, and preserved stdout/stderr/status behavior.
Source and dynamic review must show exact-size retained paths, bounded winner
lookup, correct collision and growth behavior, duplicate suppression without
leaks or invalid ownership, and status-2 cleanup on allocation or output
failure.

The complete test suite must pass; passing only a new regression test is not
sufficient. Acceptance also requires strict GCC and Clang checks,
clang-format, clang-tidy, cppcheck, Clang analyzer, man/fixture checks, ASan,
UBSan, Valgrind, timeout-safe governed smoke, and a fresh independent review
with no unresolved Critical or High finding and an explicit verdict on all
three scoped maintenance IDs. Host-capability skips must be pre-existing or
independently justified and recorded; no new skip may conceal a regression.
Until every acceptance item is evidenced, run `6ca4cebc8527` remains failed
and unreviewed, and no closure, release, installation, packaging, or
publication claim is permitted.

## Documentation Impact

User-facing docs reconciled to this recovery must describe the live CLI
(`pathaudit [--] ROOT...`, `--path`, `--command NAME`, `--help`, `--version`),
directory/ancestor `UNSAFE_OWNER` under the existing trust rule, and exact
`(command, winner, shadow)` `SHADOWED` uniqueness without inventing modes or
claiming that failed run `6ca4cebc8527` passed. README.md carries a `pathaudit`
heading for current behavior; CHANGELOG.md records the candidate repair under
`Unreleased`; `man/pathaudit.1` keeps substantive NAME and DESCRIPTION aligned
with `src/pathaudit.c`. Closure language for `pathaudit-shadow-1/2/3` stays
deferred until fresh verification and independent review.
