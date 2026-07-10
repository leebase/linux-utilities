# Craftsmanship Review — sysdiff

**Date:** 2026-07-09  
**Files reviewed:** `src/sysdiff.c`, `Makefile`, `tests/test_sysdiff.py`,
`tests/test_sysdiff.sh`, `tests/test_sysdiff_fixture.sh`,
`tests/check_sysdiff_smoke.py`, `tests/smoke_manifest.json`,
`tests/smoke_start.py`, `README.md`, `docs/*.md`

## Checks Run

Eight automated checks were executed against the repository:

| Command | Exit Code | Summary |
|---|---|---|
| `python3 -m pytest tests/ -q` | 0 | 26 tests passed in 0.36 s |
| `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c` | 0 | No diagnostics emitted |
| `gcc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 -o /dev/null src/sysdiff.c` | 0 | Clean build under GCC |
| `make clean && make` | 0 | Default build (`cc`, C17 strict flags) succeeded |
| `bash tests/test_sysdiff.sh` | 0 | Shell and fixture suites passed |
| `make sanitizer-test` | 0 | Clang ASan/UBSan build and test passed |
| `make valgrind-test` | 0 | Valgrind not found; skipped with advisory warning |
| `cppcheck --quiet --enable=all --suppress=missingIncludeSystem src/sysdiff.c` | 0 | No defects reported |

All checks passed. No compiler warnings, sanitizer errors, or cppcheck findings were produced.

## Lens Notes

### Overall Assessment

The C implementation is small, self-contained, and well-structured. It implements all acceptance checks from the format and C-source contracts with no detectable correctness bugs at the current test coverage level. Memory ownership is explicit: `parse_snapshot` owns all allocations until it returns success, the `goto cleanup` path is consistently used to avoid partial state, and `snapshot_free` is idempotent. The two-phase design (parse both, then diff) correctly enforces the no-partial-stdout-on-error guarantee. Output format, exit statuses, key validation, CRLF stripping, embedded-NUL rejection, resource limits, and duplicate-key detection all match the documented contracts.

### Correctness

Two minor correctness concerns were found:

**F003 — CRLF off-by-one at the line-length boundary** (`src/sysdiff.c:89`).
`read_line` checks `len >= SYSDIFF_MAX_LINE_BYTES` on every byte that is not `\n`.  Because `\r` is counted before `\n` is read, a CRLF-terminated line allows one fewer data byte than an LF-terminated line at the boundary. DESIGN.md acknowledges this as a known caveat, but it is not tested and represents a behavioral asymmetry in the format contract. The check could instead be deferred until after line-ending stripping, or the documented limit could clarify that it applies before line-ending removal.

**F005 — No argc==0 guard before argv[1] access** (`src/sysdiff.c:422`).
If the binary is exec'd with argc=0 (an adversarial but standards-legal scenario), none of the `argc == 1` or `argc == 2` branches match and execution falls through to `strcmp(argv[1], "compare")` where `argv[1] == NULL`, invoking undefined behavior. An early `if (argc < 1)` guard would close this at negligible cost.

### Test Coverage

**F004 — Missing focused tests for CRLF equivalence and resource-limit boundaries.**
The C-source contract (`docs/sysdiff-c-source-contract.md`) requires that CRLF-terminated snapshots compare the same as equivalent LF-terminated ones, and that both the line-length limit and the entry-count limit fail with contextual diagnostics. Neither the pytest suite nor the shell fixtures exercise these paths. DESIGN.md lists them as open caveats. Adding parametrized tests for CRLF input and for at-boundary and just-over-boundary inputs would close the gap.

### Portability

**F001 — Hardcoded `gcc` in the pytest session fixture** (`tests/test_sysdiff.py:14`).
`sysdiff_bin` always invokes `["gcc", ...]` regardless of `$CC` or what compiler the Makefile used. This means the Python tests silently diverge from the Makefile build on Clang-only systems and fail entirely if GCC is absent. The fixture should resolve the compiler through the environment (`$CC`, or `cc` via `shutil.which`) or reuse the pre-built `build/sysdiff` binary that `make test-suite` already builds.

**F002 — `smoke_start.py` sleeps 30 seconds while the smoke manifest allows only 10** (`tests/smoke_start.py:8` / `tests/smoke_manifest.json`).
`startup_timeout_seconds: 10` and `time.sleep(30)` are irreconcilable. An Agent-Orch smoke runner that polls the start helper to completion would time out. Since `sysdiff` is a batch CLI that exits immediately, the long-lived start-helper pattern is inapplicable; `smoke_start.py` should exit immediately or the step should be removed from the manifest.

### Documentation and Architecture

Documentation is thorough and consistent with the implementation. `README.md`, `docs/sysdiff-snapshot-format-and-scope.md`, `docs/sysdiff-c-source-contract.md`, `docs/DESIGN.md`, and `docs/DECISIONS.md` are coherent and mutually consistent. The DESIGN.md note about the CRLF boundary and valgrind ordering is accurate and honest. No documentation promises live system capture or undocumented features. The design doc's open-caveat section accurately names the two test gaps found above.

### Security

No untrusted data is used as a format string. Values are compared byte-for-byte without interpretation. File paths are opened with `fopen` and not exec'd, shell-expanded, or followed as symlinks beyond what the OS does normally. The `file.` key prefix is correctly treated as opaque data, not as a filesystem path to open. The F005 argc==0 finding is the only security-adjacent gap, and its practical impact is negligible outside of explicitly adversarial exec scenarios.

### Verdict

**pass** — no High or Critical findings. Five findings recorded: two Medium (F001, F002) and three Low (F003, F004, F005). None block release; all are addressable in follow-on work.
