# Post-hardening commissioning timeout diagnosis

Date: 2026-08-01  
Mission: Linux Utilities  
Run examined: `e5e872615eed`  
Workspace examined: `/home/lee/projects/linux-utilities-autonomous`

## Executive conclusion

The Codex worker did not spend the 600 seconds productively repairing Linux
Utilities. It made real diagnostic progress, but the attempt was shaped as a
broad platform investigation with a large historical context, a mismatched
workspace input set, and a full-suite validation requirement. The worker kept
expanding its inspection into Agent-Orch and auto-orch source and evidence,
then timed out immediately after a final status inspection. It never issued a
write command, never created the required commissioning report, and never
reached the independent tester, semantic judge, or human approval steps.

This is primarily a task-shape and mission-workspace configuration failure,
with model wandering contributing and the fixed harness timeout providing the
terminal failure. It is not evidence that the Codex provider was unavailable,
that deterministic routing failed, or that repository identity drifted. The
worker process started, ran many commands, and its identity snapshots matched.

The product baseline is independently red but coherent. The current 18 test
failures collapse into one test-fixture expectation cluster, one incomplete
documentation/contract cluster, and one distribution-test cascade. No source
implementation defect is justified by the present evidence. The mission is
**Not ready** for another commissioning run until the bounded repairs below
are completed and the commissioning packet is corrected.

## Evidence inspected

The complete preserved attempt was inspected under:

`/home/lee/projects/linux-utilities-agent-orch-runs/e5e872615eed/steps/step_01_commission_platform/attempt-1/`

Relevant evidence included `worker-input.txt`, `route-selection.json`,
`router-request.json`, `router-response.json`, `worker_result.json`,
`stderr.log`, `stdout.log`, `validation.json`, `policy.json`, all five
repository identity artifacts, `run.json`, `progress.json`, the evidence
manifest, and the dashboard. `stdout.log` is empty because Codex emitted its
session transcript to `stderr.log`; `stderr.log` ends with the harness timeout.

The preserved route was `codex_cli` / `gpt-5.6-sol`, route id
`legacy-direct`, with no fallback. The route decision records the hardened
precedence chain and an executed route. The worker result records exit `124`
and a 600-second timeout. Its secondary diagnostic labels the failure
`worker_binary_resolution` with a `no such file or directory` signature, but
that label does not describe the observed execution: the Codex v0.146.0
process started, printed its session id, and executed dozens of shell
commands. It should be treated as a misleading failure-classification
signature, not as the primary cause.

The engine preserved and verified:

- `repository-identity-before.json`
- `repository-identity-after-worker.json`
- `repository-identity-after-worker-check.json`
- `repository-identity-after-step.json`
- `repository-identity-check.json`

Both identity comparisons passed with no differences. The evidence chain
verified with 3 entries and 17 artifacts. `changed_files` is empty, and the
autonomous worktree remained clean after the run and after the independent
reproduction.

## Timeline of the 600-second attempt

The run began at `2026-08-01T19:00:59.845253Z`; the detached launch record is
`2026-08-01T19:01:00.059297Z`; the run sealed at
`2026-08-01T19:13:03.927397Z`. The worker-specific timeout was exactly 600
seconds. The transcript does not contain per-tool wall-clock timestamps, so
the sequence below is ordered from the recorded command history; command
durations are included where the transcript recorded them.

1. The worker read `AGENTS.md`, then consumed the large historical
   `context.md`, `result-review.md`, `sprint-plan.md`, and `WHERE_AM_I.md`
   files in multiple chunks. It spent substantial context on old product and
   recovery history before doing the current report.
2. It tried to read the recovery plan, identity-protection document, and
   scripts relative to the commissioned autonomous worktree. Those four
   checks failed immediately because the files were absent from that worktree.
   It then discovered that the files existed in the interactive checkout and
   switched to absolute paths.
3. It read the mission configuration, the 800-line mission charter, the crew
   file, previous commissioning evidence, the current playbook, and multiple
   Agent-Orch platform implementation and contract files. It revisited the
   same routing, provider, identity, scratch, and commissioning evidence in
   several commands.
4. It ran the full test command from the packet. That command took
   `132412ms` in the worker transcript. The outer run reported 19 failures in
   that attempt because the distribution regression launched a nested suite;
   the nested suite reproduced the 17 direct openunlink failures. The worker
   also observed a transient read-only shared-Git-admin failure in
   `test_release_excludes_untracked_files`.
5. Using absolute paths to the interactive checkout, it successfully ran the
   repository identity verifier, protection dry-run, shell syntax check, and
   scratch pruner dry-run. The verifier reported all 19 identity checks
   passing; the pruner selected zero candidates.
6. It read the preflight and commissioning logs, the mission charter, Agent-
   Orch routing/provider/commissioning code, and the prior failed run. It then
   ran the commissioning CLI against the autonomous worktree, which correctly
   reported `Not ready` for the generic nested-`.git` linked-worktree check.
7. It checked whether the hardening commit was an ancestor of `main`, showed
   that commit, and ran a final `git status`. No report-writing command or
   patch followed. The worker then hit the 600-second ceiling and the harness
   sealed the attempt as `FAILED`.

## Answers to the timeout questions

### What was the worker doing?

It was performing a broad evidence survey: shared-memory history, mission and
crew routing, previous runs, commissioning reports, repository identity code,
scratch behavior, Agent-Orch routing and semantic-provider implementation, and
the full product suite. It was not implementing openunlink or repairing the
commissioning report.

### Did it make substantive progress?

Yes, diagnostically: it found the autonomous-worktree input mismatch, ran the
product suite, independently confirmed identity and scratch checks through the
interactive checkout, and preserved a useful transcript. No required durable
deliverable was produced. In the governed sense the attempt made no accepted
mission progress because the required report was absent and the route-separated
gates never ran.

### Was it blocked?

It was not blocked on a hanging command. The missing relative scripts failed in
milliseconds, the full suite completed, the absolute identity and scratch
checks completed, and the platform reads completed. `crontab -l` returned a
permission error, but the worker had already been given the paused-state
evidence in files and did not need to wait on that command. The dominant issue
was excessive investigative scope and failure to converge on the required
report, amplified by the missing inputs in the selected worktree.

### Did it repeatedly inspect or modify the same areas?

It repeatedly inspected current run evidence, commissioning JSON, routing and
provider definitions, identity implementation, and mission history. The first
relative check attempt and later absolute-path check attempt were a reasonable
recovery from the worktree mismatch, but the later platform-source and prior-
run inspection went beyond what was needed to write a faithful report. It did
not repeatedly modify files: no write command occurred and `changed_files` is
empty.

### Model, harness, task shape, or environment?

All four contributed, with different weight:

- **Task shape — primary contributor.** A docs-only commissioning worker was
  asked to read a very broad historical and platform corpus, run the entire
  product suite, reconcile two worktrees, inspect routing/provider internals,
  and author a report. The declared recovery inputs were not present in the
  actual mission workspace.
- **Model behavior — material contributor.** The `gpt-5.6-sol` worker used
  `xhigh` reasoning and continued exploratory reading after the decisive facts
  were available. It did not prioritize writing the required report or
  checkpointing a partial report under `docs/`.
- **Harness — terminal contributor.** The hard 600-second worker ceiling
  stopped the attempt. The harness otherwise behaved correctly: it sandboxed
  the worker, preserved identity evidence, validated the full suite, and
  halted on the missing output. The worker-result binary-resolution label is
  inconsistent with the actual successful process startup and should not be
  used as the diagnosis.
- **Environment — secondary contributor.** The configured `main` worktree is
  four commits ahead of `origin/main` at `15605e3` and does not contain the
  recovery scripts and documents that are present on the interactive
  `agent/public-utility-guides` checkout at `34e4a4a`. The shared Git admin
  area is read-only for some worktree operations, and the worker could not
  read the crontab. These facts explain environmental observations; they do
  not explain the 600-second wandering by themselves.

### Would a longer timeout help?

Not as the next action. The worker had not begun writing at the deadline, so
the evidence does not show valuable work that was merely a few minutes from
completion. A longer ceiling would likely permit more of the same exploration.
After the packet is narrowed and its inputs are made valid, the measured local
checks leave ample time inside 600 seconds; no timeout increase is justified
now. A repair worker should receive a focused slice and its focused validator,
not a larger budget for the current task shape.

### Did it attempt to address openunlink?

No. It executed the suite and observed the failures, but it did not inspect
the implementation/test fixtures closely enough to form a repair, did not
write source or tests, and did not alter any of the 18 failing areas. The
failure list is evidence of baseline state, not evidence of a repair attempt.

## Reproduced baseline and failure clusters

Read-only reproduction command:

```text
env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
```

Current reproduction: **18 failed, 530 passed, 18 skipped in 117.75s**.
The worker's post-run validator recorded 18 failed, 529 passed, and 19
skipped in 123.17s. The small pass/skip difference is host/test-state
variation; the 18 failure identities are the same. The autonomous worktree
was clean before and after this command.

### Cluster A — one stale/incomplete seam fixture expectation, 15 failures

Affected tests:

- `tests/test_openunlink.py::test_seam_numeric_ordering_and_duplicates`
- `tests/test_openunlink.py::test_seam_fd_count_65537_preserves_retained_finding`
- `tests/test_openunlink.py::test_seam_mixed_finding_and_advisory`
- `tests/test_openunlink.py::test_seam_descriptor_zero_is_valid_name`
- `tests/test_openunlink.py::test_seam_final_close_failure_preserves_findings`
- `tests/test_openunlink.py::test_closed_stderr_pipe_preserves_finding_status`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[open-inject0-PROCESS_SCAN]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[dup-inject1-PROCESS_SCAN]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[fdopendir-inject2-PROCESS_SCAN]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[closedir-inject3-PROCESS_SCAN]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[close-inject4-PROCESS_SCAN]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[readdir-inject5-PROCESS_SCAN]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[malloc-inject6-MEMORY]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[fwrite-inject7-STDOUT_WRITE]`
- `tests/test_openunlink.py::test_injector_positive_control_paired_success[fflush-inject8-STDOUT_WRITE]`

Expected behavior is the contract's final followed `st_size` in each
`OPEN_UNLINKED` line. The current source does that. The seam helper
`_zero_link_entry` defaults `size=3`, while these callers use one-, two-, or
four-byte link text and assert sizes `1`, `2`, or `4`. Actual output therefore
contains `size=3`; the first differing byte in the assertions is the size
field. The nine fault-injector tests fail in their successful control path
before the injected failure is exercised, so they do not currently validate
those failure branches.

Classification: stale or incomplete prior test fixture, not a confirmed
product defect and not an environment issue. The contract explicitly defines
`BYTES` as final `st_size`, so changing `src/openunlink.c` to use link-text
length would weaken the contract. The smallest coherent repair is to make the
fixture's default size derive from the supplied link bytes, or to pass an
explicit contract-correct `size` in every affected scenario, then rerun the
focused suite. No source change is justified by this cluster.

### Cluster B — incomplete DOCUMENT/contract phase, 2 failures

Affected tests:

- `tests/test_openunlink.py::test_documentation_status0_nfs_disclaimer`
- `tests/test_openunlink.py::test_contract_authority_file_present`

The documentation test expects `man/openunlink.1` and `docs/openunlink.md`;
neither exists. The contract test finds `OPEN_UNLINKED` and `FD_COUNT_LIMIT`
but fails because the authority document uses comma-formatted `65,536` and
`65,537` rather than the literal strings `65536` and `65537` required by the
test. The Makefile already names `man/openunlink.1`, so this is an unfinished
document integration phase, not a missing runtime dependency.

Classification: incomplete prior work, not a product runtime defect and not
an environment issue. The repair must add the required manual and guide with
the narrow NFS silly-rename/status-0 disclaimer, and make the authoritative
contract state the exact machine-checked boundary constants. The broader
contract-required documentation surface (README/CHANGELOG/QUALITY/TESTING/
architecture alignment) must remain in the same bounded documentation slice;
it must not be replaced by test suppression.

### Cluster C — distribution-test cascade, 1 failure

Affected test:

- `tests/test_sysdiff.py::test_dist_extracts_builds_and_tests_outside_workspace`

The distribution test builds and extracts a source archive, then runs the
nested suite. Its failure output reproduces the same 17 openunlink failures;
the sysdiff fixture shell checks and packaging install/reinstall checks pass
before the nested pytest returns nonzero. This is not an independent
distribution defect on current evidence.

Classification: derivative cascade from Clusters A and B, with no separate
repair justified. Rerun it after the focused openunlink fixture and
documentation/contract repairs. If it still fails after the nested suite is
green, open a separate packaging/environment slice. During the worker's
attempt, a separate read-only Git-admin failure also appeared in
`test_release_excludes_untracked_files`; that failure is not part of the
current 18-failure reproduction and should remain classified as host/runtime
evidence if it recurs.

## Task-shape and routing assessment

The producer route was deterministic and executable: `codex_cli` with
`gpt-5.6-sol` started under `bwrap`, and provider preflight had passed. There
is no evidence-based reason to change the producer route. The independent
`user_tester` route and semantic-judge provider were preflighted, but neither
could execute because the producing step halted first. Their absence from the
run is a consequence of the failed step, not a routing failure.

The playbook was too broad for one commissioning worker. It combined platform
readiness, cross-worktree reconciliation, full product validation, historical
evidence synthesis, and report authoring. It also declared relative inputs that
were absent from the configured workspace. The full suite was material but not
the dominant cause: the direct worker invocation took about 132 seconds and
the current read-only reproduction took about 118 seconds; the remaining time
was spent in model-directed reading, output processing, and investigation.

The safe decomposition is to keep routing policy unchanged and separate
product repair from commissioning. Each repair slice should have one coherent
root cause, narrow allowed paths, a focused validator, independent user test,
semantic review, and evidence verification. The commissioning playbook should
run short trusted preflight/report commands and preserve the existing human,
user-tester, semantic, identity, and evidence gates. It should not ask the
worker to rediscover all historical AgentFlow records or repair product tests.

## Smallest safe governed repair plan

These are recommendations only. No repair run was launched in this session.

### Slice 0 — correct the commissioning baseline and packet

Before another run, an authorized operator must choose a single post-hardening
baseline for `/home/lee/projects/linux-utilities-autonomous`. The recovery
documents/scripts currently live on the interactive checkout, while the
configured autonomous `main` worktree is at `15605e3` and lacks them. Align
the worktree to an approved post-hardening commit, or make the playbook's
trusted inputs explicitly absolute and verify them before the worker starts.
Do not copy files ad hoc inside a worker and do not weaken the identity gate.

Regenerate/lint the commissioning playbook if needed, keep the existing
deterministic route and independent evaluator route, narrow the worker packet
to current commissioning evidence, and use bounded read-only commands. A
preflight failure on a missing input must stop before spending a model attempt.

### Slice 1 — repair the openunlink seam fixture contract

Use a governed test-maintenance slice limited to the seam fixture and any
directly necessary expected-byte assertions. Preserve the product contract
that output `size=` is final `st_size`. Run the focused openunlink module and
record that all nine positive controls reach their intended injected calls;
the current baseline does not establish that because their controls fail
first. Do not change production code or delete/redesign tests based only on
the current size mismatch.

### Slice 2 — finish the bounded openunlink documentation/authority slice

Add the missing manual and `docs/openunlink.md`, update the required user-facing
and quality documentation consistently, and add the exact machine-checked
`65536`/`65537` boundary spelling to the authoritative contract. Keep the
NFS silly-rename/status-0 limitation explicit. Run focused tests, `make
man-check`, and the applicable documentation/format checks. This slice must
not suppress the two failing tests or broaden openunlink behavior.

### Slice 3 — rerun the cascade and only then investigate residuals

Run the focused module, the full pytest suite, and the distribution regression
after Slices 1 and 2. The distribution failure is expected to disappear if
the nested archive contains the repaired tracked files and the focused suite
passes. If a residual remains, create a new evidence-backed slice for that
residual rather than folding speculative source changes into the prior two.

### Slice 4 — re-run commissioning, separately authorized

Only after the repair slices pass their independent review and the autonomous
worktree is clean should an operator authorize another supervised
commissioning run. Keep the mission paused, do not restore cron, do not push,
and do not resume `e5e872615eed`. Require the same identity snapshots around
every worker attempt, deterministic route decisions, explicit user-tester
evidence, semantic-judge transcript, verified evidence manifest, and final
terminal result. A longer timeout is not a substitute for this decomposition;
retain 600 seconds unless a later run proves a specific near-completion case.

## Recommendation

**Not ready.** The platform evidence chain and repository identity checks for
`e5e872615eed` are sound, but the producer timed out without a report, the
semantic and independent tester gates never ran, the commissioning packet did
not match the configured autonomous worktree, and the current product baseline
has the 18 failures described above. After the specific baseline alignment,
fixture repair, documentation/contract repair, cascade rerun, and independent
review evidence are complete, Linux Utilities can be considered for another
separately authorized supervised commissioning run. No re-arm, cron restore,
push, resume, or production action is authorized by this report.
