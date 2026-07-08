# Agent Guide: linux-utilities

This repository is operated by the `linux-utilities` auto-orch mission from
`/home/lee/projects/agent-orch/missions/linux-utilities`.

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
