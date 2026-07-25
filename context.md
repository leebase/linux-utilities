# Context

## Snapshot

Governed run `35116f657f35` (playbook
`detect_non_directory_path_entries`) delivered Detect non-directory PATH
entries for `pathaudit --path` and explicit roots: pins
`NON_DIRECTORY_ROOT` for regular-file, symlink-to-file, and ENOTDIR
components (status 1, empty stderr), mutually exclusive with
`MISSING_ROOT`, with permission findings suppressed on non-directory
roots. Exact deliverables: `tests/test_pathaudit.py`, `src/pathaudit.c`
(comment-only classify_root clarification), `README.md`,
`man/pathaudit.1`. Exact step-3 verification (non-writing):
`clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only
src/pathaudit.c` → 0; `cppcheck --quiet --enable=all
--suppress=missingIncludeSystem src/pathaudit.c` → 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 234 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`234 passed, 1 skipped in 19.50s`. Independent review
`code-reviews/review-detect-non-directory-path-entries.{md,verdict.json}`
verdict `pass`: 0 Critical/High/Medium, 2 Low (nondir-1 special-file
fixture gap vs comment; nondir-2 classify_root vs
classify_command_component taxonomy duplication). Allowlisted review
check: `python3 -m pytest -p no:cacheprovider tests/test_pathaudit.py
-q` → 94 passed, 1 skipped (~1.9s). The skip is the host-limited
`--path` `ROOT_BYTES_LIMIT` probe. Runtime `NON_DIRECTORY_ROOT` logic
pre-existed; this slice documents and pins it. This does **not** claim
that `pathaudit` is released or that the sysdiff smoke oracle directly
exercises non-directory `--path` detection.

## What's Happening Now

Handoff after run `35116f657f35`: Detect non-directory PATH entries
is documented, smoke-gated, and independently reviewed with verdict
`pass`. Remaining risks from this review are Low only: nondir-1 and
nondir-2. Prior Low pathaudit-cmd-1/2, pathaudit-wdp-1/2,
PA-WP-1–PA-WP-4, bootstrap Medium PA-M1/PA-M2 leftovers, and sysdiff
Medium packaging backlogs remain separately visible and were not
closed by this review. Smallest next action: keep Low nondir-1/2 and
prior Low findings visible for optional polish; resume prior Medium
backlog repair (pathaudit PA-M2 hostile-byte stderr fixture / PA-M1
architecture leftovers and sysdiff packaging Mediums) without claiming
release or that the sysdiff smoke oracle covers non-directory `--path`
behavior. Runs root:
`/home/lee/projects/linux-utilities-agent-orch-runs`.
