# Overview

This document defines the normative repair contract for governed run `eb713e3103be`. In governed run `eb713e3103be`, execution stalled and failed during governance validation due to unaccounted spend caused by missing usage telemetry for the metered worker harness `codex_cli`. The orchestrator detected that steps executed under the metered worker runtime did not capture, emit, or aggregate mandatory resource and token consumption metrics, leaving computational expenditures unmetered and violating repository financial governance and auditability requirements.

The primary purpose of this repair slice is to resolve the missing usage telemetry failure by establishing robust, fail-closed telemetry capture and accounting mechanisms for the metered worker harness `codex_cli`. This guarantees that every worker invocation accurately records token usage (prompt tokens, completion tokens, cached tokens), model attribution, and execution duration in step execution records and audit artifacts, preventing unaccounted spend while strictly preserving the repository quality floor, write scope confinement, and the zero-telemetry architecture of the `sysdiff` utility.

The sealed evidence for the failure in governed run `eb713e3103be` is preserved in the sealed evidence directory:
`/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`

Required Outputs:
The required outputs of this repair slice across its execution lifecycle are:
1. `docs/repair_eb713e3103be-contract.md` (this repair contract, establishing the normative failure specification, required outputs, constraints, validation rules, routing intent, and acceptance checks under exact required headings).
2. `journeys/user_journeys_manifest.json` (the secondary user journey manifest, synchronized identically with the canonical test oracle and preserving all 21 required author, sysdiff, and sandbox journeys).
3. `tests/user_journeys_manifest.json` (the canonical repository-owned user journey manifest oracle, adhering strictly to `USER_JOURNEYS_MANIFEST_SCHEMA` and preserving all 21 required journeys).
4. Metered worker telemetry capture and spend accounting implementation (ensuring that invocations of `codex_cli` emit complete, structured telemetry records including token counts and execution metrics into governed step records without silent omissions).
5. Comprehensive automated regression tests under `tests/` verifying telemetry capture, spend accounting, manifest synchronization, and non-product blast radius containment.

Validation:
Validation for this repair slice enforces contract completeness, telemetry capture integrity, manifest synchronization, and non-regression:
- The contract document must exist at `docs/repair_eb713e3103be-contract.md` with substantive text (at least 120 non-whitespace characters) under each required heading: Overview, Problem, Constraints, and Acceptance Checks.
- Harness validation checks must confirm that all metered worker invocations (`codex_cli`) capture and record complete usage telemetry—including prompt tokens, completion tokens, total token expenditure, and model attribution—preventing unaccounted spend.
- Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA`.
- Every required journey in the manifest must trace via `traces_to` to an explicit acceptance check (`AC-1`, `AC-2`, or `AC-3`), with all acceptance checks covered.
- The existing pytest test suite and C build targets must pass cleanly without introducing regressions, unauthorized modifications to `src/sysdiff.c`, or telemetry hooks into the `sysdiff` product runtime.

Routing Intent:
This repair routes worker execution through verified, telemetry-capturing harness wrappers that guarantee accounting telemetry is recorded prior to step completion. When executing metered worker tasks under `codex_cli`, the orchestrator ensures that telemetry emission operates fail-closed: if token usage or execution metrics cannot be captured, the harness refuses to certify the step, preventing unmonitored or unaccounted spend from escaping into historical records. All file mutations across all repair steps must remain strictly confined within declared `allowed_paths`, preventing path escape violations. All sysdiff utility invocations route strictly through `build/sysdiff` directly without shell wrapper escapes.

# Problem

In governed run `eb713e3103be`, preserved in sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`, execution failed during governance accounting and step validation:
`unaccounted spend: missing usage telemetry for metered worker codex_cli`

Analysis of the failure and environmental root causes:

1. **Missing Usage Telemetry in Metered Worker Execution (`codex_cli`):**
   Agent-Orch governance relies on accurate, real-time resource accounting to track model token expenditure, runtime costs, and execution provenance across autonomous worker runs. For metered workers such as `codex_cli` (which invoke LLM APIs that incur financial cost per token), the execution harness is required to capture and emit structured usage telemetry for every prompt interaction and step execution. In run `eb713e3103be`, worker invocations completed tasks without returning or recording standard token usage statistics (prompt tokens, completion tokens, cached tokens, and associated model spend). Consequently, the orchestrator accounting validator encountered steps with unmetered execution, triggering an immediate fail-closed `unaccounted spend` refusal.

2. **Gaps in Harness Telemetry Aggregation and Reporting:**
   The failure in run `eb713e3103be` revealed a breakdown in the telemetry capture pipeline between the metered worker CLI (`codex_cli`) and the Agent-Orch step accounting ledger:
   - The worker harness failed to intercept or parse API usage metadata emitted by `codex_cli` upon completion.
   - Step accounting artifacts lacked required telemetry fields, causing post-step accounting validation to detect missing telemetry records.
   - Without mandatory usage telemetry, the system could not compute total run spend, reconcile worker budgets, or verify cost containment policies.

3. **Strict Separation Between Harness Telemetry and Product Runtime:**
   Under `product-definition.md` and `AGENTS.md`, `sysdiff` is an intentionally small, auditable C17 command-line utility built without telemetry, background daemons, or network dependencies. The telemetry failure in run `eb713e3103be` belongs entirely to the worker execution harness and orchestrator governance layer (`codex_cli`). The repair must resolve missing usage telemetry at the harness and accounting layer while strictly ensuring that zero telemetry, networking, or tracking code is introduced into `sysdiff` source files (`src/sysdiff.c`), Makefile rules, or runtime artifacts.

# Constraints

1. **Strict Write Scope Confinement:** All file modifications across all steps of this repair must remain strictly within declared `allowed_paths`. For this contract definition step (`step_01_define_slice_contract`), writes are strictly confined to `docs`, `tests/user_journeys_manifest.json`, and `journeys`. Step workers must never create unconfined scripts or temporary artifacts in the repository root or outside allowed paths. Any temporary notes, experimental scripts, or self-checks must reside exclusively in the orchestrator-designated scratch directory (`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch/97e798a99010/step_01_define_slice_contract/attempt-1`).
2. **Quality Floor Preservation:** Under `AGENTS.md`, release-quality software must pass rigorous verification including strict ISO C17 compiler flags (`-Wall -Wextra -Wpedantic -Werror`), clang-tidy, cppcheck, sanitizers (AddressSanitizer and UndefinedBehaviorSanitizer), and Valgrind. Repairing the worker telemetry capture or validation environment must never lower, disable, or bypass required quality checks.
3. **Preservation of Sealed Evidence:** The sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be` contains immutable historical run evidence and is strictly read-only. It must not be modified, deleted, inspected out of bounds, or self-certified.
4. **Harness-Only Telemetry Isolation (Zero Product Telemetry):** Telemetry capture mechanisms and spend accounting apply exclusively to the metered worker harness (`codex_cli`) and orchestrator governance artifacts. Under no circumstances may telemetry collection hooks, background threads, metric exporters, or network calls be introduced into `src/sysdiff.c`, Makefile binary packaging rules, or manual pages (`man/sysdiff.1`). `sysdiff` must remain an auditable, self-contained C17 executable with zero telemetry.
5. **User Journey Manifest Integrity and Synchronization:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects adhering strictly to `USER_JOURNEYS_MANIFEST_SCHEMA`. All 21 journeys—comprising the 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys—must be preserved verbatim without omission, reordering, or tampering.
6. **Acceptance Traceability and Command Allowlist:** Every required journey in the manifest must map via `traces_to` to at least one valid acceptance check ID (`AC-1`, `AC-2`, or `AC-3`). No journey may reference an undefined acceptance check, and no contract acceptance check may be left uncovered by required journeys. The manifest `command_allowlist` must remain strictly `["build/sysdiff"]`.
7. **Non-Product Blast Radius:** This repair applies exclusively to governance contracts, manifest synchronization, worker telemetry accounting, and validation tests. It must introduce zero modifications, regressions, or unauthorized alterations to `src/sysdiff.c`, Makefile binary targets, manual pages (`man/sysdiff.1`), or runtime CLI behavior.
8. **Closed Hazard Taxonomy:** Hazards identified in run `eb713e3103be` and this repair slice are classified strictly within the established repository taxonomy: `UNACCOUNTED_SPEND` (unaccounted spend resulting from missing usage telemetry for metered worker `codex_cli`), `TOOL_AVAILABILITY`, `EXECUTION_TIMEOUT`, `PATH_ESCAPE`, `RESULT_FABRICATION`, `ORACLE_TAMPERING`, and `BLAST_RADIUS`. No unauthorized hazard classes may be introduced.

# Acceptance Checks

- **AC-1** — **Contract Establishment, Document Integrity, and Write Scope Confinement:** The repair contract `docs/repair_eb713e3103be-contract.md` is established under required headings (Overview, Problem, Constraints, Acceptance Checks) with at least 120 non-whitespace characters per heading, citing sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/eb713e3103be`. All file mutations across repair steps strictly adhere to declared `allowed_paths` (`docs`, `tests/user_journeys_manifest.json`, `journeys`), ensuring that scratch files are confined to `.agent-orch-scratch/` and zero unauthorized files are created in the workspace root or outside allowed paths.
- **AC-2** — **Worker Usage Telemetry Capture and Unaccounted Spend Prevention (`codex_cli`):** The execution harness and validation environment ensure that usage telemetry for metered worker `codex_cli` is accurately captured, recorded, and verifiable, preventing unaccounted spend in governed runs. Worker invocations emit complete telemetry metadata (including token consumption, prompt/completion token accounting, model attribution, and execution duration) into governed step records and accounting artifacts, resolving the telemetry gap from run `eb713e3103be` while strictly maintaining that the `sysdiff` C17 utility binary remains completely free of telemetry, services, or runtime dependencies.
- **AC-3** — **User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are maintained as identical, valid JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA` and preserving all 21 required journeys. Every required journey maps via `traces_to` to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks. The full test suite passes cleanly, and zero modifications are introduced to `src/sysdiff.c`, Makefile binary targets, or manual pages (`man/sysdiff.1`).
