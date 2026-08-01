# Objective

Select exactly one fifth-utility mission for the `linux-utilities` suite through
read-only, repository-grounded discovery. The decision must add a distinct,
practically useful operator capability after `sysdiff`, `pathaudit`,
`permguard`, and the already selected but not necessarily delivered
`inodealias` fourth mission. Selection is a planning commitment for a later
governed implementation playbook, not evidence that a fifth utility exists.
The chosen mission must be suitable for one intentionally small, auditable
ISO C17 command-line program; permit a bounded, fixture-testable first vertical
slice; and preserve the suite's rejection of hidden behavior, telemetry,
network dependence, daemons, and dependency sprawl.

The evaluator must first reconcile current state rather than infer it from
utility numbering. In particular, it must determine from live evidence whether
the fourth-utility decision in `plans/fourth-utility-mission-evaluation.md` has
been implemented, reviewed, released, superseded, or remains planning only.
The fifth mission must remain novel under every observed state and must not
consume repair, release, or quality-polish work that belongs to an existing
utility.

# Selection Contract

Evidence must be reproducible and grounded in the repository. At minimum, the
evaluation must inspect `product-definition.md`, `project-plan.md`,
`architecture.md`, `ROADMAP.md`, `STATUS.md`, `WHERE_AM_I.md`, `context.md`,
`sprint-plan.md`, `result-review.md`, `HISTORY.md`, `DECISIONS.md`,
`plans/fourth-utility-mission-frame.md`,
`plans/fourth-utility-mission-evaluation.md`, the live contracts under
`docs/`, source and test inventories, the `Makefile`, smoke provenance,
review verdicts, repository tags, and the latest sibling Agent-Orch run and
dashboard. Each material claim must separate the observed fact, its file or
read-only command source, its observation date, and the bounded inference.
Historical text may explain a decision but cannot override newer live state.

Compare multiple genuinely distinct candidates using the same criteria:
practical operator value; one-purpose clarity; novelty relative to every
existing, selected, or actively governed utility; bounded hostile-input and
resource behavior; fixture determinism; implementation and ownership
simplicity; Linux/POSIX and ISO C17 fit; portability limits; security and
read-only posture; dependency cost; maintenance burden; and the size of the
smallest useful vertical slice. Ratings must use an explicit common scale,
cite repository evidence, explain tradeoffs, and expose any uncertainty. A
candidate cannot win merely because it resembles an existing test harness or
can reuse existing polish gates.

The final recommendation must use one fixed format: mission name; operator
problem; repository-evidence summary; side-by-side comparison result; reason
the winner defeats every alternative; bounded first vertical slice expressed
as capabilities and limits; dependency ceiling; explicit non-goals; required
later evidence; and handoff to a separately governed implementation playbook.
It must contain exactly one recommended mission, not a ranked tie, bundle, or
menu. This selection contract does not define the selected utility's
normative command line or numeric behavior: **the CLI surface and exit statuses
will be defined by the later implementation playbook after a mission is
selected**.

# Selection Hazards

Every candidate must be classified against this closed taxonomy of exactly
eight selection hazards. The evaluation may describe concrete manifestations
inside a class, but it must not add a ninth, miscellaneous, or catch-all
class. For each class, record `clear`, `bounded with an explicit mitigation`,
or `disqualifying`, with cited evidence and a consequence. A disqualifying
rating rejects the candidate; a bounded rating must become a first-slice
limit or an explicit later deferral.

1. **Duplication of existing utilities:** repeats `sysdiff` snapshot
   comparison, `pathaudit` PATH trust analysis, `permguard` explicit-path
   mode-bit inspection, or the selected/active `inodealias` filesystem
   identity mission, including equivalent behavior under a different name.
2. **Duplicate quality-polish work:** primarily repeats tests, documentation,
   smoke, compiler warnings, formatting, static analysis, sanitizers,
   Valgrind, performance, packaging, or backlog repair already owned by an
   existing mission instead of creating a distinct operator capability.
3. **Release-process drift:** renews or substitutes tagging, publication,
   install, archive, package, release-candidate, or release-review work for
   mission selection, or treats a tag or transitive smoke result as evidence
   for an artifact or user flow it does not cover.
4. **Excessive scope:** requires several utilities, recursion, broad policy
   engines, complex language parsing, unbounded discovery, persistent state,
   platform matrices, or a first slice too large for one engineer to audit
   end to end.
5. **Unsuitable dependencies:** needs new runtime libraries, interpreters,
   databases, privileged helpers, nonstandard build systems, or additional
   infrastructure whose value and ownership are disproportionate to a small
   C utility.
6. **Background or network services:** requires a daemon, scheduler, watcher,
   server, client network access, remote API, telemetry, packet exchange, or
   hidden continuing activity to deliver its first useful result.
7. **Weak practical value:** lacks a concrete recurring Linux operator or
   developer problem, merely republishes readily available information, has
   an ambiguous success boundary, or cannot justify the cost of another
   maintained executable.
8. **Does not fit a small auditable C utility:** depends on GUI or large
   framework behavior, demands a complex evolving parser or policy model,
   cannot be deterministically fixture-tested, has unclear memory/resource
   ownership, or cannot be honestly bounded in ISO C17 plus narrowly justified
   Linux/POSIX interfaces.

# Acceptance Checks

The discovery result is acceptable only if it inventories the live status of
all existing and selected utilities and evaluates at least three distinct,
credible fifth-utility candidates. Each candidate must name its operator
problem, smallest useful capability, expected input and fixture shape,
dependency and portability boundary, overlap exclusions, and all eight closed
hazard ratings. Candidate evidence must cite repository files, tags, review
records, source/test/build surfaces, and the latest governed-run state where
relevant; unsupported recollection or generic market claims do not satisfy the
evidence requirement.

The comparison must be transparent: use one shared criteria matrix and rating
scale, show evidence and reasoning for every rating, identify all
disqualifiers and mitigations, and explain why differences affect selection.
The result must contain **exactly one recommendation** in the format required
by the Selection Contract. It may not disguise multiple missions as phases of
one recommendation. The winner must have no unresolved disqualifying hazard
and must be demonstrably distinct from existing utilities, existing repair or
polish work, release processes, and the fourth-utility mission.

The recommendation must define one bounded first vertical slice with a single
operator outcome, explicit input boundary, closed capability boundary,
resource and dependency ceilings, fixture strategy, review evidence, and
deferred behaviors. It must not prescribe a normative CLI grammar, output
grammar, or numeric exit-status contract; those belong to the later
implementation playbook after selection. Structural review must confirm that
all five required headings occur exactly once, each has at least 120
non-whitespace characters, every hazard class appears, and this discovery
slice writes only within `plans/`.

# Non-Goals

This is a mission-selection contract, not an implementation contract. It does
not create or modify C source, tests, fixtures, manuals, Make recipes, smoke
artifacts, release artifacts, tags, packages, installed files, or executable
behavior. It does not compile, format, analyze, benchmark, run coverage,
sanitize, use Valgrind, or otherwise produce build or test outputs. It neither
implements the fourth-utility `inodealias` decision nor assumes that decision
has shipped; live evidence must establish its status before fifth-mission
comparison.

The slice does not repair `permguard` Medium findings, older `pathaudit` or
`sysdiff` findings, or any future `inodealias` findings. It does not expand an
existing utility, repeat release readiness, authorize publication, add
installation or packaging, install dependencies, access the network, launch a
background service, mutate inspected system state, or claim dedicated smoke
coverage from aggregate transitive tests. It does not settle the selected
utility's command syntax, output bytes, finding taxonomy, diagnostics,
resource constants, signal behavior, or exit codes. Specifically, **a CLI
surface and exit statuses will be defined by the later implementation
playbook after a mission is selected**, along with normative tests, code,
documentation, quality-gate execution, smoke evidence, and independent
review.
