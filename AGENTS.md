# Agent Guide: linux-utilities

This repository is operated by the `linux-utilities` auto-orch mission from
`/home/lee/projects/agent-orch/missions/linux-utilities`.

This project uses AgentFlow: the markdown files in this repo are shared memory
between humans, auto-orch, Agent-Orch, and worker agents. Treat updates to those
files as part of the work, not as optional notes.

## Startup Protocol

At the start of every session, in order:

1. Read `AGENTS.md`.
2. Read `context.md` for current state and next action.
3. Read `result-review.md` for recently completed work.
4. Read `sprint-plan.md` for current sprint tasks and priorities.
5. Read `WHERE_AM_I.md` for product-level orientation.
6. Read `project-plan.md`, `product-definition.md`, and `architecture.md` when
   scope or technical direction is unclear.
7. Check the sibling runs root `../linux-utilities-agent-orch-runs/` and the
   latest dashboard before assuming manual implementation is appropriate.

If asked to set up, launch, resume, or report on governed work, read
`OPERATE.md` and follow its generate -> lint -> human approval ->
`launch-workflow --detach` -> relay-banner sequence. Auto-orch should author
playbooks and launch Agent-Orch through the real CLI; do not replace that path
with ad hoc scripts.

## Mission

Build small, elegant Linux utilities in C. The first utility is `sysdiff`.

## Constraints

- Keep each utility intentionally small and auditable.
- Prefer ISO C17 or C23.
- Avoid unnecessary dependencies, services, networking, telemetry, and hidden
  runtime behavior.
- Treat warnings, undefined behavior, unsafe input handling, and unclear
  ownership as defects.
- Use plain text or SQLite only when persistence is needed.

## Quality Gates

Release-quality work should run GCC, Clang, `-Wall -Wextra -Wpedantic -Werror`,
clang-format, clang-tidy, cppcheck, Clang static analyzer when practical,
AddressSanitizer, UndefinedBehaviorSanitizer, Valgrind, unit tests,
integration tests, regression tests, and fixture tests.

## AgentFlow Updates

- Update `context.md` and `result-review.md` when a governed run, sprint slice,
  or meaningful manual intervention completes.
- Update `sprint-plan.md` when sprint tasks change state.
- Keep Agent-Orch run evidence outside the workspace in
  `../linux-utilities-agent-orch-runs/`.
- Preserve strong smoke and review-verdict gates on code-producing playbooks.
