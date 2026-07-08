# OPERATE — the prescribed path for a visiting agent in linux-utilities

> You were asked to set up, launch, or report on a governed Agent-Orch
> workflow for this repo. Follow this sequence in order.

1. Orient: read `AGENTS.md`, `new-project-onboard.md`, and the sprint plan.
   `python3 -m agent_orch.main quickstart` prints the condensed command form.
2. Generate a workflow from a template instead of writing one from scratch:
   `python3 -m agent_orch.main init-workflow repair_before_review_feature_delivery --repo . --output-name <workflow_name>`
3. Specialize the playbook from the sprint plan: missions, narrow
   `allowed_paths`, and strong validations (`json_schema`, hardened
   headings, `require_collected_tests`) rather than bare `file_exists`.
   Keep the template's `human_approval` step and `semantic_check` gates;
   replace `__JUDGE_HARNESS__` with a real read-only judge harness
   (normally `pi_cli`) on a different route than the producing steps.
4. Lint the gates and fix every finding:
   `python3 -m agent_orch.main lint-playbook --strict playbooks/<workflow_name>.yaml`
5. Stop for human approval of the playbook before launching anything.
6. Launch detached:
   `python3 -m agent_orch.main launch-workflow playbooks/<workflow_name>.yaml --workspace . --detach`
   Run evidence defaults to the sibling runs root `../<repo>-agent-orch-runs/`
   so untrusted workers cannot reach it; pass `--runs-dir` only when you must
   override that location.
7. Report the launch banner verbatim. You are an untrusted worker in the
   Agent-Orch trust model: relay the banner lines or `launch-report.json`
   exactly — never a paraphrase of the run id or dashboard path.

Watch the printed dashboard path, or bookmark
`../<repo>-agent-orch-runs/latest/dashboard.html` for the newest run. The
`latest` pointer is presentation-only convenience, never trusted evidence.

If the run parks in WAITING_APPROVAL at a `human_approval` step (CLI exit
code 3), tell the human the exact commands and stop — approval is the
human's decision, never yours:
`python3 -m agent_orch.main approve <run_dir> <step_id>` then
`python3 -m agent_orch.main resume-run <run_dir>`.

If the failed step was repaired manually or the producing worker is unavailable,
resume with `python3 -m agent_orch.main resume-run <run_dir> --validation-only`.
That mode records validation-only worker evidence and does not rewrite
workspace files.
