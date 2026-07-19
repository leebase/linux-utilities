# Release Roadmap

Version 0.1.0 establishes the stable explicit-snapshot `compare` surface,
format-1 output lines, man page, and `make quality` gate. Near-term release
hygiene for the governed tree is completing the root documentation set
(HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, STATUS) and keeping AgentFlow
memory aligned after review closeout—without expanding product scope. Keep the
public curated seed and private orchestration histories separate; tags and
GitHub releases should continue to point at curated public commits such as
`fbdf071` rather than private `main` tip. Any intentional change to diff
presentation, key grammar, limits, or exit semantics must version the contract
documents and changelog before shipping. Packaging (install targets, distro
packages) remains deferred until source-first distribution is no longer
sufficient. Do not schedule live capture, networking, or persistence into a
patch release of 0.1.x without a new approved decision record.

## Post-Release Ideas

- Optional reversible or structured changed-line encoding if consumers need to
  round-trip values that contain ` -> ` (would be a versioned format change).
- `make install` / packaging that installs `build/sysdiff` and `man/sysdiff.1`
  without pulling orchestration artifacts into packages.
- Broader CI matrix beyond Ubuntu when portability evidence justifies the cost;
  today the gate assumes Linux toolchains, and `/dev/full` write-error checks
  are conditional.
- Split `src/sysdiff.c` into separable parse/compare/output modules only after
  the single-file surface becomes hard to audit—not before. Preserve explicit
  `parse_snapshot` ownership transfer if modules are split.
- Optional live snapshot collectors as separate tools or subcommands, keeping
  comparison pure and fixture-testable.
- Mission-methodology extras (fuzzing harnesses, benchmarks) wired as optional
  Make targets once they have deterministic ownership and failure semantics.
- Additional small utilities in the suite, selected by the Future Mission
  Discovery criteria in the mission charter, without bloating `sysdiff` itself.
