# Context

## Snapshot

Governed run `2b2fb272c21a` (playbook
`template_repair_before_review_feature_delivery`) delivered bounded
command-specific PATH risk inspection for `pathaudit --command NAME`:
walks process `PATH` in resolution order for one basename, emits
`MATCH` lines then applicable shared-taxonomy hazards (plant risk
before the winner), rejects empty or slash-containing names as
`INVALID_COMMAND`, and filters to single-basename regular `X_OK`
matches only. Exact deliverables: `src/pathaudit.c`,
`tests/test_pathaudit.py`, `README.md`, `man/pathaudit.1`. Exact
step-4 verification: `make clean && make test` → 230 passed, 1
skipped; `python3 -m pytest tests/ -q` → 230 passed, 1 skipped;
format/tidy/cppcheck/analyzer/man-check and
`pathaudit-sanitize`/`pathaudit-valgrind` exited 0; pathaudit suite →
90 passed, 1 skipped. Exact smoke (`artifacts/user-smoke/result.json`):
`app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`230 passed, 1 skipped in 18.98s`. Independent review
`code-reviews/review-command-specific-path-risk.{md,verdict.json}`
verdict `pass`: 0 Critical/High/Medium, 2 Low (pathaudit-cmd-1
near-duplicate `classify_command_component` vs `classify_root`;
pathaudit-cmd-2 dead `len==0` disjunct in `root_is_cwd_dependent`).
Allowlisted review check: `python3 -m pytest tests/ -q` → 230 passed,
1 skipped (~18.7s). The skip is the host-limited `--path`
`ROOT_BYTES_LIMIT` probe. This does **not** claim that `pathaudit` is
released, that `make install` ships it, or that the sysdiff smoke
oracle directly exercises `--command`.

## What's Happening Now

Handoff after run `2b2fb272c21a`: command-specific PATH risk inspection
is implemented, smoke-gated, and independently reviewed with verdict
`pass`. Remaining risks from this review are Low only:
pathaudit-cmd-1 and pathaudit-cmd-2. Prior Low pathaudit-wdp-1/2,
PA-WP-1–PA-WP-4, bootstrap Medium PA-M1/PA-M2 leftovers, and sysdiff
Medium packaging backlogs remain separately visible and were not
closed by this review. Smallest next action: keep Low
pathaudit-cmd-1/2 and prior Low findings visible for optional polish;
resume prior Medium backlog repair (pathaudit PA-M2 hostile-byte
stderr fixture / PA-M1 architecture leftovers and sysdiff packaging
Mediums) without claiming release or that the sysdiff smoke oracle
covers `--command` behavior. Runs root:
`/home/lee/projects/linux-utilities-agent-orch-runs`.
