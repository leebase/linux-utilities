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

## Sixth Utility Mission

The reviewed sixth planning commitment is exactly **Bootstrap `openunlink` explicit-process zero-link regular-file descriptor reporting**.
It has one purpose: for one explicit Linux PID, report open descriptors whose
followed targets are regular files with zero links, using `st_nlink == 0`
rather than trusting procfs display suffixes. Its first vertical slice is the closed
`--help` / `--version` / one-decimal-PID CLI, bounded numeric `/proc/PID/fd`
enumeration, repeated identity/type metadata checks, deterministic
`OPEN_UNLINKED` output, visible per-descriptor incompleteness advisories, a
section-1 manual, focused fixtures, strict C gates, dedicated smoke, and
independent review. All-process discovery, inode grouping, content access,
reclaim estimates, remediation, monitoring, installation, packaging, tagging,
publication, and release remain out of scope.

Run `787b9bb3d830` produced selection evidence only. Its independent verdict
is `pass` with no Critical or High findings; remaining Medium findings are
`SIXTH2-M1` (descriptor-cap behavior suppresses partial evidence),
`SIXTH2-M2` (nonzero-link unlink behavior on some filesystems is undisclosed),
and `SIXTH2-M3` (status 1 lacks a normative finding/advisory discriminator).
Remaining Lows are `SIXTH2-L1` (stderr-write semantics), `SIXTH2-L2`
(defensive `FD_SIZE_RANGE` reachability), and `SIXTH2-L3` (stale live-step
wording). Evidence is limited to the reviewed planning document, successful
byte-compilation of the three existing pytest modules, and sysdiff-centered
aggregate smoke reporting 351 passed / 18 skipped; no `openunlink` source,
tests, manual, build, quality run, dedicated smoke, installation, package, or
release exists.

Next executable action for `openunlink`: after the live
repair-before-expansion gate and prior mission sequencing are cleared under
independent review, generate a separate governed implementation playbook whose
first deliverable is a normative contract resolving `SIXTH2-M1` through
`SIXTH2-M3` before any code is accepted. Keep all six review findings visible
until a later review explicitly closes them.

## Next Utility Evaluation

Roadmap after reviewed Future Mission Discovery (plan
`plans/next-linux-utility-evaluation.md`; verdict `pass` with two Low
findings): pathaudit is at its v1 capability-completion boundary
(explicit-root, `--path`, `--command`, in-tree quality floor) and should
not grow near-duplicate detectors before suite breadth improves. Chosen
mission: bootstrap `permguard` as the third utility. That bootstrap is
now live under `docs/permguard-bootstrap-contract.md` as an
explicit-path permission scanner only—no recursion, no PATH mode, no
remediation, and no packaging/release claim for permguard or pathaudit.
`sysdiff` already has tag `v0.1.0`; do not renew release-candidate work
for it as the next mission. Recovery run `5035933ac7b4` closed Medium
PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512 under
`code-reviews/review-governed-run-ba6dc2fdd199.verdict.json` without
claiming failed origin `ba6dc2fdd199` passed. Remaining permguard notes
are Low PGR-TEST-706/PGR-PORT-707/PGR-BUILD-708/PGR-TEST-709/PGR-DOC-710
plus bootstrap Lows. Next executable action: generate a separate governed
`shebangcheck` implementation playbook beginning with its normative
contract. This roadmap does not claim installation, packaging,
publication, or a permguard release.

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
