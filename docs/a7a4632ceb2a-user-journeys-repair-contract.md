# Overview

This is the narrow repair contract for governed run `a7a4632ceb2a`. It defines
the manifest-only correction needed by the user-simulation validator: normalize
invalid journey authority metadata, retain the manifest's existing oracle
intent and utility-start command, and make the acceptance evidence explicitly
traceable. The repair is metadata work only and is not authorization to change
the utility, its interface, its tests, or its runtime behavior.

# Problem

The governed journey manifest may contain the invalid authority value
`maintainer`, even though the manifest schema supports `mission` for that
authority role. A validator also needs named, enumerated acceptance checks and
must be able to follow every required journey to one of them. Repairing only
the authority spelling would therefore be insufficient if goals, the existing
smoke command, or trace coverage were lost or silently reinterpreted.

# Constraints

Repair only the governed journey manifest metadata required by this contract
and the repository-owned contract record; do not add planning documents. Every
existing journey goal must remain verbatim, including these exact manifest
strings:

- `A user reads the repository-owned journey contract and confirms the manifest is a usable named oracle`
- `A user supplies malformed journey data and receives a specific fail-closed validation result`
- `A user runs the governed check from an unrelated current directory without changing path meaning`
- `A user observes that only the exact allowlisted smoke argv prefix is re-executed directly`
- `A user confirms that required journey authority is retained when the workspace is repaired`
- `A user follows every acceptance-check trace and sees exploratory coverage remain supplementary`
- `A user retries after producer-side narrowing and sees the pinned journey oracle reject tampering`
- `A user reviews a result that reports every journey with concrete steps commands and actionable evidence`
- `A user runs the existing deterministic smoke chain without confusing it with direct journey evidence`
- `A user confirms the workspace abstraction remains additive and does not create product release or network behavior`
- `An evaluator tries an unexpected working directory and a malformed workspace condition as exploratory coverage`

Preserve the exact `command_allowlist` entry `bash scripts/smoke.sh`, and make
no product behavior change: no source, build, runtime, CLI, smoke-script, or
release behavior may be modified.

# Acceptance Checks

The repair passes only when the checks below are all satisfied against the
repaired manifest and this contract. Each check is an explicit AC-N target for
`traces_to`; required journeys must point to these checks, while exploratory
coverage may remain supplementary. Evidence must be concrete enough to show
the resulting manifest rather than merely asserting that a repair was made.

- **AC-1** — The repository-owned contract is present, readable, and names
  governed run `a7a4632ceb2a`; the manifest remains a parseable named journey
  oracle rather than an opaque or unnamed test input.
- **AC-2** — Malformed journey data is rejected fail-closed with a specific
  validation result, and valid repaired JSON remains acceptable to the same
  schema-facing validator.
- **AC-3** — The governed check works from an unrelated current directory
  without changing the meaning of any repository-relative path it uses.
- **AC-4** — The manifest preserves the exact existing allowlist
  `command_allowlist: ["bash scripts/smoke.sh"]`; only that command starts the
  existing utility, and no replacement, wrapper, or extra prefix is introduced.
- **AC-5** — Every journey authority value exactly equal to `maintainer` is
  replaced by the schema-supported value `mission`; zero invalid `maintainer`
  values remain, and every existing journey goal listed in Constraints is
  still present without wording or intent changes.
- **AC-6** — Every non-exploratory journey has a nonempty `traces_to` array
  containing a defined AC-1 through AC-10 identifier, and the ten required
  journeys collectively cover AC-1 through AC-10. Exploratory journeys remain
  supplementary and cannot substitute for required coverage.
- **AC-7** — If a producer narrows or tampers with the manifest after repair,
  the pinned journey oracle detects that tampering and fails rather than
  accepting an untraceable or authority-invalid manifest.
- **AC-8** — A recorded result reports every journey with concrete steps,
  commands, and actionable evidence, including the authority and acceptance
  trace facts needed to audit this repair.
- **AC-9** — The preserved deterministic smoke chain can still be run through
  `bash scripts/smoke.sh`, and its output is kept distinct from direct journey
  evidence and trace coverage.
- **AC-10** — The repaired workspace abstraction remains additive: the repair
  changes no product source, executable behavior, CLI contract, release
  artifact, network behavior, or other runtime semantics.
