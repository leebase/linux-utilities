# Current Status

The suite now contains two established small C utilities plus a reviewed
third-utility bootstrap. `sysdiff` 0.1.0 implements
explicit snapshot comparison in C17: users run
`sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT` (plus `--help` / `--version`)
against plain-text format-1 files. The command validates keys, duplicates, NULs,
and resource limits; emits deterministic `+` / `-` / `~` lines or `no changes`;
escapes untrusted display bytes; and returns exit statuses 0, 1, or 2 as
documented in the man page and README. Governed run `4dec475ef201` added
additive `pathaudit` 0.1.0: a read-only ISO C17 scanner for explicitly supplied
PATH directory roots (`pathaudit [--] ROOT...`), with closed hazard taxonomy
(`EMPTY_ROOT`, `RELATIVE_ROOT`, `MISSING_ROOT`, `NON_DIRECTORY_ROOT`,
`GROUP_WRITABLE`, `WORLD_WRITABLE`), reject-closed limits, and exit statuses
0/1/2 per `docs/pathaudit-contract.md` and `man/pathaudit.1`. Later governed
slices added opt-in `--path` (including writable directories, cwd-dependent
entries, non-directory components, executable shadowing, writable
resolved-executables, unsafe executable ownership, and unsafe ownership of
PATH directories and ancestors) and exclusive `--command NAME` inspection. Run
`50c0b4936d50` extends the shared UID-0-or-`getuid()` ownership trust model to
every usable PATH directory and each ancestor through `/` under `--path` and
`--command`, with shared-ancestor dedup and ownership-blind explicit-root
mode; independent review
`code-reviews/review-path-directory-ownership.verdict.json` is `pass` with one
Low finding (`path-dir-ownership-1`). Run `574d06adfc2a` applies the shared
writability trust model to final executable
targets resolved through PATH in `--path` and `--command` modes; explicit-root
mode still does not search executables. Governed run `c9e3de33f46b`
(`pathaudit_open_repair_maintenance`) closed Low `PA-W1` by replacing the
65,537-byte automatic `readlink` buffer in `symlink_is_self_basename` with
command-bounded heap storage under
`docs/pathaudit-open-repairs-contract.md`; independent review
`code-reviews/review-pathaudit-open-repairs.verdict.json` is `pass` with
Medium `PAW1-DOC-901` and Lows `PAW1-DOC-902`/`PAW1-TEST-903`/
`PAW1-TEST-904`/`PAW1-SCOPE-905`. Pathaudit has no install target in
these slices (`make pathaudit` verifies under mktemp only) and is **not**
released. The repository includes Makefile quality targets, shell and pytest
coverage (including `tests/test_pathaudit.py`), sanitizer and Valgrind wiring,
Ubuntu CI configuration, and man pages for the established utilities.

Governed run `51100a584ac9` is the live `permguard` bootstrap under
`docs/permguard-bootstrap-contract.md`: `permguard [--] PATH...` is a
read-only ISO C17 explicit-path scanner using one `lstat` per operand. It
reports the closed four-code taxonomy `GROUP_WRITABLE`, `OTHER_WRITABLE`,
`SET_USER_ID`, and `SET_GROUP_ID` from each named object's own mode bits
without file-type heuristics; final symlinks are status-2 rejections; findings
stream per operand; mixed runs continue after errors with operational
precedence. Findings are escaped and deterministic, and exits are 0 clean, 1
hazards-only, or 2 error (including checked `STDOUT_WRITE` / ignored-`SIGPIPE`
output failure). Bootstrap contract/plan, source, tests, man page,
README/CHANGELOG text, and additive quality/memory wiring exist. Architecture,
QUALITY.md, TESTING.md, README, `docs/permguard.md`, and `man/permguard.1`
now match that shipped streaming four-code model; one-code drafts
`docs/permguard-first-vertical-slice-contract.md` /
`plans/permguard-first-vertical-slice-plan.md` open with conspicuous
superseded markers and are non-authority. This is not an installed, packaged,
or released utility. The existing sysdiff smoke oracle reaches permguard
transitively via `make test` but is not a dedicated permguard user-flow smoke.

A curated public
repository `https://github.com/leebase/linux-utilities` exists; AgentFlow notes
record a successful Ubuntu `make quality` CI run on commit `fbdf071` and a
GitHub `v0.1.0` tag/release aimed at that curated commit for `sysdiff`. Make
`install`/`uninstall` DESTDIR staging remains sysdiff-only. Accepted Low
limitations (changed-line delimiter ambiguity, Ubuntu-only CI, no packaged
`.deb`/`.rpm`, explicit-snapshot-only sysdiff scope) remain in force. The
existing sysdiff smoke oracle does not install pathaudit or permguard.

## pathaudit PA-W1 Open-Repair Status

Governed run `c9e3de33f46b` (`pathaudit_open_repair_maintenance`) closed Low
`PA-W1` under `docs/pathaudit-open-repairs-contract.md`. Focused pathaudit
pytest: 156 passed / 15 skipped. Step-5 complete `make quality` exited 0;
ordinary / ASan / UBSan / Valgrind each 359 passed / 15 skipped (scratch
writable gitdir). Smoke start/check 0 with empty blockers; check.log
`356 passed, 18 skipped in 21.16s`. Independent verdict
`code-reviews/review-pathaudit-open-repairs.verdict.json` is `pass`:
historical Low `PA-W1` closed; remaining Medium `PAW1-DOC-901` (roff
DIAGNOSTICS form swallow) and Lows `PAW1-DOC-902`, `PAW1-TEST-903`,
`PAW1-TEST-904`, `PAW1-SCOPE-905`. Prior pathaudit Medium PA-6CA-4 and Lows
PA-6CA-1/2/3 stay open. Pathaudit remains uninstalled, unpackaged, and
unreleased; this status does not invent polish or release readiness.

## Sixth Utility Mission Discovery

Governed run `787b9bb3d830`
(`discover_and_evaluate_sixth_linux_utility`) committed exactly **Bootstrap `openunlink` explicit-process zero-link regular-file descriptor reporting**
as the sixth planning mission. Its one-purpose scope is one explicit Linux PID:
report descriptors whose followed targets are regular files with
`st_nlink == 0`, while treating procfs link text only as escaped display
context. The proposed first slice closes the CLI to `--help`, `--version`, or
one PID; bounds and numerically sorts `/proc/PID/fd` entries; uses repeated
directory-relative metadata to require a stable zero-link regular target;
streams deterministic `OPEN_UNLINKED` findings and visible advisories; and
requires focused fixtures, a section-1 manual, strict quality gates, dedicated
smoke, and independent review. It excludes all-PID scans, inode grouping,
content reads, storage-reclamation claims, process control, monitoring,
networking, installation, packaging, and release.

The selection verdict in
`plans/review-sixth-utility-mission.verdict.json` is `pass`: no Critical or
High findings, three Medium (`SIXTH2-M1` descriptor-cap partial-evidence
behavior, `SIXTH2-M2` filesystem link-count boundary, `SIXTH2-M3` status-1
caller discrimination), and three Low (`SIXTH2-L1` stderr-write semantics,
`SIXTH2-L2` defensive size-range reachability, `SIXTH2-L3` stale run-step
wording). Review ran only
`python3 -m compileall -q tests/test_sysdiff.py tests/test_pathaudit.py
tests/test_permguard.py`, which exited 0. Existing smoke remains direct
sysdiff plus aggregate portfolio evidence at 351 passed / 18 skipped, not
`openunlink` verification.

No `openunlink` source, tests, manual, Make wiring, binary, sanitizer or
Valgrind result, dedicated smoke, package, tag, or release exists, and
implementation has not begun. Next executable action for this mission is to
clear the live repair-before-expansion gate by repair or explicit
reclassification plus independent review, then launch a separate governed
playbook beginning with a normative `openunlink` contract that resolves
`SIXTH2-M1`–`SIXTH2-M3` before CODE and preserves the Low findings.

## Permguard Review Status

Independent review for run `51100a584ac9` freshly ran only
`python3 -m pytest -p no:cacheprovider tests/test_permguard.py -q`: exit 0,
52 passed in 0.43s, zero skipped. Review did not rerun compilers, Make,
sanitizers, Valgrind, full pytest, or smoke as gate results. Step-5
quality-floor validation recorded GCC/Clang strict syntax, clang-format,
clang-tidy, cppcheck, Clang analyzer, ASan+UBSan `--help` and Valgrind
`--help` probes, full pytest `332 passed, 18 skipped`, and both shell fixture
suites exiting 0. Smoke start/check exited 0 with no blocking errors;
check.log pytest `332 passed, 18 skipped in 19.78s`.

`code-reviews/review-permguard-bootstrap.verdict.json` is `pass` and originally
recorded Medium PG-DOC-501/502, PG-TEST-503, PG-PORT-505, and PG-DOC-512 plus
Low PG-CRAFT-506, PG-TEST-507, PG-CLI-508, PG-MAKE-509/510/511. Prior High
PG-DOC-401 from review attempt 1 is resolved by explicit Authority
supersession in the bootstrap contract, plan, README, and CHANGELOG. Governed
recovery run `5035933ac7b4` (`repair_governed_run_ba6dc2fdd199`) closed those
five Mediums under independent review
`code-reviews/review-governed-run-ba6dc2fdd199.verdict.json` (`pass`):
architecture and user-facing docs describe the four independent predicates and
streaming continue-after-error model (PG-DOC-501); one-code contract/plan carry
conspicuous superseded pointers without a false removal claim (PG-DOC-502);
`STDOUT_WRITE` / ignored-`SIGPIPE` regressions are pinned (PG-TEST-503);
`<sys/stat.h>` owns `lstat` under `-D_POSIX_C_SOURCE=200809L` on Make and
pytest compile routes (PG-PORT-505); and QUALITY.md / TESTING.md name real
permguard gate membership, overrides, fixture oracle, and sanitizer/Valgrind
routes (PG-DOC-512). Failed run `ba6dc2fdd199` is not a passed delivery.
Remaining recovery Lows are PGR-TEST-706, PGR-PORT-707, PGR-BUILD-708,
PGR-TEST-709, and PGR-DOC-710; bootstrap Lows PG-CRAFT-506/PG-TEST-507/
PG-CLI-508/PG-MAKE-509/510/511 stay visible. Permguard remains
explicit-path-only, non-recursive, PATH-blind, read-only, uninstalled,
unpackaged, and unreleased.

## Release Status

Governed prepare-release work for identifier **0.1.0** assembles an unpublished
release candidate via `make release`: `artifacts/sysdiff-release.tar.gz`
(single root `sysdiff-release/`) and
`artifacts/sysdiff-release.tar.gz.sha256`. Version identity matches existing
`--version` / man / changelog evidence. RC-001 bytewise mixed-case ordering
remains the product contract, with explicit `rc_001` pytest coverage and shell
fixture goldens. Packaging integrity now fails closed on missing pathspecs and
requires staged tests, scripts, README, and CHANGELOG before writing the
archive (repair of review High H1), with pytest
`test_release_missing_pathspec_fails_closed_without_writing_archive` covering
that guard. Member selection uses `git ls-files` over `RELEASE_PATHSPECS`
(tracked files only; untracked scratch cannot ship —
`test_release_excludes_untracked_files`, REL-C847-001). The checksum records
the archive basename so
`(cd artifacts && sha256sum -c sysdiff-release.tar.gz.sha256)` succeeds
(repair for governed run `c847e01d15fe` / review M1). Live archive digest is
recorded in QUALITY.md **Release Verification** from
`artifacts/sysdiff-release.tar.gz.sha256` (must match `sha256sum` of the
tarball). Validation exercises `pytest -k rc_001`, both shell suites, full
`pytest tests/`, checksum verification, and out-of-tree extract
`make clean test`. Ordinary `make clean` does not delete the completed archive
or checksum. Scope is source packaging only: no `.deb`/`.rpm`, and no
Lee-authorized external publication in this step. Prior Medium backlogs remain
open and continue to prohibit new feature work.

## Clean Review Cycle Counter

Consecutive clean independent release-candidate review cycles currently stand
at **2**. Cycle 1 is governed run `8a3470eff7d3` with
`code-reviews/sysdiff-rc-review-cycle-1.verdict.json` = `pass` (0
Medium/High/Critical). Cycle 2 is governed run `c84986cf0c81` with
`code-reviews/sysdiff-rc-second-independent-cycle.verdict.json` = `pass` under
the Medium threshold (0 Medium/High/Critical, 9 Low L1–L9). The failed
pre-remediation RC cycle (`sysdiff-release-candidate-review-cycle-1.verdict.json`
fail on Medium RC-001) does not count toward the consecutive total; RC-001's
strcasecmp-mutant kill was re-verified in cycle 2. This counter records
consecutive clean RC reviews only and does not authorize publication or claim
that `sysdiff` is released without Lee-controlled release authorization.

## Release Package

Superseded for the current candidate by **Release Status** above: the active
unpublished package paths are `artifacts/sysdiff-release.tar.gz` and
`artifacts/sysdiff-release.tar.gz.sha256` from `make release`. Earlier
workspace-root `sysdiff-release.tar.gz` leftovers and
`artifacts/release/sysdiff-source.tar.gz` attempts are non-authoritative.

## Release Readiness

Product readiness for 0.1.0 remains grounded in previously recorded evidence
plus this step's packaging verification in QUALITY.md **Release Verification**:
release review (`docs/RELEASE_REVIEW.md`) records no known Medium-or-higher
findings after adversarial remediation; AgentFlow history records post-man-page
`make quality` exit 0; and public CI run `29119972847` passed on curated commit
`fbdf071`. Keep man page, contracts, and root summaries synchronized; preserve
accepted Low product limitations; treat Medium-or-higher craftsmanship or
security findings as blockers for later slices. QUALITY.md Release Verification
is the packaging evidence for the current unpublished candidate; it does not
authorize external publication.
