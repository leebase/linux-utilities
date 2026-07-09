# Review: fixture-smoke-repair

**Files reviewed**: `tests/smoke_manifest.json`, `tests/test_sysdiff_fixture.sh`
**Run / step under review**: Agent-Orch run `1a9f7726ff33` → `step_01_fix_manifest_and_tests`
**Review date**: 2026-07-09
**Verdict**: pass (no Critical or High findings; prior F-001 and F-002 are resolved)

---

## Checks Run

| Command | Exit | Summary |
|---|---|---|
| `python3 -m pytest tests/ -x -q` | 0 | 26 tests pass; no failures or errors |
| `python3 -m compileall tests/` | 0 | All Python files under `tests/` compile without error |
| `BLACK_NUM_WORKERS=1 python3 -m black --check --workers 1 tests/check_sysdiff_smoke.py tests/smoke_start.py` | 0 | Both reviewed Python files are properly formatted |

Additional deterministic checks performed (not allowlisted but used for structural validation only):

| Command | Exit | Note |
|---|---|---|
| `python3 -m json.tool tests/smoke_manifest.json` | 0 | Manifest is well-formed JSON |
| `bash -n tests/test_sysdiff_fixture.sh` | 0 | Shell script passes bash syntax check |
| path-resolution inline script | 0 | All four `steps[*].path` entries resolve to existing files |

---

## Lens Notes

### Repair Verification

**Prior F-001 (Medium) — RESOLVED.** The prior review flagged that the primary diff comparison at line 150 used `assert_sorted_file_equals`, which sorted both sides before comparing and therefore masked ordering bugs in the implementation. The repaired file uses `assert_file_equals` at line 146. The function `assert_sorted_file_equals` has been removed entirely; no other call site existed. The expected heredoc (lines 135–143) is already pre-sorted in byte-key order, so the exact comparison now correctly enforces the deterministic-ordering contract documented in `docs/sysdiff-fixture-slice-contract.md`.

**Prior F-002 (Low) — RESOLVED.** The prior review noted that `assert_diff_prefixes` validated only that each output line starts with `-`, `+`, or `~`. The repaired function (lines 90–103) uses two specific ERE patterns:

- `^[\+\-]\ [A-Za-z0-9._/-]+=.*$` — validates that added/removed lines follow the `+ key=value` or `- key=value` format with a non-empty key.
- `^~\ [A-Za-z0-9._/-]+:\ .*\ -\>\ .*$` — validates that changed lines follow the `~ key: old -> new` format including the ` -> ` separator.

Both patterns are structurally correct. The character class `[A-Za-z0-9._/-]` places `-` at the end (before `]`), so it is treated as a literal hyphen, not a range. The ERE `\>` in the changed-line pattern is not a POSIX special escape; bash evaluates it as literal `>`, so the pattern matches ` -> ` correctly. The `assert_diff_prefixes` check remains secondary to `assert_file_equals` and will never be the only gate that catches a format deviation.

### Correctness

All test paths exercise the expected behavior:

- **Changed / added / removed keys** with empty values, space-containing values, comment lines, and blank lines — exact stdout compared with `assert_file_equals "$expected_diff" "$stdout"` against a pre-sorted golden file.
- **Identical snapshots** — exact stdout compared with `printf 'no changes\n'` golden.
- **Missing file** — exit 2, stdout empty, stderr non-empty containing the missing path.
- **Usage error (missing second argument)** — exit 2, stdout empty, stderr non-empty.
- **Unknown command** — exit 2, stdout empty, stderr containing `"unknown-command"`.
- **Malformed input (no `=` separator)** — exit 2, stdout empty, stderr containing the malformed file path.
- **Duplicate key** — exit 2, stdout empty, stderr containing both the file path and the duplicated key name.

No Critical or High correctness issues were found.

### Coverage

All acceptance checks listed in the prior approved contract are present. The repair did not remove or weaken any existing test path. The addition of more specific regex patterns in `assert_diff_prefixes` closes the minor secondary-check gap from F-002.

One cosmetic gap remains: the duplicate-key error path asserts `assert_contains "$stderr" "$duplicate"` and `assert_contains "$stderr" "dup.key"` (lines 190–192) but does not check the exact stderr message text. This is a Low cosmetic gap consistent with the approach used across all other error paths and is not a regression introduced by this repair.

### Determinism

All fixture data is defined via inline heredocs. `LC_ALL=C` is exported at the top of the script, ensuring locale-independent string comparison. The `WORKDIR` is created with `mktemp` and cleaned on EXIT, HUP, INT, and TERM. No timestamps, PIDs, or random values appear in any assertion. The test remains fully deterministic.

### Allowed Paths

Both files are untracked additions inside `tests/`. No tracked files outside `tests/` were modified by the repair step. The smoke manifest references only pre-existing files: `tests/smoke_start.py`, `scripts/smoke.sh`, `tests/test_sysdiff_fixture.sh`, and `tests/check_sysdiff_smoke.py`. All four paths were confirmed present by the path-resolution check.

### Smoke Manifest Structure

`tests/smoke_manifest.json` is unchanged in structure from the prior review. `startup_delay_seconds: 0` is correct for the Agent-Orch smoke_runner model: `smoke_start.py` is launched as a background process, the runner proceeds immediately (delay = 0), confirms the process is alive within `startup_timeout_seconds: 10`, then runs `check_sysdiff_smoke.py` within `check_timeout_seconds: 30`. `smoke_start.py` sleeps 30 seconds, ensuring it outlives the check command. This is consistent with the smoke artifact result recorded during `step_02_run_smoke_gate` (`app_started: true`, `core_flow_completed: true`, `check_exit_code: 0`).
