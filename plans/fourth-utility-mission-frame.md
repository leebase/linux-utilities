# Fourth Utility Mission Frame

## Mission Boundary

This discovery slice evaluates whether the suite should commit to one fourth
small Linux utility after `sysdiff`, `pathaudit`, and the reviewed `permguard`
bootstrap. Its sole governed output is an evidence-backed mission decision:
either one narrowly specified, read-only, auditable C17 utility with a smallest
useful first delivery slice, or an honest deferral with precise unblock
conditions. “Commit” here means make one bounded planning decision for a later
delivery playbook; it does not mean create a Git commit, tag, release, binary,
or implementation.

The evaluation must distinguish observed repository state from historical
claims. It must identify what is shipped, what is implemented but unreleased,
what is explicitly deferred, and what repair or decision work is still
required. The current roadmap and sprint state may disagree in age or emphasis:
that disagreement is evidence to reconcile, not permission to repeat an old
mission. The selected utility must add a distinct operator capability, remain
small enough for one engineer to audit, require no daemon or network access,
and admit a bounded fixture-driven delivery contract.

## Evidence Plan

The decision must cite a reproducible evidence ledger with the observation,
command or file, date, and inference kept separate. Repository tags from
`git tag -l --sort=creatordate` establish published version markers only; the
currently observed sole tag, `v0.1.0`, must not be stretched into evidence that
`pathaudit` or `permguard` is released. `ROADMAP.md`, `project-plan.md`,
`context.md`, `result-review.md`, `sprint-plan.md`, and `WHERE_AM_I.md` define
current direction and backlog. Where the roadmap still names a completed next
action, the newer run evidence and sprint state take precedence and the drift
must be recorded.

The existing `tests/test_permguard.py` interface is comparative evidence for
the suite’s proven test shape: temporary builds and fixtures, hostile-byte
escaping, a closed taxonomy oracle, deterministic output, sole-argument
informational options, and exact status assertions. It is not a template that
preselects another permission scanner, and this slice must not edit or extend
it. The `Makefile` supplies evidence about C17 strict warnings, temporary
binary ownership, pytest integration, formatting, static analysis,
ASan/UBSan, Valgrind, and the current sysdiff-only install/release boundary;
it must be inspected for incremental cost and dependency growth, not changed.

The existing smoke workflow—`tests/smoke_manifest.json`,
`tests/smoke_start.py`, `scripts/smoke.sh`, and
`tests/check_sysdiff_smoke.py`—must be traced end to end. Its `make test`
check reaches the full pytest suite transitively, but its pinned user-flow
identity remains sysdiff-centered; therefore it cannot be cited as direct
fourth-utility or even permguard-specific smoke. The latest sibling
Agent-Orch dashboard and `run.json` must confirm the active run and prevent
manual duplication of governed work. Candidate evidence must come from
read-only repository inspection; unsupported market, host, or portability
claims are grounds to defer, not guess.

## Hazard Taxonomy

Every candidate must be assessed against this closed taxonomy of exactly eight
hazard classes. No candidate may pass through an invented “miscellaneous”
bucket, and no class may be silently omitted:

1. **Hostile input:** untrusted bytes, malformed records, oversized values,
   adversarial environment variables, diagnostic escaping, resource bounds,
   partial output, and fail-closed behavior.
2. **Path handling:** empty and relative paths, symlinks, traversal,
   canonical-versus-lexical identity, races, special files, duplicate
   operands, and filesystem mutation risk.
3. **Permissions:** privilege assumptions, ownership policy, set-ID behavior,
   inaccessible inputs, safe fixture construction, and whether useful tests
   require root or host-specific capabilities.
4. **Portability:** ISO C17/POSIX/Linux boundaries, feature-test macros,
   libc/kernel/procfs differences, byte ordering, toolchain availability,
   and honest platform support.
5. **Dependency growth:** any new runtime library, interpreter, service,
   database, network client, build tool, or CI package beyond the justified
   existing quality floor.
6. **Overlap with existing utilities:** duplication of `sysdiff` explicit
   snapshot comparison, `pathaudit` PATH trust inspection, or `permguard`
   explicit-path mode-bit inspection.
7. **Maintenance burden:** source and state-space size, parser complexity,
   policy ambiguity, fixture stability, privilege-gated skips, performance
   bounds, documentation load, and long-term ownership.
8. **Accidental repetition of release or quality-polish work:** renewed
   `sysdiff` release/tag/package activity, a `pathaudit` or `permguard` polish
   cycle, or work whose main result is more tests, documentation, sanitizer,
   Valgrind, static-analysis, packaging, or backlog repair rather than a new
   utility capability.

For each class, the evaluation must record `clear`, `bounded with mitigation`,
or `disqualifying`, with repository evidence and a concrete consequence.
Any disqualifying result rejects the candidate. A bounded result must become a
first-slice constraint or later deferral, never an unpriced assumption.

## Exit Statuses and CLI Surface

This discovery slice changes no executable behavior, CLI surface, output
format, manual page, Make target, install membership, or exit status. It must
record the observed `permguard` behavior without changing it:
`permguard [--] PATH...`; sole-argument `permguard --help` and
`permguard --version`; status `0` for clean inspection or successful
informational output; status `1` for completed hazard findings without an
operational error; and status `2` for usage or operational failure, with
operational failure taking precedence in mixed runs. The observed closed
finding codes are `GROUP_WRITABLE`, `OTHER_WRITABLE`, `SET_USER_ID`, and
`SET_GROUP_ID`; final symlinks are status-2 rejections.

Those facts must be verified against the live permguard contract, focused test
interface, source or man page, and current handoff records. They serve only as
suite compatibility evidence. Candidate evaluation may sketch a prospective
CLI and status model solely inside the later mission-decision document, clearly
labeled proposed and bounded; it may not modify or claim delivery of that
surface. Any selected mission’s normative CLI, output grammar, taxonomy, and
error precedence belong to its later delivery contract and playbook.

## Non-Goals

This slice does not implement, compile, execute, smoke-test, package, install,
publish, tag, or release a fourth utility. It does not repair the current
permguard Medium findings, close older `pathaudit` or `sysdiff` findings,
expand any existing utility, alter AgentFlow state documents, or reinterpret
transitive `make test` coverage as a new user-flow oracle. Candidate selection
must not authorize networking, telemetry, a daemon, remediation, recursive
filesystem mutation, dependency installation, or a broad platform promise.

The later delivery phases are deliberately omitted because this discovery
slice changes no executable behavior: **TEST authoring** is omitted; **CODE**
is omitted; user-facing **DOCUMENT** work is omitted; and **TEST + FIX** is
omitted. The planning file produced by this slice is governed internal mission
evidence, not user-facing documentation. TEST authoring, CODE, user-facing
DOCUMENT work, and TEST + FIX belong in the later delivery playbook for the
selected mission, after its discovery decision passes independent review.
Existing tests, sources, manuals, Make recipes, and smoke files are read-only
evidence here.

## Acceptance Checks

Acceptance requires a reviewable decision ledger, not merely a candidate name.
The next evaluation document must:

1. Inventory each existing utility and label every material capability
   **shipped/released**, **implemented but unreleased**, **deferred**, or
   **still required**, citing tags, current roadmap/sprint records, contracts,
   tests, Makefile membership, smoke provenance, and the latest governed run.
   A tag proves only the artifact it actually names; a passing aggregate test
   does not prove a dedicated user flow.
2. Reconcile the stale roadmap instruction to bootstrap `permguard` with the
   reviewed bootstrap and current repair backlog, and keep backlog repair
   separate from fourth-utility discovery.
3. Evaluate at least two credible fourth-utility candidates plus honest
   deferral using every class in the closed hazard taxonomy. Each candidate
   must state operator problem, novelty, smallest useful slice, likely source
   and fixture surface, dependencies, portability boundary, and explicit
   overlap exclusions.
4. Demonstrate that the recommendation is not TEST authoring, CODE,
   user-facing DOCUMENT work, TEST + FIX, release repetition, or quality-only
   polish, and that no executable or governed smoke artifact changed.
5. Either commit one bounded fourth-utility mission with one purpose, proposed
   CLI boundary, closed first-slice behavior, explicit non-goals, evidence
   requirements, dependency ceiling, and handoff to a later delivery
   playbook; or defer honestly. A deferral must name precise unblock
   conditions, the evidence needed to satisfy each condition, who or what can
   supply it, and the next read-only evaluation action—never “research more”
   or an unbounded wait.
6. Pass structural validation that all six required headings exist exactly
   once with at least 120 non-whitespace characters beneath each, all eight
   hazard classes appear, and the only governed file written by this framing
   step is `plans/fourth-utility-mission-frame.md`.

