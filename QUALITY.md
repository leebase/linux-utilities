# Quality Gates

The canonical local release gate is `make quality` (also available as
`make check` and `make-quality`). As declared in the `Makefile`, that target
runs the complete quality floor in this order:

1. `make clean`
2. `make gcc-strict` — GCC `-std=c17 -Wall -Wextra -Wpedantic -Werror -O2`
3. `make clang-strict` — Clang with the same strict flags (full link build;
   standalone `clang-syntax` exists but is not part of `quality`)
4. `make format-check` — `clang-format --dry-run --Werror`
5. `make clang-tidy-check` — selected checks with `--warnings-as-errors='*'`
6. `make cppcheck-check` — `--enable=all --error-exitcode=1`
7. `make clang-analyzer-check` — `clang --analyze` with `-analyzer-werror`
8. `make man-check` — groff `-man -Tutf8 -ww -z`, fail on nonzero exit or any
   warning
9. `make test-suite` — shell suite plus `python3 -m pytest tests/ -q` (unit,
   integration, regression, fixture, malformed-input fuzz, and benchmark
   contract modules)
10. `make benchmark-check` — `scripts/benchmark_sysdiff.py` with a temp-dir JSON
    report (thresholds must pass; does not write `artifacts/`)
11. `make test-sanitize` — AddressSanitizer then UndefinedBehaviorSanitizer
    (Clang instrumented binaries; leak-fatal ASan; halt-on-error UBSan)
12. `make test-valgrind` — GCC debug rebuild under Valgrind memcheck with
    `--error-exitcode=99`; runs the shell suite and full `pytest tests/ -q`
    with `SYSDIFF_UNDER_VALGRIND=1`, but memcheck wrapping applies only where
    helpers honor that flag (see Valgrind Hostile-Input Coverage)

Standalone `make benchmark` still writes
`artifacts/performance/sysdiff-benchmark.json` for local inspection. Default
`make` / `make sysdiff` builds `build/sysdiff` with
`-std=c17 -Wall -Wextra -Wpedantic -Werror -O2`. Hosts running the full gate
need both `gcc` and `clang`, plus `clang-format`, `clang-tidy`, `cppcheck`,
`groff`, `valgrind`, `python3`, and `pytest`. Ubuntu CI installs the required
tools (including groff) and runs exactly `make quality`. AGENTS.md lists the
intended release-quality toolset; treat Makefile targets as the executable
contract for what this repository actually gates today. See also
`docs/sysdiff-quality-floor-clean-checkout.md`.

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
