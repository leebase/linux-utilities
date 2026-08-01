# Seventh Utility Mission Evaluation

This document applies the closed criteria in
`plans/seventh-utility-mission-contract.md`. It is selection evidence, not a
behavioral contract: candidate names are working labels, and this evaluation
does not establish a command line, output schema, exit-status taxonomy,
resource constant, source layout, or test implementation. Product CLI Surface
and Exit Statuses remain deferred to a later normative implementation contract
if one is ever authorized. The live recovery contract is authoritative for this
reconciliation. `plans/seventh-utility-mission-frame.md` is a superseded
historical artifact and now says so conspicuously; its hazard taxonomy and
acceptance checks are non-authority.

Governed origin run `f7539c314ca1`
(`discover_evaluate_seventh_linux_utility`) remains **FAILED**. This file
salvages the completed post-repair evaluation left as unreviewed working-tree
residue by that run's timed-out repair loop (step-2 attempts 2 and 3 exited
124 under a 600-second worker ceiling). Salvage does not claim that the origin
run passed, does not treat either timeout as a silent pass, and does not
authorize seventh-utility implementation, build, test, smoke, packaging, or
release. Independent review attempt 2 recorded High `SEV7-H1` against the
pre-repair `elfinterp` winner; the on-disk residue below instead commits to
capability-level `sparsemap`, with honest deferral retained as a valid
alternative if fresh review rejects the field.

## Candidate Missions

The repository inventory is capability-based rather than executable-name-based.
`sysdiff` is the released v0.1.0 snapshot-comparison utility. `pathaudit` and
`permguard` are implemented preview utilities but remain uninstalled and
unpackaged. `inodealias`, `shebangcheck`, and `openunlink` are planning-only
reservations with no product artifacts: respectively, explicit-path
device/inode alias grouping, direct shebang-interpreter preflight, and
explicit-process zero-link regular-file descriptor reporting. The requested
tests confirm the implemented boundaries: `tests/test_sysdiff.py` exercises
explicit snapshot comparison, `tests/test_pathaudit.py` exercises PATH/root/
command trust and shadowing, and `tests/test_permguard.py` exercises one-object
mode-bit inspection through `lstat` semantics. None supplies a general
logical-extent, lock-table, mount-stack, or cgroup-limit operation.

The following are four credible and capability-distinct candidates. A fifth
working label is retained because the prior attempt selected it, but the
re-entry analysis rejects it as a duplicate before eligibility. Honest
deferral is also carried as the required baseline.

1. **`sparsemap` — filesystem-reported logical data/hole ranges for explicit
   regular files.** The user problem is checking whether a large artifact,
   image, database, or copy is still represented sparsely and locating the
   reported logical regions without reading its contents. Its bounded purpose
   is to walk the operating system's `SEEK_DATA`/`SEEK_HOLE` observations for
   caller-named regular files and emit ordered, terminal-safe range facts. It
   would not claim physical allocation, reclaimable space, compression,
   sharing, or copy correctness; it would not use FIEMAP, recurse, compare
   files, or mutate them.
2. **`lockscope` — advisory-lock observations for explicit file identities.**
   This would map caller-named regular files to device/inode identities and
   filter a bounded `/proc/locks` observation to report matching lock type,
   mode, owner token, and range. It answers “what locks does this Linux procfs
   instance currently report for these files?” It does not promise a durable
   lock state, resolve arbitrary table records back to paths, control
   processes, wait for locks, or duplicate `inodealias` grouping.
3. **`mountstack` — repeated mount-target observations from one mountinfo
   source.** This would parse a bounded mountinfo snapshot and identify decoded
   mount-point fields that occur more than once, helping explain a tree hidden
   by a stacked mount. It would not enter namespaces, mount or unmount
   anything, infer administrator intent, parse fstab, compare snapshots, or
   become a mount-topology engine.
4. **`cgroupceil` — local cgroup-v2 configured-limit summary.** This would read
   a closed set of ordinary limit files beneath one explicit cgroup-v2
   directory and normalize finite values versus the kernel's unlimited token.
   It answers what that directory locally configures, not the effective
   ancestor-constrained limit. It excludes ancestor traversal, v1 controllers,
   usage and pressure monitoring, systemd/container-runtime integration, and
   all mutation.
5. **`elfinterp` — ELF interpreter-path preflight, rejected as a duplicate.**
   The proposed operation accepts caller-named regular files, extracts a
   content-declared absolute interpreter path, then reports point-in-time
   metadata/access observations without executing it. That is the same
   capability-level operation already reserved by the normative
   `shebangcheck` contract; changing the declaration format from a shebang
   header to an ELF program header changes parser mechanics, not the user-facing
   operation. It is scored for auditability but is ineligible.
6. **Honest deferral.** Select no seventh utility if every genuine candidate
   misses 126/168, scores below 3 on any mandatory criterion, crosses the
   discovery boundary, or cannot defeat the alternatives under the contract's
   tie-breaks. Deferral is not a utility and therefore receives no numerical
   score.

The duplicate/polish screen also excludes a second snapshot differ, PATH or
ownership checker, mode-bit checker/fixer, hard-link identity finder, shebang
or loader-path checker, and deleted-open-file finder. Fuzzing, analyzer work,
benchmarking, coverage, packaging, release work, documentation repair, fixture
expansion, and smoke broadening are quality dimensions for owned utilities,
not seventh capabilities.

This is not presented as a high-yield fresh survey. `mountstack`, `lockscope`,
and `cgroupceil` were evaluated and rejected in the fifth-mission work
(`41/55`, `35/55`, and `43/55` respectively), while `sparsemap`,
`mountstack`, and `cgroupceil` appeared in the sixth-mission work (`42/50`,
`38/50`, and `41/50`). Those totals used different criteria and scales and are
not comparable with the closed 168-point matrix below. `elfinterp` was the only
new finalist in the failed first attempt; the stricter capability comparison
removes it. Reconsidering the remaining unreserved candidates is legitimate,
but their prior rejection and the field's low novelty yield remain decision
evidence.

## Evaluation Matrix

Each raw score is an integer from 0 to 4 and is multiplied by the contract
weight. A candidate qualifies only at 126/168 or better, with at least 3 in
Practical usefulness, Novel capability, One-purpose smallest useful slice,
and Security and privilege posture, and with no discovery-boundary violation.
The source observations were made on 2026-07-30. Repository sources were read
directly from the working tree. External interface facts were read through the
linked Linux man-pages or Linux kernel documentation web pages:

- [`lseek(2)`](https://www.man7.org/linux/man-pages/man2/lseek.2.html)
  documents `SEEK_DATA`/`SEEK_HOLE`, their backup use, error cases, feature-test
  requirement, filesystem support history, and the permission for a filesystem
  to report every region as data.
- [`proc_locks(5)`](https://www.man7.org/linux/man-pages/man5/proc_locks.5.html)
  documents the current lock/lease table, record fields, device/inode key,
  OFD-lock owner value, and PID-namespace filtering.
- [`proc_pid_mountinfo(5)`](https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html)
  documents mount-namespace scope, stacked mounts, the variable optional field
  region, and the requirement to ignore unknown optional fields.
- [Linux cgroup-v2 documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html)
  documents controller availability, hierarchical limits, local interface
  files such as `cpu.max`, `memory.max`, and `pids.max`, and the `max` token.

| Closed criterion (weight) | `sparsemap` | `lockscope` | `mountstack` | `cgroupceil` | `elfinterp` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Practical usefulness (5) | 3 (15) | 3 (15) | 3 (15) | 3 (15) | 4 (20) |
| Novel capability (5) | 4 (20) | 3 (15) | 4 (20) | 4 (20) | 0 (0) |
| One-purpose smallest useful slice (5) | 3 (15) | 3 (15) | 3 (15) | 3 (15) | 3 (15) |
| Security and privilege posture (5) | 4 (20) | 3 (15) | 4 (20) | 4 (20) | 3 (15) |
| Unix fit and composability (4) | 4 (16) | 4 (16) | 3 (12) | 3 (12) | 4 (16) |
| Deterministic testability (4) | 2 (8) | 3 (12) | 3 (12) | 3 (12) | 4 (16) |
| C auditability and ownership (4) | 4 (16) | 3 (12) | 2 (8) | 3 (12) | 3 (12) |
| Dependency economy (4) | 4 (16) | 4 (16) | 4 (16) | 4 (16) | 4 (16) |
| Portability honesty (3) | 2 (6) | 2 (6) | 2 (6) | 2 (6) | 3 (9) |
| Maintenance burden (3) | 3 (9) | 2 (6) | 2 (6) | 2 (6) | 3 (9) |
| **Total / 168** | **141** | **128** | **130** | **134** | **128** |
| **Hard gates** | **pass** | **pass** | **pass** | **pass** | **fail: novelty 0** |

The arithmetic is
`15+20+15+20+16+8+16+16+6+9 = 141` for `sparsemap`,
`15+15+15+15+16+12+12+16+6+6 = 128` for `lockscope`,
`15+20+15+20+12+12+8+16+6+6 = 130` for `mountstack`,
`15+20+15+20+12+12+12+16+6+6 = 134` for `cgroupceil`, and
`20+0+15+15+16+16+12+16+9+9 = 128` for `elfinterp`.

The following ledger records an observed fact and bounded inference for every
raw score.

**`sparsemap` score evidence**

- **Practical usefulness 3:** `lseek(2)` explicitly identifies hole discovery
  as useful to backup tools, but also says filesystems may report all regions
  as data. The operation supports a real preservation/investigation decision,
  with a material fidelity qualification rather than an allocation promise.
- **Novel capability 4:** the repository inventory and requested tests contain
  snapshot, PATH trust, mode, identity, interpreter, and descriptor-lifetime
  operations, but no logical layout report. The user-visible operation remains
  distinct even if all three planned utilities ship.
- **One-purpose smallest useful slice 3:** two seek modes and a logical EOF are
  sufficient to describe one finite observation, but unsupported interfaces,
  nonprogress, end-hole behavior, overflow, file mutation, and extent ceilings
  are irreducible first-slice states.
- **Security and privilege posture 4:** caller-selected regular files can be
  opened read-only and queried with non-mutating seeks; no content execution,
  traversal, target write, process control, or privilege is needed. Hostile
  names, symlinks, type races, sizes, and offsets have direct bounded checks.
- **Unix fit and composability 4:** explicit operands yield finite ordered
  facts suitable for selection or downstream copy diagnostics, with no daemon,
  network, hidden discovery, or remediation.
- **Deterministic testability 2:** a syscall seam can pin every transition and
  error on an ordinary unprivileged host, but `lseek(2)` permits a conforming
  live filesystem to collapse the essential sparse distinction to all-data.
  Host extent fixtures therefore cannot be the only core oracle.
- **C auditability and ownership 4:** a checked offset state machine over one
  descriptor needs modest scalar state and little allocation or text parsing.
  Its required ceilings and descriptor lifetime are straightforward to audit.
- **Dependency economy 4:** `lseek(2)` is a libc interface; the candidate needs
  no filesystem library, external allocation command, subprocess, service,
  database, plugin, or network.
- **Portability honesty 2:** current POSIX includes the seek modes, but Linux
  feature macros, `off_t` width, kernel/filesystem support, and reporting
  fidelity materially shape the result. The utility must make a Linux and
  filesystem-reported claim, not a universal storage claim.
- **Maintenance burden 3:** the state machine is closed, but a permanent
  compatibility disclaimer, unsupported/coarse-result fixtures, overflow
  coverage, and resistance to allocation-analysis feature requests remain
  necessary.

**`lockscope` score evidence**

- **Practical usefulness 3:** `proc_locks(5)` exposes current locks keyed by
  device/inode, which can narrow an immediate “why is this file operation
  blocked?” investigation. The table is point-in-time and an OFD lock has no
  single owning PID, so the answer is useful but qualified.
- **Novel capability 3:** no owned mission reports lock state. Device/inode
  matching is nevertheless adjacent to `inodealias`, while procfs owner and
  descriptor concepts are adjacent to `openunlink`; the final operation is
  distinct but not maximally separated.
- **One-purpose smallest useful slice 3:** explicit-path identity matching plus
  one documented table grammar is bounded, but both halves, record ceilings,
  numeric validation, and churn handling are required for a useful result.
- **Security and privilege posture 3:** the operation is read-only and
  unprivileged, but it consumes a namespace-wide kernel table rather than only
  information about caller-named objects and may expose transient process
  metadata. Scope and access errors need explicit treatment.
- **Unix fit and composability 4:** explicit paths can filter one bounded
  procfs observation into finite factual records without waiting, process
  control, hidden state, or mutation.
- **Deterministic testability 3:** synthetic records provide exact parser
  oracles and ordinary unprivileged child-held locks can provide integration
  evidence. Scheduling, table churn, namespace visibility, and OFD attribution
  prevent a fully exact live oracle.
- **C auditability and ownership 3:** token validation, integer/range parsing,
  path identity matching, record retention, and concurrent disappearance make
  more state than `sparsemap`, though one bounded proc source remains credible
  in small C17.
- **Dependency economy 4:** libc and Linux procfs suffice; no lock-management
  library, external `lslocks`, daemon, database, runtime, or network is needed.
- **Portability honesty 2:** `proc_locks(5)` documents Linux-specific
  PID-namespace filtering and kernel-version-sensitive OFD owner semantics.
  These assumptions can be stated, but they materially qualify the result.
- **Maintenance burden 2:** lock variants, leases, OFD semantics, namespace
  filtering, transient records, and a kernel text grammar create ongoing
  taxonomy and fixture work.

**`mountstack` score evidence**

- **Practical usefulness 3:** `proc_pid_mountinfo(5)` explicitly explains
  stacked mounts hiding an earlier tree. Reporting repeated decoded targets
  can explain a real visibility problem, but it cannot decide whether the
  stacking is erroneous.
- **Novel capability 4:** no implemented or reserved utility observes a mount
  namespace or aggregates mount targets. Its source, object, and answer remain
  separate from path trust, file identity, and descriptor lifetime.
- **One-purpose smallest useful slice 3:** one record source and one exact
  duplicate-target predicate are finite, but decoding, optional fields,
  grouping, sorting, numeric bounds, and malformed-record policy are all
  irreducible.
- **Security and privilege posture 4:** a caller-visible mountinfo source can
  be read without changing mounts, entering namespaces, traversing target
  trees, executing content, or acquiring capabilities. Input and output still
  require firm byte and record bounds.
- **Unix fit and composability 3:** the result is finite and pipeable, but a
  whole-namespace observation is less operand-directed than `sparsemap` or
  `lockscope`, and mount churn makes “same invocation, same environment”
  determinism point-in-time.
- **Deterministic testability 3:** explicit synthetic mountinfo records can pin
  parsing and grouping, but a live stacked-mount positive normally requires
  environmental control or privilege unsuitable for a core portable fixture.
- **C auditability and ownership 2:** the documented grammar has fixed fields,
  a variable optional region, escapes, grouping, and ordering. This is the
  field's widest parser and ownership surface.
- **Dependency economy 4:** libc and a procfs text source suffice; no
  `findmnt`, mount library, namespace helper, database, daemon, or service is
  necessary.
- **Portability honesty 2:** the source is Linux procfs and mount-namespace
  relative, and its parser must tolerate unknown optional fields. Those limits
  are expressible but central.
- **Maintenance burden 2:** forward-compatible optional-field handling,
  escapes, namespace semantics, churn, and pressure to grow into topology or
  policy analysis impose sustained work.

**`cgroupceil` score evidence**

- **Practical usefulness 3:** the kernel documents CPU, memory, and process
  limit files used by ordinary container and service isolation. A local
  configured-value summary answers a recurring question, but hierarchy means
  it cannot claim the effective ceiling.
- **Novel capability 4:** no existing or reserved mission reads cgroup-v2
  controller files or reports resource configuration. It neither compares
  snapshots nor inspects file trust, permissions, identity, interpreters, or
  open descriptors.
- **One-purpose smallest useful slice 3:** a closed local summary is bounded,
  but controller availability, missing files, decimal validation, compound CPU
  values, unlimited tokens, and per-file size ceilings all belong in the first
  useful slice.
- **Security and privilege posture 4:** one explicit directory can be
  inspected read-only with ordinary authority; no cgroup creation, migration,
  limit write, process control, privilege transition, or orchestration call is
  needed. Path/type races and hostile pseudo-file text remain bounded hazards.
- **Unix fit and composability 3:** one-shot normalized facts compose in shell
  workflows, but several controller files form a small fixed bundle and
  availability depends on the host's cgroup-v2 configuration.
- **Deterministic testability 3:** ordinary directory fixtures can exercise
  token parsing and missing/invalid files exactly. A live integration oracle
  depends on mounted cgroup v2 and enabled controllers, so it must remain
  supplemental.
- **C auditability and ownership 3:** bounded reads and numeric parsing are
  modest, but several file grammars, a compound CPU value, availability, and
  path ownership create more state than one extent loop.
- **Dependency economy 4:** libc file operations are sufficient; no systemd,
  container runtime, cgroup library, subprocess, service, database, or network
  is needed.
- **Portability honesty 2:** the operation is Linux cgroup-v2-specific and
  controller/hierarchy dependent. A precise local-only claim is possible, but
  the environmental qualification is material.
- **Maintenance burden 2:** controller evolution and strong pressure for
  ancestor traversal, effective-limit computation, utilization, pressure, and
  orchestration integration make the boundary costly to defend.

**`elfinterp` score evidence**

- **Practical usefulness 4:** the normative `shebangcheck` work already
  establishes that a declared interpreter's point-in-time absence or metadata
  state explains an immediate launch failure. ELF users have the same concrete
  problem.
- **Novel capability 0:** `project-plan.md` reserves exactly the operation
  “caller-named regular file, extract content-declared absolute interpreter
  path, perform nonexecuting metadata/access preflight, emit escaped findings.”
  ELF changes input grammar only, directly contradicting capability novelty.
- **One-purpose smallest useful slice 3:** a program-header subset and one
  pathname preflight are finite, but ELF class, byte order, offset arithmetic,
  duplicate declarations, malformed input, and path races are irreducible.
- **Security and privilege posture 3:** input and checks can be read-only and
  unprivileged, but an untrusted content-derived path expands authority beyond
  caller-named operands and introduces pathname/type/access races. That is a
  bounded tradeoff, not an unqualified 4.
- **Unix fit and composability 4:** explicit operands could yield finite
  factual records with no execution, daemon, network, or mutation.
- **Deterministic testability 4:** byte-built malformed/cross-class ELF inputs
  and temporary interpreter paths can provide exact unprivileged parser and
  nonexecution oracles.
- **C auditability and ownership 3:** the parser can be small, but endian/class
  handling, checked offset math, table bounds, duplicate handling, and
  content-derived path lifetime require careful review.
- **Dependency economy 4:** libc plus platform ELF/system declarations suffice;
  no loader library, subprocess, language runtime, service, or network is
  necessary.
- **Portability honesty 3:** a small C17 parser could state System V ELF and
  Linux execution assumptions precisely, while rejecting unsupported forms.
  Architecture diversity is material but bounded.
- **Maintenance burden 3:** mature fields and byte fixtures are bounded, but
  cross-class malformed inputs and duplicated interpreter-policy taxonomy
  create continuing work. The duplicate portfolio burden reinforces
  ineligibility even though the parser itself is maintainable.

Deferral is removed before arithmetic because it produces no user operation.
It remains the correct outcome if the score or boundary gates fail; here four
capability-distinct candidates clear them. Clearing the arithmetic gates does
not by itself authorize implementation: this evaluation is still unreviewed
residue from failed origin run `f7539c314ca1`, and honest deferral stays open
if a fresh independent review finds a disqualifying conflict or unresolved
uncertainty that outweighs the seven-point `sparsemap`–`cgroupceil` margin.

### Closed hazard ratings (recovery reconciliation)

Ratings use only the recovery contract's permitted phrases. They validate the
frozen field; they do not reopen discovery or rescore totals.

**`sparsemap`:** (1) Duplicate implemented capability — `clear`. (2) Duplicate
reserved mission — `clear` (logical layout is not identity grouping, shebang
preflight, or zero-link descriptor reporting). (3) Duplicate polish/repair —
`clear`. (4) Weak practical value — `bounded with explicit mitigation`
(filesystem may report all-data; claim stays “reported ranges”). (5) Excessive
scope — `bounded with explicit mitigation` (no FIEMAP, recursion, mutation, or
allocation accounting). (6) Hostile-input exposure — `bounded with explicit
mitigation` (operand/type/race, offset, extent, and escaping ceilings).
(7) Privilege/side-effect — `clear` (read-only unprivileged seeks).
(8) Dependency growth — `clear` (libc/`lseek` only). (9) Portability/ABI —
`bounded with explicit mitigation` (Linux-oriented, filesystem-dependent
fidelity; scores Portability honesty 2). (10) Non-deterministic evidence —
`bounded with explicit mitigation` (syscall seam required; host extent
fixtures supplemental; Deterministic testability 2).

**`cgroupceil`:** classes 1–3 and 7–8 `clear`; 4–6, 9–10
`bounded with explicit mitigation` (local-versus-effective hierarchy risk is
the decisive product limit). **`mountstack`:** 1–3, 7–8 `clear`; 4–6, 9–10
`bounded with explicit mitigation` (escaped mountinfo grammar and churn).
**`lockscope`:** 1–3, 7–8 `clear` with adjacency noted; 2
`bounded with explicit mitigation` (device/inode adjacency to `inodealias`,
procfs adjacency to `openunlink`); 4–6, 9–10 `bounded with explicit
mitigation`. **`elfinterp`:** class 2 **`disqualifying`** at capability level
versus the normative `shebangcheck` Mission Contract in `project-plan.md`
(identical user question with a different header decoder); remaining classes
are moot once novelty fails. Honest deferral is not rated as a utility.

## Committed Recommendation

**Commit to exactly one bounded recommendation: `sparsemap`.** The seventh
mission should solve one user problem: determine what logical data and hole
ranges the active filesystem reports for explicitly named regular files, so an
operator can investigate whether sparsity appears to have survived a build,
copy, extraction, or image-handling step. Its Unix-style purpose is a finite,
read-only observation that turns explicit operands into ordered text facts for
humans and pipelines. The word “reported” is essential: the result is not a
physical block map, allocation audit, compression report, sharing/reflink
report, reclaim estimate, or proof that a copy is correct. This commitment is
capability-level selection evidence pending fresh independent review of this
reconciled artifact; it is not an implementation authorization and does not
change the FAILED status of origin run `f7539c314ca1`.

The likely ISO C17 implementation scope is small. For each explicit operand, a
future contract can define a race-aware regular-file open/type policy, retain
one descriptor, take a bounded logical-size observation, and drive a
progress-checked `off_t` state machine using `SEEK_DATA` and `SEEK_HOLE` until
logical EOF or a classified unsupported/error state. It needs bounded operand,
extent, offset, diagnostic, and output handling; terminal-safe escaping; clear
descriptor ownership; and no content reads. The evaluation intentionally does
not freeze exact options, fields, statuses, constants, or file layout.

The security posture is favorable but not risk-free. Hostile operands may be
symlinks, special files, renamed or replaced during open, truncated or extended
during observation, inaccessible, enormous, or crafted to drive offset
overflow, nonprogress, excessive extents, diagnostics, or terminal control
bytes. The later contract must choose and document the symlink/type/race policy,
use wide checked offsets, cap all attacker-controlled dimensions, guarantee
descriptor cleanup, separate ordinary per-file failures from internal failure,
and never execute, map, copy, rewrite, punch holes in, or otherwise mutate the
target. Concurrent file mutation means only a point-in-time sequence of
observations can be claimed.

The dependency posture is libc-only. Expected interfaces are standard
descriptor/stat operations plus the platform declarations for
`SEEK_DATA`/`SEEK_HOLE`; no FIEMAP ioctl, libmount, filesystem-specific library,
external command, interpreter, database, daemon, plugin, network, or privileged
helper is justified. Portability must be stated honestly as Linux-oriented
behavior using seek modes whose useful fidelity is filesystem-dependent, with
large-file and feature-test requirements made explicit.

The smallest release-quality vertical slice is one explicit-regular-file
operation from safe operand acquisition through ordered data/hole observations,
including empty and all-data files, leading/trailing holes, unsupported or
coarse filesystem behavior, EOF, nonprogress, mutation/error seams, integer and
resource bounds, escaping, and cleanup. A deterministic syscall seam is needed
to make the transition machine independently testable, while ordinary
unprivileged live sparse-file fixtures provide supplemental integration
evidence wherever the filesystem exposes holes. The slice stops before
recursive discovery, file comparison, allocation accounting, FIEMAP,
filesystem-specific interpretation, mutation, repair, policy, or monitoring.

`sparsemap` defeats every eligible alternative. It beats `cgroupceil` because
its answer concerns only the named descriptor and does not invite a misleading
local-versus-effective hierarchy claim; `cgroupceil` would need ancestor and
controller policy to close its most important gap. It beats `mountstack`
because one checked seek loop is smaller than a forward-compatible escaped
record parser plus grouping, and a live positive needs no namespace or mount
operation. It beats `lockscope` because it avoids a global,
namespace-filtered, concurrently changing proc table, process metadata, and OFD
owner ambiguity. `elfinterp` cannot compete because it fails the novelty hard
gate, regardless of its arithmetic total. `sparsemap` beats deferral on the
present matrix because it scores 141, passes all four mandatory minima, remains
read-only and unprivileged, has a credible small-C implementation, and makes a
useful claim without crossing the discovery boundary. That defeat of deferral
is conditional: if fresh independent review finds the seven-point margin over
`cgroupceil`, the recycled-candidate provenance, the Deterministic
testability / Portability honesty scores of 2, or residual SEV7/REC7 debt
insufficiently resolved, honest deferral remains the correct alternative and
must not be overridden by lowering gates.

Differentiation is durable at the operation level: `sysdiff` compares supplied
snapshot facts; `pathaudit` analyzes executable-search trust; `permguard`
reports mode-bit policy; `inodealias` groups path identities; `shebangcheck`
preflights a content-declared interpreter; `openunlink` correlates one process's
descriptors with zero-link files. `sparsemap` alone observes a named regular
file's filesystem-reported logical layout. Shipping all seven would not merge
their user questions or their core evidence sources. Exact CLI grammar, output
bytes, finding/diagnostic taxonomy, numeric exit statuses, signal behavior, and
resource constants stay deferred; this evaluation freezes none of them.

## Risks and Next Actions

The primary product risk is semantic overclaim. A filesystem is allowed to
report all regions as data, written zeroes are not necessarily holes, and an
observed hole is not a promise about physical allocation, sharing, compression,
future contents, or reclaim. The later behavioral contract must make that
limitation visible in normal help and result semantics, not bury it in an
implementation note. The main technical risks are a nonprogressing or
inconsistent seek sequence, `off_t` overflow, a file changing during the scan,
symlink/type races, unsupported or coarse interfaces, adversarial extent count,
and terminal-unsafe operands. The main test risk is confusing a host
filesystem's permitted all-data answer with missing coverage; the exact
state-machine oracle must not depend solely on host extent fidelity. Portfolio
uncertainty remains: this recommendation is unreviewed residue from failed
attempt 3 of `f7539c314ca1`, prior review attempt 1 and attempt 2 disagreed
about the pre-repair `elfinterp` artifact (`REC7-M1`), and arithmetic plus
heading checks do not equal a governed pass.

Prior independent-review findings from
`code-reviews/review-seventh-utility-mission-evaluation.verdict.json` are
itemized here as **apparently addressed in failed-attempt residue but pending fresh adjudication**.
None is accepted as closed by this reconciliation alone:

- **`SEV7-H1` (High):** capability-level novelty failure of the prior
  `elfinterp` winner versus the normative `shebangcheck` Mission Contract in
  `project-plan.md`. Apparently addressed by scoring `elfinterp` Novel
  capability `0` (hard-gate fail) and committing to capability-distinct
  `sparsemap` instead of defending a file-format distinction. Pending fresh
  review of the `sparsemap` recommendation and novelty ledger.
- **`SEV7-M1` (Medium):** undisclosed recycled candidates / overstated survey
  yield. Apparently addressed by the provenance paragraph recording fifth-
  mission `mountstack`/`lockscope`/`cgroupceil` totals `41/55`, `35/55`,
  `43/55` and sixth-mission `sparsemap`/`mountstack`/`cgroupceil` totals
  `42/50`, `38/50`, `41/50`, with explicit non-comparability to this 168-point
  matrix and disclosure that only `elfinterp` was new to the failed origin
  attempt. Pending fresh review.
- **`SEV7-M2` (Medium):** inflated Security score for a content-derived path.
  Apparently addressed by restating `elfinterp` Security and privilege posture
  as `3` (bounded tradeoff) rather than an unqualified `4`, with total `128`.
  Pending fresh review.
- **`SEV7-M3` (Medium):** conflicting unmarked frame authority. Apparently
  addressed by the conspicuous superseded marker on
  `plans/seventh-utility-mission-frame.md` and by this evaluation citing only
  `plans/seventh-utility-mission-contract.md` as live authority. Pending fresh
  review.
- **`SEV7-L1` (Low):** omitted released-versus-preview portfolio labels.
  Apparently addressed by labeling `sysdiff` released v0.1.0; `pathaudit` and
  `permguard` implemented preview/uninstalled/unpackaged; `inodealias`,
  `shebangcheck`, and `openunlink` planning-only with no product artifacts.
  Pending fresh review.
- **`SEV7-L2` (Low):** missing external-source observation provenance.
  Apparently addressed by recording observation date `2026-07-30`, web-page
  access method, and the authoritative `lseek(2)` / `proc_locks(5)` /
  `proc_pid_mountinfo(5)` / cgroup-v2 citations used for score evidence.
  Pending fresh review.

Recovery-review debt from
`code-reviews/review-f7539c314ca1-recovery.verdict.json` (`REC7-M1`,
`REC7-M2`, `REC7-L1`–`L4`) remains visible on the evidence record and is not
declared closed here.

The smallest justified next action for this recovery is a fresh independent
REVIEW of this reconciled planning evidence against the repaired contract, with
TEST AS USER limited to the existing mechanical sysdiff-centered smoke route.
Do not treat smoke start/check zeros as `sparsemap` product evidence. Do not
authorize source, tests, builds, manuals, README changes, packaging, or
release from this evaluation alone. If REVIEW rejects the recommendation,
record honest deferral with the failed gates rather than lowering thresholds or
restarting discovery inside this recovery. Only after a clean selection review
would a separate planning step author a normative `sparsemap` behavior contract;
that later contract is not opened by this file.

No compiler, product test suite, formatter, coverage tool, analyzer, package
manager, or build command was run for this analysis-only reconciliation. Agent
phases TEST, CODE, user-facing DOCUMENT, and TEST + FIX are omitted because
only the three existing seventh-mission planning files may change. The
governed writes for this step stay within
`plans/seventh-utility-mission-evaluation.md`,
`plans/seventh-utility-mission-contract.md`, and
`plans/seventh-utility-mission-frame.md`.
