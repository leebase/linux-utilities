# Governed-run repair evidence for `ea8936c67cef`

## Overview

This repair reconstructs failed governed run `ea8936c67cef`
(`permguard_hostile_filesystem_fixtures`) and classifies the exact gate
mismatch that halted the run after independent review. Repair scope is
documentation-only: author this evidence file so later smoke and review
steps can judge the failure class without rewriting product surfaces.
Preserve all valid candidate work already delivered by origin steps 1–6
(hostile-fixtures contract, focused fixture tests, documentation prose,
quality-floor evidence, and user-smoke artifacts). Explicit non-goals:
do not modify `src/permguard.c`, `tests/test_permguard.py`, Makefile or
workflow assets, existing AgentFlow handoff docs, or the origin review
pair under `code-reviews/`; do not claim that failed origin
`ea8936c67cef` became a passed delivery; do not install, package, tag,
publish, or release `permguard`; do not invent optional polish from this
reconstruction. Relevant governed-run states from durable
`../linux-utilities-agent-orch-runs/ea8936c67cef/run.json`: overall
`status` is `FAILED`; steps
`step_01_frame_hostile_fixture_slice` through
`step_06_user_smoke_gate` are `PASSED` on attempt 1 with
`worker_exit_code` 0; `step_07_independent_review` is `FAILED` after
attempt 1 `RETRY` and attempt 2 `HALT`. Expected command exit-status
behavior for a clean recovery verdict: allowlisted checks must record
the exit status the orchestrator can re-observe for the same command in
the same workspace (a claimed nonzero exit is invalid when the
orchestrator observes 0); product `permguard` statuses remain the frozen
0/1/2 contract and are not reopened by this repair; suite-level
`python3 -m pytest tests/ -q` must be reported honestly for the
environment that executed it, and environment-dependent packaging
failures must not be forced into a durable `checks_run` claim that the
orchestrator cannot confirm.

## Failure Reconstruction

Observed evidence (durable, not inferred): `run.json` records
`validation_errors` on both review attempts as
`Reviewer checks_run claims in
code-reviews/review-permguard-hostile-filesystem-fixtures.verdict.json
could not be confirmed: python3 -m pytest tests/ -q: reviewer claimed
exit 1, orchestrator observed exit 0`. Attempt-2 `validation.json`
shows `checks_run_match` with
`claimed_exit_code: 1`, `actual_exit_code: 0`, `status: mismatch`, while
`review_verdict_clean` at threshold High still passed (0 Critical, 0
High, 0 Medium, 6 Low). The on-disk verdict `checks_run` entry names
exactly `python3 -m pytest tests/ -q` with `exit_code: 1` and a summary
citing `1 failed, 387 passed, 16 skipped` plus
`tests/test_sysdiff.py::test_release_excludes_untracked_files` failing
inside `git worktree add` with a read-only git common dir. Step-5
quality-floor validation separately recorded the same pytest command as
succeeded (orchestrator message: command succeeded with 385 passed
tests) alongside a complete `make quality` exit 0 that used a scratch
writable gitdir for this host’s EROFS common-dir property. Inference
bounded by that evidence, and labeled as inference only: the review
worker’s sandbox likely observed the EROFS packaging failure and
faithfully wrote exit 1 into the verdict, while the orchestrator’s later
`checks_run_match` re-execution did not reproduce that failure and
therefore observed exit 0; the durable halt is the mismatch gate, not a
High-threshold product verdict fail. Unavailable logs are not invented:
no claim is made about unpublished stderr beyond the summaries already
stored in `validation.json` / the verdict `checks_run` summary, and no
claim is made that either review attempt silently skipped the allowlisted
command. Reproducible mismatch statement: for the same allowlisted
command string, recording `exit_code: 1` in the verdict while the
orchestrator re-run returns 0 is sufficient and necessary to fail
`checks_run_match` and, after attempt 2, to `HALT` the origin run as
`FAILED` while leaving steps 1–6 candidate artifacts intact.

## Hazard Taxonomy

Closed taxonomy for classifying this governed-run failure (exactly four
classes; every failure maps to one primary class, with optional
secondary contributors named explicitly):

1. Product defects — defects in shipped or candidate product behavior,
   source, focused tests, or frozen CLI/status/taxonomy contracts that
   would correctly fail a High-threshold product review or a quality
   floor on their own merits.
2. Review-artifact defects — defects in review markdown/verdict contents
   relative to orchestrator-confirmable facts, including wrong
   `checks_run` exit codes, unconfirmable summaries, malformed schema,
   or heading/content contract breaks in review outputs.
3. Authoring-contract defects — defects in worker-facing playbook or
   repair-instruction authorship that omit required exact heading
   strings, numeric content minima, or other mechanical acceptance
   predicates, so later workers produce outputs that fail validation
   even when substantive analysis is sound.
4. Review-environment limitations — host or sandbox conditions (for
   example read-only git common dir / `git worktree` EROFS, long
   `TMPDIR` sun_path limits) that change suite exit status or skip
   sets without proving a workspace product regression.

Classification of `ea8936c67cef` with evidence: primary class is
review-artifact defects because the durable halt is
`checks_run_match` failing when the verdict claimed exit 1 and the
orchestrator observed exit 0 for `python3 -m pytest tests/ -q`
(`validation.json` mismatch evidence). Secondary contributor is
review-environment limitations: the verdict summary and Low PGHF-006
document the EROFS/`git worktree` packaging failure on
`test_release_excludes_untracked_files`, matching the same host
property already noted historically as pathaudit Medium PA-6CA-4 /
QUALITY.md scratch-gitdir notes, while step-5 used a scratch writable
gitdir and recorded a green pytest/quality floor. Not classified as a
product defect: review finding counts show 0 Critical/High/Medium;
permguard-focused work from steps 1–6 remained green; the single named
failing test is an unrelated sysdiff packaging case. Separately, the
prior authoring failure that this recovery playbook itself repairs—an
omission of the exact heading strings Overview, Failure Reconstruction,
Hazard Taxonomy, and Acceptance Checks plus their numeric
minima from worker-facing instructions—is an authoring-contract defect
affecting repair-doc production, not the origin permguard product slice.

## Acceptance Checks

Name the reproducible checks and the evidence required for a clean
recovery verdict on this documentation repair, without treating the
failed origin run as rewritten to passed:

1. Heading and content-floor check — `docs/governed-run-ea8936c67cef-repair.md`
   contains Markdown headings whose exact texts are `Overview`,
   `Failure Reconstruction`, `Hazard Taxonomy`, and
   `Acceptance Checks`, each followed by at least 120 non-whitespace
   characters. Evidence: orchestrator `markdown_headings_present`
   validation (or an equivalent local count) exit 0 / passed.
2. Scope integrity check — git status / allowed-path validation shows
   this recovery step changed only
   `docs/governed-run-ea8936c67cef-repair.md` (plus operational scratch),
   preserving origin candidate files and leaving source, tests,
   workflow assets, and pre-existing documentation unmodified.
   Evidence: step `allowed_paths` / changed-files list.
3. Reconstruction fidelity check — the Failure Reconstruction section
   cites the durable mismatch
   (claimed exit 1 vs orchestrator exit 0 for
   `python3 -m pytest tests/ -q`) from
   `../linux-utilities-agent-orch-runs/ea8936c67cef/` without inventing
   unavailable logs, and distinguishes observed evidence from labeled
   inference. Evidence: independent reviewer confirmation against
   `run.json` and attempt-2 `validation.json`.
4. Taxonomy closure check — Hazard Taxonomy enumerates exactly the four
   closed classes above and classifies this failure primarily as a
   review-artifact defect with review-environment secondary
   contribution, not as a permguard product defect. Evidence: review
   lens notes citing those classes and the mismatch/EROFS facts.
5. Allowlisted regression pin — focused
   `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
   tests/test_governed_run_c847e01d15fe.py -q` exits 0 (workflow /
   release-checksum regression pin only; not permguard product proof).
   Evidence: command exit 0 and passed/skipped counts in review
   `checks_run`.
6. User-smoke continuity — existing smoke oracle under
   `artifacts/user-smoke/result.json` records `app_started` true,
   `core_flow_completed` true, start/check exit 0, and empty
   `blocking_errors` after the recovery smoke step. Evidence: that
   JSON plus check.log. Expected exit-status behavior for any future
   re-review of the origin slice: `checks_run` exit codes must match
   orchestrator re-observation; environment-only packaging failures may
   be recorded as review-environment notes but must not claim a
   durable nonzero suite exit the orchestrator cannot reproduce.
   Clean recovery verdict requires independent
   `code-reviews/review-governed-run-ea8936c67cef.verdict.json` with
   `verdict: pass` at the playbook threshold and a confirmed
   `checks_run_match`, while still labeling origin `ea8936c67cef` as
   Failed rather than silently upgraded.
