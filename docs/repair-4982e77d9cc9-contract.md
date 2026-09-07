# Overview

This document defines the normative repair contract for governed run `4982e77d9cc9`. In governed run `4982e77d9cc9`, execution halted and failed due to a path escape and write scope confinement violation: the step made changes to paths outside its declared `allowed_paths` boundary, specifically creating unauthorized files including `artifacts/user-test/result.json` and ad-hoc generator scripts such as `generate_result.py` directly in the workspace root.

The primary purpose of this repair slice is to re-establish strict write scope discipline, prevent unauthorized mutations outside declared step boundaries, ensure proper utilization of isolated scratch space for temporary scripts, and maintain synchronized user journey manifests without introducing regressions or expanding non-product blast radius.

The sealed evidence for the failure in governed run `4982e77d9cc9` is preserved in the sealed evidence directory:
`/home/lee/projects/linux-utilities-agent-orch-runs/4982e77d9cc9`

The required outputs of this repair slice are:
1. `docs/repair-4982e77d9cc9-contract.md` (this repair contract, defining the problem, required outputs, constraints, validation criteria, routing intent, and acceptance checks under exact required headings).
2. `journeys/user_journeys_manifest.json` (the secondary user journey manifest, synchronized identically with the canonical test oracle).
3. `tests/user_journeys_manifest.json` (the canonical repository-owned user journey manifest oracle, adhering strictly to the canonical schema and preserving all 21 required journeys).

Routing intent: This repair routes workspace mutations and user simulation evaluations through strict, fail-closed boundaries. Step workers must never write ad-hoc helper scripts or temporary files to the repository root or outside declared `allowed_paths`; any scratch experiments or temporary generators must be confined to orchestrator-designated scratch directories (`.agent-orch-scratch/...`). When authoring or validating `artifacts/user-test/result.json`, the execution must occur only within steps where `artifacts` is explicitly authorized in `allowed_paths`. All step executions must strictly confine their file writes to declared allowed paths. Manifest synchronization across `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` is preserved without modifying product source files or expanding scope.

# Problem

In governed run `4982e77d9cc9`, preserved in sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/4982e77d9cc9`, execution failed with multiple trusted validator findings that breached orchestrator path policy and write scope confinement.

Specifically, the prior run failed because it changed paths outside `allowed_paths` (`artifacts/user-test/result.json`, `generate_result.py`, etc.):

1. **Path Escape via Ad-Hoc Scripts in Workspace Root:**
   During step execution, the worker attempted to generate and test user simulation outputs by authoring ad-hoc Python scripts directly in the repository root (including `generate_result.py`). Under Agent-Orch governance, creating files in the workspace root outside declared `allowed_paths` represents a severe path escape (`PATH_ESCAPE`) violation. Temporary utilities, test generators, and exploratory scripts must reside exclusively in designated `.agent-orch-scratch/` directories and must never pollute the governed repository tree.

2. **Unauthorized Mutation of Artifact Paths:**
   The workflow attempted to write `artifacts/user-test/result.json` during a step whose declared `allowed_paths` did not include the `artifacts` directory. Agent-Orch enforces write scope as a fundamental security and integrity boundary: any write outside declared `allowed_paths` triggers an immediate fail-closed termination of the step, however good or well-intentioned the generated artifact content may be.

3. **Compounding Governance and Provenance Risks:**
   Writing unconfined scripts into the repository root contaminates version control, breaks clean checkout guarantees, and risks accidental inclusion in releases or build artifacts. Similarly, generating result artifacts in unauthorized paths undermines the audit chain and provenance verification enforced by Agent-Orch.

This repair slice directly resolves these root causes by establishing strict write scope confinement, enforcing scratch space isolation for temporary scripts, and guaranteeing user journey manifest synchronization.

# Constraints

1. **Strict Write Scope Confinement:** All file modifications across all steps of this repair must remain strictly within declared `allowed_paths`. For this contract definition step, writes are strictly limited to `docs`, `tests`, and `journeys`. Workers must never create ad-hoc scripts (`generate_result.py`, `generate_result2.py`, `test_script.py`, etc.) in the workspace root; temporary scripts and experimental code must reside exclusively in designated `.agent-orch-scratch/` directories.
2. **Preservation of Sealed Evidence:** The sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/4982e77d9cc9` contains immutable historical run evidence and is strictly read-only. It must not be modified, inspected out of bounds, or self-certified.
3. **Artifact Path Discipline:** Results such as `artifacts/user-test/result.json` must only be authored or mutated in steps that explicitly declare `artifacts` in their `allowed_paths`. Steps lacking write authorization for `artifacts` must treat that path as read-only.
4. **Canonical Result Schema Compliance:** Any generated or validated `artifacts/user-test/result.json` must strictly conform to `USER_JOURNEYS_RESULT_SCHEMA`. Every finding object in `findings` must contain all mandatory properties: `id` (non-empty string), `severity`, `journey`, `problem`, `reproduction`, `expected`, `actual`, and `proposed_fix`. Findings must reference valid, workspace-relative, non-empty artifact logs when evidence files are cited.
5. **Allowlisted Direct Argv Execution:** All command claims recorded in `commands_run` must adhere to the manifest `command_allowlist` (`["build/sysdiff"]`). Commands must execute as direct `argv` arrays without shell wrapper indirection (`/bin/sh -c`), command chaining (`&&`), or unallowlisted tokens. Exit codes and observed outputs must reproduce deterministically.
6. **User Journey Manifest Synchronization and Integrity:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist as identical parsed JSON objects adhering to `USER_JOURNEYS_MANIFEST_SCHEMA`. All 21 journeys—comprising the 10 workspace abstraction author journeys, 4 core sysdiff utility journeys, and 7 sandbox containment and repair journeys—must be preserved without omission, reordering, or tampering.
7. **Acceptance Traceability:** Every required journey in the manifest must map via `traces_to` to at least one valid acceptance check ID (`AC-1`, `AC-2`, or `AC-3`). No journey may reference an undefined acceptance check, and no contract acceptance check may be left uncovered by required journeys. Exploratory journeys remain supplementary and cannot satisfy required coverage.
8. **Non-Product Blast Radius:** This repair applies exclusively to governance documentation, manifest synchronization, and validation rules. It must introduce zero modifications, regressions, or unauthorized dependencies to `sysdiff` C17 source code (`src/sysdiff.c`), Makefile build recipes, manual pages (`man/sysdiff.1`), or CLI contract behavior.
9. **Closed Hazard Taxonomy:** Identified hazards are classified strictly within the established governance taxonomy: `PATH_ESCAPE` (unauthorized file creation outside `allowed_paths`), `RESULT_FABRICATION` (schema-violating results and unevidenced command claims), `ORACLE_TAMPERING`, and `BLAST_RADIUS`. No unauthorized hazard classes may be introduced.

# Acceptance Checks

- **AC-1** — **Write Scope Confinement, Contract Establishment, and Scratch Isolation:** The repair contract `docs/repair-4982e77d9cc9-contract.md` is created under required headings (Overview, Problem, Constraints, Acceptance Checks) with at least 120 non-whitespace characters per heading, citing the sealed evidence directory `/home/lee/projects/linux-utilities-agent-orch-runs/4982e77d9cc9`. All file mutations across repair steps strictly adhere to declared `allowed_paths`, completely preventing path escape violations and ensuring that ad-hoc scripts (`generate_result.py`, `generate_result2.py`, `test_script.py`, `update_md.py`) and out-of-scope artifacts (`artifacts/user-test/result.json`) are never written outside declared allowed paths, with all scratch files strictly confined to `.agent-orch-scratch/`.
- **AC-2** — **Result Schema Conformance, Finding ID Integrity, and Verifiable Execution Claims:** The user testing result artifact `artifacts/user-test/result.json` strictly adheres to `USER_JOURNEYS_RESULT_SCHEMA`. Every finding in `findings` includes a mandatory, non-empty `id` property alongside `severity`, `journey`, `problem`, `reproduction`, `expected`, `actual`, and `proposed_fix`. Claimed commands in `commands_run` conform strictly to the allowlisted direct `argv` execution protocol without shell wrapper escapes (`/bin/sh -c`), allowing deterministic re-execution and verification by downstream gates.
- **AC-3** — **User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are maintained as identical, valid JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA` and preserving all 21 required journeys. Every required journey maps via `traces_to` to an enumerated check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks. The full test suite passes cleanly, and zero modifications are introduced to `src/sysdiff.c`, Makefile binary targets, or manual pages.
