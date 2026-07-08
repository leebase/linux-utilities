# Linux Utilities

Small, auditable Linux utilities built under the autonomous
`linux-utilities` mission.

The first utility is `sysdiff`: a lightweight C program that snapshots
important system state and reports changes between snapshots.

## Engineering Standard

- One executable per utility.
- Plain C, preferably C17 or C23.
- Minimal dependencies.
- `make` first; CMake only when it clearly simplifies the project.
- Automated quality gates for compiler warnings, formatting, static analysis,
  sanitizers, Valgrind, unit tests, integration tests, regression tests, and
  fixtures.
