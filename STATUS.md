# Current Status

The suite now contains two small C utilities. `sysdiff` 0.1.0 implements
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
0/1/2 per `docs/pathaudit-contract.md` and `man/pathaudit.1`. Pathaudit has no
install target in this slice (`make pathaudit` verifies under mktemp only) and
is **not** released. The repository includes Makefile quality targets, shell
and pytest coverage (including `tests/test_pathaudit.py`), sanitizer and
Valgrind wiring, Ubuntu CI configuration, and man pages for both utilities. A
curated public repository `https://github.com/leebase/linux-utilities` exists;
AgentFlow notes record a successful Ubuntu `make quality` CI run on commit
`fbdf071` and a GitHub `v0.1.0` tag/release aimed at that curated commit for
`sysdiff`. Make `install`/`uninstall` DESTDIR staging remains sysdiff-only.
Accepted Low limitations (changed-line delimiter ambiguity, Ubuntu-only CI, no
packaged `.deb`/`.rpm`, explicit-snapshot-only sysdiff scope) remain in force.
The existing sysdiff smoke oracle does not directly exercise pathaudit.

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
