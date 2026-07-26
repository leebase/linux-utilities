# Next Linux Utility Evaluation (after pathaudit)

Evaluation date: 2026-07-26. Scope: Future Mission Discovery against the
`linux-utilities` mission charter. Evidence sources: AgentFlow handoff docs,
`docs/pathaudit-contract.md`, `tests/test_pathaudit.py`, `Makefile`, root
QUALITY/TESTING/STATUS/HISTORY, release tag `v0.1.0` (`git tag -l`), and the
anti-drift rule in the mission charter. This plan is discovery only; it does
not implement code, run builds, or claim a `pathaudit` or renewed `sysdiff`
release.

## Pathaudit Completion Boundary

`pathaudit` is declared **capability-complete for v1 product scope** once the
following shipped surfaces remain in force, without requiring further detector
expansion before Future Mission Discovery may start a new utility:

1. Explicit-root mode: `pathaudit [--] ROOT...` with the closed directory
   taxonomy (`EMPTY_ROOT`, `RELATIVE_ROOT`, `MISSING_ROOT`,
   `NON_DIRECTORY_ROOT`, `GROUP_WRITABLE`, `WORLD_WRITABLE`), reject-closed
   limits, and exit statuses 0/1/2.
2. Opt-in `pathaudit --path`: process `PATH` colon split retaining empty and
   duplicate components; cwd-dependent labeling; non-directory components;
   top-level executable shadowing (`SHADOWED`); writable final executables;
   `UNSAFE_OWNER` on executables; `UNSAFE_OWNER` on usable PATH directories and
   their realpath ancestors through `/` with shared-ancestor dedup (run
   `50c0b4936d50`).
3. Exclusive `pathaudit --command NAME`: PATH-order `MATCH` lines plus
   plant-risk-before-winner shared taxonomy including the same executable and
   directory ownership trust model.
4. Quality floor already present in-tree: `tests/test_pathaudit.py`,
   `man/pathaudit.1`, README/SECURITY/contract docs, Makefile
   `pathaudit-sanitize` / `pathaudit-valgrind`, and inclusion of `pathaudit` in
   `make quality` (GCC/Clang strict, format, tidy, cppcheck, analyzer,
   ASan/UBSan/Valgrind). Do **not** schedule another polish cycle whose only
   purpose is tests, docs, sanitizers, Valgrind, or packaging—those dimensions
   already have active coverage.

**Explicitly out of scope for pathaudit v1 capability** (deferred or rejected,
not blockers for starting the next utility):

- Detect writable ancestors of PATH directories: policy-ambiguous for self-owned
  `$HOME`, sticky `/tmp`, vendor `/opt` trees, and symlink lexical-vs-realpath
  chains; treated as enhancement, not a completion gate.
- Privilege-changing mode bits (`setuid`/`setgid`) on PATH executables: crisp,
  but better as a separate permission-analysis utility than further growth of
  `src/pathaudit.c` (~1849 lines already).
- Machine-readable output modes, nested-directory recursion, ACL/capability/
  mount-option analysis, install targets, and a `pathaudit` release tag.

**Maintenance remains allowed** without reopening discovery: optional repair of
Medium `pathaudit-shadow-1` and visible Low findings
(`path-dir-ownership-1`, PA-W1/PA-W2, shadow-2/3, nondir, cmd, wdp, PA-WP,
bootstrap leftovers). Those are ordinary repair items, not new missions.

**Release note:** `sysdiff` already has tag `v0.1.0`; do not propose renewed
release-candidate, tag, or publication work for it. `pathaudit` is **not**
released; a future pathaudit release gate is separate from this boundary and
must not block bootstrapping the next utility. This boundary does **not** claim
pathaudit is released or that `tests/smoke_manifest.json` covers pathaudit.

## Evaluation Criteria

Candidates for the next mission are scored against the charter’s Mission
Selection Criteria and Project Constraints, adapted to concrete suite context:

- **Practical usefulness:** Would a Linux admin or developer keep the tool
  installed and run it without ceremony? Prefer problems operators already
  diagnose by hand with ad-hoc `stat`/`find`/`ss` rituals.
- **Simplicity / elegance:** One executable, one purpose, small auditable C17
  surface; reject platforms, daemons, and “policy engines.”
- **Maintainability:** Fixture-testable contracts, clear ownership, no hidden
  runtime; a single engineer can hold the whole program in mind.
- **Security value:** Prefer read-only inspection that surfaces real trust or
  exposure hazards; assume hostile paths/env; fail closed.
- **Technical risk:** Penalize shell-language parsing, network services, GUI
  toolkits, and ambiguous hazard/ok boundaries that invite false positives.
- **Novelty (within this suite):** Must not duplicate `sysdiff` (explicit
  snapshot compare) or deepen another pathaudit detector dimension. Must not
  be duplicate polish (tests/docs/sanitizer/Valgrind/packaging) or renewed
  `sysdiff` release work—tag `v0.1.0` already exists.
- **Fit with portable C:** ISO C17 + Linux/POSIX metadata (`stat`,
  `/proc` reads) only; no new runtime dependencies, networking clients,
  telemetry, or SQLite unless persistence is essential (it is not for v1
  slices considered here).

**Disqualifiers:** Expanding `pathaudit` with near-duplicate ancestor/
writability variants; quality-only slices when an active item already covers
that dimension; any `sysdiff` release-process item; tools that require
background services or non-C stacks to deliver the first useful slice.

Scoring below uses qualitative High / Medium / Low per factor, then a short
verdict. Breadth of capability across utilities beats further depth on
pathaudit.

## Candidate Assessments

### Candidate A — `permguard` (explicit-path permission auditor)

A small read-only scanner that classifies **operator-supplied filesystem
paths** (not process `PATH`) for permission and ownership hazards: group/other
writability, untrusted final-target ownership (UID 0 or invoking `getuid()`
only), and privilege-changing mode bits (`setuid`/`setgid`) on regular files,
plus sticky bit reporting on directories when present. Explicit roots only for
the first slice; no live PATH read, no remediation, no recursion.

| Factor | Rating | Notes |
| --- | --- | --- |
| Usefulness | High | Admins already `stat` trees before sharing or deploying; closes the setuid gap pathaudit deferred. |
| Simplicity | High | One CLI form, closed taxonomy, `stat(2)`-shaped pipeline like pathaudit’s explicit-root mode. |
| Maintainability | High | Fixture trees with `chmod`/`chown`-skip patterns already proven in `tests/test_pathaudit.py`. |
| Security value | High | Surfaces plantable or privilege-escalating mode bits on arbitrary trusted paths. |
| Technical risk | Low–Medium | Taxonomy must stay narrow; no ACL/xattr in v1. |
| Novelty | High | New binary and purpose; does not deepen pathaudit’s PATH detectors. |
| Portable C | High | Pure metadata inspection; no libraries beyond libc. |

**Verdict:** Strongest charter fit. Complements pathaudit without growing
`pathaudit.c`. Seed name appears in Future Mission Discovery.

### Candidate B — `portwatch` (local listening-socket reporter)

Read `/proc/net/tcp{,6}` and `/proc/net/udp{,6}` (and optionally Unix sockets)
to emit a deterministic table of local listeners: address, port, inode, and
optional owning PID via `/proc/*/fd` reverse map. No packets are sent.

| Factor | Rating | Notes |
| --- | --- | --- |
| Usefulness | Medium–High | Useful on minimal hosts, but overlaps `ss`/`netstat` mindshare. |
| Simplicity | Medium | Proc parsers, IPv6, endian, and namespace edge cases inflate surface. |
| Maintainability | Medium | Golden fixtures need captured proc snapshots; host variance is real. |
| Security value | Medium | Inventory aids hardening reviews; not itself a hazard classifier. |
| Technical risk | High | Easy to under-specify; PID mapping races; container vs host views. |
| Novelty | Medium | New utility, but crowded Unix niche. |
| Portable C | Medium | Linux `/proc`-specific; acceptable for this suite, less “portable C.” |

**Verdict:** Viable later mission; higher technical risk than `permguard` for
the first post-pathaudit vertical slice.

### Candidate C — `dotdoctor` (shell startup hazard checker)

Inspect common dotfiles (`.profile`, `.bashrc`, `.zshrc`, and friends) under
`$HOME` or explicit paths for world-writable files, unsafe relative `PATH`
mutations, and other startup hazards.

| Factor | Rating | Notes |
| --- | --- | --- |
| Usefulness | Medium | Developers hit these bugs, but frequency is lower than permission audits. |
| Simplicity | Low–Medium | “Parse enough shell” is a swamp; incomplete parsers lie. |
| Maintainability | Low | Shell dialect matrix and false positives damage trust. |
| Security value | Medium | Writable dotfiles are real; PATH-mutation checks partly overlap pathaudit. |
| Technical risk | High | Scope creep into a mini-shell analyzer. |
| Novelty | Medium | Seed idea; distinct product only if parsing stays non-goals. |
| Portable C | Medium | File/`stat` parts are fine; content heuristics are the risk. |

**Verdict:** Reject for next mission unless reduced to **metadata-only**
dotfile permission checks—which then collapses into `permguard`.

### Summary comparison

`permguard` wins on usefulness × simplicity × security × portable C with the
lowest honest risk. `portwatch` is the best runner-up once proc-snapshot
fixtures exist. `dotdoctor` is deferred until a non-parsing contract is
written. None of these recommendations are polish or `sysdiff` release work.

## Recommended Mission

**Recommended mission: bootstrap `permguard` as the third suite utility.**

`permguard` is a single-purpose ISO C17 command-line permission and ownership
auditor for **explicit filesystem paths**. It exists so operators can ask “are
these files and directories safe to trust?” without reading process `PATH` and
without expanding `pathaudit` further. The mission satisfies charter selection
factors: high practical usefulness for admins and developers, elegance via one
executable and a closed hazard taxonomy, novelty inside this repository
(new binary beside `sysdiff` and `pathaudit`), strong maintainability through
fixture-backed `stat` contracts already proven by pathaudit tests, clear
security value (writability, foreign ownership, setuid/setgid), bounded
technical risk if recursion/ACLs stay out of the first slice, and excellent
fit with portable C17 and Make quality gates already in the tree.

**Why not continue pathaudit instead:** ownership ancestors already shipped;
writable-ancestor detection is policy-muddy; `src/pathaudit.c` is already
large for “easily understood by a single engineer”; the charter’s anti-drift
rule prefers breadth of utilities over another near-duplicate detector.
**Why not `portwatch` or `dotdoctor` first:** higher specification and false-
positive risk before a smaller permission auditor lands. **Why not polish or
release work:** tests, docs, sanitizer/Valgrind, and packaging dimensions are
already covered for the suite; `sysdiff` tag `v0.1.0` exists—do not renew
release process for it; pathaudit release remains a later, separate gate.

Success for this mission means a reviewed vertical slice that builds under the
existing strict C flags, has a contract and pytest module, and never remediates
the filesystem—report only.

## First Vertical Slice

**Name:** `permguard` explicit-root permission scanner (v0.1.0 vertical slice).

**Smallest useful behavior:**

- CLI: `permguard [--] PATH...` with `--help` / `--version`; no other modes.
- For each operand, perform a `stat`-equivalent lookup of the final target
  (symlink-following like pathaudit). Emit zero or more findings from a closed
  taxonomy, for example: `MISSING`, `GROUP_WRITABLE`, `WORLD_WRITABLE`,
  `UNSAFE_OWNER` (final `st_uid` neither 0 nor `getuid()`), `SETUID`,
  `SETGID`, and `STICKY` (directories only). Owner-only writable private files
  stay silent.
- Deterministic bytewise ordering and quote-escaping aligned with suite
  conventions; exit `0` (clean), `1` (hazards found), `2` (usage / limits /
  inspection errors). Reject-closed resource limits analogous to pathaudit.
- **Non-goals for this slice:** no directory tree walk, no process `PATH`
  reading, no ACL/xattr/capability/mount analysis, no remediation, no install
  target, no claim that `permguard` is released, no changes to `sysdiff` or
  `pathaudit` behavior.

**Deliverables:** `docs/permguard-contract.md`, `src/permguard.c`,
`man/permguard.1`, `tests/test_permguard.py`, Makefile wiring into existing
strict/syntax/static/sanitizer/Valgrind/`test-suite` surfaces without breaking
sysdiff/pathaudit gates, plus README/CHANGELOG mentions that do not claim
release.

**Concrete acceptance evidence (must all hold):**

1. Contract tests build a temp tree and pin: private file silent; group- and
   world-writable files emit exact codes; foreign-owned file emits
   `UNSAFE_OWNER` (honest skip if host cannot `chown`); setuid/setgid regular
   files emit `SETUID`/`SETGID`; sticky directory emits `STICKY`; missing path
   emits `MISSING`; symlink-to-writable reports the final target; explicit
   ordering and escaping goldens; usage/`--help`/`--version` statuses.
2. `clang`/`gcc` `-std=c17 -Wall -Wextra -Wpedantic -Werror` clean on
   `src/permguard.c`; cppcheck and format-check clean for the new sources.
3. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
   remains green with the new module included (no regressions to sysdiff or
   pathaudit counts beyond additive tests).
4. ASan (leak-fatal) and Valgrind help or contract probes for `permguard` exit
   0 when wired like pathaudit’s mktemp gates.
5. Independent review verdict `pass` with no Critical/High findings against the
   contract and C ownership/UB rules; Medium findings tracked as repair, not
   silent scope expansion.

**Completion of this slice** means the suite has three small utilities with
`permguard` capability-bootstrapped; it does **not** mean `permguard` is
released, packaged as `.deb`/`.rpm`, or covered by the existing sysdiff smoke
oracle unless a later playbook explicitly extends smoke.
