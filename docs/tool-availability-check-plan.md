# Tool Availability Check Plan

## Purpose

Deliver the repository-local routed worker preflight described in
`docs/tool-availability-check-contract.md`. The slice adds one stdlib-only
checker at `scripts/check_tools.py`, targeted pytest coverage in
`tests/test_check_tools.py`, and user documentation in
`docs/tool-availability-check.md` plus a short `README.md` pointer.

The checker answers only whether the required routed harness infrastructure is
available enough for Agent-Orch to attempt the configured routes. It must not
launch Agent-Orch, start model sessions, rewrite playbooks, install packages,
contact the network, or add any `sysdiff` product behavior.

## Architecture

Implement `scripts/check_tools.py` as a small Python module with a CLI entrypoint
guard:

- Define an explicit default harness table for `codex_cli` and `claude_code`.
  Each row contains the harness name, the route role it supports, the local
  executable names to look for, and a short remediation-oriented description.
- Keep the probing layer separate from formatting and exit-code handling:
  `probe_harnesses(requirements, env)` returns structured results, and
  `main(argv=None, env=None)` formats stdout or stderr and returns an integer.
- Use only stdlib APIs such as `argparse`, `dataclasses`, `os`, `shutil`,
  `subprocess`, and `sys`. Prefer `shutil.which(..., path=env["PATH"])` for
  executable discovery so tests can pass a temporary PATH without touching the
  real workstation.
- Limit optional command probing to non-mutating version/help style commands
  with short timeouts if a lightweight probe is needed after discovery. Treat a
  failed lightweight probe as unavailable with an explanatory reason; do not run
  commands that can launch sessions or perform workflow work.
- Print one readable stdout status line per available required harness, naming
  both the harness and the executable or probe that satisfied it.
- On failure, accumulate all unavailable harnesses, print a single descriptive
  stderr diagnostic that names every missing harness, and return a stable
  non-zero status.
- Keep the script read-only by construction: no file writes, chmod calls,
  package-manager calls, Agent-Orch launch commands, network clients, or
  playbook edits.

## Tests

Author `tests/test_check_tools.py` before implementation so it encodes the
contract rather than the finished script. Use pytest, `tmp_path`, and
`monkeypatch` to run the script against fake executables and fake PATH values.

Test cases:

- Successful default run: create fake `codex` and `claude` executables in a
  temporary bin directory, run `python3 scripts/check_tools.py`, assert exit
  status `0`, assert stdout names `codex_cli` and `claude_code`, and assert
  stderr is empty.
- Missing `codex_cli`: expose only the fake `claude` executable, assert non-zero
  status, stdout does not claim full success, and stderr names `codex_cli`.
- Missing `claude_code`: expose only the fake `codex` executable, assert
  non-zero status and stderr names `claude_code`.
- Missing both: expose an empty temporary PATH, assert one non-zero run names
  both `codex_cli` and `claude_code` in stderr.
- Diagnostic framing: assert failure stderr contains routed-worker or
  infrastructure wording so the problem cannot be mistaken for a `sysdiff`
  comparison failure.
- Workstation independence: every subprocess test sets PATH explicitly to a
  temporary directory and never depends on installed developer tools.
- Read-only behavior: import the module and monkeypatch dangerous stdlib
  surfaces, including `subprocess.run`, file-write APIs where practical, and
  network/package-manager command patterns, then assert normal availability
  checks do not call model-launch, workflow-launch, package-install, playbook
  mutation, or network commands.
- CLI cleanliness: assert success uses stdout for status and failures use stderr
  for diagnostics.

## Verification

Run these checks from the repository root during the test and implementation
steps:

```sh
python3 -m compileall tests/test_check_tools.py
python3 -m pytest tests/test_check_tools.py
python3 -m compileall scripts tests
python3 -m pytest
```

During repair-and-verify, also run configured formatting and lint commands when
their tools are available in the environment. If an optional lint tool is not
installed, record that limitation explicitly in the governed step notes rather
than silently treating it as a pass.

Manual behavior probes after implementation:

```sh
python3 scripts/check_tools.py
PATH="$(mktemp -d)" python3 scripts/check_tools.py
```

The empty-PATH probe should fail without modifying files and should name both
required harnesses. The normal PATH probe may pass or fail depending on the
local workstation, but its output must still follow the stdout/stderr and exit
status contract.

## Acceptance Mapping

| Contract acceptance check | Concrete plan item |
| --- | --- |
| `python3 scripts/check_tools.py` with all required harness probes available exits `0` | Architecture separates probe results from `main()` exit handling; tests create fake `codex` and `claude` executables and assert status `0`; verification runs the targeted pytest file. |
| Successful run writes a readable status line for `codex_cli` and `claude_code` to stdout | Formatter emits one stdout line per available default harness; success test asserts both harness names appear in stdout and stderr is empty. |
| Checker with `codex_cli` unavailable exits non-zero and names `codex_cli` in stderr | Missing-`codex_cli` test uses a PATH containing only fake `claude`; `main()` accumulates missing harnesses and returns non-zero. |
| Checker with `claude_code` unavailable exits non-zero and names `claude_code` in stderr | Missing-`claude_code` test uses a PATH containing only fake `codex`; failure formatter writes the harness name to stderr. |
| Checker with both required harnesses unavailable exits non-zero and names both in one diagnostic run | Empty-PATH test asserts a single invocation returns non-zero and stderr contains both default harness names. |
| Failure output explains missing routed worker infrastructure, not a `sysdiff` comparison failure | Diagnostic-framing test asserts routed-worker or infrastructure wording; architecture keeps this script independent from `sysdiff` comparison code. |
| Tests can simulate available and unavailable tools without relying on real installed adapters | Tests use fake executables in `tmp_path` and pass monkeypatched PATH/env into subprocesses or module helpers. |
| Tests assert the checker is read-only and does not launch model sessions, mutate playbooks, install packages, or contact the network | Read-only test monkeypatches dangerous calls and command patterns; architecture prohibits writes, workflow launches, package managers, model session commands, and network clients. |
| `python3 -m compileall tests/test_check_tools.py` succeeds after the test step | Verification requires this command immediately after authoring tests and again during repair if tests change. |
| `python3 -m pytest tests/test_check_tools.py` succeeds after implementation | Verification requires the targeted pytest command after implementation and before broader pytest. |
| Repair-and-verify runs the full Python verification set and records unavailable optional lint tools as environment limitations | Verification section lists `compileall scripts tests`, full `pytest`, and explicit optional-lint reporting behavior. |
| Documentation explains usage, default harnesses, exit statuses, and local-preflight limitation | Documentation step will add `docs/tool-availability-check.md` with command examples, default `codex_cli`/`claude_code` checks, stdout/stderr/exit status behavior, and limitations; README points to it. |
| Documentation avoids promises of live capture, extra `sysdiff` behavior, package installation, network access, or automatic route repair | Documentation plan states non-goals and review should check wording for those prohibited promises. |

## Risks

- **Harness-name drift:** the contract names Agent-Orch harnesses, while local
  executable names may differ. Keep the harness table explicit and reviewable,
  and test both the harness name shown to users and the executable discovery
  behavior separately.
- **Accidental session launch:** availability probes can become too aggressive.
  Restrict probes to discovery and non-mutating version/help style commands,
  and keep tests that fail if model-launch or workflow-launch commands are
  invoked.
- **False dependence on the developer workstation:** tests must run with
  temporary PATH values and fake executables so CI and worker machines do not
  need real Codex or Claude installations to validate behavior.
- **Partial diagnostics:** stopping at the first missing harness would hide the
  full environment problem. Accumulate all probe results before deciding the
  exit status.
- **Stdout/stderr confusion:** operators need status on stdout and failure
  diagnostics on stderr. Cover both streams in tests.
- **Scope creep into sysdiff or Agent-Orch repair:** this slice is a preflight
  only. Do not add snapshot capture, comparison behavior, package installers,
  route rewriting, fallback selection, network checks, or workflow launch logic.
