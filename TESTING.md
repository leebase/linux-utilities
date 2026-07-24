# Test Strategy

`sysdiff` testing is layered so behavior stays fixture-backed, privilege-free,
and deterministic across hosts. The shell suite (`tests/test_sysdiff.sh`) covers
informational commands and delegates to `tests/test_sysdiff_fixture.sh` for
acceptance of compare status classes 0/1/2, exact sorted stdout, ordering
independence, comments and blank/whitespace-only lines, CRLF equivalence,
resource-limit failures, and empty stdout on error paths. Pytest
(`tests/test_sysdiff.py`) builds a temporary binary with `$CC`/`cc` and strict
C17 flags (it does not reuse `build/sysdiff` from `make`), then covers
help/version, sorted diffs, opaque `file.` keys, NUL rejection, safe escaping
of values/paths/commands, closed-stdout `EPIPE` behavior, and snapshot
byte-limit boundaries. `tests/test_pathaudit.py` encodes the pathaudit contract
and compiles `src/pathaudit.c` into a pytest-owned temporary directory (or
honors `PATHAUDIT_BIN` / `PATHAUDIT_UNDER_VALGRIND` when memory gates supply
them). Smoke (`scripts/smoke.sh` via `make test`, plus
Agent-Orch `tests/smoke_manifest.json`) exercises the same functional path
without special privileges. Dynamic analysis is separate: ASan/UBSan rebuild
and re-run the suite; Valgrind wraps the shell suite and `tests/test_sysdiff.py`
with reserved status `99` (not the malformed-fuzz corpus; see Valgrind
Hostile-Input Coverage). Under `SYSDIFF_UNDER_VALGRIND=1`, the fixture suite
skips the 65,536-entry and 16 MiB total-byte limit cases for runtime; those
paths still run on normal and sanitizer gates. Write-to-`/dev/full` checks run
only when `/dev/full` is writable (Linux-oriented). Shell fixtures export
`LC_ALL=C` for locale-stable diagnostics and honor `SYSDIFF_BIN` to select the
binary under test. Internal `tests/test_check_tools.py` covers routed-tool
preflight and is infrastructure, not product compare behavior. Defects should
land as failing regressions before fixes.

## Valgrind Hostile-Input Coverage

Distinguish two layers: ordinary hostile-input regression coverage proves the
parser reject-closes malformed snapshots (exit 2, empty stdout) via
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sysdiff_malformed_fuzz.py -q`,
and memcheck coverage proves the same paths under Valgrind. Evidence for the
ordinary corpus requires both pytest collection and execution of at least one
test; collecting without running is not proof. Under `make test-valgrind`,
the full `pytest tests/ -q` tree runs with `SYSDIFF_UNDER_VALGRIND=1`, and
shell fixtures plus `tests/test_sysdiff.py` prepend Valgrind, but
`tests/test_sysdiff_malformed_fuzz.py` ignores that flag and invokes `sysdiff`
directly, so the malformed-snapshot corpus is not covered by Valgrind unless
existing executable evidence proves otherwise (none does today; corpus cases
may still execute unwrapped under that gate). Residual risk is that leak or
use-after-free defects unique to hostile parse cleanup can escape the
Valgrind gate while the ordinary corpus still passes. Smallest future action
to close the gap: wrap `run_compare_case` with the existing Valgrind helpers
from `tests/test_sysdiff.py` and raise timeouts when
`SYSDIFF_UNDER_VALGRIND=1`. This section does not claim a Valgrind or
`make quality` gate was executed in the documentation repair step.

## Running the Tests

Build the binary first with `make` (or `make sysdiff`); output is
`build/sysdiff`. `make pathaudit` compiles pathaudit under mktemp only and does
not write a workspace binary. Functional checks:

```sh
make test
python3 -m pytest tests/ -q
bash tests/test_sysdiff_fixture.sh
./scripts/smoke.sh
```

`make test` runs `test-suite`: `tests/test_sysdiff.sh` then pytest. For the full
declared release gate (compilers, formatters, static analysis, man-check,
tests, sanitizers, Valgrind):

```sh
make quality
```

To assemble the unpublished release-candidate source archive under
`artifacts/` (`sysdiff-release.tar.gz` plus `sysdiff-release.tar.gz.sha256`),
run `make release` after tests pass. Member selection uses `git ls-files` over
`RELEASE_PATHSPECS` (tracked product paths only). Ordinary `make clean` does
not remove those artifacts. Confirm the digest with
`(cd artifacts && sha256sum -c sysdiff-release.tar.gz.sha256)`
(the checksum names the archive basename beside the tarball),
then extract under `/tmp` and run `make -C <extract>/sysdiff-release clean test`.
Pytest `test_release_archive_checksum_verifies_beside_archive` pins that
path form without rewriting the live `artifacts/` deliverable;
`test_release_excludes_untracked_files` pins the tracked-only selection.

Individual analysis targets include `make sanitizer-test`, `make asan-test`,
`make ubsan-test`, and `make valgrind-test` (the Valgrind target cleans and
rebuilds with GCC first, then sets `SYSDIFF_UNDER_VALGRIND=1` and
`PATHAUDIT_UNDER_VALGRIND=1`). Override the binary with
`SYSDIFF_BIN=/path/to/sysdiff` when running shell fixtures directly, or
`PATHAUDIT_BIN=/path/to/pathaudit` for pathaudit pytest. View man pages with
`man -l man/sysdiff.1` and `man -l man/pathaudit.1`; lint them with
`make man-check`.
Do not treat this documentation file as proof that those commands were executed
in the current documentation-writing step; run them locally or in CI when
verifying a change. Set `CC` to select the compiler used by the default build
and by pytest’s `sysdiff_bin` / `pathaudit_bin` fixtures. Maintainers: keep
shell goldens, parametrize cases, and man-page EXAMPLES aligned when changing
output or limits; ownership and cleanup expectations for parse buffers are
documented in `architecture.md`.
