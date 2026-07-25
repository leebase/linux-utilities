# Context

## Snapshot

Governed run `f94509b47fd3` (playbook
`template_repair_before_review_feature_delivery`) delivered Detect
executable shadowing across PATH entries for `pathaudit --path`: first
regular `X_OK` basename in PATH order is the winner; later distinct
`realpath` hits emit `SHADOWED` lines (`SHADOWED\t"cmd"\t"winner"\t"shadow"`)
after shared-taxonomy directory hazards, ordered by command bytes then
PATH index; explicit-root never emits `SHADOWED`; empty/missing/
non-directory/unreadable components are skipped for the scan; no nested
recursion. Exact deliverables: `tests/test_pathaudit.py`,
`src/pathaudit.c`, `README.md`. Exact step-4 verification: `gcc`/`clang
-std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/pathaudit.c`
→ 0; `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 247 passed, 1 skipped. Exact smoke
(`artifacts/user-smoke/result.json`): `app_started: true`,
`core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, empty `blocking_errors`; check.log pytest
`247 passed, 1 skipped in 18.41s`. Independent review
`code-reviews/review-executable-shadowing.{md,verdict.json}` verdict
`pass`: 0 Critical/High, 1 Medium (pathaudit-shadow-1 retained 64 KiB
realpath buffer per winner/shadow), 2 Low (pathaudit-shadow-2 quadratic
winner lookup; pathaudit-shadow-3 duplicate SHADOWED on repeated
non-winner dirs). Allowlisted review check:
`python3 -m pytest tests/ -q -p no:cacheprovider` → 247 passed, 1
skipped (~17.95s). The skip is the host-limited `--path`
`ROOT_BYTES_LIMIT` probe. This does **not** claim that `pathaudit` is
released or that the sysdiff smoke oracle directly exercises
executable-shadowing `--path` detection.

## What's Happening Now

Handoff after run `f94509b47fd3`: Detect executable shadowing across
PATH entries is documented, smoke-gated, and independently reviewed
with verdict `pass`. Remaining risks from this review: Medium
pathaudit-shadow-1 and Low pathaudit-shadow-2/3. Prior Low nondir-1/2,
pathaudit-cmd-1/2, pathaudit-wdp-1/2, PA-WP-1–PA-WP-4, bootstrap Medium
PA-M1/PA-M2 leftovers, and sysdiff Medium packaging backlogs remain
separately visible and were not closed by this review. Smallest next
action: keep Medium pathaudit-shadow-1 and Low pathaudit-shadow-2/3
visible; prefer repairing pathaudit-shadow-1 (right-size retained
realpath buffers) or resume prior Medium backlog (pathaudit PA-M2 /
PA-M1 leftovers and sysdiff packaging Mediums) without claiming
release or that the sysdiff smoke oracle covers shadowing `--path`
behavior. Runs root:
`/home/lee/projects/linux-utilities-agent-orch-runs`.
