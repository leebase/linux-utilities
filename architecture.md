# Architecture

## Current architecture

- Primary language: C.
- Build system: `make`.
- Default worker runtime: `codex_cli`.
- Smoke surface: `scripts/smoke.sh` runs `make test`.
- First executable: `build/sysdiff` from `src/sysdiff.c`.

## Direction

- Keep parsing, comparison, and output formatting separable as `sysdiff` grows.
- Keep tests fixture-backed and runnable without special privileges.
- Do not add runtime dependencies without explicit justification.
