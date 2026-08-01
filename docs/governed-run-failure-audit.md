# Governed-Run Failure Audit

## Audit Scope

This document audits every governed Agent-Orch run that reached a terminal
`FAILED` status in the durable runs root `../linux-utilities-agent-orch-runs/`,
and classifies each failure using the closed set required for this slice:
**shared smoke failure**, **allowed-path defect**, **product defect**, or
**unknown due to insufficient evidence**. It exists so that playbook authors,
recovery workers, and human approvers can tell an infrastructure halt apart
from a genuine product regression before they rewrite source, weaken an oracle,
or relabel a Failed origin run as passed.

The audit is documentation-only. It changed no source file, test, manifest,
script, smoke asset, playbook, `code-reviews/` verdict, or AgentFlow historical
record (`context.md`, `result-review.md`, `HISTORY.md`, `sprint-plan.md`,
`STATUS.md`, `WHERE_AM_I.md`, `CHANGELOG.md`). The only write performed by this
slice is this file under `docs/`. The smoke workflow was **not** executed; every
smoke statement below is read from recorded run evidence and from the pinned
asset bytes, never from a fresh run. No build, sanitizer, Valgrind, packaging,
install, tag, publication, or release claim is made or implied, and no open
Medium/Low finding is closed by assertion.

Two scope boundaries matter for reading the classifications:

1. **The runs root is shared between two workspaces.** `run.json` `workspace_dir`
   records `/home/lee/projects/linux-utilities` for every run started before
   `2026-07-29T17:09:31Z`, and `/home/lee/projects/linux-utilities-autonomous`
   from run `6e89123d0c4b` (`2026-07-29T17:09:31Z`) onward — the same timestamp
   recorded in `.agent-orch/validated-pairings.json`. Eleven of the twenty
   Failed runs therefore executed against the *sibling* workspace. Their halting
   signals are still durable and are audited here, but they are not attributable
   to the current bytes of `src/`, `tests/`, or `Makefile` in this repository,
   and this is stated per finding rather than assumed away.
2. **Product attribution, not blame assignment.** A class label answers only
   "does the durable record support attributing this halt to product bytes, to
   the step's allowed-path contract, or to the shared smoke oracle?" Where the
   record fixes the halting signal but not a product cause, the label is
   *unknown due to insufficient evidence*, and the observed mechanism is named
   explicitly so the label is not read as "nothing is known".

Inputs read for this audit: `AGENTS.md`, `OPERATE.md`, `context.md`,
`result-review.md`, `HISTORY.md`, `QUALITY.md`, `TESTING.md`,
`docs/governed-run-ea8936c67cef-repair.md`,
`tests/test_governed_run_9add44496178.py`,
`tests/test_governed_run_c847e01d15fe.py`, the pinned smoke assets
(`tests/smoke_manifest.json`, `tests/smoke_start.py`,
`tests/check_sysdiff_smoke.py`, `scripts/smoke.sh`), the `Makefile` test
targets, and the durable `run.json`, `playbook.json`, `validation.json`,
`worker_result.json`, `route-selection.json`, `stdout.log`, and `stderr.log`
records under `../linux-utilities-agent-orch-runs/`.

## Evidence Inventory

Twenty runs carry `status: FAILED` in `run.json`; one run (`9849a238752a`) was
`RUNNING` while this audit was authored and is excluded. The table lists the
step that halted, the observed outcome verbatim from the durable record, and the
assigned class.

| Run | Workspace | Playbook (`playbook_id`) | Halting step | Observed outcome (durable) | Class |
| --- | --- | --- | --- | --- | --- |
| `b24f4b8fe03e` | sibling | `template_repair_before_review_feature_delivery` | `step_03_user_smoke_gate` | both attempts: `check_exit_code: -1`, `"Smoke check did not pass before startup timeout."` | shared smoke failure |
| `e02facf58b3e` | sibling | `pathaudit_operator_documentation_and_man_page` | `step_02_user_smoke_gate` | both attempts: identical smoke timeout stdout | shared smoke failure |
| `8333eae22551` | this repo | `audit_recurring_governed_run_failure_causes` | `step_03_user_smoke_gate` | both attempts: identical smoke timeout stdout | shared smoke failure |
| `f4d805b7b217` | this repo | `repair_failed_governed_run_af89bd4b8fcd` | `step_08_user_smoke_gate` | both attempts: identical smoke timeout stdout | shared smoke failure |
| `af89bd4b8fcd` | this repo | `repair_governed_run_9add44496178` | `step_03_code_repair` | attempt 2 `HALT`: worker exit 0, clang clean, `74 passed`, only failures `Changed path outside allowed_paths: tests/test_governed_run_9add44496178.py` and `tests/test_sysdiff.sh` | allowed-path defect |
| `6ca4cebc8527` | this repo | `pathaudit_maintenance_repairs` | `step_05_test_fix_and_verify_pathaudit` | attempt 1 `RETRY`: `Changed path outside allowed_paths: docs/pathaudit.md`, `tests/test_sysdiff.py`; five validation commands failed on unexpanded literal `src/*.c`; attempt 2 exit `124` at 1500 s | allowed-path defect (primary), see also glob signature |
| `ab4d8a7348ee` | sibling | `repair_failed_governed_run_c847e01d15fe` | `step_03_review_repaired_artifacts` | attempt 1 of step 1: `Changed path outside allowed_paths: sysdiff-release.tar.gz`, `sysdiff-release.tar.gz.sha256` (recovered); run halted later on a third `fail` verdict | allowed-path defect (non-fatal) + unknown for the halt |
| `ba6dc2fdd199` | this repo | `complete_permguard_medium_repairs` | `step_03_implement_medium_repairs` | `gcc`/`clang` `-Werror`: `src/permguard.c:213:9: error: implicit declaration of function 'lstat'`; focused pytest `FFF` on `test_medium_ac01_closed_finding_scope_and_authority` and two neighbours | product defect |
| `9add44496178` | this repo | `bootstrap_openunlink_release_quality_vertical_slice` | `step_04_implement_openunlink` | both attempts: identical `tests/test_openunlink.py` failure set; `test_seam_numeric_ordering_and_duplicates` `At index 31 diff: b'3' != b'1'`; `test_seam_fd_count_65537_preserves_retained_finding` byte mismatch | product defect |
| `ea8936c67cef` | this repo | `permguard_hostile_filesystem_fixtures` | `step_07_independent_review` | both attempts: `checks_run` for `python3 -m pytest tests/ -q` — `reviewer claimed exit 1, orchestrator observed exit 0` | unknown due to insufficient evidence |
| `f7539c314ca1` | this repo | `discover_evaluate_seventh_linux_utility` | `step_02_discover_and_evaluate` (after review re-entry) | review attempt 1 same `checks_run` mismatch; review attempt 2 verdict `fail` on High `SEV7-H1`; step-2 attempts 2 and 3 exit `124` under `timeout_seconds: 600` | unknown due to insufficient evidence |
| `39a591579075` | this repo | `discover_and_evaluate_seventh_linux_utility` | `step_02_evaluate_candidates` | attempts 1 and 2 exit `124` with the `codex_cli` banner `Reading additional input from stdin...`; attempt 1 also `File not found: plans/seventh-utility-mission-evaluation.md`; attempt 2 `Semantic check failed` (frame prohibits defining grammar in the evaluation slice) | unknown due to insufficient evidence |
| `3bf06a27c562` | sibling | `pathaudit_independent_c_craftsmanship_review` | `step_02_independent_pathaudit_c_review` | both attempts `Worker timed out after 600 seconds`; verdict JSON never written | unknown due to insufficient evidence |
| `d7fd02be2e0d` | sibling | `pathaudit_c_craftsmanship_review` | `step_02_review_pathaudit_craftsmanship` | attempt 1 verdict `fail` with four Medium findings; attempt 2 `Worker timed out after 600 seconds` | unknown due to insufficient evidence |
| `c12f7287d009` | sibling | `repair_pathaudit_quality_gates` | `step_01_repair_pathaudit_quality_gates` | both attempts `Worker timed out after 600 seconds`; attempt 2 additionally `make clean && make test` → `Makefile:213: test-suite Error 1` and two pytest failures | unknown due to insufficient evidence |
| `c847e01d15fe` | sibling | `sysdiff_release_package_and_notes` | `step_01_prepare_release` | attempts 1, 3, 4: `sha256sum -c artifacts/release/SHA256SUMS` → `sha256sum: sysdiff-source.tar.gz: No such file or directory` | product defect (release recipe) |
| `580b0f6ff811` | sibling | `prepare_sysdiff_release_package_and_notes` | none — every `step_results` entry is `PASSED` | run `FAILED` with `evidence_verification.status: divergent`, `first_divergence: Unrecorded file in chained evidence tree: steps/._.syncthing.._step_03_review_release_candidate.tmp` | unknown due to insufficient evidence |
| `ace075e584b7` | sibling | `repair_governed_run_c847e01d15fe` | none — all steps `PASSED` | `divergent`, `first_divergence: ... steps/._step_01_repair_release_checksum` | unknown due to insufficient evidence |
| `d38247ab7c12` | sibling | `repair_governed_run_c847e01d15fe` | none — all steps `PASSED` | `divergent`, `first_divergence: ... steps/._step_01_repair_governed_run` | unknown due to insufficient evidence |
| `a82455eee1c4` | sibling | `pathaudit_hostile_path_regression_coverage` | `step_04_review_hostile_path_coverage` | both attempts: `$.findings[0..2].severity: 'low' is not one of ['Critical', 'High', 'Medium', 'Low']` | unknown due to insufficient evidence |

Shared smoke assets, read but not executed. `tests/smoke_manifest.json` declares
`start_command` `python3 tests/smoke_start.py`, `check_command`
`python3 tests/check_sysdiff_smoke.py`, `startup_timeout_seconds: 10`,
`poll_interval_seconds: 0.25`, and `check_timeout_seconds: 30`.
`tests/smoke_start.py` is a five-line helper that immediately
`raise SystemExit(0)`. `tests/check_sysdiff_smoke.py` shells out to
`bash scripts/smoke.sh`, which is `set -euo pipefail` followed by `make test`.
`Makefile:150` routes `test` to `test-suite`, and `Makefile:262-268` builds
`$(BIN)`, runs `test-shell` (`./tests/test_sysdiff.sh`), then runs
`pytest tests/ -q` over the entire `tests/` directory. The smoke gate is
therefore a full-suite gate wearing a smoke-gate budget.

Cost of that gate over time, from in-repo records only: `HISTORY.md:130`
`127 passed in 10.58s`; `HISTORY.md:143` `127 passed in 10.84s`;
`HISTORY.md:173` `158 passed in 12.88s`; `HISTORY.md:258` `280 passed, 18
skipped in 20.40s`; `HISTORY.md:360` `332 passed, 18 skipped in 19.78s`;
`HISTORY.md:402` `346 passed, 18 skipped`; `HISTORY.md:42` and
`result-review.md:132` `356 passed, 18 skipped in 21.16s`. Those figures are
pytest-only and exclude the `make` build and `tests/test_sysdiff.sh` that run
first inside the same 30-second `check_timeout_seconds` budget.

Evidence that the smoke assets themselves were not tampered with: each failing
smoke attempt's `validation.json` records passing `file_hash_matches` pins, and
the digests are byte-identical across both workspaces and both date clusters —
`tests/smoke_manifest.json` `cc458d93e9882667…`, `scripts/smoke.sh`
`daca1ec8b6d0da5d…`, `tests/check_sysdiff_smoke.py` `28a1eec3aa6597d2…`,
`tests/smoke_start.py` `bc6d21ca69d0acb2…`. The worker instruction in
`worker-input.txt` and the retry feedback both forbid editing them.

Regression oracles read as inputs. `tests/test_governed_run_c847e01d15fe.py`
pins the release-checksum seam that halted `c847e01d15fe`: a basename-only
`SHA256SUMS` verified from a foreign cwd. `tests/test_governed_run_9add44496178.py`
pins format-1 changed-line delimiter shielding so a raw ` -> ` inside a value
cannot collide with the sole literal separator; `result-review.md:12-15` records
that this module's own first draft carried harness defects (a missing parent
`mkdir` for colliding-pair temporaries, and a BRE `grep` reading `\x3E` as
`x3E`). `tests/test_openunlink.py` contributes 62 tests, including
`test_seam_fd_count_65537_preserves_retained_finding` and one sibling case that
construct `FD_LIMIT_TRIGGER = 65537` entries under a 180-second subprocess
timeout.

## Failure Taxonomy

The closed set has four labels. Each Failed run receives exactly one primary
label; secondary contributors are named but never replace the primary.

**Shared smoke failure.** The pinned smoke oracle did not complete inside its
declared window, and the failure is a property of the shared gate rather than of
the step's own deliverable. Diagnostic signature: `stdout.log` reports
`app_started: true`, `start_exit_code: 0`, `core_flow_completed: false`,
`check_exit_code: -1`, and the single blocking error
`Smoke check did not pass before startup timeout.`; `artifacts/user-smoke/check.log`
contains exactly `Smoke check timed out.`; all `file_hash_matches` pins pass.
`check_exit_code: -1` is the discriminator — the check process was terminated
rather than observed exiting nonzero, so no test verdict exists in the record.
This is not a product defect: a red suite would surface as a nonzero
`check_exit_code` with pytest output in `check.log`.

**Allowed-path defect.** The step's `allowed_paths` contract omitted a path the
step had to write for its own validation to pass, so the orchestrator rejected
otherwise-green work. Diagnostic signature: `validation.json` records
`worker_exit_code` pass and `command_succeeds` pass, while the only failing
outcomes are `allowed_paths` entries. This is an authoring defect in the
playbook, not evidence about product bytes.

**Product defect.** Bytes under `src/`, `Makefile`, or a shipped recipe fail a
focused gate on their own merits, in an environment where the gate is otherwise
healthy. Diagnostic signature: a compiler diagnostic with a file and line, or a
deterministic focused-suite failure that reproduces identically across attempts,
with no timeout or allowed-path outcome present at the halt.

**Unknown due to insufficient evidence.** The durable record fixes the halting
signal but does not support attributing the halt to product bytes, to the
allowed-path contract, or to the smoke oracle. This label covers four distinct
substantiated mechanisms, each named rather than blurred:

- *Worker wall-clock exhaustion* — `exit_code: 124` against a finite
  `timeout_seconds`. The record proves the ceiling was hit; it does not record
  what the worker was doing, so neither "the task is too big" nor "the harness
  hung" is provable from the artifacts retained.
- *Reviewer `checks_run` non-reproducibility* — the reviewer recorded an exit the
  orchestrator could not re-observe. `docs/governed-run-ea8936c67cef-repair.md`
  bounds this correctly: the review sandbox plausibly saw the read-only git
  common dir / `git worktree` EROFS packaging failure and honestly wrote exit 1,
  while orchestrator re-execution saw 0. That reconstruction is labelled
  inference in the source and is preserved as inference here.
- *Evidence-tree divergence* — `evidence_verification.status: divergent` caused by
  filesystem-sync metadata files appearing inside the run evidence tree. The
  cause is known and is unambiguously infrastructural; it is simply outside the
  first three product-facing classes.
- *Verdict-artifact shape violations* — a verdict that cannot be accepted by
  `builtin:review_verdict/v1`, which blocks the gate without saying anything
  about the reviewed artifact.

Root cause versus downstream symptom. Several runs show a symptom chain that
must not be collapsed. In `39a591579075`, `File not found:
plans/seventh-utility-mission-evaluation.md` is downstream of the exit-124 halt
— the worker never finished writing — so the missing-output error is a symptom,
not an independent cause; the attempt-2 `Semantic check failed` on frame
violation is a genuinely separate authoring defect that happens to appear in the
same attempt. In `6ca4cebc8527`, the five `src/*.c` command failures are all one
root cause (a validation command containing an unexpanded literal glob, executed
without a shell) and must be counted once, not five times. In `f7539c314ca1`,
the exit-124 pair is downstream of the review-driven `REPAIR` re-entry, which is
itself downstream of High `SEV7-H1`; the origin remains Failed on the timeout,
and `result-review.md:254-277` is correct to keep those layers distinct. In
`ab4d8a7348ee`, the attempt-1 allowed-path violation was recovered on attempt 2
and is *not* the halt cause; the halt is the fourth consecutive `fail` verdict.
Conversely, `ba6dc2fdd199`'s pytest failures and its `lstat` compile error are
the same root cause (a missing declaration in `src/permguard.c`) observed
through two gates.

## Recurrence Analysis

Counts below are stated as *distinct runs* and, where the record supports it,
*distinct attempts*. A count is given only when every member was read from a
durable record; where a signature appears once, it is reported as once.

**R1 — Smoke check exceeds its pinned window. 4 runs, 8 attempts.**
`b24f4b8fe03e` (2026-07-24T11:09Z), `e02facf58b3e` (2026-07-24T12:09Z),
`8333eae22551` (2026-07-31T14:15Z), `f4d805b7b217` (2026-07-31T15:15Z). Every
attempt produced byte-identical `stdout.log`, and every attempt passed all
`file_hash_matches` pins. This is the single largest recurring cause and the
only one that has recurred across both workspaces and across a ten-day gap.
Substantiated root cause: `scripts/smoke.sh` runs `make test`, which is a full
build plus shell suite plus whole-directory pytest, against a manifest budget of
`check_timeout_seconds: 30` that has never changed (the manifest digest
`cc458d93e9882667…` is identical in the 2026-07-24 and 2026-07-31 records) while
the smoke-bound suite grew from `127 passed in 10.58s` to `356 passed, 18
skipped in 21.16s` on pytest alone. The gate has no margin left. A supporting
factor for the 2026-07-31 cluster specifically: `tests/test_openunlink.py`
entered `tests/` during run `9add44496178` and adds 62 tests including two
65,537-entry cases carrying 180-second subprocess timeouts — well beyond the
whole smoke budget on their own. That factor is stated as supported-but-not-
isolated: `check.log` retains only `Smoke check timed out.`, with no per-phase
timing, so the record cannot separate suite growth from host contention, and
the 2026-07-24 cluster predates `openunlink` entirely and ran against the
sibling workspace's `tests/` tree.

**R2 — Worker wall-clock exhaustion (`exit_code: 124`). 8 runs, 12 attempts,
3 harnesses.** `3bf06a27c562` (2 attempts), `d7fd02be2e0d` (1),
`ab4d8a7348ee` (1) on `claude_code`; `c12f7287d009` (2), `6ca4cebc8527` (1, at a
1500-second ceiling) on `cursor_cli`/`grok-4.5`; `39a591579075` (2),
`f7539c314ca1` (2), `9add44496178` (1, recovered on attempt 2) on
`codex_cli`/`gpt-5.6-sol`. Harness attribution is read from each attempt's
`route-selection.json`. Within this group a sub-signature is worth separating
because it is harness-specific: all five `codex_cli` timeouts emit
`Reading additional input from stdin...` followed by the Codex banner before
hitting the ceiling, whereas the `claude_code` and `cursor_cli` timeouts emit
only `Worker timed out after 600 seconds.` The stdin-banner sub-signature is
3 runs / 5 attempts and appears in no non-Codex route in this record. What the
record does *not* contain is any worker transcript for those attempts, so the
distinction between "hung waiting on stdin" and "worked until the ceiling" is
not resolvable from retained artifacts. `result-review.md:265-267` separately
notes that both `f7539c314ca1` timeout blobs also carry
`failure_classification: worker_binary_resolution` despite stderr showing an
active Codex session — that classifier field is contradicted by its own
stderr and should not be cited as a cause.

**R3 — Allowed-path accounting misses a file the step must write. 3 runs.**
`ab4d8a7348ee` step 1 attempt 1 (`sysdiff-release.tar.gz`,
`sysdiff-release.tar.gz.sha256` — workspace-root artifacts written by the
`release` recipe, absent from an otherwise generous fifteen-entry allowlist);
`6ca4cebc8527` step 5 attempt 1 (`docs/pathaudit.md`, `tests/test_sysdiff.py`
against an allowlist that named `docs/pathaudit-maintenance-repair-contract.md`
and `tests/test_pathaudit.py` but not their siblings); `af89bd4b8fcd` step 3
attempt 2 (`tests/test_governed_run_9add44496178.py`, `tests/test_sysdiff.sh`
against `allowed_paths: ['src', 'Makefile', 'dist']`). The shared root cause is
one thing, not three: the allowlist was derived from `outputs.required` rather
than from the full set of files the step's own validation forces the worker to
touch. `af89bd4b8fcd` is the clearest instance — the step could not pass without
repairing the harness defects in the regression module it was told to satisfy,
and repairing them was out of scope by construction.

**R4 — Reviewer `checks_run` cannot be re-observed. 2 runs, 3 attempts.**
`ea8936c67cef` step 7 (both attempts) and `f7539c314ca1` step 4 attempt 1. Both
name the identical command, `python3 -m pytest tests/ -q`, and both record
`reviewer claimed exit 1, orchestrator observed exit 0`. This is a recurring
signature with a recurring shape: the reviewer ran a whole-suite command whose
result is environment-dependent on this host.

**R5 — Deterministic product defects surfacing at the implement step. 2 runs.**
`ba6dc2fdd199` (`src/permguard.c:213` calls `lstat` with no visible declaration;
rejected identically by `gcc` and `clang` under `-Werror`, with three focused
pytest failures downstream) and `9add44496178` (`src/openunlink.c` emits wrong
finding bytes; the failure set is character-for-character identical across both
attempts, indicating the second attempt made no progress on the failing seam).
Both are correctly classed as product defects: no timeout, no allowed-path
outcome, and no smoke involvement at the halt.

**R6 — Evidence-tree divergence from filesystem-sync artifacts. 3 runs.**
`580b0f6ff811`, `ace075e584b7`, `d38247ab7c12`, all on 2026-07-21 in the sibling
workspace. Each records `evidence_verification.ok: false` with a
`first_divergence` naming a `._`-prefixed sync artifact
(`steps/._.syncthing.._step_03_review_release_candidate.tmp`,
`steps/._step_01_repair_release_checksum`,
`steps/._step_01_repair_governed_run`). This class produces a contradiction
worth stating plainly: in all three runs *every* `step_results` entry is
`PASSED`, yet the run status is `FAILED`. A reader who consults only step
outcomes will conclude these runs succeeded.

**R7 — Verdict artifact rejected on shape. 1 run, 2 attempts.**
`a82455eee1c4` step 4 emitted `severity: 'low'` where the schema requires
`Low`, on all three findings, on both attempts. Not recurring across runs in this
record, but recurring across attempts within the run — the retry carried the same
casing rather than repairing it.

**R8 — Validation command with an unexpanded shell glob. 1 run, 5 commands,
2 attempts.** `6ca4cebc8527` step 5 ran `gcc … src/*.c`, `clang … src/*.c`,
`clang-format … src/*.c`, `clang-tidy src/*.c`, and `cppcheck … src/*.c`; each
reported the literal path `src/*.c` as missing, so the glob was passed to
`execve` rather than to a shell. Counted once as a cause.

**R9 — Failed runs that leave no trace in AgentFlow. 11 of 20 runs.** Searching
the tracked repository for each Failed run id finds no mention of
`8333eae22551`, `b24f4b8fe03e`, `e02facf58b3e`, `a82455eee1c4`, `c12f7287d009`,
`3bf06a27c562`, `d7fd02be2e0d`, `ab4d8a7348ee`, `ace075e584b7`, `d38247ab7c12`,
or `39a591579075` in `context.md`, `result-review.md`, `HISTORY.md`,
`sprint-plan.md`, `STATUS.md`, or `WHERE_AM_I.md`. The mechanism is structural:
closeout is the last step, so a run that halts earlier can never record itself.
The most pointed instance is `8333eae22551` — the run that authored the previous
revision of this very file — which is absent from every AgentFlow record. Eight
of the eleven belong to the sibling workspace, which partly explains the gap;
`8333eae22551` and `39a591579075` do not, and are unexplained omissions in this
repository's own records.

## Corrective Actions

Each action below is narrowly scoped, attaches to one substantiated recurring
cause, and names the existing gate or artifact that should verify it. None of
these actions is performed by this slice; each requires its own authorized,
correctly allowlisted playbook.

**A1 → R1 (shared smoke failure).** Bring the smoke budget and the smoke cost
back into agreement by exactly one of two moves, decided by a human before
launch: raise `check_timeout_seconds` in `tests/smoke_manifest.json` to a value
justified by the recorded `check.log` wall-clock, or narrow `scripts/smoke.sh`
to a bounded core flow instead of `make test`. Both edit pinned assets, so the
change must be its own slice with the smoke assets in `allowed_paths` — workers
under any other playbook remain forbidden to touch them, per the standing
`worker-input.txt` instruction. *Verified by:* the smoke step's own
`file_hash_matches` pins (which will require new digests, making the change
visible and deliberate) together with `artifacts/user-smoke/result.json`
returning `check_exit_code: 0` and empty `blocking_errors`.

**A2 → R1 (detection).** Make the smoke gate self-diagnosing: require closeout
prose to record the `check.log` wall-clock figure alongside the pass/skip counts
it already records, so budget erosion is visible before it becomes a halt. The
practice already exists informally — `HISTORY.md:42` and `result-review.md:132`
both carry `356 passed, 18 skipped in 21.16s`. *Verified by:* `TESTING.md`,
which already designates the manifest as the pinned oracle and already warns
that it is sysdiff-centered transitive evidence, extended to require the timing
figure in the same sentence as the count.

**A3 → R3 (allowed-path defect).** Add one pre-launch authoring check: every
path in `outputs.required`, **and** every file the mission text instructs the
worker to write or repair, must appear in that step's `allowed_paths` before
human approval — including generated artifacts written beside a target
(`sysdiff-release.tar.gz.sha256`), sibling documents in the same directory, and
any harness or oracle file the step's own validation command will force the
worker to fix. *Verified by:* `lint-playbook --strict` in the `OPERATE.md`
generate → lint → approve sequence, and, after the fact, by each attempt's
`validation.json`, where a clean run shows zero failing `allowed_paths`
outcomes.

**A4 → R4 (reviewer evidence).** Constrain reviewer `checks_run` entries to
focused, deterministic commands scoped to the slice under review, and instruct
reviewers that an environment-dependent packaging failure belongs in a finding
or a note, never in a durable `exit_code` the orchestrator will re-execute. The
concrete rule to state in review missions: each entry is
`{command, exit_code, summary}`, the command string is exactly re-executable in
the workspace, and whole-suite commands are not acceptable evidence for a
focused slice. *Verified by:* the existing non-advisory `checks_run_match` gate
plus `json_schema` at `schema_path: builtin:review_verdict/v1` on the verdict
path — the same pair that caught `ea8936c67cef` and `f7539c314ca1`.

**A5 → R2 (worker timeouts).** Require every producing step and every blocking
system validation to name a numeric `timeout_seconds` sized to that step's real
work, and split multi-repair loops so one budget cannot absorb unbounded
re-entry. `6ca4cebc8527` shows that raising the ceiling alone is insufficient —
it timed out at 1500 seconds — so the split matters more than the number.
*Verified by:* `playbook.json` step metadata, readable before approval, and
after the fact by `run.json` attempt `exit_code` sequences, which must be quoted
verbatim in closeout (`result-review.md:254-277` already does this correctly for
the `0`/`124`/`124` pair).

**A6 → R2 (detection, Codex sub-signature).** Retain the worker stdout/stderr
transcript for timed-out attempts, not just the banner prefix currently visible
in `validation_errors`. Without it, the `Reading additional input from
stdin...` sub-signature cannot be promoted above "unknown", and the same three
runs will keep producing unclassifiable halts. *Verified by:* the per-attempt
`stdout.log` / `stderr.log` artifacts already enumerated in
`artifact_inventory.json`, which should be non-empty for exit-124 attempts.

**A7 → R5 (product defects).** Keep the failing-regression-first ordering that
`TESTING.md` already states ("Defects should land as failing regressions before
fixes") and require each implement step's validation to name the exact focused
pytest module path rather than a directory. Both `ba6dc2fdd199` and
`9add44496178` were caught correctly by this discipline; the corrective action
is to preserve it, and to treat an attempt that reproduces a character-identical
failure set as a signal to stop and re-frame rather than to retry. *Verified
by:* the named module in each step's `command_succeeds` validation, visible in
`validation.json`.

**A8 → R6 (evidence divergence).** Keep filesystem-sync metadata out of the runs
root, either by excluding `../linux-utilities-agent-orch-runs/` from sync scope
or by excluding `._*` patterns from the chained evidence tree. *Verified by:*
`run.json` `evidence_verification.status`, which must read `verified` — and
which is the *only* field that distinguishes these three runs from successful
ones, since all their step outcomes are `PASSED`.

**A9 → R8 (validation-command globs).** Enumerate source paths explicitly in
validation commands (`src/sysdiff.c src/pathaudit.c …`) rather than relying on
`src/*.c`, since commands are executed without a shell. *Verified by:* the
step's `validation.json` `command_succeeds` outcomes, which recorded the literal
unexpanded path five times in `6ca4cebc8527`.

**A10 → R9 (unrecorded failures).** Require that every Failed run id be entered
in `context.md` or `result-review.md` by the next governed run in the workspace,
whether or not a recovery playbook is authorized for it — the record of the
failure is cheaper than the archaeology. *Verified by:* a grep of the tracked
AgentFlow files for each id under `../linux-utilities-agent-orch-runs/`, which
today returns nothing for eleven of twenty Failed runs.

**A11 → residual git-redirection risk (see below).** Before any run that needs a
writable git directory, snapshot the workspace `.git` into the attempt's scratch
directory and restore it unconditionally on exit, including on halt; and list
`.git` in `allowed_paths` for any step permitted to touch it, so the change is
visible to the path-scope gate rather than invisible to it. *Verified by:* the
`allowed_paths` outcomes in `validation.json` (which currently never mention
`.git`) and by `git rev-parse --git-dir` resolving inside the workspace rather
than under `.agent-orch-scratch/`.

## Residual Risks

**The workspace git directory currently points into a failed run's scratch
tree.** The `.git` file at the repository root contains
`gitdir: /home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch/af89bd4b8fcd/step_03_code_repair/attempt-2/standalone-repo/.git`,
and `git rev-parse --git-dir --git-common-dir` resolves to that path. That
directory is a full clone whose `config` records
`url = file:///home/lee/projects/linux-utilities-autonomous`. The redirection is
live: this repository's index, refs, and objects are being read from a scratch
path belonging to a Failed run, under a directory the mission brief defines as
non-governed and disposable. Deleting `.agent-orch-scratch/af89bd4b8fcd/` would
detach the working tree from its history. Supporting evidence for how it got
there: six runs (`4ae7a820b0a3`, `5035933ac7b4`, `5a3c165c0a46`,
`c9e3de33f46b`, `ea8936c67cef`, `af89bd4b8fcd`) left writable-gitdir workaround
residue in scratch; the successful ones also left a `workspace-gitdir` backup
directory, while `af89bd4b8fcd/step_03_code_repair/attempt-2/` has a
`clone_writable_gitdir.err` and no backup. That the redirection was left behind
by the halted attempt is well supported by the path name and the 2026-07-31
08:45 mtime on `.git`; that this specific step performed the write is inference,
since no allowlist or validation outcome in any run records `.git` at all. This
audit does not repair it — `.git` is outside `docs/` and outside this slice's
scope. It should be the subject of a separately authorized, narrowly allowlisted
repair before further governed work runs in this workspace.

**The smoke gate will keep failing until A1 lands, and every playbook inherits
it.** Four Failed runs already halted on it, including a documentation-only
audit that had nothing to do with product behavior. Any run that reaches a
`user_smoke_gate` step is exposed regardless of what it changed, so the observed
failure rate understates the risk: the two most recent Failed runs in this
workspace, `8333eae22551` and `f4d805b7b217`, both had all prior steps `PASSED`.

**`tests/test_openunlink.py` is in `tests/` while `src/openunlink.c` is recorded
as failing it.** Run `9add44496178` halted with a character-identical failure
set across both attempts, and the module is collected by `pytest tests/`, which
is what `make test` — and therefore the smoke gate — runs. This audit did not
execute the suite and makes no claim about its current state. If those tests
still fail, the smoke gate has a second, independent reason to fail that the
`Smoke check timed out.` log cannot distinguish from a timeout.

**Contradictory and missing evidence that limits every conclusion here.**
(i) Three runs are `FAILED` with every step `PASSED`, so step-level reading
contradicts run-level status. (ii) `f7539c314ca1`'s timeout metadata carries
`failure_classification: worker_binary_resolution` while its own stderr shows an
active Codex session; the classifier field is unreliable and is not used as
evidence above. (iii) `artifacts/user-smoke/check.log` retains one line for a
timeout, so the growth-versus-contention question behind R1 cannot be settled
from the record. (iv) No worker transcript survives for exit-124 attempts. (v)
Eleven of twenty Failed runs are unrecorded in AgentFlow, and eleven executed
against the sibling workspace `/home/lee/projects/linux-utilities`, so
conclusions drawn from them do not transfer to current `src/` bytes without
re-verification. (vi) The audit compares recorded outcomes only; nothing here
was re-run.

**What this audit deliberately does not do.** It does not close `PAW1-DOC-901`,
`PAW1-DOC-902`, `PAW1-TEST-903`, `PAW1-TEST-904`, `PAW1-SCOPE-905`, `PA-6CA-1`
through `PA-6CA-4`, `SEV7R-M1`/`M2`, `SEV7R-L1`/`L2`, `SIXTH2-M1` through
`M3`, `SIXTH2-L1` through `L3`, the permguard recovery Lows, or the FUM5
findings. It does not relabel any Failed origin run as passed — `af89bd4b8fcd`,
`9add44496178`, `f7539c314ca1`, `ea8936c67cef`, `ba6dc2fdd199`, and
`6ca4cebc8527` all remain Failed. It does not authorize `sparsemap`,
`shebangcheck`, `inodealias`, or `openunlink` implementation, and it does not
claim a fresh `make quality`, sanitizer, Valgrind, smoke, or independent-review
result for this documentation step. If a future `run.json` contradicts a
citation here, prefer the runs-root evidence and amend this file in a separately
authorized `docs/` slice.
