# Context

## Snapshot

Governed run `51100a584ac9` (`bootstrap_permguard_first_vertical_slice`)
delivered and independently reviewed the live `permguard` bootstrap under
`docs/permguard-bootstrap-contract.md`. The ISO C17 utility accepts
`permguard [--] PATH...` plus sole-argument `--help` / `--version`, performs
exactly one `lstat` per operand, never follows the final symlink, streams
findings per operand, and continues after per-operand errors. Its closed
four-code taxonomy emits `GROUP_WRITABLE`, `OTHER_WRITABLE`, `SET_USER_ID`,
and `SET_GROUP_ID` from the named object's own mode bits without file-type
heuristics; final symlinks are status-2 rejections. Operand bytes are escaped,
and exits are 0 clean, 1 hazards-only, or 2 operational failure (with error
precedence over hazards). Delivered artifacts are the bootstrap contract and
plan, `src/permguard.c`, `tests/test_permguard.py`, `man/permguard.1`,
README/CHANGELOG documentation, and additive Makefile wiring. Independent
verdict `code-reviews/review-permguard-bootstrap.verdict.json` is `pass` with
5 Medium and 6 Low findings. This reviewed bootstrap is not a release and does
not provide recursion, PATH reading, remediation, or packaging.

## What's Happening Now

Closeout for `51100a584ac9` records evidence by provenance. Independent review
freshly ran only
`python3 -m pytest -p no:cacheprovider tests/test_permguard.py -q` → exit 0,
52 passed in 0.43s, zero skipped; its session fixture transitively performed a
strict-warning build into a temp tree, but review did not freshly run Make,
the full suite, sanitizers, Valgrind, or static analyzers as gate results.
Step-5 quality-floor validation recorded GCC/Clang strict syntax, clang-format,
clang-tidy, cppcheck, Clang analyzer, ASan+UBSan `--help` and Valgrind `--help`
probes, full pytest `332 passed, 18 skipped`, and both shell fixture suites
exiting 0; the quality worker separately reported focused pytest 52 passed.
Smoke `artifacts/user-smoke/result.json` records start/check 0 and empty
`blocking_errors`; check.log records `332 passed, 18 skipped in 19.78s` through
`make test`, which reaches permguard transitively but is not a
permguard-specific user flow. One-code drafts
`docs/permguard-first-vertical-slice-contract.md` /
`plans/permguard-first-vertical-slice-plan.md` are superseded non-authority.
Next: bounded governed repair of Medium PG-DOC-501 (architecture taxonomy
mismatch), remaining PG-DOC-502 draft markers, PG-TEST-503 (`STDOUT_WRITE` /
SIGPIPE coverage), PG-PORT-505 (hand-declared `lstat`), and PG-DOC-512
(QUALITY/TESTING silence), then fresh independent review. Keep Low
PG-CRAFT-506/PG-TEST-507/PG-CLI-508/PG-MAKE-509/510/511 visible. Do not claim
installation, packaging, publication, recursion, remediation, or release
readiness. Runs root: `/home/lee/projects/linux-utilities-agent-orch-runs`.

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
