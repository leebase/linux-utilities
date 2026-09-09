# Context

## Agentwatch failed-run closeout — 2026-09-09

Directed manual closeout of failed governed run `ee643f02e70a` completed the
`agentwatch` first vertical slice without resuming, relabeling, or modifying the
run archive. The run's only reported implementation-test defect was corrected:
`test_proc_stat_record_size_boundary` now compares the bytes token
`b"PROCFS_UNTRUSTED"` with bytes `CompletedProcess.stderr`. The overwritten
shared journey manifest was restored to its canonical 21-journey sysdiff form,
preserving delivered treehash/snslice behavior, and stale Makefile integrity
pins were advanced to the authorized agentwatch-integrated Makefile hash
`a4ea71c27b4a5f17db47a960a327e11d4fdebbe1a50123db7193682483c7d9f1`.

Final verification: focused agentwatch `102 passed`; complete `make test`
`1229 passed / 19 skipped / 0 failed`; GCC strict, Clang strict and syntax,
clang-format, clang-tidy, cppcheck, and Clang static analyzer gates all exited
0. Cppcheck's one actionable const-correctness finding was repaired. No
Auto-Orch mission state, governed run evidence, treehash source, or snslice
source was modified.

## Linux Utilities truth validation — 2026-09-07 UTC

Lee-authorized validation started on clean, synchronized `main` at
`02f20e81b0bf519b7bf72b454fc01dd6247df7cb`, after the reported `8877370`
checkpoint. The six historical failures in `tests/test_repair_a187b2fa74c9.py`
were four malformed bare-string command-claim failures and two child-interpreter
`employee_contract` import failures. Their exact historical diagnostics remain
in run `a868a10e150e`, step 05, attempt 2. The six already passed against actual
starting disk bytes, but global result-read interception could hide later bad
or missing evidence. Removed that interception and made the current repair
verifier read the disk artifact; added negative read-through regressions.

Initial `make test` reproduced a separate source-distribution defect:
941 passed, 22 skipped, 1 failed. The archive included mission/governance tests
without their workspace dependencies. Its explicit product inventory now
contains the four utilities and their required product tests/dependencies;
full-checkout governance coverage remains enabled. Updated exact Makefile pins
and current packaging documentation. C sources, manual pages, journey manifests,
and release recipes are unchanged.

Fresh governed run `187272ea3090` completed all three steps using clean
Agent-Orch `88af416b4667aa27d786e5fc1a6b87bab8a1f6d5`. Its new
`artifacts/user-test/result.json` covers all 21 manifest journeys, with nonempty
steps and object command claims carrying observed integer exits. Both journey
rules passed: 21 verified claims, zero skipped, four distinct command executions.
Nine fresh supporting captures and live stdin/readonly probes establish the
substantive observations beyond repeated help commands. Astra Low independently
reviewed the sealed evidence; the governed review passed with no findings and
its full-suite claim passed orchestrator re-execution. Run evidence verification:
6 chain entries, 94 artifacts, no divergence.
Standalone copied-artifact probes confirm valid evidence passes, missing
name/steps/commands and bare strings fail with exact-path diagnostics, a false
exit claim fails observed-exit comparison, and a non-allowlisted claim is not
executed and fails journey verification. The original six focused cases passed
again (6 passed, 0 skipped, 0 failed, 0.71s); actual artifact bytes are unchanged.

Verification: final `make test` 944 passed / 22 skipped / 0 failed (138.21s);
related six repair modules 125 passed; independent governed reviewer pytest
946 passed / 20 skipped / 0 failed (144.94s); clean-environment `make distcheck`
514 passed / 35 skipped / 0 failed, exit 0. GCC strict compilation and actual
GCC analyzer compilation passed for all four C sources; man and benchmark
checks passed. `make test-sanitize` remains visibly unavailable because native
Clang is absent. Native clang-format, clang-tidy, cppcheck, Valgrind, Ruff and
Black are also unavailable; local fallback wrappers/shims are not native-tool
passes. No tools were installed.

Earlier fresh run `bf791d975135` remains failed for insufficient semantic
proof; `9965e95fc78e` remains failed for a task-harness import error corrected
before the final new run. Expected-negative retry probe `a347573853b6` remains
failed by design: its complete stderr and bounded retry feedback were verified
without claiming model consumption. No failed run was resumed or relabeled.
Historical failed run artifacts were not modified and no live-run recovery is
claimed. Agent-Orch and unrelated repositories were not modified. Deferred
release-policy investigation is recorded in
`tmp/linux-utilities-contract-validation/ask-lee.md`; it does not block this
bounded validation or authorize a release or scheduling change.

## Supervised stale-oracle remediation — 2026-09-05

Lee-authorized manual remediation refreshes the two post-chain Makefile hash
pins while preserving the unchanged `src/sysdiff.c` pin. Smoke now builds
`build/sysdiff` and checks tiny unchanged, changed, and malformed snapshots
under ten-second startup/check budgets; `make test` retains full coverage.
Dependent smoke-contract assertions and testing guidance are aligned.
Removed stale `artifacts/user-test/result.json` with placeholder journey
evidence rather than fabricate fresh claims. Existing artifact guards still
validate fresh evidence; journey manifests and behavior tests are unchanged.

Validation: `bash scripts/smoke.sh` exit 0; requested four repair modules
via `pytest -q` exit 0, 75 passed / 2 skipped in 1.53s (existing
absent-artifact guards); full `make test` exit 0, 830 passed / 23 skipped
in 138.52s. Smoke also rejects incorrect output and incorrect status.
`git diff --check` passes. Source SHA-256 remains
`1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1`;
Makefile SHA-256 remains
`59b45e65b60b70520a56ce35dfa779dc980a46d9a0a708424ebebbf6692b698c`.
No governed run was launched; unrelated pre-existing edits are preserved.

## Post-hardening commissioning preparation — 2026-08-01

The autonomous `main` worktree is prepared for another supervised commissioning
cycle, but no run was launched. The missing e5e872615eed inputs were the four
recovery documents and two recovery scripts that existed only in the
interactive hardening checkout. A bounded packet now lives under
`commissioning/`, with a manifest and `check_packet.py`; the prepared playbook
declares only that packet, the narrow verifier inputs, and mission authority
files. Agent-Orch preflight now rejects missing or unreadable declared inputs
before worker invocation while allowing outputs produced by earlier steps; its
focused platform test and the full platform-commissioning test module pass.

The openunlink fixture slice now derives default expected `size` from supplied
link bytes, preserving explicit boundary sizes. The documentation/contract
slice adds the guide and manual and records exact `65536`/`65537`, final
`st_size`, final `st_nlink == 0`, and NFS silly-rename semantics. Validation:
focused openunlink `134 passed` in 46.42s; complete suite `548 passed,
18 skipped` in 117.16s; distribution extraction `1 passed` in 60.12s;
identity JSON and protection dry-run passed; packet completeness passed for
10 inputs; strict repaired-playbook lint passed; and `git diff --check` passed.
The guarded pruner dry-run was safe and listed one terminal old candidate
(`5a3c165c0a46`) without deleting it. Mission state is halted/paused and
auto-orch preflight refuses to start it, but the host crontab still contains an
uncommented Linux Utilities loop line. Treat that residual schedule as a
governance blocker to autonomous re-arm; do not change it, push, restore cron,
re-arm, or launch the prepared playbook without authorization.

## Snapshot

Governed repair run `ec1d95cebdc9` (`repair_governed_run_a868a10e150e`) has
successfully repaired and verified the failure from governed run `a868a10e150e`.
Origin `a868a10e150e` remains **FAILED** in the historical record
(`/home/lee/projects/linux-utilities-agent-orch-runs/a868a10e150e`): it failed
validation when executing regression check `python3 -m pytest
tests/test_repair_a187b2fa74c9.py: test_user_test_result_commands_run_are_objects_not_bare_strings`
because `artifacts/user-test/result.json` recorded user journey command claims
as bare strings rather than structured objects with required `command` and
`exit_code` properties under Draft 2020-12 `USER_JOURNEYS_RESULT_SCHEMA`.
Recovery run `ec1d95cebdc9` established normative repair contract
`docs/repair-a868a10e150e-contract.md` (AC-1, AC-2, AC-3), comprehensive
regression suite `tests/test_repair_a868a10e150e.py`, repair implementation
`src/repair_a868a10e150e.py`, and synchronized user journey manifests in
`tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`
preserving all 21 required journeys. Orchestrator validation under step 3
attempt 2 passed all gates: pytest recorded 49 passed in 1.64s (duration
2.493474s, exit 0), black check exit 0 (duration 0.020066s), and ruff check
exit 0 (duration 0.0188s). Independent review artifacts
`code-reviews/review-repair-a868a10e150e.md` and
`code-reviews/review-repair-a868a10e150e.verdict.json` record verdict `pass`
with zero findings (0 Critical, 0 High, 0 Medium, 0 Low). Blast radius was
strictly contained: source hash for `src/sysdiff.c` remains
`1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1` and
Makefile hash remains
`59b45e65b60b70520a56ce35dfa779dc980a46d9a0a708424ebebbf6692b698c`. Live
portfolio remains three implemented utilities plus planning-only `inodealias`,
`shebangcheck`, and `openunlink`, with reviewed `sparsemap` selection evidence only.

## What's Happening Now

Recovery run `ec1d95cebdc9` is closing out handoff after independent review
verdict `pass` confirmed resolution of the result schema and bare string
command claims defect without regressions or product modifications. Origin run
`a868a10e150e` (and ancestor `a187b2fa74c9`) remains labeled Failed in the
historical run archive; recovery `ec1d95cebdc9` provides the authoritative
verified repair and review evidence. Prior visible debt stays open: pathaudit
Medium `PAW1-DOC-901` and Lows from `c9e3de33f46b`; PA-6CA-4 and PA-6CA-1/2/3;
permguard recovery/bootstrap Lows; FUM5 Mediums/Lows; `openunlink` `SIXTH2-M1`–`M3`
and Lows; seventh-mission `SEV7R-*`. Planning order is unchanged: `inodealias` →
`shebangcheck` → `openunlink` ahead of any seventh-utility CODE. Host crontab
retains an uncommented Linux Utilities loop line, serving as a governance
blocker to autonomous re-arm until authorized scheduling reconciliation. Runs
root: `/home/lee/projects/linux-utilities-agent-orch-runs`.

## Prior snapshot — governed run af89bd4b8fcd repair (f4d805b7b217)

Documentation-only repair of AgentFlow records for failed governed run
`af89bd4b8fcd` (`repair_governed_run_9add44496178`) was recorded under
recovery run `f4d805b7b217`. Origin `af89bd4b8fcd` stays **FAILED** after
step_03_code_repair HALTed on an authoring-contract path-scope defect:
attempt 2 changed `tests/test_governed_run_9add44496178.py` and
`tests/test_sysdiff.sh` outside step_03 `allowed_paths` (`src`,
`Makefile`, `dist`), even though that attempt's clang `-fsyntax-only` and
focused pytest recorded 74 passed in orchestrator validation. That slice
updated only `context.md` and `result-review.md`; it did not author a new
contract, plan, source file, test, or smoke oracle, and it did not claim
fresh smoke, full quality, sanitizers, Valgrind, or independent review for
that documentation step. Live portfolio remains three implemented utilities
plus planning-only `inodealias`, `shebangcheck`, and `openunlink`, with
reviewed `sparsemap` selection evidence only.

## Prior snapshot — pathaudit PA-W1 open-repair `c9e3de33f46b`

Governed run `c9e3de33f46b` (`pathaudit_open_repair_maintenance`) closed Low
`PA-W1` under `docs/pathaudit-open-repairs-contract.md`:
`symlink_is_self_basename` no longer reserves a 65,537-byte automatic
`readlink` buffer; it allocates `strlen(command) + 1` bytes, compares only
when `readlink` returns exactly the command length, frees before every
return, and propagates allocation failure as stderr-only `OUT_OF_MEMORY`
status 2 rather than a silent non-match. Bare `tool -> tool` remains
reject-closed `INSPECTION_ERROR_<ELOOP>`; slash-bearing and byte-different
loops stay non-candidates. Exact step-5 evidence: focused pathaudit pytest
156 passed / 15 skipped; GCC/Clang strict, clang-format (one line-break
repair), clang-tidy, cppcheck, Clang analyzer exit 0; focused ASan+UBSan and
Valgrind each 156/15; complete `make quality` exit 0 with ordinary / ASan /
UBSan / Valgrind each 359 passed / 15 skipped (scratch writable gitdir).
Smoke start/check 0 with empty blockers; check.log
`356 passed, 18 skipped in 21.16s` (sysdiff-centered; not a dedicated PA-W1
oracle). Independent verdict
`code-reviews/review-pathaudit-open-repairs.verdict.json` is `pass` with no
Critical or High; remaining Medium `PAW1-DOC-901` (roff `\"` comment swallow
in new DIAGNOSTICS form) and Lows `PAW1-DOC-902`, `PAW1-TEST-903`,
`PAW1-TEST-904`, `PAW1-SCOPE-905`. This does not install, package, tag,
publish, or release `pathaudit`.

## Prior snapshot — seventh utility recovery `4824cd763b27`

Bounded recovery run `4824cd763b27`
(`template_repair_before_review_feature_delivery`) reconciled the completed
post-repair seventh-mission evaluation left by failed origin run
`f7539c314ca1` (`discover_evaluate_seventh_linux_utility`) and obtained a
fresh independent High-threshold review of the on-disk `sparsemap`
recommendation. Origin `f7539c314ca1` remains **FAILED**: its step-2
attempts exited `0`/`124`/`124` under a 600-second worker ceiling after
review attempt 2 failed High `SEV7-H1` on the pre-repair `elfinterp`
winner; those timed-out repair attempts are distinct from this recovery,
which does not rewrite the origin run to passed. Fresh verdict
`code-reviews/review-seventh-utility-mission-evaluation-recovery.verdict.json`
is `pass` with no Critical or High findings. Remaining Mediums are
`SEV7R-M1`/`SEV7R-M2`; remaining Lows are `SEV7R-L1`/`SEV7R-L2`. Weighted
totals: `sparsemap` 141, `cgroupceil` 134, `mountstack` 130, `lockscope`
128, `elfinterp` 128 with novelty hard-gate fail. Allowlisted check:
focused `tests/test_governed_run_c847e01d15fe.py` → 4 passed / 0 skipped.
Smoke check.log `351 passed, 18 skipped in 20.99s` (sysdiff-centered; not
`sparsemap` product evidence). No `sparsemap` source, test, build, man page,
package, install, tag, publication, or release exists or was authorized.

## Prior snapshot — sixth utility mission `787b9bb3d830`

Governed run `787b9bb3d830`
(`discover_and_evaluate_sixth_linux_utility`) selected and independently
reviewed exactly **Bootstrap `openunlink` explicit-process zero-link regular-file descriptor reporting**.
For one explicit Linux PID, the
planning-only utility would report descriptors whose stable followed target is
a regular file with `st_nlink == 0`; it would not trust procfs suffix text,
scan every PID, open target content, group inodes, estimate reclaimable space,
signal a process, install, package, publish, or release. The first slice
proposes the closed `--help` / `--version` / PID CLI, bounded numeric
`/proc/PID/fd` enumeration, repeated metadata checks, escaped
`OPEN_UNLINKED` findings, visible advisories, a manual, focused fixtures,
quality gates, dedicated smoke, and independent review. No implementation
artifact exists.

The independent verdict is `pass` with no Critical or High findings. Remaining
Mediums are `SIXTH2-M1` (descriptor-cap partial evidence), `SIXTH2-M2`
(filesystems that retain nonzero link count), and `SIXTH2-M3` (status-1 caller
discrimination); remaining Lows are `SIXTH2-L1` (stderr writes),
`SIXTH2-L2` (defensive size-range reachability), and `SIXTH2-L3` (stale
run-step wording). Review only byte-compiled the three existing pytest modules;
the separate 351-passed / 18-skipped smoke is sysdiff-centered aggregate
evidence, not an `openunlink` build or test.

## Prior snapshot — permguard recovery `5035933ac7b4`

Governed recovery run `5035933ac7b4` (`repair_governed_run_ba6dc2fdd199`)
reconciled the dirty permguard Medium-repair candidate left by failed run
`ba6dc2fdd199` and obtained a clean independent review. Exact focused
permguard pytest is 63 passed / 0 skipped. Step-5 complete `make quality`
exited 0; ordinary, ASan+UBSan, and Valgrind routes each reported
354 passed / 15 skipped under a scratch writable gitdir for this host's
read-only git common dir. Governed smoke (`artifacts/user-smoke/result.json`)
passed with `app_started`/`core_flow_completed` true, start/check exit 0,
empty `blocking_errors`; check.log pytest
`351 passed, 18 skipped in 21.76s`. Independent verdict
`code-reviews/review-governed-run-ba6dc2fdd199.verdict.json` is `pass` and
closes Medium PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512.
Remaining findings are Low PGR-TEST-706, PGR-PORT-707, PGR-BUILD-708,
PGR-TEST-709, and PGR-DOC-710. Failed run `ba6dc2fdd199` itself is still
not a passed delivery.

## Prior snapshot — pathaudit recovery `4ae7a820b0a3`

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
Failed run `6ca4cebc8527` itself is still not a passed delivery. Later
recovery `5035933ac7b4` closed the overlapping permguard Medium backlog
without treating this pathaudit recovery as superseded for its own IDs.

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
