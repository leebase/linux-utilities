# Fourth Utility Mission Evaluation

Decision date: 2026-07-29. This is an internal discovery decision only. It
does not implement, build, install, package, smoke-test, tag, or release a
fourth utility, and it does not repair any existing utility.

## Repository and Release Evidence

The evidence ledger separates observations from inferences:

| Observation | Reproducible command or file | Date | Bounded inference |
| --- | --- | --- | --- |
| Exact stdout from `git tag -l` is one line, `v0.1.0`; exit status was 0. | `git tag -l` | 2026-07-29 | There is exactly one repository version marker. No tag names `pathaudit` or `permguard`. |
| The annotated tag names “sysdiff 0.1.0 — initial public release candidate,” points to `fbdf07100d6d3129274432a355aaa6164fb880df`, and its tree contains `src/sysdiff.c`, `man/sysdiff.1`, and sysdiff tests but no pathaudit or permguard files. | `git show --no-patch --format=fuller v0.1.0`; `git ls-tree -r --name-only v0.1.0` | 2026-07-29 | The marker is evidence only for the sysdiff artifact. It cannot establish a pathaudit or permguard release. For mission selection, sysdiff is the shipped/tagged utility and no renewed sysdiff release-readiness mission is eligible. |
| The live tree implements three source files, but the ordinary build, `install`, `uninstall`, `dist`, and release surfaces remain sysdiff-centered. Pathaudit and permguard compile in temporary directories and join aggregate quality recipes without workspace binaries. | `Makefile`, especially `SRC`, `PATHAUDIT_SRC`, `PERMGUARD_SRC`, `BIN`, `pathaudit`, `permguard`, `install`, `uninstall`, `test-suite`, and release recipes | 2026-07-29 | Pathaudit and permguard are implemented but unreleased and installed-independent. Adding a fourth utility has incremental source/test/manual wiring cost, but no new quality tool is justified. |
| The smoke manifest names sysdiff fixture scripts. Its check calls `tests/check_sysdiff_smoke.py`, which calls `scripts/smoke.sh`, which calls `make test`; `make test` reaches full pytest transitively. | `tests/smoke_manifest.json`; `tests/smoke_start.py`; `tests/check_sysdiff_smoke.py`; `scripts/smoke.sh`; `Makefile` | 2026-07-29 | Aggregate smoke can catch regressions but is not direct user-flow evidence for pathaudit, permguard, or a fourth utility. A later delivery must not relabel it as such. |
| Current Agent-Orch run `6e89123d0c4b` is `RUNNING` at `step_02_evaluate_and_select_mission`; step 1 passed and created only the frame. The dashboard identifies this same active step and the evaluation file as its missing output. | `../linux-utilities-agent-orch-runs/6e89123d0c4b/run.json`; latest `dashboard.html` | 2026-07-29 | This evaluation is the active governed work. Manual implementation would duplicate and exceed the authorized slice. |

Inventory by delivery state:

- **Shipped/released:** `sysdiff` has the sole `v0.1.0` marker and an
  explicit-snapshot compare surface. Its current tag, installation, source
  archive, testing, sanitizer, Valgrind, documentation, and packaging work
  make further release-readiness or quality-polish work ineligible here.
- **Implemented but unreleased:** `pathaudit` has explicit-root, `--path`, and
  `--command` capabilities plus in-tree quality wiring. It has no matching
  release tag or install membership. `permguard` has the reviewed explicit-
  operand bootstrap described below, but also has no release tag, install
  membership, packaging, recursion, PATH mode, or remediation.
- **Deferred:** pathaudit writable-ancestor and set-ID-on-PATH expansion;
  pathaudit and permguard release/packaging; permguard recursion, PATH lookup,
  ownership/ACL/capability/mount policy, and remediation; broader sysdiff
  platform and packaging ideas in `ROADMAP.md`.
- **Still required, but not part of this mission:** the sprint’s active
  permguard Medium repair for PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and
  PG-DOC-512; visible pathaudit Medium/Low repair; and the already enumerated
  sysdiff packaging, testing, sanitizer, Valgrind, documentation, and
  release-authority backlogs.

`ROADMAP.md` still says the next executable action is the permguard bootstrap.
That direction is stale: `context.md`, `result-review.md`, `sprint-plan.md`,
`WHERE_AM_I.md`, and run `51100a584ac9` show the bootstrap is implemented and
reviewed. The newer sprint state controls. Its next action is repair, not a
third-utility bootstrap and not a fourth-utility mission. This decision does
not duplicate that repair.

## Permguard Verification

The real installed-independent interface is `permguard [--] PATH...`, with at
least one explicit operand, `--` to end option parsing, and sole-argument
`permguard --help` and `permguard --version`. There is no enabling flag,
configuration discovery, implicit scan, process `PATH` read, or installed
binary dependency: supplying explicit operands is the opt-in act. `Makefile`
intentionally creates no `build/permguard` and does not install it.

The observed closed finding codes are `GROUP_WRITABLE`, `OTHER_WRITABLE`,
`SET_USER_ID`, and `SET_GROUP_ID`, evaluated from each named non-symlink
object's own `lstat` mode bits without file-type heuristics. Final symlinks are
status-2 `SYMBOLIC_LINK` rejections. Findings stream in operand position and
fixed code rank; duplicate operands remain duplicate. Status `0` means a
clean operational scan or successful informational output, `1` means completed
hazard findings without an operational error, and `2` means usage or
operational failure. Valid mixed scans continue after errors, and operational
failure takes precedence over simultaneous findings.

Those facts agree across `docs/permguard-bootstrap-contract.md`,
`src/permguard.c`, `man/permguard.1`, `tests/test_permguard.py`, and the
current handoff records. The source has the documented one-`lstat` loop and
closed classifier; the test oracle pins the exact CLI, taxonomy, escaped
bytes, symlink behavior, mixed output, and numeric statuses.

Exact executable evidence on 2026-07-29:

```text
$ python3 -B -m pytest -p no:cacheprovider tests/test_permguard.py -q
....................................................                     [100%]
52 passed in 0.95s
```

The command exited 0 and ran the full file, not a selected case. This is real
CLI evidence because the session fixture compiles `src/permguard.c` with
`-std=c17 -Wall -Wextra -Wpedantic -Werror` into pytest's temporary session
tree, asserts it is not a repository binary, and launches that executable
through temporary filesystem fixtures. It proves the focused contract suite,
not installation, packaging, a dedicated smoke flow, the aggregate suite,
sanitizers, Valgrind, static analysis, or release readiness.

## Candidate Comparison

Candidate A — **`inodealias`: explicit-path filesystem identity grouping.**
Operator problem: determine which supplied names are aliases for the same
directory entry identity without comparing contents or inferring permission
policy. The smallest useful slice accepts at least two explicit paths, performs
one `lstat` per operand, treats the final symlink itself as the named object,
and groups equal `(st_dev, st_ino)` pairs. Proposed output is one
`ALIAS<TAB>"FIRST_PATH"<TAB>"LATER_PATH"` record for every later operand that
matches the earliest successful operand of that identity. Proposed statuses
are 0 for no aliases, 1 for at least one alias, and 2 for usage, inspection,
or output failure, with continue-after-error and operational precedence.
Likely surface: one small C17 source, a contract, one pytest module, a man page,
and temporary hard-link fixtures. It requires libc plus POSIX `lstat`, no new
runtime or quality dependency. It excludes content comparison, permission or
ownership classification, PATH reading, recursion, canonicalization,
remediation, and persistence.

| Closed hazard class | Rating | Repository evidence, mitigation, and consequence |
| --- | --- | --- |
| **Hostile input** | bounded with mitigation | Permguard proves byte-escaped argv diagnostics and checked output. The first slice must reuse that escaping, cap operand count/owned bytes, pin partial-output behavior, and fail status 2 on output loss. |
| **Path handling** | bounded with mitigation | Identity is one point-in-time `lstat` of each lexical operand; empty/relative paths, duplicates, missing entries, symlinks, special files, and races need explicit fixtures or contract statements. No traversal, canonicalization, following final symlinks, or mutation is allowed. |
| **Permissions** | clear | Ordinary user-created files, directories, hard links, and symlinks are sufficient. No `chown`, root, set-ID, ACL, or inaccessible fixture is required for the core definition of done. |
| **Portability** | bounded with mitigation | C17 plus POSIX `lstat`, `dev_t`, and `ino_t`; product support remains Linux. Equality uses the native typed values, not formatting assumptions. Feature-test macro/prototype handling must resolve PG-PORT-505's lesson rather than copy the hand declaration. |
| **Dependency growth** | clear | No runtime library, interpreter, service, database, network client, or new build/CI package. Pytest and the existing quality tools are already present. |
| **Overlap with existing utilities** | clear | It does not compare snapshot contents (`sysdiff`), inspect process PATH trust (`pathaudit`), or classify mode bits (`permguard`). Equivalent active repository work was not found in `ROADMAP.md`, `sprint-plan.md`, plans, docs, source, or tests. |
| **Maintenance burden** | bounded with mitigation | A linear operand table and pair identity matching are intentionally small. Cap inputs; keep one output relation and avoid recursive discovery, content hashing, canonical-path policy, or persistent indexes. |
| **Accidental repetition of release or quality-polish work** | clear | This is a new operator capability. Its later initial contract/tests/manual and additive reuse of existing gates are delivery necessities, not a standalone polish cycle; it creates no sysdiff release/tag work and no pathaudit/permguard repair or package work. |

Candidate B — **`portwatch`: fixture-fed Linux listening-socket reporter.**
Operator problem: decode local TCP/UDP listeners from explicit procfs snapshot
files without sending packets. A smallest slice could accept one explicit
`/proc/net/tcp`-shaped file and emit decoded IPv4 listen records, excluding PID
reverse mapping, IPv6, Unix sockets, and live `/proc` discovery. Likely
surface is a C parser plus captured text fixtures and byte-order oracles, with
libc only. This is distinct from all three utilities, but the useful real-world
promise rapidly depends on kernel/procfs details excluded from that tiny slice.

| Closed hazard class | Rating | Repository evidence, mitigation, and consequence |
| --- | --- | --- |
| **Hostile input** | disqualifying | Proc records combine untrusted widths, hexadecimal fields, counts, and malformed lines. The prior evaluation already rates this parser risk high; a safe bounded parser is possible, but the proposed IPv4-only slice would not yet support an honest “local listening sockets” claim. |
| **Path handling** | bounded with mitigation | An explicit fixture path avoids `/proc/*` traversal, but live usefulness later introduces procfs races and namespace identity. The first slice would need regular input limits and no symlink safety claim. |
| **Permissions** | clear | Explicit readable fixtures need no privilege. PID-to-fd ownership mapping is excluded because it adds permission-dependent omissions. |
| **Portability** | disqualifying | `/proc/net` grammar, Linux socket states, address byte order, namespaces, and IPv6 are central rather than incidental. An IPv4 fixture decoder is too narrow; a complete first useful contract is too broad for this bounded mission. |
| **Dependency growth** | clear | A parser can use libc only, with existing pytest fixtures and quality tools. |
| **Overlap with existing utilities** | clear | No repository utility reports sockets, and no active roadmap or sprint item supplies equivalent capability. |
| **Maintenance burden** | disqualifying | TCP/UDP, IPv4/IPv6, namespace, inode/PID mapping, and kernel-format fixtures create a larger evolving state space than the selected identity grouper. |
| **Accidental repetition of release or quality-polish work** | clear | It would be a new capability rather than release or polish, but that does not cure its parser, portability, and maintenance disqualifiers. |

Candidate C — **honest deferral of fourth-utility selection.** Deferral would
perform no executable work until a later read-only evaluation. It is safe, but
current repository evidence is sufficient to bound Candidate A.

| Closed hazard class | Rating | Consequence of deferral |
| --- | --- | --- |
| **Hostile input** | clear | No new parser or runtime input exists; no capability is delivered. |
| **Path handling** | clear | No filesystem operation is added; alias diagnosis remains an ad-hoc operator task. |
| **Permissions** | clear | No privilege assumptions arise, but no privilege-free hard-link fixture capability is used. |
| **Portability** | clear | No platform promise is made; the available C17/POSIX/Linux boundary remains unused. |
| **Dependency growth** | clear | No dependencies are added. |
| **Overlap with existing utilities** | clear | No duplication occurs, but no distinct suite breadth is gained. |
| **Maintenance burden** | clear | No code is owned; the cost is indefinite decision churn despite concrete evidence. |
| **Accidental repetition of release or quality-polish work** | bounded with mitigation | Deferral would be justified only if active repair policy forbids any later new capability. The current frame authorizes a decision and keeps repair separate, so that unblock condition is not present. |

Candidate A has no disqualifying class and has a small privilege-free fixture
surface. Candidate B is rejected on hostile parser, portability, and
maintenance grounds. Honest deferral is not chosen because the repository
already supplies the toolchain, test shape, non-overlap evidence, and a
bounded mission; waiting would not produce a missing fact.

## Committed Decision

Commit the stable mission title **Bootstrap `inodealias` explicit-path identity
grouping** for a later delivery playbook. “Commit” is a planning decision, not
a Git commit or release.

Purpose: let an operator submit names and deterministically learn which names
refer to the same `lstat` filesystem identity. Proposed CLI boundary:
`inodealias [--] PATH...` with at least two operands, plus sole-argument
`--help` and `--version`. Before `--`, leading-dash operands are rejected as
options. The later normative contract must pin exact help, diagnostics,
escaping, limits, and output bytes.

Closed first-slice behavior:

1. Attempt exactly one `lstat` for each operand after valid parsing. Do not
   follow the final symlink, open content, canonicalize, traverse, or mutate.
2. Preserve command-line order. For each successful later operand whose
   `(st_dev, st_ino)` equals an earlier successful identity, emit exactly one
   `ALIAS` record pairing the earliest such operand with that later operand.
   Duplicate spellings are not deduplicated.
3. Propose status 0 for a completed scan with no alias, 1 for one or more alias
   records and no operational error, and 2 for usage or operational failure.
   Continue after per-operand inspection errors; status 2 overrides aliases.
   Ignore SIGPIPE and check stdout so output loss is operational failure.
4. Escape every untrusted operand byte with the suite's printable-ASCII,
   quote/backslash, uppercase-hex convention. Bound operand count and total
   copied operand bytes in the normative contract before implementation.

Release-quality vertical slice means the later playbook delivers and jointly
reviews a normative contract, one auditable C17 source, privilege-free
temporary-fixture pytest coverage, a section-1 manual, minimal discoverability
text, and additive integration into the existing strict compilers, format,
tidy, cppcheck, analyzer, ASan/UBSan, Valgrind, and aggregate test surfaces.
It must run those existing gates; it must not invent parallel release,
packaging, sanitizer, Valgrind, documentation-polish, or smoke missions.

Required acceptance evidence includes distinct same-content files not
aliasing; a regular-file hard link aliasing; a directory hard link explicitly
out of fixture scope; target and symlink not aliasing under `lstat`; duplicate
operands; multiple alias groups; missing plus alias mixed precedence; relative,
empty, leading-dash, quote, control, and non-UTF-8 operands; deterministic
complete stdout/stderr/status bytes; checked closed-pipe behavior; read-only
before/after metadata; strict GCC and Clang; all existing static/dynamic gates;
the full new pytest module passing; aggregate regressions passing; and an
independent review verdict with no unresolved Critical or High finding.

Dependency ceiling: ISO C17, libc, and the POSIX metadata/signal interfaces
already justified by the suite; existing Python/pytest may drive tests. No new
runtime library, process service, database, network access, telemetry,
interpreter dependency for the binary, build tool, or CI package is permitted.

Explicit non-goals are content equality or hashing, snapshot comparison,
permission/ownership policy, PATH inspection, recursive hard-link discovery,
directory enumeration, canonical paths, mount or namespace analysis, live
monitoring, repair, rename/unlink/link creation, persistent indexing, install
membership, packaging, tagging, release, and changes to sysdiff, pathaudit, or
permguard behavior.

## Deferred and Remaining Work

This decision ships no fourth-utility artifact. `inodealias` source, tests,
contract, manual, Make wiring, user-facing documentation, smoke identity,
installation, packaging, tag, and release are all deferred to separately
approved governed work. The current sysdiff-centered smoke remains unchanged
and cannot be cited as a direct inodealias flow.

Existing work remains owned by its current backlog and is neither closed nor
copied into this mission:

- Permguard Medium PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512
  remain the active bounded repair slice, followed by independent review.
  The Low PG-CRAFT-506, PG-TEST-507, PG-CLI-508, and PG-MAKE-509/510/511
  findings remain visible.
- Pathaudit remains implemented but unreleased. Its shadowing/bootstrap
  Mediums and visible Low findings remain ordinary repair. Writable-ancestor,
  set-ID-on-PATH, ACL/capability/mount work, install, packaging, and release
  remain deferred rather than becoming inodealias requirements.
- Sysdiff's `v0.1.0` marker makes renewed release-readiness work ineligible for
  this mission. Its already active documentation, testing, sanitizer,
  Valgrind, packaging, source-archive, and release-authority items stay in
  their existing lanes; none is proposed again.
- `portwatch` is deferred until a future evaluator can present a complete
  smallest-useful Linux contract that prices IPv6, byte order, namespaces,
  procfs grammar, resource bounds, and fixture provenance without PID reverse
  mapping scope creep. Repository maintainers can supply such a contract and
  captured kernel-versioned fixture evidence; absent that, it remains
  rejected, not a vague research task.

No source, test, build, smoke, release, or user-facing documentation file was
authorized to change in this slice. The sole governed output is this planning
decision under `plans/`.

## Next Executable Slice

After this decision passes independent review and after Agent-Orch schedules
the work without colliding with the active permguard repair, generate a
governed delivery playbook titled **Bootstrap `inodealias` explicit-path
identity grouping**. Its first step must author the normative contract from the
proposed boundary above; later steps must write tests, implement the C source,
add the required initial manual/discoverability text and additive Make wiring,
run the existing release-quality floor, execute a dedicated temporary-fixture
inodealias user flow rather than relabeling sysdiff smoke, and obtain an
independent review verdict.

The executable definition of done for that later slice is a full dedicated
`tests/test_inodealias.py` pass with no selected-case filtering, plus aggregate
regression and existing quality-gate evidence recorded by provenance. Required
fixtures must be created below temporary directories and must prove hard-link
identity, non-alias controls, lexical operand preservation, symlink
non-following, duplicate/multi-group ordering, hostile-byte escaping,
mixed-error precedence, output failure, and no mutation. Host inability to
create an ordinary file hard link on the test filesystem must be an explicit
failure or capability report, never an invented pass.

Before launch, the playbook must re-read the latest run dashboard and
`run.json`, verify that no newer active mission already implements equivalent
inode identity grouping, and preserve the dependency ceiling and non-goals
from this decision. It must not run as an ad hoc manual implementation and
must not alter existing utility behavior as a convenience refactor.
