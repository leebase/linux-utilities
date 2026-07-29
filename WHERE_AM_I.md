# Where Am I

## pathaudit Governed Run `6ca4cebc8527` Recovery

Governed recovery run `4ae7a820b0a3` (`repair_governed_run_6ca4cebc8527`)
reconciled the dirty pathaudit maintenance candidate left by failed run
`6ca4cebc8527` and passed independent review. Focused pathaudit pytest:
151 passed / 15 skipped. Step-5 static gates on `src/pathaudit.c` all
exited 0. Step-6 ASan+UBSan and Valgrind pathaudit routes each
151 passed / 15 skipped. Step-7 complete suite: 343 passed / 15 skipped
(scratch writable gitdir). Smoke start/check 0 with empty blockers;
check.log `340 passed, 18 skipped in 22.01s`. Verdict
`code-reviews/review-pathaudit-governed-run-6ca4cebc8527.verdict.json`
is `pass` and closes `pathaudit-shadow-1/2/3`. Remaining: Medium
PA-6CA-4 (review-worker complete-suite/`git worktree` EROFS note) and
Low PA-6CA-1/2/3. Failed origin `6ca4cebc8527` is still not a passed
delivery; this does not release pathaudit or close unrelated backlogs.

## Fifth Utility Mission

The reviewed fifth-suite mission is `shebangcheck`: a future small ISO C17
command-line utility for read-only preflight of explicitly named scripts
against a closed direct-absolute-interpreter shebang subset. Its bounded first
vertical slice would accept only explicit regular-file operands, read a fixed
maximum first-line prefix, reject or classify malformed and unsupported
headers, inspect the directly named interpreter without launching it or
searching PATH, and emit deterministic escaped findings. `/usr/bin/env`
resolution, shell parsing, recursion, monitoring, remediation, persistence,
networking, installation, packaging, and release are outside that slice. A
later normative contract must still define the exact CLI, output bytes,
finding taxonomy, limits, diagnostics, signal behavior, and exit statuses.

Governed run `e5f6740c1571` selected the mission and passed independent review
with no Critical or High findings, Medium FUM5-M1/FUM5-M2, and Low
FUM5-L1–FUM5-L4. The Mediums preserve uncertainty in the comparison matrix
and the usefulness rating for a slice that excludes common env-launcher
shebangs; the Lows preserve an arithmetic error, a traceability omission, an
ambiguous heading-count contract clause, and an unexplained security score.
No `shebangcheck` source, tests, manual, Make wiring, smoke identity, package,
tag, or release was produced or verified. The suite still has three
implemented utilities, while fourth mission `inodealias` and fifth mission
`shebangcheck` remain planning commitments.

Next action is not feature implementation yet: complete bounded repair and
fresh independent review of permguard Medium PG-DOC-501/502, PG-TEST-503,
PG-PORT-505, and PG-DOC-512, keep recovery findings Medium PA-6CA-4 and Low
PA-6CA-1/2/3 visible after run `4ae7a820b0a3`, and clear any other applicable
Medium-or-higher expansion gate. Only then should Agent-Orch generate a
separate governed `shebangcheck` implementation playbook beginning with its
normative contract and continuing through fixtures, implementation,
documentation, dedicated smoke, quality evidence, and independent review.

## Bootstrap permguard (`51100a584ac9`)

The suite now has a reviewed third-utility bootstrap under the live contract
`docs/permguard-bootstrap-contract.md`. Governed run `51100a584ac9` delivered
`permguard`, a small ISO C17 read-only scanner for explicit operands:
`permguard [--] PATH...`, plus sole-argument `--help` and `--version`. It
performs one `lstat` per operand and reports the closed four-code taxonomy
`GROUP_WRITABLE`, `OTHER_WRITABLE`, `SET_USER_ID`, and `SET_GROUP_ID` from each
named object's own mode bits without file-type heuristics. Final symlinks are
status-2 rejections; findings stream per operand; mixed runs continue after
errors with operational precedence. It does not recurse, read PATH, mutate
permissions, install, package, or publish the utility.

Independent review allowlisted focused pytest at 52 passed / 0 skipped in
0.43s. That command transitively compiled permguard with strict C17 warning
flags into a temp tree; review did not freshly run Make, full pytest,
sanitizers, Valgrind, or static analyzers as gate results. Step-5 quality-floor
validation recorded static gates, ASan+UBSan/Valgrind `--help` probes, full
pytest 332 passed / 18 skipped, and shell fixtures passing. Smoke passed
start/check 0, empty blockers, and check.log pytest
`332 passed, 18 skipped in 19.78s`; that pinned sysdiff-named oracle reaches
permguard transitively through `make test` but is not a permguard-specific
end-to-end flow.

Verdict is `pass`, not finding-free: Medium PG-DOC-501 (architecture taxonomy
mismatch), PG-DOC-502 (superseded draft residue), PG-TEST-503 (`STDOUT_WRITE`
/SIGPIPE coverage gap), PG-PORT-505 (hand-declared `lstat`), and PG-DOC-512
(QUALITY/TESTING silence) plus Low PG-CRAFT-506, PG-TEST-507, PG-CLI-508,
PG-MAKE-509/510/511 remain. One-code vertical-slice drafts are superseded
non-authority. Next action is a bounded governed repair of the five Mediums
and a fresh independent review before feature expansion. This is not evidence
for broader permission auditing, recursion, remediation, release readiness, or
a published release.

## Prior — Permguard First Vertical Slice (`f742c10135e5`)

Run `f742c10135e5` delivered and reviewed a one-code `WORLD_WRITABLE_FILE`
slice under `docs/permguard-first-vertical-slice-contract.md`. Focused review
pytest was 67 passed / 0 skipped; verdict `pass` with Medium PG-REV-301/302
and Low PG-REV-202/203/205/206/303/304. Current run `51100a584ac9` supersedes
that product authority.

## Prior — Permguard Delivery (`629d1f459446`)

Run `629d1f459446` delivered and reviewed an earlier one-code slice after
repairing High PG-DOC-101. Its focused review check was 66 passed / 0 skipped,
and its pass verdict retained Medium PG-REV-201 plus Low PG-REV-202–207.
Superseded by later cycles.

## Prior — Permguard Bootstrap (`a8341dfae9f2`)

Historical four-code bootstrap from run `a8341dfae9f2` (world-writable
directories and set-ID executables also hazardous; verdict `pass` with
PG-DOC-001/PG-TEST-002). Superseded by `629d1f459446`.

## Next Utility Evaluation

Product orientation after reviewed Future Mission Discovery: pathaudit is
declared capability-complete for v1 product scope, and the chosen next
mission is bootstrap `permguard` (third suite utility)—a read-only
explicit-path permission/ownership auditor, not another pathaudit
detector. First vertical slice is `permguard [--] PATH...` with a closed
hazard taxonomy and suite-aligned exits; non-goals include recursion,
PATH reading, remediation, and any release claim. Review outcome:
`pass` with unresolved Low `permguard-writability-overlap` and
`first-slice-scope-breadth` only; review evidence was plan verification,
not a new-utility smoke or release gate. Its historical next action was to
launch governed work for that permguard bootstrap slice; run `51100a584ac9`
has now completed it under `docs/permguard-bootstrap-contract.md`. Do not
treat the selection handoff itself as implementation or release of
permguard, pathaudit, or sysdiff; prior Medium/Low repair backlogs remain
separately visible.

## Detect unsafe ownership of PATH directories

Governed run `50c0b4936d50` delivered Detect unsafe ownership of PATH
directories for `pathaudit --path` and `pathaudit --command`: every
usable PATH directory and each ancestor through `/` inherits the
executable ownership trust rule (UID 0 and invoking real UID from
`getuid()`); untrusted owners emit `UNSAFE_OWNER` on the canonical
directory `realpath`; shared ancestors deduplicate to the lowest PATH
index; missing/empty/non-directory invent no ownership lines;
`owner_uid_is_trusted` is shared with executable ownership;
explicit-root stays ownership-blind. Exact evidence: step-2
`make clean && make` exit 0; full pytest 280 passed, 18 skipped in
26.84s. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`280 passed, 18 skipped in 20.40s`. Review
`code-reviews/review-path-directory-ownership.{md,verdict.json}`
is `pass` (0 Critical/High/Medium, 1 Low path-dir-ownership-1);
allowlisted pathaudit pytest → 143 passed, 15 skipped. This does
**not** claim that `pathaudit` is released or that the sysdiff smoke
oracle covers directory-ownership `--path` / `--command` detection.
Next: keep Low `path-dir-ownership-1` visible; prefer Detect writable
ancestors of PATH directories as next genuine capability; Medium
pathaudit-shadow-1 is closed by later recovery `4ae7a820b0a3`.

## Detect executables with unsafe ownership

Governed run `1d5eedc01202` delivered Detect executables with unsafe
ownership for `pathaudit --path` and `pathaudit --command`: final
followed-target `st_uid` trusts only UID 0 and the invoking real UID
from `getuid()`; every other owner emits `UNSAFE_OWNER` on the
executable `realpath`; ownership composes with writability via shared
code-rank sort; candidates are never executed; explicit-root never
searches executables. Exact evidence: step-4 `make quality` exit 0;
Clang `-fsyntax-only` exit 0; cppcheck exit 0; full pytest 271 passed,
14 skipped in 19.02s. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`271 passed, 14 skipped in 19.94s`. Review
`code-reviews/review-pathaudit-unsafe-executable-ownership.{md,verdict.json}`
is `pass` (0 Critical/High/Medium/Low formal findings); allowlisted
full pytest → 271 passed, 14 skipped. This does **not** claim that
`pathaudit` is released or that the sysdiff smoke oracle covers an
ownership-specific `--path` / `--command` user flow. Next: keep
informational ownership notes visible; Medium pathaudit-shadow-1 is
closed by later recovery `4ae7a820b0a3`; resume prior Medium backlog
other than the closed shadow IDs.

## Detect writable resolved-executables through PATH

Governed run `574d06adfc2a` delivered Detect writable
resolved-executables through PATH for `pathaudit --path` and
`pathaudit --command`: final executable targets reuse
`GROUP_WRITABLE` / `WORLD_WRITABLE` on the executable `realpath`
(owner-only write silent); symlink resolution follows the final
target; shebang/ELF probing excludes non-executable decoys; unsafe
inspection reject-closes via `INSPECTION_ERROR_N`; explicit-root never
searches executables; findings precede `SHADOWED`. Exact evidence:
step-3 Clang `-fsyntax-only` exit 0; full pytest 269 passed, 1 skipped.
Exact smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`269 passed, 1 skipped in 18.74s`. Review
`code-reviews/review-pathaudit-writable-executables.{md,verdict.json}`
is `pass` (0 Critical/High/Medium, 2 Low PA-W1/PA-W2); allowlisted
full pytest → 269 passed, 1 skipped. This does **not** claim that
`pathaudit` is released or that the sysdiff smoke oracle covers
writable-executable `--path` / `--command` detection. Next: keep Low
PA-W1/PA-W2 visible; Medium pathaudit-shadow-1 is closed by later
recovery `4ae7a820b0a3`; resume prior Medium backlog other than the
closed shadow IDs.

## Detect executable shadowing across PATH entries

Governed run `f94509b47fd3` delivered Detect executable shadowing
across PATH entries for `pathaudit --path`: first regular `X_OK`
basename in PATH order wins; later distinct `realpath` hits emit
`SHADOWED` lines after directory hazards; explicit-root never emits
`SHADOWED`; empty/missing/non-directory/unreadable components are
skipped for the scan; no nested recursion. Exact evidence: step-4
GCC/Clang `-fsyntax-only` exit 0; full pytest 247 passed, 1 skipped.
Exact smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`247 passed, 1 skipped in 18.41s`. Review
`code-reviews/review-executable-shadowing.{md,verdict.json}` is
`pass` (0 Critical/High, 1 Medium pathaudit-shadow-1, 2 Low
pathaudit-shadow-2/3); allowlisted full pytest → 247 passed, 1
skipped. This does **not** claim that `pathaudit` is released or that
the sysdiff smoke oracle covers executable-shadowing `--path`
detection. Later recovery `4ae7a820b0a3` closed pathaudit-shadow-1/2/3;
keep that historical Medium/Low record visible as prior evidence only.

## Detect non-directory PATH entries

Governed run `35116f657f35` delivered Detect non-directory PATH entries
for `pathaudit --path` and explicit roots: pins `NON_DIRECTORY_ROOT`
for regular-file, symlink-to-file, and ENOTDIR components (status 1,
empty stderr), mutually exclusive with `MISSING_ROOT`, with permission
findings suppressed on non-directory roots. Exact evidence: step-3
Clang `-fsyntax-only` + cppcheck exit 0; full pytest 234 passed, 1
skipped. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`234 passed, 1 skipped in 19.50s`. Review
`code-reviews/review-detect-non-directory-path-entries.{md,verdict.json}`
is `pass` (0 Critical/High/Medium, 2 Low nondir-1/2); allowlisted
pathaudit pytest → 94 passed, 1 skipped. Runtime logic pre-existed;
this slice documents and pins it. This does **not** claim that
`pathaudit` is released or that the sysdiff smoke oracle covers
non-directory `--path` detection. Next: keep Low nondir visible;
resume prior Medium backlog.

## Command-Specific PATH Risk Inspection

Governed run `2b2fb272c21a` delivered bounded command-specific PATH
risk inspection for `pathaudit --command NAME`: PATH-order `MATCH`
lines for one basename; plant-risk-before-winner shared-taxonomy
hazards; `INVALID_COMMAND` / `PATH_UNSET` reject-close; single-
basename collision filtering. Exact evidence: step-4
`make clean && make test` → 230 passed, 1 skipped; full pytest 230
passed, 1 skipped; format/tidy/cppcheck/analyzer/man-check +
`pathaudit-sanitize` / `pathaudit-valgrind` exit 0; pathaudit pytest
90 passed, 1 skipped. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`230 passed, 1 skipped in 18.98s`. Review
`code-reviews/review-command-specific-path-risk.{md,verdict.json}`
is `pass` (0 Critical/High/Medium, 2 Low pathaudit-cmd-1/2);
allowlisted full pytest → 230 passed, 1 skipped. This does **not**
claim that `pathaudit` is released or that the sysdiff smoke oracle
covers `--command`. Next: keep Low pathaudit-cmd visible; resume
prior Medium backlog.

## Working-Directory-Dependent PATH Entries

Governed run `79a1cc2bac7a` delivered working-directory-dependent PATH
detection for `pathaudit --path`: empty fields retain `""` →
`EMPTY_ROOT`; non-absolute components → `RELATIVE_ROOT` plus cwd
lookup; absolute entries never mislabeled. Exact evidence: step-4
GCC/Clang `-fsyntax-only` + cppcheck exit 0; pathaudit pytest 62
passed, 1 skipped; full pytest 202 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `202 passed, 1 skipped in
18.42s`. Review
`code-reviews/review-pathaudit-working-directory-path.{md,verdict.json}`
is `pass` (0 Critical/High/Medium, 2 Low pathaudit-wdp-1/2); allowlisted
pathaudit pytest → 62 passed, 1 skipped; full pytest → 202 passed, 1
skipped. This does **not** claim that `pathaudit` is released or that
the sysdiff smoke oracle covers cwd-dependent `--path` detection. Next:
keep Low pathaudit-wdp visible; resume prior Medium backlog.

## Writable PATH Directories

Governed run `d27d2ade171f` delivered additive `pathaudit --path`: an
opt-in mode that audits process `PATH` directory components with the
shared hazard taxonomy (including writable-directory findings). Exact
evidence: step-5 `make clean && make test` → 196 passed, 1 skipped;
format/tidy/cppcheck/analyzer + `pathaudit-sanitize` /
`pathaudit-valgrind` exit 0; ASan+UBSan pathaudit 56 passed, 1 skipped.
Exact smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `196 passed, 1 skipped in
18.33s`. Review
`code-reviews/review-pathaudit-writable-path.{md,verdict.json}` is
`pass` (0 Critical/High/Medium, 4 Low PA-WP-1–PA-WP-4); allowlisted
pytest → 56 passed, 1 skipped. This does **not** claim that `pathaudit`
is released or that the sysdiff smoke oracle covers `--path`. Prior Low
PA-WP findings remain visible after `79a1cc2bac7a`.

## pathaudit Vertical-Slice Bootstrap

Governed run `4dec475ef201` delivered the second utility in this suite:
additive `pathaudit` 0.1.0 — a read-only ISO C17 scanner for explicitly
supplied PATH directory roots (contract
`docs/pathaudit-contract.md`, source `src/pathaudit.c`, man
`man/pathaudit.1`, tests `tests/test_pathaudit.py`). Exact evidence:
pathaudit pytest 26 passed; full suite 158 passed (132 + 26); GCC/Clang
strict + format/tidy/cppcheck/analyzer + ASan/UBSan/Valgrind contract
coverage clean. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`158 passed in 12.88s`. Review
`code-reviews/review-pathaudit-bootstrap.{md,verdict.json}` is `pass`
(0 Critical/High, 2 Medium PA-M1/PA-M2, 7 Low PA-L1–PA-L7). This does
**not** claim that `pathaudit` is released, installable, or covered by
the existing sysdiff smoke oracle. Prior to `--path`, next was PA-M2 /
PA-M1 leftovers; those Mediums remain separately visible after
`d27d2ade171f` unless a later review closes them.

## Prepared Unpublished sysdiff 0.1.0 Release Candidate

Governed run `580b0f6ff811` prepared an unpublished `sysdiff` **0.1.0**
release candidate and completed independent package review. Archive and
checksum: workspace-root `sysdiff-release.tar.gz` and
`sysdiff-release.tar.gz.sha256` (digest
`9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f`).
RC-001 pass; clean `/tmp` extract `make clean test` → 121 passed, 7
skipped. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`128 passed in 10.64s`. Review
`code-reviews/review-sysdiff-release.{md,verdict.json}` is `pass`
(0 Critical/High, 1 Low L1). High H1 was repaired between review
attempts. This does **not** claim that a release was published. Next
authorized action: Lee-controlled publication authorization; do not
modify package inputs after the reviewed archive.

## First Independent sysdiff Release-Candidate Review

Governed run `6d0a6fbfe83d` completed the first independent `sysdiff`
release-candidate review. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log shows
install/uninstall staging and pytest `127 passed in 10.75s`. Exact review
check: `python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.89s` at HEAD `510fa2d`. Review
`code-reviews/review-first-sysdiff-release-candidate.{md,verdict.json}` is
`pass` (0 Medium/High/Critical, 10 Low L1–L10). Step-2 attempt 1 failed on
Medium M1; attempt 2 passed. Consecutive clean RC reviews in this required
sequence: **1**. The second consecutive clean review remains outstanding.
This does not claim that `sysdiff` is released without Lee-controlled release
authorization. Prior Medium backlogs remain open and continue to prohibit new
feature work while Medium-or-higher debt remains.

## Second Independent Release-Candidate Review Cycle

Governed run `c84986cf0c81` completed a prior independent release-candidate
review cycle for `sysdiff`. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log shows
install/uninstall staging and pytest `127 passed in 10.84s`. Exact review
check: `python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.96s`. Review
`code-reviews/sysdiff-rc-second-independent-cycle.{md,verdict.json}` is
`pass` under Medium (0 Medium/High/Critical, 9 Low L1–L9). RC-001
strcasecmp-mutant kill re-verified. Historical relative to the current
mission sequence after `6d0a6fbfe83d` (required consecutive counter is 1 with
second outstanding). This does not claim that `sysdiff` is released without
Lee-controlled release authorization.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` completed a prior first independent
release-candidate review cycle for `sysdiff`. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`; check.log shows install/uninstall staging and pytest
`127 passed in 10.58s`. Exact review check: `python3 -m pytest tests/ -q`
exited 0 with `127 passed in 11.06s`. Review
`code-reviews/sysdiff-rc-review-cycle-1.{md,verdict.json}` is `pass`
(0 Medium/High/Critical, 7 Low F1–F7 preserved). Historical relative to run
`6d0a6fbfe83d`. This does not claim that `sysdiff` is released or that the
mission is complete. A second consecutive review cycle with no
release-blocking findings is still required.

## First Consecutive Release-Blocking Independent Review

Governed run `7eb4e29dee6e` completed the first consecutive clean
release-blocking independent review of `sysdiff` 0.1.0. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`; check.log shows install/uninstall staging and pytest
`124 passed in 10.23s`. Exact full suite: `python3 -m pytest tests/ -q` exited
0 with `124 passed in 10.71s`. Review
`code-reviews/sysdiff-independent-review-1.{md,verdict.json}` is `pass` (0
Medium/High/Critical, 5 Low L-1–L-5 preserved). This is not a second clean
review, not mission completion, and not release readiness.

## Reproducible Source Archive — Isolated Build Verification

Governed run `939ee21b0d76` completed isolated `make dist` verification and
extracted-tree quality exercise. Exact archive identity at
`SOURCE_DATE_EPOCH=946684800`: 89851 bytes; SHA-256
`5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544` (both
builds identical; basename-only checksum matching); 44 members; empty
member diff. Report
`docs/reproducible-source-archive-isolated-build.md` (Overall Result PASS).
Extracted-tree gates exit 0 including ASan/UBSan/Valgrind (118 passed, 6
skipped); install/uninstall 2→0 files. Smoke passed with start/check 0.
Review
`code-reviews/review-reproducible-source-archive-isolated-build.{md,verdict.json}`
is `pass` (0 High/Critical, 5 Medium F1–F5, 4 Low F6–F9); allowlisted
pytest 124 passed in 10.71 s. Closeout handoff is recorded. This is not a
`.deb`/`.rpm` claim, not commit-identical dirty-tree provenance, and not
full release readiness.

## Reproducible sysdiff Source Release (`make dist` / `make distcheck`)

Governed run `240bfcbc634e` delivered conventional reproducible source
packaging: `make dist` / `make distcheck`, six `test_dist_*` regressions,
README "Source releases", and artifacts `dist/sysdiff-source.tar.gz` plus
`dist/sysdiff-source.tar.gz.sha256` (digest
`970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a`). Exact
checks: pytest 38 passed (5.80 s impl / ~5.8 s review); `make clean && make
test`; `make dist && make distcheck`; Clang `-fsyntax-only`. Smoke passed
with start/check 0. Review
`code-reviews/review-sysdiff-source-release.{md,verdict.json}` is `pass`
(0 High/Critical, 5 Medium F1–F5, 5 Low F6–F10). Closeout handoff is
recorded. This is not a `.deb`/`.rpm` claim, not a fresh `make quality`,
and not full release readiness. Prior `b54d61531266` `source-release`
naming is superseded by this workflow.

## Deterministic sysdiff Performance Benchmarks

Governed run `a0eda97cd039` delivered the Linux performance/resource harness:
`scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`,
`make benchmark`, README "Performance Benchmarks", and
`artifacts/performance/sysdiff-benchmark.json` (`passed: true`). Exact
gated evidence: `startup_ms_median` 1.2422580039128661 <= 200.0;
`fixture_ms_median` 7.362931006355211 <= 100.0; `peak_rss_kib` 2540.0 <=
32768.0; baseline `/bin/true` median 1.3354689872357994; 8000-entry fixture.
Exact checks: pytest 25 passed (1.73 s repair / 1.62 s review);
`make -n benchmark`; harness `--output`. Smoke passed with start/check 0.
Review `code-reviews/review-sysdiff-performance-benchmarks.{md,verdict.json}`
is `pass` (0 High/Critical/Medium, 9 Low B1–B9). Closeout handoff is
recorded. This is not a microbenchmark claim, not a fresh `make quality`,
and not full release readiness.

## Deterministic Malformed-Snapshot Fuzz Regression Coverage

Governed run `feb8e707ea28` delivered bounded deterministic malformed-snapshot
fuzz regression coverage: contract
`docs/malformed-snapshot-fuzz-regression-contract.md`, corpus module
`tests/test_sysdiff_malformed_fuzz.py`, and review
`code-reviews/review-malformed-snapshot-fuzz-regression.{md,verdict.json}`.
Exact checks: `python3 -m pytest tests/test_sysdiff_malformed_fuzz.py -q`
(40 passed in 0.18–0.19 s) and Clang `-fsyntax-only` on `src/sysdiff.c`
(exit 0). Smoke passed with start/check 0. Review is `pass` at High (0
High/Critical, 4 Medium, 3 Low). This is not open-ended fuzzing, not a fresh
sanitizer/Valgrind product gate, and not release readiness.

## Current Milestone

The current milestone is the reviewed pathaudit maintenance recovery from
run `4ae7a820b0a3` for failed origin `6ca4cebc8527`. It closes
`pathaudit-shadow-1/2/3` under independent verdict `pass` while leaving
Medium PA-6CA-4 and Low PA-6CA-1/2/3 visible, and it does not claim that
the failed origin run passed or that pathaudit is released. The separately
reviewed permguard bootstrap from run `51100a584ac9` remains live under
`docs/permguard-bootstrap-contract.md` with Medium
PG-DOC-501/502, PG-TEST-503, PG-PORT-505, PG-DOC-512 still open. This
milestone does not change the separately prepared unpublished `sysdiff`
0.1.0 package from run `580b0f6ff811`.

## Milestone state

- Run `4ae7a820b0a3` recovered and reviewed the dirty pathaudit
  maintenance candidate from failed `6ca4cebc8527`: focused pytest
  151/15; static gates exit 0; ASan+UBSan and Valgrind pathaudit
  151/15 each; complete suite 343/15 (writable gitdir); smoke
  start/check 0 with check.log 340/18; verdict `pass` closing
  pathaudit-shadow-1/2/3 with remaining Medium PA-6CA-4 and Low
  PA-6CA-1/2/3. Origin `6ca4cebc8527` is still not a passed delivery.
- Run `51100a584ac9` delivered and reviewed the live `permguard` bootstrap:
  bootstrap contract/plan/source/man/tests/Makefile wiring; focused pytest
  52/0 (review allowlisted, 0.43s); step-5 full 332/18 plus static gates and
  ASan/Valgrind `--help` probes; smoke start/check 0 and check.log 332/18.
  Review `pass` with Medium PG-DOC-501/502, PG-TEST-503, PG-PORT-505,
  PG-DOC-512 and Low PG-CRAFT-506, PG-TEST-507, PG-CLI-508, PG-MAKE-509/510/511.
  Not installed, packaged, released, recursive, or remedial.
- Run `f742c10135e5` is prior one-code evidence under
  `docs/permguard-first-vertical-slice-contract.md`: focused review pytest
  67/0; verdict `pass` with Medium PG-REV-301/302. Superseded as product
  authority by `51100a584ac9`.
- Run `629d1f459446` is prior one-code evidence: focused review pytest 66/0;
  High PG-DOC-101 repaired; verdict `pass` with Medium PG-REV-201 and Low
  PG-REV-202–207. Superseded by later cycles.
- Run `a8341dfae9f2` historically delivered a four-code `permguard`
  bootstrap (verdict `pass` with PG-DOC-001/PG-TEST-002); historical relative
  to the restored live bootstrap authority in `51100a584ac9`.
- Run `50c0b4936d50` delivered and reviewed Detect unsafe ownership of
  PATH directories: step-2 `make clean && make` exit 0; full pytest
  280/18 in 26.84s; smoke start/check 0; review `pass` with Low
  `path-dir-ownership-1` only; allowlisted pathaudit pytest 143 passed,
  15 skipped. Not a pathaudit release; smoke oracle does not directly
  exercise directory-ownership `--path` / `--command` detection.
- Run `1d5eedc01202` delivered and reviewed Detect executables with
  unsafe ownership: step-4 `make quality` exit 0; Clang `-fsyntax-only`
  exit 0; cppcheck exit 0; full pytest 271/14 in 19.02s; smoke
  start/check 0; review `pass` with empty formal findings; allowlisted
  full pytest 271 passed, 14 skipped. Not a pathaudit release; smoke
  oracle does not directly exercise an ownership-specific `--path` /
  `--command` user flow.
- Run `574d06adfc2a` delivered and reviewed Detect writable
  resolved-executables through PATH: step-3 Clang `-fsyntax-only`
  exit 0; full pytest 269/1; smoke start/check 0; review `pass` with
  Low PA-W1/PA-W2 only; allowlisted full pytest 269 passed, 1 skipped.
  Not a pathaudit release; smoke oracle does not directly exercise
  writable-executable `--path` / `--command` detection.
- Run `f94509b47fd3` delivered and reviewed Detect executable shadowing
  across PATH entries: step-4 GCC/Clang `-fsyntax-only` exit 0; full
  pytest 247/1; smoke start/check 0; review `pass` with Medium
  pathaudit-shadow-1 and Low pathaudit-shadow-2/3; allowlisted full
  pytest 247 passed, 1 skipped. Not a pathaudit release; smoke oracle
  does not directly exercise executable-shadowing `--path` detection.
  Later recovery `4ae7a820b0a3` closed those three shadow IDs.
- Run `35116f657f35` delivered and reviewed Detect non-directory PATH
  entries: step-3 Clang `-fsyntax-only` + cppcheck exit 0; full pytest
  234/1; smoke start/check 0; review `pass` with Low nondir-1/2 only;
  allowlisted pathaudit pytest 94 passed, 1 skipped. Runtime
  `NON_DIRECTORY_ROOT` logic pre-existed; slice documents and pins it.
  Not a pathaudit release; smoke oracle does not directly exercise
  non-directory `--path` detection.
- Run `2b2fb272c21a` delivered and reviewed command-specific PATH risk
  inspection: step-4 `make clean && make test` → 230/1; full pytest
  230/1; format/tidy/cppcheck/analyzer/man + sanitize/valgrind exit 0;
  pathaudit pytest 90/1; smoke start/check 0; review `pass` with Low
  pathaudit-cmd-1/2 only; allowlisted full pytest 230 passed, 1
  skipped. Not a pathaudit release; smoke oracle does not directly
  exercise `--command`.
- Run `79a1cc2bac7a` delivered and reviewed working-directory-dependent
  PATH detection: step-4 GCC/Clang `-fsyntax-only` + cppcheck exit 0;
  pathaudit pytest 62/1; full pytest 202/1; smoke start/check 0; review
  `pass` with Low pathaudit-wdp-1/2 only; allowlisted checks match. Not a
  pathaudit release; smoke oracle does not directly exercise
  cwd-dependent `--path` detection.
- Run `d27d2ade171f` delivered and reviewed additive `pathaudit --path`:
  step-5 full test 196 passed / 1 skipped; sanitize/valgrind/static
  gates exit 0; smoke start/check 0; review `pass` with Low PA-WP-1–PA-WP-4
  only; allowlisted pytest 56 passed, 1 skipped. Not a pathaudit release;
  smoke oracle does not directly exercise `--path`.
- Run `4dec475ef201` delivered and reviewed additive `pathaudit` 0.1.0:
  contract/source/man/26 tests/Makefile wiring; pytest 26 + full 158;
  smoke start/check 0; review `pass` with Medium PA-M1/PA-M2 and Low
  PA-L1–PA-L7. Not a pathaudit release; smoke oracle does not directly
  exercise pathaudit.
- Run `580b0f6ff811` prepared and reviewed the unpublished 0.1.0 release
  package: `sysdiff-release.tar.gz` + `.sha256` (digest
  `9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f`);
  RC-001 pass; clean extract 121/7; smoke start/check 0 with empty
  `blocking_errors`; review `pass` with Low L1 only after H1 repair. Not a
  published release.
- Run `6d0a6fbfe83d` recorded the first independent `sysdiff`
  release-candidate review: smoke start/check 0 with empty `blocking_errors`
  (check.log pytest `127 passed in 10.75s`); review check
  `python3 -m pytest -p no:cacheprovider tests/ -q` → 127 passed in 10.89 s;
  verdict `pass` with 0 Medium/High/Critical and 10 Low (L1–L10); consecutive
  clean RC reviews in this required sequence = 1; second still outstanding.
  Not a publication claim by itself.
- Run `c84986cf0c81` recorded a prior independent release-candidate review
  cycle: smoke start/check 0 with empty `blocking_errors`; review check
  `python3 -m pytest -p no:cacheprovider tests/ -q` → 127 passed in 10.96 s;
  verdict `pass` under Medium with 0 Medium/High/Critical and 9 Low (L1–L9);
  RC-001 strcasecmp-mutant kill re-verified. Historical relative to the
  current mission sequence; not a publication claim by itself.
- Run `8a3470eff7d3` recorded a prior first independent release-candidate
  review cycle: smoke start/check 0 with empty `blocking_errors`; review
  check `python3 -m pytest tests/ -q` → 127 passed in 11.06 s; verdict `pass`
  with 0 Medium/High/Critical and 7 Low (F1–F7). Historical relative to
  `6d0a6fbfe83d`; not a release, not mission completion.
- Run `7eb4e29dee6e` recorded the first consecutive clean release-blocking
  independent review: smoke start/check 0 with empty `blocking_errors`;
  full suite `python3 -m pytest tests/ -q` → 124 passed in 10.71 s; review
  verdict `pass` with 0 Medium/High/Critical and 5 Low (L-1–L-5). Not a
  second clean review, not mission completion, not release readiness.
- Run `939ee21b0d76` completed isolated source-archive verification: byte-
  identical `make dist` archives (SHA-256
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`, 89851
  bytes, 44 members), extracted-tree quality gates exit 0 including
  ASan/UBSan/Valgrind (118 passed, 6 skipped), install/uninstall 2→0, smoke
  start/check 0. Review
  `review-reproducible-source-archive-isolated-build.verdict.json` is `pass`
  (0 High/Critical, 5 Medium F1–F5, 4 Low F6–F9); allowlisted pytest 124
  passed in 10.71 s. Closeout recorded; next is Medium F1–F5 repair.
- Repository is initialized and committed on `main`.
- AgentFlow docs are present and should be read at session start.
- Agent-Orch scaffold and templates are present.
- Product baseline is intentionally tiny: `sysdiff --help` and `--version` plus
  a strict C build and smoke test, now with fixture-backed
  `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`.
- Run `fa24bb888cc0` produced the durable documentation contract for the first
  release-oriented `sysdiff compare` slice. The contract is
  explicit-snapshot-only and lives at
  `docs/sysdiff-snapshot-format-and-scope.md`.
- Run `3a9e56296af6` implemented the minimal C quality-gate harness and wired
  fixture-backed comparison tests into the smoke path.
- Run `b14e0191e257` delivered the core parser/comparer slice, resumed from
  source run `aa1eaef577cd`. It compares explicit snapshot files as
  bytewise-key-sorted `key=value` maps, keeps values opaque, validates key
  syntax, detects duplicate keys, rejects embedded NUL bytes, avoids partial
  stdout on parse errors, and reports deterministic added, removed, changed,
  and no-change output.
- Run `b6deb04a6055` delivered the routed tool-availability preflight for
  Agent-Orch worker infrastructure. Closeout validation and two Low review
  findings remain open.
- Run `5ff82aa95e06`, `sysdiff_fixture_smoke_repair`, completed closeout and
  resolved prior smoke-fixture F-001 Medium and F-002 Low findings.
- Run `c02d741432d3`, `sysdiff_c_source_implementation`, hardened resource
  limits and parse cleanup, passed smoke/review, and completed closeout.
- Run `c434e00a3772`, `craftsmanship_review_closeout`, completed the required C
  craftsmanship gate before further feature selection; verdict `pass` at
  High/Critical with Medium test/smoke findings that overlap the current
  fixture-acceptance backlog.
- The latest governed product slice is run `eab8bbd05f50`,
  `sysdiff_fixture_diff_acceptance_tests`. It authored fixture acceptance
  tests, verified fixture compare behavior in `src/sysdiff.c`, passed the
  pinned user smoke gate on attempt 1, and received a `pass` verdict at the
  High threshold in
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`.
- Fixture acceptance coverage now includes status 0/1/2, exact sorted stdout,
  ordering independence, comments/blank lines, CRLF equivalence, resource
  limits, and empty stdout on errors. Review also notes `argc < 1` is guarded
  and `make valgrind-test` cleans/rebuilds before Valgrind.
- The release-preparation verification on 2026-07-10 resolved the former
  F001–F004 findings and passed fresh Linux `make quality`. This is the release
  evidence, not the earlier smoke artifact with `start_exit_code: -15`.
- A later adversarial last-stop audit rejected that first candidate, found five
  additional Medium issues, and repaired them through Cursor/Grok coding plus
  independent planner review. Current protections include safe byte rendering,
  checked stdout/EPIPE behavior, a 16 MiB total snapshot cap, honest static and
  dynamic analysis failure semantics, and 41 governed tests.
- `sysdiff` v0.1.0 has Ubuntu CI and curated public release material. See
  `docs/RELEASE_REVIEW.md` for scope, evidence, and the accepted Low
  limitation.
- The publication follow-up adds a reviewed section-1 manual page at
  `man/sysdiff.1`. `make man-check` treats groff warnings as failures and is
  included in the canonical gate; post-integration `make quality` exited `0`.
- Lee approved the current diff output format on 2026-07-09:
  `+ key=value`, `- key=value`, and `~ key: old -> new`. Future OpenAI/Codex
  routes should use `gpt-5.5`; do not add GPT-5.4 assignments.
- Run `e7bbd28465b5` completed the sysdiff release documentation set through
  smoke and review (`pass`; Low F1/F2). Closeout is recording that result here.
- Run `5665167f1c1d` added deterministic memory regression gates. Exact
  implementation validation was: both shell syntax checks passed; 18 tool-
  preflight tests passed in 0.59 s; `make test-sanitize` exited 0; and `make
  test-valgrind` exited 0. Governed smoke recorded start/check exit codes 0 and
  no blocking errors.
- Review `review-deterministic-memory-gates.verdict.json` is `pass` at the High
  threshold (0 High/Critical, 4 Medium, 6 Low). Its fresh check was narrower:
  18 preflight tests passed in 0.57 s; sanitizer and Valgrind evidence came
  from the preceding validated implementation step.
- Memory-gate availability is host-dependent: Linux, working Clang sanitizer
  runtimes, GCC, and Valgrind are required. The current host passed; preflight
  intentionally fails instead of skipping when a prerequisite is absent.
- Run `a2d750c92da3` delivered reproducible install/uninstall packaging checks:
  Makefile staging via `DESTDIR`/`prefix`, shell exact-manifest and mode
  assertions, installed-program behavior, idempotent reinstall, and
  leftover-free file uninstall, with README installation docs. Validation ran
  `bash -n`, `make clean && make test`, and both shell suites. Review
  `review-install-uninstall-packaging.verdict.json` is `pass` (0 High/Critical,
  1 Medium F1, 6 Low F2–F7); allowlisted pytest reported 50 passed in 2.24 s.
- Packaging smoke note: `artifacts/user-smoke/result.json` passed, but the
  smoke manifest exercises fixtures; staged install/uninstall is covered by
  `make test` / `tests/test_sysdiff.sh`, not by that smoke oracle.
- Run `feb8e707ea28` delivered deterministic malformed-snapshot fuzz regression
  coverage: contract plus `tests/test_sysdiff_malformed_fuzz.py` (38 rejection
  cases + 2 structural tests). Validation ran the fuzz pytest module (40
  passed) and Clang `-fsyntax-only` (exit 0); no `src/sysdiff.c` edits.
- Review `review-malformed-snapshot-fuzz-regression.verdict.json` is `pass` at
  High (0 High/Critical, 4 Medium F1–F4, 3 Low F5–F7); allowlisted pytest
  reported 40 passed in 0.19 s. Review did not freshly rerun ASan/UBSan/
  Valgrind or `make quality`.
- Malformed-fuzz smoke note: `artifacts/user-smoke/result.json` passed, but the
  smoke manifest exercises fixtures; the hostile corpus is covered by the
  pytest module, not by that smoke oracle.
- Run `a0eda97cd039` delivered deterministic performance benchmarks: harness
  `scripts/benchmark_sysdiff.py`, contract tests, Makefile `benchmark`,
  README section, and `artifacts/performance/sysdiff-benchmark.json`
  (`schema_version` 1, `passed: true`).
- Exact gated measurements vs thresholds:
  `startup_ms_median` 1.2422580039128661 <= 200.0;
  `fixture_ms_median` 7.362931006355211 <= 100.0;
  `peak_rss_kib` 2540.0 <= 32768.0; plus `baseline_ms_median`
  1.3354689872357994; fixture_entry_count 8000; warmups 1; sample_count 5.
- Validation ran pytest (25 passed), `make -n benchmark`, and the harness
  `--output` path; repair closed prior Medium B1/B2 (exit-status checks and
  spawn-floor / scaled fixture).
- Review `review-sysdiff-performance-benchmarks.verdict.json` is `pass`
  (0 High/Critical/Medium, 9 Low B1–B9); allowlisted pytest reported 25
  passed in 1.62 s. Review did not freshly rerun `make quality` and does not
  claim microbenchmark or release readiness.
- Benchmark smoke note: `artifacts/user-smoke/result.json` passed, but the
  smoke manifest exercises fixtures; performance gates are covered by
  `make benchmark` / pytest / the committed JSON, not by that smoke oracle.
- Remaining environmental variability: Linux-only host; scheduler noise;
  spawn-dominated startup metric; RSS backend fallback order; `/bin/true`
  availability on minimal images.
- Closeout for `a0eda97cd039` is recorded in AgentFlow handoff docs with
  exact measurements/thresholds, verification outcomes, verdict, remaining
  Low findings and host variability, and next recommended action.
- Run `240bfcbc634e` delivered conventional `make dist` / `make distcheck`
  source packaging: tracked `DIST_PATHSPECS` via `git ls-files`, normalized
  archive metadata, six `test_dist_*` regressions, README "Source releases",
  and artifacts `dist/sysdiff-source.tar.gz` plus `.sha256` (digest
  `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a`).
- Validation ran pytest (38 passed in 5.80 s), `make clean && make test`,
  `make dist && make distcheck`, and Clang `-fsyntax-only` (exit 0).
- Review `review-sysdiff-source-release.verdict.json` is `pass`
  (0 High/Critical, 5 Medium F1–F5, 5 Low F6–F10); allowlisted pytest
  reported 38 passed in about 5.8 s. Review did not freshly rerun
  `make quality` and does not claim full release readiness.
- Source-release smoke note: `artifacts/user-smoke/result.json` passed, but
  the smoke manifest exercises fixtures; archive reproducibility is covered
  by `make distcheck` / pytest, not by that smoke oracle. Review F5 notes
  stale `.agent-orch` smoke pins that predate the dist work.
- Closeout for `240bfcbc634e` is recorded in AgentFlow handoff docs with
  exact artifact/checksum paths, verification outcomes, verdict, remaining
  risks, and next repair action. Prior `b54d61531266` `source-release`
  naming is historical and superseded by `dist`/`distcheck`.

## Next milestone

Next executable action: a bounded governed repair of permguard Medium
PG-DOC-501 (architecture taxonomy mismatch), remaining PG-DOC-502 draft
markers, PG-TEST-503 (`STDOUT_WRITE`/SIGPIPE coverage), PG-PORT-505
(hand-declared `lstat`), and PG-DOC-512 (QUALITY/TESTING silence), followed by
fresh independent review before feature expansion. Keep Low
PG-CRAFT-506/PG-TEST-507/PG-CLI-508/PG-MAKE-509/510/511, recovery Medium
PA-6CA-4 and Low PA-6CA-1/2/3, evaluation Lows, and prior pathaudit/sysdiff
backlogs visible. Do not claim permguard or pathaudit released, and preserve
the unpublished sysdiff candidate from `580b0f6ff811`.
