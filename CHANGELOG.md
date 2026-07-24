# Changelog

## Release Notes

This prepare-release step packages the reviewed `sysdiff` **0.1.0** release
candidate without publishing it. Version `0.1.0` is taken from
`src/sysdiff.c` (`--version`), `man/sysdiff.1`, README, and the existing
`0.1.0` changelog section—not invented here. `make release` writes
`artifacts/sysdiff-release.tar.gz` with a single `sysdiff-release/`
archive root (source, Makefile, license, user documentation, man pages,
scripts, and tests) plus companion `artifacts/sysdiff-release.tar.gz.sha256`
in standard `sha256sum` form (archive basename only, verified with
`(cd artifacts && sha256sum -c sysdiff-release.tar.gz.sha256)`; repair for
governed run `c847e01d15fe`, which failed when a nested basename-only
checksum was checked from another directory). Member selection uses
`git ls-files` over `RELEASE_PATHSPECS` so untracked scratch cannot ship
(REL-C847-001). Staging uses `/tmp` outside the workspace; ordinary
`make clean` removes only `build/` and leaves the archive and checksum for
later smoke and review. Pathspec existence is checked in the parent shell
before staging, and post-stage required files include tests, scripts,
README, and CHANGELOG so a truncated member list cannot ship with a success
message. Pytest `test_release_archive_checksum_verifies_beside_archive`,
`test_release_excludes_untracked_files`, and
`test_release_missing_pathspec_fails_closed_without_writing_archive` pin
checksum path form, tracked-only selection, and fail-closed packaging.
RC-001 remains locale-independent bytewise key ordering (`strcmp` in
`compare_entries_by_key`); pytest names containing `rc_001` pin the
mixed-case Alpha/alpha golden and kill a `strcasecmp` mutant from clean
scratch. User-visible compare behavior is unchanged. Compatibility remains
Linux/Ubuntu C17 with Make `install`/`uninstall` DESTDIR staging and no
`.deb`/`.rpm`. No GitHub tag promotion or external publication occurred.

## Unreleased

`make quality` now runs the complete sysdiff quality floor in one aggregate:
strict GCC and Clang link builds, clang-format, clang-tidy, cppcheck, Clang
static analysis (`clang --analyze` with analyzer-werror), man-check, shell and
pytest suites (including malformed-input fuzz and benchmark contract tests),
`benchmark-check` (harness validation with a temp-dir JSON report), ASan, UBSan,
and Valgrind. Standalone `make benchmark` still writes
`artifacts/performance/sysdiff-benchmark.json`. No `sysdiff` compare behavior
change.

Benchmark peak-RSS repair: the tiny C wrapper now reports via a dedicated
tempfile and redirects the measured child's stdout/stderr to `/dev/null`, and
is compiled with `-std=c17 -Wall -Wextra -Werror` using `waitpid` plus
`getrusage(RUSAGE_CHILDREN)` (no undeclared `wait4`). README now points the
declared gate surface at `docs/sysdiff-quality-floor-clean-checkout.md`, which
mirrors `Makefile` `quality` (including `clang-strict`, `clang-analyzer-check`,
`benchmark-check`, and Valgrind over shell plus pytest). No `sysdiff` compare
behavior change.

Added a reproducible source release workflow: `make dist` writes
`dist/sysdiff-source.tar.gz` and `dist/sysdiff-source.tar.gz.sha256` with a
normalized `sysdiff/` prefix, stable `SOURCE_DATE_EPOCH` metadata, and a
basename-only checksum; `make distcheck` proves same-epoch byte identity, safe
archive members, and a clean out-of-tree build plus `make test`. Pytest coverage
and README "Source releases" documentation accompany the targets. This is not a
packaged `.deb`/`.rpm` claim and does not change `sysdiff` compare behavior.

Documentation completion and repair for the governed repository: root release
docs now include HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP, and STATUS, with
README, CHANGELOG, architecture, and man-page text reconciled to `src/sysdiff.c`,
the `Makefile`, and the shell/pytest/smoke suites. Repair pass corrected the man
page FILES wording (paths are opened with `fopen` binary mode `rb`, not a
separate regular-file check), clarified unconditional POSIX `SIGPIPE` ignore
versus Linux support/CI focus, documented parse ownership, Valgrind limit-case
skips, conditional `/dev/full` coverage, quality-tool prerequisites, and
byte-limit-before-NUL precedence. No product behavior, Makefile targets, or test
expectations are intentionally changed in this documentation slice. Claims about
gate results remain limited to evidence recorded elsewhere (release review and
AgentFlow history); this Unreleased entry does not assert a fresh `make quality`
run. Accepted Low limitations from 0.1.0 remain visible: opaque ` -> `
changed-line presentation, Ubuntu-focused CI, source-first packaging without a
`.deb`/`.rpm` (Make `install`/`uninstall` staging is present), and
explicit-snapshot-only comparison scope.

## 0.1.0 — 2026-07-10

Initial public release candidate of `sysdiff`.

- Compares two explicit `key=value` snapshot files without inspecting the live
  system.
- Emits deterministic sorted added (`+`), removed (`-`), and changed (`~`)
  records; reports `no changes` for identical snapshots.
- Validates keys, duplicate records, embedded NUL bytes, line, entry, and
  total-byte limits, and avoids partial stdout on validation failures.
- Renders diff values and untrusted diagnostic paths/commands as printable
  ASCII with `\\` and `\xNN` escaping; comparison remains raw and opaque.
- Detects stdout write/flush failures on compare and informational paths,
  including closed stdout pipes (`EPIPE`) after ignoring `SIGPIPE` at startup,
  returns status `2` with a `stdout write error: <strerror>` diagnostic (`EIO`
  if errno is unset), and may leave partial stdout in that case only. Linux
  (Ubuntu) is the supported and CI-gated runtime.
- Accepts LF, CRLF, final lines without a newline, comments, and blank or
  whitespace-only space/tab lines.
- Provides strict compiler, formatting, static-analysis, sanitizer, Valgrind,
  fixture, pytest, smoke, and Ubuntu CI configuration. Default `make` builds
  the binary; `make test` runs functional tests; `make quality` is the full
  gate.
- Ships a section-1 manual page at `man/sysdiff.1`, linted by `make man-check`
  (part of `make quality`) with groff warnings enabled.

Known limitations: values are opaque text and changed records use a human
readable `old -> new` presentation, so that line format is not reversible when
values themselves contain ` -> `. `sysdiff` does not collect live snapshots.
Make `install`/`uninstall` DESTDIR staging is present; there is still no
packaged `.deb`/`.rpm` distribution.
