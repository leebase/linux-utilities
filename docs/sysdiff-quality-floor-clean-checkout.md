# sysdiff quality floor — clean-checkout contract

Release-candidate quality floor for `sysdiff` on Linux. The executable contract
is the Makefile aggregate `make quality` (also `make check` / `make-quality`).
This document records a fresh clean-build provenance run, the exact gate list,
observed results, and remaining risks. A passing complete `make quality` from
`make clean` is the definition of done; targeted subsets alone are not enough.

## Checkout Provenance

Verification ran in the governed workspace
`/home/lee/projects/linux-utilities` on host `linuxmint` (Linux
`6.17.0-35-generic`, x86_64, Ubuntu/Mint 24.04-family userspace). Git HEAD at
gate start was `a69423e2a1cfa4b30c199797aaa10cead4879370` on branch `main`.
The working tree was intentionally dirty with pre-existing AgentFlow and
slice deliverables; those unrelated edits were preserved (no reset, discard,
or overwrite of user work). Commands executed in order at UTC
2026-07-19T07:49:00Z through 2026-07-19T07:53:06Z: standalone `make clean`
(exit 0), then `make quality` (which itself begins with another `make clean`),
then standalone `make benchmark` as the final step of this window to
regenerate durable performance evidence at
`artifacts/performance/sysdiff-benchmark.json`. This attempt explicitly
permits and validates that benchmark output path: prior governed run
`cfd2baab9b0c` failed changed-path policy because `make benchmark`
legitimately wrote the same JSON; build outputs under `build/`, reproducible
release-test outputs under `dist/`, pytest caches, and Python bytecode caches
are likewise in scope when existing commands generate them. Immediately after
benchmark exit, the artifact was hashed and this document transcribed from
those bytes so medians cannot drift from the named file. Artifact identity
pins: mtime `2026-07-19T07:53:06Z` (UTC), SHA-256
`e4a17df113c304a1cb3176a727e9f0638918d9d6af4507393bc203d8f6823a93`.
Toolchain versions observed on this host: GCC 13.3.0, Clang/LLVM 18.1.3
(clang, clang-format, clang-tidy), Cppcheck 2.13.0, Valgrind 3.22.0, GNU
groff 1.23.0, Python 3.12.3, pytest 8.4.2, GNU Make 4.3. Scratch notes for
this attempt live under
`.agent-orch-scratch/ec85b0a6ba28/step_01_run_and_repair_quality_floor/attempt-3/`
and are not governed outputs. No source or Makefile repairs were required on
this pass; the repository already satisfied every required gate after
`make clean`.

## Quality Gates

The Makefile is the source of truth. `make quality` runs, in order, without
silent skips: (1) `make clean` removes `build/`; (2) `make gcc-strict` links
`src/sysdiff.c` with GCC `-std=c17 -Wall -Wextra -Wpedantic -Werror -O2` into
a `mktemp` binary; (3) `make clang-strict` does the same with Clang; (4)
`make format-check` runs `clang-format --dry-run --Werror`; (5)
`make clang-tidy-check` applies selected analyzer/bugprone/performance/
portability checks with `--warnings-as-errors='*'`; (6) `make cppcheck-check`
uses `--enable=all --error-exitcode=1`; (7) `make clang-analyzer-check`
runs `clang --analyze` with `-analyzer-werror` and text output under
`mktemp`; (8) `make man-check` renders `man/sysdiff.1` via
`groff -man -Tutf8 -ww -z` and fails on nonzero exit or any warning; (9)
`make test-suite` builds `build/sysdiff`, runs `./tests/test_sysdiff.sh`
(informational CLI, DESTDIR install/uninstall packaging, and transitive
`tests/test_sysdiff_fixture.sh`), then
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
covering unit, integration, regression, fixture, malformed-input fuzz
(including a valid-pair positive control), and benchmark contract modules
(harness absence is a hard fail, not a skip); (10) `make benchmark-check`
invokes `scripts/benchmark_sysdiff.py` with JSON under `mktemp` (thresholds
must pass; does not write workspace `artifacts/`); (11) `make test-sanitize`
preflights via `scripts/check_tools.py --memory-gate sanitize`, then runs
AddressSanitizer (`detect_leaks=1:abort_on_error=1`) and
UndefinedBehaviorSanitizer (`halt_on_error=1`) against shell plus pytest
with instrumented `mktemp` binaries; (12) `make test-valgrind` preflights
`--memory-gate valgrind`, rebuilds with GCC `-O1 -g`, and runs shell plus
pytest under Valgrind memcheck with `--error-exitcode=99`. Separately,
`make benchmark` regenerates
`artifacts/performance/sysdiff-benchmark.json` as durable local evidence and
is an allowed changed path for this quality-floor retry. No dependencies were
added, gates weakened, or product features introduced for this floor run.

## Results

All required gates passed on this host. Explicit sequence: `make clean`
exited 0; `make quality` exited 0 at UTC 2026-07-19T07:52:58Z (wall clock
about 3 minutes 58 seconds from quality start at 07:49:00Z). Observed
per-stage outcomes: `gcc-strict`, `clang-strict`, `format-check`,
`clang-tidy-check` (613 non-user warnings suppressed; zero user findings),
`cppcheck-check` (106 active checkers, exit 0), `clang-analyzer-check`, and
`man-check` all succeeded. Functional suite: shell fixtures reported
`ok: sysdiff fixture acceptance tests passed`; pytest under normal
`test-suite` reported **124 passed in 10.20s**. Quality-embedded
`benchmark-check` exited 0 with thresholds satisfied under a temporary
JSON path. ASan suite: preflight available, fixtures ok, **124 passed in
28.50s**. UBSan suite: preflight available, fixtures ok, **124 passed in
10.66s**. Valgrind suite: preflight available, fixtures ok, **124 passed
in 157.76s** (0:02:37). Standalone `make benchmark` exited 0 at UTC
2026-07-19T07:53:06Z and wrote
`artifacts/performance/sysdiff-benchmark.json` with `schema_version` 1 and
`passed: true` (SHA-256
`e4a17df113c304a1cb3176a727e9f0638918d9d6af4507393bc203d8f6823a93`,
mtime `2026-07-19T07:53:06Z`). Measured medians (peak RSS reported as the
per-run maximum across samples) vs inclusive thresholds, transcribed from
that same artifact in this pass:
`startup_ms_median` 1.22835100046359 ≤ 200.0;
`fixture_ms_median` 7.385764009086415 ≤ 100.0;
`peak_rss_kib` 2540.0 ≤ 32768.0; plus `baseline_ms_median`
1.2662539957091212 (`/bin/true` spawn floor); metadata
`fixture_entry_count` 8000, `warmups` 1, `sample_count` 5,
`work_dir_kind` tempdir. Repairs this attempt: none required—no gate
exposed a repository defect. Prior-floor regressions (fuzz positive control;
benchmark harness absence as hard fail) remain in tree and continue to pass
inside the 124-test aggregate. Definition of done is met: clean then
complete `make quality` green, plus durable benchmark JSON regenerated and
validated with matching documented numbers.

## Remaining Risks

Host and environment remain first-class residual risk: the full floor
requires Linux with both GCC and Clang, sanitizer runtimes, Valgrind,
clang-format, clang-tidy, cppcheck, groff, Python 3, and pytest; missing
tools fail loudly rather than skip, so incomplete images cannot claim this
floor. Performance numbers are not bit-stable across hosts—scheduler noise,
thermal throttling, and cgroup limits can move medians; thresholds are
conservative release guardrails, not microbenchmark claims. The durable
JSON under `artifacts/performance/` is local evidence (commonly gitignored)
and is absent from a fresh clone until `make benchmark` is re-run; this
document's SHA-256 and mtime pins exist so auditors can detect drift when
the file is present. Valgrind wraps the shell suite and pytest collection
when `SYSDIFF_UNDER_VALGRIND=1` is set, but not every pytest module routes
every child through memcheck the same way (`tests/test_sysdiff.py` honors
the flag for compare helpers; malformed-fuzz and benchmark modules primarily
exercise `SYSDIFF_BIN` / harness paths). ASan with leak detection does cover
the hostile corpus via `SYSDIFF_BIN`, so memory-safety risk is largely
mitigated, yet documentation that says “full pytest under Valgrind” can
overstate per-module wrap depth. Packaging checks inside the shell suite
rebuild/install the uninstrumented workspace `build/sysdiff` even under
sanitizer/Valgrind gates (known Medium from the install/uninstall review).
Source-release Medium findings from `make dist`/`distcheck` (dirty-tree
provenance, docs membership, `dist/` hygiene) are outside this floor’s pass
criteria and remain open backlog. Changed-path policy for governed runs must
continue to allow `artifacts/performance/sysdiff-benchmark.json` whenever
`make benchmark` is part of the step contract; treating that write as an
unexpected path will fail a green floor again (as in `cfd2baab9b0c`). This
evidence does not assert a `.deb`/`.rpm`, cross-distro identical timings, or
product-release closure beyond the Makefile quality contract recorded here.
