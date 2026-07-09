# Tool Availability Check

`scripts/check_tools.py` is a repository-local preflight for the routed
Agent-Orch worker harnesses used by this project. Run it before depending on a
generated playbook route so missing local infrastructure is reported directly,
before the failure is confused with a `sysdiff` implementation, review, or
closeout problem.

## Usage

From the repository root:

```sh
python3 scripts/check_tools.py
```

The default check verifies these required harnesses:

| Harness | Agent-Orch role | Local executable |
| --- | --- | --- |
| `codex_cli` | `implementation_worker` | `codex` |
| `claude_code` | `slice_reviewer` | `claude` |

The script checks executable discovery on `PATH` only. It does not run version
commands, launch Agent-Orch, start a model session, modify playbooks, install
packages, or contact the network.

This command is meant for operators and agents preparing governed work. It is
not part of the `sysdiff compare` interface, and it does not build, test, or
execute the C utility.

## Successful Output

When every required harness is available, the command exits `0` and writes one
status line per harness to stdout:

```text
available: codex_cli (implementation_worker) via codex at /path/to/codex
available: claude_code (slice_reviewer) via claude at /path/to/claude
```

Stderr is empty on success.

## Failure Output

When one or more required harnesses are missing, the command exits non-zero,
writes no success status to stdout, and reports every missing harness to
stderr in one run:

```text
Missing routed worker infrastructure for required Agent-Orch harnesses:
- codex_cli (implementation_worker, primary implementation worker harness) is unavailable: none of the required executables were found on PATH: codex. Expected executable(s): codex
- claude_code (slice_reviewer, review worker harness) is unavailable: none of the required executables were found on PATH: claude. Expected executable(s): claude
```

If only one executable is missing, only that harness is listed. The diagnostic
is about routed worker infrastructure, not a `sysdiff` comparison failure.

Successful status lines are intentionally written only when all required
harnesses are available. A failed run keeps stdout empty so shell callers can
treat stderr as the complete diagnostic.

## Exit Status

- `0`: every required harness is discoverable on `PATH`.
- `1`: one or more required harnesses are unavailable.
- `2`: command-line usage error reported by Python `argparse`, such as an
  unsupported argument.

## Scope

This preflight is advisory infrastructure validation. It does not replace the
Agent-Orch governed workflow, choose fallback routes, repair local
installations, change generated playbooks, or prove that a later model session
will complete successfully. It also does not add `sysdiff` behavior, inspect
snapshot files, collect live system state, or run the C quality gates.

Use `OPERATE.md` and the Agent-Orch CLI path when setting up, launching,
resuming, or reporting on governed work. This check only answers whether the
local executables for the default routed harnesses are discoverable.
