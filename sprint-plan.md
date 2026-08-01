# Sprint Plan

## Post-hardening commissioning preparation — 2026-08-01

- [x] Align the commissioning packet with the configured autonomous worktree:
  `commissioning/post-hardening-commissioning-packet.md`, its JSON manifest,
  and `commissioning/check_packet.py` are present and readable. The packet
  excludes unrelated platform history and the prepared playbook declares only
  the bounded context plus narrow authority inputs.
- [x] Add the reusable pre-worker declared-input preflight guard in Agent-Orch;
  it fails missing/unreadable inputs before worker invocation while allowing
  outputs declared by prior steps. Platform regression coverage is green.
- [x] Repair the openunlink seam fixture expectation without changing product
  source: default fixture size is the supplied link payload length, while
  explicit sizes remain available for boundary tests.
- [x] Complete the openunlink documentation/contract slice with exact limit
  constants, final `st_size` and `st_nlink == 0` semantics, NFS silly-rename
  limitation, guide, and section-1 manual.
- [x] Validate focused `134 passed` / 46.42s, full `548 passed` / 18 skipped /
  117.16s, distribution extraction `1 passed` / 60.12s, packet completeness,
  identity, scratch syntax/dry-run, strict playbook lint, and diff checks.
- [ ] Before any autonomous re-arm, obtain authorized reconciliation of the
  still-uncommented Linux Utilities cron line. Mission state is halted and
  auto-orch preflight no-ops, but the schedule is not cleanly disarmed.
- [ ] Obtain separate authorization before launching the prepared
  `post_hardening_commissioning_repaired.yaml`; keep mission scheduling paused,
  do not push, and do not restore cron or re-arm.

## pathaudit PA-W1 Open-Repair Maintenance (`c9e3de33f46b`)

- [x] Governed run `c9e3de33f46b` (`pathaudit_open_repair_maintenance`)
  closed Low `PA-W1` under `docs/pathaudit-open-repairs-contract.md`:
  command-bounded `readlink` storage in `symlink_is_self_basename`,
  preserved bare-self `INSPECTION_ERROR_<ELOOP>` reject-close, AC-4
  non-self loop regressions, and bounded prose. Steps 1–7 passed attempt 1.
- [x] Exact evidence: focused pathaudit pytest 156 passed / 15 skipped;
  step-5 static gates exit 0 (one clang-format line-break repair); focused
  ASan+UBSan and Valgrind each 156/15; complete `make quality` exit 0 with
  ordinary / ASan / UBSan / Valgrind each 359 passed / 15 skipped (scratch
  writable gitdir); smoke start/check 0 with empty `blocking_errors` and
  check.log `356 passed, 18 skipped in 21.16s`.
- [x] Independent verdict
  `code-reviews/review-pathaudit-open-repairs.verdict.json` is `pass` and
  closes historical Low `PA-W1`. Remaining: Medium `PAW1-DOC-901` and Low
  `PAW1-DOC-902` / `PAW1-TEST-903` / `PAW1-TEST-904` / `PAW1-SCOPE-905`.
  Not a pathaudit release.
- [ ] Keep Medium `PAW1-DOC-901` and those four Lows visible until a later
  independent review closes them. Do not invent release readiness or
  optional polish as authorized work from this closeout. Prior pathaudit
  Medium PA-6CA-4 and Lows PA-6CA-1/2/3 stay open. Planning order remains
  `inodealias` → `shebangcheck` → `openunlink` ahead of any seventh-utility
  CODE.

## Seventh Utility Mission Recovery (`4824cd763b27` / origin `f7539c314ca1`)

- [x] Bounded recovery run `4824cd763b27`
  (`template_repair_before_review_feature_delivery`) repaired the live
  seventh-mission recovery contract, reconciled the on-disk evaluation,
  passed mechanical smoke, and obtained a fresh independent High-threshold
  review of the `sparsemap` recommendation. Failed origin run
  `f7539c314ca1` (`discover_evaluate_seventh_linux_utility`) remains
  **FAILED**; its step-2 timed-out attempts (`0`/`124`/`124` under a
  600-second ceiling after High `SEV7-H1` on pre-repair `elfinterp`) are
  distinct from this recovery and are not silent passes.
- [x] Fresh verdict
  `code-reviews/review-seventh-utility-mission-evaluation-recovery.verdict.json`
  is `pass` (no Critical/High). Weighted totals re-derived:
  `sparsemap` 141 / `cgroupceil` 134 / `mountstack` 130 / `lockscope` 128 /
  `elfinterp` 128. Allowlisted check: focused
  `tests/test_governed_run_c847e01d15fe.py` → 4 passed / 0 skipped
  (workflow only). Smoke start/check 0; check.log
  `351 passed, 18 skipped in 20.99s` (sysdiff-centered; not `sparsemap`
  product evidence).
- [ ] Keep Medium `SEV7R-M1` (asymmetric recycled-candidate provenance /
  omitted sixth-evaluation `sparsemap` rejection rationale) and
  `SEV7R-M2` (compressed non-winner hazard ledger defects), plus Low
  `SEV7R-L1` (incomplete attempt record) and `SEV7R-L2` (unhedged
  syscall-seam prescription), visible until a later review closes them.
- [ ] Do **not** implement, build, product-test, package, install, tag,
  publish, or release `sparsemap`. This recovery is selection-review
  evidence only and does not silently authorize a CODE playbook. Keep
  earlier planning-mission ordering visible and ahead of any seventh-
  utility implementation: `inodealias` (fourth), `shebangcheck` (fifth),
  `openunlink` (sixth, still gated on `SIXTH2-M1`–`M3` plus Lows).

## Sixth Utility Mission Discovery (`787b9bb3d830`)

- [x] Select and independently review exactly **Bootstrap `openunlink` explicit-process zero-link regular-file descriptor reporting**
  as the sixth planning mission. One-purpose scope: for one explicit Linux PID, report open
  descriptors whose followed targets are regular files with `st_nlink == 0`;
  procfs link text is escaped display context, not the predicate.
- [x] Record the planning-only first vertical slice: exact `--help`,
  `--version`, or one-decimal-PID CLI; bounded canonical numeric enumeration of
  fixed `/proc/PID/fd`; repeated directory-relative identity/type checks;
  ascending escaped `OPEN_UNLINKED` findings; visible per-descriptor
  advisories; closed statuses and taxonomies; focused fixtures; section-1
  manual; strict C/static/memory gates; dedicated user smoke; and independent
  review. All-PID discovery, target-content access, inode grouping, reclaim
  estimates, process control, monitoring, installation, packaging, tagging,
  publication, and release are excluded.
- [x] Record selection evidence accurately. Review artifacts
  `plans/review-sixth-utility-mission.md` and
  `plans/review-sixth-utility-mission.verdict.json` are `pass` with no Critical
  or High findings. Review allowlisted only Python byte-compilation of the
  three existing pytest modules, which exited 0. Existing smoke is
  sysdiff-centered aggregate evidence at 351 passed / 18 skipped, not an
  `openunlink` build, test, quality, dedicated-smoke, or release gate.
- [ ] Keep Medium `SIXTH2-M1` (descriptor-cap total suppression),
  `SIXTH2-M2` (nonzero-link filesystem boundary), and `SIXTH2-M3` (status-1
  finding/advisory discrimination), plus Low `SIXTH2-L1` (stderr writes),
  `SIXTH2-L2` (defensive size-range code), and `SIXTH2-L3` (stale run-step
  statement), visible until fresh independent review explicitly closes them.
- [ ] Next executable action for `openunlink`: do not begin implementation
  while the repair-before-expansion gate remains live. After applicable
  Medium-or-higher debt is repaired or explicitly reclassified and
  independently reviewed, generate a separate governed implementation
  playbook beginning with a normative contract that resolves
  `SIXTH2-M1`–`SIXTH2-M3` before CODE. This discovery does not reorder or
  implement planning-only `inodealias` or `shebangcheck`.

## permguard Medium-Repair Governed Run `ba6dc2fdd199` Recovery (`5035933ac7b4`)

- [x] Governed recovery run `5035933ac7b4`
  (`repair_governed_run_ba6dc2fdd199`) reconciled the dirty permguard
  Medium-repair candidate from failed run `ba6dc2fdd199` and obtained a
  clean independent review. Failed origin `ba6dc2fdd199` is still not a
  passed delivery.
- [x] Exact evidence: focused permguard pytest 63 passed / 0 skipped;
  step-5 complete `make quality` exit 0 with ordinary / ASan+UBSan /
  Valgrind each 354 passed / 15 skipped (scratch writable gitdir); smoke
  start/check 0 with empty `blocking_errors` and check.log
  `351 passed, 18 skipped in 21.76s`.
- [x] Independent verdict
  `code-reviews/review-governed-run-ba6dc2fdd199.verdict.json` is `pass`
  and closes Medium PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and
  PG-DOC-512. Remaining: Low PGR-TEST-706, PGR-PORT-707, PGR-BUILD-708,
  PGR-TEST-709, and PGR-DOC-710. Not a permguard release.
- [ ] Keep those five Lows visible along with bootstrap Lows
  PG-CRAFT-506/PG-TEST-507/PG-CLI-508/PG-MAKE-509/510/511, pathaudit
  Medium PA-6CA-4 and Lows PA-6CA-1/2/3, and FUM5 Mediums/Lows. Next:
  generate a separate governed `shebangcheck` implementation playbook
  beginning with its normative contract. Do not claim unrelated backlog
  closure or that failed origin `ba6dc2fdd199` passed.

## pathaudit Governed Run `6ca4cebc8527` Recovery (`4ae7a820b0a3`)

- [x] Governed recovery run `4ae7a820b0a3`
  (`repair_governed_run_6ca4cebc8527`) reconciled the dirty pathaudit
  maintenance candidate from failed run `6ca4cebc8527` and obtained a
  clean independent review. Failed origin `6ca4cebc8527` is still not a
  passed delivery.
- [x] Exact evidence: focused pathaudit pytest 151 passed / 15 skipped;
  step-5 static gates (GCC/Clang `-fsyntax-only`, clang-format,
  clang-tidy, cppcheck, Clang analyzer) all exit 0; step-6 ASan+UBSan
  and Valgrind pathaudit routes each 151 passed / 15 skipped; step-7
  complete suite 343 passed / 15 skipped (scratch writable gitdir);
  smoke start/check 0 with empty `blocking_errors` and check.log
  `340 passed, 18 skipped in 22.01s`.
- [x] Independent verdict
  `code-reviews/review-pathaudit-governed-run-6ca4cebc8527.verdict.json`
  is `pass` and closes `pathaudit-shadow-1/2/3`. Remaining: Medium
  PA-6CA-4 (review-worker complete-suite/`git worktree` EROFS
  environment note) and Low PA-6CA-1/2/3. Not a pathaudit release.
- [ ] Keep Medium PA-6CA-4 and Low PA-6CA-1/2/3 visible; do not treat
  PA-6CA-4 as a pathaudit product regression. Permguard Medium
  PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512 are closed by
  later recovery `5035933ac7b4` without claiming failed origin
  `ba6dc2fdd199` passed. Do not claim unrelated backlog closure.

## Discover and evaluate a fifth small Linux utility mission

- [x] Run `e5f6740c1571` selected exactly one fifth mission:
  `shebangcheck`, a read-only explicit-script validator for a closed
  direct-absolute-interpreter shebang subset. The bounded first slice is to
  inspect only explicit regular-file operands, cap the first-line/prefix read,
  avoid PATH search and all execution, inspect the directly named interpreter
  under a later closed usability rule, and produce deterministic escaped
  findings. Exact CLI, output grammar, finding taxonomy, limits, diagnostics,
  signal behavior, and exit statuses are deferred to the implementation
  contract.
- [x] Record independent review verdict `pass` from
  `code-reviews/review-fifth-utility-mission.verdict.json`: no Critical/High,
  Medium FUM5-M1/FUM5-M2, and Low FUM5-L1–FUM5-L4. The Mediums concern the
  comparison matrix's mismatch with contract criteria and inconsistent
  practical-value treatment of the excluded `/usr/bin/env` form; the Lows
  cover arithmetic, traceability, heading-count clarity, and security-score
  explanation. This is a reviewed selection, not a finding-free result.
- [x] Pathaudit maintenance recovery: failed origin run `6ca4cebc8527`
  remains not a passed delivery; recovery run `4ae7a820b0a3` reconciled
  and independently reviewed that candidate and closed
  `pathaudit-shadow-1/2/3` (remaining PA-6CA-4 Medium and PA-6CA-1/2/3
  Low).
- [x] Permguard Medium-repair recovery: failed origin run `ba6dc2fdd199`
  remains not a passed delivery; recovery run `5035933ac7b4` reconciled
  and independently reviewed that candidate and closed Medium
  PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512 (remaining
  Low PGR-TEST-706/PGR-PORT-707/PGR-BUILD-708/PGR-TEST-709/PGR-DOC-710).
- [ ] Generate a separate governed `shebangcheck` implementation playbook.
  It must begin with the normative contract and later provide fixtures, C
  source, documentation, dedicated user smoke, quality evidence, and
  independent review. Keep remaining Medium-or-higher notes (including
  PA-6CA-4 and FUM5-M1/M2) visible. This discovery run performed no
  implementation, compiler, formatter, product test, release, installation,
  packaging, publication, or verification work for `shebangcheck`.

## Bootstrap permguard (`51100a584ac9`)

Governed run `51100a584ac9`
(`bootstrap_permguard_first_vertical_slice`) delivered and independently
reviewed the live `permguard` bootstrap under
`docs/permguard-bootstrap-contract.md`: ISO C17 `permguard [--] PATH...` with
one `lstat` per operand, streaming per-operand emission, continue-after-error
mixed status 2, final-symlink rejection, and a closed four-code taxonomy
(`GROUP_WRITABLE`, `OTHER_WRITABLE`, `SET_USER_ID`, `SET_GROUP_ID`). Bootstrap
contract/plan, source, 52-test focused suite, man page, README/CHANGELOG, and
additive Makefile wiring exist. Independent allowlisted check: focused pytest
52 passed / 0 skipped in 0.43s. Step-5 quality-floor validation: GCC/Clang
strict, format, tidy, cppcheck, analyzer, ASan+UBSan/Valgrind `--help` probes,
full pytest 332 passed / 18 skipped, shell fixtures pass. Smoke start/check
exited 0 with empty `blocking_errors`; check.log recorded 332 passed / 18
skipped in 19.78s. Verdict
`code-reviews/review-permguard-bootstrap.verdict.json` is `pass` with Medium
PG-DOC-501/502, PG-TEST-503, PG-PORT-505, PG-DOC-512 and Low
PG-CRAFT-506, PG-TEST-507, PG-CLI-508, PG-MAKE-509/510/511. One-code
vertical-slice drafts are superseded non-authority. Not installed, packaged,
released, recursive, or remedial.

Sprint posture: later recovery `5035933ac7b4` closed the five Medium IDs
under a fresh independent review without claiming failed origin
`ba6dc2fdd199` passed; keep bootstrap Lows
PG-CRAFT-506/PG-TEST-507/PG-CLI-508/PG-MAKE-509/510/511 and recovery Lows
PGR-TEST-706/PGR-PORT-707/PGR-BUILD-708/PGR-TEST-709/PGR-DOC-710 visible.

## Prior — Permguard First Vertical Slice (`f742c10135e5`)

Governed run `f742c10135e5` delivered and reviewed a one-code
`WORLD_WRITABLE_FILE` slice under
`docs/permguard-first-vertical-slice-contract.md`. Independent allowlisted
check: focused pytest 67 passed / 0 skipped in 0.71s. Quality worker: full and
each ASan/UBSan/Valgrind route 350/15. Step validation: focused 67; full
347/18. Smoke start/check 0 with check.log 347/18. Verdict
`code-reviews/review-permguard-first-vertical-slice.verdict.json` is `pass`
with Medium PG-REV-301/302 and Low PG-REV-202/203/205/206/303/304. Superseded
as product authority by run `51100a584ac9`.

## Prior — Permguard Delivery (`629d1f459446`)

Run `629d1f459446` delivered and reviewed the live single-code slice after
repairing High PG-DOC-101. Focused review pytest was 66 passed / 0 skipped;
verdict `pass` carried Medium PG-REV-201 and Low PG-REV-202–207. Run
`f742c10135e5` supersedes that evidence and confirms PG-REV-201/204/207
resolved.

## Prior — Permguard Bootstrap (`a8341dfae9f2`)

Governed run `a8341dfae9f2`
(`bootstrap_permguard_first_vertical_slice`) delivered an earlier four-code
`permguard` bootstrap (world-writable files/directories and set-ID
executables). Verdict `code-reviews/review-permguard-bootstrap.verdict.json`
was `pass` with 2 Medium (PG-DOC-001, PG-TEST-002) and 3 Low findings. That
contract/plan taxonomy is superseded by `629d1f459446`.

## Next Utility Evaluation

Reviewed Future Mission Discovery selects bootstrap `permguard` as the
next mission after pathaudit v1 capability completion (explicit-root /
`--path` / `--command` plus quality floor; writable-ancestor and
setuid-on-PATH deferred, not blockers). First vertical slice: explicit-
root `permguard [--] PATH...` contract + C17 scanner + man + pytest +
Makefile wiring, without recursion, PATH reading, remediation, or a
release claim. Independent review
`code-reviews/review-next-linux-utility-evaluation.verdict.json` =
`pass` with two Low findings (`permguard-writability-overlap`,
`first-slice-scope-breadth`); evidence checks were plan-only, not
implementation smoke. Its historical posture preferred governed permguard
bootstrap next; run `51100a584ac9` has now completed that slice under
`docs/permguard-bootstrap-contract.md`. Keep evaluation Lows and prior
pathaudit Medium/Low plus sysdiff packaging Mediums visible; do not
schedule pathaudit-only polish or renewed `sysdiff` release work
(`v0.1.0` tag already exists). No utility was implemented or released by
this evaluation handoff.

## Detect unsafe ownership of PATH directories

Governed run `50c0b4936d50` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect unsafe
ownership of PATH directories for `pathaudit --path` and
`pathaudit --command` (`UNSAFE_OWNER` on usable PATH directory and
ancestor realpaths when `st_uid` is neither UID 0 nor `getuid()`;
shared-ancestor dedup to lowest PATH index; missing/empty/non-directory
invent no ownership lines; `owner_uid_is_trusted` shared with
executables; explicit-root never emits directory/ancestor
`UNSAFE_OWNER`). Exact verification (step-2): `make clean && make`
exit 0; full pytest → 280 passed, 18 skipped in 26.84s. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `280 passed, 18 skipped in
20.40s`). Review
`code-reviews/review-path-directory-ownership.{md,verdict.json}`
verdict `pass` (0 Critical/High/Medium, 1 Low path-dir-ownership-1).
Allowlisted review check: pathaudit pytest → 143 passed, 15 skipped.
Do **not** claim that `pathaudit` is released. Next: keep Low
`path-dir-ownership-1` visible; prefer Detect writable ancestors of PATH
directories as next genuine capability; Medium pathaudit-shadow-1 is
closed by later recovery `4ae7a820b0a3`; do not treat sysdiff smoke
as directory-ownership `--path` / `--command` coverage.

## Detect executables with unsafe ownership

Governed run `1d5eedc01202` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect
executables with unsafe ownership for `pathaudit --path` and
`pathaudit --command` (`UNSAFE_OWNER` on final followed-target realpath
when `st_uid` is neither UID 0 nor `getuid()`; composes with
writability via code rank; explicit-root never emits `UNSAFE_OWNER`;
candidates never executed). Exact verification (step-4): `make quality`
exit 0; Clang `-fsyntax-only` exit 0; cppcheck exit 0; full pytest →
271 passed, 14 skipped in 19.02s. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `271 passed, 14 skipped in
19.94s`). Review
`code-reviews/review-pathaudit-unsafe-executable-ownership.{md,verdict.json}`
verdict `pass` (0 Critical/High/Medium/Low formal findings). Allowlisted
review check: full pytest → 271 passed, 14 skipped. Do **not** claim that
`pathaudit` is released. Next: keep informational ownership notes
visible; Medium pathaudit-shadow-1 is closed by later recovery
`4ae7a820b0a3`; resume prior Medium backlog other than the closed shadow
IDs; do not treat sysdiff smoke as ownership-specific `--path` /
`--command` coverage.

## Detect writable resolved-executables through PATH

Governed run `574d06adfc2a` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect writable
resolved-executables through PATH for `pathaudit --path` and
`pathaudit --command` (shared `GROUP_WRITABLE` / `WORLD_WRITABLE` on final
executable realpaths; owner-only write silent; symlink → final target;
reject-closed inspection; explicit-root never searches executables;
findings precede `SHADOWED`). Exact verification (step-3): Clang
`-fsyntax-only` exit 0; full pytest → 269 passed, 1 skipped. Exact
smoke: `artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `269 passed, 1 skipped in
18.74s`). Review
`code-reviews/review-pathaudit-writable-executables.{md,verdict.json}`
verdict `pass` (0 Critical/High/Medium, 2 Low PA-W1/PA-W2). Allowlisted
review check: full pytest → 269 passed, 1 skipped. Do **not** claim that
`pathaudit` is released. Next: keep Low PA-W1/PA-W2 visible; Medium
pathaudit-shadow-1 is closed by later recovery `4ae7a820b0a3`; resume
prior Medium backlog other than the closed shadow IDs; do not treat
sysdiff smoke as writable-executable `--path` / `--command`
coverage.

## Detect executable shadowing across PATH entries

Governed run `f94509b47fd3` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect
executable shadowing across PATH entries for `pathaudit --path`
(`SHADOWED` lines for later distinct realpath hits against the first
PATH-order winner; directory hazards precede shadows; explicit-root
never emits `SHADOWED`). Exact verification (step-4): GCC/Clang
`-fsyntax-only` exit 0; full pytest → 247 passed, 1 skipped. Exact
smoke: `artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `247 passed, 1 skipped in
18.41s`). Review
`code-reviews/review-executable-shadowing.{md,verdict.json}` verdict
`pass` (0 Critical/High, 1 Medium pathaudit-shadow-1, 2 Low
pathaudit-shadow-2/3). Allowlisted review check: full pytest → 247
passed, 1 skipped. Do **not** claim that `pathaudit` is released. Later
recovery `4ae7a820b0a3` closed pathaudit-shadow-1/2/3; keep that
historical Medium/Low record visible as prior evidence only; do not
treat sysdiff smoke as shadowing `--path` coverage.

## Detect non-directory PATH entries

Governed run `35116f657f35` (playbook
`detect_non_directory_path_entries`) delivered Detect non-directory PATH
entries for `pathaudit --path` / explicit roots (`NON_DIRECTORY_ROOT`
for regular-file, symlink-to-file, ENOTDIR; status 1; mutually
exclusive with `MISSING_ROOT`; no permission findings on non-directory
roots). Exact verification (step-3, non-writing): Clang `-fsyntax-only`
exit 0; cppcheck exit 0; full pytest → 234 passed, 1 skipped. Exact
smoke: `artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `234 passed, 1 skipped in
19.50s`). Review
`code-reviews/review-detect-non-directory-path-entries.{md,verdict.json}`
verdict `pass` (0 Critical/High/Medium, 2 Low nondir-1/2). Allowlisted
review check: pathaudit pytest → 94 passed, 1 skipped. Runtime logic
pre-existed; slice documents and pins it. Do **not** claim that
`pathaudit` is released. Next: keep Low nondir visible; resume prior
Medium backlog; do not treat sysdiff smoke as non-directory `--path`
coverage.

## Command-Specific PATH Risk Inspection

Governed run `2b2fb272c21a` (playbook
`template_repair_before_review_feature_delivery`) delivered bounded
command-specific PATH risk inspection for `pathaudit --command NAME`
(PATH-order MATCH lines for one basename; plant-risk-before-winner
hazards; `INVALID_COMMAND` / `PATH_UNSET` reject-close). Exact
verification (step-4): `make clean && make test` → 230 passed, 1
skipped; full pytest → 230 passed, 1 skipped; format/tidy/cppcheck/
analyzer/man-check + `pathaudit-sanitize` / `pathaudit-valgrind`
exited 0; pathaudit pytest → 90 passed, 1 skipped. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `230 passed, 1 skipped in
18.98s`). Review
`code-reviews/review-command-specific-path-risk.{md,verdict.json}`
verdict `pass` (0 Critical/High/Medium, 2 Low pathaudit-cmd-1/2).
Allowlisted review check: full pytest → 230 passed, 1 skipped. Do
**not** claim that `pathaudit` is released. Next: keep Low
pathaudit-cmd visible; resume prior Medium backlog; do not treat
sysdiff smoke as `--command` coverage.

## Working-Directory-Dependent PATH Entries

Governed run `79a1cc2bac7a` (playbook
`pathaudit_working_directory_dependent_path_entries`) delivered
working-directory-dependent PATH detection for `pathaudit --path`
(empty fields → `EMPTY_ROOT` retained as `""`; non-absolute →
`RELATIVE_ROOT` plus cwd lookup; absolute never mislabeled). Exact
verification (step-4, non-writing): GCC/Clang `-fsyntax-only` exit 0;
cppcheck exit 0; pathaudit pytest → 62 passed, 1 skipped in 3.87s; full
pytest → 202 passed, 1 skipped in 22.46s. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `202 passed, 1 skipped in
18.42s`). Review
`code-reviews/review-pathaudit-working-directory-path.{md,verdict.json}`
verdict `pass` (0 Critical/High/Medium, 2 Low pathaudit-wdp-1/2).
Allowlisted review checks: pathaudit pytest → 62 passed, 1 skipped;
full pytest → 202 passed, 1 skipped. Do **not** claim that `pathaudit`
is released. Next: keep Low pathaudit-wdp visible; resume prior Medium
backlog; do not treat sysdiff smoke as cwd-dependent `--path` coverage.

## Writable PATH Directories

Governed run `d27d2ade171f` (playbook
`pathaudit_detect_writable_path_directories`) delivered additive
`pathaudit --path` (writable PATH directories via shared hazard taxonomy).
Exact verification: step-5 `make clean && make test` → 196 passed, 1
skipped; format/tidy/cppcheck/analyzer + `pathaudit-sanitize` /
`pathaudit-valgrind` exited 0; ASan+UBSan pathaudit → 56 passed, 1
skipped. Exact smoke: `artifacts/user-smoke/result.json` →
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors` (check.log pytest
`196 passed, 1 skipped in 18.33s`). Review
`code-reviews/review-pathaudit-writable-path.{md,verdict.json}` verdict
`pass` (0 Critical/High/Medium, 4 Low PA-WP-1–PA-WP-4). Allowlisted
review check: pytest `tests/test_pathaudit.py` → 56 passed, 1 skipped.
Do **not** claim that `pathaudit` is released. Next: keep Low PA-WP
visible; resume prior Medium backlog; do not treat sysdiff smoke as
`--path` coverage.

## pathaudit Vertical-Slice Bootstrap

Governed run `4dec475ef201` (playbook
`pathaudit_bootstrap_deterministic_scanner`) delivered the additive
`pathaudit` 0.1.0 vertical slice: contract, C17 scanner, man page,
26-test suite, Makefile wiring, and README/QUALITY/TESTING docs. Exact
verification: step-3 `pytest tests/test_pathaudit.py` → 26 passed in
0.38s; full `pytest tests/` → 158 passed in 14.98s (132 prior + 26);
GCC/Clang strict syntax, clang-format, clang-tidy, cppcheck, Clang
analyzer, ASan/Valgrind help probes exited 0. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `158 passed in 12.88s`). The
sysdiff smoke oracle does **not** directly exercise pathaudit. Review
`code-reviews/review-pathaudit-bootstrap.{md,verdict.json}` verdict
`pass` (0 Critical/High, 2 Medium PA-M1/PA-M2, 7 Low PA-L1–PA-L7). Do
**not** claim that `pathaudit` is released. Next: repair PA-M2 and
finish PA-M1 leftovers (CHANGELOG + architecture.md); keep Low visible.

## Prepared Unpublished sysdiff 0.1.0 Release Candidate

Governed run `580b0f6ff811` (playbook
`prepare_sysdiff_release_package_and_notes`) prepared an unpublished
`sysdiff` **0.1.0** release candidate via `make release`. Archive:
`sysdiff-release.tar.gz`; checksum: `sysdiff-release.tar.gz.sha256`
(digest
`9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f`).
RC-001 pass (`pytest -k rc_001` → 2 passed). Clean extraction `/tmp`
`make clean test` → 121 passed, 7 skipped. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log pytest `128 passed in 10.64s`).
Review `code-reviews/review-sysdiff-release.{md,verdict.json}` verdict
`pass` (0 Critical/High, 1 Low L1). Step-3 attempt 1 failed on High H1;
repair then attempt 2 passed. Do **not** claim that a release was
published. Next authorized action: await Lee-controlled release
authorization; keep L1 and prior Medium backlogs visible; do not modify
package inputs after the reviewed archive.

## First Independent sysdiff Release-Candidate Review

Governed run `6d0a6fbfe83d` (playbook
`template_repair_before_review_feature_delivery`) recorded the first
independent `sysdiff` release-candidate review. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`127 passed in 10.75s`). Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` → exit 0,
`127 passed in 10.89s` at HEAD `510fa2d`. Review
`code-reviews/review-first-sysdiff-release-candidate.{md,verdict.json}` verdict
`pass` with 0 Medium/High/Critical and 10 Low (L1–L10). Step-2 attempt 1
failed on Medium M1 (quality-floor provenance); attempt 2 held it at Low L1
and passed. Consecutive clean RC reviews in this required sequence: **1**.
The second consecutive clean review remains outstanding. Do not claim that
`sysdiff` is released; prior Medium backlogs remain open and continue to
prohibit new feature work while Medium-or-higher debt remains.

## Second Independent Release-Candidate Review Cycle

Governed run `c84986cf0c81` (playbook
`sysdiff_second_independent_release_candidate_review_cycle`) recorded a prior
independent release-candidate review cycle. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`127 passed in 10.84s`). Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` → exit 0,
`127 passed in 10.96s`. Review
`code-reviews/sysdiff-rc-second-independent-cycle.{md,verdict.json}` verdict
`pass` under Medium with 0 Medium/High/Critical and 9 Low (L1–L9). RC-001
strcasecmp-mutant kill re-verified. That earlier AgentFlow claim of consecutive
clean RC cycles = 2 is historical; the current mission sequence after run
`6d0a6fbfe83d` treats the required consecutive clean counter as 1 with the
second still outstanding. Do not claim that `sysdiff` is released from either
pass alone; prior Medium backlogs remain separately open.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` (playbook
`sysdiff_first_independent_rc_review_cycle`) recorded a prior first
independent release-candidate review cycle. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`127 passed in 10.58s`). Exact review check:
`python3 -m pytest tests/ -q` → exit 0, `127 passed in 11.06s`. Review
`code-reviews/sysdiff-rc-review-cycle-1.{md,verdict.json}` verdict `pass` with
0 Medium/High/Critical and 7 Low (F1–F7) preserved. Historical relative to the
current mission sequence anchored by run `6d0a6fbfe83d`. Do not claim that
`sysdiff` is released or that the mission is complete; a second consecutive
review cycle with no release-blocking findings is still required. Prior Medium
backlogs remain separately open.

## First Consecutive Release-Blocking Independent Review

Governed run `7eb4e29dee6e` (playbook
`complete_first_consecutive_release_blocking_independent_review`) recorded the
first consecutive clean release-blocking independent review. Exact smoke:
`artifacts/user-smoke/result.json` → `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors` (check.log: install/uninstall staging, fixtures ok, pytest
`124 passed in 10.23s`). Exact full suite: `python3 -m pytest tests/ -q` →
exit 0, `124 passed in 10.71s`. Review
`code-reviews/sysdiff-independent-review-1.{md,verdict.json}` verdict `pass`
with 0 Medium/High/Critical and 5 Low (L-1–L-5) preserved. Do not claim a
second clean review, mission completion, or release readiness from this first
consecutive clean pass; prior Medium backlogs remain separately open.

## Reproducible Source Archive — Isolated Build Verification

Governed run `939ee21b0d76` (playbook
`verify_reproducible_source_archive_isolated_build`) completed isolated
`make dist` verification and extracted-tree quality exercise. Exact archive
identity at `SOURCE_DATE_EPOCH=946684800`: 89851 bytes; SHA-256
`5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544` (both
builds; basename-only checksum matching); 44 members; empty member diff.
Extracted-tree gates all exit 0 (including ASan/UBSan/Valgrind at 118
passed / 6 skipped); install/uninstall 2→0 files. Smoke passed
(`artifacts/user-smoke/result.json` start/check 0). Review verdict `pass`
with 0 High/Critical, 5 Medium (F1–F5), 4 Low (F6–F9); allowlisted
`python3 -m pytest tests/ -q` → 124 passed in 10.71 s. Closeout handoff
recorded; next is repair F1–F5. Do not claim `.deb`/`.rpm`, commit-identical
dirty-tree archives, or full release closure.

## Reproducible sysdiff Source Release (`make dist` / `make distcheck`)

Governed run `240bfcbc634e` delivered conventional reproducible source
packaging (`make dist` / `make distcheck`; artifacts
`dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256` with
digest `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a`;
six `test_dist_*` regressions; README "Source releases"). Exact verification:
`python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py -q` → 38 passed
in 5.80 s (impl) / ~5.8 s (review); `make clean && make test` → 0;
`make dist && make distcheck` → 0; Clang `-fsyntax-only` → 0. User smoke
passed (`artifacts/user-smoke/result.json` start/check 0). Review verdict
`pass` with 0 High/Critical, 5 Medium (F1–F5), 5 Low (F6–F10). Closeout
handoff recorded; next is repair F1–F5. Do not claim `.deb`/`.rpm`,
commit-identical dirty-tree archives, `make quality`, or release closure.
Prior run `b54d61531266` (`source-release` naming) is superseded by this
`dist`/`distcheck` workflow.

## Deterministic sysdiff Performance Benchmarks

Governed run `a0eda97cd039` delivered the Linux performance/resource harness
(`scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`,
`make benchmark`, README section, committed
`artifacts/performance/sysdiff-benchmark.json`). Exact evidence:
`startup_ms_median` 1.2422580039128661 <= 200.0;
`fixture_ms_median` 7.362931006355211 <= 100.0;
`peak_rss_kib` 2540.0 <= 32768.0; `baseline_ms_median` 1.3354689872357994;
8000-entry fixture; `passed: true`. Exact verification: pytest 25 passed in
1.73 s (repair) / 1.62 s (review); `make -n benchmark` → 0; harness
`--output` → 0. User smoke passed (`artifacts/user-smoke/result.json`
start/check 0). Review verdict `pass` with 0 High/Critical/Medium, 9 Low
(B1–B9). Closeout handoff recorded; optional Low B1–B9 polish remains. Do
not claim microbenchmarks, cross-host bit-stable timings, `make quality`, or
release closure.

## Deterministic Malformed-Snapshot Fuzz Regression Coverage

Governed run `feb8e707ea28` delivered the deterministic malformed-snapshot fuzz
regression contract and pytest corpus (`docs/malformed-snapshot-fuzz-regression-
contract.md`, `tests/test_sysdiff_malformed_fuzz.py`). Exact verification:
`python3 -m pytest tests/test_sysdiff_malformed_fuzz.py -q` → 40 passed in
0.18 s (impl) / 0.19 s (review); `clang -std=c17 -Wall -Wextra -Wpedantic
-Werror -fsyntax-only src/sysdiff.c` → exit 0. User smoke passed
(`artifacts/user-smoke/result.json` start/check 0). Review verdict `pass` at
High with 0 High/Critical, 4 Medium (F1–F4), 3 Low (F5–F7). Finish closeout,
then repair F1–F4; do not claim open-ended fuzzing, sanitizer product readiness,
or release closure from this slice.

## Current sprint

- [x] Governed run `c9e3de33f46b` closed pathaudit Low `PA-W1` (command-
  bounded `symlink_is_self_basename` `readlink` storage) under independent
  verdict `pass`. Exact evidence: focused 156/15; `make quality` 359/15
  ordinary/ASan/UBSan/Valgrind each; smoke start/check 0 with check.log
  356/18. Remaining Medium `PAW1-DOC-901` and Lows `PAW1-DOC-902`/
  `PAW1-TEST-903`/`PAW1-TEST-904`/`PAW1-SCOPE-905`. Not a pathaudit
  release, install, package, tag, or publication.
- [ ] Keep `PAW1-DOC-901` and the four new Lows visible. Do not invent
  release readiness or optional polish from this maintenance closeout.
  Preserve planning order: `inodealias` → `shebangcheck` → `openunlink`
  (still gated on `SIXTH2-M1`–`M3`) ahead of any seventh-utility CODE.
- [x] Bounded recovery `4824cd763b27` reconciled and High-threshold-reviewed
  the `sparsemap` seventh-mission evaluation left by failed origin
  `f7539c314ca1`. Fresh verdict `pass` with Medium `SEV7R-M1`/`SEV7R-M2`
  and Low `SEV7R-L1`/`SEV7R-L2` retained. Origin remains Failed; timeouts
  `0`/`124`/`124` stay distinct from this recovery. Not an
  implementation, install, package, tag, publication, or release of
  `sparsemap`.
- [ ] Keep `SEV7R-M1`/`SEV7R-M2`/`SEV7R-L1`/`SEV7R-L2` visible. Do not
  silently authorize `sparsemap` CODE.
- [x] Deliver, validate, smoke-gate, and independently review the `permguard`
  bootstrap in run `51100a584ac9`,
  `bootstrap_permguard_first_vertical_slice`, under
  `docs/permguard-bootstrap-contract.md` (four-code
  `GROUP_WRITABLE`/`OTHER_WRITABLE`/`SET_USER_ID`/`SET_GROUP_ID` taxonomy;
  symlink rejection; streaming continue-after-error). Review allowlisted
  focused pytest: 52 passed / 0 skipped in 0.43s. Step-5 validation: full
  332 passed / 18 skipped plus static gates and ASan/Valgrind `--help`
  probes. Smoke: start/check 0, empty blockers, check.log 332 passed / 18
  skipped. Verdict `pass` with Medium PG-DOC-501/502, PG-TEST-503,
  PG-PORT-505, PG-DOC-512 and Low PG-CRAFT-506, PG-TEST-507, PG-CLI-508,
  PG-MAKE-509/510/511. Not installed, packaged, released, recursive, or
  remedial.
- [x] Recovery run `5035933ac7b4` closed Medium PG-DOC-501/502,
  PG-TEST-503, PG-PORT-505, and PG-DOC-512 under independent verdict
  `pass` without claiming failed origin `ba6dc2fdd199` passed. Exact
  evidence: focused pytest 63/0; `make quality` exit 0 with
  354/15 ordinary/ASan/Valgrind each; smoke start/check 0 with check.log
  351/18. Remaining Low PGR-TEST-706/PGR-PORT-707/PGR-BUILD-708/
  PGR-TEST-709/PGR-DOC-710 plus bootstrap Lows stay visible.
- [ ] Next executable action for earlier planning missions: generate a
  separate governed `shebangcheck` implementation playbook beginning with
  its normative contract (or clear `openunlink` Medium debt first under
  the live repair-before-expansion gate), then fixtures, source,
  documentation, dedicated smoke, quality evidence, and independent
  review. Keep recovery Lows, bootstrap Lows, pathaudit Medium PA-6CA-4
  and Lows, FUM5 Mediums/Lows, seventh-mission `SEV7R-*` findings, and
  other prior Medium/Low backlogs visible. Do not claim permguard
  released or `sparsemap` implemented.
- [x] Prior one-code cycle: run `f742c10135e5` under
  `docs/permguard-first-vertical-slice-contract.md` (67 focused passed;
  Medium PG-REV-301/302). Superseded as product authority by `51100a584ac9`.
- [x] Prior live-slice cycle: run `629d1f459446` repaired High PG-DOC-101 and
  passed review with Medium PG-REV-201 and Low PG-REV-202–207. Superseded by
  later cycles.
- [x] Historical: deliver and review earlier four-code `permguard` bootstrap
  in run `a8341dfae9f2` (verdict `pass` with PG-DOC-001/PG-TEST-002 Mediums).
  Historical relative to the restored live bootstrap authority in
  `51100a584ac9`.
- [x] Record reviewed Future Mission Discovery selection: pathaudit v1
  capability-complete; chosen mission bootstrap `permguard`; first
  vertical slice explicit-root permission scanner; review verdict
  `pass` with Low `permguard-writability-overlap` and
  `first-slice-scope-breadth`; plan-evidence checks only. Not an
  implementation or release of any utility.
- [x] Superseded selection action: bootstrap `permguard` contract,
  `src/permguard.c`, `man/permguard.1`, `tests/test_permguard.py`, and
  Makefile wiring. Completed by current run `51100a584ac9` after prior
  one-code run `f742c10135e5`, single-code run `629d1f459446`, and
  historical four-code run `a8341dfae9f2`; Medium PG-DOC-501/502,
  PG-TEST-503, PG-PORT-505, PG-DOC-512 were later closed by recovery
  `5035933ac7b4` without claiming failed origin `ba6dc2fdd199` passed.
  Evaluation Lows and prior pathaudit/sysdiff backlogs remain visible and
  were not closed.
- [x] Deliver, smoke-test, independently review, and close out
  Detect unsafe ownership of PATH directories for `pathaudit --path` /
  `--command` in run `50c0b4936d50`,
  `template_repair_before_review_feature_delivery`. Exact evidence:
  step-2 `make clean && make` exit 0; full pytest 280 passed / 18
  skipped in 26.84s; smoke start/check 0 with empty `blocking_errors`
  (check.log pytest `280 passed, 18 skipped in 20.40s`); review
  verdict `pass` with 0 Critical/High/Medium and 1 Low
  (`path-dir-ownership-1`); allowlisted pathaudit pytest → 143 passed,
  15 skipped. Not a pathaudit release; sysdiff smoke oracle does not
  directly exercise directory-ownership `--path` / `--command`
  detection.
- [x] Historical next-after-`50c0b4936d50` preference (Detect writable
  ancestors of PATH directories) is superseded by reviewed Future Mission
  Discovery: writable-ancestor is deferred out of pathaudit v1 scope;
  suite next mission is `permguard` bootstrap. Keep Low
  `path-dir-ownership-1` and prior Medium/Low backlogs visible as
  ordinary repair; Medium pathaudit-shadow-1 and Low pathaudit-shadow-2/3
  were later closed by recovery `4ae7a820b0a3` without claiming other
  findings closed.
- [x] Deliver, smoke-test, independently review, and close out
  Detect executables with unsafe ownership for `pathaudit --path` /
  `--command` in run `1d5eedc01202`,
  `template_repair_before_review_feature_delivery`. Exact evidence:
  step-4 `make quality` exit 0; Clang `-fsyntax-only` exit 0;
  cppcheck exit 0; full pytest 271 passed / 14 skipped in 19.02s;
  smoke start/check 0 with empty `blocking_errors` (check.log pytest
  `271 passed, 14 skipped in 19.94s`); review verdict `pass` with 0
  Critical/High/Medium/Low formal findings; allowlisted full pytest →
  271 passed, 14 skipped. Not a pathaudit release; sysdiff smoke
  oracle does not directly exercise an ownership-specific `--path` /
  `--command` user flow.
- [x] Deliver, smoke-test, independently review, and close out
  Detect writable resolved-executables through PATH for `pathaudit
  --path` / `--command` in run `574d06adfc2a`,
  `template_repair_before_review_feature_delivery`. Exact evidence:
  step-3 Clang `-fsyntax-only` exit 0; full pytest 269 passed / 1
  skipped; smoke start/check 0 with empty `blocking_errors` (check.log
  pytest `269 passed, 1 skipped in 18.74s`); review verdict `pass`
  with 0 Critical/High/Medium and 2 Low (PA-W1, PA-W2); allowlisted
  full pytest → 269 passed, 1 skipped. Not a pathaudit release;
  sysdiff smoke oracle does not directly exercise writable-executable
  `--path` / `--command` detection.
- [x] Keep Low PA-W1 from `574d06adfc2a` closed by later run `c9e3de33f46b`
  (fresh independent review); retain historical Low PA-W1 as prior evidence
  only. Keep Low PA-W2 visible for optional polish unless a later review
  explicitly closes it; keep Medium `PAW1-DOC-901` and Lows
  `PAW1-DOC-902`/`PAW1-TEST-903`/`PAW1-TEST-904`/`PAW1-SCOPE-905` visible.
  Do not claim that `pathaudit` is released or that `tests/smoke_manifest.json`
  covers writable-executable `--path` / `--command` behavior.
- [x] Deliver, smoke-test, independently review, and close out
  Detect executable shadowing across PATH entries for `pathaudit
  --path` in run `f94509b47fd3`,
  `template_repair_before_review_feature_delivery`. Exact evidence:
  step-4 GCC/Clang `-fsyntax-only` exit 0; full pytest 247 passed / 1
  skipped; smoke start/check 0 with empty `blocking_errors` (check.log
  pytest `247 passed, 1 skipped in 18.41s`); review verdict `pass`
  with 0 Critical/High, 1 Medium (pathaudit-shadow-1), and 2 Low
  (pathaudit-shadow-2, pathaudit-shadow-3); allowlisted full pytest →
  247 passed, 1 skipped. Not a pathaudit release; sysdiff smoke oracle
  does not directly exercise executable-shadowing `--path` detection.
- [x] Keep Medium pathaudit-shadow-1 and Low pathaudit-shadow-2/3 from
  `f94509b47fd3` closed by later recovery `4ae7a820b0a3` (fresh
  independent review); retain the historical Medium/Low record as prior
  evidence only. Keep recovery findings Medium PA-6CA-4 and Low
  PA-6CA-1/2/3 visible. Do not claim that `pathaudit` is released or that
  `tests/smoke_manifest.json` covers shadowing `--path` behavior.
- [x] Deliver, smoke-test, independently review, and close out
  Detect non-directory PATH entries for `pathaudit --path` / explicit
  roots in run `35116f657f35`, `detect_non_directory_path_entries`.
  Exact evidence: step-3 Clang `-fsyntax-only` + cppcheck exit 0; full
  pytest 234 passed / 1 skipped; smoke start/check 0 with empty
  `blocking_errors` (check.log pytest `234 passed, 1 skipped in
  19.50s`); review verdict `pass` with 0 Critical/High/Medium and 2
  Low (nondir-1, nondir-2); allowlisted pathaudit pytest → 94 passed,
  1 skipped. Runtime `NON_DIRECTORY_ROOT` logic pre-existed; slice
  documents and pins it. Not a pathaudit release; sysdiff smoke oracle
  does not directly exercise non-directory `--path` detection.
- [ ] Keep Low nondir-1/2 from `35116f657f35` visible for optional
  polish unless a later review explicitly closes them; do not claim
  that `pathaudit` is released or that `tests/smoke_manifest.json`
  covers non-directory `--path` behavior.
- [x] Deliver, smoke-test, independently review, and close out
  command-specific PATH risk inspection for `pathaudit --command NAME`
  in run `2b2fb272c21a`,
  `template_repair_before_review_feature_delivery`. Exact evidence:
  step-4 `make clean && make test` → 230 passed, 1 skipped; full pytest
  230 passed / 1 skipped; format/tidy/cppcheck/analyzer/man-check +
  `pathaudit-sanitize`/`pathaudit-valgrind` exit 0; pathaudit pytest
  90 passed / 1 skipped; smoke start/check 0 with empty
  `blocking_errors` (check.log pytest `230 passed, 1 skipped in
  18.98s`); review verdict `pass` with 0 Critical/High/Medium and 2
  Low (pathaudit-cmd-1, pathaudit-cmd-2); allowlisted full pytest →
  230 passed, 1 skipped. Not a pathaudit release; sysdiff smoke oracle
  does not directly exercise `--command`.
- [ ] Keep Low pathaudit-cmd-1/2 from `2b2fb272c21a` visible for
  optional polish unless a later review explicitly closes them; do not
  claim that `pathaudit` is released or that `tests/smoke_manifest.json`
  covers `--command` behavior.
- [x] Deliver, smoke-test, independently review, and close out
  working-directory-dependent PATH detection for `pathaudit --path` in
  run `79a1cc2bac7a`,
  `pathaudit_working_directory_dependent_path_entries`. Exact evidence:
  step-4 GCC/Clang `-fsyntax-only` + cppcheck exit 0; pathaudit pytest
  62 passed / 1 skipped (3.87s); full pytest 202 passed / 1 skipped
  (22.46s); smoke start/check 0 with empty `blocking_errors` (check.log
  pytest `202 passed, 1 skipped in 18.42s`); review verdict `pass` with
  0 Critical/High/Medium and 2 Low (pathaudit-wdp-1, pathaudit-wdp-2);
  allowlisted pathaudit pytest → 62 passed, 1 skipped; full pytest →
  202 passed, 1 skipped. Not a pathaudit release; sysdiff smoke oracle
  does not directly exercise cwd-dependent `--path` detection.
- [ ] Keep Low pathaudit-wdp-1/2 from `79a1cc2bac7a` visible for
  optional polish unless a later review explicitly closes them; do not
  claim that `pathaudit` is released or that `tests/smoke_manifest.json`
  covers cwd-dependent `--path` behavior.
- [x] Deliver, smoke-test, independently review, and close out additive
  `pathaudit --path` (writable PATH directories) in run `d27d2ade171f`,
  `pathaudit_detect_writable_path_directories`. Exact evidence: step-5
  `make clean && make test` → 196 passed, 1 skipped; format/tidy/
  cppcheck/analyzer + `pathaudit-sanitize`/`pathaudit-valgrind` exit 0;
  ASan+UBSan pathaudit 56 passed, 1 skipped; smoke start/check 0 with
  empty `blocking_errors` (check.log pytest `196 passed, 1 skipped in
  18.33s`); review verdict `pass` with 0 Critical/High/Medium and 4 Low
  (PA-WP-1–PA-WP-4); allowlisted pytest → 56 passed, 1 skipped. Not a
  pathaudit release; sysdiff smoke oracle does not directly exercise
  `--path`.
- [ ] Keep Low PA-WP-1–PA-WP-4 from `d27d2ade171f` visible for optional
  polish unless a later review explicitly closes them; do not claim that
  `pathaudit` is released or that `tests/smoke_manifest.json` covers
  `--path`.
- [x] Deliver, smoke-test, independently review, and close out the additive
  `pathaudit` 0.1.0 vertical slice in run `4dec475ef201`,
  `pathaudit_bootstrap_deterministic_scanner`. Deliverables:
  `docs/pathaudit-contract.md`, `src/pathaudit.c`, `man/pathaudit.1`,
  `tests/test_pathaudit.py` (26 passed), Makefile quality/sanitizer/
  Valgrind wiring, README/QUALITY/TESTING docs. Exact evidence: step-3
  pathaudit pytest 26/0.38s; full pytest 158/14.98s; GCC/Clang strict
  syntax + format/tidy/cppcheck/analyzer + ASan/Valgrind help probes
  exit 0; smoke start/check 0 with empty `blocking_errors` (check.log
  pytest `158 passed in 12.88s`); review verdict `pass` with 0
  Critical/High, 2 Medium (PA-M1, PA-M2), 7 Low (PA-L1–PA-L7). Not a
  pathaudit release; sysdiff smoke oracle does not directly exercise
  pathaudit.
- [ ] Keep bootstrap Medium PA-M2 / PA-M1 leftovers and Low PA-L1–PA-L7
  visible after `4dec475ef201` unless a later review explicitly closes
  them; do not claim that `pathaudit` is released or that
  `tests/smoke_manifest.json` covers pathaudit.
- [x] Prepare, verify, smoke-test, and independently review the unpublished
  `sysdiff` **0.1.0** release candidate in run `580b0f6ff811`,
  `prepare_sysdiff_release_package_and_notes`. Archive
  `sysdiff-release.tar.gz` + checksum `sysdiff-release.tar.gz.sha256`
  (digest
  `9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f`);
  RC-001 pass; clean extract 121 passed / 7 skipped; smoke start/check 0
  with empty `blocking_errors` (check.log pytest `128 passed in 10.64s`);
  review verdict `pass` with 0 Critical/High and 1 Low (L1). H1 packaging
  guard repaired between review attempts. This is a prepared but
  **unpublished** candidate—not a published release.
- [ ] Keep Lee-controlled release authorization as the gate for any
  external `sysdiff` publication or tag push; keep Low L1 visible; do not
  modify release-package inputs after the reviewed archive; prior Medium
  backlogs remain open. Do not claim that `sysdiff` is released.
- [x] Deliver and record the first independent `sysdiff` release-candidate
  review in run `6d0a6fbfe83d`,
  `template_repair_before_review_feature_delivery`. Exact smoke start/check 0
  with empty `blocking_errors` (check.log pytest `127 passed in 10.75s`);
  review check `python3 -m pytest -p no:cacheprovider tests/ -q` → 127 passed
  in 10.89 s at HEAD `510fa2d`; verdict `pass` with 0 Medium/High/Critical
  and 10 Low (L1–L10). Step-2 attempt 1 failed on Medium M1; attempt 2 passed.
  This is the first clean review in the required consecutive sequence only—
  not a release, not mission completion.
- [ ] Keep Low findings L1–L10 visible after run `6d0a6fbfe83d`; do not treat
  them as blocking. Consecutive clean RC counter for this required sequence
  is 1; a second consecutive clean independent RC review remains outstanding.
  Do not claim that `sysdiff` is released without Lee-controlled release
  authorization. Prior Medium-or-higher backlogs remain open and continue to
  prohibit new feature work while that debt remains.
- [x] Run a prior second independent release-candidate review cycle in run
  `c84986cf0c81`,
  `sysdiff_second_independent_release_candidate_review_cycle`. Exact smoke
  start/check 0 with empty `blocking_errors` (check.log pytest
  `127 passed in 10.84s`); review check
  `python3 -m pytest -p no:cacheprovider tests/ -q` → 127 passed in 10.96 s;
  verdict `pass` under Medium with 0 Medium/High/Critical and 9 Low (L1–L9);
  RC-001 strcasecmp-mutant kill re-verified. Historical relative to the
  current mission sequence; not a publication or Lee-authorized release claim.
- [ ] Keep historical Low findings L1–L9 from `c84986cf0c81` visible; do not
  treat them as blocking. Do not claim that `sysdiff` is released without
  Lee-controlled release authorization.
- [x] Deliver and record a prior first independent release-candidate review
  cycle in run `8a3470eff7d3`,
  `sysdiff_first_independent_rc_review_cycle`. Closed mixed-case ordering
  gap (RC-001) in tests/fixtures; exact smoke start/check 0 with empty
  `blocking_errors` (check.log pytest `127 passed in 10.58s`); review
  check `python3 -m pytest tests/ -q` → 127 passed in 11.06 s; verdict
  `pass` with 0 Medium/High/Critical and 7 Low (F1–F7). Historical relative
  to run `6d0a6fbfe83d`'s required sequence.
- [x] Keep Low findings F1–F7 visible after the prior first independent RC
  review cycle; do not treat them as blocking. Do not claim that `sysdiff`
  is released.
- [x] Deliver and record the first consecutive clean release-blocking
  independent review in run `7eb4e29dee6e`,
  `complete_first_consecutive_release_blocking_independent_review`. Exact
  smoke: start/check 0, no blocking errors. Exact full suite:
  `python3 -m pytest tests/ -q` → 124 passed in 10.71 s. Review verdict
  `pass` with 0 Medium/High/Critical and 5 Low (L-1–L-5). This is the
  first consecutive clean review only—not a second clean review, not
  mission completion, and not release readiness.
- [ ] Keep Low findings L-1–L-5 visible after the first consecutive clean
  review; do not treat them as blocking. A second consecutive clean
  release-blocking independent review has not been claimed or completed.
- [x] Deliver and review isolated source-archive verification in run
  `939ee21b0d76`, `verify_reproducible_source_archive_isolated_build`.
  Report `docs/reproducible-source-archive-isolated-build.md` records
  byte-identical archives (SHA-256
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`,
  89851 bytes, 44 members) and extracted-tree quality gates exit 0
  (including ASan/UBSan/Valgrind). User smoke passed; review verdict
  `pass` with 0 High/Critical, 5 Medium (F1–F5), and 4 Low (F6–F9).
- [x] Finish closeout for run `939ee21b0d76`. Recorded exact archive
  hashes, quality results, pytest provisioning recovery, smoke
  start/check 0, independent review `pass` with Medium F1–F5 still open,
  and that this is isolated verification evidence—not a `.deb`/`.rpm`,
  not commit-identical dirty-tree provenance, and not full release
  readiness.
- [ ] Repair isolated-archive / source-release Medium findings F1–F5 from
  `review-reproducible-source-archive-isolated-build.verdict.json`:
  clean-tree or committed-object packaging plus honest provenance; name
  (or split) the six git-gated `test_dist_*` skips in extracts; make
  `dist`/`distcheck` usable or honestly unavailable from the tarball; add
  `dist/` to `.gitignore`; allowlist user-facing docs instead of shipping
  all of `docs/`. Consider Low F6–F9 afterward. Prefer this Medium
  backlog next. Overlaps prior `240bfcbc634e` packaging Medium themes.
- [x] Deliver and review reproducible sysdiff source release in run
  `240bfcbc634e`, `build_verify_reproducible_sysdiff_source_release`. Added
  Makefile `dist` / `distcheck`, six `test_dist_*` regressions, README
  "Source releases", and artifacts `dist/sysdiff-source.tar.gz` +
  `dist/sysdiff-source.tar.gz.sha256` (digest
  `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a`).
  Implementation validation and user smoke passed; review verdict `pass`
  with 0 High/Critical, 5 Medium (F1–F5), and 5 Low (F6–F10).
- [x] Finish closeout for run `240bfcbc634e`. Recorded exact artifact/
  checksum paths, verification (`make dist && make distcheck`, pytest 38
  passed, smoke start/check 0), independent review `pass` with Medium
  F1–F5 still open, and that this is a bounded source-archive
  workflow—not a `.deb`/`.rpm`, not a fresh `make quality`, and not full
  release readiness.
- [x] Deliver and review deterministic sysdiff performance benchmarks in run
  `a0eda97cd039`, `sysdiff_deterministic_performance_benchmarks`. Added
  `scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`, Makefile
  `benchmark`, README "Performance Benchmarks", and
  `artifacts/performance/sysdiff-benchmark.json` (`passed: true`; thresholds
  startup 200.0 ms / fixture 100.0 ms / peak RSS 32768 KiB; measured
  ~1.24 ms / ~7.36 ms / 2540 KiB; baseline ~1.34 ms; 8000-entry fixture).
  Repair closed prior Medium B1/B2; implementation validation and user smoke
  passed; review verdict `pass` with 0 High/Critical/Medium and 9 Low
  (B1–B9).
- [x] Finish closeout for run `a0eda97cd039`. Recorded exact JSON
  measurements/thresholds, verification (pytest 25 passed, `make -n
  benchmark`, harness `--output`, smoke start/check 0), independent review
  `pass` with Low B1–B9 only, remaining host/scheduler/RSS variability, and
  that this is a conservative release guardrail—not a microbenchmark, not a
  fresh `make quality`, and not full release readiness.
- [ ] Optionally polish performance-benchmark Low findings B1–B9 (exit-status
  short-circuit in RSS fallback; `--output` test; tighter or relabeled
  startup gate; real build-isolation test; VmHWM race; `/bin/true`
  preflight; drop dead global; threshold-map extensibility; hard-fail if
  harness script missing). Non-blocking.
- [x] Deliver and review earlier source-release naming slice in run
  `b54d61531266`, `sysdiff_reproducible_source_release` (`source-release` /
  `source-release-verify`). Superseded by `240bfcbc634e` `dist`/`distcheck`.
- [x] Finish closeout for run `b54d61531266` (historical; current packaging
  surface is `make dist` / `make distcheck` from `240bfcbc634e`).
- [x] Bootstrap a smokeable `sysdiff` workspace for auto-orch Author grounding.
- [x] Embed AgentFlow and Agent-Orch onboarding scaffold.
- [x] Run Agent-Orch doctor and resolve readiness findings.
- [ ] Finish closeout validation for Agent-Orch run `fa24bb888cc0` before
  installing hourly cron. Handoff docs record the completed snapshot-format
  contract, user smoke pass, review pass verdict, open findings, and next
  implementation step, but the Agent-Orch run ended `FAILED` at closeout due
  to the missing read-only judge adapter for `claude_code`.
- [x] Define and review the `sysdiff` snapshot-format and initial-scope
  contract for explicit `key=value` snapshot comparison.
- [ ] Resolve or encode snapshot-contract review findings F-001 through F-004.
- [x] Expand `sysdiff` with the smallest useful fixture-backed comparison slice
  against `docs/sysdiff-snapshot-format-and-scope.md`.
- [ ] Finish closeout validation for Agent-Orch run `3a9e56296af6`. Handoff
  docs record the minimal C quality-gate harness result, smoke pass, review
  pass verdict, and open findings F-01 through F-03; leave this open until
  Agent-Orch records the closeout step as passed.
- [ ] Resolve minimal C harness review finding F-01 where still relevant. The
  changed-line ambiguity for values containing ` -> ` remains open; later
  slices reworked sanitizer/target concerns and should be reconciled against
  their original verdicts only as historical context.
- [x] Deliver and review the sysdiff core parser/comparer slice. Resumed run
  `b14e0191e257` inherited implementation from `aa1eaef577cd`, passed the
  user smoke gate, and received a `pass` verdict at the High-severity threshold
  in `code-reviews/review-sysdiff-core.verdict.json`.
- [ ] Finish closeout validation for Agent-Orch run `b14e0191e257`. Handoff
  docs recorded the implemented core behavior, smoke evidence, review pass
  verdict, and open findings F001 through F004; leave this open until
  Agent-Orch records the closeout step as passed.
- [x] Resolve the implementation side of sysdiff core F001 by adding
  deterministic line-length and entry-count limits in run `c02d741432d3`.
- [x] Deliver fixture acceptance coverage for CRLF equivalence and
  line/entry resource-limit failures in run `eab8bbd05f50`. The latest
  fixture-acceptance review confirms those paths are exercised by
  `tests/test_sysdiff_fixture.sh` (entry-limit skipped under Valgrind for
  runtime).
- [x] Resolve the latest C-source memory-ownership and sanitizer availability
  concerns: `parse_snapshot` now uses explicit centralized cleanup, and
  `make sanitizer-test` provides ASan/UBSan coverage when `clang` is present.
- [x] Deliver and review the routed tool-availability preflight. Run
  `b6deb04a6055`, `add-routed-tool-availability-check`, added
  `scripts/check_tools.py`, `tests/test_check_tools.py`, contract/plan/docs,
  and README discoverability for checking the default `codex_cli` and
  `claude_code` harness executables before governed work depends on those
  routes.
- [ ] Finish closeout validation for Agent-Orch run `b6deb04a6055`. Handoff
  docs record the implemented preflight behavior, review pass verdict,
  `flake8` environment limitation, and open Low findings F001 and F002; leave
  this open until Agent-Orch records the closeout step as passed.
- [ ] Resolve tool-availability review findings F001 and F002: guard or
  type-enforce available results before `_print_success` formats executable
  paths, and add explicit empty-stdout assertions to both per-harness
  partial-failure tests.
- [x] Deliver and review Agent-Orch run `1a9f7726ff33`,
  `fix_smoke_manifest_and_rebuild_fixture_tests`. Step 1 fixed
  `tests/smoke_manifest.json` and `tests/test_sysdiff_fixture.sh`; governed
  smoke passed on `step_02_run_smoke_gate` attempt 2 after attempt 1 retried for
  out-of-step AgentFlow doc edits; review verdict
  `code-reviews/review-smoke-fixture-fix.verdict.json` reports `pass` with no
  High or Critical findings.
- [x] Record closeout failure for Agent-Orch run `1a9f7726ff33`. Closeout
  attempts selected unavailable or inaccessible GPT-5.4 routing for semantic
  validation, so the run ended `FAILED` at `step_04_closeout_handoff_docs` and
  was superseded by follow-up run `5ff82aa95e06`. Future OpenAI/Codex routes
  should use `gpt-5.5`.
- [x] Resolve smoke-fixture review findings F-001 and F-002. Follow-up run
  `5ff82aa95e06` replaced the primary sorted diff comparison with an exact
  order-preserving comparison and strengthened `assert_diff_prefixes` to
  validate full diff line shapes.
- [x] Deliver, review, and close out Agent-Orch run `5ff82aa95e06`,
  `sysdiff_fixture_smoke_repair`. The user smoke gate passed on attempt 1 with
  four manifest steps completed; review verdict
  `code-reviews/review-fixture-smoke-repair.verdict.json` reports `pass` with
  no findings; closeout evidence records `COMPLETED`.
- [x] Deliver and review Agent-Orch run `c02d741432d3`,
  `sysdiff_c_source_implementation`. The run added the C-source contract and
  plan, implemented deterministic resource limits and explicit parse cleanup,
  added Makefile quality targets, documented user-visible limits, passed smoke,
  and received a `pass` verdict at the High threshold in
  `code-reviews/review-sysdiff-c-source.verdict.json`.
- [x] Finish closeout validation for Agent-Orch run `c02d741432d3`. Attempt 1
  of `step_09_closeout_handoff_docs` retried because the handoff did not match
  the current review verdict; attempt 2 preserved the current verdict details
  and Agent-Orch now records the run as `COMPLETED`.
- [x] Complete a C craftsmanship review before selecting additional sysdiff
  feature work. Agent-Orch run `c434e00a3772` wrote
  `code-reviews/craftsmanship-review.md` and
  `code-reviews/craftsmanship-review.verdict.json`; the verdict is `pass` at
  the High/Critical threshold with no High or Critical findings.
- [x] Add the Makefile `check` alias required by the quality-gate surface.
  `Makefile` now includes `check` in `.PHONY`, and `check` delegates to
  `test-suite`; `code-reviews/review-makefile-quality-gates.verdict.json`
  passed this narrow repair at the High threshold.
- [x] Deliver and review Agent-Orch run `eab8bbd05f50`,
  `sysdiff_fixture_diff_acceptance_tests`. Authored fixture acceptance tests,
  verified fixture compare behavior, passed its then-current user smoke (whose
  start helper timed out), and received a `pass`
  verdict at the High threshold in
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`.
- [x] Finish closeout validation for Agent-Orch run `eab8bbd05f50`; Agent-Orch
  records the run as `COMPLETED`.
- [x] Resolve fixture-acceptance review F001 by making the pytest `sysdiff_bin`
  fixture portable instead of hardcoding `gcc`; prefer `$CC`, `cc`, or
  `clang`, keeping the same strict C17 warning flags.
- [x] Resolve fixture-acceptance review F002 by making `tests/smoke_start.py`
  exit immediately with status 0, or by keeping any intentional delay strictly
  below `tests/smoke_manifest.json`'s 10-second `startup_timeout_seconds`.
- [x] Resolve fixture-acceptance review F003 by treating whitespace-only
  lines as blank (ignore them) to match the fixture-slice contract, or updating
  the contract and README to state that whitespace-only lines are parse errors.
- [x] Resolve fixture-acceptance review F004 by removing the unreachable
  `copy_range` `SIZE_MAX` guard or replacing it with a comment/static assertion
  that documents the call-site bound.
- [x] Confirm `argc < 1` guard is present in `main` before `argv[1]` access
  (noted by the fixture-acceptance review; supersedes craftsmanship F005 as
  current evidence).
- [x] Confirm standalone `make valgrind-test` cleans and rebuilds before
  Valgrind (noted by the fixture-acceptance review; supersedes the earlier
  Makefile/C-source Valgrind-after-sanitizer Medium as current evidence).
- [x] Prepare and verify the `sysdiff` v0.1.0 public release candidate: fresh
  Linux `make quality` pass, CI, curated release docs, and release review.
- [x] Perform an adversarial last-stop release audit; reject the first candidate
  and repair all five Medium findings with Cursor `grok-4.5-high` under
  independent planner review.
- [x] Add terminal-safe rendering, checked stdout/EPIPE behavior, a 16 MiB
  aggregate snapshot limit, honest Valgrind/cppcheck gates, leak-enabled ASan,
  immutable CI action pinning, and regression coverage.
- [x] Create `leebase/linux-utilities`, push the clean seed, repair the stalled
  hosted install, upgrade checkout to immutable v6, and obtain a zero-annotation
  successful Ubuntu `make quality` run (`29119972847`).
- [x] Add and review `man/sysdiff.1`, integrate warning-gated groff rendering
  into `make quality`/Ubuntu CI, reconcile public docs, and pass the governed
  quality gate with 41 tests.
- [x] Complete the sysdiff release documentation set
- [x] Implement deterministic ASan, UBSan, and Valgrind regression targets in
  run `5665167f1c1d`; implementation validation passed both memory gates and
  the independent review verdict passed at the High threshold with no
  High/Critical findings.
- [ ] Finish closeout for run `5665167f1c1d`. Preserve the distinction between
  fresh governed smoke (`artifacts/user-smoke/result.json`) and review finding
  F1's stale legacy `.agent-orch/user-smoke/result.json`; do not claim a fresh
  release or full quality gate from this slice.
- [ ] Repair deterministic-memory-gate Medium findings F1-F4: refresh legacy
  smoke pins, declare the POSIX `SIGPIPE` dependency portably, route
  `/dev/full` and closed-pipe fixture helpers through Valgrind, and add
  negative controls that prove ASan/UBSan/Valgrind fail on injected defects.
- [ ] Consider the six Low findings from
  `review-deterministic-memory-gates.verdict.json` after the Medium repair;
  retain explicit Linux/Clang/GCC/Valgrind host prerequisites and loud
  preflight failures.
- [x] Deliver and review reproducible install/uninstall packaging checks in
  run `a2d750c92da3`, `sysdiff_reproducible_install_uninstall_packaging_checks`.
  Added Makefile `install`/`uninstall` with `DESTDIR`/`prefix` path variables,
  shell packaging assertions (exact manifest, modes, installed behavior,
  reinstall, uninstall), and README installation docs. Implementation
  validation and user smoke passed; review verdict `pass` with 0 High/Critical,
  1 Medium (F1), and 6 Low (F2–F7) findings.
- [ ] Finish closeout for run `a2d750c92da3`. Record smoke
  (`artifacts/user-smoke/result.json` start/check 0, no blocking errors) and
  that smoke covers fixtures while packaging is covered by `make test`/shell.
  Do not claim a release, complete packaging, or a zero-finding clean review.
- [ ] Repair packaging-slice Medium F1: guard or extract the packaging block so
  sanitizer/Valgrind gates do not ignore `SYSDIFF_BIN` and re-run uninstrumented
  staged install three extra times; optionally address Low F2–F7 afterward.
- [x] Deliver and review deterministic malformed-snapshot fuzz regression
  coverage in run `feb8e707ea28`. Added
  `docs/malformed-snapshot-fuzz-regression-contract.md` and
  `tests/test_sysdiff_malformed_fuzz.py`; no `src/sysdiff.c` edits required.
  Implementation validation and user smoke passed; review verdict `pass` with
  0 High/Critical, 4 Medium (F1–F4), and 3 Low (F5–F7) findings.
- [ ] Finish closeout for run `feb8e707ea28`. Record exact commands
  (`pytest …malformed_fuzz.py -q` → 40 passed; Clang `-fsyntax-only` → 0),
  smoke (`artifacts/user-smoke/result.json` start/check 0), and that this is a
  bounded deterministic corpus—not open-ended fuzzing, not a fresh sanitizer
  gate, and not a release.
- [ ] Repair malformed-fuzz Medium findings F1–F4: add a 16 MiB total-byte
  over-limit case; make the LINE_TOO_LONG case actually hit `read_line`'s
  guard; add a positive-control compare; honor `SYSDIFF_UNDER_VALGRIND` with
  scaled timeouts. Consider Low F5–F7 afterward.

## Complete the sysdiff release documentation set

Governed run `e7bbd28465b5` delivered the required root release documentation
(HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, STATUS), reconciled README,
CHANGELOG, architecture, and `man/sysdiff.1`, passed the pinned user smoke
gate on attempt 1 (`start_exit_code`/`check_exit_code` 0, no blocking errors),
and received review verdict `pass` in
`code-reviews/sysdiff-release-documentation-review.verdict.json`. Open follow-ups
are Low only: man-page NAME whatis separator (F1) and FILES directory
open-vs-read wording (F2). Do not treat this docs cycle as a fresh
`make quality` product gate; prior release evidence still stands separately.
