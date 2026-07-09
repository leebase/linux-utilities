# Review: Tool Availability Check

**Subject:** `scripts/check_tools.py`, `tests/test_check_tools.py`, `docs/tool-availability-check.md`, README tool-availability section
**Contract:** `docs/tool-availability-check-contract.md`
**Plan:** `docs/tool-availability-check-plan.md`
**Verdict:** pass (severity threshold: High — no High findings)

---

## Checks Run

| Check | Command | Exit code | Outcome |
|---|---|---|---|
| Compile script | `python3 -m compileall scripts/check_tools.py` | 0 | Pass |
| Compile tests | `python3 -m compileall tests/test_check_tools.py` | 0 | Pass |
| Targeted pytest | `python3 -m pytest tests/test_check_tools.py -v` | 0 | 9/9 passed |
| Compile all scripts+tests | `python3 -m compileall scripts tests` | 0 | Pass |
| Full pytest suite | `python3 -m pytest -v` | 0 | 26/26 passed (includes sysdiff suite) |
| Lint (ruff) | `python3 -m ruff check scripts/check_tools.py tests/test_check_tools.py` | 0 | All checks passed |
| Format (black) | `python3 -m black --check scripts/check_tools.py tests/test_check_tools.py` | 0 | 2 files unchanged |
| Type check (mypy) | `mypy scripts/check_tools.py` | 0 | No issues found |

**Environment limitation:** `python3 -m flake8` is not installed in the current venv (`No module named flake8`). ruff covers equivalent lint checks and passes. This is an environment gap, not a product defect.

---

## Lens Notes

### Correctness

The implementation correctly satisfies every contract acceptance check:

- **Probe accumulation** — `probe_harnesses` collects all results before any decision is made. Missing harnesses are accumulated into `missing` in `main()` so a single run reports all gaps, never stopping at the first one.
- **Exit codes** — `0` when all harnesses are available, `1` on any missing harness, and `2` on argparse usage error (e.g., unrecognized argument) via argparse's default error handling. The documentation explicitly lists all three codes and they match the implementation.
- **Stdout/stderr discipline** — success status goes to stdout, failure diagnostics go to stderr. On failure, `_print_failure` is called and `main` returns immediately; `_print_success` is never reached, so stdout remains empty on any failure path.
- **shutil.which with explicit PATH** — `_env_path` extracts `PATH` from the provided `env` mapping, passing it to `shutil.which(..., path=search_path)`. This means the probe never touches the real workstation's `PATH` when `env` is provided — tests can run in complete isolation.

**One fragility (Low, F001):** `_print_success` accepts `Sequence[HarnessProbeResult]` and unconditionally formats `result.executable` and `result.path` into an f-string. Both fields are typed `str | None` on `HarnessProbeResult`. The function is only ever called from `main()` after verifying `missing` is empty, so the values will always be non-None in practice. But the function's own signature provides no guard; a future caller passing an unavailable result would silently print `"None"` for the executable and path fields. There is no bug today and mypy does not flag it, but tightening the contract to accept only available results (or adding an assertion) would make the invariant self-documenting.

### Read-Only Safety

The script is read-only by construction:

- The imports are `argparse`, `os`, `shutil`, `sys`, `dataclasses`, and `typing` — no `subprocess`, no network clients, no file-write APIs beyond what `os` and `shutil` export. The implementation uses none of `os.chmod`, `os.remove`, `os.mkdir`, `shutil.copy`, or any write-mode `open` call.
- `shutil.which` is the only external call, and it is read-only by definition.
- No `subprocess.run` calls exist in the script. The read-only guard test (`test_availability_check_is_read_only_and_does_not_launch_workflows`) patches `module.subprocess.run` only if `hasattr(module, "subprocess")`, which evaluates to False since `check_tools.py` does not import `subprocess`. The test still passes and correctly validates the absence of any subprocess call.
- No playbook edits, route rewrites, model session invocations, package manager calls, or network connections are present.

### Test Adequacy

All eight test cases required by the plan are implemented. All 9 tests pass:

- `test_successful_default_run_reports_required_harnesses` — fake `codex` + `claude` in tmp_path, asserts exit 0, both harness names in stdout, and stderr is empty.
- `test_missing_codex_cli_reports_only_stderr_failure` — only fake `claude`, asserts non-zero and `codex_cli` in stderr.
- `test_missing_claude_code_reports_required_harness` — only fake `codex`, asserts non-zero and `claude_code` in stderr.
- `test_missing_both_required_harnesses_are_reported_together` — empty bin dir, asserts non-zero and both names in stderr in one run.
- `test_failure_diagnostic_frames_routed_worker_infrastructure` — asserts stderr contains "routed worker" or "worker infrastructure" and does not contain "sysdiff" or "comparison".
- `test_cli_streams_keep_success_on_stdout_and_failures_on_stderr` — full stream check: success has `stdout` with both names and `stderr == ""`; failure has `stdout == ""` and `stderr` with both names.
- `test_module_main_accepts_explicit_environment_without_real_path` — direct `module.main([], env=...)` call confirms the API works without subprocess overhead.
- `test_probe_layer_accumulates_structured_missing_harness_results` — calls `probe_harnesses` directly and asserts the missing set contains both names.
- `test_availability_check_is_read_only_and_does_not_launch_workflows` — patches `subprocess.run`, write-mode `open`, `os.chmod/remove/unlink/mkdir/makedirs`, `pathlib.Path.write_text/write_bytes`, and `socket.create_connection/socket` before calling `main`.

**One test-coverage gap (Low, F002):** The partial-failure tests (`test_missing_codex_cli_*` and `test_missing_claude_code_*`) check that stdout does not contain `"all required"`, but do not assert `result.stdout == ""`. The strict empty-stdout guarantee on any failure path is fully verified only in `test_cli_streams_keep_success_on_stdout_and_failures_on_stderr`. The per-harness tests would pass even if the script wrote a partial "available:" line for the harness that was found. This is not a bug in the implementation (which correctly keeps stdout empty on any failure), but the tests leave a gap in per-case isolation.

### API Contract

The public API matches the plan exactly:

- `DEFAULT_HARNESSES` is an explicit, reviewable `tuple[HarnessRequirement, ...]` with two entries for `codex_cli` (role: `implementation_worker`, executable: `codex`) and `claude_code` (role: `slice_reviewer`, executable: `claude`).
- `probe_harnesses(requirements, env)` returns a structured list without side effects.
- `main(argv, env, stdout, stderr)` separates formatting from exit-code logic and returns an int rather than calling `sys.exit` directly — correct for testability.
- `HarnessRequirement` and `HarnessProbeResult` are frozen dataclasses, keeping probe results immutable.
- The `HarnessProbeResult.name` property delegates to `requirement.name`, enabling `result_harness_name` in the tests to resolve the name without needing to know the internal structure.

### Documentation

`docs/tool-availability-check.md` covers all required topics: command usage, default harness table, successful output format, failure output format, exit status table (0/1/2), and scope limitations. Non-goals (model sessions, package installation, network access, sysdiff behavior, automatic route repair) are explicitly stated. The README section is short and accurate, pointing to the dedicated doc. No prohibited promises are made.

### Scope Adherence

The implementation is strictly advisory infrastructure validation with no scope creep:

- No `sysdiff` C code is touched.
- No Agent-Orch processes are launched.
- No fallback routing or playbook rewriting is performed.
- No host-state beyond `PATH`-based executable discovery is read.
- The `scripts/` directory is the only filesystem location written to (the script itself, placed there by the implementation step — the script does not write files at runtime).
