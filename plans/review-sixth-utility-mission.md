# Independent Review — Sixth Utility Mission Selection

Subject: `plans/sixth-utility-mission-evaluation.md` (decision date 2026-07-30,
551 lines), reviewed against the step-02 mission charter, the live portfolio
evidence, and the governance records that constrain later implementation.

Committed mission under review: **Bootstrap `openunlink` explicit-process
zero-link regular-file descriptor reporting**.

Verdict: **pass**. Six findings are recorded — three Medium and three Low. No
finding is High or Critical. The Mediums must be resolved by the later governed
contract step before code is accepted, but none of them undermines the choice of
candidate or the shape of the slice. This review approves mission *selection*
only; it does not clear the live repair-before-expansion gate and does not
authorize an implementation playbook.

## Checks Run

The one allowlisted repository check for this review step was
`python3 -m compileall -q tests/test_sysdiff.py tests/test_pathaudit.py
tests/test_permguard.py`, which exited `0`. That command byte-compiles the three
live per-utility pytest modules named in the evaluation's Portfolio Evidence
section and confirms they remain syntactically valid Python in the current dirty
worktree, so the evaluation's claim of three complete source/test/manual triplets
rests on test modules that still parse.

Separate executable user evidence is `artifacts/user-smoke/result.json`, which
records `app_started: true`, `core_flow_completed: true`, `start_exit_code: 0`,
`check_exit_code: 0`, and an empty `blocking_errors` array.
`artifacts/user-smoke/check.log` corroborates the aggregate figure the evaluation
quotes: the sysdiff fixture acceptance path passed and the pytest aggregate
reported `351 passed, 18 skipped in 21.56s`. `tests/smoke_manifest.json` names
only sysdiff steps (`tests/smoke_start.py`, `scripts/smoke.sh`,
`tests/test_sysdiff_fixture.sh`, `tests/check_sysdiff_smoke.py`), which matches
the evaluation's own careful statement that this is sysdiff smoke plus aggregate
regression evidence rather than a pathaudit or permguard user-flow claim. No
non-allowlisted script, shell, or `make` command was run for this review, and no
product, test, manual, smoke, or shared-state file was modified.

Read-only corroboration of the document's cited evidence was performed by reading
the referenced repository files directly. `src/` holds exactly `sysdiff.c`,
`pathaudit.c`, and `permguard.c`, with no fourth, fifth, or sixth binary.
`plans/fourth-utility-mission-evaluation.md` reserves `inodealias`, and the
`project-plan.md` Mission Contract reserves `shebangcheck` as the fifth mission,
so both reservations the evaluation relies on are real. Every debt identifier
cited was confirmed in its named source:
`code-reviews/review-fourth-utility-mission.verdict.json` carries Medium
`FUM-M1`; `code-reviews/review-fifth-utility-mission.verdict.json` carries
Mediums `FUM5R2-M1` through `FUM5R2-M6`; `result-review.md` and `sprint-plan.md`
carry `PA-6CA-4`, `PA-M1`, `PA-M2`, `FUM5-M1`, and `FUM5-M2`; and the packaging
runs `939ee21b0d76`, `240bfcbc634e`, `b54d61531266`, and `a2d750c92da3` appear in
`result-review.md` as described. The repair-before-expansion gate is live at
`project-plan.md:231`, `sprint-plan.md:397`, `sprint-plan.md:738`,
`STATUS.md:149`, and `WHERE_AM_I.md:368`, and the evaluation cites it correctly.

## Lens Notes

**Prior-finding closure.** This is attempt 2. `run.json` records that cycle 1
failed on `SIXTH-H1` (mid-scan descriptor churn classified as the operational
code `FD_RACE`, discarding every already-collected `OPEN_UNLINKED` line) and
`SIXTH-H2` (a readiness paragraph naming only Low debt while omitting the
repair-before-expansion gate). Both are genuinely closed, not re-worded. Churn is
now the status-1 advisory `FD_UNSTABLE` that preserves stable findings, and
output streams in numeric descriptor order (lines 326-332 and 352-362); the open
Medium debt is enumerated by identifier with sources, and the gate is stated with
all four citations (lines 68-87).

**Duplicated capability.** Clear. Zero-link descriptor reporting for one explicit
PID does not compare snapshot maps (`sysdiff`), assess PATH trust or executable
shadowing (`pathaudit`), report mode bits (`permguard`), group
`(st_dev, st_ino)` aliases (planning-only `inodealias`), or parse interpreter
headers (planning-only `shebangcheck`). Inode aggregation is the nearest
collision, and it is both forbidden in the non-goals (line 545) and fenced by an
acceptance oracle requiring duplicated descriptors for one object to emit
separate ascending-FD lines rather than grouped rows.

**User value and selection rigor.** The scorecard arithmetic is correct in all
six columns (43, 42, 44, 40, 38, 41), and the document does not conceal that
`futuremtime` outscores the selection by one point. The override is argued on
substance — link count is a stronger predicate than the cosmetic ` (deleted)`
suffix, and the manual alternative is race-prone — rather than by quietly
adjusting scores, and the fifth round's rejection of `openunlink` is answered
with named controls instead of being ignored. Two honesty gaps remain: the
success claim has no stated boundary for filesystems where unlink does not zero
`st_nlink` (SIXTH2-M2), and the meaning of status 1 is not pinned as a caller
contract (SIXTH2-M3).

**Unix architecture and dependencies.** One-shot, single translation unit, one
explicit operand, deterministic ordered text on stdout, diagnostics on stderr; no
daemon, watcher, network, telemetry, plugin, configuration file, or cloud call.
Runtime dependencies are libc plus fixed `/proc`; pytest and the existing quality
tools drive validation only. The one hidden dependency is environmental rather
than packaged: the mandatory dedicated smoke needs a mounted, readable procfs.
Because the fixture holder is a same-UID child it stays visible under `hidepid`,
so this is a narrow residual risk and is not raised as a finding.

**Hostile input and bounds.** The user supplies only a decimal PID, but procfs
supplies descriptor names and target bytes. The ceilings are concrete and
self-consistent: 65,536 retained descriptors; 65,536 accepted link-text bytes
read into a 65,537-byte sentinel buffer so an exact fit is distinguishable from
truncation; and a line buffer sized for the true worst case of four-byte `\xNN`
escaping (`"` and `\` cost only two). Descriptor-name grammar is canonical ASCII
decimal with a no-leading-zero rule, and the count cap is correctly separated
from the fd-number range, so a process with a high `dup2` target and few open
descriptors is not falsely capped. The count cap's failure mode is the one real
problem in this area (SIXTH2-M1).

**C implementation realism.** Achievable in one C17 translation unit. Ownership
is assigned explicitly for the `DIR *` duplicate versus the retained inspection
descriptor with no double close after `fdopendir`, `readdir` storage is borrowed
only until the next call, all allocation completes before streaming starts,
`_FILE_OFFSET_BITS=64` and `<inttypes.h>` formatting are required, and narrowing
from `pid_t`, `off_t`, `ino_t`, `dev_t`, `nlink_t`, and `size_t` is prohibited.
The before/after `(st_dev, st_ino, file type)` comparison with `st_nlink == 0` on
the final observation is implementable and truthfully disclaims ABA replacement.

**Exit behavior.** Three statuses; `SIGPIPE` ignored so closed stdout reaches the
checked `STDOUT_WRITE` path; status-2 numeric precedence stated without
retracting streamed stdout; a defined empty-stdout rule for pre-inspection
failures; and distinct stderr shapes for per-descriptor, PID-owned, and global
diagnostics. Two gaps: status 1 carries two materially different meanings whose
discriminator is never made normative (SIXTH2-M3), and stderr write failure is
unspecified even though the sibling `shebangcheck` contract pins it at
`project-plan.md:204-205` (SIXTH2-L1).

**Acceptance checks and first-slice size.** Fifteen bullets cover exact bytes,
every advisory code, seam-injected `errno` mapping without root or a `hidepid`
mount, escaping of hostile bytes, sanitizers, Valgrind, dedicated smoke, and
independent review; the sysdiff smoke is explicitly demoted to aggregate
regression evidence. The notable omissions are a filesystem-boundary check for
SIXTH2-M2 and a caller-discriminator check for SIXTH2-M3. The slice is large —
contract, source, seam-instrumented tests, a handshake-driven helper process, man
page, smoke, and review — but it stays at one binary with one finding code and
defers install, packaging, tagging, and publication. It sits at the upper bound
of a bootstrap rather than past it, so no scope finding is raised.
