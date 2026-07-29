# Result Review

## Bootstrap permguard

Objective: deliver and independently review the `permguard` bootstrap as a
small ISO C17 read-only explicit-path scanner without recursion, PATH lookup,
remediation, install/package wiring, or any release claim. Governed run
`51100a584ac9` (`bootstrap_permguard_first_vertical_slice`) is the authoritative
cycle for live contract `docs/permguard-bootstrap-contract.md`: classify each
named object's own mode bits into the closed four-code taxonomy
(`GROUP_WRITABLE`, `OTHER_WRITABLE`, `SET_USER_ID`, `SET_GROUP_ID`) via exactly
one `lstat` per operand, reject final symlinks as status 2, stream findings per
operand while continuing after errors, and reduce exits to 0/1/2 with
operational-error precedence. Implementation delivered the bootstrap contract
and plan, `src/permguard.c`, `tests/test_permguard.py` (52 contract cases),
`man/permguard.1`, README/CHANGELOG documentation, and additive Makefile
quality/sanitizer/Valgrind wiring; review attempt 1 failed on High PG-DOC-401
(dual-contract ambiguity), and the repair loop added explicit Authority
supersession in the bootstrap contract, plan, README, and CHANGELOG before
attempt 2 passed. Test and quality results by provenance: independent review
allowlisted only `python3 -m pytest -p no:cacheprovider tests/test_permguard.py
-q` → exit 0, 52 passed in 0.43s, zero skipped (session fixture also compiled
under C17 strict warnings into a temp tree); review did not freshly run Make,
full pytest, sanitizers, Valgrind, or static analyzers as gate results.
Step-5 quality-floor validation recorded GCC/Clang `-fsyntax-only` strict,
clang-format, clang-tidy, cppcheck, Clang analyzer, ASan+UBSan `--help` and
Valgrind `--help` probes, full pytest `332 passed, 18 skipped`, and both shell
fixture suites exiting 0. Smoke `artifacts/user-smoke/result.json` records
`app_started` true, `core_flow_completed` true, start/check exit 0, empty
`blocking_errors`; check.log pytest `332 passed, 18 skipped in 19.78s` through
`make test`, not a permguard-specific end-to-end flow. Review outcome:
`code-reviews/review-permguard-bootstrap.md` / `.verdict.json` = `pass` (0
Critical/High; Medium PG-DOC-501/502, PG-TEST-503, PG-PORT-505, PG-DOC-512;
Low PG-CRAFT-506, PG-TEST-507, PG-CLI-508, PG-MAKE-509/510/511). Remaining
non-blocking risks: architecture.md still describes a sticky-bit /
file-type-conditioned taxonomy and buffer-until-complete emission the slice
does not ship (PG-DOC-501); superseded one-code drafts still lack in-file
markers beside a false removal claim (PG-DOC-502 residue); no
`STDOUT_WRITE`/SIGPIPE regression (PG-TEST-503); hand-declared `lstat` vs
LFS redirection (PG-PORT-505); QUALITY.md/TESTING.md never mention permguard
(PG-DOC-512); plus the six Lows. Next recommended capability: bounded
governed repair of those five Medium findings (architecture accuracy,
draft markers, stdout-failure tests, POSIX prototype flags, quality/testing
docs) and fresh independent review before feature expansion. Do not claim
install, package, publication, recursion, remediation, or release readiness.

## Prior — Permguard First Vertical Slice (`f742c10135e5`)

Run `f742c10135e5` delivered and reviewed a one-code `WORLD_WRITABLE_FILE`
slice under `docs/permguard-first-vertical-slice-contract.md`. Independent
allowlisted focused pytest was 67 passed / 0 skipped; quality worker reported
full and each ASan/UBSan/Valgrind route 350/15; step validation recorded
focused 67 and full 347/18; smoke start/check 0 with check.log 347/18.
Verdict `pass` with Medium PG-REV-301/302 and Low
PG-REV-202/203/205/206/303/304. Run `51100a584ac9` supersedes that product
authority with the four-code bootstrap contract; retain this section as
historical closeout evidence only.

## Prior — Permguard Delivery (`629d1f459446`)

Run `629d1f459446` delivered and reviewed the live single-code slice after
repairing High PG-DOC-101 by deleting stale four-code normative documents and
widening the former-code scan. Its review ran focused pytest at 66 passed /
0 skipped and passed with Medium PG-REV-201 plus Low PG-REV-202–207. Current
run `f742c10135e5` supersedes its closeout evidence, confirms
PG-REV-201/204/207 resolved, and establishes the current risk set above.

## Prior — Permguard Bootstrap Result (`a8341dfae9f2`)

Objective: deliver and independently review an earlier four-code `permguard`
bootstrap without recursion, PATH lookup, remediation, install/package wiring,
or a release claim. Governed run `a8341dfae9f2`
(`bootstrap_permguard_first_vertical_slice`) delivered
`docs/permguard-contract.md`, `plans/permguard-implementation-plan.md`,
`src/permguard.c`, `tests/test_permguard.py`, `man/permguard.1`,
README/CHANGELOG documentation, and additive Makefile quality, sanitizer, and
Valgrind wiring under a taxonomy that also reported world-writable directories
and set-user-ID/set-group-ID executables. Independent verdict
`code-reviews/review-permguard-bootstrap.verdict.json` was `pass` with Medium
PG-DOC-001/PG-TEST-002 and Low PG-DIAG-003/PG-PORT-004/PG-CLI-005. That
contract/plan pair and four-code taxonomy are superseded by run `629d1f459446`
and were deleted during its High PG-DOC-101 repair; retain this section as
historical evidence only.

## Next Utility Evaluation

Future Mission Discovery plan
`plans/next-linux-utility-evaluation.md` (2026-07-26) was independently
reviewed in `code-reviews/review-next-linux-utility-evaluation.md` /
`.verdict.json` with verdict `pass` (0 Critical/High/Medium; 2 Low:
`permguard-writability-overlap`, `first-slice-scope-breadth`). Chosen
mission: bootstrap `permguard` as the third suite utility. Pathaudit
completion boundary: v1 capability-complete (explicit-root, `--path`,
`--command`, in-tree quality floor); further detector expansion is not
required before starting the next utility; pathaudit remains unreleased
and is not covered by the sysdiff smoke oracle. First vertical slice:
explicit-root `permguard [--] PATH...` with a closed `stat`-shaped
taxonomy (writability, ownership, setuid/setgid, sticky); no recursion,
PATH read, remediation, or release claim. Review checks were
plan-evidence only (`compileall`, `git tag -l`, `wc -l`, taxonomy grep)—
not product smoke for a new binary. Unresolved: those two Low findings
plus prior pathaudit/sysdiff Medium/Low backlogs kept visible as ordinary
repair. Its historical next action was governed bootstrap of the permguard
vertical slice; run `51100a584ac9` has now completed that action under
`docs/permguard-bootstrap-contract.md`. The selection handoff itself did not
implement or release a utility.

## Detect unsafe ownership of PATH directories

Governed run `50c0b4936d50` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect unsafe
ownership of PATH directories for `pathaudit --path` and
`pathaudit --command`: every usable PATH directory and each ancestor
through `/` inherits the executable ownership trust rule (UID 0 and
invoking real UID from `getuid()`, not `geteuid`); untrusted final-target
`st_uid` emits `UNSAFE_OWNER` on the canonical offending directory
`realpath`; shared ancestor realpaths deduplicate to the lowest PATH
index; missing, empty, and non-directory components invent no ownership
lines; `owner_uid_is_trusted` is shared with executable ownership;
explicit-root mode stays ownership-blind and never emits directory or
ancestor `UNSAFE_OWNER`. Exact deliverables touched in-run:
`tests/test_pathaudit.py`, `src/pathaudit.c`, `README.md`, `SECURITY.md`.
Exact step-2 verification: `make clean && make` exited 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 280 passed, 18 skipped in 26.84s. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `280 passed, 18 skipped in
20.40s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise directory-ownership `--path` /
`--command` detection; pathaudit coverage is `tests/test_pathaudit.py`.
Independent review artifacts:
`code-reviews/review-path-directory-ownership.md` and
`code-reviews/review-path-directory-ownership.verdict.json`.
Verdict: `pass` with no Critical, High, or Medium findings and one Low
finding (`path-dir-ownership-1`: O(N²) linear dedup of `UNSAFE_OWNER`
findings under a hostile all-foreign-owned PATH; bounded by input
limits; non-blocking). Allowlisted review check:
`python3 -m pytest -p no:cacheprovider tests/test_pathaudit.py -q` →
exit 0, 143 passed, 15 skipped in ~1.8s. The 15 skips are host-capability
self-skips (no distinct foreign UID / unprivileged `chown`, oversized-
PATH env rejection), not failures. Remaining risks: Low
`path-dir-ownership-1` plus prior Medium pathaudit-shadow-1 and Low
pathaudit-shadow-2/3, Low PA-W1/PA-W2, Low nondir-1/2, pathaudit-cmd-1/2,
pathaudit-wdp-1/2, and PA-WP-1–PA-WP-4, bootstrap Medium PA-M1/PA-M2
leftovers, and sysdiff Medium backlogs not closed by this review.
Recommended next action: keep Low `path-dir-ownership-1` visible; prefer
next genuine capability Detect writable ancestors of PATH directories;
optional Medium pathaudit-shadow-1 repair remains available. Do not claim
that `pathaudit` is released.

## Detect executables with unsafe ownership

Governed run `1d5eedc01202` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect
executables with unsafe ownership for `pathaudit --path` and
`pathaudit --command`: final followed-target `st_uid` trusts only UID 0
and the invoking real UID from `getuid()` (not `geteuid`); every other
owner emits `UNSAFE_OWNER` on the executable `realpath`; ownership
composes with writability via shared code-rank sort (`UNSAFE_OWNER`
after `GROUP_WRITABLE`/`WORLD_WRITABLE`, before `SHADOWED`); symlink
resolution follows the final target; shebang/ELF probing keeps
non-executable decoys out of the candidate set; candidates are never
executed; explicit-root mode never searches executables and never
emits `UNSAFE_OWNER`. Exact deliverables touched in-run:
`tests/test_pathaudit.py`, `src/pathaudit.c`,
`docs/pathaudit-contract.md`, `README.md`, `man/pathaudit.1`,
`CHANGELOG.md`, `architecture.md`. Exact step-4 verification:
`make quality` exited 0; `clang -std=c17 -Wall -Wextra -Wpedantic
-Werror -fsyntax-only src/pathaudit.c` exited 0; `cppcheck --quiet
--enable=all --suppress=missingIncludeSystem --error-exitcode=1
src/pathaudit.c` exited 0; `python3 -m pytest -p no:cacheprovider
tests/ -q` → 271 passed, 14 skipped in 19.02s. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `271 passed, 14 skipped in
19.94s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise an ownership-specific `--path` /
`--command` user flow; pathaudit coverage is `tests/test_pathaudit.py`.
Independent review artifacts:
`code-reviews/review-pathaudit-unsafe-executable-ownership.md` and
`code-reviews/review-pathaudit-unsafe-executable-ownership.verdict.json`.
Verdict: `pass` with no Critical, High, Medium, or Low formal findings
(empty `findings` array). Allowlisted review check:
`python3 -m pytest tests/ -q -p no:cacheprovider` → exit 0, 271 passed,
14 skipped in ~19s. The 14 skips are privilege-gated foreign-owner /
root-owner fixtures that honestly `pytest.skip` on this non-root host
(UID 1000); trusted-owner and explicit-root ownership-blind cases run
and pass. Remaining risks: informational review notes only
(per-finding `getuid()` re-call; `stat`/`realpath` TOCTOU under
concurrent FS change, contract-disclaimed; positive emission path
host-privilege gated) plus prior Medium pathaudit-shadow-1 and Low
pathaudit-shadow-2/3, Low PA-W1/PA-W2, Low nondir-1/2,
pathaudit-cmd-1/2, pathaudit-wdp-1/2, and PA-WP-1–PA-WP-4, bootstrap
Medium PA-M1/PA-M2 leftovers, and sysdiff Medium backlogs not closed by
this review. Recommended next action: keep informational ownership
notes visible; prefer repairing pathaudit-shadow-1 or resume prior
Medium backlog. Do not claim that `pathaudit` is released.

## Detect writable resolved-executables through PATH

Governed run `574d06adfc2a` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect writable
resolved-executables through PATH for `pathaudit --path` and
`pathaudit --command`: apply the existing directory trust model to final
executable targets resolved through PATH (`GROUP_WRITABLE` /
`WORLD_WRITABLE` on the executable `realpath`; owner-only write silent);
symlink resolution follows the final target; shebang/ELF probing keeps
non-executable same-basename decoys out of the candidate set; unsafe
inspection reject-closes via `INSPECTION_ERROR_N`; explicit-root mode
still never searches executables; writability findings sort with
directory hazards and precede `SHADOWED`. Exact deliverables touched
in-run: `tests/test_pathaudit.py`, `src/pathaudit.c`. Exact step-3
verification: `clang -std=c17 -Wall -Wextra -Wpedantic -Werror
-fsyntax-only src/pathaudit.c` exited 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 269 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `269 passed, 1 skipped in
18.74s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise writable-executable `--path` /
`--command` detection; pathaudit coverage is `tests/test_pathaudit.py`.
Independent review artifacts:
`code-reviews/review-pathaudit-writable-executables.md` and
`code-reviews/review-pathaudit-writable-executables.verdict.json`.
Verdict: `pass` with no Critical, High, or Medium findings and two Low
findings (PA-W1: ~64 KiB stack `readlink` target buffer in
`symlink_is_self_basename`; PA-W2: documented trust-model scope gap where
group/other-writable `+x` files that are neither `#!` nor ELF are not
reported). Allowlisted review check:
`python3 -m pytest tests/ -q -p no:cacheprovider` → exit 0, 269 passed,
1 skipped in ~18s. Remaining risks: Low PA-W1/PA-W2 plus prior Medium
pathaudit-shadow-1 and Low pathaudit-shadow-2/3, Low nondir-1/2,
pathaudit-cmd-1/2, pathaudit-wdp-1/2, and PA-WP-1–PA-WP-4, bootstrap
Medium PA-M1/PA-M2 leftovers, and sysdiff Medium backlogs not closed by
this review. Recommended next action: optional Low PA-W polish; prefer
repairing pathaudit-shadow-1 or resume prior Medium backlog. Do not
claim that `pathaudit` is released.

## Detect executable shadowing across PATH entries

Governed run `f94509b47fd3` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect
executable shadowing across PATH entries for `pathaudit --path`: walk
process `PATH` left-to-right; the first regular `X_OK` file per basename
is the winner; every later distinct `realpath` hit emits
`SHADOWED\t"COMMAND"\t"WINNER_REALPATH"\t"SHADOWED_REALPATH"` after
shared-taxonomy directory hazard lines; `SHADOWED` lines are ordered by
command basename bytes then PATH index of the shadowed hit; repeated
identical realpaths do not self-shadow; empty/missing/non-directory/
unreadable components are skipped for the scan without inventing
shadows; no nested-directory recursion; explicit-root mode never emits
`SHADOWED`; shadowing alone exits status 1 with empty stderr. Exact
deliverables touched in-run: `tests/test_pathaudit.py`,
`src/pathaudit.c`, `README.md`. Exact step-4 verification:
`gcc`/`clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only
src/pathaudit.c` exited 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 247 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `247 passed, 1 skipped in
18.41s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise executable-shadowing `--path` detection;
pathaudit coverage is `tests/test_pathaudit.py`. Independent review
artifacts: `code-reviews/review-executable-shadowing.md` and
`code-reviews/review-executable-shadowing.verdict.json`. Verdict:
`pass` with no Critical or High findings, one Medium finding
(pathaudit-shadow-1: fixed 65537-byte `realpath` scratch buffer retained
per winner/shadow instead of a right-sized copy), and two Low findings
(pathaudit-shadow-2: O(distinct_executables²) linear winner lookup;
pathaudit-shadow-3: repeated non-winner PATH directories can emit
duplicate identical `SHADOWED` lines because de-dup checks only the
winner realpath). Allowlisted review check:
`python3 -m pytest tests/ -q -p no:cacheprovider` → exit 0, 247 passed,
1 skipped in ~17.95s. Remaining risks: Medium pathaudit-shadow-1 and
Low pathaudit-shadow-2/3 plus prior pathaudit Low nondir-1/2,
pathaudit-cmd-1/2, pathaudit-wdp-1/2, and PA-WP-1–PA-WP-4, bootstrap
Medium PA-M1/PA-M2 leftovers, and sysdiff Medium backlogs not closed by
this review. Recommended next action: repair pathaudit-shadow-1 or
resume prior Medium backlog; keep Low shadow findings visible. Do not
claim that `pathaudit` is released.

## Detect non-directory PATH entries

Governed run `35116f657f35` (playbook
`detect_non_directory_path_entries`) delivered Detect non-directory PATH
entries for `pathaudit --path` and explicit-root modes: pins
`NON_DIRECTORY_ROOT` for regular-file, symlink-to-file, and ENOTDIR
PATH/root components with exit status 1 and empty stderr; mutually
exclusive with `MISSING_ROOT`; permission findings never attach to
non-directory roots; relative non-directory files keep `RELATIVE_ROOT`
and add `NON_DIRECTORY_ROOT`. Exact deliverables touched in-run:
`tests/test_pathaudit.py`, `src/pathaudit.c` (comment-only
`classify_root` clarification; runtime logic pre-existed), `README.md`,
`man/pathaudit.1`. Exact step-3 verification (non-writing; no
`make`/build dir): `clang -std=c17 -Wall -Wextra -Wpedantic -Werror
-fsyntax-only src/pathaudit.c` exited 0; `cppcheck --quiet --enable=all
--suppress=missingIncludeSystem src/pathaudit.c` exited 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 234 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `234 passed, 1 skipped in
19.50s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise non-directory `--path` detection;
pathaudit coverage is `tests/test_pathaudit.py`. Independent review
artifacts: `code-reviews/review-detect-non-directory-path-entries.md`
and `code-reviews/review-detect-non-directory-path-entries.verdict.json`.
Verdict: `pass` with no Critical, High, or Medium findings and two Low
findings (nondir-1 comment names FIFO/device/socket but suite only pins
file/symlink/ENOTDIR on the shared `!S_ISDIR` branch; nondir-2
pre-existing `classify_root` vs `classify_command_component` taxonomy
duplication). Allowlisted review check:
`python3 -m pytest -p no:cacheprovider tests/test_pathaudit.py -q` →
exit 0, 94 passed, 1 skipped in ~1.9s. Remaining risks: Low nondir-1/2
plus prior pathaudit Low pathaudit-cmd-1/2, pathaudit-wdp-1/2, and
PA-WP-1–PA-WP-4, bootstrap Medium PA-M1/PA-M2 leftovers, and sysdiff
Medium backlogs not closed by this review. Recommended next action:
optional Low polish; resume prior Medium backlog repair. Do not claim
that `pathaudit` is released.

## Command-Specific PATH Risk Inspection

Governed run `2b2fb272c21a` (playbook
`template_repair_before_review_feature_delivery`) delivered bounded
command-specific PATH risk inspection for exclusive opt-in
`pathaudit --command NAME`: walk process `PATH` in resolution order
for one basename; emit `MATCH` lines (`realpath` of regular `X_OK`
files) in PATH order including shadows/repeats; then emit applicable
shared-taxonomy hazard lines with plant-risk-before-winner
applicability; reject empty or `/`-containing names as
`INVALID_COMMAND`; unset `PATH` reject-closes as `PATH_UNSET`. Exact
deliverables touched in-run: `tests/test_pathaudit.py`,
`src/pathaudit.c`, `README.md`, `man/pathaudit.1`. Exact step-4
verification: `make clean && make test` → 230 passed, 1 skipped;
`python3 -m pytest tests/ -q` → 230 passed, 1 skipped; format-check,
clang-tidy-check, cppcheck-check, clang-analyzer-check, man-check,
`pathaudit-sanitize`, and `pathaudit-valgrind` exited 0; pathaudit
suite alone → 90 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `230 passed, 1 skipped in
18.98s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise `--command`; pathaudit coverage is
`tests/test_pathaudit.py`. Independent review artifacts:
`code-reviews/review-command-specific-path-risk.md` and
`code-reviews/review-command-specific-path-risk.verdict.json`.
Verdict: `pass` with no Critical, High, or Medium findings and two
Low findings (pathaudit-cmd-1 near-duplicate classification logic
between `classify_command_component` and `classify_root`;
pathaudit-cmd-2 dead `root->len == 0` disjunct in
`root_is_cwd_dependent`). Allowlisted review check:
`python3 -m pytest tests/ -q` → exit 0, 230 passed, 1 skipped in
~18.7s. Remaining risks: Low pathaudit-cmd-1/2 plus prior pathaudit
Low pathaudit-wdp-1/2 and PA-WP-1–PA-WP-4, bootstrap Medium PA-M1/PA-M2
leftovers, and sysdiff Medium backlogs not closed by this review.
Recommended next action: optional Low polish; resume prior Medium
backlog repair. Do not claim that `pathaudit` is released.

## Working-Directory-Dependent PATH Entries

Governed run `79a1cc2bac7a` (playbook
`pathaudit_working_directory_dependent_path_entries`) delivered
working-directory-dependent PATH detection for opt-in `pathaudit --path`:
empty colon fields retain `""` and report `EMPTY_ROOT` without rewriting
to `.` or looking them up; every non-absolute component (`.`, `..`,
`./bin`, bare names) reports `RELATIVE_ROOT` and is still looked up
against the process cwd so missing/writable relative targets can add
further codes; absolute `/`-prefixed entries never receive
`EMPTY_ROOT`/`RELATIVE_ROOT`. Exact deliverables touched in-run:
`tests/test_pathaudit.py`, `src/pathaudit.c`, `README.md`. Exact step-4
verification (non-writing; no `make`/build dir):
`gcc`/`clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only
src/pathaudit.c` exited 0; `cppcheck --quiet --enable=all
--suppress=missingIncludeSystem src/pathaudit.c` exited 0;
`python3 -B -m pytest tests/test_pathaudit.py -q -p no:cacheprovider` →
62 passed, 1 skipped in 3.87s; full `python3 -B -m pytest tests/ -q -p
no:cacheprovider` → 202 passed, 1 skipped in 22.46s. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `202 passed, 1 skipped in
18.42s`. The pinned smoke oracle remains the sysdiff fixture path and
does **not** directly exercise cwd-dependent `--path` detection;
pathaudit coverage is `tests/test_pathaudit.py`. Independent review
artifacts: `code-reviews/review-pathaudit-working-directory-path.md` and
`code-reviews/review-pathaudit-working-directory-path.verdict.json`.
Verdict: `pass` at the High threshold with no Critical, High, or Medium
findings and two Low findings (pathaudit-wdp-1 dead `root->len == 0`
disjunct in `root_is_cwd_dependent`; pathaudit-wdp-2 misleading
`OUT_OF_MEMORY` on practically unreachable `signal(SIGPIPE)` failure).
Allowlisted review checks: `python3 -m pytest tests/test_pathaudit.py -q
-p no:cacheprovider` → exit 0, 62 passed, 1 skipped in ~1.6s;
`python3 -m pytest tests/ -q -p no:cacheprovider` → exit 0, 202 passed,
1 skipped in ~17.5s. Remaining risks: Low pathaudit-wdp-1/2 plus prior
pathaudit Low PA-WP-1–PA-WP-4, bootstrap Medium PA-M1/PA-M2 leftovers,
and sysdiff Medium backlogs not closed by this review. Recommended next
action: optional Low polish; resume prior Medium backlog repair. Do not
claim that `pathaudit` is released.

## Writable PATH Directories

Governed run `d27d2ade171f` (playbook
`pathaudit_detect_writable_path_directories`) delivered the additive
opt-in `pathaudit --path` mode that reads process `PATH` once, splits on
ASCII `:`, retains empty and duplicate components, and applies the shared
hazard taxonomy (including `GROUP_WRITABLE` / `WORLD_WRITABLE`) without
changing explicit-root behavior. Exact deliverables touched in-run:
`docs/pathaudit-contract.md`, `src/pathaudit.c`, `tests/test_pathaudit.py`,
`man/pathaudit.1`, README/CHANGELOG docs. Exact step-5 verification:
`make clean && make test` → 196 passed, 1 skipped; `format-check`,
`clang-tidy-check`, `cppcheck-check`, `clang-analyzer-check`,
`pathaudit-sanitize`, and `pathaudit-valgrind` exited 0; ASan+UBSan
pathaudit suite → 56 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors`; check.log pytest `196 passed, 1 skipped in
18.33s`. The pinned smoke oracle remains the sysdiff fixture path and does
**not** directly exercise `--path`; pathaudit coverage is
`tests/test_pathaudit.py`. Independent review artifacts:
`code-reviews/review-pathaudit-writable-path.md` and
`code-reviews/review-pathaudit-writable-path.verdict.json`. Verdict:
`pass` at the High/Critical threshold with no Critical, High, or Medium
findings and four Low findings (PA-WP-1 duplicated limit accounting;
PA-WP-2 misleading `OUT_OF_MEMORY` on unreachable guards; PA-WP-3
redundant PATH scans; PA-WP-4 host-limited `--path` aggregate bytes-limit
probe, covered via explicit-root). Allowlisted review check:
`python3 -m pytest -p no:cacheprovider tests/test_pathaudit.py -q` →
exit 0, 56 passed, 1 skipped in ~1.56s. Remaining risks: Low PA-WP-1–PA-WP-4
plus prior pathaudit/sysdiff Medium backlogs not closed by this review.
Recommended next action: optional Low polish; resume prior Medium backlog
repair. Do not claim that `pathaudit` is released.

## pathaudit Vertical-Slice Bootstrap

Governed run `4dec475ef201` (playbook
`pathaudit_bootstrap_deterministic_scanner`) delivered the additive
`pathaudit` 0.1.0 vertical slice and completed independent review. Exact
deliverables: `docs/pathaudit-contract.md`, `src/pathaudit.c`,
`man/pathaudit.1`, `tests/test_pathaudit.py` (26 contract tests),
Makefile quality/sanitizer/Valgrind wiring for both utilities, and
README/QUALITY/TESTING documentation. Explicit non-goals: not a
`pathaudit` release, not an install/uninstall path for pathaudit, and no
change to `sysdiff` compare behavior (`src/sysdiff.c`, `man/sysdiff.1`,
fixture/smoke manifests byte-identical to HEAD aside from additive
wiring). Step-3 validation passed exactly: GCC/Clang
`-std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only`; clang-format
`--dry-run --Werror`; clang-tidy; cppcheck; Clang `--analyze`;
`pytest tests/test_pathaudit.py` → 26 passed in 0.38s; full
`pytest tests/` → 158 passed in 14.98s; ASan and Valgrind help probes
exited 0. Review additionally confirmed the contract suite clean under
ASan (leak detection), UBSan (halt-on-error), and Valgrind memcheck
(26 passed). Governed user smoke passed:
`artifacts/user-smoke/result.json` records `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
and empty `blocking_errors`; check.log pytest `158 passed in 12.88s`.
The pinned smoke oracle (`tests/smoke_manifest.json`) remains the
sysdiff fixture path and does **not** directly exercise pathaudit;
pathaudit coverage is `tests/test_pathaudit.py` (and full-suite pytest
when that suite is invoked). Independent review artifacts:
`code-reviews/review-pathaudit-bootstrap.md` and
`code-reviews/review-pathaudit-bootstrap.verdict.json`. Verdict: `pass`
at the High threshold with no Critical or High findings, two Medium
findings (PA-M1 AgentFlow/CHANGELOG/architecture visibility;
PA-M2 missing hostile-byte stderr diagnostic fixture), and seven Low
findings (PA-L1–PA-L7). Allowlisted review checks:
`python3 -m pytest tests/test_pathaudit.py -q -p no:cacheprovider` →
26 passed in 0.30s; `python3 -m pytest tests/ -q -p no:cacheprovider` →
158 passed in 12.03s (132 without pathaudit). Remaining risks: PA-M1
leftovers after this handoff (CHANGELOG Unreleased + architecture.md
ownership), PA-M2, Low PA-L1–PA-L7, plus prior sysdiff Medium backlogs.
Recommended next action: repair PA-M2 and finish PA-M1 leftovers; keep
Low findings visible. Do not claim that `pathaudit` is released.

## Release Package

Governed run `580b0f6ff811` (playbook
`prepare_sysdiff_release_package_and_notes`) prepared and verified an
unpublished `sysdiff` **0.1.0** release candidate, passed user smoke, and
received an independent package review. Do not claim that a release was
published, that Lee authorized external distribution, or that package
inputs may still be edited after the reviewed archive. Archive path:
`sysdiff-release.tar.gz` (single root `sysdiff-release/`, 28 intentional
members). Checksum path: `sysdiff-release.tar.gz.sha256` containing
`9492eee35f58f467ea3ffa0fd82b4bade46a5df0fedbd3dc814f05537372f33f  sysdiff-release.tar.gz`
(`sha256sum -c` → OK; two independent `make release` rebuilds
byte-identical). QUALITY.md **Release Verification** records: `pytest -k
rc_001` → 2 passed; both shell suites ok; full `pytest tests/` → 128
passed; `make clean && make test && make release`; clean `/tmp` extract
`make clean test` → **121 passed, 7 skipped**. RC-001 result: pass —
bytewise mixed-case ordering and strcasecmp-mutant kill; no
`src/sysdiff.c` compare-behavior change. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`,
empty `blocking_errors` (check.log: DESTDIR install/uninstall staging,
fixture acceptance ok, pytest `128 passed in 10.64s`). Independent review
artifacts: `code-reviews/review-sysdiff-release.md` and
`code-reviews/review-sysdiff-release.verdict.json`. Verdict: `pass` with
no Critical or High findings and one Low finding (L1: packaged README
links to non-packaged `STATUS.md`/`HISTORY.md`). Step-3 attempt 1 failed
the verdict gate on High H1 (missing-pathspec guard fail-open inside
process substitution); repair moved the existence check to the parent
shell and attempt 2 re-verified fail-closed plus pytest
`test_release_missing_pathspec_fails_closed_without_writing_archive`.
Allowlisted review check `python3 -m pytest tests/ -q` exited 0 with
`128 passed in 11.07s`. Remaining risks: L1; prior Medium backlogs;
accepted Low product limitations; worktree-not-commit packaging;
no fresh full `make quality` in the review step. Next authorized action:
Lee-controlled publication authorization only—do not publish, and do not
modify release-package inputs after this reviewed archive.

## First Independent sysdiff Release-Candidate Review

Governed run `6d0a6fbfe83d` (playbook
`template_repair_before_review_feature_delivery`) completed user smoke, the
first independent `sysdiff` release-candidate review, and this handoff record.
This is the first clean review in the required consecutive clean-review
sequence. Do not claim that `sysdiff` is released, that the mission is
complete, or that a second consecutive clean RC review has occurred. Exact
smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`. `artifacts/user-smoke/check.log` confirms DESTDIR
install/uninstall staging, fixture acceptance ok, and smoke-bound pytest
`127 passed in 10.75s`. Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.89s` (reviewed at HEAD `510fa2d`). Independent review
artifacts: `code-reviews/review-first-sysdiff-release-candidate.md` and
`code-reviews/review-first-sysdiff-release-candidate.verdict.json`. Verdict:
`pass` with no Medium, High, or Critical findings, and ten Low findings
(L1–L10) preserved: L1 unreproducible complete-floor provenance in
`docs/sysdiff-quality-floor-clean-checkout.md`; L2 STATUS.md stale "no install
target"; L3 quality-floor doc still labels resolved packaging risk as known
Medium; L4 no-op `tests/smoke_start.py`; L5 dead `read_line` overflow
disjuncts in `src/sysdiff.c`; L6 stale-errno stdout diagnostic in
`complete_stdout`/`emit_write_error`; L7 undeclared POSIX SIGPIPE under
`-std=c17`; L8 pytest `test_dist_*` regenerates workspace `dist/`; L9
TESTING.md wrong SYSDIFF_BIN reuse claim; L10 STATUS.md unanchored
clean-review counter conflicting with this sequence position. Step-2 attempt 1
failed the verdict gate on Medium M1 (same provenance issue); attempt 2 held
it at Low and passed. Remaining risks stay visible (Low L1–L10 plus prior-slice
Medium backlogs). Prior Medium-or-higher debt continues to prohibit new
feature work until repaired. A second consecutive clean independent RC review
is still required before the two-clean-review requirement is satisfied.

## Second Independent Release-Candidate Review Cycle

Governed run `c84986cf0c81` (playbook
`sysdiff_second_independent_release_candidate_review_cycle`) completed user
smoke, the second independent release-candidate review, and this handoff
record. Verdict `code-reviews/sysdiff-rc-second-independent-cycle.verdict.json`
is `pass` under the Medium threshold: 0 Medium/High/Critical, 9 Low (L1–L9).
Exact smoke (`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`. `artifacts/user-smoke/check.log` confirms DESTDIR
install/uninstall staging, fixture acceptance ok, and smoke-bound pytest
`127 passed in 10.84s`. Exact review check:
`python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.96s`. RC-001 strcasecmp-mutant result: independently
reconstructed (`strcmp` → `strcasecmp` in `compare_entries_by_key`); kill is
behavioral and robust to qsort Alpha/alpha tie-breaking; full suite with
`SYSDIFF_BIN` on the mutant reports `1 failed, 126 passed` on the mixed-case
bytewise ordering test. Consecutive clean RC review cycles now stand at 2
(prior: `sysdiff-rc-review-cycle-1.verdict.json` pass). Fresh quality evidence
this cycle: step-1 non-writing gates (pytest 127; gcc/clang `-fsyntax-only`;
cppcheck; shell `bash -n`; `check_tools.py`) plus smoke/review pytest—not a
fresh full `make quality`. Remaining Low L1–L9 stay visible. This records the
second consecutive clean RC cycle; it does not declare `sysdiff` released.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` (playbook `sysdiff_first_independent_rc_review_cycle`)
completed user smoke, the independent release-candidate review, and this
handoff record. This is the first independent release-candidate review cycle.
Do not claim that `sysdiff` is released, that the mission is complete, or that
a second consecutive clean RC review has occurred. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, empty
`blocking_errors`. `artifacts/user-smoke/check.log` confirms assembled-product
`make install`/`make uninstall` staging, fixture acceptance ok, and smoke-bound
pytest `127 passed in 10.58s`. Exact review check: `python3 -m pytest tests/ -q`
exited 0 with `127 passed in 11.06s` (no skips). Independent review artifacts:
`code-reviews/sysdiff-rc-review-cycle-1.md` and
`code-reviews/sysdiff-rc-review-cycle-1.verdict.json`. Verdict: `pass` with no
Medium, High, or Critical findings, and seven Low findings (F1–F7) preserved:
STATUS/ROADMAP install-target wording; TESTING.md SYSDIFF_BIN reuse claim;
mutant-test hardcoded `/tmp`; unused scratch Makefile copy; `finally`-block
assertions/`rm -rf`; mutant oracle not tied to shell golden. Remaining risks
stay visible (Low F1–F7 plus prior-slice Medium backlogs). A second consecutive
review cycle with no release-blocking findings is still required before mission
completion.

## First Consecutive Release-Blocking Independent Review

- Governed run `7eb4e29dee6e` (playbook
  `complete_first_consecutive_release_blocking_independent_review`) completed
  user smoke, the independent release-blocking review, and this handoff record.
  This is the first consecutive clean release-blocking independent review. Do
  not claim a second clean review, mission completion, or release readiness.
- Exact smoke outcome (`artifacts/user-smoke/result.json`): `app_started:
  true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, empty `blocking_errors`. `artifacts/user-smoke/check.log`
  confirms assembled-product `make install`/`make uninstall` staging (modes
  755/644), fixture acceptance ok, and smoke-bound pytest `124 passed in
  10.23s`.
- Exact full-suite outcome (review allowlisted check): `python3 -m pytest
  tests/ -q` exited 0 with `124 passed in 10.71s` (non-vacuous compile under
  `-std=c17 -Wall -Wextra -Wpedantic -Werror` when `SYSDIFF_BIN` unset).
- Independent review artifacts:
  `code-reviews/sysdiff-independent-review-1.md` and
  `code-reviews/sysdiff-independent-review-1.verdict.json`. Verdict: `pass`
  with no Medium, High, or Critical findings, and five Low findings (L-1–L-5)
  preserved: man `--help`/`--version` arity diagnostic; architecture Valgrind
  clean/rebuild wording; accepted ` -> ` irreversibility; DESIGN quality-sequence
  wording; SIGPIPE Linux-conditional docs vs unconditional POSIX ignore.
- Remaining risks stay visible (Low L-1–L-5 plus prior-slice Medium backlogs).
  This handoff records the first consecutive clean gate only; it does not
  assert full product-release closure.

## Reproducible Source Archive — Isolated Build Verification

- Governed run `939ee21b0d76` (playbook
  `verify_reproducible_source_archive_isolated_build`) completed isolated
  verification of `make dist` reproducibility and the extracted-tree quality
  surface. Report:
  `docs/reproducible-source-archive-isolated-build.md`. Exact archive
  identity at `SOURCE_DATE_EPOCH=946684800`: size 89851 bytes; SHA-256
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544` for
  both independent external builds; checksum file contents
  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544  sysdiff-source.tar.gz`
  (`sha256sum -c` → OK); 44 members under `sysdiff/`; `cmp` and member-list
  `diff` empty. Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Quality results from the extracted tree (report Overall Result PASS;
  independently re-executed in review): gcc-strict, clang-strict,
  format-check, clang-tidy-check, cppcheck-check, clang-analyzer-check,
  man-check, `make clean all`, test-suite, `./tests/test_sysdiff.sh`,
  `bash tests/test_sysdiff_fixture.sh`, malformed-fuzz pytest,
  benchmark-check, `make test-asan`, `make test-ubsan`, and
  `make test-valgrind` all exited 0. Extracted-tree pytest counts: 118
  passed, 6 skipped (test-suite / ASan / UBSan / Valgrind). Malformed-fuzz:
  41 passed in 0.18 s. Staged install produced exactly two files
  (`usr/local/bin/sysdiff` mode 755 size 21384;
  `usr/local/share/man/man1/sysdiff.1` mode 644 size 7191); uninstall took
  staged file count from 2 to 0.
- Failed experiment then recovered: first `make test-suite` under
  `PATH=/usr/bin:/bin` alone failed with `No module named pytest`; after
  provisioning an isolated venv with `pytest==8.4.2` under the external
  verify root, the same gates exited 0 (tool provisioning, not a silent
  skip of a required gate).
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; archive/quality evidence is
  the isolated verification and review path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-reproducible-source-archive-isolated-build.md` and
  `.verdict.json`. Verdict: `pass` with no High or Critical findings, five
  Medium findings (F1–F5), and four Low findings (F6–F9). Allowlisted check
  only: `python3 -m pytest tests/ -q` exited 0 (124 passed in 10.71 s; 0
  skipped in the git workspace). Review confirmed every quantitative claim
  in the report (digest, size, member count, gate exits, install modes/
  sizes, 2→0 residue) and found no Critical/High C craftsmanship, ownership,
  UB, diagnostics, or sanitizer issues.
- Non-blocking risks remain: F1 Medium — Artifact Identity labels revision
  `a69423e2a1cfa4b30c199797aaa10cead4879370` while `make dist` packages
  dirty working-tree bytes; F2 Medium — the six extracted-tree skips are the
  git-gated `test_dist_*` regressions, so dist coverage is not exercised in
  the non-git extract; F3 Medium — `make dist` / `make distcheck` exit 2
  from the extracted tarball; F4 Medium — `dist/` not in `.gitignore`; F5
  Medium — whole-directory `docs/` ships internal review/plan material; Low
  F6 extension-based exec bits; F7 undisclosed gzip implementation
  sensitivity; F8 README untracked-vs-dirty wording; F9 `distcheck`
  overwrites workspace `dist/`.
- Recommended next action: bound a governed repair for Medium F1–F5
  (clean-tree or committed-object packaging plus honest provenance; name the
  six dist skips / split git-free coverage; make dist usable or honestly
  unavailable in source distributions; add `dist/` to `.gitignore`;
  allowlist user-facing docs). Keep Low F6–F9 visible. Do not infer a
  packaged `.deb`/`.rpm`, commit-identical archives from dirty trees, or
  full release closure from this verification pass.

## Reproducible sysdiff Source Release (`make dist` / `make distcheck`)

- Governed run `240bfcbc634e` (playbook
  `build_verify_reproducible_sysdiff_source_release`) delivered Makefile
  `dist` and `distcheck`, six `test_dist_*` regressions in
  `tests/test_sysdiff.py`, and README "Source releases". Exact artifacts:
  `dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256`
  (basename-only digest
  `970694ed1d8dc929ab2d3f9642c734dc04536742b043f59b30ed8a201a4c919a  sysdiff-source.tar.gz`).
  `make dist` selects tracked `DIST_PATHSPECS` via `git ls-files`, stages under
  `sysdiff/`, and writes a normalized ustar+gzip archive (`SOURCE_DATE_EPOCH`
  default 0, owner/group 0, sorted members, `gzip -n -9`). `make distcheck`
  rebuilds twice, compares digests/raw bytes/checksum files, extracts under
  `/tmp` outside the workspace, and runs `make` plus `make test` on the clean
  tree. Explicit non-goal: not a `.deb`/`.rpm`, and not a change to `sysdiff`
  compare behavior. Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Step-1 validation passed exactly:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py -q` exited 0
  with 38 passed in 5.80 s; `make clean && make test` exited 0;
  `make dist && make distcheck` exited 0 (`distcheck: ok`); and
  `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c`
  exited 0. Changed files were `Makefile`, `README.md`, and
  `tests/test_sysdiff.py`.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; source-release coverage is
  the Make/pytest/`distcheck` path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-sysdiff-source-release.md` and `.verdict.json`.
  Verdict: `pass` with no High or Critical findings, five Medium findings
  (F1–F5), and five Low findings (F6–F10). Allowlisted check only:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff.py -q`
  exited 0 (38 passed in about 5.8 s). Manual inspection confirmed
  reproducibility mechanics and out-of-tree extract-build-test; the review
  did not freshly rerun `make quality` or claim full release readiness.
- Non-blocking risks remain: F1 Medium — `git ls-files` + working-tree `cp`
  packages dirty tracked bytes with no commit stamp; F2 Medium — shipped
  README Documentation links omit root STATUS/QUALITY/TESTING/HISTORY/
  DECISIONS/ROADMAP/architecture from `DIST_PATHSPECS`; F3 Medium — dist
  tests overwrite repository `dist/` at epoch `946684800` vs default 0;
  F4 Medium — `dist/` is generated but not in `.gitignore`; F5 Medium —
  recorded `.agent-orch/user-smoke` pins predate dist work and do not
  exercise `distcheck`; Low F6 sanitizer/Valgrind re-run expensive dist
  nested builds; F7 decoy-file interrupt residue; F8 unanchored exclusion
  globs; F9 triplicated `0.1.0` version string; F10 undocumented bash/git/
  tar/gzip/sha256sum prerequisites for dist.
- Recommended next action: bound a governed repair for Medium F1–F5
  (clean-tree or committed-object packaging plus provenance; archive/docs
  self-consistency; isolate dist tests from repo `dist/`; add `dist/` to
  `.gitignore`; refresh smoke evidence to cover `distcheck`). Keep Low
  F6–F10 visible. Do not infer a packaged `.deb`/`.rpm`, commit-identical
  archives from dirty trees, a fresh `make quality`, or full release
  closure from this review pass.

## Deterministic sysdiff Performance Benchmarks

- Governed run `a0eda97cd039` (playbook
  `sysdiff_deterministic_performance_benchmarks`) delivered
  `scripts/benchmark_sysdiff.py`, `tests/test_sysdiff_benchmark.py`, Makefile
  `benchmark`, README "Performance Benchmarks", and committed
  `artifacts/performance/sysdiff-benchmark.json`. Exact report evidence
  (`schema_version` 1, `passed: true`): measurements
  `startup_ms_median` 1.2422580039128661,
  `fixture_ms_median` 7.362931006355211, `peak_rss_kib` 2540.0,
  `baseline_ms_median` 1.3354689872357994; thresholds
  `startup_ms_median` 200.0, `fixture_ms_median` 100.0,
  `peak_rss_kib` 32768.0; metadata fixture_entry_count 8000, warmups 1,
  sample_count 5, `work_dir_kind` tempdir, baseline_command `/bin/true`.
  Repair closed prior Medium B1 (unchecked child exit status) and B2
  (spawn-floor / tiny fixture). Explicit non-goal: not a microbenchmark
  claim, not a change to `sysdiff` compare behavior, not `make quality`.
  Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Step-4 repair/verify passed exactly:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff_benchmark.py -q`
  exited 0 with 25 passed in 1.73 s; `make -n benchmark` exited 0; and
  `python3 scripts/benchmark_sysdiff.py --output
  artifacts/performance/sysdiff-benchmark.json` exited 0 with
  `passed: true`.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; benchmark coverage is the
  Make/pytest/harness path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-sysdiff-performance-benchmarks.md` and
  `.verdict.json`. Verdict: `pass` with no High, Critical, or Medium
  findings, and nine Low findings (B1–B9). Allowlisted check only:
  `python3 -m pytest -p no:cacheprovider tests/test_sysdiff_benchmark.py -q`
  exited 0 (25 passed in 1.62 s). Review read the committed JSON and smoke
  result; it did not freshly rerun `make benchmark` or `make quality`.
- Non-blocking risks remain (all Low): B1 RSS fallback masks exit-status
  failures; B2 CLI `--output` write path untested; B3 startup gate ~160x
  loose / spawn-dominated; B4 temp-isolation test does not exercise
  `build_sysdiff_in_temp`; B5 `/proc` VmHWM races short-lived children; B6
  hardcoded `/bin/true` without preflight; B7 unused `_RSS_WRAPPER_WORK`;
  B8 `build_report` hardcodes three threshold keys; B9 suite still skips
  green if the harness script is absent.
- Remaining environmental variability: Linux-only; scheduler noise; spawn
  floor vs product work; RSS backend availability order; minimal images
  without `/bin/true`. Recommended next action: resume Medium backlog
  (source-release F-001–F-003 first) while keeping Low B1–B9 visible for
  optional harness polish. Do not infer microbenchmark claims, cross-host
  bit-stable timings, a fresh `make quality`, or release closure.

## Reproducible sysdiff Source Release

- Governed run `b54d61531266` (playbook
  `sysdiff_reproducible_source_release`) delivered `make source-release` and
  `make source-release-verify` in the Makefile, seven pytest release tests in
  `tests/test_sysdiff.py`, README "Source Releases" docs, and CHANGELOG
  Unreleased notes. Exact artifacts:
  `dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256`
  (basename-only digest
  `1646e8465cdb9365c5ad90d2107a795fde762d3a68d46c69b61502f6531c1128  sysdiff-source.tar.gz`).
  Archive members are the six product paths under `sysdiff/` (Makefile,
  LICENSE, README.md, CHANGELOG.md, src/sysdiff.c, man/sysdiff.1). Explicit
  non-goal: not a `.deb`/`.rpm`, and not a change to `sysdiff` compare
  behavior. Closeout handoff for this run is now recorded in AgentFlow
  (`context.md`, `result-review.md`, `sprint-plan.md`, `WHERE_AM_I.md`).
- Step-2 validation passed exactly: `make clean && make test`;
  `bash tests/test_sysdiff.sh`; `bash tests/test_sysdiff_fixture.sh`;
  `python3 -m pytest tests/test_sysdiff.py -q` exited 0 with 40 passed in
  2.05 s; `make source-release-verify` exited 0; and
  `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c`
  exited 0. Step-1 also confirmed artifact existence and
  `make source-release-verify` plus pytest (40 passed in 2.14 s).
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; source-release coverage is
  the Make/pytest path above, not that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-sysdiff-reproducible-source-release.md` and
  `.verdict.json`. Verdict: `pass` with no High or Critical findings, three
  Medium findings (F-001–F-003), and three Low findings (F-004–F-006).
  Allowlisted check only: `python3 -m pytest tests/test_sysdiff.py -q`
  exited 0 (40 passed in 2.13 s). Manual inspection confirmed checksum OK,
  normalized member metadata, and out-of-tree default `make` build success;
  the review did not freshly rerun `make quality` or claim full release
  readiness.
- Non-blocking risks remain: F-001 Medium — shipped README/Makefile document
  tests, quality gates, scripts, and docs that are not archive members, so
  `make test`/`quality`/`check` fail in a clean extract while default `make`
  succeeds; F-002 Medium — release tests write into repository `dist/` and
  pin epoch `946684800` vs default `SOURCE_DATE_EPOCH=0`; F-003 Medium —
  `dist/` is generated but not in `.gitignore`; Low F-004 unpinned gzip
  compression level across environments; F-005 over-broad `*../*` verify
  glob; F-006 CHANGELOG still lists “source-first packaging without an
  install target” despite install/uninstall targets.
- Recommended next action: bound a governed repair for Medium F-001–F-003
  (archive/docs self-consistency first; then isolate release tests from repo
  `dist/` and add `dist/` to `.gitignore` or pin a committed-artifact
  decision). Keep Low F-004–F-006 visible. Do not infer a packaged
  `.deb`/`.rpm`, cross-distro bit-identical gzip digests, a fresh
  `make quality`, or full release closure from this review pass.

## Deterministic Malformed-Snapshot Fuzz Regression Coverage

- Governed run `feb8e707ea28` (playbook
  `template_repair_before_review_feature_delivery`) delivered the malformed-
  snapshot fuzz regression contract at
  `docs/malformed-snapshot-fuzz-regression-contract.md` and the deterministic
  pytest corpus `tests/test_sysdiff_malformed_fuzz.py` (fixed-byte cases plus
  seeded mutations under `CORPUS_SEED = 0x5FED1FF5`). No `src/sysdiff.c` changes
  were required; the existing parser already reject-closes every corpus case
  with exit status 2 and empty stdout. Explicit non-goal: this is not open-
  ended fuzzing, not a new CLI surface, and not a release gate.
- Step-3 validation passed exactly: `python3 -m pytest
  tests/test_sysdiff_malformed_fuzz.py -q` exited 0 with 40 passed in 0.18 s
  (38 parametrized rejection cases plus two structural corpus tests); and
  `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c`
  exited 0. Changed deliverables were the contract, the fuzz test module, and
  the two review artifacts.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; the malformed corpus is covered
  by the pytest module, not by that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-malformed-snapshot-fuzz-regression.md` and
  `.verdict.json`. Verdict: `pass` at the High threshold with no High or
  Critical findings, four Medium findings (F1–F4), and three Low findings
  (F5–F7). Allowlisted check only: `python3 -m pytest
  tests/test_sysdiff_malformed_fuzz.py -q` exited 0 (40 passed in 0.19 s). The
  review did not freshly rerun ASan, UBSan, Valgrind, or `make quality`.
- Non-blocking risks remain: F1 Medium — no corpus case exceeds the 16 MiB
  total-byte limit; F2 Medium — the claimed `read_line` LINE_TOO_LONG case is
  behaviorally identical to the post-strip 65537-byte guard; F3 Medium —
  rejection-only suite lacks a positive-control compare; F4 Medium — harness
  ignores `SYSDIFF_UNDER_VALGRIND` so Valgrind never sees hostile inputs
  (ASan/UBSan via `SYSDIFF_BIN` is noted as the carry path, not newly proven
  here); Low F5 duplicate seeded mutations; F6 silent valid-mutation drops;
  F7 hardcoded fallback compile flags vs project `CFLAGS`.
- Recommended next action: finish closeout for `feb8e707ea28`, then bound a
  repair for Medium F1–F4. Do not infer open-ended fuzzing coverage, a fresh
  sanitizer/Valgrind product gate, a release, or a complete `make quality`
  from this threshold-High review pass.

## Add reproducible install and uninstall packaging checks

- Governed run `a2d750c92da3`, playbook
  `sysdiff_reproducible_install_uninstall_packaging_checks`, delivered Makefile
  `install`/`uninstall` using `DESTDIR` plus `prefix`/`bindir`/`mandir`/`man1dir`,
  a packaging block in `tests/test_sysdiff.sh` that stages into a workspace
  `DESTDIR`, asserts an exact two-file manifest and modes 755/644, runs the
  installed binary for `--help`/`--version`/`compare`, checks byte-identical
  reinstall, and asserts leftover-free file/symlink uninstall, plus README
  installation wording that matches those targets. Explicit non-goal: no
  `.deb`/`.rpm` generation.
- Step-1 validation passed: `bash -n tests/test_sysdiff.sh`;
  `make clean && make test`; `bash tests/test_sysdiff.sh`; and
  `bash tests/test_sysdiff_fixture.sh`. Changed files were `Makefile`,
  `README.md`, and `tests/test_sysdiff.sh`.
- Governed user smoke passed: `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
  `check_exit_code: 0`, and empty `blocking_errors`. Smoke exercises the
  fixture path via `tests/smoke_manifest.json`; packaging is covered by the
  shell/`make test` path, not by that smoke oracle.
- Independent review artifacts:
  `code-reviews/review-install-uninstall-packaging.md` and
  `.verdict.json`. Verdict: `pass` with no High or Critical findings, one
  Medium finding (F1), and six Low findings (F2–F7). Allowlisted check only:
  `python3 -m pytest tests/test_sysdiff.py tests/test_check_tools.py -q -p
  no:cacheprovider` exited 0 (50 passed in 2.24 s).
- Non-blocking risks remain: F1 Medium — packaging ignores `SYSDIFF_BIN` and
  repeats uninstrumented staged install under sanitizer/Valgrind gates; Low
  F2 empty-directory residue unasserted; F3 no whitespace/`metachar` DESTDIR
  coverage in-suite; F4 bare `make` / jobserver warning; F5 undocumented
  `bindir`/`mandir`/`man1dir`; F6 undeclared GNU find/stat/install dependency;
  F7 bare permission-denied install diagnostics.
- Recommended next action: finish closeout for `a2d750c92da3`, then bound a
  repair for F1 (skip or isolate packaging under instrumented gates). Do not
  infer a release, complete packaging/product gate, clean review with zero
  findings, or a fresh `make quality` from this threshold pass.

## 2026-07-18 — Deterministic sanitizer and Valgrind regression coverage

- Governed run `5665167f1c1d`,
  `deterministic_sanitizer_valgrind_regression_coverage`, added explicit
  sanitizer/Valgrind preflight, per-target `mktemp` binaries, `SYSDIFF_BIN`
  routing through shell and pytest coverage, leak-fatal ASan policy,
  halt-on-error UBSan policy, and Valgrind status-99/error-log enforcement. Normal
  `build/sysdiff` is not replaced by an instrumented binary.
- Step-1 validation passed exactly: both shell syntax checks (`bash -n` on
  `tests/test_sysdiff.sh` and `tests/test_sysdiff_fixture.sh`); 18 tests passed
  in 0.59 s for
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
  tests/test_check_tools.py -q`; `make test-sanitize` exited 0; and `make
  test-valgrind` exited 0.
- Governed user smoke passed its pinned manifest-oracle validation;
  `artifacts/user-smoke/result.json` records both flows true, start/check exit
  codes 0, and no blocking errors. This is distinct from the stale historical
  `.agent-orch/user-smoke/result.json` identified by review finding F1.
- Independent review artifacts are
  `code-reviews/review-deterministic-memory-gates.md` and `.verdict.json`.
  Verdict: `pass` at the High threshold, with no High/Critical findings, four
  Medium findings, and six Low findings. The review's only allowlisted command
  was `python3 -m pytest -p no:cacheprovider tests/test_check_tools.py -q`,
  which exited 0 with 18 passed in 0.57 s; it did not freshly rerun the
  sanitizer or Valgrind targets.
- Medium risks remain: stale legacy smoke hashes (F1); implicit POSIX
  `SIGPIPE` exposure that is not portable from glibc to musl under the current
  strict-C flags (F2); shell `/dev/full` and closed-pipe helpers that bypass
  Valgrind, although pytest covers closed-pipe (F3); and no detector negative
  control (F4). Six Low findings cover unused/duplicated Valgrind command
  construction, stale routed-harness defaults, ordinary pytest cache hygiene,
  overstated smoke-layer independence, missing `man-check` temp cleanup trap,
  and a preflight probe that links but does not execute.
- Host availability remains a real boundary: gates require Linux, Clang with
  usable ASan/UBSan runtimes, and GCC plus Valgrind. The current host passed
  compile/link preflights and full implementation validation; unsupported or
  incomplete hosts fail loudly rather than silently skip.
- Recommended next action: regenerate the stale legacy smoke evidence against
  the current tree, then use a bounded governed repair slice for F2-F4. Do not
  infer a release, a fresh `make quality`, or broader platform support from
  this threshold-High review pass.

## Sysdiff Release Documentation Set

- Governed run `e7bbd28465b5`, playbook
  `sysdiff_complete_release_documentation_set`, authored and repaired the root
  release docs (HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, STATUS) and
  reconciled README, CHANGELOG, architecture, and `man/sysdiff.1` without
  executing compilers, builds, or the full quality gate in those write steps.
- User smoke gate (`step_03_user_smoke_gate` attempt 1) passed:
  `artifacts/user-smoke/result.json` reports `app_started: true`,
  `core_flow_completed: true`, `start_exit_code: 0`, `check_exit_code: 0`, and
  empty `blocking_errors`, with pinned smoke-manifest hashes validated.
- Independent review
  `code-reviews/sysdiff-release-documentation-review.verdict.json` is `pass`
  (High/Critical threshold). Allowlisted check
  `python3 -m compileall tests/test_check_tools.py` exited 0. Two Low findings
  remain: F1 NAME uses `\(em` instead of ` \- ` for whatis/apropos; F2 FILES
  directory wording is imprecise about open-vs-read failure on Linux.
- This slice confirms documentation fidelity and smoke continuity; it does not
  claim a fresh `make quality` or a new product-release gate beyond prior
  recorded evidence.

## 2026-07-10 — Section-1 manual page ready for publication

- Added `man/sysdiff.1` with exact CLI, format, escaping, limits, security,
  output, exit-status, example, copyright, and version documentation.
- Added `make man-check`; it captures groff diagnostics and fails on either a
  nonzero render or any warning. `make quality` and Ubuntu CI include this gate;
  CI installs groff.
- Reconciled README, changelog, decisions, design, specification, and release
  review. The key grammar now says exactly that consecutive dots (`..`) are
  rejected.
- Final governed `make quality` exited `0`: groff lint, strict compilers,
  static analysis, 41 tests, leak-enabled ASan, UBSan, and Valgrind passed.
- GitHub authentication is active as `leebase`; no remote existed before this
  publication step.
- Created and pushed `https://github.com/leebase/linux-utilities` from the clean
  seed. Public commits are `255bdde` (man page), `8abf062` (noninteractive CI
  install), and `fbdf071` (checkout v6).
- Initial CI run `29119319248` was cancelled after hosted apt stalled for over
  six minutes. The bounded repair added noninteractive apt/needrestart handling
  and a 15-minute job timeout.
- CI run `29119799430` passed but exposed a Node 20 deprecation annotation from
  checkout v4. The official immutable checkout-v6 pin removed it.
- Final CI run `29119972847` passed the Ubuntu `make quality` job in full with
  zero annotations on commit `fbdf071`.

## 2026-07-10 — Adversarial public-release remediation

- Final evaluator rejected the first seed with five Medium findings: raw
  terminal-control output, successful exit on stdout loss, multi-gigabyte
  aggregate input exposure, non-gating Valgrind/cppcheck behavior, and stale
  public docs.
- Cursor `agent` using `grok-4.5-high` wrote tests and implementation through
  eight bounded review iterations. The planner independently reviewed every
  diff and returned C/POSIX/static-analysis findings until clean.
- Added printable-ASCII byte escaping for values and untrusted diagnostics,
  checked stdout/flush/EPIPE handling, a 16 MiB per-snapshot total-byte limit,
  byte-limit/NUL precedence, Valgrind status 99 with error-log enforcement,
  gating cppcheck, a normal default build, leak-enabled ASan, immutable CI
  action pinning, and adversarial fixtures.
- Governed pytest now reports 41 passing tests. Final post-documentation
  `make quality` completed with exit status `0`, including the final Valgrind
  fixture success line.
- Public docs now record the rejected findings and repairs. Remaining Low
  limitations are explicit and do not block making the repository public; the
  GitHub release itself must wait for first-remote CI success.

## 2026-07-10 — v0.1.0 release candidate prepared

- Verified the governing run `eab8bbd05f50` is `COMPLETED`; its prior smoke
  result is historical rather than release evidence.
- Resolved its F001–F004 follow-ups: portable pytest compiler selection,
  immediate smoke start, whitespace-only blank-line handling with shell and
  pytest coverage, and removal of the unreachable `copy_range` `SIZE_MAX`
  guard.
- Added Ubuntu CI that installs the tools required by `make quality` and runs
  that exact command. Added public release documentation, contribution guide,
  MIT placeholder license, changelog, AI-development safeguards, and a fresh
  release review.
- Historical first-pass verification: `make quality`; pytest reported 26 passed.
  The quality gate includes GCC/Clang strict builds, formatting, clang-tidy,
  cppcheck, fixtures, pytest, ASan, UBSan, and Valgrind.
- Accepted Low limitation: changed output is human-readable and not reversible
  when opaque values contain ` -> `. No Medium-or-higher findings remain.

## 2026-07-10 — Fixture acceptance-test slice delivered

- Completed Agent-Orch run `eab8bbd05f50`,
  `sysdiff_fixture_diff_acceptance_tests`, through review and into closeout
  handoff. Steps authored fixture acceptance tests, verified fixture compare
  behavior, passed the pinned user smoke gate, and wrote the review artifacts.
- Review files:
  `code-reviews/review-sysdiff-fixture-acceptance-tests.md` and
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`.
- Verdict is `pass` at the High severity threshold, with no High or Critical
  findings. Review check `python3 -m pytest tests/ -q` exited `0` (26 tests
  collected and passed in 0.40 s across `tests/test_sysdiff.py` and
  `tests/test_check_tools.py`).
- Smoke evidence in `artifacts/user-smoke/result.json` records
  `app_started: true`, `core_flow_completed: true`, `check_exit_code: 0`, empty
  `blocking_errors`, and `start_exit_code: -15` (SIGTERM from the start-helper
  timeout mismatch).
- Delivered acceptance coverage includes status 0/1/2, exact sorted stdout for
  mixed add/remove/change, ordering independence, comments/blank lines, CRLF
  and mixed-ending equivalence, line/entry resource limits, empty stdout on
  error paths including malformed after-path cases, and pytest coverage for
  help/version, comparisons, malformed input, and opaque `file.` keys.
- The review notes `main` now guards `argc < 1` before `argv[1]` use, and that
  `Makefile` `valgrind-test` cleans and rebuilds with strict GCC flags before
  Valgrind.
- Historical findings from this verdict, resolved by the 2026-07-10 release
  preparation: F001 Medium (`tests/test_sysdiff.py`
  hardcodes `gcc`); F002 Medium (`tests/smoke_start.py` 30 s sleep vs 10 s
  startup timeout); F003 Low (whitespace-only lines rejected vs contract blank
  wording); F004 Low (unreachable `copy_range` `SIZE_MAX` guard).

## 2026-07-09 — Output format approved and C craftsmanship gate set

- Lee approved the current `sysdiff` format-1 diff output:
  `+ key=value`, `- key=value`, and `~ key: old -> new`.
- Lee approved keeping and committing the current overnight sysdiff work on
  `main`.
- Before additional sysdiff feature work, run a C craftsmanship review covering
  `src/sysdiff.c`, `Makefile`, tests, smoke manifest, and user-facing docs.
  Medium-or-higher craftsmanship findings should block new feature slices.
- Future OpenAI/Codex routes should use `gpt-5.5`; do not add GPT-5.4
  assignments.

## Previous completed work

- Completed the C craftsmanship review in Agent-Orch run `c434e00a3772`,
  `craftsmanship_review_closeout`. Verdict
  `code-reviews/craftsmanship-review.verdict.json` was `pass` at the
  High/Critical threshold. Several of its findings overlap the current fixture
  acceptance verdict (portable pytest compiler choice; smoke-start timeout).
  Fixture acceptance coverage and the `argc < 1` guard supersede the earlier
  missing CRLF/resource-limit test and `argc == 0` concerns for planning
  purposes; treat the latest fixture-acceptance verdict as current.
- Applied the narrow Makefile quality-gate action: `Makefile` includes `check`
  in `.PHONY` and adds `check: test-suite`. Follow-up review
  `code-reviews/review-makefile-quality-gates.verdict.json` passed at the High
  threshold; the fixture-acceptance review now reports that standalone
  `valgrind-test` cleans/rebuilds before Valgrind.
- Advanced Agent-Orch run `c02d741432d3`,
  `sysdiff_c_source_implementation`, through review and closeout. It added
  `docs/sysdiff-c-source-contract.md` and
  `plans/sysdiff-c-source-implementation-plan.md`, hardened `src/sysdiff.c`,
  updated `Makefile`, documented limits in `README.md`, passed smoke, and
  passed review at the High threshold.
- The previous governed run `5ff82aa95e06`,
  `sysdiff_fixture_smoke_repair`, completed closeout. It changed only
  `tests/smoke_manifest.json` and `tests/test_sysdiff_fixture.sh`, passed
  smoke and review, and resolved prior smoke-fixture findings F-001 Medium and
  F-002 Low by enforcing exact diff order and stronger diff-line checks.
- The previous routed tool-availability run `b6deb04a6055` added
  `scripts/check_tools.py`, tests, docs, and README discoverability for the
  default `codex_cli` and `claude_code` harness checks. Its review verdict
  `code-reviews/review-tool-availability-check.verdict.json` reports `pass` at
  a High severity threshold with two Low findings still open.
- Earlier `sysdiff` core history remains relevant: the changed-line ambiguity
  finding for values containing ` -> ` remains outside the fixture acceptance
  slice and is still visible for future output-format work.

## Verification

- Final post-documentation `make quality` — exit `0`; strict GCC/Clang,
  clang-format, clang-tidy, gating cppcheck, 41 pytest tests, shell fixtures,
  leak-enabled ASan, UBSan, and Valgrind all passed.
- Official `actions/checkout` lookup — pinned SHA
  `34e114876b0b11c390a56381ad16ebd13914f8d5` matches `refs/tags/v4`.
- Post-man-page `make quality` — exit `0`; includes warning-gated groff render,
  41 governed tests, sanitizers, and Valgrind.

- `python3 -m pytest tests/ -q` — exit `0`; 26 tests passed (fixture-acceptance
  review check)
- Agent-Orch `SmokeTestAdapter` / user smoke gate for `eab8bbd05f50`
  `step_04_user_smoke_gate` attempt 1 against `tests/smoke_manifest.json`;
  evidence: `artifacts/user-smoke/result.json` (`check_exit_code: 0`,
  `start_exit_code: -15`, no blocking errors)
- Prior craftsmanship checks from run `c434e00a3772` remain historical evidence
  only; current open findings are those in
  `code-reviews/review-sysdiff-fixture-acceptance-tests.verdict.json`
