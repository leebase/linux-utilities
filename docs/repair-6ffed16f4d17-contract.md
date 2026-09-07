# Overview

This document defines the normative repair contract for governed run `6ffed16f4d17`. In governed run `6ffed16f4d17`, execution failed during `step_05` because the step violated the orchestrator's write scope policy by writing to `journeys/user_journeys_manifest.json`, a path outside its declared `allowed_paths`.

The primary purpose of this repair slice is to re-establish strict write scope discipline, resolve the path confinement failure, and ensure that all workspace mutations strictly adhere to declared step permissions without compromising the integrity of user journey manifests or test oracles.

The required outputs of this repair slice are:
1. `docs/repair-6ffed16f4d17-contract.md` (this repair contract, defining the failure, constraints, routing intent, validation criteria, and acceptance checks under exact required headings).
2. `journeys/user_journeys_manifest.json` (the secondary user journey manifest, fully synchronized with the canonical test oracle).
3. `tests/user_journeys_manifest.json` (the canonical repository-owned user journey manifest oracle, adhering strictly to the canonical schema and preserving all 21 required author, sysdiff, and sandbox journeys).

Routing intent: This repair enforces that step write boundaries are respected at all stages of the workflow. The orchestrator's path confinement enforcement operates fail-closed: any modification outside a step's declared `allowed_paths` aborts the execution immediately, regardless of code correctness. In this repair, journey manifest synchronization is maintained in step 1 where `journeys` is explicitly in `allowed_paths`, while subsequent implementation steps (including `step_05`) whose declared `allowed_paths` are restricted to `docs/` and `tests/` must confine all their writes strictly within those bounds and never touch `journeys/`. If a step requires modifying a path, that path must be declared in `allowed_paths` within the playbook specification prior to execution; otherwise, the step must treat that path as read-only.

# Problem

In governed run `6ffed16f4d17`, execution halted at `step_05` with a write scope violation. During that step, the worker or process attempted to update or synchronize the journey manifest at `journeys/user_journeys_manifest.json`. However, the playbook specification for `step_05` defined an `allowed_paths` filter that did not include the `journeys` directory (restricting writes to `docs/` and `tests/`).

Agent-Orch enforces write scope as a primary security and governance boundary. When any step writes to a file or directory outside its declared `allowed_paths`, the orchestrator immediately marks the step as failed with an out-of-scope write error. Under the repo operating rules and orchestrator contract, changing any file outside the declared write scope fails the step unconditionally, however good or well-intentioned the change is.

The root cause of this failure was a disconnect between manifest synchronization requirements and step-level write permissions:
1. Prior repair runs (such as `0191293dc09e`, finding UJ-0191293D-001) established that both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must exist, adhere to the canonical schema, and remain identical parsed objects containing all 21 journeys.
2. In run `6ffed16f4d17`, `step_05` attempted to satisfy manifest synchronization by directly writing to `journeys/user_journeys_manifest.json`.
3. Because `step_05` lacked write authorization for `journeys/` in its declared `allowed_paths`, the orchestrator intercepted the write as a forbidden path escape / scope violation.

This failure demonstrates that manifest synchronization must not be attempted in steps that lack `journeys` in their allowed paths. Manifest synchronization must be performed in governed steps explicitly authorized with `journeys` in `allowed_paths` (such as `step_01_define_repair_contract`), and subsequent steps must strictly respect their declared write boundaries.

# Constraints

1. **Strict Write Scope Confinement:** All file modifications must remain strictly within the declared `allowed_paths` for each step. In this contract definition step, writes are restricted to `docs`, `tests`, and `journeys`. Subsequent steps whose `allowed_paths` are limited to `docs/` and `tests/` must strictly avoid touching `journeys/` or any other path outside their declared scope.
2. **Manifest Integrity and Synchronization:** Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` must be identical parsed objects adhering to `USER_JOURNEYS_MANIFEST_SCHEMA`. All 21 journeys—comprising the 10 preserved workspace-abstraction author journeys, the 4 core sysdiff utility journeys, and the 7 bubblewrap sandbox containment and payload measurement journeys—must be preserved verbatim without omission, reordering, or tampering.
3. **Traceability Preservation:** Every non-exploratory user journey in the manifests must trace to an explicit acceptance check identifier (`AC-1`, `AC-2`, or `AC-3`). No journey may trace to an undefined or unnumbered acceptance check, and no contract acceptance check may be left untraced. Exploratory journeys remain supplementary and do not satisfy required acceptance coverage.
4. **Command Allowlist Immutability:** The manifest `command_allowlist` must remain strictly `["build/sysdiff"]`. No wrappers, shell expansions, or unauthorized command prefixes may be introduced.
5. **Non-Product Blast Radius:** This repair applies exclusively to governance documentation, manifest synchronization, and orchestrator path confinement verification. It must introduce no changes, regressions, or dependencies to the `sysdiff` C17 source code (`src/sysdiff.c`), Makefile build targets, man pages (`man/sysdiff.1`), or runtime behavior.
6. **Hazard Classification:** In accordance with the governance hazard taxonomy, the violation in run `6ffed16f4d17` is classified under `PATH_ESCAPE` (writing outside declared step `allowed_paths`). The repair must enforce fail-closed path containment without inventing unauthorized hazard classes.

# Acceptance Checks

Validation for this repair enforces structural document integrity, schema compliance, full journey traceability, and zero test regression. The repair is considered complete and accepted only when the following enumerated checks pass:

- **AC-1** — **Write Scope Confinement and Path Policy Compliance:** The repair contract `docs/repair-6ffed16f4d17-contract.md` is present, readable, and defines the problem from governed run `6ffed16f4d17` under the exact headings Overview, Problem, Constraints, and Acceptance Checks with at least 120 non-whitespace characters per heading. All writes in this and downstream steps remain strictly confined within their respective declared `allowed_paths`, ensuring that steps with write scopes restricted to `docs/` and `tests/` never write to `journeys/user_journeys_manifest.json` or cause path escape violations.
- **AC-2** — **User Journey Manifest Synchronization and Traceability:** The repository maintains synchronized user journey manifests at `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` as identical parsed objects. Both manifests strictly adhere to `USER_JOURNEYS_MANIFEST_SCHEMA`, preserve the immutable `command_allowlist` (`["build/sysdiff"]`), and contain all 21 required journeys. Every required journey has a valid authority and maps via `traces_to` to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with zero unmapped or orphaned acceptance checks.
- **AC-3** — **Test Suite Integrity and Non-Product Blast Radius:** The complete test suite (`pytest tests/`) passes cleanly with zero failures and no unexpected skips or suppressed tests. The repair introduces zero modifications to `src/sysdiff.c`, Makefile, or man pages, ensuring full CLI contract preservation, zero product regressions, and strict adherence to non-product blast radius boundaries.
