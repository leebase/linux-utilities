# New Project Onboard for linux-utilities

This file is the platform-owned Agent-Orch onboarding guide for linux-utilities. It is generated from the platform template and refreshed explicitly with `python3 -m agent_orch.main refresh-onboarding .` whenever the base Agent-Orch contract changes. The refresh command rewrites only this platform-owned file and leaves repo-owned notes in `docs/project-onboarding.md` untouched.

Refresh is intended for repos that were scaffolded by Agent-Orch and still have `.agent-orch/project.yaml`, so the platform-owned guide can stay aligned with repo metadata instead of guessing.

## Platform-owned guidance

- Project name: linux-utilities
- Primary language: C
- Default worker: codex_cli
- Start with `AGENTS.md`, then read `docs/project-onboarding.md` for repo-owned notes. If you were asked to set up or launch a governed workflow, follow `OPERATE.md` — the generate, lint, human-approve, launch-detached, relay-the-banner sequence.
- For broad delivery work, prefer one governed workflow under `playbooks/`, validate it, run Agent-Orch, and monitor `dashboard.html`. For a single-sprint feature slice, start from `playbooks/templates/repair_before_review_feature_delivery.yaml` and specialize the placeholder allowed paths, validations, and routing fields before you run it. Keep the template's `human_approval` contract gate and its `semantic_check` judge gates, and replace `__JUDGE_HARNESS__` with a real read-only judge harness (normally `pi_cli`) on a different route than the producing steps.
- Use `launch-workflow` for the common path: it announces the run id, dashboard path, and `launch-report.json` before step 1 executes, keeps the dashboard refreshed during the run (including FAILED runs), and supports `--detach` for background execution. Run evidence defaults to the repo sibling `../linux-utilities-agent-orch-runs/`, outside the worker-writable workspace, and `latest/dashboard.html` under that runs root always points at the newest launched run.
- A run parked in WAITING_APPROVAL at a `human_approval` step (CLI exit code 3) is waiting for the human, not failed: the human runs `python3 -m agent_orch.main approve <run_dir> <step_id>` then `python3 -m agent_orch.main resume-run <run_dir>`. Approval is never implicit; agents relay the commands and stop.
- Failed or stale detached runs resume with `python3 -m agent_orch.main resume-run <run_dir>`; detached runs whose recorded executor PID is dead, zombie, or reused by another process are treated as stale without mutating the old run. If the failed step was repaired manually, or the producing worker is unavailable or usage-limited, use `python3 -m agent_orch.main resume-run <run_dir> --validation-only` so validators run against the current workspace without worker writes.
- Refresh this file instead of copying platform guidance into repo-owned notes.
- Refresh relies on `.agent-orch/project.yaml` so the generated guide stays tied to scaffolded repo metadata.
- Refresh never rewrites `docs/project-onboarding.md`; that file stays repo-owned.

## What belongs elsewhere

Repo-specific onboarding details, team notes, and local CI caveats belong in `docs/project-onboarding.md`.
