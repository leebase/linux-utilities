# Fifth Utility Mission Evaluation

Decision date: 2026-07-29. This is read-only mission selection for a later
governed playbook. It does not assert that a fifth executable exists, and it
does not define a normative command line, output grammar, or numeric exit
statuses.

## Candidate Set

The following evidence ledger separates observation from inference. All
observations were made on 2026-07-29.

| Observed fact | Source | Bounded inference |
| --- | --- | --- |
| The live source, test, and manual inventories contain `sysdiff`, `pathaudit`, and `permguard`, but no `inodealias` or fifth executable. | `rg --files`; `src/`, `tests/`, `man/`; `Makefile` variables `ALL_SRCS` and `ALL_MANPAGES` | Three utilities are implemented. The fourth mission is not implemented in the live tree, so the fifth choice must remain novel both before and after a possible `inodealias` delivery. |
| The only repository tag is `v0.1.0`; its tag message and tree identify sysdiff and contain no pathaudit or permguard product file. | `git tag -l`; `git show --no-patch v0.1.0`; `git ls-tree -r --name-only v0.1.0` | Only sysdiff has repository release-marker evidence. Release work for any existing utility is not a new mission. |
| Pathaudit implements explicit-root, process-PATH, and command-specific trust analysis; permguard implements explicit-path mode-bit inspection. | `docs/pathaudit-contract.md`, `src/pathaudit.c`, `tests/test_pathaudit.py`; `docs/permguard-bootstrap-contract.md`, `src/permguard.c`, `tests/test_permguard.py` | A candidate cannot win by checking PATH resolution, executable shadowing, path ownership/writability, or named-object mode bits under another name. |
| `plans/fourth-utility-mission-evaluation.md` selects `inodealias` identity grouping, while `code-reviews/review-fourth-utility-mission.verdict.json` passes the decision with one Medium and two product-document Lows. No inodealias product artifact appears in the inventory. | The named evaluation and verdict; repository-wide `rg` for `inodealias` and `st_ino` excluding the decision files | `inodealias` is selected planning, not implemented, reviewed product behavior, installed software, or a release. Filesystem-identity grouping and hard-link alias diagnosis are nevertheless reserved and ineligible for the fifth mission. |
| Current shared state requires repair and independent review of five permguard Medium findings before feature expansion; older pathaudit and sysdiff repair items also remain visible. | `context.md`, `sprint-plan.md`, `result-review.md`, `STATUS.md`, `WHERE_AM_I.md` | The evaluation may select a mission, but a later implementation playbook must obey the repair-before-expansion gate. Repair itself is not a fifth utility. |
| The immediately preceding run `6ca4cebc8527` (`pathaudit_maintenance_repairs`) is `FAILED`: contract, test, code, and documentation steps passed, but verification failed on an unexpanded `src/*.c` command and then timed out; smoke, independent review, and closeout remain pending. Its changed paths are still visible in `git status`. | `../linux-utilities-agent-orch-runs/6ca4cebc8527/run.json` and `dashboard.html`; `git status --short`; `docs/pathaudit-maintenance-repair-contract.md` | The right-sized shadow storage, basename index, and duplicate-shadow suppression edits are incomplete, unreviewed maintenance state—not established capability and not fifth-mission material. This evaluation must preserve those edits and avoid claiming their findings closed. |
| The latest sibling run is `e5f6740c1571`, status `RUNNING`, at `step_02_discover_and_evaluate`; its dashboard names this evaluation as the missing governed output. | `../linux-utilities-agent-orch-runs/latest/run.json`; latest `dashboard.html` | This document is the active governed work. Manual implementation, testing, smoke, or shared-state editing would exceed and duplicate the run. |
| Existing quality and smoke surfaces cover three C sources, but install/release and the named smoke user flow remain sysdiff-centered. | `Makefile`; `tests/smoke_manifest.json`; `scripts/smoke.sh`; `tests/check_sysdiff_smoke.py`; `QUALITY.md`; `TESTING.md` | A fifth utility can reuse the quality floor later, but transitive `make test` is not dedicated fifth-utility smoke and quality wiring is not itself operator value. |

The candidates below come from concrete Linux operating tasks. No download
counts, issue counts, survey results, or other external demand evidence were
collected, so none is claimed. Each dossier states only the practical problem
and the smallest capability that could be evaluated with repository-local
fixtures.

**Candidate A — `shebangcheck`, explicit-script interpreter validation.**
Operators and developers encounter scripts that are present and executable but
fail at launch because the shebang is malformed, uses a missing absolute
interpreter, contains a carriage return, or names an interpreter that is not
executable. The smallest useful capability reads a bounded first line from
explicit regular-file operands and validates only direct absolute-interpreter
shebangs. Likely inputs are ordinary temporary script files plus temporary
interpreter files/directories; likely output is one deterministic finding per
invalid script. The dependency ceiling is ISO C17 plus libc and narrowly
justified POSIX file metadata/read interfaces, with Linux as the declared
product platform. It excludes PATH lookup, `/usr/bin/env` operand semantics,
shell parsing, script execution, recursive discovery, permission repair,
content comparison, mode-bit auditing, and filesystem-identity grouping.

| Closed selection hazard | Rating | Evidence, consequence, and mitigation |
| --- | --- | --- |
| 1. Duplication of existing utilities | clear | Repository inventory shows no shebang validator. Pathaudit only probes `#!`/ELF while deciding whether a PATH candidate is executable; it does not validate an explicitly named script's interpreter. The slice must never search process PATH or classify path trust. |
| 2. Duplicate quality-polish work | clear | The result is a new launchability diagnosis, not tests, docs, sanitizers, packaging, or backlog repair. Existing gates are later acceptance machinery only. |
| 3. Release-process drift | clear | The mission needs no tag, install target, package, source archive, release review, or publication. The `v0.1.0` tag supplies no evidence for it. |
| 4. Excessive scope | bounded with an explicit mitigation | Full shebang behavior includes kernel-length limits, optional arguments, `/usr/bin/env -S`, CRLF, and platform differences. The first slice admits only one bounded first line and one direct absolute interpreter token; all launcher and argument semantics are deferred. |
| 5. Unsuitable dependencies | clear | Files and metadata can be inspected with libc/POSIX calls. No parser library, interpreter, database, service, or new build system is needed. |
| 6. Background or network services | clear | Inspection is one-shot over explicit files. It starts no watcher, daemon, subprocess, interpreter, or network client. |
| 7. Weak practical value | clear | The observable outcome is narrow: identify an explicit script that cannot use its direct shebang interpreter under the declared checks before a deployment or invocation. It provides more than republishing metadata because it relates the script header to the interpreter object. |
| 8. Does not fit a small auditable C utility | bounded with an explicit mitigation | Byte parsing and path inspection are deterministic if capped. Reject special files and final symlinks, read only a contract-sized prefix, escape operand/header bytes, and refuse to emulate a shell or the complete Linux loader. |

**Candidate B — `openunlink`, deleted-but-open regular-file descriptor
reporting.** Administrators diagnosing disk space that did not return after
deletion need to find a process that still holds an unlinked regular file.
The smallest useful capability inspects one explicitly identified Linux
process descriptor directory, follows its numeric descriptor links for
metadata, and reports descriptors whose regular-file target has `st_nlink ==
0`. Likely evidence is a same-UID helper process that opens and unlinks a
temporary file while a test inspects its `/proc/<pid>/fd`; output would identify
the process/descriptor and observed size without claiming reclaimable totals.
It needs libc, POSIX directory/stat calls, and Linux procfs. It excludes
signals, process control, file closing, `/proc`-wide discovery, owner lookup,
network sockets, aggregation by inode, and inodealias-style grouping.

| Closed selection hazard | Rating | Evidence, consequence, and mitigation |
| --- | --- | --- |
| 1. Duplication of existing utilities | clear | No existing or selected mission diagnoses process-held deleted files. It neither compares snapshots, audits PATH/mode bits, nor groups caller-supplied filesystem aliases. |
| 2. Duplicate quality-polish work | clear | It is a distinct runtime inspection capability, not a memory-gate, test, documentation, release, or repair project. |
| 3. Release-process drift | clear | No packaging or publication is required for its first outcome. Existing release evidence would remain unrelated. |
| 4. Excessive scope | bounded with an explicit mitigation | System-wide PID discovery, totals, namespaces, containers, and remediation would be excessive. Limit the slice to one explicit process descriptor directory and per-descriptor facts. |
| 5. Unsuitable dependencies | clear | libc plus Linux procfs is enough; no `lsof`, daemon, database, or privilege helper is required by design. |
| 6. Background or network services | clear | The scanner is one-shot and passive. A test helper may hold a fixture descriptor, but product behavior launches no helper and performs no network activity. |
| 7. Weak practical value | clear | It answers a concrete disk-space diagnosis question and can distinguish an unlinked object through link count rather than guessing from a ` (deleted)` display suffix. |
| 8. Does not fit a small auditable C utility | bounded with an explicit mitigation | Numeric-directory enumeration is manageable, but procfs entries race with descriptor close/reuse and access can be denied. Cap entries, define point-in-time observations, continue or fail according to a later contract, and make Linux/procfs support explicit. |

**Candidate C — `mountstack`, stacked mount-target detection from explicit
mountinfo.** Operators investigating why a directory's expected contents are
hidden need to notice multiple mounts layered on the same mount point. The
smallest capability parses one explicit Linux
`/proc/*/mountinfo`-shaped snapshot and reports decoded mount-point fields that
occur more than once, preserving source order. Fixtures are bounded text files
covering escaped spaces, malformed numeric fields, optional fields, and
duplicates. It needs libc only at runtime but is Linux-format-specific. It
excludes live namespace entry, unmounting, filesystem identity, propagation
policy, capacity checks, fstab parsing, snapshot diffing, and recursive mount
discovery.

| Closed selection hazard | Rating | Evidence, consequence, and mitigation |
| --- | --- | --- |
| 1. Duplication of existing utilities | clear | No current utility interprets mount topology. Explicit record decoding is not sysdiff's opaque key/value comparison and must not grow into general state diffing. |
| 2. Duplicate quality-polish work | clear | Stacked-target diagnosis is new operator behavior; fixture tests would validate it rather than constitute the mission. |
| 3. Release-process drift | clear | It requires no tag, package, installer, or release-candidate work. |
| 4. Excessive scope | bounded with an explicit mitigation | General mount policy, propagation, namespace traversal, and fstab reconciliation are excluded. Only duplicate decoded mount-point fields in one bounded input are eligible. |
| 5. Unsuitable dependencies | clear | A purpose-built bounded parser can use libc; no libmount is required for the narrow slice. |
| 6. Background or network services | clear | An explicit file is read once; there is no namespace watcher, daemon, or network access. |
| 7. Weak practical value | bounded with an explicit mitigation | Hidden contents from overmounting are real, but duplicate target text alone does not explain intent or safety. Phrase the result as stacked targets, never as an erroneous mount or remediation recommendation. |
| 8. Does not fit a small auditable C utility | bounded with an explicit mitigation | Mountinfo escaping, separators, optional fields, and record limits make the parser larger than Candidate A. A closed grammar subset, decoded-field cap, line/record/byte ceilings, and reject-closed malformed input are mandatory. |

**Candidate D — `lockscope`, explicit Linux kernel-lock snapshot decoding.**
Developers and administrators debugging blocked file access need a compact view
of active advisory locks. The smallest capability parses an explicit
`/proc/locks`-shaped snapshot and emits normalized lock kind, access mode,
owner PID, device/inode token, and byte range without resolving paths.
Fixtures are bounded text records containing whole-file locks, finite ranges,
EOF ranges, blocked-lock markers, and malformed fields. Runtime needs libc and
is Linux/procfs-format-specific. It excludes live polling, PID-to-command
mapping, `/proc/*/fd` reverse lookup, waiting/deadlock inference, lock
acquisition, signals, and inodealias grouping.

| Closed selection hazard | Rating | Evidence, consequence, and mitigation |
| --- | --- | --- |
| 1. Duplication of existing utilities | clear | Existing and selected utilities do not decode kernel lock records or diagnose lock contention. Device/inode tokens remain opaque record fields rather than alias grouping. |
| 2. Duplicate quality-polish work | clear | Normalized lock inspection is new user behavior, not a test/quality/release activity. |
| 3. Release-process drift | clear | No release machinery is part of the smallest capability. |
| 4. Excessive scope | bounded with an explicit mitigation | Path resolution, process metadata, polling, and deadlock graphs would turn one parser into a policy tool. The first slice accepts one explicit snapshot and performs no joins. |
| 5. Unsuitable dependencies | clear | The narrow record parser needs libc only, though avoiding a library transfers grammar ownership to this project. |
| 6. Background or network services | clear | Snapshot decoding is finite and passive; no watcher, lock holder, or remote lookup runs. |
| 7. Weak practical value | bounded with an explicit mitigation | Raw lock records are difficult to read, but without path resolution the result serves diagnosis rather than directly naming the user's file. Documentation must not overclaim deadlock or blocker identification. |
| 8. Does not fit a small auditable C utility | bounded with an explicit mitigation | Kernel record variants, large numeric ranges, blocked markers, and device/inode syntax create parser maintenance. Freeze the accepted grammar, cap all fields, and reject unknown/malformed records rather than guessing. |

**Candidate E — `cgroupceil`, explicit cgroup-v2 resource-ceiling summary.**
Container and service operators need to understand why CPU, memory, or process
creation is constrained even when host resources appear available. The
smallest capability reads a caller-supplied cgroup-v2 directory containing a
closed set of limit files and normalizes only “unlimited” versus finite
values. Fixtures are ordinary directories and small text files with `max`,
decimal values, missing files, and malformed data. It needs libc/POSIX file
access and Linux cgroup-v2 semantics. It excludes hierarchy traversal,
effective-limit inheritance, utilization, pressure metrics, v1 controllers,
systemd/Docker/Kubernetes integration, mutation, monitoring, and persistence.

| Closed selection hazard | Rating | Evidence, consequence, and mitigation |
| --- | --- | --- |
| 1. Duplication of existing utilities | clear | No existing or selected mission reads cgroup controls. It is not snapshot comparison because it assigns semantics to a closed live-file set. |
| 2. Duplicate quality-polish work | clear | Resource-ceiling interpretation is a new operator capability rather than quality or documentation maintenance. |
| 3. Release-process drift | clear | The useful slice has no packaging, tagging, install, or publication requirement. |
| 4. Excessive scope | bounded with an explicit mitigation | “Effective resources” requires ancestor traversal and controller-specific rules. Limit the slice to literal values in one explicit v2 directory and make non-inheritance explicit. |
| 5. Unsuitable dependencies | clear | No systemd, container runtime, or cgroup library is required for literal-file inspection; libc is sufficient. |
| 6. Background or network services | clear | It performs a one-shot read and starts no monitor, service, runtime client, or network request. |
| 7. Weak practical value | bounded with an explicit mitigation | Literal local ceilings are useful evidence, but omitting ancestors can mislead about effective limits. The first slice must say “local configured values,” not “effective available resources.” |
| 8. Does not fit a small auditable C utility | bounded with an explicit mitigation | Several files and controller units create a wider taxonomy than Candidate A. Admit only a closed file set and decimal/`max` grammar with strict byte/value bounds; defer hierarchy and arithmetic. |

## Charter Fit

The product charter calls for one-purpose, auditable Linux tools written as
small C17 executables, with deterministic behavior, no hidden service,
telemetry, networking, or dependency sprawl (`product-definition.md`,
`project-plan.md`, `AGENTS.md`, and `README.md`, observed 2026-07-29). All five
candidates can be read-only and one-shot, but they do not fit equally well.

The live mission inventory is:

- **`sysdiff` — released/tagged evidence:** explicit deterministic comparison
  of two plain-text snapshots. `v0.1.0` is the sole tag, and its tree is
  sysdiff-only. Its release, quality, sanitizer, benchmark, archive, install,
  documentation, and remaining repair work are existing lanes, not candidates.
- **`pathaudit` — implemented preview, unreleased:** explicit-root, `--path`,
  and `--command` trust analysis, including PATH directory conditions,
  executable shadowing, writability, and ownership. The Makefile compiles it
  in temporary locations and does not install it. Run `6ca4cebc8527` attempted
  maintenance for shadow storage, lookup complexity, and duplicate rows, but
  failed verification and never reached smoke or independent review; its dirty
  edits are not completed evidence. Pathaudit's active capabilities and this
  incomplete repair disqualify PATH search, executable-origin trust,
  shadowing, and pathaudit polish as fifth missions.
- **`permguard` — reviewed preview bootstrap, unreleased:** explicit named-path
  mode-bit inspection with four live finding codes and no recursion, PATH read,
  remediation, install, or package. Five Medium repairs and fresh independent
  review are required before feature expansion. Permission-policy or permguard
  repair candidates are rejected.
- **`inodealias` — fourth mission selected, planning only:** the fourth
  evaluation reserves explicit-path `(st_dev, st_ino)` identity grouping.
  The review passed but recorded FUM-M1 (the handoff must require completion
  and independent review of permguard Medium repair) plus portability and
  attribution Lows. No source, test, manual, Make variable, smoke identity,
  tag, or release exists. The fifth mission therefore excludes hard-link
  discovery, alias grouping, and equivalent filesystem-identity reporting
  regardless of whether inodealias is later delivered.

Candidate A fits the charter most directly: one bounded header read, one
direct relationship to inspect, ordinary deterministic fixtures, and no
privilege or procfs dependency. Candidate B has stronger incident-response
impact but its useful fixture necessarily coordinates a live process and
procfs, adding races and permission variability. Candidates C and D are
deterministic with explicit snapshots but own evolving Linux text grammars;
Candidate C also risks becoming a topology/policy engine, while Candidate D's
smallest path-free result is less actionable. Candidate E has excellent
ordinary-file fixtures but either reports only local literal controls, which
can be mistaken for effective limits, or grows into hierarchy traversal and
controller policy.

None of the five duplicates a current quality, documentation, sanitizer,
packaging, release, or repair item. The selection itself does not override the
current repair-before-feature-expansion rule: a later implementation remains
blocked until the bounded permguard Medium repair is completed and
independently reviewed, and any broader Medium-or-higher project gate still
applies.

## Comparative Evaluation

The common scale is **1 (poor), 2 (weak), 3 (acceptable with material
limits), 4 (strong), 5 (excellent)**. Every score is favorable at the high
end; therefore “security exposure 5” means the lowest exposure, and
“dependency cost 5” means the lowest cost. Scores compare the deliberately
smallest slices above, not imagined mature products.

| Criterion | A: shebangcheck | B: openunlink | C: mountstack | D: lockscope | E: cgroupceil |
| --- | ---: | ---: | ---: | ---: | ---: |
| Practical usefulness | 5 | 5 | 4 | 3 | 4 |
| Unix simplicity | 5 | 4 | 3 | 3 | 4 |
| Novelty in this suite | 5 | 5 | 5 | 5 | 5 |
| Maintainability | 5 | 3 | 3 | 2 | 3 |
| Technical risk | 5 | 3 | 3 | 2 | 3 |
| Educational value | 4 | 5 | 4 | 4 | 4 |
| Potential impact | 4 | 5 | 4 | 3 | 4 |
| Sustainability | 5 | 3 | 3 | 2 | 3 |
| Security exposure | 5 | 3 | 4 | 4 | 4 |
| Dependency cost | 5 | 5 | 5 | 5 | 5 |
| Small C17 + plain make suitability | 5 | 4 | 3 | 3 | 4 |
| **Total / 55** | **53** | **45** | **41** | **35** | **43** |

The totals expose rather than replace judgment. Candidate A scores highest
because its useful boundary is also its smallest boundary: inspect explicit
ordinary files, parse one capped line, and relate it to one direct interpreter
path. The semantics can be fully demonstrated with privilege-free fixtures,
and likely future kernel or launcher details can be refused rather than
silently approximated.

Candidate B loses to A despite greater incident impact because procfs
descriptor enumeration is inherently point-in-time, permission-sensitive, and
racy; its best positive fixture needs a coordinated live holder process.
Candidate C loses because correct mountinfo tokenization and escaping create a
larger maintained grammar, while duplicate mount points do not by themselves
prove an operator error. Candidate D loses because `/proc/locks` variants and
range parsing impose the highest parser maintenance, yet the no-path slice is
less actionable and path resolution would cause scope growth. Candidate E
loses because literal values are not effective hierarchical ceilings; closing
that semantic gap requires ancestor/controller logic that the first slice
must exclude. No alternative has a compensating dependency, novelty, or
security advantage: all are dependency-free and novel, while A is simpler,
more deterministic, and at least as secure.

Uncertainty remains. This comparison has repository evidence for overlap,
delivery state, build cost, and current governance, but no external frequency
or adoption study. “Practical usefulness” and “potential impact” are reasoned
from the concrete operator outcome, not demand measurement. A later playbook
must validate exact Linux shebang behavior against authoritative platform
documentation and executable fixtures before it defines product bytes.

## Recommended Fifth Utility

**Mission name:** Bootstrap `shebangcheck` explicit-script direct-interpreter
validation.

**Operator problem:** An explicitly named script can look present and
executable yet fail immediately because its first line does not form a
supported direct shebang or because the named absolute interpreter is missing
or unusable. The mission gives an operator a read-only preflight result without
executing either the script or interpreter.

**Repository-evidence summary:** On 2026-07-29, the tree contains three
implemented utilities (`src/sysdiff.c`, `src/pathaudit.c`,
`src/permguard.c`), the sole tag `v0.1.0` identifies sysdiff, and
`plans/fourth-utility-mission-evaluation.md` reserves inode identity for
planning-only `inodealias`. Repository-wide inspection found no shebang
validation mission. Pathaudit's shebang probe only filters PATH candidates and
must remain separate. Current permguard and older project repairs remain
existing work rather than inputs to this choice.

**Side-by-side comparison result:** Candidate A scores 53/55, ahead of
openunlink 45, cgroupceil 43, mountstack 41, and lockscope 35 on the shared
favorable scale. More importantly, it has no disqualifying selection hazard:
its two bounded hazards—complete loader-syntax scope and hostile file/header
handling—become explicit first-slice limits.

**Why it defeats every alternative:** It defeats openunlink by avoiding
procfs permissions, process/descriptor races, and live-holder fixtures. It
defeats mountstack by avoiding an evolving multi-field kernel record grammar
and ambiguous policy inference from duplicate targets. It defeats lockscope
by avoiding the least stable parser and the path-resolution scope needed for
an actionable result. It defeats cgroupceil because its local observation is
the relevant direct relation; it does not omit an ancestor hierarchy necessary
to interpret the claimed result. All alternatives are novel and
dependency-cheap, so those ties do not erase A's determinism, auditability, and
maintenance advantages.

**Bounded first vertical slice:** Inspect explicit regular script operands,
read no more than a contract-defined first-line/prefix ceiling, recognize only
a closed direct-absolute-interpreter shebang subset, and determine whether that
interpreter object exists and meets the later contract's narrow usability
test. Produce deterministic, escaped findings for unsupported/malformed
headers and unusable direct interpreters. Reject or explicitly classify final
symlinks, special files, oversized/unterminated headers, inspection failures,
and output failures. Do not execute anything and do not search PATH. Exact
CLI, output bytes, finding taxonomy, ordering, diagnostics, resource constants,
signal behavior, and exit statuses are intentionally left to the later
implementation contract.

**Dependency ceiling:** One ISO C17 executable, libc, and only the POSIX
file/read/metadata/signal interfaces justified by the normative slice, built
with plain `make`. Existing Python/pytest and quality tools may drive tests.
No runtime library, shell/interpreter dependency for the binary, database,
privileged helper, service, network client, build tool, or new CI package.

**Explicit non-goals:** PATH search; `/usr/bin/env` name resolution or `-S`;
shell quoting or tokenization; multiple interpreter arguments; complete
emulation of every Linux kernel shebang rule; script/interpreter execution;
content hashing or comparison; recursive discovery; directory walking;
permission ownership policy; chmod/chown; symlink resolution policy beyond
the closed slice; inode aliasing; PATH trust; persistence; monitoring;
installation; packaging; tagging; publication; and repair or expansion of
sysdiff, pathaudit, permguard, or inodealias.

**Required later evidence:** A separately governed contract must cite the
authoritative Linux/POSIX boundary it chooses and pin exact behavior with
ordinary temporary fixtures for valid direct interpreters, missing and
non-executable interpreters, empty/malformed shebangs, CRLF, whitespace,
embedded NUL, missing newline, over-limit input, leading-dash/empty/relative/
hostile-byte operands, special files, symlinks, concurrent replacement,
closed stdout, and partial inspection failure. It must prove no script or
interpreter execution, bounded reads/allocation, deterministic complete
streams, strict GCC/Clang builds, static analysis, ASan/UBSan, Valgrind,
focused and aggregate tests, a dedicated user flow rather than relabeled
sysdiff smoke, and independent review with no unresolved release-blocking
finding.

**Handoff:** After the current permguard Medium repair is completed and
independently reviewed, and after any still-applicable Medium-or-higher
feature-expansion gate is cleared, Agent-Orch may generate a separate governed
implementation playbook for this one mission. That playbook—not this
evaluation—must author the normative contract before tests, code, user-facing
documentation, quality execution, smoke, and independent review. This
recommendation is exactly one planning commitment and is not implementation or
release evidence.

## Initial Vertical Slice

The first slice has one observable user value: before attempting a deployment
or invocation, a user can submit explicit ordinary script files and learn
which ones fail a deliberately narrow direct-interpreter preflight. A clean
result means only that each admitted shebang and interpreter satisfied the
closed checks at inspection time; it is not a promise that the script will run
successfully, safely, or identically later.

Likely inputs are explicit path operands naming temporary regular scripts.
Fixture interpreters can be ordinary regular files with controlled execute
bits under a temporary directory; no installed language runtime needs to be
invoked or even present. Likely outputs are deterministic escaped findings
that associate one script operand with one reason and, where safe, its parsed
direct interpreter path. The later contract must decide whether validation is
all-before-output or per-operand streaming and must specify operational-error
precedence without inheriting either behavior by assumption.

The capability boundary is deliberately closed:

1. Inspect only caller-named operands; do not enumerate directories or read
   process PATH, environment configuration, package metadata, or policy files.
2. Admit only regular files under a later, explicit final-symlink policy.
   Open/fstat sequencing, concurrent replacement, and read-error behavior must
   be specified so metadata and bytes are not silently attributed to different
   objects.
3. Read a fixed maximum prefix sufficient for the contract's maximum first
   line. Never read the script body, allocate from an unbounded header length,
   or accept truncation as a valid line.
4. Recognize `#!` only in the exact initial position and only the later
   contract's closed direct-absolute-interpreter form. Treat CR, NUL,
   unsupported whitespace/arguments, relative interpreters, env launchers,
   missing terminators, and excess length as explicit unsupported or malformed
   cases rather than guessing.
5. Inspect the direct interpreter path without launching it. The later
   contract must pin whether “usable” means existence, regular-file type,
   execute permission through the invoking credentials, or a smaller closed
   combination; it must not imply execution success from mode bits alone.
6. Bound operand count, total copied operand bytes, per-line bytes, finding
   count, and allocation arithmetic. Escape every untrusted displayed byte,
   handle stdout loss and SIGPIPE deliberately, and leave no hidden activity.

Initial review evidence should include a contract oracle, a focused temporary-
fixture test module, strict compiler/static/dynamic checks using existing
tools, full regression coverage, and one dedicated end-to-end script-check
flow. The current sysdiff smoke manifest may remain aggregate regression
evidence but cannot be renamed as direct shebangcheck smoke. No source or test
is authorized by this discovery step.

## Risks and Non-Goals

The main semantic risk is accidentally claiming to emulate Linux script
loading. Kernel shebang limits and optional-argument behavior vary across
platforms and versions, and `/usr/bin/env` adds its own parsing and PATH
semantics. Mitigation is a product claim narrower than the kernel: validate
only the contract's direct absolute-interpreter subset, label unsupported
forms honestly, and cite authoritative platform evidence during the later
contract step. No external portability or demand evidence is invented here.

The main filesystem risk is time-of-check/time-of-use change. A script or its
interpreter can be replaced after inspection; symlinks and special files can
redirect or block naive reads; execute accessibility can vary by credentials,
mount options, ACLs, and later state. The slice must be explicitly point-in-
time, read-only evidence, reject blocking file types, bound every operation,
and avoid safety or future-execution guarantees. It must not open an
interpreter for execution or mutate either object.

Resource and output risks include hostile argv bytes, long/nonterminated first
lines, embedded NUL, allocation overflow, duplicate operands, partial
inspection errors, and closed output pipes. The later contract must set
constant ceilings, use terminal-safe byte escaping, state duplicate and
partial-output behavior, and make operational failures visible. Existing
sysdiff/permguard techniques are evidence that the suite values those
properties, not authority to copy their exact CLI or numeric statuses.

Governance risk is equally explicit. The live sprint still requires bounded
repair and independent review of permguard PG-DOC-501, PG-DOC-502,
PG-TEST-503, PG-PORT-505, and PG-DOC-512 before feature expansion; older
Medium-or-higher gates may also remain. The failed, unreviewed pathaudit
maintenance run `6ca4cebc8527` also requires a separately governed recovery
decision; this document neither validates its dirty edits nor closes
`pathaudit-shadow-1/2/3`. Selecting shebangcheck does not bypass, repair,
close, or compete with that work, and it does not implement the planning-only
inodealias fourth mission.

Non-goals for this evaluation and first slice are all implementation, C source,
tests, fixtures, manuals, Make changes, smoke artifacts, shared AgentFlow
updates, compilation, formatting, analysis, coverage, sanitizers, Valgrind,
benchmarking, installation, packaging, tags, and publication. Product
non-goals are PATH resolution, env-launcher semantics, general shell parsing,
script execution, recursion, monitoring, networking, telemetry, persistence,
policy engines, remediation, and expansion or polish of an existing utility.
The selection authorizes only a later separately governed playbook after the
recorded gates are satisfied.
