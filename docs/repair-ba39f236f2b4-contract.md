# Overview

This document defines the normative repair contract for governed run `ba39f236f2b4`. In governed run `ba39f236f2b4`, execution failed during validation because essential toolchain utilities—specifically `clang`, `cppcheck`, and `clang-tidy`—were missing from the execution environment or could not be located in `$PATH`. This prevented the automated verification and static analysis commands required by the repository quality floor from executing successfully.

The primary purpose of this repair slice is to resolve the toolchain availability failure by repairing the validation environment and implementation to guarantee that `clang`, `cppcheck`, and `clang-tidy` are reliably available, discoverable, and functioning across all validation commands and quality checks, while strictly preserving repository quality standards, write scope confinement, and manifest synchronization.

The sealed evidence for the failure in governed run `ba39f236f2b4` is preserved in the sealed evidence directory:
`/home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4`

Required Outputs:
The required outputs of this repair slice across its execution lifecycle are:
1. `docs/repair-ba39f236f2b4-contract.md` (this repair contract, establishing the normative failure specification, required outputs, constraints, validation rules, routing intent, and acceptance checks under exact required headings).
2. `journeys/user_journeys_manifest.json` (the secondary user journey manifest, synchronized identically with the canonical test oracle and preserving all 21 required journeys).
3. `tests/user_journeys_manifest.json` (the canonical repository-owned user journey manifest oracle, adhering strictly to the canonical schema and command allowlist).
4. Validation environment and toolchain repair implementation (providing discoverable, robust wrappers, preflight scripts, or environment adaptations ensuring `clang`, `cppcheck`, and `clang-tidy` can be invoked by validation commands without missing-binary failures).
5. Comprehensive automated regression tests under `tests/` verifying tool availability, manifest synchronization, and non-product blast radius containment.

Validation:
Validation for this repair slice enforces contract completeness, tool availability, manifest integrity, and non-regression:
- The contract document must exist at `docs/repair-ba39f236f2b4-contract.md` with substantive text (>= 120 non-whitespace characters) under each required heading: Overview, Problem, Constraints, and Acceptance Checks.
- Preflight and validation checks must confirm that `clang`, `cppcheck`, and `clang-tidy` are accessible and executable, returning standard zero exit codes on help or version queries and successfully executing validation targets (such as `clang-tidy-check`, `cppcheck-check`, and `clang-analyzer-check` in the Makefile, or equivalent validator commands).
- Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA`.
- Every required journey in the manifest must trace to an explicit acceptance check (`AC-1`, `AC-2`, or `AC-3`), with all acceptance checks covered.
- The existing pytest test suite and C build targets must pass cleanly without introducing regressions or modifying `src/sysdiff.c`.

Routing Intent:
This repair routes static analysis and compiler validation through dependable, verified toolchain execution paths. The orchestrator must ensure that any step executing validation commands has access to working implementations of `clang`, `cppcheck`, and `clang-tidy`, either through host package discovery or robust repository-provided wrapper and shim mechanisms that cleanly bridge missing tools to available system compilers (e.g., standard GCC with syntax and static analyzer flags) when dedicated binaries are not installed. All step executions must strictly confine their file writes to declared `allowed_paths`, preventing path escape violations.

# Problem

In governed run `ba39f236f2b4`, preserved in sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4`, execution failed during validation. Specifically, a previous validation command failed because `clang`, `cppcheck`, and `clang-tidy` were missing from the validation environment or could not be found in `$PATH`.

Analysis of the failure and environmental root causes:

1. **Missing Toolchain Dependencies in the Validation Environment:**
   Under repository operating rules defined in `AGENTS.md`, release-quality work in this project must pass rigorous compiler and static analysis gates, specifically including GCC, Clang (`-Wall -Wextra -Wpedantic -Werror`), clang-format, clang-tidy, cppcheck, and the Clang static analyzer. When a governed workflow or validation step executes commands that depend directly on `clang`, `cppcheck`, or `clang-tidy` (such as `make clang-tidy-check`, `make cppcheck-check`, or direct toolchain invocations in automated validator scripts), the execution environment must provide those executables. In run `ba39f236f2b4`, the execution environment lacked installed packages or accessible paths for `clang`, `cppcheck`, and `clang-tidy`, resulting in command-not-found errors (exit status 127) or unhandled invocation failures that aborted validation fail-closed.

2. **Gaps in Tool Wrapper and Preflight Infrastructure:**
   Although prior repair slices introduced partial wrapper scripts in `scripts/` (such as `scripts/clang` and `scripts/cppcheck`), significant gaps remained:
   - `clang-tidy` had no wrapper or fallback script in `scripts/`, causing recipes like `make clang-tidy-check` to fail immediately when `clang-tidy` was absent from host `$PATH`.
   - The wrappers in `scripts/` were not automatically exported or prepended to `$PATH` across arbitrary validator subshells or container execution contexts, meaning commands invoking bare `clang` or `cppcheck` could still fail if the calling harness did not explicitly point to `scripts/` or invoke `scripts/ensure_tools.sh`.
   - The validation command relied upon all three tools (`clang`, `cppcheck`, `clang-tidy`) being concurrently functional, but no single unified preflight check verified their availability before executing quality gates.

3. **Need for Validation Environment and Implementation Repair:**
   To resolve this failure, we need to repair the validation environment and implementation to ensure these tools are reliably available. This requires establishing explicit tool discovery, robust wrapper and fallback support for `clang`, `cppcheck`, and `clang-tidy`, and structured preflight validation so that all automated validation commands execute predictably without missing-binary failures, while maintaining strict adherence to the project's quality floor.

# Constraints

1. **Strict Write Scope Confinement:** All file modifications across all steps of this repair must remain strictly within declared `allowed_paths`. For this contract definition step (`step_01_define_slice_contract`), writes are strictly confined to `docs`, `tests`, and `journeys`. Step workers must never create unconfined scripts or temporary artifacts in the repository root or outside allowed paths. Any temporary notes, experimental scripts, or self-checks must reside exclusively in the orchestrator-designated scratch directory (`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch/eb713e3103be/step_01_define_slice_contract/attempt-1`).
2. **Quality Floor Preservation:** Under `AGENTS.md`, release-quality software must pass rigorous verification including strict compiler flags (`-Wall -Wextra -Wpedantic -Werror`), clang-tidy, cppcheck, and sanitizers. Repairing the validation environment or implementation to ensure `clang`, `cppcheck`, and `clang-tidy` are available must never dilute, disable, or bypass required quality checks when native tools are present. Fallback mechanisms must enforce strict syntax checking and static analysis (e.g. GCC `-fanalyzer` and strict compiler warnings).
3. **Preservation of Sealed Evidence:** The sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4` is strictly read-only historical evidence. It must never be modified, deleted, or self-certified.
4. **User Journey Manifest Integrity and Synchronization:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA`. All 21 journeys—comprising the 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys—must be preserved without omission or unauthorized modification.
5. **Acceptance Traceability and Command Allowlist:** Every required journey in the manifest must map via `traces_to` to at least one valid acceptance check ID (`AC-1`, `AC-2`, or `AC-3`). No journey may reference an undefined acceptance check, and no contract acceptance check may be left uncovered by required journeys. The manifest `command_allowlist` must remain strictly `["build/sysdiff"]`.
6. **Non-Product Blast Radius:** This repair applies strictly to governance documentation, manifest synchronization, validation environment tooling, and regression tests. It must introduce zero modifications, regressions, or unauthorized alterations to `sysdiff` C17 source code (`src/sysdiff.c`), Makefile binary compilation rules, or manual pages (`man/sysdiff.1`).
7. **Closed Hazard Taxonomy:** Hazards identified in run `ba39f236f2b4` are classified strictly within the established repository taxonomy: `TOOL_AVAILABILITY` (missing compiler and static analysis tools preventing validation), `EXECUTION_TIMEOUT`, `ORACLE_TAMPERING`, and `BLAST_RADIUS`. No unauthorized hazard classes may be introduced.

# Acceptance Checks

- **AC-1** — **Contract Establishment, Document Integrity, and Write Scope Confinement:** The repair contract `docs/repair-ba39f236f2b4-contract.md` is created under required headings (Overview, Problem, Constraints, Acceptance Checks) with at least 120 non-whitespace characters per heading, citing sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4`. All file mutations across repair steps strictly adhere to declared `allowed_paths` (`docs`, `tests`, `journeys`), ensuring that scratch files are confined to `.agent-orch-scratch/` and zero unauthorized files are created in the workspace root.
- **AC-2** — **Tool Availability and Validation Environment Repair (`clang`, `cppcheck`, `clang-tidy`):** The validation environment and implementation ensure that `clang`, `cppcheck`, and `clang-tidy` are reliably available and executable. Validation commands and static analysis targets (including `clang-tidy-check`, `cppcheck-check`, and `clang-analyzer-check`) locate the required tools, execute cleanly without missing-binary failures or untyped exit 127 faults, and provide robust diagnostic output while preserving the mandatory quality floor.
- **AC-3** — **User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are maintained as identical, valid JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA` and preserving all 21 required journeys. Every required journey maps via `traces_to` to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks. The full test suite passes cleanly, and zero modifications are introduced to `src/sysdiff.c`, Makefile binary targets, or manual pages.
