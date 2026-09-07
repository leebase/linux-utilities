# Bubblewrap ARG_MAX and E2BIG Repair Implementation Plan

Contract authority: `docs/bwrap-argmax-repair-contract.md`.

## Architecture

This repair addresses process invocation failures within the Agent-Orch sandboxed execution environment caused by Linux kernel `execve()` argument limits (`MAX_ARG_STRLEN` and `ARG_MAX` / `E2BIG`). The implementation strictly separates prompt transport from command-line arguments, introduces pre-exec payload measurement with fail-closed typed refusal, bounds validation retry feedback, and maintains hardened bubblewrap (`bwrap`) sandbox containment without modifying the `sysdiff` product codebase.

### 1. Off-Argv Prompt Transport Mechanism
- **Transport Decoupling:** Large mission packets, system prompts, structured instructions, and context payloads are removed from positional command-line arguments passed to `/usr/bin/bwrap` or worker binaries.
- **Standard Input Streaming:** The worker launch harness (`WorkerLaunch.stdin_text`) streams prompt payloads directly to worker processes over standard input or dedicated non-argv descriptor pipes.
- **Command-Line Invariant:** Positional command-line arguments are restricted to fixed flags, subcommands, path parameters, and configuration switches, guaranteeing that no individual `argv` element approaches the 32-kernel-page limit (`MAX_ARG_STRLEN` = 131,072 bytes on 4 KiB page Linux architectures).

### 2. Pre-Exec Payload Measurement and Fail-Closed Typed Refusal
- **Pre-Exec Accounting:** Before invoking `execve()` (or `subprocess.Popen` / `os.execve`), the orchestrator measures the complete composed launch footprint, including all bubblewrap sandbox arguments (`--ro-bind`, `--tmpfs`, `--unshare-all`, `--dir`, `--symlink`, etc.), target executable path, user arguments, and environment variables (`envp`).
- **Kernel Limit Oracles:** The launch harness computes:
  1. `max_single_launch_entry_bytes()`: Validates that every individual `argv` argument string and `envp` key-value string (including the terminating NUL byte) is $\le 131,072$ bytes.
  2. `max_total_launch_bytes()`: Validates that the combined size of all argument strings, environment strings, and their associated pointer table overhead ($\text{sizeof}(\text{char*}) \times (N_{\text{args}} + N_{\text{env}} + 2)$) remains well below the host `_SC_ARG_MAX` limit (typically 2,097,152 bytes on Linux).
- **Typed Classification (`LAUNCH_PAYLOAD_TOO_LARGE`):** If any entry or the total payload exceeds limits, the launch is halted immediately before kernel invocation. The failure is recorded with the typed classification `LAUNCH_PAYLOAD_TOO_LARGE`.
- **Value-Free Diagnostics:** Diagnostic records and `failure_evidence` emit strictly structural, numeric accounting (total argument count, total environment entry count, cumulative byte size, and the exact byte length of the largest entry). Unchecked prompt contents, payload snippets, and environment variable values are excluded to prevent credential or secret leakage.

### 3. Bounded Retry Feedback and Log Artifact Chaining
- **Console Output Excerpting:** Process console streams (`stdout` and `stderr`) captured in validation outcomes, test failure summaries, and retry feedback packets are bounded to fixed head and tail slices (`PROCESS_OUTPUT_EXCERPT_HEAD_BYTES = 4000` and `PROCESS_OUTPUT_EXCERPT_TAIL_BYTES = 4000`).
- **Elision Accounting:** When output exceeds 8,000 bytes, middle content is elided and replaced by a deterministic marker indicating the exact count of omitted bytes (e.g., `[... 145,230 bytes elided ...]`).
- **Hash-Chained Log References:** Bounded excerpts explicitly point to the immutable, complete, hash-chained log artifact stored in the run directory, breaking compounding feedback loops where validator output previously bloated subsequent mission packets.

### 4. Hardened Bubblewrap Sandbox Preservation
- **Non-Bypass Policy:** Hardened bubblewrap containment on Linux remains non-negotiable. The repair must never bypass sandboxing, omit namespace isolation (`--unshare-all`, `--unshare-net` where applicable), or grant unsandboxed execution to work around payload limits.
- **Filesystem Isolation:** Sandbox mount rules, read-only system binds (`/usr`, `/lib`, `/bin`), private `/tmp`, and isolated working directories remain strictly enforced.

### 5. Non-Product Blast Radius
- **Strict Boundary:** This repair is strictly isolated to orchestrator execution harnesses, validation feedback formatting, and journey manifest synchronization.
- **Product Immutability:** Zero modifications, dependencies, or regressions are introduced to `src/sysdiff.c`, `Makefile`, man pages (`man/sysdiff.1`), or existing product test suites (`tests/test_sysdiff.py`, `tests/test_sysdiff_fixture.sh`, `tests/test_sysdiff_benchmark.py`, `tests/test_sysdiff_malformed_fuzz.py`).

---

## Tests

The testing strategy establishes comprehensive regression coverage across unit testing, integration testing, sandbox containment validation, edge-case boundary verification, and user journey manifest synchronization.

### 1. Concrete Test Implementation Plan

#### A. Off-Argv Prompt Transport and Bubblewrap Containment (AC-1)
- **Unit & Integration Tests:**
  - `test_worker_launch_transports_prompt_via_stdin_text`: Verify that large prompts (> 128 KiB, up to 1 MiB) are delivered via `WorkerLaunch.stdin_text` and received intact by worker processes, with no prompt text present in `sys.argv` or `/proc/PID/cmdline`.
  - `test_bwrap_argv_length_under_kernel_page_limit`: Assert that all generated `bwrap` command-line invocations contain no individual argument exceeding 131,072 bytes (`MAX_ARG_STRLEN`), even when configured with extensive mount configurations.
  - `test_bwrap_sandbox_containment_enforced_on_linux`: Verify that bubblewrap isolation flags (`--ro-bind`, `--unshare-all`, `--proc`, `--dev`) are consistently applied on Linux platforms and that unsandboxed fallback execution is strictly prohibited.
  - `test_user_journey_contract_oracle_integrity`: Verify that `tests/user_journeys_manifest.json` is a valid, readable named oracle conforming to canonical schemas and mapping to all acceptance checks.

#### B. Pre-Exec Payload Measurement and Typed Refusal (AC-2)
- **Measurement & Boundary Tests:**
  - `test_pre_exec_payload_measurement_within_limits`: Assert that normal launch payloads pass pre-exec accounting and proceed to execution without disruption.
  - `test_pre_exec_single_arg_boundary_rejection`: Test boundary payload sizes near 128 KiB:
    - Single argument of $131,071$ bytes (including NUL) is accepted.
    - Single argument of $131,073$ bytes is intercepted prior to `execve()` and rejected fail-closed.
  - `test_pre_exec_total_argmax_boundary_rejection`: Test cumulative `argv` + `envp` + pointer table payloads near host `_SC_ARG_MAX` (2 MiB), ensuring oversized total payloads trigger immediate pre-exec refusal.
  - `test_typed_refusal_launch_payload_too_large`: Verify that rejected launches raise/return `LAUNCH_PAYLOAD_TOO_LARGE` with complete `failure_evidence` rather than raising uncaught `OSError: [Errno 7] E2BIG`.
  - `test_value_free_diagnostic_evidence_zero_leakage`: Assert that `failure_evidence` contains numeric counters (`total_argv_bytes`, `total_envp_bytes`, `argc`, `envc`, `max_arg_bytes`) and contains zero substrings of prompt text, environment secrets, or file contents.
  - `test_manifest_tampering_rejected_by_pinned_oracle`: Verify that attempts to mutate journey manifests, shrink traces, or alter allowlists are rejected by SHA-256 hash validation.

#### C. Bounded Validation Feedback, Manifest Synchronization, and Product Non-Regression (AC-3)
- **Output Bounding & Manifest Synchronization Tests:**
  - `test_process_output_excerpt_head_tail_bounds`: Feed 100 KiB and 1 MiB compiler/test failure logs into validation outcome formatting; assert output is bounded to `PROCESS_OUTPUT_EXCERPT_HEAD_BYTES = 4000` and `PROCESS_OUTPUT_EXCERPT_TAIL_BYTES = 4000` with exact elided byte accounting (e.g., `[... 94,000 bytes elided ...]`).
  - `test_retry_packet_size_remains_bounded`: Simulate a 5-step iterative failure-retry cycle; assert prompt packet byte size does not grow monotonically and never exceeds safety thresholds.
  - `test_user_journeys_manifest_synchronization`: Verify that `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are bit-for-bit identical, adhere to schema, and contain all 13 mapped journeys.
  - `test_sysdiff_product_suite_zero_regressions`: Run `make test`, `tests/test_sysdiff.py`, `tests/test_sysdiff_fixture.sh`, `tests/test_sysdiff_benchmark.py`, and `tests/test_sysdiff_malformed_fuzz.py` to confirm zero functional or performance regressions.
  - `test_sysdiff_cli_behavior_unaltered`: Verify real `build/sysdiff` execution across no-argument usage (exit 2), `--help` (exit 0), `--version` (exit 0), `compare` on clean/modified snapshots (exit 0 / 1), and malformed snapshot inputs (exit 2 with escaped diagnostics).

---

### 2. Contract Acceptance Check Mapping

| Acceptance Check | User Journey Mapping | Concrete Plan / Test Item | Verification Oracle & Gate | Blast Radius Boundary |
| :--- | :--- | :--- | :--- | :--- |
| **AC-1**: Prompt Transport Off-Argv & Hardened Sandbox Containment | 1. Worker launcher delivers large prompt payloads via stdin without exceeding `MAX_ARG_STRLEN`<br>2. User confirms bwrap sandbox containment enforced on Linux without unsandboxed bypass<br>3. User reads journey contract confirming manifest is usable oracle | - Decouple prompt transport to `WorkerLaunch.stdin_text`<br>- Enforce bwrap namespace/mount isolation<br>- `test_worker_launch_transports_prompt_via_stdin_text`<br>- `test_bwrap_sandbox_containment_enforced_on_linux` | `pytest tests/test_bwrap_argmax_repair.py`<br>`tests/smoke_manifest.json`<br>Journey validation gate | No changes to `src/sysdiff.c` or build artifacts; orchestrator harness and test harness only |
| **AC-2**: Pre-Exec Payload Measurement & Typed Refusal | 4. Operator observes pre-exec measurement rejecting oversized bwrap arguments fail-closed with `LAUNCH_PAYLOAD_TOO_LARGE`<br>5. Evaluator inspects edge-case payload sizes near 128 KiB confirming byte accounting without leakage<br>6. User retries after producer narrowing and pinned oracle rejects tampering | - Pre-exec `max_single_launch_entry_bytes()` and `max_total_launch_bytes()` checks<br>- Intercept before `execve()` -> `LAUNCH_PAYLOAD_TOO_LARGE`<br>- Sanitize diagnostic logging to numeric byte metrics<br>- `test_pre_exec_single_arg_boundary_rejection`<br>- `test_value_free_diagnostic_evidence_zero_leakage` | `pytest tests/test_bwrap_argmax_repair.py`<br>Typed exception validation<br>Manifest SHA-256 pin check | Orchestrator launch boundary only; value-free failure evidence in run artifacts |
| **AC-3**: Bounded Validation Output, Test Integrity, & Non-Product Scope | 7. Validator bounds process output in retry feedback to head/tail excerpts with log artifact pointers<br>8. Maintainer verifies synchronized manifests adhere to canonical schema and cover ACs<br>9. Developer runs sysdiff test suite and smoke verification confirming no regressions<br>10–13. User runs real sysdiff binary (no-arg, `--help`, `compare`, malformed snapshot) | - Implement 4000/4000 byte head/tail excerpting with elision marker<br>- Synchronize `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`<br>- `test_process_output_excerpt_head_tail_bounds`<br>- `test_sysdiff_product_suite_zero_regressions`<br>- `make test` & `scripts/smoke.sh` | Full `pytest tests/ -q`<br>`scripts/smoke.sh`<br>`make quality`<br>User journey simulation step | `src/sysdiff.c`, `Makefile`, man pages untouched; manifest synchronization preserved |

---

## Verification

The verification sequence executes a deterministic, multi-stage protocol to ensure that all repair mechanisms are fully validated without regressing repository assets.

### 1. Verification Protocol Steps

1. **Manifest and Schema Integrity Check:**
   - Verify that `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are synchronized, pass JSON linting, and conform to the canonical user journey schema.
   - Assert that all 13 declared journeys map to valid acceptance check identifiers (`AC-1`, `AC-2`, `AC-3`).
   - Pin manifest SHA-256 hashes to guarantee oracle immutability during execution.

2. **Focused Repair Regression Execution:**
   - Execute the dedicated test suite for prompt transport, pre-exec payload measurement, typed refusal classification, diagnostic zero-leakage, and bounded excerpting:
     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_bwrap_argmax_repair.py -v
     ```
   - Assert 100% pass rate with zero skips, warnings, or unhandled errors.

3. **Full Repository Test Suite Execution:**
   - Execute the entire pytest suite from the repository workspace root:
     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
     ```
   - Confirm that all existing tests (governed workspace abstraction, commissioning dependencies, historical runs `9add44496178`, `c847e01d15fe`, `17ca9404991a`, permguard, pathaudit, and openunlink) pass cleanly.

4. **Deterministic Smoke and Product Quality Verification:**
   - Run the unchanged smoke chain:
     ```bash
     tests/smoke_manifest.json -> tests/smoke_start.py -> tests/check_sysdiff_smoke.py -> scripts/smoke.sh -> make test
     ```
   - Verify that `build/sysdiff` compiles cleanly under `-Wall -Wextra -Wpedantic -Werror -std=c17`.
   - Run `make test`, `tests/test_sysdiff_fixture.sh`, and `tests/test_sysdiff_benchmark.py`.

5. **Independent User Journey Simulation:**
   - Replay all 13 journeys from `tests/user_journeys_manifest.json` via the governed simulation runner.
   - Validate that each journey executes its allowlisted commands (`build/sysdiff`), produces expected exit codes (0, 1, 2), and matches expected stdout/stderr patterns.
   - Confirm `artifacts/user-test/result.json` records valid passes for all 13 journeys with complete trace chains.

6. **Blast Radius and Scope Boundary Audit:**
   - Run `git diff --check` and `git status --short`.
   - Confirm that all modified files reside strictly within declared scopes (`plans/`, `docs/`, `tests/`, `journeys/`).
   - Verify that `src/sysdiff.c`, `Makefile`, `man/sysdiff.1`, and unrelated test fixtures have zero uncommitted changes or regressions.

7. **Independent Review Verdict:**
   - Generate structured review verdict ensuring clean evaluation with no findings at or above the High/Critical threshold.

---

## Risks

The implementation involves specific technical and operational risks that are managed through concrete fail-closed mitigations:

### 1. Payload Truncation vs. Fail-Closed Refusal Risk
- **Risk:** Attempting to handle oversized `argv` payloads by silently truncating arguments could corrupt prompt instructions or command parameters, causing nondeterministic agent behavior.
- **Mitigation:** Strict fail-closed policy. Prompts are streamed via standard input without length truncation. Any remaining command-line argument exceeding `MAX_ARG_STRLEN` or total launch payload exceeding `ARG_MAX` is intercepted and refused prior to `execve()`, raising a typed `LAUNCH_PAYLOAD_TOO_LARGE` classification.

### 2. Sandbox Isolation Degradation Risk
- **Risk:** Modifying launch routines could inadvertently weaken bubblewrap containment, drop namespace isolation flags, or introduce fallback execution paths that run unsandboxed on the host.
- **Mitigation:** Bubblewrap sandbox arguments are hardened and treated as mandatory on Linux. No fallback path to direct host process creation is permitted for sandboxed worker tasks. Unit tests explicitly verify sandbox argument construction and reject unsandboxed invocations.

### 3. Diagnostic Secret and Context Leakage Risk
- **Risk:** Detailed error logs generated when payloads exceed limits might dump full argument strings or environment variables to stderr or unencrypted log streams, exposing sensitive prompt text or credentials.
- **Mitigation:** Value-free error reporting. Diagnostics for `LAUNCH_PAYLOAD_TOO_LARGE` emit strictly numeric and structural metadata (number of arguments, number of environment entries, cumulative payload bytes, size of largest argument). Actual string contents and environment values are never included in failure evidence.

### 4. Compounding Feedback Loop Risk
- **Risk:** If a validation error contains full, unbounded process console dumps (e.g., hundreds of kilobytes of stack traces), embedding this into retry feedback will cause prompt packets to expand monotonically until hitting system limits.
- **Mitigation:** Hard bounding of console output excerpts to `PROCESS_OUTPUT_EXCERPT_HEAD_BYTES = 4000` and `PROCESS_OUTPUT_EXCERPT_TAIL_BYTES = 4000` with clear elision counts and pointers to immutable hash-chained log artifacts on disk.

### 5. Manifest Desynchronization and Oracle Tampering Risk
- **Risk:** `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` could diverge during editing, or producer agents might attempt to weaken journey definitions or remove acceptance check traces.
- **Mitigation:** Synchronized schema validation tests assert file equality and canonical structure. SHA-256 hash pinning ensures the manifest oracle cannot be tampered with during execution or evaluation phases.

### 6. Product Blast Radius Spillover Risk
- **Risk:** Orchestrator and harness changes might introduce unintended edits or build dependency changes into the core `sysdiff` C17 utility.
- **Mitigation:** Automated changed-path auditing before completion, combined with full execution of `make quality`, `make test`, and `scripts/smoke.sh`, guaranteeing zero alterations or regressions to `src/sysdiff.c`, `Makefile`, and man pages.
