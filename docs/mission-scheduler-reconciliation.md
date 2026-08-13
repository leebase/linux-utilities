# Linux Utilities scheduler reconciliation

Date: 2026-08-01  
Mission: `linux-utilities`  
Prior commissioning run: `e5e872615eed`

## Result

The Linux Utilities autonomous loop was already disabled when this session
inspected the live user crontab. No crontab mutation was necessary or made:
the exact loop entry is preserved as a comment. The separate scratch-pruner
entry remains active and is maintenance, not autonomous mission scheduling.

The supplied premise that the mission remains halted is not true in the live
configuration. Auto-Orch reports `mission is armed`; `state.md` contains
`loop_state: idle` and no `value_exhausted: true`. This is a separate
configuration/state drift and remains unresolved. This session did not alter
mission state, re-arm anything, launch a run, restore autonomous execution,
push, or change Agent-Orch.

## Cron configuration before and after

The relevant crontab block was captured with `crontab -l` at session start.
The before and after configurations are identical because the loop was already
commented. The exact preserved entry is:

```cron
# linux-utilities auto-orch: hourly, ALL DAY (widened from 00:00-07:00 on
# 2026-07-28 by Lee — "get some reps under our belt"). 24 cycles/day rather
# than 8: 3x the model spend, and 3x the scratch, hence the prune below.
# Halts itself after 5 consecutive empty cycles, so a dry backlog costs ~5h.
# linux-utilities auto-orch: hourly, Codex gpt-5.6-sol (envision/reconsider/score/author) + Claude Fable 5 (ideate) two-round ideation, cursor_cli/grok-4.5 coding, claude_code/claude-opus-4-8 review - enabled 2026-07-17 by Lee
# RE-ARMED 2026-07-18 after OS2 phase 2 containment shipped (d52c4db)
# REPOINTED 2026-07-27: auto-orch split into its own repo; paths moved.
# RESTORED 2026-07-28: schedule was correct but every fire silently no-opped --
#   the split deleted the four untracked loop-state docs + cycle-reports/, so
#   Mission.load failed preflight. State rebuilt and committed; preflight errors=0.
#   Reviewer model updated claude-opus-4-8 -> claude-opus-5.
# PAUSED 2026-07-31 by Lee: keep disarmed pending (1) repository-identity protection, (2) scratch-pruner path fix, (3) crew-vs-mission.md routing reconciliation.
#5 * * * * cd /home/lee/projects/auto-orch && ( AGENT_ORCH_CURSOR_TIMEOUT_SECONDS=1500 AGENT_ORCH_CLAUDE_TIMEOUT_SECONDS=1200 AGENT_ORCH_CLAUDE_BINARY=/home/lee/.local/bin/claude PATH=/home/lee/.local/bin:/home/lee/.npm-global/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/flock -n /tmp/auto-orch-linux-utilities.lock /home/lee/projects/auto-orch/.venv/bin/python -m auto_orch.main --missions-root ./missions loop linux-utilities ) >> /home/lee/projects/auto-orch/missions/linux-utilities/cron.log 2>&1
```

The entry's association is the `loop linux-utilities` argument and its output
is `/home/lee/projects/auto-orch/missions/linux-utilities/cron.log`. Its
schedule is `5 * * * *` (hourly at minute 5). Its inline environment is:

- `AGENT_ORCH_CURSOR_TIMEOUT_SECONDS=1500`
- `AGENT_ORCH_CLAUDE_TIMEOUT_SECONDS=1200`
- `AGENT_ORCH_CLAUDE_BINARY=/home/lee/.local/bin/claude`
- `PATH=/home/lee/.local/bin:/home/lee/.npm-global/bin:/usr/local/bin:/usr/bin:/bin`

The command also uses the non-overlap lock
`/tmp/auto-orch-linux-utilities.lock` and the Auto-Orch virtualenv at
`/home/lee/projects/auto-orch/.venv/bin/python`.

To restore this exact schedule after separate authorization, remove only the
leading `#` from the preserved `#5 * * * * ...` line, then run the full
mission preflight and obtain explicit re-arm authorization. Do not restore it
as part of commissioning preparation.

## Operational verification

| Check | Result |
| --- | --- |
| Active `loop linux-utilities` cron entries | None |
| Active Linux Utilities path references | Scratch-pruner only (`45 4 * * *`), not mission execution |
| Linux Utilities mission state | `loop_state: idle`; no `value_exhausted: true` |
| Auto-Orch preflight | Exit 0; reports `[PASS] mission.state: mission is armed` |
| Active Linux Utilities/Agent-Orch process | None observed |
| Governed run launched in this session | No; no new run ID |
| Repository, packet, Agent-Orch, remote | Unchanged by this reconciliation |

The preflight result is safe with respect to execution because the scheduler
entry is disabled, but it is not the expected halted result. The session
therefore cannot truthfully claim that the mission and scheduler states agree.

## Other autonomous mission drift

The configured crontab entries were compared with the current mission state
files. No other enabled loop was found with `value_exhausted: true`:

| Mission | Scheduler | Observed state | Drift |
| --- | --- | --- | --- |
| `data-migration-factory` | Enabled hourly at `:15` | Idle; last cycle success | None observed |
| `employee-zero-resident` | Enabled daily at `06:20` | Idle; last cycle success | None observed |
| `elect-bob-pilot` | Disabled | No current state file | No actionable mismatch |
| `erd-tool` | Disabled | No current loop markers | No actionable mismatch |
| `rfp-factory` | Disabled/paused | No current state file | No actionable mismatch |
| `linux-utilities` | Disabled | Armed/idle | **Mismatch: scheduler disabled while mission is armed** |

No other mission was changed.

## Mission-state reconciliation and platform gap

The authoritative live state before and after this session is unchanged:

```text
<!-- auto-orch loop state -->
loop_state: idle
consecutive_empty_cycles: 0
<!-- end loop state -->
```

The state file contains no `value_exhausted: true` marker. Its counters,
backlog summary, last run ID/status, cycle report reference, and review history
were preserved exactly. The state-file SHA-256 was unchanged by the read-only
inspection and preflight.

The root cause is the state predicate in Auto-Orch: preflight considers the
mission halted only when the literal `value_exhausted: true` marker is present;
all other states, including normal `loop_state: idle`, are reported as
`mission is armed`. `loop_state` is therefore not itself a pause flag.

The supported transitions are asymmetric:

1. A real loop cycle that reaches the configured consecutive-empty threshold
   writes `loop_state: value_exhausted`, `value_exhausted: true`, a diagnosis,
   and a halt notice.
2. The supported `auto-orch rearm NAME --reason ...` command clears that halt
   and records an operator audit entry.

There is no supported operator pause/hold command and no state recognized as
“paused but commissioning-ready.” Reaching value exhaustion would require
launching a loop cycle and changing mission counters, which is prohibited for
this reconciliation. Adding `value_exhausted` by hand would misrepresent the
cause and edit generated loop state, so it was not done. Changing
`launch_approved` would alter mission configuration/readiness and would not
make preflight report the required halted mission-state result.

Accordingly, the exact before and after mission state are identical, and the
read-only preflight remains successful with `[PASS] mission.state: mission is
armed`. No governed work started and no mission state was modified.

This is a reusable platform state-model gap: Auto-Orch needs an explicit,
audited, reversible operator pause state that blocks autonomous execution while
remaining distinct from value exhaustion and does not alter backlog or failure
counters. Implementing that platform capability is outside this session.

## Recommendation

**Ready after specific follow-up.** The scheduler side is safely disarmed and
the commissioning packet and repository preparation remain valid. Before
claiming readiness for a separately authorized supervised commissioning run,
the platform must provide and use an explicit paused-state mechanism, then
read-only preflight must report that pause. This session did not alter
Agent-Orch, restore cron, re-arm the mission, launch a governed run, push, or
weaken a gate.
