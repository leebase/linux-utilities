# Review: smoke-fixture-fix

**Files reviewed**: `tests/smoke_manifest.json`, `tests/test_sysdiff_fixture.sh`
**Review date**: 2026-07-09
**Verdict**: pass (no High or Critical findings)

---

## Checks Run

| Command | Exit | Summary |
|---|---|---|
| `python3 -m json.tool tests/smoke_manifest.json` | 0 | JSON is well-formed |
| `python3 -c "import json,os; [os.path.exists(s['path']) or exit(1) for s in json.load(open('tests/smoke_manifest.json'))['steps']]"` | 0 | All `path` values in `steps` resolve to existing files |
| `bash -n tests/test_sysdiff_fixture.sh` | 0 | Bash syntax check passes |
| `python3 -m compileall tests/` | 0 | All Python test files compile without error |
| `git status --short -- tests/smoke_manifest.json tests/test_sysdiff_fixture.sh` | 0 | Both files are new additions (`??`); no tracked files were modified outside `tests/` |

---

## Lens Notes

### Correctness

**F-001 (Medium)** — `assert_sorted_file_equals` is used for the primary diff comparison
(line 150 of `test_sysdiff_fixture.sh`) instead of `assert_file_equals`. Because both
sides are sorted before comparing, a non-sorted implementation whose output contains the
right lines in the wrong order would pass the test. The contract in
`docs/sysdiff-fixture-slice-contract.md` explicitly requires deterministic output sorted by
key byte-order. The expected heredoc (lines 139–147) is already pre-sorted, so switching
to `assert_file_equals` would correctly enforce ordering without any other change. This
does not fail the verdict (Medium, not High), but it leaves the ordering contract
unverified.

### Coverage

The fixture test covers every acceptance check listed in the contract:

- Changed/added/removed keys, empty value, value with spaces, comment lines, blank lines ✓
- Exact stdout for both the changed and identical cases ✓
- `assert_diff_prefixes` verifies no stray output formats ✓
- Exit status 0, 1, and 2 are all exercised ✓
- Stderr content is checked with `assert_nonempty` and `assert_contains` for all error
  paths ✓
- Stdout is asserted empty for all error paths ✓

Minor gap: `assert_diff_prefixes` validates only that each line starts with `-`, `+`, or
`~`; it does not validate the full format (e.g., `key=value` or `key: old -> new`).
However, because `assert_sorted_file_equals` is called first against a fully-specified
expected output, any format deviation would already be caught there. This is a Low
cosmetic gap in the secondary check only.

### Determinism

All fixture data is defined inline via heredoc, so there are no external files or
environment-dependent inputs. `LC_ALL=C sort` is used when sorting, making the sort
locale-independent. The `WORKDIR` is always derived from the script's own path and is
cleaned up on EXIT, HUP, INT, and TERM. No random values, timestamps, or PIDs appear
in any assertion. The test is deterministic.

### Allowed Paths

Both files are additions inside `tests/`. No files outside `tests/` (or
`scripts/`, which is unchanged) were modified. The smoke manifest references only
pre-existing files: `tests/smoke_start.py`, `scripts/smoke.sh`, and
`tests/check_sysdiff_smoke.py`. `scripts/smoke.sh` itself simply runs `make test`,
which is the correct smoke gate for this project.

### Smoke Manifest Structure

`tests/smoke_manifest.json` is structurally sound: `steps`, `start_command`,
`check_command`, timeouts, and polling interval are all present and consistent.
`startup_delay_seconds: 0` is appropriate because `smoke_start.py` is a one-shot
script with no daemon to wait for.
