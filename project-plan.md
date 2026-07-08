# Project Plan

## Current direction

- Keep the utility suite small and auditable.
- Build `sysdiff` first, starting with deterministic fixture comparison before
  any broad system probing.
- Use auto-orch for ongoing discovery and Agent-Orch for governed delivery
  slices with smoke and review-verdict gates.
- Prefer standard C and POSIX-adjacent shell test harnesses unless a stronger
  need is proven.
