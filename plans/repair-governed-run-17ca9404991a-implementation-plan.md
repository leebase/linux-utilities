# Architecture

This is a compatibility repair at the Agent-Orch governed-workspace boundary,
not a sysdiff feature. First inspect the preserved origin attempt logs and the
current checkout before changing anything: the origin `17ca9404991a` recorded
the same three failures in both attempts, while the current exact three-test
rerun is green and may already contain candidate repairs. The implementation
surface is the imported `agent_orch` path and validator layer, especially
`resolve_workspace_path`, `normalize_relative_path`, `_load_json_artifact`,
`_run_structural_rule_with_context`, `_run_user_journeys_execution_rule`,
`_allowlisted_journey_command`, and `validate_step`. Existing callers must
resolve every result, manifest, contract, seed, finding-artifact, and playbook
path from the canonical workspace before opening, parsing, or schema-checking
it. Lexical, absolute, parent, current-directory, and symlink escapes must
return a containment diagnostic first; they must never become a later JSON
schema error. Preserve direct `subprocess` argv execution with the governed
workspace as `cwd`, leading environment assignments, exact exit-code checks,
and optional observed-output checks. Parse shell words before checking syntax,
reject real unquoted control operators and malformed claims, then compare the
parsed non-assignment argv token-by-token against the manifest prefix. Quoted
operator-looking payload text is data and must not be rejected as shell
control syntax. The blast-radius oracle must continue to inspect actual source
and scope without matching the forbidden-operation inventory embedded in its
own assertion.

The repository-owned compatibility boundary is encoded by
`tests/test_governed_workspace_abstraction.py`, its temporary-workspace
helpers and symlink/sentinel fixtures, `tests/user_journeys_manifest.json`,
`tests/smoke_manifest.json`, and the three named compatibility modules
`tests/test_governed_run_9add44496178.py`,
`tests/test_governed_run_c847e01d15fe.py`, and
`tests/test_commissioning_dependencies.py`. Audit
`playbooks/governed-workspace-abstraction.yaml` (repair step, smoke step,
independent journey step, and review step) and the template playbook that
defines the repair workflow for stale allowed-path or validator wiring. Audit
the final commissioning playbook and its packet/checker assets as read-only
governance inputs; they must not be changed or made dependent on the
interactive checkout. `scripts/smoke.sh`, `tests/smoke_start.py`,
`tests/check_sysdiff_smoke.py`, and `tests/test_sysdiff_fixture.sh` remain the
existing smoke/helper chain. `Makefile` behavior remains product evidence:
`make test` delegates through `test-suite` to the strict sysdiff shell fixture
and the whole pytest tree, while quality, release, and distribution rules
retain their existing scopes. `src/sysdiff.c` remains the single C17
snapshot-comparison implementation with its current CLI, output, and strict
build contract; no C source or Makefile repair is justified by these three
Python compatibility failures.

# Tests

Before implementation, inspect the preserved full failure output in
`../linux-utilities-agent-orch-runs/17ca9404991a/steps/step_05_implement_slice/attempt-{1,2}/validation.json`
and `last_message.txt`, then inspect the exact affected test bodies and the
validator callers listed above. Re-run the focused baseline with
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/test_governed_workspace_abstraction.py::test_workspace_rule_paths_fail_closed_for_symlink_escape
tests/test_governed_workspace_abstraction.py::test_commands_use_token_prefixes_and_direct_argv
tests/test_governed_workspace_abstraction.py::test_blast_radius_is_additive_and_non_product -q`.
Record whether the current candidate is red or green separately from the
origin evidence; do not overwrite the historical failure with a focused pass.

The focused regression must keep three independent assertions. The symlink
fixture must place its target genuinely outside the temporary workspace and
prove path containment is reported before result-schema validation, with
equivalent coverage for manifest, contract, seed, and finding-artifact paths
where callers differ. The direct-argv fixture must use a quoted Python payload
containing literal operator-looking text, write cwd and argv sentinels, and
assert the canonical workspace and literal argument; pipeline, redirection,
malformed, prefix-miss, and rejected-command sentinel cases must remain
negative. The blast-radius fixture must assemble forbidden tokens without
self-matching while still rejecting networking, installation, packaging,
publication, release, product-source, and unrelated test changes. Do not
remove a negative assertion, turn it into a skip, narrow the allowlist, or
edit the pinned manifest to make a result pass.

Run the focused abstraction module and all affected compatibility modules:
`tests/test_governed_workspace_abstraction.py`,
`tests/test_governed_run_9add44496178.py`,
`tests/test_governed_run_c847e01d15fe.py`, and
`tests/test_commissioning_dependencies.py`. Inspect their real collection,
pass, skip, and failure counts and audit changed paths after every repair.
The entire `python3 -m pytest tests/ -q` suite is required. Passing only the
new regression test is not done, and a focused green result must never be
reported as complete-suite closure. Existing sysdiff, fixture, benchmark,
commissioning, and malformed-input tests remain in scope through that full
command rather than being replaced by a new abstraction-only oracle.

# Verification

Map the repair evidence directly to the contract. **AC-1** is satisfied only
when the focused symlink/direct-argv/blast-radius regression, every affected
compatibility module, and the changed-path audit all exit successfully with
their actual counts recorded. Confirm that rejected claims create no sentinel,
accepted claims run with the governed cwd, and containment errors precede
schema loading. **AC-2** is satisfied only by an exit-0
`python3 -m pytest tests/ -q` run from the governed workspace, with expected
collection and no hidden, filtered, timed-out, or newly skipped cases. A
worker exit code, preserved validator claim, or focused test cannot substitute
for this suite.

For **AC-3**, preserve and hash-check the unchanged
`tests/user_journeys_manifest.json` and its command allowlist, then run the
existing hash-pinned smoke route through `tests/smoke_manifest.json`,
`tests/smoke_start.py`, `tests/check_sysdiff_smoke.py`, `scripts/smoke.sh`,
and `make test`. Record each command’s real exit status, start/check result,
blocking-error field, helper/manifest hashes, and observed output. Only after
AC-1 and AC-2 are green, independently replay every named and exploratory
journey from the pinned manifest through the existing user-simulation gate.
Verify structural result coverage, direct allowlisted argv re-execution,
canonical cwd, exit codes, claimed output, findings, workspace-relative
artifacts, and complete journey coverage. A skipped, substituted, altered, or
unverifiable journey is not AC-3 evidence, and prior run artifacts cannot
manufacture a pass.

Finally, run the playbook’s strict lint/validation path and an independent
review at the existing threshold. Compare `git diff --name-only` with the
repair allowlist and use `git diff --check`; explicitly confirm no changes to
`tests/user_journeys_manifest.json`, smoke inputs, commissioning packets or
checkers, `Makefile`, `src/sysdiff.c`, sysdiff CLI behavior, installation,
packaging, release, networking, or unrelated product tests. Report only
commands actually executed, preserve the origin run as FAILED, and distinguish
current repair evidence from historical evidence and worker narrative.

# Risks

The main risk is fixing the wrong layer because the current checkout may carry
candidate test or validator changes even though the origin run is failed. The
preserved attempt output and a pre-change source/test diff are therefore
mandatory. A symlink fixture that points to a directory still under `tmp_path`
would falsely exercise schema validation rather than escape containment; the
fixture must resolve outside the canonical root. Conversely, changing path
resolution only in one structural dispatcher could leave manifest, contract,
seed, or finding-artifact callers opening unsafe paths through
`_load_json_artifact`. Centralize the check or prove every caller uses the
same helper, and preserve fail-closed errors for missing and malformed files.

Shell parsing has a second-order injection risk: broad raw-text operator
matching rejects harmless quoted arguments, while permissive parsing can allow
pipelines or redirections to be misrepresented as direct execution. Keep
quote-aware operator detection, shell-word parsing, token-prefix matching,
environment-assignment handling, no-shell process creation, and the zero
verified-claims failure as one invariant. The blast-radius test can also be
weakened accidentally while avoiding self-match; assemble only the oracle’s
test data, retain explicit assertions for each forbidden class, and verify
the source scan against the intended files.

The pinned journey and smoke manifests are authority, not repair targets.
Changing them, widening or shrinking the command allowlist, hiding a journey,
editing smoke helpers, or converting a failure to a skip creates
`ORACLE_TAMPERING` or `RESULT_FABRICATION`. Touching `Makefile` or
`src/sysdiff.c` risks `BLAST_RADIUS` and would conflate a Python governance
repair with product behavior. Commissioning assets may encode repository
ownership and path assumptions, so audit them for compatibility but leave
them immutable. If the full suite, smoke route, journey replay, validator
lint, or independent review cannot complete, stop with the failed gate and
name the missing evidence rather than calling the repair done.
