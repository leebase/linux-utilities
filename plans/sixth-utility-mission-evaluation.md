# Sixth Utility Mission Evaluation

Decision date: 2026-07-30. This document selects a mission for later governed
delivery. It does not implement, compile, test, install, package, publish, or
release a sixth utility, and it does not change the authority or backlog of any
existing or previously selected mission.

## Portfolio Evidence

The live portfolio contains three implemented utilities, each represented by a
C source, a focused test surface, and a section-1 manual:

- `sysdiff` compares two explicitly supplied `key=value` snapshot maps after
  complete validation and emits a deterministic sorted diff. The implementation
  is `src/sysdiff.c`, its main contract tests are in `tests/test_sysdiff.py` and
  `tests/test_sysdiff_fixture.sh`, and its user contract is published in
  `man/sysdiff.1`. `README.md` identifies it as released at `v0.1.0`.
- `pathaudit` inspects explicit directory roots, the process `PATH`, or one
  command name for missing, relative, non-directory, writable, ownership, and
  executable-shadowing conditions. The evidence is `src/pathaudit.c`,
  `tests/test_pathaudit.py`, and `man/pathaudit.1`, with architecture decisions
  in `architecture.md`. It is an implemented preview, not an installed or
  released utility.
- `permguard` performs one `lstat` per explicit operand and reports the named
  object's group/other-write and set-ID mode bits without following a final
  symlink. The live evidence is `src/permguard.c`,
  `tests/test_permguard.py`, `man/permguard.1`, and
  `docs/permguard-bootstrap-contract.md`. It too is an implemented preview,
  not an installed or released utility.

The source, test, and manual inventories contain no fourth, fifth, or sixth
binary. `plans/fourth-utility-mission-evaluation.md` reserves explicit-path
`(st_dev, st_ino)` alias grouping for planning-only `inodealias`.
`project-plan.md` and `plans/fifth-utility-mission-evaluation.md` reserve
explicit-script, direct-interpreter validation for planning-only
`shebangcheck`. A sixth mission must therefore remain distinct from both
planned capabilities as well as all three implemented programs.

The fifth-mission evaluation already considered three candidates reused here:
`openunlink` as Candidate B, `mountstack` as Candidate C, and `cgroupceil` as
Candidate E. It selected `shebangcheck` instead and specifically priced
`openunlink` down because procfs descriptor enumeration is point-in-time,
permission-sensitive, and racy. Reconsideration is legitimate because that
evaluation reserved only its selected mission, but the prior rejection remains
evidence. This evaluation answers it by reducing `openunlink` to one explicit
PID, separating numeric enumeration from ordered inspection, treating ordinary
descriptor churn as a visible non-fatal skip instead of a whole-scan failure,
mapping access versus absence only from observed `errno`, and prohibiting
all-PID discovery or reclaimable-space claims. Those controls bound rather than
erase procfs risk; the risk and maintainability scores remain lower than the
simpler candidates. The two scorecards use different criteria and denominators,
so their totals are not directly comparable.

Executable portfolio evidence is successful. The current
`artifacts/user-smoke/result.json` records `app_started: true`,
`core_flow_completed: true`, start and check exit codes of `0`, and an empty
`blocking_errors` array. Its `artifacts/user-smoke/check.log` shows that the
smoke check ran `make test`, the sysdiff fixture acceptance path passed, and
the aggregate pytest result was **351 passed, 18 skipped**. The named steps in
`tests/smoke_manifest.json` remain sysdiff-centered, so this is direct sysdiff
smoke and aggregate regression evidence for the three-source portfolio, not a
dedicated pathaudit or permguard user-flow claim. Readiness for another
*planning* mission follows from the three complete source/test/manual triplets,
the current successful aggregate run, and the reviewed governance records; it
does not imply readiness to implement, that previews are released, or that any
open finding is closed.

The completion records retain Medium debt by identifier. `result-review.md`
and `sprint-plan.md` keep pathaudit `PA-6CA-4` and bootstrap `PA-M1`/`PA-M2`
visible; `code-reviews/review-fourth-utility-mission.verdict.json` retains
`FUM-M1`; `result-review.md` retains fifth-selection `FUM5-M1`/`FUM5-M2`; and
`code-reviews/review-fifth-utility-mission.verdict.json` retains
`FUM5R2-M1` through `FUM5R2-M6`. The sysdiff completion records also retain
qualified, non-globally-unique packaging identifiers: source-archive `F1`–`F5`
for runs `939ee21b0d76` and `240bfcbc634e`, reproducible-source-release
`F-001`–`F-003` for run `b54d61531266`, and install/uninstall `F1` for run
`a2d750c92da3`, as enumerated in `result-review.md` and `sprint-plan.md`.
Later recovery closed specified permguard Mediums but did not close these
unrelated sets.

Consequently this document authorizes selection only. Implementation of the
committed sixth mission remains blocked by the repair-before-expansion policy
stated in `project-plan.md`, `sprint-plan.md`, `STATUS.md`, and
`WHERE_AM_I.md`: the applicable Medium-or-higher debt must be repaired or
explicitly reclassified and independently reviewed before a feature playbook
may launch. A future playbook must re-read those live records rather than use
this successful planning decision as an override.

The active sibling run
`../linux-utilities-agent-orch-runs/787b9bb3d830/run.json` is `RUNNING` at
`step_02_discover_and_evaluate_missions`, and its dashboard identifies this
evaluation as the current governed work. Accordingly, this document is the
only output of the slice. Existing dirty worktree changes are preserved, and
no implementation or smoke asset is treated as writable mission material.

## Candidate Missions

Every candidate below is a one-shot local command, not a platform, framework,
daemon, watcher, cloud integration, telemetry collector, or network client.
None needs network access. All exclude snapshot comparison, PATH trust,
mode-bit policy, inode-alias grouping, and shebang validation.

1. **`openunlink` — explicit-process zero-link regular-file descriptor
   reporting.** Given one decimal Linux PID, enumerate only that process's
   `/proc/PID/fd` entries and report descriptors whose followed target is a
   regular file with `st_nlink == 0`. This answers a recurring storage and
   process-lifetime diagnostic question without trusting the cosmetic
   ` (deleted)` link-text suffix. The smallest slice needs libc, C17, procfs
   directory/metadata interfaces, bounded `readlinkat`, and a coordinated
   same-UID fixture process. It does not scan all PIDs, estimate reclaimable
   blocks, inspect mappings, group inodes, signal a process, close descriptors,
   or open file content. Unlike the fifth-round sketch, descriptor churn is a
   status-1 `FD_UNSTABLE` advisory that preserves stable findings, and observed
   procfs denial is never claimed distinguishable from absence when `hidepid`
   returns `ENOENT`.
2. **`sparsemap` — explicit-file data/hole extent reporting.** Given explicit
   regular files, walk bounded `SEEK_DATA`/`SEEK_HOLE` transitions and print
   their observed extents in offset order. This helps explain logical size
   versus data placement without reading content. It is distinct from
   `inodealias` because it never groups identities, and from `permguard`
   because it makes no permission judgment. The first slice excludes
   allocation/reclaim estimates, compression, reflink sharing, FIEMAP,
   filesystem traversal, and mutation. Filesystem support variability is a
   material boundary.
3. **`futuremtime` — explicit-path future modification-time detection.** Take
   one realtime sample, inspect explicitly named objects with `lstat`, and
   report mtimes later than that sample plus a fixed, user-supplied slack.
   This targets clock-skew symptoms in builds, caches, synchronization, and
   backups. It requires only time and metadata interfaces and deterministic
   far-future fixtures. It excludes recursion, timestamp repair, time-zone
   parsing, network time checks, birth/change/access-time policy, and any claim
   that a future timestamp proves clock misconfiguration.
4. **`execbudget` — prospective `execve` argument/environment budget
   measurement.** Measure the byte and pointer cost of explicit prospective
   arguments plus the current environment against Linux's observed execution
   limits, reporting measured totals and conservative headroom. It addresses
   `E2BIG` diagnosis without executing a command or printing environment
   contents. The slice excludes shell parsing, command lookup, execution,
   environment mutation, response-file generation, and a guarantee that a
   later `execve` succeeds. Linux stack-limit and per-string rules make an
   honest contract harder than the arithmetic first appears.
5. **`mountstack` — stacked mount-target detection from explicit
   mountinfo.** Parse one caller-supplied Linux `mountinfo` snapshot and report
   decoded mount-point fields occurring more than once. It can reveal
   overmounts while remaining deterministic and namespace-passive. It does not
   enter namespaces, read live procfs implicitly, compare snapshots, infer
   intent, parse fstab, or unmount anything. The maintained mountinfo grammar,
   octal escaping, optional fields, and bounded numeric parsing are its main
   costs.
6. **`cgroupceil` — local cgroup-v2 configured-limit summary.** Read a closed
   set of limit files from one explicit cgroup-v2 directory and normalize only
   finite decimal values versus `max`. It can clarify local CPU, memory, and
   process ceilings without contacting systemd or a container runtime. The
   slice excludes ancestor traversal, effective-limit claims, v1 controllers,
   utilization/pressure metrics, monitoring, mutation, and orchestration
   integration. Its usefulness is deliberately limited to local configured
   values.

These six candidates are distinct from one another: process descriptor
lifetime, sparse extents, wall-clock metadata, execution-size accounting,
mount topology records, and cgroup control values are separate inputs and
operator outcomes. No candidate is disguised quality polish, packaging,
release work, or repair of an existing utility.

## Evaluation Criteria

The shared scale is **1 (poor), 2 (weak), 3 (acceptable with material
limits), 4 (strong), and 5 (excellent)**. Every column is favorable at the
high end. Thus a technical-risk score of 5 means low and easily bounded risk,
while a dependency-burden score of 5 means libc and already justified system
interfaces are sufficient. Scores apply only to the stated first slices, not
to imagined feature-rich successors.

Every candidate is evaluated on the same ten criteria:

1. **Practical usefulness:** whether the command answers a concrete recurring
   Linux operator or developer question with an honest success boundary.
2. **Unix simplicity:** whether explicit inputs, deterministic text output,
   finite execution, and composition through exit status preserve one-job
   command-line behavior.
3. **Novelty:** whether the capability is distinct from implemented `sysdiff`,
   `pathaudit`, and `permguard`, and from planned `inodealias` and
   `shebangcheck`.
4. **Maintainability:** size and stability of the owned grammar, taxonomy,
   fixtures, platform contract, and future compatibility surface.
5. **Technical risk:** hostile-input exposure, races, integer/resource
   hazards, OS variability, and the difficulty of rejecting uncertainty
   truthfully.
6. **Educational value:** whether a small implementation teaches useful C,
   Unix, Linux, file, process, or resource concepts without requiring a
   framework.
7. **Likely impact:** how consequential the diagnosed failure is and how much
   manual or error-prone investigation the tool can replace. This is reasoned
   portfolio judgment; no external adoption or frequency study is claimed.
8. **Dependency burden:** runtime, build, privilege, service, fixture, and CI
   costs. Existing C toolchains and pytest may drive validation but are not
   runtime dependencies.
9. **Auditability:** whether inputs, ownership, bounds, system calls, output,
   and failure reduction can be reviewed end to end in one small source.
10. **Suitability for a small ISO C implementation:** whether ISO C17 plus
    narrow, explicitly documented Linux/POSIX interfaces can deliver the whole
    first user outcome without a library ecosystem or multi-component design.

Selection is not a mechanical sum. A candidate is rejected regardless of
total if its useful boundary requires a daemon, network or cloud dependency,
telemetry, a general-purpose platform/framework, privilege escalation,
unbounded discovery, or a first slice whose central claim cannot be made
truthfully. Bounded Linux-specific interfaces are permitted because this is a
Linux utility suite, but their portability and environmental failure modes
must be explicit.

## Comparative Scorecard

| Criterion | `openunlink` | `sparsemap` | `futuremtime` | `execbudget` | `mountstack` | `cgroupceil` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Practical usefulness | 5 | 4 | 4 | 4 | 4 | 4 |
| Unix simplicity | 4 | 4 | 5 | 5 | 4 | 4 |
| Novelty | 5 | 5 | 5 | 5 | 5 | 5 |
| Maintainability | 3 | 4 | 5 | 3 | 3 | 4 |
| Technical risk (higher is safer) | 3 | 3 | 4 | 2 | 3 | 3 |
| Educational value | 5 | 5 | 3 | 5 | 4 | 4 |
| Likely impact | 5 | 4 | 3 | 4 | 4 | 4 |
| Dependency burden (higher is lighter) | 5 | 5 | 5 | 5 | 5 | 5 |
| Auditability | 4 | 4 | 5 | 3 | 3 | 4 |
| Small ISO C suitability | 4 | 4 | 5 | 4 | 3 | 4 |
| **Total / 50** | **43** | **42** | **44** | **40** | **38** | **41** |

`futuremtime` has the highest raw total because its implementation and fixtures
are exceptionally small. It is not selected: its diagnosis is readily
reconstructed from existing metadata tools, a future mtime has many benign
causes, and the narrow non-recursive slice replaces less difficult manual work.
Its lower likely-impact score is therefore selection-significant rather than
an arbitrary tie-break.

`openunlink` is selected on judgment despite ranking one point below. Link
count is a stronger predicate than parsing a display suffix, and correlating it
with a particular process descriptor replaces a more specialized, race-prone
manual investigation. The exact predicate remains small enough to audit when
the slice accepts one PID, sorts numeric descriptors, caps enumeration and
link text, and makes every procfs race or access failure explicit. Its lower
maintainability and risk scores honestly price procfs, process churn, and
permissions.

`sparsemap` is a close alternative, but `SEEK_DATA`/`SEEK_HOLE` support and
semantics vary by filesystem; the output cannot safely imply physical
allocation, sharing, compression, or reclaim. `cgroupceil` has useful ordinary
file fixtures, yet local values can be mistaken for effective inherited
limits, and fixing that gap would add hierarchy/controller policy.
`execbudget` is educational and dependency-light, but Linux `execve` limits
combine total bytes, pointer overhead, per-string ceilings, architecture, and
the current stack limit; a headroom number risks becoming a false guarantee.
`mountstack` owns the widest evolving record grammar, and duplicate decoded
targets are evidence of stacking rather than proof of error.

All six pass the novelty and dependency screens, and none requires a platform
product, framework, daemon, cloud service, telemetry, or network. The rejected
candidates remain uncommitted ideas, not roadmap promises.

## Committed Selection

The one committed mission title is **Bootstrap `openunlink` explicit-process
zero-link regular-file descriptor reporting**.

**One-purpose problem statement:** for one explicitly supplied Linux PID,
report each open file descriptor whose followed target is a regular file with
`st_nlink == 0`, using the metadata predicate rather than trusting procfs link
display text.

**Intended user:** a Linux administrator, reliability engineer, developer, or
consultant diagnosing file lifetime and apparent non-reclamation in a process
they are already permitted to inspect.

**Rationale:** this outcome is more consequential and less easily reproduced
correctly than the slightly smaller alternatives, while still fitting one C17
translation unit, one explicit input, one finding code, bounded procfs
enumeration, deterministic numeric ordering, temporary same-UID fixtures, and
the suite's existing quality floor. It is novel relative to every implemented
and planned mission: it does not compare state, assess PATH trust or mode
policy, group identities across caller paths, or parse interpreter headers.
The claim is intentionally metadata-only. It does not promise that the object
consumes disk blocks, quantify reclaimable storage, or say why its link count
became zero. Exactly this candidate is committed; the other five are rejected
for this mission.

## First Vertical Slice

The initial CLI surface is closed:

```text
openunlink --help
openunlink --version
openunlink PID
```

`PID` is one ASCII decimal integer in the inclusive range `1..INT_MAX`, with
no sign, whitespace, suffix, or second operand. Informational options succeed
only as sole arguments. There is no implicit current PID, all-process mode,
proc-root option, environment configuration, or stdin input. `--version`
prints `openunlink 0.1.0\n`; the eventual contract must pin the complete help
and usage bytes before code is accepted.

The sole product input is `/proc/PID/fd` for that explicit PID. The scanner
opens that directory read-only, gives a duplicated descriptor to `fdopendir`,
and retains the original descriptor for later directory-relative inspection.
It completes `readdir` and `closedir` on the duplicate before findings begin,
ignores only `.` and `..`, accepts all other entries only as canonical
ASCII-decimal descriptor names in `0..INT_MAX` (no leading zero unless the
name is exactly `0`), stops before retaining a 65,537th descriptor, and sorts
retained descriptor numbers numerically. A malformed, out-of-range, or
duplicate proc entry, or an enumeration read/close failure, is a whole-scan
error before output. Closing the retained inspection descriptor is checked
after scanning; a failure returns status `2` without retracting output already
streamed.

Before the first descriptor inspection, checked arithmetic allocates the
65,537-byte reusable target buffer and one reusable line buffer sized for the
worst-case four-byte escaping of a 65,536-byte target plus fixed fields.
Descriptor storage is already bounded by enumeration. Allocation therefore
either fails as `MEMORY` before output or remains fixed throughout scanning;
no finding-sized allocation occurs after streaming starts.

Each sorted descriptor is inspected through directory-relative followed-target
metadata, bounded link-text, and repeated metadata calls. A finding requires
the same `(st_dev, st_ino, file type)` on both metadata observations, with
`S_ISREG(st_mode)` and `st_nlink == 0` on the final observation. The link text
is display context only and never decides the finding. If an entry vanishes,
becomes stale, or changes identity/type, the scanner emits `FD_UNSTABLE` on
stderr, continues, and preserves every stable finding. Another per-descriptor
metadata/link failure is `FD_UNREADABLE`; an unrepresentable or negative size
is `FD_SIZE_RANGE`. These are visible incomplete-inspection advisories, not
whole-scan failures or clean results. Undetectable ABA replacement and any
change after the final observation remain outside the point-in-time claim.
The scanner opens no target content and sends no process signal.

Successful output contains zero or more lines in ascending numeric descriptor
order:

```text
OPEN_UNLINKED<TAB>pid=PID<TAB>fd=FD<TAB>size=BYTES<TAB>target="ESCAPED_TARGET"<LF>
```

`BYTES` is the nonnegative `st_size` observed for the stable target; a negative
or unrepresentable value produces `FD_SIZE_RANGE` and skips that descriptor.
In the quoted target, printable ASCII `0x20..0x7e` is literal except `"` and
`\`, which render as `\"` and `\\`; all other bytes render as uppercase
`\xNN`. Link text may include ` (deleted)`, but that suffix has no semantic
authority. The maximum accepted link text is 65,536 bytes, deliberately above
Linux `PATH_MAX` plus the procfs deletion suffix. `readlinkat` receives a
65,537-byte buffer: a return of 65,537 means exact-fit versus truncation cannot
be distinguished and therefore produces `TARGET_LENGTH_LIMIT`; a result at or
below 65,536 is accepted and explicitly NUL-terminated by the program.

After the descriptor list is complete, findings and advisories stream in
numeric descriptor order. A later `FD_UNSTABLE`, `FD_UNREADABLE`,
`FD_SIZE_RANGE`, or `TARGET_LENGTH_LIMIT` never retracts earlier
`OPEN_UNLINKED` lines. A whole-scan status-2 failure that occurs before
descriptor inspection leaves stdout empty; `STDOUT_WRITE` during emission may
leave an arbitrary byte prefix, including a partial final line. A final
inspection-directory close failure may leave complete prior findings and
advisories and still returns status `2`. Each stream preserves the numeric
subsequence routed to it, but no total ordering is promised after a caller
merges independently buffered stdout and stderr.

The exit statuses are exactly `0` for successful help/version or a completed
stable scan with no finding or advisory; `1` for a completed scan with at least
one `OPEN_UNLINKED` finding or per-descriptor advisory; and `2` for a global
usage, process-directory, descriptor-count, allocation, or output failure.
Status `2` has numeric precedence but does not erase stdout already streamed.
The program ignores `SIGPIPE`; closed stdout therefore reaches the checked
status-2 path. Finding lines use stdout. Advisories use the exact stderr shape
`openunlink: CODE: pid=PID fd=FD\n`; PID-owned operational diagnostics use
`openunlink: CODE: pid=PID\n`; global diagnostics use
`openunlink: CODE\n`.

The closed hazard/result taxonomy has one finding code, `OPEN_UNLINKED`; four
status-1 advisory codes; and seven operational codes. Implementations may not
invent another result without revising the contract:

- `FD_UNSTABLE` — a descriptor vanishes, becomes stale, or changes followed
  target identity/type during its bounded inspection.
- `FD_UNREADABLE` — a retained descriptor cannot be inspected for another
  per-descriptor metadata or link-text reason; it is not silently clean.
- `FD_SIZE_RANGE` — the stable zero-link regular target's observed `st_size`
  is negative or cannot be represented losslessly for output.
- `TARGET_LENGTH_LIMIT` — `readlinkat` fills the 65,537-byte sentinel buffer,
  so link text cannot be represented within the 65,536-byte display ceiling.

- `USAGE` — bad arity, option, or PID grammar/range.
- `FD_COUNT_LIMIT` — a 65,537th decimal descriptor entry is observed.
- `PROCESS_NOT_FOUND` — opening `/proc/PID/fd` reports `ENOENT` or `ENOTDIR`;
  this may mean the PID exited, is invisible under `hidepid`, or procfs is
  absent, and the utility does not claim to distinguish those causes.
- `PROCESS_ACCESS` — opening `/proc/PID/fd` reports `EACCES` or `EPERM`.
- `PROCESS_SCAN` — opening, reading, closing, or validating the descriptor
  directory fails for another observed reason or exposes an unexpected entry
  grammar.
- `MEMORY` — checked allocation fails.
- `STDOUT_WRITE` — stdout write or final flush fails.

The test strategy must combine unit, fixture, integration, regression, and
quality layers. Unit checks pin PID parsing, decimal descriptor ordering,
checked limit arithmetic, every escaped byte, exact line construction, and
exit reduction, including status `1` for advisory-only completion. A
handshake-driven same-UID helper process opens controlled temporary objects and
keeps them alive while the product runs; it must include a still-linked regular
file, a regular file unlinked after open, two duplicated descriptors for the
same unlinked object, and non-regular descriptors. A compile-time test seam in
the single translation unit must deterministically inject opening `errno`,
directory errors, disappearing/reused descriptors, allocation failures,
65,536/65,537-byte target boundaries, size-range failures, and output loss
rather than relying on timing accidents. The production build excludes the
seam. No test requires root, `chown`, mount reconfiguration, a container
runtime, network, `strace`, `nm`, `objdump`, or another installed diagnostic
utility; a source-level prohibited-call audit and the injected-call seam use
only the existing compiler and pytest floor.

A new section-1 page `man/openunlink.1` is mandatory in the implementation
slice. It must state the exact synopsis, output grammar, escaping, closed
taxonomies, limits, statuses, Linux procfs and same-UID/`hidepid` boundary,
point-in-time race limitation, privacy of displayed link targets, and all
non-goals. It must distinguish link count from physical allocation and
reclaimable bytes; state that `ENOENT` cannot distinguish an exited PID from a
PID hidden by `hidepid`; explain that advisories make status `1` an incomplete
result without suppressing stable findings; include one controlled example;
pass warning-gated groff lint; and avoid any installation or release claim not
separately authorized.

Explicit acceptance checks for the vertical slice are:

- exact help/version/usage bytes; PID `0`, signs, whitespace, overflow,
  missing PID, extra operands, and combined informational options reject as
  `USAGE`;
- a process with only linked ordinary fixtures produces empty stdout/stderr
  and status `0`;
- one unlinked open regular file produces exactly one escaped, byte-for-byte
  `OPEN_UNLINKED` line and status `1`, while a linked filename literally ending
  in ` (deleted)` does not produce a finding;
- duplicated descriptors for the same object produce separate ascending-FD
  lines rather than inode grouping; multiple objects remain numerically sorted;
- deleted directories, pipes, sockets, devices, and other non-regular targets
  are silent, and no target content is opened, read, executed, or modified;
- a deterministically closed or reused unrelated descriptor produces exact
  `FD_UNSTABLE` stderr and status `1` while stable `OPEN_UNLINKED` stdout
  remains present; advisory-only `FD_UNSTABLE`, `FD_UNREADABLE`,
  `FD_SIZE_RANGE`, and `TARGET_LENGTH_LIMIT` cases never return a false-clean
  `0`;
- an actual missing PID maps observed `ENOENT` to `PROCESS_NOT_FOUND`;
  test-seam `ENOENT`/`ENOTDIR`, `EACCES`/`EPERM`, and other errors pin the
  truthful `PROCESS_NOT_FOUND`, `PROCESS_ACCESS`, and `PROCESS_SCAN` mapping
  without requiring root or a `hidepid` mount;
- malformed/unexpected proc entries, directory read/close failure, a 65,537th
  descriptor, and allocation failure produce their distinct status-2 codes
  before descriptor output; no generic `RESOURCE_LIMIT` diagnostic exists;
- an injected final close failure produces `PROCESS_SCAN` and status `2` while
  preserving any stable findings already emitted;
- test-seam link text of exactly 65,536 bytes is accepted using a 65,537-byte
  buffer, while a 65,537-byte return produces `TARGET_LENGTH_LIMIT`; legitimate
  near-`PATH_MAX` text plus ` (deleted)` remains below the accepted ceiling;
- spaces, quotes, backslashes, tabs, newlines, control bytes, DEL, and
  non-UTF-8 target bytes are terminal-safe and repeat-run deterministic;
- closed stdout and final-flush failure produce `STDOUT_WRITE`, status `2`,
  and no signal-derived shell status;
- before/after fixture metadata and contents are unchanged, the helper
  receives no signal, the runtime marker proves target content is not read,
  and a source-level audit of the sole translation unit confirms that its only
  product open is the fixed process descriptor directory and finds no target
  open/read, network, fork/exec, unlink, chmod/chown, or signal call site;
- strict GCC and Clang C17 builds with
  `-Wall -Wextra -Wpedantic -Werror`, clang-format, clang-tidy, cppcheck,
  Clang static analyzer, ASan, UBSan, Valgrind, focused tests, and the aggregate
  suite all pass with honest capability skips only;
- dedicated user smoke builds a temporary binary, coordinates one linked and
  one unlinked fixture, validates exact status/output, and records a successful
  `openunlink` flow. The existing sysdiff smoke may count only as aggregate
  regression evidence;
- independent review confirms the CLI, one-code finding plus closed advisory
  and operational taxonomies, procfs race handling, ownership/cleanup,
  no-content/no-control posture, exact bounds, documentation, and no unresolved
  Medium-or-higher mission finding.

That is a release-sized bootstrap: normative contract, one source, focused
tests, manual, additive existing-gate wiring, dedicated smoke, quality
evidence, and independent review. Installation, packaging, tagging, and
publication remain separately authorized work and are not part of this slice.
Even after this planning document passes review, that implementation slice may
not launch until the live repair-before-expansion gate described under
Portfolio Evidence is cleared and recorded by independent review.

## Risks and Non-Goals

**Hostile input risk:** although the user supplies only a decimal PID, procfs
supplies descriptor names and target bytes that can be long, malformed,
non-UTF-8, or terminal-hostile. Decimal parsing must avoid locale and signed
character traps; all sizes and sums use checked arithmetic; descriptor count
and the current target have the fixed ceilings above; and every displayed byte
is escaped. Target text is not retained across descriptors, so there is no
invented aggregate-target limit or unbounded finding buffer. No procfs string
is passed to a shell, format string, allocator size calculation, or path join
without validation.

**Path and race risk:** `/proc/PID/fd/N` entries are Linux magic symlinks whose
targets can disappear or be reused while scanned. The utility uses an opened
directory, directory-relative calls, numeric names, and a before/after
identity/type comparison, then reports only a point-in-time observation.
Detected churn is the status-1 advisory `FD_UNSTABLE`, which preserves stable
findings and prevents a false-clean status; undetectable ABA replacement and
change after the final check are disclaimed. Link display text is advisory,
not a path to open and not evidence of deletion. The program never
canonicalizes, traverses, or mutates the displayed target.

**Environment and permission risk:** procfs may be absent, mounted elsewhere,
restricted by `hidepid`, filtered by a container or namespace, or deny a PID
under ordinary credential rules. The first slice intentionally uses fixed
`/proc`, reads no `PATH`, locale, configuration, or cloud/container metadata,
and acquires no privilege. Absence and denial are explicit status-2 outcomes,
not empty-success scans, but the code names only the observed kernel error:
`ENOENT`/`ENOTDIR` is `PROCESS_NOT_FOUND`, even when `hidepid` caused
invisibility, while only `EACCES`/`EPERM` is `PROCESS_ACCESS`. Results describe
the PID visible in the caller's current PID and mount namespaces only.

**Portability risk:** the utility is Linux/procfs-specific even though its core
is ISO C17. POSIX/Linux declarations must come from headers under explicit
feature-test macros, `_FILE_OFFSET_BITS=64` is required where `off_t` is used,
and numeric formatting must use the correct `<inttypes.h>` types. Other Unix
systems, non-procfs layouts, and cross-namespace promises are out of scope;
unsupported hosts fail explicitly rather than silently passing.

**Ownership and undefined-behavior risk:** the later contract must assign one
owner to the opened directory/`DIR *`, descriptor-number array, target buffers,
and current escaped-line storage, with one cleanup path and no double close
after `fdopendir`; the retained inspection descriptor and the duplicate owned
by `DIR *` are distinct. `readdir` storage is borrowed only until the next
call; only the validated numeric descriptor value is retained. All conversions,
comparisons, allocation products/sums, `errno` captures, sort comparators, byte
classification, repeated-stat comparisons, and stdio completion paths need
regression coverage. No unchecked narrowing from `pid_t`, `off_t`, `ino_t`,
`dev_t`, `nlink_t`, or `size_t` is acceptable.

**Scope-creep risk and explicit non-goals:** the slice will not scan every PID,
walk `/proc/PID/map_files` or `maps`, resolve process names/users/cgroups,
aggregate objects by inode, estimate physical or reclaimable disk blocks,
distinguish memfd/tmpfs/reflink/compressed storage policy, inspect mount
ownership, close another process's descriptor, send signals, kill/restart a
process, remediate files, monitor continuously, persist history, compare two
scans, emit JSON, add plugins, run a daemon, use telemetry, call cloud or
container APIs, or access the network. It will not implement or alter
`inodealias`, `shebangcheck`, `sysdiff`, `pathaudit`, or `permguard`; close
their findings; change manifests or smoke assets in this evaluation; or make
an install, package, tag, publication, or release claim. Selection also does
not waive the Medium-or-higher repair gate or authorize an implementation
playbook to start before that gate is cleared.
