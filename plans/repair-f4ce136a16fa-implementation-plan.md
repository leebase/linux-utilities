# Implementation Plan: Repair Governed Run f4ce136a16fa (Test Harness Decontamination and Regression Restoration)

Contract Authority: `docs/repair-f4ce136a16fa-contract.md`  
Sealed Evidence Directory: `/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa`

# Architecture

Governed run `f4ce136a16fa` failed during slice implementation at step `step_05_implement_slice`. The trusted failure evidence recorded: `Command failed: python3 -m pytest tests/test_repair_b8bf0e7c59d5.py: test_python_test_harness_decontamination`. In that run, execution attempted to satisfy slice repairs but left foreign project paths and unauthorized run-directory bypasses in the repository's test harness, causing the regression oracle `tests/test_repair_b8bf0e7c59d5.py` to fail fail-closed.

Under repository operating rules in `AGENTS.md` and core architectural principles in `architecture.md`, `sysdiff` is built as an auditable, minimal, self-contained ISO C17 command-line utility with zero hidden runtime behavior, zero foreign repository coupling, and zero unmanaged runtime dependencies. Testing and governance harnesses must adhere strictly to these architectural boundaries: test files must remain strictly isolated within `linux-utilities` and declared runtime dependencies, resolving packages solely through standard Python site-packages and approved platform paths (such as `/home/lee/projects/agent-orch/src`). Test modules must never inject foreign project directories (specifically `/home/lee/projects/employee-contract/src`) into `sys.path`, nor introduce unauthorized bypasses for sibling run directories (`/home/lee/projects/linux-utilities-agent-orch-runs/`) to mask baseline dependency failures.

This architectural implementation plan establishes the complete decontamination of the Python test harness, excises all foreign repository paths from `sys.path`, removes unauthorized run-directory bypasses from dependency tests, guarantees that `tests/test_repair_b8bf0e7c59d5.py` and the entire test suite pass cleanly, preserves synchronized user journey manifests, and maintains strict non-product blast radius confinement and ISO C17 product fidelity.

### 1. Concrete Plan Items Mapped to Contract Acceptance Checks

The architecture maps directly to the three normative acceptance checks declared in `docs/repair-f4ce136a16fa-contract.md`:

- **Plan Item 1 (Covering AC-1 — Contract Establishment, Document Integrity, and Write Scope Confinement):**
  - Maintain the normative repair contract `docs/repair-f4ce136a16fa-contract.md` under required headings (`Overview`, `Problem`, `Constraints`, `Acceptance Checks`) with at least 120 non-whitespace characters per heading, citing immutable sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa`.
  - Establish this implementation plan `plans/repair-f4ce136a16fa-implementation-plan.md` under required headings (`Architecture`, `Tests`, `Verification`, `Risks`) with at least 120 non-whitespace characters per heading.
  - Enforce strict write scope confinement: during the current planning step (`step_03_plan_slice_delivery`), file modifications are strictly confined to `plans/`. Downstream implementation steps must strictly adhere to declared `allowed_paths` (`docs`, `tests`, `journeys`).
  - Restrict all transient scratch operations, temporary notes, and self-checks exclusively to orchestrator-designated scratch space (`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch/7581beae0012/step_03_plan_slice_delivery/attempt-1`). Ensure zero untracked files or scratch scripts pollute the workspace root.
  - Maintain strict compliance with the closed repository hazard taxonomy: `BLAST_RADIUS`, `ORACLE_TAMPERING`, `RESULT_FABRICATION`, `PATH_ESCAPE`, `TOOL_AVAILABILITY`, and `EXECUTION_TIMEOUT`.

- **Plan Item 2 (Covering AC-2 — Test Harness Decontamination and Regression Suite Restoration):**
  - Completely eliminate all foreign repository paths (specifically `/home/lee/projects/employee-contract/src`) from `sys.path` across all test modules in `tests/`, specifically in `tests/test_governed_run_17ca9404991a_repair.py`, `tests/test_governed_workspace_abstraction.py`, and `tests/test_commissioning_dependencies.py`.
  - Excise unauthorized run-directory bypasses (`/home/lee/projects/linux-utilities-agent-orch-runs/`) from `tests/test_commissioning_dependencies.py`, restoring clean dependency validation against committed baselines without hardcoded exemptions.
  - Restore the regression test suite in `tests/test_repair_b8bf0e7c59d5.py` to a 100% clean passing state under pytest, verifying that both `test_python_test_harness_decontamination` and `test_commissioning_dependencies_no_run_bypass` succeed without errors.
  - Preserve the non-product blast radius boundary: introduce zero modifications, regressions, or alterations to production ISO C17 source code (`src/sysdiff.c`), Makefile binary targets, manual pages (`man/sysdiff.1`), or user documentation (`README.md`, `CHANGELOG.md`), safeguarding smoke oracle hash pins.

- **Plan Item 3 (Covering AC-3 — User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius):**
  - Maintain exact bit-for-bit and parsed JSON synchronization between `tests/user_journeys_manifest.json` (canonical test oracle) and `journeys/user_journeys_manifest.json` (secondary manifest).
  - Preserve all 21 required user journeys verbatim (10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys), adhering strictly to `USER_JOURNEYS_MANIFEST_SCHEMA`.
  - Ensure every journey in the manifest maps via `traces_to` to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks.
  - Keep `command_allowlist` strictly pinned to `["build/sysdiff"]`.
  - Verify that the full pytest suite (`python3 -m pytest tests/`) and C build quality targets (`make test`, `make quality`, `scripts/smoke.sh`) pass cleanly without product regressions.

### 2. Test Harness Decontamination and Clean sys.path Architecture

In the failed run `f4ce136a16fa`, test files contained foreign import path injections:
```python
for _extra_path in (
    "/home/lee/projects/employee-contract/src",  # FOREIGN LEAK
    "/home/lee/.local/lib/python3.12/site-packages",
):
```
The inclusion of `/home/lee/projects/employee-contract/src` introduces severe cross-project coupling, dependency contamination, and false test passes from unrelated modules. Under repository rules, test execution must remain hermetic and self-contained within `linux-utilities` and declared runtime dependencies.

The architectural solution mandates:
1. Complete removal of `"/home/lee/projects/employee-contract/src"` from `tests/test_governed_run_17ca9404991a_repair.py` and `tests/test_governed_workspace_abstraction.py`.
2. Python imports must resolve packages strictly from standard Python site-packages and approved platform paths (`/home/lee/projects/agent-orch/src`), ensuring zero cross-project leakage.
3. Automated static scanning in `tests/test_repair_b8bf0e7c59d5.py` will actively inspect all `.py` files under `tests/` and assert that no active line references `employee-contract`.

### 3. Excision of Run-Directory Bypasses in Dependency Validation

In `tests/test_commissioning_dependencies.py`, the test `test_declared_packet_inputs_all_exist_in_committed_baselines` previously contained an ad-hoc bypass:
```python
if candidate.as_posix().startswith(
    "/home/lee/projects/linux-utilities-agent-orch-runs/"
):
    continue
```
This bypass allowed uncommitted run directory files to satisfy validation checks, violating the repository invariant that commissioning artifacts must be verifiable against committed baselines alone. Under `AGENTS.md` and repository operating rules, test modules must never poke into uncommitted run directories or hardcode exemptions to satisfy validation gates.

The architectural solution mandates:
1. Complete removal of the `linux-utilities-agent-orch-runs` bypass block from `tests/test_commissioning_dependencies.py`.
2. Verification that all declared inputs are evaluated cleanly and strictly against committed baselines without special exemptions.
3. Verification via `test_commissioning_dependencies_no_run_bypass` that `/home/lee/projects/linux-utilities-agent-orch-runs/` does not appear anywhere in `tests/test_commissioning_dependencies.py`.

### 4. Non-Product Blast Radius and Quality Floor Preservation

To satisfy `AC-2` and `AC-3` while protecting smoke oracle hash pins:
- This repair slice applies strictly to test harness decontamination, regression test restoration, manifest synchronization, and governance documentation.
- `src/sysdiff.c` remains pristine ISO C17 source code, preserving its compile-time limits (`SYSDIFF_MAX_LINE_BYTES == 65536`, `SYSDIFF_MAX_SNAPSHOT_ENTRIES == 65536`, 16 MiB total-byte limit), memory ownership model, and three-state exit status contract.
- `src/sysdiff.c`, `Makefile`, `README.md`, `man/sysdiff.1`, and `CHANGELOG.md` must not be modified during this repair. File hashes must match the baseline smoke oracle pins (`BASELINE_SYSDIFF_SHA256` and `BASELINE_MAKEFILE_SHA256`).
- All quality gates defined in `AGENTS.md`—including strict ISO C17 builds with `-Wall -Wextra -Wpedantic -Werror`, clang-tidy, cppcheck, sanitizers (ASan and UBSan), Valgrind, and unit/integration tests—remain fully intact and unenfeebled.

# Tests

The testing strategy establishes rigorous multi-layered regression verification across document integrity, test harness cleanliness, dependency validation purity, manifest synchronization, and full test suite execution.

### 1. Concrete Test Implementation Plan

#### Test Suite for AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement
1. `test_repair_contract_headings_and_character_counts`:
   - Inspect `docs/repair-f4ce136a16fa-contract.md`.
   - Parse all ATX headings outside fenced code blocks using `_parse_markdown_headings`.
   - Assert that each required heading (`Overview`, `Problem`, `Constraints`, `Acceptance Checks`) exists and contains $\ge 120$ non-whitespace characters.
2. `test_implementation_plan_headings_and_character_counts`:
   - Inspect `plans/repair-f4ce136a16fa-implementation-plan.md`.
   - Parse all ATX headings outside fenced code blocks.
   - Assert that each required heading (`Architecture`, `Tests`, `Verification`, `Risks`) exists and contains $\ge 120$ non-whitespace characters.
3. `test_sealed_evidence_reference_integrity`:
   - Assert that both `docs/repair-f4ce136a16fa-contract.md` and `plans/repair-f4ce136a16fa-implementation-plan.md` explicitly reference the sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa`.
   - Verify that all test procedures treat the sealed evidence directory as read-only.
4. `test_write_scope_confinement_and_clean_workspace_root`:
   - Inspect the workspace root for untracked scratch files, temporary snapshots, or generator scripts.
   - Assert that all temporary test outputs, scratch notes, and validation files reside exclusively in `.agent-orch-scratch/`.
5. `test_closed_hazard_taxonomy_compliance`:
   - Verify that all failure classifications in the contract and implementation plan conform strictly to the closed hazard taxonomy: `BLAST_RADIUS`, `ORACLE_TAMPERING`, `RESULT_FABRICATION`, `PATH_ESCAPE`, `TOOL_AVAILABILITY`, and `EXECUTION_TIMEOUT`.

#### Test Suite for AC-2: Test Harness Decontamination and Regression Suite Restoration
1. `test_python_test_harness_decontamination`:
   - Scan target test modules: `tests/test_governed_run_17ca9404991a_repair.py`, `tests/test_governed_workspace_abstraction.py`, and `tests/test_commissioning_dependencies.py`.
   - Assert that foreign path marker `/home/lee/projects/employee-contract` does not appear on any active (non-comment) line.
   - Verify that `tests/test_repair_b8bf0e7c59d5.py::test_python_test_harness_decontamination` passes cleanly under pytest.
2. `test_commissioning_dependencies_no_run_bypass`:
   - Read `tests/test_commissioning_dependencies.py`.
   - Assert that the string `"/home/lee/projects/linux-utilities-agent-orch-runs/"` is completely absent from the file.
   - Verify that `tests/test_repair_b8bf0e7c59d5.py::test_commissioning_dependencies_no_run_bypass` passes cleanly under pytest.
3. `test_sysdiff_c17_source_has_no_proc_or_hidden_runtime_hooks`:
   - Scan `src/sysdiff.c` to confirm absence of process sniffing, `/proc` queries, `getppid`, or `/tmp/.sysdiff_call` hooks.
4. `test_sysdiff_c17_compilation_and_strict_flags`:
   - Verify that `src/sysdiff.c` compiles warning-free under GCC and Clang with strict flags (`-std=c17 -Wall -Wextra -Wpedantic -Werror -O2`).
5. `test_sysdiff_compare_three_state_exit_contract`:
   - Verify 3-state exit status contract: status 0 for identical snapshots (`no changes\n`), status 1 for differing snapshots (sorted diff lines), and status 2 for missing or malformed snapshots.
6. `test_smoke_oracle_hash_pin_integrity`:
   - Verify that SHA-256 hashes of `src/sysdiff.c` and `Makefile` exactly match `BASELINE_SYSDIFF_SHA256` and `BASELINE_MAKEFILE_SHA256`.

#### Test Suite for AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius
1. `test_user_journeys_manifests_are_synchronized`:
   - Read `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`.
   - Assert that both files parse to identical JSON data structures.
2. `test_user_journeys_manifest_schema_conformance`:
   - Validate both manifest files against `USER_JOURNEYS_MANIFEST_SCHEMA` using `jsonschema.Draft202012Validator`.
   - Assert zero schema errors.
3. `test_user_journeys_manifest_preserves_all_21_journeys`:
   - Assert that the manifest contains exactly 21 journeys: 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys.
4. `test_user_journeys_command_allowlist`:
   - Assert that `command_allowlist` is strictly `["build/sysdiff"]`.
5. `test_journey_traceability_to_contract_acceptance_checks`:
   - Verify that every declared acceptance check (`AC-1`, `AC-2`, `AC-3`) is covered by at least one journey in `traces_to`.
   - Verify that no journey contains a trace to an undefined acceptance check ID.
6. `test_full_suite_and_smoke_pass_without_regression`:
   - Execute `python3 -m pytest tests/ -q` and verify exit code 0.
   - Execute `scripts/smoke.sh` and verify exit code 0.
   - Execute `make test` and `make quality` and verify clean exits.

---

### 2. Acceptance Check Traceability Matrix

Every acceptance check declared in `docs/repair-f4ce136a16fa-contract.md` is mapped to concrete plan items, concrete test implementations, verification oracles, and blast radius boundaries in the matrix below:

| Acceptance Check ID | Contract Acceptance Check Description | User Journey Mapping | Concrete Implementation Plan Item | Concrete Test Implementation | Verification Oracle & Gate | Blast Radius Boundary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AC-1** | **Contract Establishment, Document Integrity, and Write Scope Confinement:** The repair contract `docs/repair-f4ce136a16fa-contract.md` is established under required headings (Overview, Problem, Constraints, Acceptance Checks) with at least 120 non-whitespace characters per heading, citing sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa`. All file mutations across repair steps strictly adhere to declared `allowed_paths` (`docs`, `tests`, `journeys`), ensuring that scratch files are confined to `.agent-orch-scratch/` and zero unauthorized files are created in the workspace root or outside allowed paths. | 1. User reads journey contract confirming manifest is a usable named oracle<br>2. User supplies malformed journey data receiving fail-closed validation<br>3. User runs governed check from unrelated directory without changing path meaning<br>4. User observes allowlisted smoke argv prefix re-executed directly<br>5. User confirms required journey authority retained on repair<br>6. User follows every AC trace seeing exploratory coverage supplementary<br>15. Worker launcher delivers large prompt payloads via stdin<br>16. User confirms bubblewrap sandbox containment | - Establish and maintain `docs/repair-f4ce136a16fa-contract.md` with $\ge 120$ non-ws characters per heading (`Overview`, `Problem`, `Constraints`, `Acceptance Checks`)<br>- Author `plans/repair-f4ce136a16fa-implementation-plan.md` with $\ge 120$ non-ws characters per heading (`Architecture`, `Tests`, `Verification`, `Risks`)<br>- Explicitly cite sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa`<br>- Enforce write confinement to `plans/` in planning step and declared paths in implementation steps<br>- Restrict scratch files to `.agent-orch-scratch/7581beae0012/` | `test_repair_contract_headings_and_character_counts`<br>`test_implementation_plan_headings_and_character_counts`<br>`test_sealed_evidence_reference_integrity`<br>`test_write_scope_confinement_and_clean_workspace_root`<br>`test_closed_hazard_taxonomy_compliance` | `_run_markdown_headings_rule`<br>`git status --porcelain`<br>Scratch directory confinement validator | Writes strictly confined to `plans/` (planning step), `docs/`, `tests/`, `journeys/`; zero untracked root pollutions |
| **AC-2** | **Test Harness Decontamination and Regression Suite Restoration:** The repair eliminates all foreign repository paths (specifically `/home/lee/projects/employee-contract/src`) from `sys.path` in all test modules (including `tests/test_governed_run_17ca9404991a_repair.py` and `tests/test_governed_workspace_abstraction.py`) and excises unauthorized run-directory bypasses from `tests/test_commissioning_dependencies.py`. The regression test suite in `tests/test_repair_b8bf0e7c59d5.py` passes cleanly under pytest with `test_python_test_harness_decontamination` succeeding, maintaining strict non-product blast radius boundaries and preserving production C17 code. | 7. User retries after producer narrowing and pinned oracle rejects tampering<br>8. User reviews result reporting every journey with concrete steps and evidence<br>17. Operator observes pre-exec payload measurement rejecting oversized arguments<br>18. Evaluator inspects edge-case payload sizes near 128 KiB boundary | - Completely excise `employee-contract` path from `sys.path` in `tests/test_governed_run_17ca9404991a_repair.py` and `tests/test_governed_workspace_abstraction.py`<br>- Excise unauthorized run-directory bypass from `tests/test_commissioning_dependencies.py`<br>- Ensure `tests/test_repair_b8bf0e7c59d5.py` passes cleanly under pytest<br>- Maintain production C17 source (`src/sysdiff.c`), Makefile, and man page integrity matching baseline hashes<br>- Verify three-state exit status contract without binary modification | `test_python_test_harness_decontamination`<br>`test_commissioning_dependencies_no_run_bypass`<br>`test_sysdiff_c17_source_has_no_proc_or_hidden_runtime_hooks`<br>`test_sysdiff_c17_compilation_and_strict_flags`<br>`test_sysdiff_compare_three_state_exit_contract`<br>`test_smoke_oracle_hash_pin_integrity` | `pytest tests/test_repair_b8bf0e7c59d5.py`<br>Static token scanning on test files<br>Smoke oracle hash verification (`BASELINE_SYSDIFF_SHA256`, `BASELINE_MAKEFILE_SHA256`) | Test files and governance manifests only; zero modifications to `src/sysdiff.c`, `Makefile`, or `man/sysdiff.1` |
| **AC-3** | **User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are maintained as identical, valid JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA` and preserving all 21 required journeys. Every required journey maps via `traces_to` to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks. The full test suite passes cleanly, and zero modifications are introduced to `src/sysdiff.c`, Makefile binary targets, or manual pages (`man/sysdiff.1`). | 9. User runs deterministic smoke chain<br>10. User confirms workspace abstraction remains additive<br>11. User runs sysdiff with no args<br>12. User asks sysdiff for help<br>13. User compares two snapshots with sysdiff<br>14. User gives sysdiff malformed snapshot<br>19. Validator bounds process output in retry feedback<br>20. Maintainer verifies synchronized manifest schema & AC coverage<br>21. Developer runs sysdiff test suite and smoke verification | - Synchronize `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` bit-for-bit<br>- Preserve all 21 required author, sysdiff, and sandbox journeys verbatim<br>- Enforce full schema compliance with `USER_JOURNEYS_MANIFEST_SCHEMA`<br>- Ensure every journey maps via `traces_to` to AC-1, AC-2, or AC-3<br>- Retain immutable command allowlist `["build/sysdiff"]`<br>- Execute full pytest suite and C smoke/quality targets cleanly | `test_user_journeys_manifests_are_synchronized`<br>`test_user_journeys_manifest_schema_conformance`<br>`test_user_journeys_manifest_preserves_all_21_journeys`<br>`test_user_journeys_command_allowlist`<br>`test_journey_traceability_to_contract_acceptance_checks`<br>`test_full_suite_and_smoke_pass_without_regression` | `jsonschema.Draft202012Validator`<br>`python3 -m pytest tests/ -q`<br>`scripts/smoke.sh`<br>`make test`<br>`make quality` | Manifest synchronization and full regression suite clean pass; zero foreign dependencies, zero test-suite regressions |

# Verification

The verification protocol defines a deterministic sequence of validation stages to prove that all acceptance checks are completely satisfied, the test harness is decontaminated, manifests are synchronized, and no regressions or blast radius violations exist.

### 1. Step-by-Step Verification Protocol

1. **Pre-Execution Write Scope and Workspace Cleanliness Audit:**
   - Execute `git status --porcelain` to verify that all modifications strictly adhere to declared `allowed_paths` (`plans/` for the current planning step).
   - Confirm that no temporary files, ad-hoc scripts, or untracked snapshot files exist in the repository root.
   - Confirm that all transient scratch operations are strictly confined within `.agent-orch-scratch/7581beae0012/step_03_plan_slice_delivery/attempt-1/`.

2. **Document Heading and Character Floor Validation:**
   - Run markdown heading validation on `docs/repair-f4ce136a16fa-contract.md` asserting that each required heading (`Overview`, `Problem`, `Constraints`, `Acceptance Checks`) exists and has $\ge 120$ non-whitespace characters.
   - Run markdown heading validation on `plans/repair-f4ce136a16fa-implementation-plan.md` asserting that each required heading (`Architecture`, `Tests`, `Verification`, `Risks`) exists and has $\ge 120$ non-whitespace characters.
   - Verify explicit citation of sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/f4ce136a16fa`.

3. **Static Test Harness Cleanliness Inspection:**
   - Run static grep inspection across `tests/` asserting 0 matches for:
     ```bash
     grep -rn "employee-contract" tests/
     ```
   - Assert that no active line in any test file modifies `sys.path` to include foreign project directories.
   - Run static grep inspection on `tests/test_commissioning_dependencies.py` asserting 0 matches for:
     ```bash
     grep -rn "linux-utilities-agent-orch-runs" tests/test_commissioning_dependencies.py
     ```
   - Confirm that the unauthorized run-directory bypass has been excised completely.

4. **Product Blast Radius and Hash Pin Verification:**
   - Compute SHA-256 hashes of `src/sysdiff.c` and `Makefile`:
     ```bash
     sha256sum src/sysdiff.c Makefile
     ```
   - Verify match against baseline values:
     - `src/sysdiff.c`: `1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1`
     - `Makefile`: `cfb431431b1188d22109d1127827123d63359983401e869e7a4557b48a9808ff`
   - Confirm zero changes to `man/sysdiff.1`, `README.md`, or `CHANGELOG.md`.

5. **User Journey Manifest Synchronization and Schema Conformance Gate:**
   - Execute bit-for-bit diff:
     ```bash
     diff -u tests/user_journeys_manifest.json journeys/user_journeys_manifest.json
     ```
   - Assert exit code 0 (zero differences).
   - Validate manifests against `USER_JOURNEYS_MANIFEST_SCHEMA` using `jsonschema.Draft202012Validator`.
   - Verify that exactly 21 journeys exist, that every journey maps via `traces_to` to at least one valid acceptance check (`AC-1`, `AC-2`, `AC-3`), and that `command_allowlist` is `["build/sysdiff"]`.

6. **Focused Regression Test Suite Execution:**
   - Run the dedicated repair test suite under pytest:
     ```bash
     python3 -m pytest tests/test_repair_b8bf0e7c59d5.py -v
     ```
   - Assert 100% pass rate with zero failures, errors, or unexpected skips, verifying that both `test_python_test_harness_decontamination` and `test_commissioning_dependencies_no_run_bypass` succeed cleanly.

7. **Full Repository Pytest Suite Execution:**
   - Run the full test suite from the repository root:
     ```bash
     python3 -m pytest tests/ -q
     ```
   - Assert clean exit (code 0) across all test modules without foreign path injections.

8. **Deterministic C Toolchain Smoke and Quality Gate Verification:**
   - Execute smoke script:
     ```bash
     ./scripts/smoke.sh
     ```
   - Execute Makefile quality targets:
     ```bash
     make test
     make quality
     ```
   - Assert clean exit (code 0) across all build and test targets.

9. **Non-Product Blast Radius Audit:**
   - Run `git diff --check` to confirm zero formatting or whitespace issues.
   - Run `git diff --name-only` to verify that only authorized repair paths are modified.

# Risks

Managing technical, governance, and operational risks is essential to preventing recurrent failures, oracle tampering, and quality degradation during the execution of this repair.

### 1. Oracle Tampering and Test Evasion Risk (`ORACLE_TAMPERING`)
- **Risk:** An autonomous worker or developer might attempt to resolve `test_python_test_harness_decontamination` or `test_commissioning_dependencies_no_run_bypass` by deleting, weakening, or altering assertions in `tests/test_repair_b8bf0e7c59d5.py` rather than properly cleaning the contaminated test files.
- **Impact:** Fails governance rules in `AGENTS.md`, triggers fail-closed oracle tampering detection, and invalidates the integrity of the test suite.
- **Mitigation:** `tests/test_repair_b8bf0e7c59d5.py` is treated as a canonical, immutable regression oracle. The verification protocol strictly forbids weakening oracle assertions. The repair must fix the underlying defects in `tests/test_governed_run_17ca9404991a_repair.py`, `tests/test_governed_workspace_abstraction.py`, and `tests/test_commissioning_dependencies.py`.

### 2. Unauthorized Blast Radius Expansion Risk (`BLAST_RADIUS`)
- **Risk:** Modifying production C code (`src/sysdiff.c`), `Makefile`, `README.md`, or manual pages (`man/sysdiff.1`) during a test harness repair slice will alter file hashes pinned by smoke oracles (`file_hash_matches` in `step_08_user_smoke_gate`).
- **Impact:** Breaks immutable smoke hash pins, causes downstream verification gates to fail closed, and violates non-product blast radius boundaries.
- **Mitigation:** Strict non-product blast radius containment. This repair slice modifies only test files, governance manifests, and documentation within declared `allowed_paths`. `src/sysdiff.c` and `Makefile` are verified against `BASELINE_SYSDIFF_SHA256` and `BASELINE_MAKEFILE_SHA256`.

### 3. Path Escape and Write Scope Violation Risk (`PATH_ESCAPE`)
- **Risk:** Writing test scripts, intermediate logs, or scratch artifacts outside declared `allowed_paths` or leaving files in the workspace root triggers an immediate fatal path escape failure by the orchestrator.
- **Impact:** Immediate step abort and failure regardless of test or code quality.
- **Mitigation:** All scratch files, temporary snapshots, and exploratory scripts must reside strictly within `.agent-orch-scratch/7581beae0012/`. File writes in each step must strictly respect the step's declared `allowed_paths` (`plans/` for planning).

### 4. Result Fabrication and Claim Divergence Risk (`RESULT_FABRICATION`)
- **Risk:** A worker might claim that tests or validators passed without actually executing the underlying commands or by creating synthetic passing outputs.
- **Impact:** Severe governance failure under `AGENTS.md`, failing semantic review gates and invalidating run evidence.
- **Mitigation:** The response contract requires reporting only commands and checks actually executed. All verification gates must execute real pytest, make, and diff commands with captured terminal output.

### 5. Manifest Desynchronization and Schema Conformance Risk
- **Risk:** Updating `tests/user_journeys_manifest.json` without applying the exact same updates to `journeys/user_journeys_manifest.json`, omitting journeys, or referencing undefined acceptance check trace IDs.
- **Impact:** Fails schema validation against `USER_JOURNEYS_MANIFEST_SCHEMA` and triggers manifest desynchronization errors in journey gates.
- **Mitigation:** Synchronized manifest validation asserts bit-for-bit or parsed object identity between both files. Automated schema validation confirms adherence to Draft 2020-12, preserves all 21 required journeys, and verifies complete coverage of `AC-1`, `AC-2`, and `AC-3`.

### 6. Toolchain Availability and Static Analysis Risk (`TOOL_AVAILABILITY`)
- **Risk:** Compiler or static analysis toolchain discrepancies (e.g. missing `clang-tidy`, `cppcheck`, or specific Python package versions) causing quality targets to fail or exit with error codes.
- **Impact:** Fails `make quality` and violates the repository quality floor established in `AGENTS.md`.
- **Mitigation:** Quality targets rely on canonical system tools and environment variables (`CC`, `CFLAGS`, `PATH`). Pytest runs use clean environment flags (`PYTHONDONTWRITEBYTECODE=1`) and standard site-packages.
