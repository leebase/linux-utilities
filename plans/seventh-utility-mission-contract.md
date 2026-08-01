# Seventh Utility Evaluation Recovery Contract

## Recovery Authority and Purpose

This contract governs only the bounded planning-evidence recovery of governed
run `f7539c314ca1` (`discover_evaluate_seventh_linux_utility`). That origin run
remains **FAILED**. Nothing in this contract changes its status, treats either
exit-124 repair attempt as a pass, adopts a prior review attempt selectively,
or claims that the origin run completed successfully.

The recovery's bounded purpose is to validate the already completed on-disk
seventh-utility evaluation and its post-repair recommendation of **`sparsemap`**:
filesystem-reported logical data/hole ranges for explicit regular files via
`SEEK_DATA` and `SEEK_HOLE`. The evaluation is unreviewed working-tree residue
from the failed repair loop, not accepted selection authority. The purpose of
this playbook is to reconcile that existing evidence and obtain a fresh
independent verdict before any implementation may be proposed or authorized.

Mission discovery is closed for this recovery. It must not generate another
candidate survey, replace the fixed candidate set, change the weights or
qualification gates to improve an outcome, or repeat the earlier discovery
exercise. The fixed evidence set is `sparsemap`, `cgroupceil`, `mountstack`,
`lockscope`, the duplicate-gated `elfinterp`, and honest deferral. Only the
smallest edits needed to make the existing evaluation internally consistent,
traceable, and reviewable are permitted.

The fixed post-repair arithmetic is `sparsemap` 141, `cgroupceil` 134,
`mountstack` 130, `lockscope` 128, and `elfinterp` 128 out of 168;
`elfinterp` fails the Novel capability hard gate with raw score 0. These facts
are evidence to re-check, not proof of a governed pass. `sparsemap` remains a
recommendation pending fresh review, not an implemented or authorized seventh
utility.

## Frozen Evaluation Basis

The ten weighted criteria remain Practical usefulness (5), Novel capability
(5), One-purpose smallest useful slice (5), Security and privilege posture
(5), Unix fit and composability (4), Deterministic testability (4), C
auditability and ownership (4), Dependency economy (4), Portability honesty
(3), and Maintenance burden (3). Raw scores remain integers from 0 through 4.
Qualification still requires at least 126 of 168, raw scores of at least 3 in
the first four criteria, and no disqualifying closed hazard. Ties still resolve
by Practical usefulness, then safer privilege posture, then smaller dependency
surface, then smaller first-slice state space; a remaining tie requires honest
deferral.

The recovery must preserve the evaluated portfolio boundary. `sysdiff` is
implemented and released at v0.1.0. `pathaudit` and `permguard` are implemented
preview utilities but remain uninstalled and unpackaged. `inodealias`,
`shebangcheck`, and `openunlink` remain planning-only reservations with no
source, tests, manual, build, or dedicated smoke evidence. A seventh mission
must remain capability-distinct from all six even if every reservation is
later delivered.

The existing evaluation must continue to disclose candidate provenance:
`mountstack`, `lockscope`, and `cgroupceil` were considered in the fifth
evaluation; `sparsemap`, `mountstack`, and `cgroupceil` were considered in the
sixth evaluation; only `elfinterp` was newly introduced by the failed origin
run. Earlier scores used different criteria and scales and are not numerically
comparable. This recovery must not describe the field as a fresh high-yield
survey.

The recommendation must remain narrow and honest. `sparsemap` may report only
logical data/hole observations returned by the filesystem for caller-selected
regular files. It must not imply physical allocation, exclusive ownership,
sharing, compression, reclaimable space, copy correctness, or faithful sparse
distinction on every conforming filesystem. Its scores of 2 for Deterministic
testability and 2 for Portability honesty, its seven-point margin over
`cgroupceil`, and the possibility that a filesystem reports all regions as
data remain material limitations for independent review.

## CLI Surface

Product CLI decisions are deferred because this is a planning-only recovery.
This contract does not establish a `sparsemap` executable name as shipped
authority, command grammar, option spelling, operand count, help or version
bytes, output record shape, diagnostic syntax, ordering rule, resource
constant, signal behavior, or compatibility promise. Capability-level mention
of explicit regular-file operands and filesystem-reported logical ranges is
permitted only to identify the recommendation being reviewed.

A later, separately approved implementation playbook must begin with a
normative product contract before any CLI decision becomes authoritative. The
present recovery may verify that the evaluation consistently defers those
decisions, but it may neither fill them in nor treat examples, candidate labels,
or review prose as an accidental interface. A fresh planning-review verdict
does not itself authorize that later contract or any implementation.

## Closed Hazard Taxonomy

The discovery hazard taxonomy remains closed to exactly the following ten
classes. Reconciliation may use only the ratings `clear`, `bounded with
explicit mitigation`, and `disqualifying`; it may describe manifestations
inside a class but may not add an eleventh or miscellaneous class. Using these
hazards to review the frozen evaluation is evidence validation, not permission
to generate candidates, rescore the field, or renew mission discovery.

1. **Duplicate implemented capability.** Reject behavior that repeats
   `sysdiff` explicit snapshot comparison, `pathaudit` PATH trust and command
   resolution analysis, or `permguard` explicit-path mode-bit reporting under
   another name or input spelling.
2. **Duplicate reserved mission.** Reject explicit-path filesystem identity or
   hard-link grouping reserved for `inodealias`, direct-interpreter shebang
   preflight reserved for `shebangcheck`, and explicit-process zero-link
   regular-file descriptor reporting reserved for `openunlink`. Capability
   novelty, not file format or executable name, is controlling.
3. **Duplicate polish, repair, or release work.** Reject a mission whose main
   result is tests, fixtures, documentation, manuals, compiler gates,
   formatting, static analysis, sanitizers, Valgrind, benchmarks, smoke,
   installation, packaging, publication, backlog repair, or another feature of
   an existing utility rather than a distinct executable capability.
4. **Weak practical value or Unix fit.** Reject speculative problems,
   information dumps without a concrete bounded decision, non-composable
   interactive workflows, trivial wrappers, and slices that are not useful on
   their own.
5. **Excessive scope or maintenance pressure.** Reject policy engines,
   recursive whole-system discovery, bundled modes, evolving languages,
   unbounded input, persistent catalogs, and any useful behavior that cannot
   remain small and closed.
6. **Hostile-input and security exposure.** Reject candidates that cannot
   bound hostile bytes, counts, paths, records, offsets, or kernel data; render
   output terminal-safely; avoid executing inspected content; and state
   race/TOCTOU limits without overstating safety or authorization.
7. **Privilege and side-effect hazard.** Reject a baseline that needs root,
   set-ID installation, Linux capabilities, `ptrace`, process signaling,
   namespace changes, mounting, device writes, permission changes, or other
   mutation. The core useful path and fixtures must be unprivileged.
8. **Dependency or service growth.** Reject a first slice requiring runtime
   dependencies beyond libc, external command orchestration, an interpreter,
   database, network, remote API, daemon, watcher, scheduler, telemetry,
   plugins, or disproportionate build and CI machinery.
9. **Portability and ABI hazard.** Reject a candidate whose Linux, POSIX,
   kernel, libc, filesystem, procfs, sysfs, namespace, architecture, or
   feature-test boundary cannot be specified and tested honestly. Platform
   headers and native types are mandatory; hand-declared interfaces are not.
10. **Non-deterministic or privilege-fragile evidence.** Reject a mission whose
    essential behavior cannot be covered by stable fixtures or a narrow seam,
    whose ordinary results depend on uncontrolled host timing or global state,
    or whose core positive cases routinely skip for privilege, kernel
    configuration, filesystem behavior, or uncommon hardware.

The prior origin-review debt is retained until a fresh independent review
explicitly adjudicates it. Review attempt 1 reported a clean-at-High-threshold
pass but was retried because its claimed pytest result disagreed with
orchestrator re-execution. Review attempt 2 then failed the same `elfinterp`
artifact on High `SEV7-H1`. That disagreement is evidence, not permission to
choose the favorable verdict. The repair candidate replaces `elfinterp` with
`sparsemap`, but `SEV7-H1` is not closed merely by the presence of changed
bytes. Reconciliation may itemize how the on-disk evaluation appears to
address each SEV7 finding; apparent address is not accepted closure.

The remaining origin findings also stay visible: `SEV7-M1` for recycled
candidate provenance, `SEV7-M2` for the inflated content-derived-path security
score, `SEV7-M3` for conflicting frame authority, `SEV7-L1` for omitted
released-versus-preview portfolio labels, and `SEV7-L2` for missing external
source observation provenance. The attempt-2 frame marker and attempt-3
evaluation, as reconciled in recovery run `4824cd763b27`, appear to address
these items, but they remain unreviewed residue from failed attempts and are
not accepted closures until a fresh independent REVIEW says so.

Recovery-review debt also remains part of the evidence record:
`REC7-M1` preserves the disagreement between the two origin review attempts;
`REC7-M2` requires repaired SEV7 items to be described as apparently addressed
but still unreviewed rather than as residual unperformed work; `REC7-L1` and
`REC7-L2` require accurate timeout/classifier evidence and a complete residue
inventory; `REC7-L3` requires later AgentFlow handoff reconciliation; and
`REC7-L4` preserves the missing pre-edit-hash provenance limitation. This
contract does not claim any of those findings closed.

## Exit Statuses

Product exit-status decisions are deferred because this is a planning-only recovery.
No numeric status for a future `sparsemap` process, no clean versus
finding distinction, no operational-error precedence, no partial-output rule,
and no signal-derived shell behavior is defined here. Those decisions belong
only in a later normative implementation contract after this evaluation
recovery receives its own fresh independent review.

The recorded statuses of the governed origin run are evidence, not product
semantics: `f7539c314ca1` is `FAILED`; step-2 attempt 1 exited 0; attempts 2
and 3 exited 124 after the recorded 600-second worker timeout; and neither
timed-out attempt is a silent pass. Existing user-smoke start/check zeros apply
to the repository's mechanical sysdiff-centered smoke route, not to a
`sparsemap` binary or future `sparsemap` exit contract.

## AgentFlow Phase Boundary and Required Gates

AgentFlow phases TEST, CODE, user-facing DOCUMENT, and TEST + FIX are omitted because this recovery changes planning evidence only.
It must not create or modify product source, product tests, build rules,
manuals, README or release material, binaries, packages, or quality evidence.
Internal Markdown beneath `plans/` is planning evidence, not user-facing
product documentation.

TEST AS USER and REVIEW remain as separate required gates later in this playbook.
TEST AS USER must run the existing mechanical smoke flow and record its actual
result without claiming that it exercises `sparsemap`. REVIEW must
independently inspect the reconciled evaluation, the frozen contract, prior
review disagreement, hazard ratings, sparsemap limitations, and all retained
debt, then issue a fresh verdict. Neither gate may be replaced by the other or
inferred from evidence left by `f7539c314ca1`.

## Explicit Non-goals

This recovery excludes source, tests, builds, and product documentation. It
must not create or edit C source; unit, integration, regression, fixture, fuzz,
sanitizer, Valgrind, or smoke tests; Makefiles or other build wiring; binaries
or generated build products; manuals, README text, changelogs, release notes,
or any other user-facing documentation. It does not run product compilers,
formatters, static analyzers, sanitizers, Valgrind, coverage, benchmarks, or a
new utility's test suite.

This recovery also excludes installation, packaging, tagging, publication, and
release. It may not install a binary or dependency, add install/uninstall
rules, create an archive or package, create or move a tag, push or publish an
artifact, announce availability, or make any release-readiness claim for
`sparsemap` or another seventh utility.

It excludes implementation authorization and any claim that governed run
`f7539c314ca1` succeeded. It does not turn the on-disk sparsemap recommendation
into an accepted selection, close prior findings by assertion, reinterpret
timeout 124 as success, claim that existing aggregate tests or smoke cover a
seventh utility, reorder earlier planned missions, expand an existing utility,
or begin a normative product contract. A failed fresh review leaves the
recommendation unaccepted and implementation unauthorized; it does not justify
lowering the gates or restarting mission discovery inside this recovery.

## Recovery Acceptance Checks

1. Read-only run evidence still identifies `f7539c314ca1` as `FAILED`, records
   step-2 attempt exits 0/124/124, preserves the two origin-review outcomes,
   and never relabels a failed or timed-out attempt as passed.
2. The candidate set, criteria, weights, 126-point threshold, hard minimums,
   and tie-break order remain frozen. No new candidate search or mission
   discovery occurs.
3. Arithmetic re-checks reproduce `sparsemap` 141, `cgroupceil` 134,
   `mountstack` 130, `lockscope` 128, and `elfinterp` 128 with Novel capability
   0 and a failed hard gate. Any mismatch fails reconciliation rather than
   inviting score changes for convenience.
4. Reconciliation and REVIEW check the existing candidate reasoning and
   sparsemap recommendation against every class in the Closed Hazard Taxonomy,
   using only the three allowed rating phrases when a rating is recorded. A
   bounded hazard remains a named limit or deferral; a disqualifying conflict
   fails the recovery rather than triggering a new survey, score adjustment,
   or substitute recommendation.
5. The sparsemap recommendation retains its filesystem-reporting limitation,
   testability and portability scores of 2, provenance as a recycled
   candidate, seven-point margin over `cgroupceil`, and prohibitions on
   physical-allocation, sharing, compression, reclaim, or copy-correctness
   claims.
6. The evaluation itemizes `SEV7-H1`, `SEV7-M1`–`M3`, and `SEV7-L1`–`L2` as
   apparently addressed in failed-attempt residue but pending fresh
   adjudication. Recovery findings `REC7-M1`–`M2` and `REC7-L1`–`L4` remain
   visible where relevant and are not silently declared closed.
7. CLI surface and product exit statuses remain deferred. The evaluation makes
   no command grammar, output grammar, diagnostic, signal, resource-constant,
   source-layout, or implementation decision.
8. The evaluation states that TEST, CODE, user-facing DOCUMENT, and TEST + FIX
   are omitted because only planning evidence changes, while TEST AS USER and
   REVIEW remain separate required later gates in this playbook.
9. TEST AS USER reports only the existing mechanical smoke outcome and REVIEW
   produces a fresh independent verdict on the reconciled planning evidence.
   Neither result is represented as a sparsemap build, product test, dedicated
   smoke, implementation review, or release gate.
10. Structural validation finds the exact Markdown headings `CLI Surface`,
    `Closed Hazard Taxonomy`, `Exit Statuses`, and `Explicit Non-goals`
    exactly once, with at least 120 non-whitespace characters beneath each.
11. Reconciliation writes stay inside the three existing seventh-mission
    planning files: `plans/seventh-utility-mission-contract.md`,
    `plans/seventh-utility-mission-evaluation.md`, and
    `plans/seventh-utility-mission-frame.md`. No second contract is created,
    no scratch artifact counts as governed output, and no product source,
    test, build, man page, README, or AgentFlow handoff file is changed by
    this planning-only recovery step.
