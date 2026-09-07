# Implementation Plan: Repair Governed Run eb713e3103be Telemetry Accounting

Contract Authority: `docs/repair_eb713e3103be-contract.md`  
Sealed Evidence Directory: `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`

# Architecture

Governed run `eb713e3103be` failed during governance validation due to unaccounted spend caused by missing usage telemetry for the metered worker harness `codex_cli`. The orchestrator detected that steps executed under the metered worker runtime did not capture, emit, or aggregate mandatory resource and token consumption metrics, leaving computational expenditures unmetered and violating repository financial governance and auditability requirements. This architectural plan establishes a robust, fail-closed telemetry capture and accounting pipeline for `codex_cli` worker invocations, integrates step-level and run-level token spend tracking, strictly confines file mutations within declared scopes, and preserves the absolute zero-telemetry invariant of the `sysdiff` C17 product binary.

### 1. Root Cause Analysis and Problem Decomposition

In governed run `eb713e3103be`, autonomous worker invocations executing under the metered worker harness `codex_cli` completed their assignments without capturing or emitting structured API token consumption metadata. In the Agent-Orch governance architecture:
- Metered workers incur direct financial expenditure per invocation (prompt tokens, completion tokens, cached tokens, and associated model rates).
- The orchestrator step validation pipeline includes a mandatory financial governance gate that checks step execution records for verifiable usage telemetry.
- When `codex_cli` completed without returning token usage metadata, the accounting validator encountered unmetered steps, immediately triggering a fail-closed `unaccounted spend: missing usage telemetry for metered worker codex_cli` validation failure.

The architectural breakdown revealed two key technical deficits:
1. **Lack of Harness-Level Interception:** The execution wrapper for `codex_cli` did not parse or extract token usage objects emitted in worker process output or structured adapter responses upon step termination.
2. **Missing Accounting Record Materialization:** Step validation artifacts and accounting ledgers were generated without mandatory telemetry fields (`prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`, `model`, and `duration_seconds`), preventing the orchestrator from calculating cumulative spend, verifying task budgets, or proving financial auditability.

### 2. Metered Worker Telemetry Capture Pipeline (`codex_cli`)

To resolve the root cause and prevent unaccounted spend, the worker execution harness is augmented with a deterministic, fail-closed telemetry capture pipeline:
- **Telemetry Extraction Hook:** Upon completion of any worker process executed under `codex_cli`, the harness intercepts the execution envelope and extracts token metrics from API response payloads or CLI execution logs.
- **Normalized Telemetry Schema:** Captured usage metrics are normalized into a standardized record schema:
  - `prompt_tokens` (integer, $\ge 0$): Number of tokens consumed in input prompts and context.
  - `completion_tokens` (integer, $\ge 0$): Number of tokens generated in model outputs.
  - `cached_tokens` (integer, $\ge 0$, optional/default 0): Number of tokens read from context caches.
  - `total_tokens` (integer, $\ge 0$): Sum of prompt and completion tokens.
  - `model` (non-empty string): The specific LLM model identifier attributed to the execution.
  - `wall_clock_seconds` (float, $> 0.0$): Measured execution duration of the worker invocation.
- **Fail-Closed Capture Guarantee:** If a worker invocation completes its file mutations but fails to provide valid, non-null usage telemetry, the harness marks the execution outcome as unverified and raises a typed validation failure `unaccounted spend: missing usage telemetry for metered worker codex_cli`. Unmetered spend is never permitted to pass silently or escape into historical ledgers.

### 3. Spend Accounting and Budget Reconciliation Architecture

The governance accounting layer aggregates telemetry from individual worker steps into run-level financial ledgers:
- **Step-Level Ledgers:** Each executed step writes a governed accounting record containing the normalized telemetry object alongside step metadata (step ID, attempt number, start time, end time).
- **Run-Level Aggregation:** The run accounting validator aggregates token totals across all completed steps, applies model-specific pricing coefficients, and computes cumulative monetary expenditure.
- **Budget Threshold Verification:** Aggregated spend is reconciled against pre-allocated mission and run budget ceilings. Exceeding budget ceilings or encountering missing telemetry records triggers an immediate halt, preventing financial drift.

### 4. Zero-Product Telemetry Invariant (`sysdiff` Isolation)

Under `AGENTS.md` and `architecture.md`, `sysdiff` is an auditable, lightweight C17 utility designed for deterministic offline snapshot comparison:
- **Absolute Boundary Separation:** Telemetry capture mechanisms, token counters, and spend accounting exist exclusively in the orchestrator harness layer (`agent_orch` Python harness, test oracles, and governance accounting validators).
- **Zero In-Product Telemetry:** No telemetry collection hooks, metric exporters, network sockets, background threads, or diagnostic logging services may be added to `src/sysdiff.c`, Makefile binary targets, or user manual pages (`man/sysdiff.1`). `sysdiff` remains a self-contained C17 binary with zero external dependencies and zero telemetry.

### 5. Write Scope Confinement and Governance Integrity

All file modifications across the repair lifecycle adhere strictly to Agent-Orch write scope rules:
- **Allowed Paths Discipline:** Writes in this planning step are confined exclusively to `plans/`. Downstream test authoring is confined to `tests/` and `journeys/`. Implementation steps are confined to declared harness and validation scopes.
- **Scratch Space Confinement:** All temporary exploratory scripts, self-checks, and transient test outputs reside exclusively within `.agent-orch-scratch/97e798a99010/`. No temporary files or ad-hoc scripts may ever be placed in the repository root or outside declared allowed paths.
- **Closed Hazard Taxonomy:** All failure modes and mitigations are classified within the 7 closed repository hazard categories: `UNACCOUNTED_SPEND`, `TOOL_AVAILABILITY`, `EXECUTION_TIMEOUT`, `PATH_ESCAPE`, `RESULT_FABRICATION`, `ORACLE_TAMPERING`, and `BLAST_RADIUS`.

### 6. User Journey Manifest Parity and Traceability

- Both `tests/user_journeys_manifest.json` (canonical test oracle) and `journeys/user_journeys_manifest.json` (secondary manifest) are maintained as identical JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA`.
- All 21 journeys—comprising the 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys—are preserved verbatim.
- Every journey maintains valid `traces_to` mapping to acceptance check IDs (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks. The command allowlist remains strictly `["build/sysdiff"]`.

# Tests

The test strategy provides rigorous regression verification across unit, integration, validation, and user journey layers. It proves that worker usage telemetry capture operates fail-closed, unaccounted spend is prevented, documents and manifests satisfy strict schema and formatting constraints, and the `sysdiff` product runtime is unaffected.

### 1. Concrete Test Implementation Plan

The regression test suite will be implemented in `tests/test_repair_eb713e3103be.py` covering all three contract acceptance checks:

#### A. Contract Establishment, Document Integrity, and Write Scope Confinement (AC-1)
- `test_repair_contract_headings_and_character_counts`:
  - Verify that `docs/repair_eb713e3103be-contract.md` exists and is readable.
  - Parse all ATX headings outside fenced code blocks and assert that each required heading (`Overview`, `Problem`, `Constraints`, `Acceptance Checks`) contains at least 120 non-whitespace characters in its scope.
  - Verify that `plans/repair_eb713e3103be-implementation-plan.md` exists with at least 120 non-whitespace characters under each required heading (`Architecture`, `Tests`, `Verification`, `Risks`).
- `test_sealed_evidence_reference_integrity`:
  - Assert that the contract explicitly cites `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be` as the immutable sealed evidence directory for run `eb713e3103be`.
  - Confirm the test suite does not modify or delete sealed evidence files.
- `test_closed_hazard_taxonomy_compliance`:
  - Assert that all 7 repository hazard categories (`UNACCOUNTED_SPEND`, `TOOL_AVAILABILITY`, `EXECUTION_TIMEOUT`, `PATH_ESCAPE`, `RESULT_FABRICATION`, `ORACLE_TAMPERING`, `BLAST_RADIUS`) are enumerated and adhered to in contract and plan documents.
- `test_write_scope_confinement_and_workspace_root_cleanliness`:
  - Verify that no unauthorized ad-hoc scripts (such as `generate_result.py`, `test_script.py`, or temporary scratch files) exist in the repository root.
  - Assert that step scratch operations are strictly confined within `.agent-orch-scratch/`.

#### B. Worker Usage Telemetry Capture and Spend Accounting (AC-2)
- `test_codex_cli_telemetry_schema_validation`:
  - Construct valid and invalid telemetry payload dictionaries.
  - Assert that the telemetry validator accepts complete records containing `prompt_tokens`, `completion_tokens`, `total_tokens`, `model`, and `wall_clock_seconds`.
  - Assert that negative token values, missing fields, non-numeric token counts, or empty model strings fail validation.
- `test_codex_cli_telemetry_capture_on_successful_execution`:
  - Mock or execute a metered worker invocation with simulated LLM response metadata.
  - Verify that the harness intercepts process completion, extracts token usage metrics, and populates the step execution record.
- `test_fail_closed_rejection_on_missing_usage_telemetry`:
  - Simulate a metered worker invocation where `codex_cli` completes with exit status 0 but emits no usage telemetry metadata.
  - Assert that the step validator refuses to certify the step, raising an explicit `unaccounted spend: missing usage telemetry for metered worker codex_cli` error.
- `test_fail_closed_rejection_on_partial_or_corrupted_telemetry`:
  - Simulate worker outputs with missing `prompt_tokens` or null `completion_tokens`.
  - Assert that partial telemetry is treated as unmetered spend and rejected fail-closed.
- `test_run_level_spend_aggregation_and_budget_reconciliation`:
  - Simulate a multi-step workflow with distinct token consumptions across multiple steps.
  - Verify that the accounting aggregator sums prompt tokens, completion tokens, and cached tokens correctly across steps.
  - Verify that cost calculations match model pricing tables and correctly flag budget overruns.
- `test_sysdiff_product_runtime_zero_telemetry_guarantee`:
  - Inspect `src/sysdiff.c`, `Makefile`, and `man/sysdiff.1` using static code analysis.
  - Assert that no telemetry symbols, HTTP/network headers, metrics libraries, background daemons, or tracking functions exist in `sysdiff` product sources.

#### C. User Journey Manifest Parity, Traceability, and Non-Product Blast Radius (AC-3)
- `test_user_journeys_manifests_are_synchronized`:
  - Load `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`.
  - Assert bit-for-bit or parsed JSON object equality between both files.
- `test_user_journeys_manifest_schema_and_command_allowlist`:
  - Validate the parsed manifest against `USER_JOURNEYS_MANIFEST_SCHEMA` using a Draft 2020-12 validator.
  - Assert that `command_allowlist` is strictly `["build/sysdiff"]`.
- `test_user_journeys_manifest_preserves_all_21_journeys`:
  - Verify that exactly 21 journeys are declared in the manifest.
  - Confirm the presence of the 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys.
- `test_journey_traceability_to_contract_acceptance_checks`:
  - Extract all `traces_to` identifiers from every manifest journey.
  - Verify that every declared acceptance check (`AC-1`, `AC-2`, `AC-3`) is covered by at least one journey.
  - Verify that no journey references an undefined acceptance check ID.
- `test_sysdiff_c17_build_and_quality_floor`:
  - Compile `build/sysdiff` using strict C17 flags (`-Wall -Wextra -Wpedantic -Werror -std=c17`).
  - Run `make test`, `scripts/smoke.sh`, and `tests/test_sysdiff_fixture.sh` to confirm zero build or functional regressions.
- `test_sysdiff_cli_behavior_unaltered`:
  - Execute `build/sysdiff` with no arguments, verifying exit status 2 and usage guidance on stderr.
  - Execute `build/sysdiff --help` and `build/sysdiff --version`, verifying exit status 0 and expected text.
  - Execute `build/sysdiff compare` with valid and malformed snapshot fixtures, verifying deterministic diffs and escaped error diagnostics.

---

### 2. Contract Acceptance Check Traceability Matrix

| Acceptance Check | User Journey Mapping | Concrete Implementation Plan Item | Concrete Test Item | Verification Oracle & Gate | Blast Radius Boundary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AC-1** — Contract Establishment, Document Integrity, and Write Scope Confinement | 1. User reads journey contract confirming manifest is a usable named oracle<br>2. User supplies malformed journey data receiving fail-closed validation<br>3. User runs governed check from unrelated directory without changing path meaning<br>4. User observes allowlisted smoke argv prefix re-executed directly<br>5. User confirms required journey authority retained on repair<br>6. User follows every AC trace seeing exploratory coverage supplementary | - Establish `docs/repair_eb713e3103be-contract.md` with $\ge 120$ non-ws chars per heading<br>- Author `plans/repair_eb713e3103be-implementation-plan.md` with $\ge 120$ non-ws chars per heading<br>- Cite sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`<br>- Strictly confine mutations to declared `allowed_paths`<br>- Confine scratch work to `.agent-orch-scratch/97e798a99010/` | `test_repair_contract_headings_and_character_counts`<br>`test_sealed_evidence_reference_integrity`<br>`test_closed_hazard_taxonomy_compliance`<br>`test_write_scope_confinement_and_workspace_root_cleanliness` | `agent_orch.validators._run_markdown_headings_rule`<br>`git status --porcelain`<br>Scratch directory confinement check | Writes strictly confined to `plans/` (current step), `docs/`, `tests/`, `journeys/`; zero root pollutions |
| **AC-2** — Worker Usage Telemetry Capture and Unaccounted Spend Prevention (`codex_cli`) | 7. User retries after producer narrowing and pinned oracle rejects tampering<br>8. User reviews result reporting every journey with concrete steps and evidence<br>17. Operator observes pre-exec payload measurement rejecting oversized arguments<br>18. Evaluator inspects edge-case payload sizes near 128 KiB boundary | - Implement harness interception for `codex_cli` execution output<br>- Parse token metrics (`prompt_tokens`, `completion_tokens`, `cached_tokens`, `total_tokens`, `model`, `wall_clock_seconds`)<br>- Enforce fail-closed validator error `unaccounted spend: missing usage telemetry for metered worker codex_cli`<br>- Reconcile step-level spend against run budgets<br>- Maintain zero product telemetry in `sysdiff` | `test_codex_cli_telemetry_schema_validation`<br>`test_codex_cli_telemetry_capture_on_successful_execution`<br>`test_fail_closed_rejection_on_missing_usage_telemetry`<br>`test_fail_closed_rejection_on_partial_or_corrupted_telemetry`<br>`test_run_level_spend_aggregation_and_budget_reconciliation`<br>`test_zero_telemetry_in_sysdiff_product_runtime` | Step accounting validator gate<br>Spend ledger verification<br>Static AST/grep check on `src/sysdiff.c` | Metered worker harness and governance accounting only; zero telemetry hooks or code changes in `src/sysdiff.c` |
| **AC-3** — User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius | 9. User runs deterministic smoke chain<br>10. User confirms workspace abstraction remains additive<br>11. User runs sysdiff with no args<br>12. User asks sysdiff for help<br>13. User compares two snapshots with sysdiff<br>14. User gives sysdiff malformed snapshot<br>15. Worker launcher delivers large prompt payloads<br>16. User confirms bwrap sandbox containment<br>19. Validator bounds process output in retry feedback<br>20. Maintainer verifies synchronized manifest schema & AC coverage<br>21. Developer runs sysdiff test suite and smoke verification | - Synchronize `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` identically<br>- Preserve all 21 required journeys verbatim<br>- Ensure every journey maps via `traces_to` to AC-1, AC-2, or AC-3<br>- Keep `command_allowlist` strictly `["build/sysdiff"]`<br>- Execute full pytest suite and C build quality gates without regressions | `test_user_journeys_manifests_are_synchronized`<br>`test_user_journeys_manifest_schema_and_command_allowlist`<br>`test_user_journeys_manifest_preserves_all_21_journeys`<br>`test_journey_traceability_to_contract_acceptance_checks`<br>`test_sysdiff_c17_build_and_quality_floor`<br>`test_sysdiff_cli_behavior_unaltered` | `jsonschema.Draft202012Validator`<br>`python3 -m pytest tests/ -q`<br>`scripts/smoke.sh`<br>`make test`<br>`make quality` | Complete immutability of `src/sysdiff.c`, `Makefile`, and `man/sysdiff.1`; zero CLI behavioral changes |

# Verification

The verification protocol executes in sequential, deterministic stages to validate that all contract acceptance checks are fully met, all telemetry accounting rules operate fail-closed, and no regressions or blast radius leaks occur.

### 1. Verification Protocol Steps and Execution Sequence

1. **Pre-Execution Write Scope Audit:**
   - Execute `git status --porcelain` to verify that no unauthorized files have been created in the repository root or outside declared allowed paths.
   - Confirm that all transient scratch files reside exclusively within `/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch/97e798a99010/step_03_plan_slice_delivery/attempt-1/`.

2. **Document Structure and Heading Character Floor Validation:**
   - Run structural validation on `docs/repair_eb713e3103be-contract.md` asserting that each required heading (`Overview`, `Problem`, `Constraints`, `Acceptance Checks`) has $\ge 120$ non-whitespace characters.
   - Run structural validation on `plans/repair_eb713e3103be-implementation-plan.md` asserting that each required heading (`Architecture`, `Tests`, `Verification`, `Risks`) has $\ge 120$ non-whitespace characters.
   - Confirm citation of sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`.

3. **User Journey Manifest Synchronization and Schema Conformance Gate:**
   - Run `diff -u tests/user_journeys_manifest.json journeys/user_journeys_manifest.json` to prove bit-for-bit equivalence.
   - Validate manifests against `USER_JOURNEYS_MANIFEST_SCHEMA` using `jsonschema.Draft202012Validator`.
   - Verify that exactly 21 journeys exist and that every journey maps via `traces_to` to at least one valid acceptance check (`AC-1`, `AC-2`, `AC-3`), with zero unmapped acceptance checks.
   - Confirm that `command_allowlist` is strictly `["build/sysdiff"]`.

4. **Focused Telemetry Accounting Regression Suite Execution:**
   - Run the dedicated repair test suite under pytest with bytecode generation disabled:
     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repair_eb713e3103be.py -v
     ```
   - Confirm 100% pass rate with zero skips, errors, or unhandled exceptions.

5. **Full Repository Pytest Suite Execution:**
   - Run the entire automated test suite from the repository root:
     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q
     ```
   - Assert clean exit (code 0) across all test modules (governed workspace abstraction, commissioning dependencies, prior run repairs, permguard, pathaudit, bwrap argmax, and sysdiff).

6. **Deterministic C Toolchain Smoke and Quality Gate Verification:**
   - Execute the standard smoke verification chain:
     ```bash
     ./scripts/smoke.sh
     ```
   - Compile and test the `sysdiff` utility under strict ISO C17 compiler flags:
     ```bash
     make clean && make test
     ```
   - Execute the full quality target surface:
     ```bash
     make check
     ```
   - Confirm `build/sysdiff` builds cleanly without warnings and passes all snapshot comparison, edge-case, and malformed input test fixtures.

7. **Zero-Product Blast Radius Audit:**
   - Run `git diff --check` to ensure no whitespace or formatting errors.
   - Run `git diff --name-only` against the baseline checkout.
   - Assert that `src/sysdiff.c`, `Makefile`, and `man/sysdiff.1` remain completely unmodified.

# Risks

Managing technical, governance, and operational risks is critical to ensuring that the repair resolves the root cause without introducing side effects or regressions.

### 1. Inadvertent Product Telemetry Contamination Risk
- **Risk:** Developers or autonomous agents might attempt to resolve the missing telemetry failure by adding logging, metric collection, or telemetry libraries directly to `src/sysdiff.c` or its Makefile targets.
- **Impact:** Violates the foundational architectural constraint in `AGENTS.md` and `product-definition.md` that `sysdiff` must remain an intentionally small, auditable, dependency-free C17 utility with zero telemetry.
- **Mitigation:** Strict structural separation. Telemetry capture hooks are restricted to the worker harness wrapper (`codex_cli`) and Agent-Orch accounting ledgers. Static analysis checks in regression tests inspect `src/sysdiff.c` and reject any network symbols, telemetry hooks, or metrics collection functions.

### 2. Partial Telemetry and Silent Unmetered Spend Escapes Risk
- **Risk:** A worker invocation might return partial telemetry (for instance, prompt tokens without completion tokens, or token counts without model attribution) that an overly permissive parser might accept, allowing unmetered spend to escape undetected.
- **Impact:** Causes accounting discrepancies in run-level financial tracking and fails downstream governance validation.
- **Mitigation:** Fail-closed validation rules. The telemetry parser validates against a strict schema requiring all mandatory fields (`prompt_tokens`, `completion_tokens`, `total_tokens`, `model`, `wall_clock_seconds`). Any missing, null, or non-numeric field causes immediate validation refusal with the typed diagnostic `unaccounted spend: missing usage telemetry for metered worker codex_cli`.

### 3. Path Escape and Write Scope Violation Risk (`PATH_ESCAPE`)
- **Risk:** Generating test fixtures, telemetry mock files, or simulation results directly in the repository root or outside declared allowed paths will trigger an immediate fatal path escape failure.
- **Impact:** Immediate step failure enforced by orchestrator write-scope confinement.
- **Mitigation:** All transient files, experimental scripts, and self-checks must be strictly confined to the orchestrator-designated scratch directory (`.agent-orch-scratch/97e798a99010/`). Production code modifications must strictly stay within the declared `allowed_paths` for each step.

### 4. Manifest Desynchronization and Oracle Tampering Risk (`ORACLE_TAMPERING`)
- **Risk:** Modifying `tests/user_journeys_manifest.json` without synchronizing `journeys/user_journeys_manifest.json`, altering journey definitions, or removing acceptance check traces.
- **Impact:** Violates manifest schema integrity, invalidates test oracles, and triggers validation failure.
- **Mitigation:** Synchronized manifest validation asserts exact identity between both manifest files. Schema validation confirms adherence to `USER_JOURNEYS_MANIFEST_SCHEMA`. Traceability assertions ensure all 21 required journeys are preserved verbatim and map to valid acceptance check IDs.

### 5. Quality Floor Degradation Risk
- **Risk:** Modifying compiler flags, disabling strict warning levels (`-Wall -Wextra -Wpedantic -Werror`), or bypassing sanitizers/Valgrind to work around test failures.
- **Impact:** Subverts the repository craftsmanship standard defined in `AGENTS.md`.
- **Mitigation:** Make targets and quality gates are immutable under this repair slice. All verification steps require clean runs of `make test`, `scripts/smoke.sh`, and `make check` without flag alterations or relaxed warnings.
