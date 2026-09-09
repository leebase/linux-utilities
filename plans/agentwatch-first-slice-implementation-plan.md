# agentwatch First-Slice Implementation Plan

This plan implements `docs/agentwatch-first-slice-contract.md` as a Linux-only,
single-command supervisor. Work is test-first: land the deterministic harness
and failing contract cases before adding production behavior, then make each
acceptance group pass without widening the interface or the process-management
policy. The intended product is `build/agentwatch`; it has no runtime dependency
beyond libc and Linux/POSIX interfaces and produces no normal operational
output.

# Architecture

Add `src/agentwatch.c` as one auditable C17 translation unit and give it a
dedicated `AGENTWATCH_PLATFORM_CFLAGS := -D_GNU_SOURCE` in the Makefile so every
compile, analyzer, sanitizer, and Valgrind route sees the libc declarations for
`prctl`, `pipe2`, and related Linux interfaces even when callers replace
`CFLAGS`. Keep parsing, platform calls, procfs observation, lifecycle control,
diagnostics, and final status selection as small functions rather than creating
a general process-management library.

The top-level flow is an explicit state machine: parse options; install the
self-pipe and handlers; enable `PR_SET_CHILD_SUBREAPER`; create a close-on-exec
exec-error pipe; fork; establish the direct child's process group; complete the
exec handshake; observe/reap; enter TERM cleanup on timeout, interruption, or
internal failure; enter KILL cleanup after the grace deadline; perform the final
two-second reap; and select the result by precedence. Record independent facts
(`first_interrupt`, `timed_out`, `start_failed`, `internal_failure`, direct-child
wait status, and cleanup completeness) rather than overwriting one status code.
One pure final-status function applies: interruption, command-start failure,
timeout, internal/cleanup failure, then the direct command result. This also
preserves ordinary child exits 124/125 and never emits reserved status 126.

Argument parsing uses a strict decimal parser that accepts only unsigned
base-10 values in `0.001..86400.000`, rejects signs, exponent notation,
whitespace, suffixes, NaN/infinity, excess precision that changes the defined
millisecond value, overflow, repeated options, missing values, missing `--`, and
an empty command. Convert once to integer milliseconds with checked arithmetic;
all absolute deadlines use `clock_gettime(CLOCK_MONOTONIC)`. `argv` and command
strings remain borrowed and are passed unchanged to `execvp`; no shell or
command reconstruction exists.

Signal handlers perform only async-signal-safe actions: the first INT, TERM, or
HUP number is stored in `volatile sig_atomic_t`, and a byte is best-effort
written to a nonblocking self-pipe; SIGCHLD only writes a wake byte. Block the
handled signals while installing handlers and across each observe-to-`ppoll`
transition, then use an atomic mask handoff so a wake cannot be lost. Ignore
SIGPIPE so pipe/output failures become checked errors. In the child, restore an
appropriate signal mask/dispositions, call `setpgid(0, 0)`, close unused file
descriptors, and call `execvp`; on failure write the captured fixed-width errno
to the CLOEXEC handshake pipe and `_exit(127)`. The parent also calls
`setpgid(child, child)` to close the parent/child race and treats only documented
benign results as success.

Model `/proc` behind narrow functions (`scan_proc`, `read_identity`, and
`revalidate_identity`) whose production backend uses `/proc` but whose test
backend consumes scripted records and errors. Parse numeric directory names
strictly, stop after 65,536 entries, retain at most 4,096 unique identities, and
rate-limit scan starts to one per 50 milliseconds. Read `/proc/PID/stat` into a
4,097-byte sentinel buffer, require EOF by 4,096 bytes, locate the final `)` of
the parenthesized `comm`, and strictly parse field 4 (`ppid`) and field 22
(`starttime`) with range checks and complete-record validation. Retain
`struct ProcessIdentity { pid_t pid; uint64_t starttime; pid_t observed_ppid; }`
in a fixed-capacity owned array; establish membership only by repeatedly linking
an observed identity to the root identity or another already-connected observed
identity. Never infer ancestry from a bare PID.

The direct child owns exactly one process group, and only its positive PGID may
be used with `kill(-pgid, signal)`; explicitly reject zero, one, the supervisor
PID/group, and all unrelated values. Individual delivery takes an immutable
snapshot of connected identities, excludes the supervisor and duplicates,
rereads each target's starttime immediately before `kill`, and signals only an
exact `(pid,starttime)` match. `ENOENT`/mid-read disappearance and `ESRCH` are
benign gone races; malformed, oversized, inaccessible, or inconsistent records
are untrusted and cannot authorize individual delivery. Observation uncertainty
is remembered and becomes status 125 only when cleanup completeness cannot be
proved; owned-group cleanup remains available.

After every wake and before every possible return, call a drain routine that
loops `waitpid(-1, &status, WNOHANG)`, retries EINTR, records the direct child's
status exactly once, accounts for adopted children, and continues until zero or
ECHILD as appropriate. Normal completion requires the direct child to be known
terminated and a terminal ECHILD observation. Cleanup always remains bounded:
TERM observation lasts through the configured grace deadline, KILL is delivered
to revalidated survivors, and final observation/reaping stops after two more
monotonic seconds with `CLEANUP_INCOMPLETE` rather than hanging.

Use one initialized `Supervisor` owner for all mutable resources: both ends of
the wake pipe, both exec-pipe ends until ownership transfers/closes, the direct
PID/PGID, the fixed identity table, deadlines, result facts, and diagnostic
state. File descriptors use `-1` as the closed sentinel and one idempotent
cleanup function closes each at most once. The child closes parent-owned ends
before exec. No process record owns strings or file descriptors, no procfs data
escapes its scan buffer, and no allocation is needed for the bounded table. If a
small test/backend allocation is retained, it has one owner and every failure
converges on the same best-effort TERM/KILL/reap path. Diagnostics name only the
closed taxonomy and escape untrusted command/procfs bytes as printable ASCII
with uppercase `\\xHH` escapes.

# Tests

Write `tests/test_agentwatch.py` before production implementation. Like existing
utility tests, it builds into pytest-owned `/tmp` directories, seals locale and
environment where relevant, applies hard per-test timeouts, and fails rather
than skips when required source is absent. Build a normal integration binary and
a test-seam binary enabled by `AGENTWATCH_TEST_SEAM`; the seam redirects only
platform boundaries (clock, procfs directory/stat reads, prctl, pipe/fork/exec
handshake, setpgid, ppoll, kill, waitpid, allocation if present, and checked
stdio), while production policy and state transitions remain the same. Each
injector needs a positive-control assertion proving that the intended call was
reached, so a passing error test cannot result from dead code.

Implement tests in this order:

1. Pin exact help/version bytes, silent successful operation, grammar and every
   numeric boundary/invalid class. Prove a missing executable returns 127 with
   `COMMAND_START_FAILURE`, while a real helper that exits 127 returns 127
   without that wrapper failure. Add exit/signal helpers compiled under `/tmp`.
2. Add real Linux lifecycle fixtures: ordinary exits 0, 2, 123, 124, 125, and
   127; direct signal deaths; a child plus grandchild; a double-forked child that
   leaves the original process group; and an original child that exits before
   its adopted descendant. Use pipes for synchronization, inspect waitable
   state deterministically, and assert agentwatch does not return until all
   descendants are reaped. Avoid timing-only sleeps as readiness signals.
3. Add timeout/interruption fixtures synchronized by readiness pipes. Assert
   monotonic timeout 124; INT/TERM/HUP results `128+N`; TERM is observed before
   KILL; cooperative children exit during grace; resistant group members and
   separately tracked descendants are killed; and precedence holds when
   interruption, timeout, injected internal failure, start failure, and child
   exit facts coincide.
4. Add scripted procfs unit scenarios for exact and tricky `stat` parsing
   (spaces and `)` in `comm`), disappearance at each read stage, malformed and
   truncated records, 4,096/4,097-byte boundaries, EACCES, inconsistent parent
   identity, 65,536/65,537 directory entries, 4,096/4,097 identities, duplicate
   PIDs, and scan throttling at 49/50 milliseconds. Assert bounded call counts,
   never merely elapsed wall time.
5. Add PID-reuse and signaling traces: unchanged starttime permits one
   individual signal; changed/missing/untrusted identity permits none; a parent
   link without a complete observed identity chain permits none; duplicate
   group/individual targets are suppressed; and group sends contain exactly
   `-direct_child_pgid`, never `-1`, the supervisor group, or another group.
6. Build a table-driven fault matrix covering every closed diagnostic:
   `INVALID_ARGUMENTS`, `SUBREAPER_SETUP_FAILURE`, `SIGNAL_SETUP_FAILURE`,
   `COMMAND_START_FAILURE`, `TIMEOUT`, `INTERRUPTED`, `PROCFS_DISAPPEARED`,
   `PROCFS_UNTRUSTED`, `TRACKING_LIMIT`, `PID_IDENTITY_CHANGED`,
   `SIGNAL_DELIVERY_FAILURE`, `REAP_FAILURE`, `CLEANUP_INCOMPLETE`, and
   `INTERNAL_FAILURE`. Inject every specified platform failure class, assert
   cleanup attempts and bounded call counts, exact precedence/status, silence
   for benign races or ultimately complete uncertainty, and escaped diagnostics
   for control bytes, quotes, backslashes, and non-ASCII bytes.
7. Add source/build/documentation audits that forbid `kill(-1,...)`, shell
   insertion, daemonization, cgroups, namespaces, networking, persistence,
   privilege changes, log capture, background continuation, and unbounded
   procfs loops. These checks support review but do not replace runtime tests.

Acceptance mapping:

- **AC-1:** parser/CLI byte tests, numeric boundary table, exec-error handshake
  integration, and real-child-exit-127 regression; implement strict parsing,
  help/version dispatch, CLOEXEC pipe, `fork`, and `execvp` separation.
- **AC-2:** real child/grandchild/double-fork fixtures and waitpid trace tests;
  implement pre-fork subreaper setup, owned process group, persistent
  supervision, and drain-through-ECHILD completion.
- **AC-3:** synchronized timeout and three-interruption suites plus precedence
  and TERM-to-KILL traces; implement monotonic deadlines, self-pipe wakeups,
  identity revalidation, grace observation, escalation, and result arbitration.
- **AC-4:** scripted procfs boundary/error/throttle suites with exact operation
  counts; implement capped scanning, size-sentinel reads, strict stat parsing,
  uncertainty classification, and the 50-millisecond scan gate.
- **AC-5:** identity-change, incomplete-chain, duplicate-target, and negative
  PGID trace tests; implement `(pid,starttime)` retention, observed-chain
  closure, immediate reread, and direct-child-group-only signaling.
- **AC-6:** the positive-controlled full taxonomy/fault matrix, diagnostic byte
  checks, cleanup-ceiling virtual-clock cases, and status-precedence matrix;
  implement one cleanup convergence path and exhaustive taxonomy mapping.
- **AC-7:** non-goal audits plus strict compilers, formatting, analyzers,
  sanitizer, Valgrind, unit/integration/regression/fixture/timeout/interruption/
  hostile-procfs/zombie gates; integrate agentwatch into every applicable
  Makefile and documented quality route without adding install/release scope.

# Verification

Verification must be deterministic and layered. During test-first development,
run the focused pytest module after each acceptance group, using its virtual
clock and scripted syscall/procfs traces for races and ceilings; real-process
tests synchronize through pipes and enforce an outer timeout only as a hang
guard. Assert exact stdout/stderr bytes, exit statuses, call order, target PIDs,
signal numbers, waitpid terminal conditions, descriptor closure, and maximum
operation counts. Do not treat probabilistic PID reuse, arbitrary sleeps, or
host process-table contents as proof.

Extend the Makefile with an `agentwatch` target and agentwatch membership in
`ALL_SRCS`, `test-suite`, GCC/Clang strict builds, syntax, clang-format,
clang-tidy, cppcheck, Clang analyzer, ASan, UBSan, and clean GCC Valgrind routes.
Keep all temporary/instrumented binaries under `mktemp` directories; only the
ordinary target writes `build/agentwatch`. The implementation slice should run,
and report verbatim outcomes for, at minimum:

```sh
python3 -m pytest -p no:cacheprovider tests/test_agentwatch.py
make agentwatch
make gcc-strict
make clang-strict
make format-check
make clang-tidy-check
make cppcheck-check
make clang-analyzer-check
make test-suite
make test-sanitize
make test-valgrind
make quality
```

Also run an explicit zombie regression around the real double-fork fixture and
an outer bounded-time check around timeout/interruption cleanup. Review the
test-seam build to ensure it changes platform inputs only, not policy. A clean
quality run is release-quality evidence only after each named route actually
includes agentwatch; tool absence is a failure or explicitly reported missing
capability, never silently converted to a pass.

Documentation changes in the implementation slice are `architecture.md` for
the subreaper/procfs/state-machine decision, `README.md` and
`docs/agentwatch.md` for the exact CLI/status/taxonomy/non-goal user contract,
`man/agentwatch.1` for the installed-style reference (without adding an install
target), `TESTING.md` and `QUALITY.md` for gate membership and Linux fixture
requirements, and `CHANGELOG.md`/decision records if required by repository
convention. Update distribution or release inventories only when product scope
explicitly authorizes shipping agentwatch; otherwise verify they remain
unchanged. Update AgentFlow state files only in the later governed slice whose
write scope permits those files.

# Risks

The largest correctness risk is signaling an unrelated reused PID. Mitigate it
with retained starttime identities, complete observed ancestry chains,
immediate pre-signal rereads, strict parse/range validation, and tests that prove
the kill seam is untouched on any mismatch or uncertainty. Group signaling has
a broader kernel effect than individual signaling, so preserve the exact PGID
created for the direct child, validate it before every send, and test all
forbidden negative-target cases.

Signal delivery, waitpid, exec handshaking, and sleep transitions contain races
that ordinary integration tests rarely reproduce. The self-pipe plus atomic
mask handoff prevents lost wakeups; state facts make precedence independent of
event arrival order; deterministic scripted traces enumerate interleavings.
Handlers must never call allocation, stdio, clock, wait, or procfs code. The
child-side post-fork path must remain async-signal-safe up to `execvp` apart from
the specifically required calls and fixed errno write.

Procfs is hostile, mutable text. Parenthesized command names, partial reads,
oversized records, permission changes, PID disappearance/reuse, scan churn, and
identity-table exhaustion can otherwise cause unsafe ancestry conclusions or
unbounded work. Sentinel buffers, strict numeric parsing, per-scan caps,
monotonic throttling, closed uncertainty states, and operation-count assertions
bound the damage. The plan deliberately does not promise control of a process
that escapes both the owned group and observable/reapable ancestry; when that
uncertainty prevents proof of cleanup, return 125.

Cleanup itself can hang if deadlines are recomputed incorrectly or ECHILD is
never reached. Store absolute saturating monotonic deadlines, recalculate poll
durations from them, continue nonblocking reaping on every wake, and impose the
contract's final two-second ceiling. Faults during fault cleanup must not restart
grace or erase the primary cause. Status collisions (a child legitimately exits
124/125/127) are mitigated by separate event facts and taxonomy diagnostics.

Finally, test seams can accidentally become alternate implementations and broad
Makefile edits can regress mature utilities. Keep seams at platform-call
boundaries, compile production without seam code, review both preprocessed
surfaces, add agentwatch to existing gates incrementally, and run the full suite.
Do not add daemon, PID-1, restart, cgroup, namespace, resource-control,
networking, logging, persistence, packaging, installation, or multi-command
behavior under the guise of making tests easier.
