# Context

## Snapshot

Future Mission Discovery plan `plans/next-linux-utility-evaluation.md` was
independently reviewed
(`code-reviews/review-next-linux-utility-evaluation.{md,verdict.json}`) with
verdict `pass` (0 Critical/High/Medium; 2 Low:
`permguard-writability-overlap`, `first-slice-scope-breadth`). Chosen mission:
bootstrap `permguard` as the third suite utility. Pathaudit completion
boundary: capability-complete for v1 product scope (explicit-root, `--path`,
`--command`, in-tree quality floor) without requiring further detector
expansion before the next utility; pathaudit remains unreleased and sysdiff
smoke does not cover it. First vertical slice: `permguard [--] PATH...`
explicit-root permission scanner (closed taxonomy including writability,
`UNSAFE_OWNER`, `SETUID`/`SETGID`, `STICKY`; no recursion, no PATH read, no
remediation). Review checks were plan-evidence only (`compileall` on
`tests/test_pathaudit.py`, `git tag -l` → `v0.1.0`, `wc -l src/pathaudit.c`
→ 1849, taxonomy grep); this handoff does not claim permguard implementation,
a pathaudit/sysdiff release, or that smoke exercised the evaluation.

## What's Happening Now

Recorded the reviewed next-utility selection into AgentFlow without
implementing code. Next executable action: author and launch a governed
playbook to bootstrap the `permguard` explicit-root vertical slice
(`docs/permguard-contract.md`, `src/permguard.c`, `man/permguard.1`,
`tests/test_permguard.py`, Makefile wiring) under existing strict C/quality
gates. Keep evaluation Low findings visible; keep prior pathaudit Medium/Low
and sysdiff packaging Medium backlogs visible as ordinary repair, not
blockers for starting permguard. Do not schedule pathaudit-only polish or
renewed sysdiff release work; do not claim pathaudit or permguard released.
Runs root: `/home/lee/projects/linux-utilities-agent-orch-runs`.

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
