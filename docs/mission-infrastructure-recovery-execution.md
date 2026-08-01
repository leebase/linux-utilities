# Mission Infrastructure Recovery Execution

## Findings

Local recovery work is observable and currently consistent: the repository
identity verifier accepts the expected linked-worktree layout, and the guarded
scratch-pruner finds no removable live-root candidates. Those results establish
detection and bounded cleanup, not trusted-boundary enforcement. The six
identity metadata paths have no immutable bit, so a worker-writable checkout
could still undermine a repository-local verifier unless a pinned external
control plane protects and runs it. Routing remains ambiguous, and the latest
completed autonomous run did not pass its smoke gate. The mission is therefore
not ready for re-arm.

## Evidence

The product checkout is `/home/lee/projects/linux-utilities`; the worker
checkout is `/home/lee/projects/linux-utilities-autonomous`. The identity JSON
check reported all 19 checks passed, including the expected linked-worktree
pointer, common directory, worktree administration paths, `main` worker HEAD,
`origin` URL `git@github.com:leebase/linux-utilities.git`, sanitized Git
environment, and no nested repository. The protection dry-run listed exactly
six paths: the worker `.git` pointer, repository `config` and `HEAD`, and the
worktree `HEAD`, `commondir`, and `gitdir`. `lsattr` showed no `i` attribute on
any of them; the recovery record states that the real `chattr +i` attempt was
denied by this host. No immutable protection is claimed.

The canonical autonomous scratch root is
`/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch`. Its
reported size is 2.2G, and the guarded dry run selected zero candidates. The
recovery record documents that earlier selected terminal spill roots had
matching evidence under `/home/lee/projects/linux-utilities-agent-orch-runs`.
The installed cron entry is directly readable and points to
`/home/lee/projects/linux-utilities/scripts/prune-agent-orch-scratch.sh`; the
autonomous mission loop remains commented out. Autonomous scheduling remains
paused.

The latest completed governed run is `9849a238752a`, status `FAILED`. Its
`step_08_user_smoke_gate` ran twice and halted both times with “Smoke check did
not pass before startup timeout.” The recorded smoke state was
`app_started: true`, `core_flow_completed: false`, `start_exit_code: 0`, and
`check_exit_code: -1`. This is not a successful current autonomous smoke run.

Routing is unresolved by direct inspection. `mission.md` prescribes
`implementation_worker` as `cursor_cli`/`grok-4.5`, `slice_reviewer` as
`claude_code`/`claude-opus-5`, and an independent `user_tester` as
`codex_cli`/`gpt-5.6-sol`. `config.yaml` selects the `mixed-flagship` crew;
its governed mandate instead prescribes Claude/Opus as primary and
Codex/Sol as reviewer, with Codex as judge and no `user_tester` entry.
`routing.py` gives mission-level workers/stages execution precedence over a
crew's stage map, while separately rendering the crew governed mandate into
the author prompt. That is not a deterministic authority rule. Neither
routing source was changed.

## Local Verification

The focused identity command
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/test_repository_identity.py -q` passed: 5 tests. The commands
`python3 scripts/check_repository_identity.py --json` and
`python3 scripts/check_repository_identity.py --protect --dry-run --json`
both passed; the latter made no changes and listed six paths. `bash -n
scripts/prune-agent-orch-scratch.sh` passed, and
`scripts/prune-agent-orch-scratch.sh --dry-run` reported zero candidates and
zero retained. Strict playbook lint passed with
`PYTHONDONTWRITEBYTECODE=1 python3 -m agent_orch.main lint-playbook --strict
playbooks/mission_infrastructure_recovery_validation.yaml`, reporting no lint
findings. `bash -n scripts/smoke.sh`, `bash -n tests/test_sysdiff_fixture.sh`,
and `bash -n tests/test_sysdiff.sh` passed. `git diff --check` passed.

The declared full-suite command
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
passed with 337 tests passed and 18 skipped. The read-only `lsattr -d` check
found no immutable flags. `crontab -l` read back the active guarded pruner
entry and the commented-out Linux Utilities autonomous loop. The checkout was
already dirty with broader recovery and product-history changes; the governed
worker changed only the execution report under `docs/`, and this closeout
preserves all intentional existing changes rather than discarding them.

The current recovery run `fe54e33800e9` finished `FAILED` after its two allowed
attempts. Both semantic validations could not obtain a judgment because the
judge exited with “No API key found for openai-codex”; the run evidence is
verified with 34 artifacts and no evidence-chain divergence. That harness
problem is not evidence of readiness or of a successful smoke run.

## Open Platform Decisions

An owner must provide trusted-boundary identity enforcement outside the
worker-writable checkout. The platform should pin the verifier or equivalent
guard, run it before and after each worker attempt, and halt on mismatch; the
worker must not be able to rewrite the authority it uses to validate itself.
The host's rejected immutable-bit operation leaves this decision open.

Lee must choose whether the mission charter or the `mixed-flagship` governed
crew map is authoritative, define precedence, and make primary,
implementation, reviewer, judge, and independent `user_tester` routes agree.
Until that policy exists, the contradictory producer/reviewer instructions and
the crew's missing tester route must remain unresolved; this report does not
choose between them.

The platform owner must also diagnose the smoke startup-budget failure shown by
run `9849a238752a`, then produce a fresh governed run with smoke exit 0 and a
clean review verdict. No local workaround, scheduling change, re-arm, routing
edit, or platform-repository change is authorized by this validation.

## Recommendation

**Not ready.** Local identity detection, scratch cleanup validation, focused
tests, shell syntax checks, playbook lint, and the identity protection dry-run
are useful evidence, but they do not establish immutable trusted-boundary
protection. The full suite also has the recorded read-only-filesystem failure,
and the latest completed autonomous smoke run failed twice. Do not treat the
verifier as structural enforcement, the zero-candidate dry-run as fresh cron
proof, or historical smoke artifacts as current success. Re-arm only after
trusted-boundary protection is evidenced, one routing authority and precedence
rule are explicitly chosen with an independent `user_tester` route, and a new
governed run completes smoke successfully with its review gates intact.
