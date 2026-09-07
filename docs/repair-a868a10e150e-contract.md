# Overview

This document defines the normative repair contract for governed run `a868a10e150e`. In governed run `a868a10e150e`, execution failed during validation when executing the repair verification command for prior repair slice `a187b2fa74c9`. The trusted failure evidence recorded:
`Command failed: python3 -m pytest tests/test_repair_a187b2fa74c9.py: test_user_test_result_commands_run_are_objects_not_bare_strings`

The failure occurred because `artifacts/user-test/result.json` contained user journey test evidence where command claims under `commands_run` were represented as bare string entries (such as `"build/sysdiff --help"`) rather than structured schema-compliant objects containing required `command` and `exit_code` properties (such as `{"command": "build/sysdiff --help", "exit_code": 0}`). When `test_user_test_result_commands_run_are_objects_not_bare_strings` executed assertion `assert isinstance(claim, dict)`, it detected plain strings and failed closed, blocking downstream simulation gate validation and execution verification.

The primary purpose of this repair slice is to resolve this contract and schema non-conformance failure by establishing a normative repair contract, ensuring that `artifacts/user-test/result.json` strictly adheres to the Draft 2020-12 `USER_JOURNEYS_RESULT_SCHEMA`, guaranteeing that all command claims within `commands_run` are structured dictionary objects with valid `command` and `exit_code` fields, ensuring all allowlisted commands execute successfully against `build/sysdiff` from the workspace root, maintaining full synchronization between canonical and secondary user journey manifests, and upholding the project quality floor and non-product blast radius without regressions.

The sealed evidence for the failure in governed run `a868a10e150e` is preserved in the sealed evidence directory:
`/home/lee/projects/linux-utilities-agent-orch-runs/a868a10e150e`

Required Outputs:
The required outputs of this repair slice across its execution lifecycle are:
1. `docs/repair-a868a10e150e-contract.md` (this repair contract, establishing the normative failure specification, required outputs, constraints, validation rules, routing intent, and acceptance checks under exact required headings).
2. `journeys/user_journeys_manifest.json` (the secondary user journey manifest, synchronized identically with the canonical test oracle and preserving all 21 required author, sysdiff, and sandbox containment journeys).
3. `tests/user_journeys_manifest.json` (the canonical repository-owned user journey manifest oracle, adhering strictly to `USER_JOURNEYS_MANIFEST_SCHEMA`, preserving all 21 required journeys, and maintaining the immutable command allowlist `["build/sysdiff"]`).
4. Schema-compliant user test simulation artifact `artifacts/user-test/result.json` conforming strictly to `USER_JOURNEYS_RESULT_SCHEMA`, containing required root keys `journeys` and `findings`, with each journey containing `name`, `status`, `steps_taken`, and structured `commands_run` claim objects with `command` (string) and `exit_code` (integer).
5. Comprehensive automated regression verification under `tests/` ensuring that `test_user_test_result_commands_run_are_objects_not_bare_strings` and related user journey validator checks pass cleanly without regressions.

Validation:
Validation for this repair slice enforces contract completeness, result artifact schema conformance, command claim verification, manifest integrity, and non-regression:
- The contract document must exist at `docs/repair-a868a10e150e-contract.md` with substantive text (at least 120 non-whitespace characters) under each required heading: Overview, Problem, Constraints, and Acceptance Checks.
- `artifacts/user-test/result.json` must exist, be valid JSON, and pass Draft 2020-12 validation against `USER_JOURNEYS_RESULT_SCHEMA` without schema errors, specifically verifying that every element of `commands_run` is an object with required `command` and `exit_code` properties.
- Every allowlisted command claim in `commands_run` (prefixed with `build/sysdiff`) must be re-executable from the workspace root and match its claimed exit code.
- Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA`.
- Every required journey in the manifest must trace via `traces_to` to an explicit acceptance check (`AC-1`, `AC-2`, or `AC-3`), with all acceptance checks covered.
- The existing test suite and smoke verification must pass cleanly without introducing product regressions or unauthorized modifications to `src/sysdiff.c`, `Makefile`, or `man/sysdiff.1`.

Routing Intent:
This repair routes user simulation evaluation and artifact generation through schema-governed, deterministic execution paths. When recording user journey executions, test harnesses and worker adapters must emit structured command claims conforming strictly to `USER_JOURNEYS_RESULT_SCHEMA` (`{"command": str, "exit_code": int}`). Command execution verification routes allowlisted binary invocations (`build/sysdiff`) directly with current working directory set to the governed workspace root. All step executions across this repair must strictly confine file mutations to declared `allowed_paths`, preventing path escape violations. Production C17 source and build recipes remain untouched to protect non-product blast radius boundaries.

# Problem

In governed run `a868a10e150e`, preserved in sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/a868a10e150e`, execution failed during validation. The trusted failure evidence recorded:
`Command failed: python3 -m pytest tests/test_repair_a187b2fa74c9.py: test_user_test_result_commands_run_are_objects_not_bare_strings`

Analysis of the failure and environmental root causes reveals:

1. **Schema Non-Conformance in User-Test Result Artifact (`artifacts/user-test/result.json`):**
   Under the repository's Agent-Orch governance framework, user journey simulation gates validate `artifacts/user-test/result.json` against the Draft 2020-12 JSON schema defined by `USER_JOURNEYS_RESULT_SCHEMA`. This schema specifies that each journey record within the `journeys` array must include a `commands_run` property defined as an array of objects:
   ```json
   "commands_run": {
     "type": "array",
     "minItems": 1,
     "items": {
       "type": "object",
       "required": ["command", "exit_code"],
       "properties": {
         "command": {"type": "string", "minLength": 1},
         "exit_code": {"type": "integer"},
         "stdout_contains": {"type": "string", "minLength": 1}
       }
     }
   }
   ```
   In governed run `a868a10e150e`, `artifacts/user-test/result.json` recorded `commands_run` as an array of bare strings (for example `["build/sysdiff --help"]`) instead of an array of objects (such as `[{"command": "build/sysdiff --help", "exit_code": 0}]`). When `tests/test_repair_a187b2fa74c9.py: test_user_test_result_commands_run_are_objects_not_bare_strings` executed, the assertion `assert isinstance(claim, dict)` failed because `claim` was of type `str`.

2. **Downstream Type Errors and Validation Refusal:**
   In addition to triggering failure in `test_user_test_result_commands_run_are_objects_not_bare_strings`, string elements in `commands_run` cause runtime type exceptions in downstream test suites and validators. Automated tests (such as `test_user_test_result_command_claims_safe_dict_access_no_attribute_error`) iterate through `commands_run` and call dictionary methods such as `claim.get("command", "")` and `claim.get("exit_code")`. When `claim` is a string instead of a dictionary, Python raises `AttributeError: 'str' object has no attribute 'get'`. Furthermore, the orchestrator validator refuses to re-execute command claims from an invalid schema artifact, preventing user simulation gates (`_run_user_journeys_rule` and `_run_user_journeys_execution_rule`) from verifying legitimate binary execution.

3. **Lineage to Prior Runs `a187b2fa74c9` and `036f50eb30d6`:**
   Governed run `036f50eb30d6` failed due to compounding issues including invalid journey key naming (`"journey"` instead of `"name"`), omitted top-level `"findings"`, and string command claims. Run `a187b2fa74c9` attempted to address `036f50eb30d6` but failed at step `step_08b_user_simulation_gate` with `$.journeys[0].commands_run[0]: 'build/sysdiff --help' is not of type 'object'`. Governed run `a868a10e150e` was launched to repair run `a187b2fa74c9`, but failed when executing the regression gate `python3 -m pytest tests/test_repair_a187b2fa74c9.py: test_user_test_result_commands_run_are_objects_not_bare_strings` because the test result artifact had not been transformed from bare strings into structured objects.

4. **Non-Product Blast Radius Containment:**
   The failure in `a868a10e150e` is entirely an artifact formatting and governance schema issue. It does not stem from any defect in the `sysdiff` utility itself. Under repository operating rules, this repair slice must resolve the failure strictly within the governance artifacts, manifests, test suites, and documentation. It must not alter production C source code (`src/sysdiff.c`), Makefile binary targets, or manual pages (`man/sysdiff.1`).

# Constraints

1. **Strict Write Scope Confinement:** All file modifications across all steps of this repair must remain strictly within declared `allowed_paths`. For this framing step (`step_01_frame_repair`), writes are strictly confined to `docs`, `tests`, and `journeys`. Step workers must never create unconfined scripts or temporary artifacts in the repository root or outside allowed paths. Any temporary notes, experimental scripts, or self-checks must reside exclusively in the orchestrator-designated scratch directory (`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch/ec1d95cebdc9/step_01_frame_repair/attempt-1`).
2. **Failure Rationale Grounding and Quality Floor Preservation:** Grounded in the failure rationale: Repair the trusted failure from governed run `a868a10e150e` (Evidence: Command failed: `python3 -m pytest tests/test_repair_a187b2fa74c9.py: test_user_test_result_commands_run_are_objects_not_bare_strings`). Under `AGENTS.md`, release-quality software must pass rigorous verification including strict ISO C17 compiler flags (`-std=c17 -Wall -Wextra -Wpedantic -Werror`), clang-tidy, cppcheck, sanitizers (AddressSanitizer and UndefinedBehaviorSanitizer), and Valgrind. Repairing test artifacts or governance manifests must never lower, disable, or bypass required quality checks.
3. **Preservation of Sealed Evidence:** The sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/a868a10e150e` contains immutable historical run evidence and is strictly read-only. It must not be modified, deleted, inspected out of bounds, or self-certified.
4. **Result Artifact Schema Conformance:** `artifacts/user-test/result.json` must strictly conform to Draft 2020-12 `USER_JOURNEYS_RESULT_SCHEMA`. The top-level object must contain required properties `journeys` and `findings`. Every journey entry must contain `name` (string), `status` (`passed` or `failed`), `steps_taken` (string or non-empty string list), and `commands_run` (array of objects). Every item in `commands_run` must be an object containing `command` (string) and `exit_code` (integer), and optionally `stdout_contains` (string). Plain string items in `commands_run` are strictly prohibited.
5. **Command Claim Re-execution from Workspace Root:** Every command claim in `commands_run` prefixed with `build/sysdiff` must be re-executable directly from the governed workspace root and must match its claimed exit code without requiring changes to the production binary.
6. **Non-Product Blast Radius and Hash Pin Integrity:** This repair slice applies strictly to governance documentation, manifest synchronization, user test result artifacts, and test suites. It must introduce zero modifications, regressions, or unauthorized alterations to `sysdiff` C17 source code (`src/sysdiff.c`), Makefile binary targets, or manual pages (`man/sysdiff.1`). Baseline SHA-256 hash pins for `src/sysdiff.c` (`1cb1d154a8594c6bc7e81e19c3bfc5d15c6dce2f9e91dffe172c549dec8f01b1`) and `Makefile` (`59b45e65b60b70520a56ce35dfa779dc980a46d9a0a708424ebebbf6692b698c`) must remain intact.
7. **User Journey Manifest Integrity and Synchronization:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects adhering strictly to `USER_JOURNEYS_MANIFEST_SCHEMA`. All 21 journeys—comprising the 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys—must be preserved verbatim without omission, reordering, or tampering.
8. **Acceptance Traceability and Command Allowlist:** Every required journey in the manifest must map via `traces_to` to at least one valid acceptance check ID (`AC-1`, `AC-2`, or `AC-3`). No journey may reference an undefined acceptance check, and no contract acceptance check may be left uncovered by required journeys. The manifest `command_allowlist` must remain strictly `["build/sysdiff"]`.
9. **Closed Hazard Taxonomy:** Hazards identified in run `a868a10e150e` and this repair slice are classified strictly within the established repository taxonomy: `SCHEMA_VIOLATION` (invalid data types in result artifact properties), `ORACLE_TAMPERING` (tampering with test results or manifest schemas), `RESULT_FABRICATION` (unverifiable command claims), `BLAST_RADIUS` (unauthorized mutation of production code), `PATH_ESCAPE`, `TOOL_AVAILABILITY`, and `EXECUTION_TIMEOUT`. No unauthorized hazard classes may be introduced.

# Acceptance Checks

- **AC-1** — **Contract Establishment, Document Integrity, and Write Scope Confinement:** The repair contract `docs/repair-a868a10e150e-contract.md` is established under required headings (Overview, Problem, Constraints, Acceptance Checks) with at least 120 non-whitespace characters per heading, citing sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/a868a10e150e`. All file mutations across repair steps strictly adhere to declared `allowed_paths` (`docs`, `tests`, `journeys`), ensuring that scratch files are confined to `.agent-orch-scratch/` and zero unauthorized files are created in the workspace root or outside allowed paths.
- **AC-2** — **User-Test Result Artifact Schema Conformance, Command Claim Object Structure, and Simulation Gate Passing:** The user test result artifact `artifacts/user-test/result.json` conforms strictly to Draft 2020-12 `USER_JOURNEYS_RESULT_SCHEMA`. The root object contains required properties `journeys` and `findings`. Every journey item contains valid `name`, `status`, `steps_taken`, and `commands_run` properties. In particular, every item in `commands_run` is a structured object containing `command` (string) and `exit_code` (integer), completely eliminating bare string elements and resolving the failure in `test_user_test_result_commands_run_are_objects_not_bare_strings`. All allowlisted command claims re-executed from the workspace root match their claimed exit codes against `build/sysdiff`, and the user simulation gate passes cleanly without schema violation errors.
- **AC-3** — **User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are maintained as identical, valid JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA` and preserving all 21 required author, sysdiff, and sandbox containment journeys without omission. Every required journey maps via `traces_to` to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks. The full test suite passes cleanly, and non-product blast radius boundaries are strictly preserved with zero modifications to `src/sysdiff.c`, `Makefile`, or `man/sysdiff.1`.

## Authorized source-distribution follow-up — 2026-09-06

Lee authorized fresh Linux Utilities truth validation and minimal repair of independently reproduced defects. The source archive shipped governance tests without their mission dependencies. This follow-up changes only the distribution inventory and its assertions; binary build targets, C sources, and manual pages remain unchanged. For current verification, the Makefile pin is `f0a00c8edce2a01787db570b53479d1d07ca3246c600c5bac0d493c21c8e5629`, superseding the historical `59b45e65b60b70520a56ce35dfa779dc980a46d9a0a708424ebebbf6692b698c` baseline above. The independent sysdiff source pin is unchanged. Full-checkout governance tests remain required; historical run evidence is not rewritten or declared recovered.
