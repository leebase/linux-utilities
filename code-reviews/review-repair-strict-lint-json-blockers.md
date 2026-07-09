# Review: Repair — Strict-Lint and JSON Blockers

**Run / step under review:** `d3b2e8bc606c` → `step_03_review_verified_repair`, attempt 2
**Reviewer:** claude_code / sonnet (slice_reviewer role)
**Date:** 2026-07-08
**Verdict:** FAIL — one High finding (bugfix template src pin conflict); two Medium findings remain unresolved from attempt 1; one new Medium finding added (smoke_runner not in workers.allowed)

---

## Checks Run

`python3 -m compileall .agent-orch playbooks` — exit 0. The `.agent-orch/` directory contains only YAML; `playbooks/` and `playbooks/templates/` contain only JSON. No Python source files are present in either tree, so `compileall` found nothing to compile and exited cleanly. No Python syntax errors are present in the reviewed tree.

---

## User Smoke Artifact

`artifacts/user-smoke/result.json` records `./scripts/smoke.sh` at exit code 0 with empty stderr (attempt 4, run `d3b2e8bc606c`, step `step_02_user_smoke_gate`). The four oracle sha256 pins embedded in the repaired playbooks were verified against the current working-tree files:

| File | Pinned hash (prefix) | Actual sha256 (prefix) | Match |
|---|---|---|---|
| `scripts/smoke.sh` | `daca1ec8…` | `daca1ec8…` | ✓ |
| `tests/test_sysdiff.sh` | `ac7ced42…` | `ac7ced42…` | ✓ |
| `Makefile` | `56a1c626…` | `56a1c626…` | ✓ |
| `src/sysdiff.c` | `8df0bbfa…` | `8df0bbfa…` | ✓ |

All four pins match the current working tree. The smoke artifact is consistent with the oracle. The smoke passed without `stderr`, confirming no build or test regression in the baseline.

---

## Lens Notes

### Strict-Lint Compatibility

The repair resolved the previously blocking placeholder clusters:

- `__JUDGE_HARNESS__` was replaced with `pi_cli` in the `authoring_notes` and in the `semantic_check` validator in `repair_before_review_feature_delivery.yaml`.
- Per-step `routing` blocks with `__TEST_AUTHOR_HARNESS__`, `__TEST_AUTHOR_MODEL__`, `__PRIMARY_HARNESS__`, `__PRIMARY_MODEL__`, `__FALLBACK_HARNESS__`, and `__FALLBACK_MODEL__` were removed from steps 04 and 05 of the main delivery template.
- The `execution` block carrying `__TASK_TYPE__` and `__CAPABILITY__` was removed from step_05.
- All-zeros sha256 sentinel values in smoke gates were replaced with concrete oracle hashes.
- Top-level `routing` and `roles` blocks were added to all five playbooks; `role` fields were added to all steps that lacked them.

Remaining `__PLACEHOLDER__` values (`__SLICE_NAME__`, `__SLICE_MODULE__`, `__PROJECT_SRC__`, `__README_REQUIRED_HEADING__`, `__USER_GUIDE_REQUIRED_HEADING__`) are intentional template-authoring sentinels documented in `authoring_notes` ("Replace every __PLACEHOLDER__ before launch and lint with --strict"). They do not constitute strict-lint blockers in the template-library context; they become blockers only when a specialist attempts to launch without substitution.

**Finding F001 (High):** `playbooks/templates/bugfix.yaml` step_02 pins `src/sysdiff.c` at sha256 `8df0bbfa…`, but step_01's `allowed_paths` explicitly includes `src/`. Any successful C-source bugfix in step_01 writes a modified `src/sysdiff.c`, producing a new hash. Step_02's `file_hash_matches` check then halts the run. The `on_fail` retry message misleads by stating the oracle changed "outside this playbook's allowed paths", when the change was a legitimate repair done by step_01 itself. The template cannot serve its primary use case — fixing bugs in `src/sysdiff.c` — without the smoke gate blocking every run. This finding is unchanged from attempt 1.

The fix is to remove the `file_hash_matches` entry for `src/sysdiff.c` from `bugfix.yaml` step_02. The oracle mechanism (`scripts/smoke.sh`, `tests/test_sysdiff.sh`, `Makefile`) is already protected by the three remaining pins; the step_01 `allowed_paths` constraint already limits what the bugfix worker can write; pinning the subject under repair is counterproductive.

**Finding F004 (Medium):** All three templates that include a smoke gate (`bugfix.yaml` step_02, `onboarding_ci_bootstrap.yaml` step_02, `repair_before_review_feature_delivery.yaml` step_08) use `"worker": "smoke_runner"`. The `smoke_runner` harness does not appear in the `workers.allowed` list in `.agent-orch/project.yaml` (which lists `fake_worker`, `codex_cli`, `pi_cli`, `claude_code`, `grok_cli`). A strict-lint pass that validates step `worker` fields against `workers.allowed` would flag all three smoke gates as referencing an unregistered harness, failing the lint before launch. Even if the current linter version is permissive on this check, an unregistered worker produces an opaque failure at runtime if Agent-Orch attempts to dispatch to it. The fix is to add `smoke_runner` to `workers.allowed` in `.agent-orch/project.yaml`, or to replace `"worker": "smoke_runner"` with an appropriate registered harness in all three smoke gate steps.

### Autonomous-Run Safety

The `run_policy` (`on_step_failure: halt`, `require_validation_pass_to_advance: true`) is correctly set in all five playbooks. All steps carry explicit `role` or `worker` bindings. Review steps use `checks_run_match` and `review_verdict_clean` with `severity_threshold: High`, correctly enforcing route-back on High/Critical findings.

**Finding F003 (Medium):** The `step_02_approve_contract` (`human_approval`) step was removed from `repair_before_review_feature_delivery.yaml`. Step IDs jump from `step_01_define_slice_contract` directly to `step_03_plan_slice_delivery`. Autonomous runs now proceed from contract authoring to planning and implementation without any human checkpoint on contract intent. The `authoring_notes` array does not flag this gap or advise specialists to consider re-inserting a human gate. The remaining safety controls (halt on failure, validation pass required, review verdict gate with repair cycle) catch implementation failures but not contract-intent failures. This finding is unchanged from attempt 1.

The fix is to add a note to `authoring_notes` stating that the human approval gate between step_01 and step_03 was removed for autonomous-mode runs, and that specialists should evaluate re-inserting a `human_approval` step after `step_01_define_slice_contract` for high-stakes slices where contract correctness is load-bearing.

### JSON-Only Output Assumptions

The `json_schema` + `review_verdict_clean` + `checks_run_match` triple-gate is consistently applied in all three review steps (`bugfix.yaml` step_03, `onboarding_ci_bootstrap.yaml` step_03, `repair_before_review_feature_delivery.yaml` step_09). The `json_parse` validator is present on all smoke artifact outputs. Review step missions explicitly instruct the worker to include only deterministic allowlisted commands in `checks_run`.

**Finding F002 (Medium):** `repair_before_review_feature_delivery.yaml` step_08 hardcodes the smoke output path as `artifacts/user-smoke/result.json`. Sibling templates use discriminated names (`bugfix-result.json`, `onboarding-ci-bootstrap-result.json`). The hardcoded path collides with the already-committed smoke artifact from the current run (`d3b2e8bc606c`) and provides no `__` sentinel to alert a specializing author to rename it before launch. If a specialist derives a new slice playbook without renaming this path, the gate silently overwrites evidence from prior runs. This finding is unchanged from attempt 1.

The fix is to change the output path to `artifacts/user-smoke/__SLICE_NAME__-result.json` (and update the matching `file_exists` validator accordingly), consistent with the naming convention in sibling templates.

### Smoke-Oracle Grounding

Hash pins are verified against the current working tree (all four match; see table above). The `onboarding_ci_bootstrap.yaml` smoke gate is structurally sound: step_01 writes only to `.github/` and `docs/`, leaving none of the four pinned files reachable from the implementation worker. The `bugfix.yaml` smoke gate has the concrete F001 conflict described above.

The `repair_before_review_feature_delivery.yaml` step_08 pins `src/sysdiff.c` at `8df0bbfa…`, while step_07 lists `__PROJECT_SRC__/` in `allowed_paths`. When specialized to `src/` for a sysdiff slice, and when step_07 outputs a modified `src/sysdiff.c` as part of repair-and-verify, step_08 will fail its pin. This latent conflict is masked by the placeholder but is the same structural defect as F001, deferred to specialization time. The `src/sysdiff.c` pin in the main delivery template should be replaced with placeholder sentinels (`__SMOKE_SUBJECT_FILE__` / `__SMOKE_SUBJECT_HASH__`) so specialists are forced to decide at specialization time whether to pin the implementation file and at what hash.

### Maintainability

The addition of top-level `roles` blocks eliminates per-step routing duplication and makes worker assignment legible at a glance. The `markdown_headings_present` gates with `min_chars_under_heading` in `starter_proof.yaml`, `bugfix.yaml`, and `docs_only.yaml` strengthen structural validation beyond bare `file_exists` checks. The removal of the `execution` block from `step_05_implement_slice` eliminates an unresolvable placeholder cluster.

F002's naming inconsistency between smoke artifact paths reduces template composability and requires a maintainer to audit each template's artifact names to prevent collisions. F004's unregistered `smoke_runner` worker creates a gap between the playbook worker declarations and the project's worker registry that must be kept in sync manually.

---

## Summary

The repair resolved all previously blocking placeholder clusters and brought all five templates to a state where they can be linted with `--strict` once sentinel placeholders are substituted at specialization time. Three findings from attempt 1 remain unresolved: F001 (High — `bugfix.yaml` pins the subject under repair, making the template self-defeating for C-source bugfixes), F002 (Medium — hardcoded smoke artifact path in the main delivery template), and F003 (Medium — undocumented removal of the human approval gate). Attempt 2 adds F004 (Medium — `smoke_runner` worker not in `workers.allowed`, a potential strict-lint blocker and runtime dispatch failure). The verdict remains fail on account of F001.
