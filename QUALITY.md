# Quality Gates

The canonical local release gate is `make quality` (also available as
`make check` and `make-quality`). As declared in the `Makefile`, that target
runs the complete quality floor in this order:

1. `make clean`
2. `make gcc-strict` — GCC `-std=c17 -Wall -Wextra -Wpedantic -Werror -O2`
   for `src/sysdiff.c` and `src/pathaudit.c` (mktemp binaries only)
3. `make clang-strict` — Clang with the same strict flags (full link build;
   standalone `clang-syntax` exists but is not part of `quality`)
4. `make format-check` — `clang-format --dry-run --Werror` on both C sources
5. `make clang-tidy-check` — selected checks with `--warnings-as-errors='*'`
6. `make cppcheck-check` — `--enable=all --error-exitcode=1`
7. `make clang-analyzer-check` — `clang --analyze` with `-analyzer-werror`
8. `make man-check` — groff `-man -Tutf8 -ww -z` for `man/sysdiff.1` and
   `man/pathaudit.1`, fail on nonzero exit or any warning
9. `make test-suite` — shell suite plus `python3 -m pytest tests/ -q` (unit,
   integration, regression, fixture, malformed-input fuzz, pathaudit contract,
   and benchmark contract modules); pins `SYSDIFF_BIN` to `build/sysdiff` and
   scrubs ambient `PATHAUDIT_BIN` / `PATHAUDIT_UNDER_VALGRIND`
10. `make benchmark-check` — `scripts/benchmark_sysdiff.py` with a temp-dir JSON
    report (thresholds must pass; does not write `artifacts/`)
11. `make test-sanitize` — AddressSanitizer then UndefinedBehaviorSanitizer
    (Clang instrumented binaries for sysdiff and pathaudit; leak-fatal ASan;
    halt-on-error UBSan)
12. `make test-valgrind` — GCC debug rebuild under Valgrind memcheck with
    `--error-exitcode=99`, `SYSDIFF_UNDER_VALGRIND=1`, and
    `PATHAUDIT_UNDER_VALGRIND=1` (see Valgrind Coverage)

Pathaudit hermetic-gate regressions (PAC-M1 through PAC-M4) are pinned in the
pytest suite: **PAC-M1** `make test-suite` scrubs ambient `PATHAUDIT_*`
(`tests/test_pathaudit.py`, `tests/test_governed_run_c847e01d15fe.py`);
**PAC-M2** nested dist extract env drops `PATHAUDIT_*` beside `SYSDIFF_*`
(`scrubbed_nested_dist_env` in `tests/test_sysdiff.py`); **PAC-M3** runners
allowlist-forward sanitizer options into the sealed child env
(`tests/test_pathaudit.py`); **PAC-M4** hostile-byte stderr operand diagnostics
(`test_inspection_error_escapes_hostile_bytes_on_stderr`).

Standalone `make benchmark` still writes
`artifacts/performance/sysdiff-benchmark.json` for local inspection. Default
`make` / `make sysdiff` builds `build/sysdiff` with
`-std=c17 -Wall -Wextra -Wpedantic -Werror -O2`. `make pathaudit` compiles
`src/pathaudit.c` under mktemp only (no workspace binary). Hosts running the
full gate need both `gcc` and `clang`, plus `clang-format`, `clang-tidy`,
`cppcheck`, `groff`, `valgrind`, `python3`, and `pytest`. Ubuntu CI installs the
required tools (including groff) and runs exactly `make quality`. AGENTS.md
lists the intended release-quality toolset; treat Makefile targets as the
executable contract for what this repository actually gates today. See also
`docs/sysdiff-quality-floor-clean-checkout.md`.

## Fresh Quality-Floor Evidence

For governed run `c84986cf0c81` (second independent RC review cycle), fresh
executable evidence is recorded as follows—not as a silent claim of a full
`make quality` re-run inside this playbook. Step 1 (verify/repair) exited 0
on non-writing checks: `python3 -m pytest -p no:cacheprovider tests/ -q`
(**127 passed**), `gcc`/`clang` `-fsyntax-only` on `src/sysdiff.c`,
`cppcheck`, `bash -n` on both shell suites, and `python3 scripts/check_tools.py`;
pinned smoke hashes were unchanged and no source repair was required. Step 2
user smoke (`artifacts/user-smoke/result.json`) recorded start/check exit 0
with empty `blocking_errors`; `check.log` shows DESTDIR install/uninstall
staging, fixture acceptance ok, and smoke-bound pytest **`127 passed in
10.84s`**. Step 3 allowlisted review check repeated
`python3 -m pytest -p no:cacheprovider tests/ -q` → exit 0, **`127 passed in
10.96s`**. RC-001 strcasecmp-mutant kill was independently reconstructed and
confirmed. Prior complete clean-checkout `make quality` provenance remains in
`docs/sysdiff-quality-floor-clean-checkout.md`; do not conflate that historical
floor with this cycle's fresh subset evidence.

## Valgrind Coverage

`make test-valgrind` rebuilds `sysdiff` and `pathaudit` with GCC debug flags
into mktemp binaries, sets `SYSDIFF_BIN` / `PATHAUDIT_BIN` to those paths and
`SYSDIFF_UNDER_VALGRIND=1` / `PATHAUDIT_UNDER_VALGRIND=1`, then runs
`./tests/test_sysdiff.sh` followed by `python3 -m pytest tests/ -q`.
Memcheck is applied only where harness helpers honor the flag.

The shell suite (`tests/test_sysdiff.sh`) wraps each `run_sysdiff` invocation
in Valgrind memcheck (`--error-exitcode=99`, full leak check). Under that flag
it skips the DESTDIR install/reinstall/uninstall packaging block, then
delegates to `tests/test_sysdiff_fixture.sh`. The fixture suite wraps compare
and most acceptance cases through its `run_status` helper under the same
flag, while omitting the heaviest entry-count and 16 MiB aggregate byte-limit
cases for runtime; those boundaries remain covered by ordinary and sanitizer
paths (and by pytest `test_snapshot_byte_limit_boundary` under memcheck).

In `tests/test_sysdiff.py`, only call sites that go through `_valgrind_command`
(via `run_sysdiff`, `run_sysdiff_bytes`, and `run_with_closed_stdout_pipe`)
run the product binary under memcheck: help/version, compare diffs, malformed
and NUL rejection, safe escaping, closed-stdout EPIPE, and the snapshot
byte-limit boundary. Other pytest modules executed by the same gate
(`tests/test_sysdiff_malformed_fuzz.py`, `tests/test_sysdiff_benchmark.py`,
`tests/test_check_tools.py`) and dist/`make` subprocess helpers that do not
call `_valgrind_command` do not prepend Valgrind; nested extract builds
explicitly unset `SYSDIFF_UNDER_VALGRIND`.

## Valgrind Hostile-Input Coverage

Ordinary hostile-input regression coverage (reject-close, exit 2, empty stdout)
for the deterministic malformed-snapshot corpus lives in
`tests/test_sysdiff_malformed_fuzz.py` and is exercised by
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sysdiff_malformed_fuzz.py -q`.
That command is evidence only when pytest both collects the module and
executes at least one test (collection alone is not sufficient). Memcheck
coverage is a separate claim: `make test-valgrind` sets
`SYSDIFF_UNDER_VALGRIND=1` and runs the full pytest tree, and shell plus
`tests/test_sysdiff.py` helpers prepend Valgrind, but
`tests/test_sysdiff_malformed_fuzz.py` never consults that variable and
invokes `sysdiff` directly, so the malformed-snapshot corpus is not covered
by Valgrind unless existing executable evidence proves otherwise (none does
today; corpus cases may still execute unwrapped under that gate). Residual
risk: allocation or lifetime defects that only appear on hostile parse/free
paths may pass the Valgrind gate while ordinary corpus rejection checks still
pass. Smallest future action to close the gap: share
`_valgrind_command`/`_finish_valgrind` into the fuzz module’s
`run_compare_case` and scale per-case timeouts under
`SYSDIFF_UNDER_VALGRIND=1`. This documentation repair does not claim
`make quality`, `make test-valgrind`, or any other write-producing gate ran.

## Known Gaps

- Presentation ambiguity: format-1 changed lines use `old -> new`, so values
  containing that delimiter sequence are not reversibly parseable from stdout.
- CI and packaging: the public gate is Ubuntu-focused; there is no multi-distro
  or multi-architecture matrix. Make `install` / `uninstall` staging via
  `DESTDIR`/`prefix` is present; there is still no packaged `.deb`/`.rpm`.
- Product scope: `sysdiff` compares explicit snapshots only; it does not collect
  live state. That is intentional, not an unfinished feature of 0.1.0.
- Portability of the gate itself: sanitizers and Valgrind assume a Linux-like
  toolchain; fixture write-error checks that use `/dev/full` are skipped when
  that device is absent; Valgrind omits the heaviest entry-count and 16 MiB
  byte-limit cases (still covered outside Valgrind).
- Tool-availability preflight (`scripts/check_tools.py`) is infrastructure for
  Agent-Orch routes; Low review findings around typing/empty-stdout assertions
  remain internal follow-ups and are outside the curated public seed.
- Malformed-input fuzz coverage is the deterministic corpus in
  `tests/test_sysdiff_malformed_fuzz.py` (gated via `test-suite`), not
  open-ended fuzzing; that corpus is not under Valgrind memcheck (see
  Valgrind Hostile-Input Coverage). Performance benchmarking is gated via
  `benchmark-check` inside `make quality` and via standalone `make benchmark`.

## Release Verification

Release-candidate verification for `sysdiff` **0.1.0** records executable
packaging evidence for the `artifacts/` candidate (not a full
`make quality` re-run). Archive identity is taken from the live artifacts:
`artifacts/sysdiff-release.tar.gz` and
`artifacts/sysdiff-release.tar.gz.sha256` contain
`95b2316dcf84ca2d709ce228d6a8632791e9e2393e68ebb64ac9968692cc6013  sysdiff-release.tar.gz`
(`(cd artifacts && sha256sum -c sysdiff-release.tar.gz.sha256)` → OK).
`make release` selects members with `git ls-files` over `RELEASE_PATHSPECS`
(same tracked-only model as `make dist`), so untracked scratch under product
trees cannot ship (regression `test_release_excludes_untracked_files`; repair
for review REL-C847-001 / M1 after governed run `c847e01d15fe`). The bundled
Makefile in the archive carries `git ls-files` selection and basename
checksum emission; two independent out-of-tree rebuilds are byte-identical to
the live `artifacts/` deliverable. Commands run with preserved output on this
repair: `python3 -m pytest tests/ -q` → **130 passed**; clean extraction under
`/tmp` with `make -C …/sysdiff-release clean test` → **121 passed, 9 skipped**
(git-gated `test_dist_*` and `test_release_*` skips in the non-git extract). Missing-pathspec
negative check: `make release … NOPE.md …` → exit nonzero, no archive written
(also covered by pytest). Checksum form regression: basename beside the
archive so `(cd artifacts && sha256sum -c …)` succeeds (c847e01d15fe failure
class). RC-001 result: pass — bytewise Alpha/alpha ordering and
strcasecmp-mutant kill; no `src/sysdiff.c` compare-behavior change. Clean
extraction builds from the single `sysdiff-release/` root; `make clean`
preserves the archive. Remaining risks: prior Medium backlogs still open;
accepted Low limitations (` -> ` presentation, Ubuntu CI focus, no
`.deb`/`.rpm`, explicit-snapshot-only scope). No external publication
occurred.

## Release Readiness

Historical documentary readiness notes for `sysdiff` **0.1.0** remain below the
executable packaging evidence in **Release Verification**. Rely on that section
for archive checksum, RC-001, clean-extraction, and commands run in this
prepare-release step. Prior recorded post-man-page `make quality` exit 0,
Ubuntu CI run `29119972847` on curated commit `fbdf071`, and
`docs/RELEASE_REVIEW.md` still support product readiness claims. Known
limitations stay in force: `old -> new` presentation ambiguity, Ubuntu-only CI
matrix, source-first packaging without `.deb`/`.rpm`, and explicit-snapshot-only
product scope. Publication still requires Lee authorization.
