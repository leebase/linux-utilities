# Tool Availability Check Contract

## Overview

This slice adds a small repository-local preflight for Agent-Orch routed worker
infrastructure. The durable implementation output is `scripts/check_tools.py`,
with tests in `tests/test_check_tools.py` and user-facing documentation in
`docs/tool-availability-check.md` plus the `README.md` tool-availability
section.

The script checks whether the routed worker harnesses required by this project
are available before a generated playbook depends on them. For the current
linux-utilities mission, the required harness names are `codex_cli` for the
primary implementation path and `claude_code` for the reviewer path. The check
is advisory infrastructure validation: it does not build `sysdiff`, inspect
snapshot files, launch model work, modify playbooks, or replace Agent-Orch
routing decisions.

The user-facing command is:

```sh
python3 scripts/check_tools.py
```

With no arguments, it checks the default required harness set for this
repository. A successful run exits `0` and reports that each required harness is
available. A failed run exits non-zero and identifies every missing required
harness in a descriptive diagnostic.

## Problem

Recent governed runs depend on routed workers, but a missing local harness is
currently discovered late, after a playbook has already been authored or a run
has advanced to a step that needs that route. That makes failures harder to
interpret: the broken condition is environmental, while the visible failure may
look like an implementation, review, or closeout problem.

The project needs a focused preflight that can be run before or during
playbook authoring to answer one narrow question: are the local tools needed for
the configured routed harnesses present enough for Agent-Orch to attempt the
route? The answer must be deterministic, fast, and easy for both humans and
workers to read.

Required outputs for the full slice are:

- `docs/tool-availability-check-contract.md`: this contract.
- `docs/tool-availability-check-plan.md`: a traceable implementation plan.
- `tests/test_check_tools.py`: pytest coverage that encodes this contract
  before implementation.
- `scripts/check_tools.py`: the stdlib-only Python checker.
- `docs/tool-availability-check.md`: user documentation for the command,
  output, exit status, and limitations.
- `README.md`: a short discoverability section pointing to the dedicated doc.

The checker should make missing routing infrastructure visible without
expanding the product scope. It is not a Linux utility release feature, not a
general environment audit, and not a substitute for the existing C quality
gates.

## Constraints

- Keep the implementation in a single Python script under `scripts/`.
- Use only the Python standard library.
- Keep checks read-only. The script must not create, edit, delete, chmod, or
  launch workflow files.
- Do not start Agent-Orch, invoke model sessions, run prompts, open network
  connections, or perform package installation.
- Do not require privileged access or host-specific state beyond executable
  discovery and lightweight local command probing.
- Keep the default required harness names explicit and reviewable:
  `codex_cli` and `claude_code`.
- Report all missing required harnesses in one run instead of stopping at the
  first missing tool.
- Keep stdout for successful human-readable status and stderr for failure
  diagnostics.
- Use stable exit statuses: `0` when every required harness is available and a
  non-zero status when one or more required harnesses are missing or cannot be
  checked.
- Keep behavior testable with a temporary `PATH` and monkeypatched environment;
  tests must not depend on the developer's real installed tools.

Validation for this slice is intentionally Python-focused. The contract step is
valid when this document exists and contains substantive content under the
required headings. Later steps must validate the plan with traceability back to
this contract, compile `tests/test_check_tools.py`, run
`python3 -m pytest tests/test_check_tools.py`, and include the tool check in
the broader slice verification with `python3 -m pytest`,
`python3 -m compileall scripts tests`, and the configured formatting and lint
commands when those tools are available in the environment.

Routing intent is limited to preflight visibility. The implementation worker
for this slice is routed through the `implementation_worker` role, whose
current playbook target is `codex_cli`. The reviewer is routed through the
`slice_reviewer` role, whose current target is `claude_code`. The checker
should name those harnesses clearly in output so a failed preflight can be
connected back to the affected route, but it must not choose fallback models or
rewrite playbook routing fields.

## Acceptance Checks

- Running `python3 scripts/check_tools.py` with all required harness probes
  available exits `0`.
- The successful run writes a readable status line for `codex_cli` and
  `claude_code` to stdout.
- Running the checker with `codex_cli` unavailable exits non-zero and names
  `codex_cli` in stderr.
- Running the checker with `claude_code` unavailable exits non-zero and names
  `claude_code` in stderr.
- Running the checker with both required harnesses unavailable exits non-zero
  and names both harnesses in one diagnostic run.
- Failure output is descriptive enough to tell the operator that the issue is
  missing routed worker infrastructure, not a `sysdiff` comparison failure.
- Tests can simulate available and unavailable tools without relying on the
  real developer workstation or installed Agent-Orch adapters.
- Tests assert that the checker is read-only and does not call commands that
  launch model sessions, mutate playbooks, install packages, or contact the
  network.
- `python3 -m compileall tests/test_check_tools.py` succeeds after the test
  step.
- `python3 -m pytest tests/test_check_tools.py` succeeds after implementation.
- The repair-and-verify step runs the full Python verification set required by
  the playbook for this slice and records any unavailable optional lint tool as
  an environment limitation instead of silently skipping a required gate.
- Documentation explains command usage, default checked harnesses, exit
  statuses, and the fact that this is a local preflight rather than a workflow
  launcher.
- Documentation does not promise live system capture, additional `sysdiff`
  behavior, package installation, network access, or automatic route repair.
