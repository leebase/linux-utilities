# Governed Workspace Abstraction Implementation Plan

## Architecture

This is a bounded recovery of the failed governed-workspace-abstraction
delivery, not a sysdiff feature change. Preserve the repository-owned pinned
`tests/user_journeys_manifest.json` oracle as the evaluator authority and keep the
contract at `docs/governed-workspace-abstraction-contract.md` as the source of
AC-1 through AC-10. The implementation boundary is
`playbooks/governed-workspace-abstraction.yaml`: it must declare workspace-
relative inputs, invoke the validators with the contract path, pin the
manifest before accepting results, and keep producer repair writes separate
from the manifest that judges them. The failed origin's missing AC-4 coverage
and malformed user-result shape must be repaired through this governed path;
no old run evidence is promoted to a pass.

Resolve every manifest, seed, contract, result, finding, and playbook path
from the canonical workspace root. Normalize POSIX separators, reject empty,
absolute, root, `.`, parent-escaping, and symlink-escaping paths, and use that
root as `cwd` for every command. Parse `command_allowlist` and
`commands_run[].command` with shell-word parsing; compare complete tokens as
argv prefixes and execute the matched argv directly without a shell. Reject
shell operators, malformed or unmatched claims, wrong-cwd execution, and zero
verifiable claims. Require the canonical result object (`journeys` and
`findings`), journey fields (`name`, `status`, `steps_taken`, `commands_run`),
command fields (`command`, integer `exit_code`, optional observed
`stdout_contains`), and finding fields (`id`, `severity`, `journey`, `problem`,
`reproduction`, `expected`, `actual`, `proposed_fix`, with optional
`observations` and `artifacts`).
Accept only `human`, `mission`, `author`, and `exploratory`, default omitted
authority to `author`, require real contract traces for non-exploratory
journeys, and preserve seeded journeys at equal or stronger authority. The
evaluator may write only user-test results, findings, and scratch evidence. Pin
the current manifest SHA-256
`0d21f5624b734e7b4ff58e02a42190bde9818cc2ae02e272ae964a72564bfbcc` before
repair and user simulation. The closed hazard classes are `PATH_ESCAPE`,
`COMMAND_INJECTION`, `ORACLE_TAMPERING`, `RESULT_FABRICATION`, and
`BLAST_RADIUS`; no new class or utility-facing status may be invented. The
repair does not change a utility CLI, so no man page is authored.

## Tests

Use the existing `tests/test_governed_workspace_abstraction.py` regression
surface as the focused oracle, with private temporary workspaces and negative
sentinels proving that rejected commands do not execute. Keep its AC-labelled
coverage for schema/default authority, malformed and duplicate JSON, path and
symlink containment, direct argv-prefix execution, shell rejection, authority
preservation, complete contract traces, manifest tampering, result discipline,
canonical finding fields, closed hazard classification, smoke compatibility,
and bounded non-product scope. Add explicit fixtures for malformed and
unmatched command claims, shell operators, wrong `cwd`, zero verifiable claims,
missing result fields, exit/stdout mismatches, and failed journeys without
actionable findings. The plan must preserve, collect, and run the three
compatibility modules
`tests/test_governed_run_9add44496178.py`,
`tests/test_governed_run_c847e01d15fe.py`, and
`tests/test_commissioning_dependencies.py` unchanged in meaning.

The explicit compatibility blast radius is
`tests/test_governed_run_9add44496178.py`,
`tests/test_governed_run_c847e01d15fe.py`,
`tests/test_commissioning_dependencies.py`, `tests/smoke_manifest.json`,
`tests/smoke_start.py`, `tests/check_sysdiff_smoke.py`, `scripts/smoke.sh`,
`README.md`, and `CHANGELOG.md`. Also preserve the smoke fixture
`tests/test_sysdiff_fixture.sh`. These files are read-only compatibility
inputs for this recovery except for the separately declared explanatory
documentation work in `README.md` and `CHANGELOG.md`; the smoke manifest,
helpers, fixture, and script must remain hash-pinned and unmodified. The
focused abstraction tests may assert this boundary, but may not weaken the
historical product or commissioning assertions.

The AC mapping below is deliberately six-way: every acceptance check names
the focused regression, the playbook and pinned oracle, deterministic smoke,
the independent user simulation, and the independent review. A row is not
accepted merely because its focused test passes.

| Contract check | Existing `tests/test_governed_workspace_abstraction.py` regression surface | Playbook and pinned oracle | Deterministic smoke | Independent user simulation | Independent review |
| --- | --- | --- | --- | --- | --- |
| AC-1 — schema acceptance | `test_manifest_accepts_valid_schema_and_author_default` validates the committed named journeys and allowlist, optional fields, and omitted-author default. | `playbooks/governed-workspace-abstraction.yaml` loads `tests/user_journeys_manifest.json` and enables the structural/contract validators before execution; the pinned oracle must remain valid. | Step `step_08_user_smoke_gate` runs the unchanged `tests/smoke_manifest.json` -> `tests/smoke_start.py` -> `tests/check_sysdiff_smoke.py` -> `scripts/smoke.sh` chain as aggregate compatibility evidence. | `step_08b_user_simulation_gate` reads the pinned manifest and reports every named journey, proving the accepted schema is the evaluator input. | `step_09_review_verified_slice` checks the schema test, manifest contents, and validator configuration, and records the complete-suite check in the review verdict. |
| AC-2 — malformed-manifest rejection | `test_manifest_rejects_invalid_json_duplicate_keys_types_empty_fields_and_authority` and `test_duplicate_manifest_keys_are_rejected_without_execution` assert path-specific fail-closed errors and no sentinel execution. | The playbook validates JSON, duplicate keys, required fields, types, and closed authority before any command claim; the pinned `tests/user_journeys_manifest.json` cannot be replaced. | Smoke remains the pinned existing route; its unchanged hashes and successful `scripts/smoke.sh` run show malformed abstraction input did not replace smoke. | The independent tester must use only the pinned oracle; `user_journeys_all_passed` and `user_journeys_execution_verified` reject malformed or altered input before accepting a result. | The reviewer reruns/reports the full `tests/` command, inspects the negative tests and fail-closed ordering, and treats any bypass as a repair finding. |
| AC-3 — workspace-relative resolution | `test_workspace_paths_are_root_relative_and_symlink_contained` and `test_workspace_rule_paths_fail_closed_for_symlink_escape` cover normalization, foreign `cwd`, lexical escapes, and symlink escapes for all governed path roles. | The playbook supplies only relative POSIX paths and requires canonical-root resolution for manifest, seed, contract, result, finding, and playbook paths; the manifest oracle is resolved from that root. | Smoke starts from the governed root and retains the pinned helper chain, proving its path meaning is not dependent on a tester's incidental directory. | `step_08b_user_simulation_gate` runs from the governed root, records workspace-relative artifacts, and its validators reject outside or current-directory-dependent claims. | The independent review compares path handling with the contract and checks the complete suite plus the final changed-path boundary. |
| AC-4 — direct allowlisted execution | `test_commands_use_shell_word_parsing_and_token_prefixes`, `test_rejected_claims_are_never_shelled`, `test_commands_use_governed_cwd`, and `test_zero_verifiable_claims_fail` cover shell-word parsing, token-by-token argv-prefix matching, direct argv execution, shell operators, malformed/unmatched claims, wrong cwd, side-effect sentinels, and zero claims. | The playbook's non-advisory `user_journeys_execution_verified` gate matches the pinned manifest's `bash scripts/smoke.sh` argv prefix token-by-token, sets governed-workspace cwd, rejects operators and malformed/unmatched claims, and never invokes a shell on claim text. | The smoke gate independently runs the literal allowlisted `bash scripts/smoke.sh` route and preserves all smoke helper hashes; smoke is not generalized into shell permission. | The independent tester records bare argv, actual integer exit code, and observed output for every journey; step 08b rejects operators, prefix misses, wrong cwd, and unverifiable claims before acceptance. | The reviewer inspects the no-shell implementation and negative tests, reproduces the exact full-suite command, and flags any substring match, invented execution evidence, or zero-claim pass. |
| AC-5 — journey authority | `test_authority_order_and_seed_cannot_be_weakened` checks all four values, defaulting, ordering, unknown values, and removal/demotion of seeded journeys. | The playbook preserves the pinned author journeys and requires an out-of-scope seed if human/mission authority is introduced; repair cannot edit the oracle or weaken a seed. | Deterministic smoke uses its own pinned manifest and does not grant journey authority or substitute for authority validation. | The independent tester reads the same pinned journey authorities and cannot promote, demote, remove, or rewrite them while producing results. | The reviewer checks authority comparisons, seed scope, manifest pin evidence, and the full-suite result before approving the verdict. |
| AC-6 — contract traces | `test_contract_traceability_covers_all_acceptance_ids` and `test_exploratory_journeys_do_not_satisfy_missing_contract_coverage` require real traces for every required journey and all AC-1 through AC-10. | The playbook passes `contract_path` to the traceability validator; the pinned manifest supplies required traces and keeps exploratory coverage supplemental. | The unchanged smoke route is classified only as aggregate compatibility evidence and cannot satisfy missing contract traces. | Step 08b must attempt every pinned journey, including exploratory coverage, while its structural gate verifies journey-to-AC coverage against the contract. | The reviewer maps the contract IDs to manifest journeys and focused tests, then checks the complete-suite evidence and verdict threshold. |
| AC-7 — immutable authority during repair | `test_manifest_pin_rejects_hash_trace_and_allowlist_tampering` mutates copies to remove/demote seeds, reduce traces, or narrow commands and requires rejection before result acceptance. | The playbook's step-07 hash check pins `tests/user_journeys_manifest.json`; producer repair omits it from `allowed_paths`, and step 08b checks the same hash before judging results. | Step 08 pins `tests/smoke_manifest.json`, `tests/smoke_start.py`, `tests/check_sysdiff_smoke.py`, and `scripts/smoke.sh`, so smoke evidence cannot be rewritten either. | The independent tester may write only `artifacts/user-test` and `tmp`; altered manifest hash, authority, traces, or allowlist fails before user evidence converts to acceptance. | The reviewer inspects producer/evaluator scope and both pin records, reruns the exact full suite, and rejects a verdict that relies on mutable journey authority. |
| AC-8 — result and failure discipline | `test_result_requires_canonical_journey_fields`, `test_findings_require_canonical_fields_and_artifacts`, and `test_execution_verified_rejects_mismatched_exit_output_and_zero_claims` cover omitted journeys, empty steps/claims, every required finding field, actionable evidence, exit/output mismatches, malformed findings, and zero verifiable commands. | The playbook requires the `journeys`/`findings` object, complete journey and command fields, complete finding shape, workspace-relative evidence, direct-command reproduction, and both structural and execution validators against the pinned oracle. | Smoke records its own start/check result and blocking errors through the existing helpers; it is not used to fill missing journey steps or findings. | Step 08b writes `artifacts/user-test/result.json` and append-only `findings-log.md`, attempts every journey, and must reproduce real exit codes and observed stdout before passing; every failed journey carries a complete finding. | The reviewer reads the result and findings log, verifies the complete-suite claim, checks that validator failures halt or route to repair, and treats omitted journeys or unactionable findings as review blockers. |
| AC-9 — existing smoke compatibility | `test_smoke_manifest_and_helper_chain_remain_unchanged` asserts the smoke manifest/helper/script/`make test` route and its separation from direct journey evidence. | The playbook keeps the abstraction additive, does not edit smoke inputs, and makes smoke and user simulation separate sequential gates. | Step 08 runs the deterministic `tests/smoke_manifest.json`, `tests/smoke_start.py`, `tests/check_sysdiff_smoke.py`, `scripts/smoke.sh`, and `make test` path with hash checks. | Step 08b consumes smoke output only as aggregate context and explicitly reports direct journey evidence separately. | Step 09 reviews smoke artifacts, the compatibility modules, the unchanged path list, and the full suite before issuing an independent verdict. |
| AC-10 — bounded blast radius | `test_blast_radius_is_additive_and_non_product` checks the five closed hazard classes, declared surfaces, no runtime/network/release behavior, unchanged sysdiff behavior, no CLI or man-page change, and compatibility-module membership. | The playbook limits implementation/repair outputs to its declared paths and explicitly excludes product source, CLI, man page, network, install, package, release, and manifest mutation. | Smoke hash-pins the existing manifest, helpers, fixture, and script and runs the existing route rather than adding a new product oracle. | The independent tester is restricted to result/findings/scratch paths and cannot edit source, tests, smoke, README, CHANGELOG, or the pinned manifest. | The reviewer audits all changed paths, playbook scopes, hazard classification, compatibility tests, smoke evidence, documentation wording, absence of a man-page obligation, and the complete-suite result for boundedness. |

## Verification

Run the governed sequence in order: focused tests and manifest authoring,
playbook implementation, documentation, repair, deterministic smoke,
independent user simulation, and independent review. In step 07, hash-check
the immutable journey manifest and run the focused abstraction module together
with `tests/test_governed_run_9add44496178.py`,
`tests/test_governed_run_c847e01d15fe.py`, and
`tests/test_commissioning_dependencies.py`. Then run the complete
`tests/` suite from the governed workspace root using the playbook's exact
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
command; a passing focused module alone is not acceptance. Also run the
repository quality routes that are available and relevant, `git diff --check`,
and a changed-path audit against the declared playbook scopes. Preserve real
exit codes, collected counts, skips, and unavailable-tool reasons.

Step 08 must produce deterministic smoke evidence from the unchanged
`tests/smoke_manifest.json` -> `tests/smoke_start.py` ->
`tests/check_sysdiff_smoke.py` -> `scripts/smoke.sh` -> `make test` chain with
empty blocking errors and valid pinned hashes. Step 08b must independently
attempt every pinned journey, including exploratory coverage, and produce a
result with the canonical top-level `journeys` and `findings` arrays, concrete
steps, direct argv claims, reproduced integer exit statuses and observed
outputs, and actionable workspace-relative evidence for failures. Invalid
schema, authority, path, command, hash, result, or finding data must fail
closed before execution or acceptance; an unmatched claim or zero verifiable
claims must not be converted into a pass. Its structural and non-advisory
execution validators must pass before step 09. Step 09 must independently
review the contract, plan, playbook, focused and compatibility tests, smoke
result, user result, and documentation; its verdict must be clean through the
High threshold and its checks-run claims must reproduce exactly.

Definition of done is a passing complete `tests/` suite plus the focused and
three compatibility regressions, deterministic smoke, successful independent
user simulation, bounded diff, and independent review. Do not declare done
from a passing `tests/test_governed_workspace_abstraction.py` alone. This
plan records no future result: each claim above must be backed by later
governed-run evidence, and failures must halt or return to the declared repair
step rather than being hidden by changed tests, smoke or manifest data.

## Risks

The primary safety risks are the contract's closed `PATH_ESCAPE`,
`COMMAND_INJECTION`, `ORACLE_TAMPERING`, `RESULT_FABRICATION`, and
`BLAST_RADIUS` classes. A lexical path check can still escape through a
symlink or foreign `cwd`; mitigate with canonical workspace resolution,
normalized relative paths, resolved-candidate containment checks, and explicit
workspace `cwd`. A permissive JSON parser can accept duplicate keys, and a
shell runner can execute operators hidden in a journey claim; use duplicate-key
rejection, closed enums, shell-word parsing, token-by-token prefixes, direct
argv execution, and negative sentinels. Keep diagnostics path-specific without
executing untrusted text.

The failed recovery could become green by changing the manifest, removing a
journey, reducing traces, narrowing the allowlist, or writing a result that
omits difficult journeys. Prevent that by pinning
`tests/user_journeys_manifest.json` before repair and user simulation, keeping
producer writes away from it, requiring every journey and actionable failure
evidence, and allowing the evaluator to write only result, findings, and
scratch paths. Any pin mismatch is a halt condition, not a repair opportunity.

Compatibility drift is the remaining blast-radius risk: the abstraction could
replace the sysdiff smoke route, alter historical governed-run assertions, or
turn README/CHANGELOG wording into an unsupported release claim. Preserve and
hash-check the named smoke files, run the complete suite, inspect all changed
paths, and require independent review of both code and evidence. A green
simulation proves only the bounded journey-verification contract; it does not
authorize product behavior changes, networking, installation, packaging,
release, publication, deployment, a new man page, or a claim about who ran a
command. Any hazard outside the five named classes is a contract gap and must
halt for explicit contract revision rather than being silently folded into a
passing result.
