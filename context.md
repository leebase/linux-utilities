# Context

## Snapshot

Governed recovery run `4ae7a820b0a3` (`repair_governed_run_6ca4cebc8527`)
reconciled the dirty pathaudit maintenance candidate left by failed run
`6ca4cebc8527` and obtained a clean independent review. Exact focused
pathaudit pytest is 151 passed / 15 skipped. Step-5 static gates on
`src/pathaudit.c` (GCC/Clang `-fsyntax-only`, clang-format, clang-tidy,
cppcheck, Clang analyzer) all exited 0. Step-6 ASan+UBSan and Valgrind
pathaudit routes each reported 151 passed / 15 skipped. Step-7 complete
suite recorded 343 passed / 15 skipped under a scratch writable gitdir.
Governed smoke (`artifacts/user-smoke/result.json`) passed with
`app_started`/`core_flow_completed` true, start/check exit 0, empty
`blocking_errors`; check.log pytest `340 passed, 18 skipped in 22.01s`.
Independent verdict
`code-reviews/review-pathaudit-governed-run-6ca4cebc8527.verdict.json`
is `pass` and closes `pathaudit-shadow-1/2/3`. Remaining findings are
Medium PA-6CA-4 (review-worker complete-suite/`git worktree` EROFS
environment note; not a pathaudit product defect) and Low PA-6CA-1/2/3.
Failed run `6ca4cebc8527` itself is still not a passed delivery.

## What's Happening Now

Closeout records the reviewed recovery without claiming that failed run
`6ca4cebc8527` passed, without releasing pathaudit, and without closing
unrelated backlogs. Live product state remains three implemented utilities
plus planning-only `inodealias` and `shebangcheck`. Permguard Medium
PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512 still require
bounded governed repair plus fresh independent review before feature
expansion. Keep Low PA-6CA-1/2/3 and Medium PA-6CA-4 visible; do not treat
PA-6CA-4 as a pathaudit regression. Fifth-mission selection risks
FUM5-M1/M2 and FUM5-L1–L4 remain open planning notes. Next action: clear
the active permguard Medium-or-higher expansion gates, then generate a
separate governed `shebangcheck` implementation playbook beginning with
its normative contract. Runs root:
`/home/lee/projects/linux-utilities-agent-orch-runs`.

## Prior snapshot — fifth utility mission evaluation `e5f6740c1571`

Governed run `e5f6740c1571`
(`discover_evaluate_fifth_linux_utility`) selected exactly one fifth mission:
bootstrap `shebangcheck` for read-only validation of direct absolute
interpreters named by explicitly supplied script files. The bounded first
vertical slice is planning only: inspect explicit regular-file operands, read
a contract-capped first line or prefix, accept only a closed direct-absolute-
interpreter shebang subset, inspect the named interpreter without executing
it or searching PATH, and emit deterministic escaped findings for malformed,
unsupported, or unusable cases. Exact CLI, output bytes, finding taxonomy,
resource constants, diagnostics, signal behavior, and numeric exit statuses
remain for a later normative implementation contract. The independent review
verdict is `pass` with no Critical or High findings, two Medium findings
(FUM5-M1 and FUM5-M2), and four Low findings (FUM5-L1 through FUM5-L4).
This selection does not implement, verify, install, package, tag, publish, or
release `shebangcheck`; live product state remains three implemented utilities
and planning-only fourth mission `inodealias`. At that closeout, failed
pathaudit maintenance run `6ca4cebc8527` was still dirty and unreviewed;
recovery run `4ae7a820b0a3` now supersedes that maintenance posture for
`pathaudit-shadow-1/2/3` while leaving the failed origin run as not a passed
delivery.

## Prior snapshot — permguard first vertical slice `f742c10135e5`

Governed run `f742c10135e5` delivered and reviewed a one-code
`WORLD_WRITABLE_FILE` slice under
`docs/permguard-first-vertical-slice-contract.md`. Independent allowlisted
focused pytest was 67 passed / 0 skipped; verdict `pass` with Medium
PG-REV-301/302 and Low PG-REV-202/203/205/206/303/304. Run `51100a584ac9`
supersedes that product authority with the four-code bootstrap contract;
retain the prior section as historical closeout evidence only.

## Prior snapshot — permguard delivery `629d1f459446`

Governed run `629d1f459446` delivered and reviewed the same live single-code
first-slice contract after repairing High PG-DOC-101, which had been caused by
stale four-code contract and plan files. Its independent review ran focused
pytest at 66 passed / 0 skipped and passed with Medium PG-REV-201 plus Low
PG-REV-202–207. Run `f742c10135e5` supersedes that closeout evidence: it
confirmed PG-REV-201/204/207 resolved and recorded the current findings above.

## Prior snapshot — permguard bootstrap `a8341dfae9f2`

Governed run `a8341dfae9f2` (`bootstrap_permguard_first_vertical_slice`)
completed an earlier reviewed four-code bootstrap. Independent verdict
`code-reviews/review-permguard-bootstrap.verdict.json` was `pass` with Medium
PG-DOC-001/PG-TEST-002 and Low PG-DIAG-003/PG-PORT-004/PG-CLI-005. That cycle's
contract/plan filenames were later deleted during `629d1f459446` High
PG-DOC-101 repair; live four-code authority is now restored by run
`51100a584ac9` under `docs/permguard-bootstrap-contract.md`. Retain this
section as historical evidence only.

## Prior snapshot — Detect unsafe ownership of PATH directories

Governed run `50c0b4936d50` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect unsafe
ownership of PATH directories for `pathaudit --path` and
`pathaudit --command`: every usable PATH directory and each ancestor
through `/` inherits the executable ownership trust rule (UID 0 and
invoking real UID from `getuid()`, not `geteuid`); untrusted final-target
`st_uid` emits `UNSAFE_OWNER` on the canonical offending directory
`realpath`; shared ancestor realpaths deduplicate to the lowest PATH
index; missing, empty, and non-directory components invent no ownership
lines; `owner_uid_is_trusted` is shared with executable ownership so
policy cannot drift; explicit-root mode stays ownership-blind and never
emits directory or ancestor `UNSAFE_OWNER`. Exact deliverables:
`tests/test_pathaudit.py`, `src/pathaudit.c`, `README.md`, `SECURITY.md`.
Exact step-2 verification: `make clean && make` → 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 280 passed, 18 skipped in 26.84s. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`280 passed, 18 skipped in 20.40s`. Independent review
`code-reviews/review-path-directory-ownership.{md,verdict.json}`
verdict `pass`: 0 Critical/High/Medium findings and one Low finding
(`path-dir-ownership-1`: O(N²) linear dedup scan of `UNSAFE_OWNER`
findings under a hostile all-foreign-owned PATH; bounded by input
limits; non-blocking). Allowlisted review check:
`python3 -m pytest -p no:cacheprovider tests/test_pathaudit.py -q` →
143 passed, 15 skipped in ~1.8s. The 15 skips are host-capability
self-skips (no distinct foreign UID / unprivileged `chown`, oversized-
PATH env rejection), not failures. This does **not** claim that
`pathaudit` is released or that the sysdiff smoke oracle directly
exercises directory-ownership `--path` / `--command` behavior.
