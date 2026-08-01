# Seventh Utility Mission Frame

> **SUPERSEDED — not normative.** This frame is a superseded planning artifact
> retained only as provenance from an earlier failed framing attempt. It is
> **not** authority for evaluating, scoring, accepting, or implementing a
> seventh utility. Recovery of failed governed run `f7539c314ca1` and recovery
> run `4824cd763b27` both treat
> `plans/seventh-utility-mission-contract.md` as the sole live FRAME/recovery
> contract. Do not use the historical body below to supply, replace, or
> reinterpret current acceptance checks, hazard ratings, criteria names, or
> qualification gates. Any conflict with the live contract is resolved in
> favor of the live contract.

## Mission Scope

This FRAME artifact defines the research boundary for selecting exactly one
seventh small Linux utility mission for the `linux-utilities` suite. The
selection must add one practically useful operator or developer capability
that fits the Unix model of a small, one-shot, composable program. It is a
planning commitment for a later governed delivery playbook, not evidence that
the utility exists. If no credible candidate clears every hard gate below, the
only acceptable alternative is an evidence-backed deferral with explicit
unblock conditions; the evaluation must not choose a weak mission merely to
fill the seventh position.

Numbering does not imply implementation status. The evaluation must reconcile
the live tree and governed evidence before comparing candidates. It must treat
`sysdiff`, `pathaudit`, and `permguard` as implemented capabilities with their
actual release boundaries, and it must reserve the planning-only missions
already selected for `inodealias`, `shebangcheck`, and `openunlink` whether or
not any is implemented by the time evaluation occurs. A seventh mission must
remain novel after all six earlier missions are hypothetically delivered.

The intended result is one narrow mission name, one user problem, and one
smallest useful first vertical slice. That slice must be read-only, bounded,
deterministic, fixture-testable without special privileges, suitable for an
intentionally small ISO C17 implementation, and honest about any Linux-specific
interfaces. Preference belongs to explicit caller-selected inputs and
deterministic text results that compose with shell pipelines. Background
operation, implicit discovery, mutation, and policy engines are outside the
selection boundary.

Explicit non-goals are implementation, backlog repair, product expansion,
quality polishing, installation, packaging, tagging, publication, and release.
This research does not alter an existing utility, implement any previously
selected mission, close any review finding, install a dependency, run a
service, or create product evidence. It does not claim that aggregate
`make test` or the sysdiff-centered smoke flow directly exercises a future
seventh utility.

The CLI surface and exit statuses are intentionally deferred because this
slice selects a mission rather than implementing a utility. Command grammar,
output bytes, finding and diagnostic codes, resource constants, signal
behavior, and numeric status meanings belong to a later normative contract and
separately governed implementation playbook. A mission evaluation may describe
an input class and user-visible outcome only at the capability level; it must
not turn those descriptions into a premature behavioral contract.

Phase omissions are explicit: **TEST**, **CODE**, **DOCUMENT**, and
**TEST + FIX** are omitted because this research slice must not change source,
tests, build files, man pages, or user-facing product documentation. It also
must not change smoke artifacts, binaries, generated packages, or AgentFlow
handoff files. Internal selection evidence may be written only beneath
`plans/`.

## Evaluation Criteria

Every candidate must first pass the Closed Hazard Taxonomy. Candidates that
remain eligible are compared with one shared, evidence-cited matrix. Each
criterion receives an integer score from 0 through 4: `0` means absent or
contradicted, `1` weak, `2` materially limited, `3` strong with a bounded
tradeoff, and `4` strong with direct evidence and no material first-slice
qualification. Scores must be explained; arithmetic without evidence is not a
decision.

| Criterion | Weight | What earns a strong score |
| --- | ---: | --- |
| Practical usefulness | 5 | Solves a concrete, recurring Linux operator or developer problem and gives a result that supports an immediate decision, without overstating what was inspected. |
| Novel capability | 5 | Remains distinct from all implemented and reserved missions, even if `inodealias`, `shebangcheck`, and `openunlink` are later delivered. |
| Smallest useful slice | 5 | One bounded outcome is useful on its own and can be audited end to end without bundling later phases or a second utility. |
| Security and privilege posture | 5 | Read-only, non-root baseline behavior; explicit authority boundaries; bounded hostile inputs; no process control, privilege transition, or unsafe implicit trust. |
| Unix fit and composability | 4 | One-shot execution, explicit or tightly bounded input, deterministic text reporting, meaningful pipeline use, and no daemon, GUI, network, or hidden state. |
| Deterministic testability | 4 | Core positive, negative, boundary, and race/error seams can be exercised with ordinary temporary fixtures on an unprivileged Linux host. |
| C auditability and ownership | 4 | A small ISO C17 program with simple resource ownership, closed limits, modest parsing, and narrowly justified POSIX/Linux calls is credible. |
| Dependency economy | 4 | libc is the runtime ceiling; no external command orchestration, third-party library, interpreter, database, plugin, or new service is needed. |
| Portability honesty | 3 | Linux, POSIX, libc, filesystem, and kernel-version assumptions can be stated precisely without a false cross-platform promise. |
| Maintenance burden | 3 | Taxonomy and policy remain closed, fixtures stable, documentation finite, performance bounded, and future feature pressure resistible. |

The maximum weighted score is 168. Selection requires at least 126 points,
scores of at least `3` for Practical usefulness, Novel capability, Smallest
useful slice, and Security and privilege posture, plus no disqualifying hazard.
The matrix is comparative rather than self-certifying: the winner must also
defeat every alternative in prose. Ties are resolved, in order, by the higher
Practical usefulness score, then lower privilege exposure, then smaller
dependency surface, then smaller first-slice state space. If candidates remain
tied, the evaluation must defer instead of making an arbitrary choice.

Practical usefulness must be supported by an identifiable task and a bounded
user decision, not by generic claims that “administrators may want this.”
Unix fit requires more than having a command line: the candidate should accept
explicit operands or one tightly scoped Linux data source, perform finite
read-only work, emit deterministic terminal-safe text, avoid interactive
prompts, and combine cleanly with shell redirection and pipelines. Merely
reformatting information already exposed by an earlier suite utility, or
wrapping a common command without adding a safer bounded interpretation, earns
no novelty credit.

Evidence must separate observed fact, source, observation date, inference, and
uncertainty. At minimum it must cover current source/test/manual/build
inventories, earlier mission decisions and review verdicts, current roadmap
and sprint state, smoke provenance, repository tags where relevant, and the
latest sibling Agent-Orch run/dashboard. Historical claims cannot override
newer live evidence. Any external technical claim used later must come from an
authoritative Linux, POSIX, libc, or filesystem source and be labeled when it
is an inference; unsupported popularity or market claims receive no score.

## Closed Hazard Taxonomy

Every candidate must be evaluated against exactly the following ten selection
hazards. The permitted ratings are `clear`, `bounded with explicit
mitigation`, and `disqualifying`. A bounded rating must become a stated
first-slice limit or a named later deferral. Any disqualifying rating rejects
the candidate regardless of its weighted score. The evaluation may describe
specific manifestations within these classes, but it may not add a
miscellaneous or eleventh class.

1. **Duplicate implemented capability.** Reject behavior that repeats
   `sysdiff` explicit snapshot comparison, `pathaudit` PATH trust and command
   resolution analysis, or `permguard` explicit-path mode-bit reporting under
   another name or input spelling.
2. **Duplicate reserved mission.** Reject explicit-path filesystem identity or
   hard-link grouping reserved for `inodealias`, direct-interpreter shebang
   preflight reserved for `shebangcheck`, and explicit-process zero-link
   regular-file descriptor reporting reserved for `openunlink`. A candidate
   must remain distinct even while those missions are planning-only.
3. **Duplicate polish, repair, or release work.** Reject missions whose main
   result is more tests, fixtures, docs, man pages, compiler gates, formatting,
   static analysis, sanitizers, Valgrind, benchmarks, smoke, packaging,
   installation, publication, backlog repair, or another feature of an
   existing utility rather than a new executable capability.
4. **Weak practical value or Unix fit.** Reject speculative problems,
   information dumps without a concrete decision, non-composable interactive
   workflows, trivial wrappers, or candidates whose smallest honest slice is
   not independently useful.
5. **Excessive scope or maintenance pressure.** Reject broad policy engines,
   recursive whole-system discovery, several bundled modes, complex or
   evolving languages, unbounded input, persistent catalogs, and missions
   whose useful behavior cannot remain small and closed.
6. **Hostile-input and security exposure.** Reject candidates that cannot
   bound attacker-controlled bytes, counts, paths, records, or kernel data;
   escape output safely; define partial-output behavior later; avoid execution
   of inspected content; and state race/TOCTOU limits without claiming
   authorization or safety they did not establish.
7. **Privilege and side-effect hazard.** Reject a baseline that needs root,
   set-ID installation, Linux capabilities, `ptrace`, process signaling,
   namespace changes, mounting, device writes, permission changes, or other
   mutation. Core positive fixtures must run unprivileged; privilege-gated
   supplemental evidence cannot substitute for the useful path.
8. **Dependency or service growth.** Reject any first slice requiring a
   runtime dependency beyond libc, external command orchestration, a language
   runtime, database, network access, remote API, daemon, watcher, scheduler,
   telemetry, plugin framework, or disproportionate new build/CI machinery.
9. **Portability and ABI hazard.** Reject candidates whose Linux/kernel/libc
   boundary cannot be specified and tested honestly. Bounded candidates must
   use platform headers and correct feature-test macros, preserve native type
   widths, avoid hand-declared system interfaces, and state filesystem,
   procfs/sysfs, namespace, architecture, or kernel-version limitations.
10. **Non-deterministic or privilege-fragile evidence.** Reject a mission whose
    essential result cannot be covered by stable temporary fixtures or a
    narrow test seam, whose ordinary test outcome depends on host timing or
    global state, or whose core positive cases would routinely skip for lack
    of privilege, kernel configuration, or uncommon hardware.

Security constraints across all non-rejected candidates are read-only
operation, no execution of content-derived paths, no ambient privilege
assumption, finite resource ceilings, terminal-safe rendering of untrusted
bytes, explicit race disclaimers, and no remediation advice presented as a
proven safe action. Portability constraints are an ISO C17 implementation
base, standard declarations from platform headers, narrowly justified
POSIX/Linux interfaces, locale-independent result ordering where ordering
matters, and an explicit Linux-only boundary whenever procfs, sysfs, or other
kernel ABI data is essential.

## Acceptance Checks

The FRAME is satisfied only when the later evaluation produces a reproducible
decision that meets all of the following objective checks:

1. It inventories `sysdiff`, `pathaudit`, `permguard`, `inodealias`,
   `shebangcheck`, and `openunlink`, labeling each capability as implemented,
   released, planning-only, failed/incomplete, or superseded from current
   evidence rather than utility number or historical wording.
2. It evaluates at least four credible, genuinely distinct seventh-utility
   candidates plus an honest-deferral baseline. At least three candidates must
   survive initial duplicate screening; straw candidates included only to be
   rejected do not count.
3. For every candidate, it states one operator problem, one smallest useful
   outcome, the bounded input/data source, expected fixture shape, dependency
   ceiling, privilege posture, Linux/portability boundary, maintenance limit,
   and explicit overlap exclusions.
4. It supplies an evidence ledger separating fact, source or read-only
   command, date, inference, and uncertainty, including the latest sibling
   governed run and the distinction between aggregate regression evidence and
   dedicated user-flow smoke.
5. It completes all ten hazard ratings for every candidate using only the
   three allowed rating phrases. Every bounded hazard maps to a first-slice
   constraint or named deferral; any disqualifying hazard removes that
   candidate before scoring.
6. It completes every weighted criterion for every eligible candidate, shows
   the arithmetic against the 168-point maximum, applies the 126-point and
   four hard-minimum gates, and follows the stated tie-break order.
7. It recommends exactly one seventh mission and explains why it defeats each
   alternative. If none qualifies, it records an honest deferral with specific
   failed gates, evidence needed to clear them, and the next bounded read-only
   action; it must not lower the gates after seeing the scores.
8. The recommendation contains one stable mission title, one purpose, a
   capability-level first vertical slice, practical usefulness boundary,
   read-only/security posture, dependency and privilege ceilings, portability
   statement, explicit non-goals, later evidence requirements, and handoff to
   a separate governed implementation playbook.
9. The recommendation explicitly says that CLI surface and exit statuses are
   deferred to the later normative implementation contract. It does not define
   command grammar, output grammar, numeric statuses, signal semantics, or
   runtime taxonomy in this research slice.
10. The evaluation explicitly records that **TEST**, **CODE**, **DOCUMENT**,
    and **TEST + FIX** are omitted because the research slice must not change
    source, tests, build files, man pages, or user-facing product
    documentation. It makes no implementation, build, test, smoke, package,
    installation, publication, or release claim for the selected mission.
11. Structural validation finds the headings `Mission Scope`, `Evaluation
    Criteria`, `Closed Hazard Taxonomy`, and `Acceptance Checks` exactly once,
    with at least 120 non-whitespace characters under each heading.
12. Step-scope validation finds no write outside `plans/`; for this framing
    step, the sole governed output is
    `plans/seventh-utility-mission-frame.md`.
