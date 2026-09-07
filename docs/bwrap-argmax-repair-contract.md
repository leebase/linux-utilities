# Overview

This document defines the normative repair contract for resolving bubblewrap (`bwrap`) `ARG_MAX` and `MAX_ARG_STRLEN` (`E2BIG`) launch failures within the Agent-Orch sandboxed execution environment. The purpose of this slice is to establish a robust, fail-closed mechanism that prevents oversized worker payloads from crashing during process invocation, eliminates runaway prompt-expansion retry loops, and provides structured, value-free diagnostics when argument or environment limits are exceeded.

The required outputs of this slice are:
1. `docs/bwrap-argmax-repair-contract.md` (this repair contract, detailing the problem, constraints, validation, routing intent, and acceptance criteria).
2. `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` (synchronized user journey manifests adhering to the canonical schema and mapping required user journeys to all enumerated acceptance checks).
3. Dedicated regression testing and validation evidence ensuring bubblewrap sandbox containment and pre-exec payload measurement operate correctly without regression.

Routing intent: This repair strictly separates prompt transport from command-line arguments. By delivering mission prompts via standard input (`stdin_text`) rather than positional command-line arguments, individual string lengths remain well below kernel limits. When an oversized payload is detected prior to invocation, the orchestrator routes the failure to a typed `LAUNCH_PAYLOAD_TOO_LARGE` classification with actionable diagnostic metadata rather than letting `execve()` fail with an untyped operating system error. Validation retry loops are bounded to prevent compounding feedback growth.

# Problem

On Linux platforms, the kernel enforces strict limits on arguments passed to `execve()`:
1. `MAX_ARG_STRLEN` limits any single argument or environment string to 32 kernel pages (131,072 bytes on standard 4 KiB page architectures, accounting for the terminating NUL byte).
2. `ARG_MAX` (`_SC_ARG_MAX`) limits the total combined size of all argv strings, envp strings, and their respective pointer tables (typically 2 MiB on Linux).

Prior to this repair, sandboxed worker invocations constructed command lines for `/usr/bin/bwrap` where the full mission prompt was appended directly as a positional command-line argument. When prompt compositions or retry packets grew beyond 128 KiB (for instance, during multi-step runs with extensive context or retry feedback), `execve()` failed immediately with `OSError: [Errno 7] Argument list too long: '/usr/bin/bwrap'`.

This failure mode exhibited several critical deficiencies:
- **Untyped Worker Abortion:** The process failed before the worker started, surfacing only as an uninformative non-zero exit code or raw `OSError(E2BIG)`. This consumed an attempt without executing the task or generating structured run evidence.
- **Compounding Feedback Loops:** When a step failed with verbose console output (e.g., hundreds of kilobytes of compiler warnings or test backtraces), unbounded validator output was inserted into the run's `validation_errors`, which became retry feedback in the next attempt's mission packet. This caused successive attempts to grow monotonically until hitting `MAX_ARG_STRLEN` or `ARG_MAX`.
- **Diagnostic Information Leakage Risk:** Raw error logs reporting oversized arguments risked dumping sensitive prompt contents or environment credentials into untracked error streams.

The repair must address the root cause by removing prompts from `argv`, bounding validator console excerpts, measuring payloads prior to execution, and providing safe, value-free diagnostic reports.

# Constraints

1. **Prompt Off-Argv Transport:** Large mission prompts and structured worker instructions must never be passed as positional `argv` elements. Prompts must be streamed to the sandboxed worker process via standard input (`WorkerLaunch.stdin_text`) or dedicated descriptor channels.
2. **Pre-Exec Payload Measurement:** Before calling `execve()`, the orchestrator must measure the full composed launch payload (including all `bwrap` flags, mount arguments, and environment variables) against host kernel limits (`max_single_launch_entry_bytes()` and `max_total_launch_bytes()`).
3. **Fail-Closed Typed Refusal:** Any launch exceeding `MAX_ARG_STRLEN` or `ARG_MAX` must be refused immediately before process invocation. The refusal must emit a structured `LAUNCH_PAYLOAD_TOO_LARGE` failure record containing value-free byte accounting (argument counts, environment counts, byte totals, and largest argument sizes) without logging secret prompt text or environment values.
4. **Bounded Retry Feedback:** Process console output (stdout/stderr) captured in validation outcomes and retry feedback must be bounded to head and tail excerpts (e.g., `PROCESS_OUTPUT_EXCERPT_HEAD_BYTES = 4000` and `PROCESS_OUTPUT_EXCERPT_TAIL_BYTES = 4000`). Excerpts must state the exact number of elided bytes and explicitly reference the complete, hash-chained log artifact.
5. **Hardened Bubblewrap Sandbox Preservation:** All worker processes on Linux must remain sandboxed with bubblewrap (`bwrap`). Hardened filesystem isolation, read-only root mounts, and credential protection must not be weakened, bypassed, or disabled to accommodate oversized payloads.
6. **Non-Product Blast Radius:** This repair applies solely to orchestrator execution, validation, and journey manifests. It must introduce no changes, regressions, or dependencies to the `sysdiff` C17 utility source code (`src/sysdiff.c`), Makefile build rules, man pages, or existing test suites.

# Acceptance Checks

- **AC-1** — **Prompt Transport Off-Argv and Hardened Sandbox Containment:** The worker execution harness delivers mission prompts and large instruction payloads via standard input (`stdin_text`) rather than positional `argv` arguments, ensuring no individual command-line argument exceeds kernel `MAX_ARG_STRLEN` (131,072 bytes), while bubblewrap (`bwrap`) OS sandbox containment remains strictly enforced on Linux without granting unsandboxed execution bypasses.
- **AC-2** — **Pre-Exec Payload Measurement and Typed Refusal:** The orchestrator measures `argv` and `envp` byte sizes against host kernel limits (`max_single_launch_entry_bytes()` and `max_total_launch_bytes()`) before calling `execve()`. Payloads exceeding limits are refused fail-closed prior to process execution with a typed `LAUNCH_PAYLOAD_TOO_LARGE` classification and value-free byte accounting in `failure_evidence`.
- **AC-3** — **Bounded Validation Output, Test Integrity, and Non-Product Blast Radius:** Validation errors and retry feedback bound process output to fixed head and tail excerpts with elision markers and pointers to hash-chained log artifacts, breaking compounding prompt expansion loops. The repair maintains full test suite integrity, covers canonical user journey schemas, and introduces zero regressions or modifications to `sysdiff` C17 source code, build targets, or CLI contracts.
