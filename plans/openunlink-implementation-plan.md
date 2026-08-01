# `openunlink` Initial Vertical-Slice Implementation Plan

Contract authority: `docs/sixth-utility-capability-contract.md`.

This plan delivers only the contract's sixth-utility bootstrap: inspect one
explicit Linux PID and report retained descriptors whose followed targets are
observed as stable regular files with final `st_nlink == 0`. The contract
controls every byte, predicate, limit, status, taxonomy entry, ownership rule,
and non-goal. Any desired behavioral change returns to FRAME as an explicit
contract revision before tests or code adopt it.

The implementation artifacts are `src/openunlink.c`,
`tests/test_openunlink.py`, additive non-writing Makefile integration,
`man/openunlink.1`, `docs/openunlink.md`, and matching updates to `README.md`,
`CHANGELOG.md`, `QUALITY.md`, `TESTING.md`, and `architecture.md`. Dedicated
TEST AS USER evidence and independent review evidence belong to their governed
run steps. This slice does not add installation, uninstallation, packaging,
distribution, publication, tagging, or release behavior.

## Architecture

### Product shape and compile contract

Implement the product as exactly one small ISO C17 translation unit,
`src/openunlink.c`, linked only with libc. Put guarded
`_POSIX_C_SOURCE=200809L` and `_FILE_OFFSET_BITS=64` definitions before all
headers, and also pass both definitions through a dedicated, non-droppable
`OPENUNLINK_PLATFORM_CFLAGS` Make variable and through every pytest compile
route. Obtain `open`, `dup`, `fdopendir`, `readdir`, `closedir`, `fstatat`,
`readlinkat`, `close`, signal, allocation, and stdio declarations only from
platform headers. Add compile-time assertions for Linux's required
`CHAR_BIT == 8`, at least 64-bit `off_t`, and a `uintmax_t` capable of
representing every nonnegative supported `off_t`; render the checked size with
`PRIuMAX`.

Keep the CLI closed to sole-argument `--help`, sole-argument `--version`, and
one canonical ASCII-decimal PID in `1..INT_MAX`. Parse bytes directly without
locale-sensitive character predicates, signs, whitespace, prefixes, suffixes,
leading zeroes, or implicit PID selection. Derive the fixed `/proc/PID/fd`
capacity from the literal fragments and `INT_DECIMAL_BOUND == 3 * sizeof(int)`,
check every `size_t` addition, and never accept a proc root, path, environment
setting, configuration value, or stdin input.

### Scan pipeline and deterministic precedence

Use one explicit scan state and one cleanup path with the following operation
order:

1. Validate the command, install ignored `SIGPIPE` handling, format the fixed
   process-directory path, and open it with
   `O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW`. Map only `ENOENT`/`ENOTDIR` to
   `PROCESS_NOT_FOUND`, only `EACCES`/`EPERM` to `PROCESS_ACCESS`, and every
   other failure here to `PROCESS_SCAN`.
2. Duplicate the original directory descriptor, pass the duplicate to
   `fdopendir`, and transfer ownership to `DIR *` only on success. Allocate,
   with checked multiplication/addition, exactly one 65,536-element descriptor
   array, one 65,537-byte link-text sentinel buffer, and one reusable
   worst-case finding-line buffer. Allocation failure is `MEMORY`; no scan
   result is emitted before all three allocations succeed.
3. Set `errno = 0` before every `readdir`. Ignore only `.` and `..`; reject
   malformed, noncanonical, out-of-range, or retained-duplicate descriptor
   names as `PROCESS_SCAN`. Store the first 65,536 valid names in observed
   order. The 65,537th valid name stops enumeration immediately, records one
   `FD_COUNT_LIMIT`, and leaves later names unobserved. Sort only the retained
   numeric values and detect retained duplicates before inspection.
4. Close the `DIR *` before descriptor inspection. A `readdir` or `closedir`
   failure is `PROCESS_SCAN` and precedes descriptor output. If the cap was
   reached, attempt its one advisory before inspecting the retained set.
5. Inspect retained descriptor numbers in ascending numeric order. Reformat
   each number canonically, call followed `fstatat(..., 0)`, bounded
   `readlinkat`, and a second followed `fstatat(..., 0)` in the contract's
   exact first-applicable classification order. Stable findings remain
   reportable even when other retained descriptors produce advisories.
6. Flush stdout after the complete descriptor loop. A finding/help/version
   write or final flush failure selects `STDOUT_WRITE`. Only after a successful
   flush close the original inspection descriptor; its first failure selects
   `PROCESS_SCAN`. Cleanup still frees all owned buffers, but no cleanup
   failure replaces an earlier operational code.

The original process-directory descriptor has one owner and one close. Before
successful `fdopendir`, the duplicate is scanner-owned; afterward `DIR *`
exclusively owns it even when `closedir` reports failure. Each allocation has
one owner and one cleanup site. `argv`, its strings, and each `dirent` name are
borrowed; no `dirent` pointer survives the next directory operation. There is
no result list, target descriptor, inode table, per-descriptor allocation,
`realloc`, or capacity growth.

### Descriptor classifier and output

Centralize errno classification so the first or second `fstatat` maps only
`ENOENT`, `ENOTDIR`, and `ESTALE` to `FD_UNSTABLE`; all other errors map to
`FD_UNREADABLE`. A non-regular first target is silent and bypasses
`readlinkat` and the second metadata call. For a regular first target,
`readlinkat` additionally maps only `EINVAL` to `FD_UNSTABLE`. A return of
65,537 bytes is immediately `TARGET_LENGTH_LIMIT`; a return of at most 65,536
bytes is length-authoritative even when it contains NUL.

After bounded link text, require the second observation to match the first
`st_dev`, `st_ino`, and regular-file type. A mismatch is `FD_UNSTABLE`.
Stable final `st_nlink != 0` is silent regardless of a literal
` (deleted)` suffix. Stable final `st_nlink == 0` proceeds through a checked,
lossless nonnegative `off_t` to `uintmax_t` conversion; negative or
unrepresentable values are `FD_SIZE_RANGE`, and all other cases are the sole
finding `OPEN_UNLINKED`.

Build the reusable line capacity mechanically from the contract literal
pieces, two `INT_DECIMAL_BOUND` fields, one `UINTMAX_DECIMAL_BOUND` field,
four output bytes per possible target byte, and one NUL. Escape by unsigned
byte value: literal printable ASCII except `"` and `\`, those two as `\"` and
`\\`, and every other byte as uppercase `\xNN`. Findings are complete stdout
lines in ascending retained-FD order. Count advisory first and descriptor
advisories in ascending retained-FD order go to best-effort stderr. Do not
promise cross-stream ordering.

Use one final status reducer. Help/version succeed with `0`. A completed scan
with neither finding nor advisory returns `0`. A completed scan with any
finding or advisory returns `1`; byte-nonempty stdout means at least one
complete finding, while byte-empty stdout means advisory-only. Any operational
code returns `2` and has precedence. Attempt at most one operational
diagnostic, and never invent `STDERR_WRITE`.

### Test-only seam without production state

`tests/test_openunlink.py` will contain a small embedded C seam helper and a
versioned, length-prefixed binary scenario encoder. Pytest writes the helper,
header, scenario, trace, and all binaries only beneath its temporary tree.
The seam build compiles `src/openunlink.c` with a test-only macro/header and
links the generated helper; production and ordinary strict builds omit that
macro, helper, scenario parser, injected state, and all control environment
variables.

The generated header routes only the declared boundary calls to type-correct
test functions. The helper deterministically models process-directory
`open`, `dup`, `fdopendir`, arbitrary ordered `readdir` entries, `closedir`,
both `fstatat` observations, arbitrary-length and arbitrary-byte `readlinkat`,
final `close`, the three source allocations, stdout writes/flush, and
best-effort stderr writes. It also supplies the test-only reachability hook
needed to force the otherwise defensive nonnegative-but-unrepresentable size
branch. The helper uses real libc internally without those source-local
remappings, so loading scenario data does not consume product allocation or
call counters.

Every modeled call records arguments, order, count, errno/result, resource
ownership, and close/free state to the trace. Failure tests assert that the
intended call was reached, and each injector has a paired successful positive
control. This prevents a test from passing merely because a defective product
bypassed the injected operation. The 65,536/65,537-entry scenarios are
generated algorithmically from the binary script rather than materialized as
65,537 Python subprocesses or host procfs entries.

### Additive Make and documentation integration

Add `OPENUNLINK_SRC`, `OPENUNLINK_MANPAGE`, and
`OPENUNLINK_PLATFORM_CFLAGS`; append them to `ALL_SRCS` and `ALL_MANPAGES`.
Add phony `openunlink`, `openunlink-test`, `openunlink-sanitize`, and
`openunlink-valgrind` targets. Each creates a named directory under `/tmp`,
installs an EXIT/HUP/INT/TERM cleanup trap, compiles or tests there, and leaves
no `build/openunlink`, top-level `openunlink`, cache, trace, or fixture in the
workspace. Default `all`, `sysdiff`, `install`, `uninstall`, release, and
distribution behavior remain sysdiff-owned and unchanged.

`openunlink-test` runs the complete focused module with cache and bytecode
writes disabled. `openunlink-sanitize` builds a strict Clang ASan+UBSan
production binary and tells the pytest seam builder to use the same
instrumentation before running the complete module. `openunlink-valgrind`
builds a separate strict GCC debug binary, enables full leak/error checking
with a nonzero error exit, all leak kinds, and `--track-fds=yes` descriptor
reporting through the pytest runner, and also runs the complete module.
Neither focused memory target may substitute a `--help` probe for the contract
suite.

Extend `gcc-strict`, `clang-strict`, `clang-syntax`, `format-check`,
`clang-tidy-check`, `cppcheck-check`, and `clang-analyzer-check` to include
`src/openunlink.c` with both platform feature flags where applicable. Extend
aggregate `test-asan`, `test-ubsan`, and `test-valgrind` to compile
`openunlink` beside the existing three binaries, set an absolute
`OPENUNLINK_BIN`, select matching seam instrumentation, and run the full
portfolio. Extend ordinary `test-suite` to scrub ambient `OPENUNLINK_BIN`,
`OPENUNLINK_UNDER_VALGRIND`, and seam-build controls so a stale override
cannot bypass the source-owned suite.

Write `man/openunlink.1` and `docs/openunlink.md` from the contract, then make
README, CHANGELOG, QUALITY, TESTING, and architecture summaries agree. The
manual must state exact synopsis and bytes, the closed finding/advisory/error
taxonomies, per-stream ordering, all resource bounds, statuses and the
status-1 stdout discriminator, read-only ownership-neutral behavior,
Linux/procfs/namespace/`hidepid` assumptions, point-in-time races, target-text
privacy exposure, and every non-goal. User docs must say that status 0 is only
a narrow `st_nlink == 0` observation and that NFS silly-rename can retain a
nonzero link count.

## Tests

### Pytest-owned real fixture

Follow the established pathaudit/permguard pattern: a session fixture either
resolves an absolute `OPENUNLINK_BIN` supplied by a memory gate or compiles
`src/openunlink.c` with strict C17 and both platform feature flags into a
pytest-owned temporary directory. Child environments are sealed to
`LC_ALL=C`/`LANG=C`, forward only declared sanitizer controls, and never use
ambient PATH or configuration to change product behavior. Relative overrides,
missing sources, non-executable overrides, stale override poisoning, and
Valgrind-unavailable routing fail closed.

A context-managed same-UID Python child creates requested objects in a private
temporary directory, reports its PID and exact descriptor numbers only after
all objects are held, and then waits for explicit snapshot/release commands.
Its modes cover a still-linked regular file, one open-then-unlinked regular
file, two duplicated descriptors for that unlinked object, a linked filename
literally ending in ` (deleted)`, and pipe/socket descriptors. The parent
reads one bounded handshake record, performs scans while the child is frozen,
requests before/after `fstat` and content-hash evidence, confirms the child
survived and received no product control action, and always releases/reaps it
through fixture cleanup.

Real-procfs tests compare full stdout, stderr, and numeric status bytes. They
cover linked-only `0`, one exact `OPEN_UNLINKED` line, separate ordered lines
for duplicates, silent non-regular targets, literal-suffix false-positive
resistance, byte-identical repeat scans, and unchanged metadata/content.
Required Linux procfs visibility is a gate prerequisite: absent or restricted
procfs for the same-UID helper fails the required focused/quality gate with
the observed contract diagnostic; it is not converted into release-quality
success by an unconditional skip.

### Deterministic seam and byte oracles

The scenario runner emits arbitrary canonical and malformed directory names,
duplicate names, exact errno values, two metadata snapshots, link payloads
including embedded NUL/non-UTF-8 bytes, allocation results, stdio failures,
and cleanup failures. Its trace assertions pin the first-applicable operation
and prove bypass-sensitive positive controls. Test families will cover:

- all three CLI forms, rejected PID grammar/range/arity/options, exact help,
  version, usage, finding, advisory, and operational diagnostic bytes;
- first-observed subset retention, numeric sort, exactly 65,536 valid entries
  without a count advisory, and a 65,537th valid entry with one retained
  finding, one count advisory, and no later inspection;
- first/second metadata churn, descriptor reuse, all closed errno mappings,
  non-regular early exit, nonzero links, negative and forced-unrepresentable
  size, and mixed stable findings with per-descriptor advisories;
- exact 65,536-byte link acceptance, exact 65,537-byte length advisory, and
  exhaustive escaping for space, quote, backslash, tab, LF, CR, NUL, controls,
  DEL, and every `0x80..0xff` byte with checked maximum line capacity;
- process open errors, duplication/`fdopendir`/`readdir`/`closedir` errors,
  malformed/out-of-range/duplicate entries, all three allocation failures,
  stdout writes/flush, stderr loss, and final original-descriptor close;
- compound failures that pin first-operational-error precedence, one
  operational diagnostic at most, cleanup non-replacement, flushed findings
  surviving a final close failure, and possible partial stdout only for
  `STDOUT_WRITE`;
- ownership counters proving exactly three scan allocations, no `realloc` or
  descriptor-loop allocation, successful `DIR *` transfer, and no leak,
  double free, descriptor leak, or double close on any partial path;
- a shell-style status-1 caller that branches on both status and stdout byte
  length, distinguishing finding-bearing and advisory-only results.

Static source tests require the feature-test definitions before headers,
platform headers and `PRIuMAX`, unsigned-byte escaping, the fixed procfs path,
and the intended system-call surface. They reject hand-written system
prototypes, target-content `open`/`read`, fork/exec, PATH search, socket/network
calls, `kill` or process-control calls, target `unlink`/`rename`/`chmod`/`chown`,
grouping/deduplication of findings, and invented taxonomy tokens. Runtime seam
traces independently prove only fixed `/proc/PID/fd` is opened and no target
content or control operation occurs.

Documentation and Makefile tests parse the relevant target blocks and
maintainer documents. They require all four openunlink focused targets to be
phony and non-writing, feature flags on every compile/analyzer route,
openunlink in all source/manual/strict/analyzer/memory lists, override
scrubbing in ordinary `test-suite`, full focused pytest invocation in both
memory targets, groff warning-gating, and preservation of existing sysdiff,
pathaudit, and permguard target wiring. They also require the exact status-0
NFS silly-rename disclaimer in the manual, README-facing documentation, and
`docs/openunlink.md`.

### Acceptance-check mapping

The identifiers below name every paragraph or bullet in the contract's
**Acceptance Checks** section so review can trace each requirement without
assuming that a focused pass implies portfolio completion.

| ID | Contract acceptance check | Implementation item | Verification item |
| --- | --- | --- | --- |
| OU-AC-01 | Test-only control of directory open/duplication, `fdopendir`/`readdir`/`closedir`, both metadata calls, `readlinkat`, final close, allocation, stdout/flush, stderr, arbitrary ordered names/bytes, and a positive control for every injector | Test-only generated seam and length-prefixed scenario/trace protocol; production macro path absent | Seam trace tests assert call reachability, argument/order/counter state, paired success, and injected failure bytes/status |
| OU-AC-02 | Handshake-controlled same-UID fixture with linked, unlinked, duplicated, literal-suffix, pipe, and socket resources; synthetic cases stay in the seam | Context-managed helper reports PID/FDs only when frozen and waits for explicit release | Real-procfs fixture tests plus cleanup/survival and before/after metadata/hash assertions |
| OU-AC-03 | Exact CLI and stream bytes; reject PID zero, leading zero, signs, whitespace, empty/overflow, missing/extra operands, unknown/combined options | Closed parser, exact constants, best-effort usage diagnostic, checked informational stdout | Parameterized byte-oriented CLI suite asserts statuses `0`/`2`, exact stdout/stderr, and closed stdout behavior |
| OU-AC-04 | Linked-only silence, one unlinked finding, duplicate descriptor lines, silent non-regular targets, numeric order, repeatability | Repeated followed metadata classifier and ascending retained-FD loop; never group by inode | Frozen real fixture runs compare exact lines and repeat byte-for-byte |
| OU-AC-05 | Literal ` (deleted)` with nonzero links and simulated NFS silly-rename remain silent; user docs state the narrow status-0 boundary (`SIXTH2-M2`) | Finding predicate uses final stable `st_nlink == 0` only | Real suffix fixture, seam nonzero-link case, and documentation oracle across manual/README/docs |
| OU-AC-06 | 65,536 entries pass without count advisory; 65,537 preserves retained finding, emits exactly one advisory, omits later entries, uses first-observed subset, then numeric order (`SIXTH2-M1`) | Fixed array, observed-order retention, immediate boundary stop, post-retention numeric sort | Algorithmic seam scenarios include retained and excluded sentinels and assert exact streams/status `1` |
| OU-AC-07 | Disappearance, stale identity/reuse, unreadability, size range, and long target map exactly; advisory-only stdout is empty and mixed findings survive; shell caller distinguishes status-1 classes (`SIXTH2-M3`) | Closed first-applicable classifier and final status reducer | One case per errno/identity/range branch, mixed cases, and a status-plus-stdout-length caller oracle |
| OU-AC-08 | Accept 65,536 link bytes, reject a full 65,537 return, escape all hostile bytes uppercase and terminal-safe, and prove capacity arithmetic | Sentinel buffer, length-authoritative escaping, mechanically derived reusable line buffer | Boundary payloads and exhaustive byte corpus assert exact output and maximum-capacity completion |
| OU-AC-09 | Map process open errors, bad entries, duplicates, directory failures, allocation failure, final close, and compound precedence to exact status-2 diagnostics | Central operational-code reducer, captured errno, one diagnostic, cleanup non-replacement, flush-before-final-close | Failure matrix asserts empty pre-output stdout, preserved flushed findings on final close, one diagnostic, and trace order |
| OU-AC-10 | Fail each of three allocations, perform no `realloc`/loop allocation, and cover duplicate/`fdopendir`/`closedir`/final-close ownership without leak or double close | Three fixed allocations and explicit descriptor/`DIR *` ownership transfer | Allocation/resource counters, ASan+UBSan, and Valgrind run every focused ownership scenario |
| OU-AC-11 | Closed stdout/help/version/finding/final flush becomes `STDOUT_WRITE`, never SIGPIPE; stderr failure changes no selected status and invents no code | Ignore SIGPIPE, check every stdout operation, keep stderr best-effort | Real closed-pipe plus seam write/flush/stderr failures assert exact status/bytes and no signal-derived result |
| OU-AC-12 | Product opens only fixed `/proc/PID/fd`, never target content, subprocesses, network, mutations, process control, or remediation; fixtures remain unchanged | Single fixed-path open call and directory-relative metadata/link inspection only | Source call-surface audit, seam argument trace, helper survival, and before/after metadata/content hashes |
| OU-AC-13 | Platform headers under both feature macros, at least 64-bit `off_t`, eight-bit bytes, lossless size conversion/`PRIuMAX`, no hand prototypes or signed-byte classification; Linux/procfs errors do not silently pass | Dedicated platform flags, compile-time assertions, checked conversion, unsigned escape loop | Strict pytest compile oracles, source audits, negative/forced-range seam, and observed procfs error mapping |
| OU-AC-14 | GCC/Clang strict C17, format, tidy, cppcheck, analyzer, all test layers, ASan, UBSan, and Valgrind pass with positive-control seams | Add source to every quality list and instrument production plus seam builds | Focused targets and final clean `make quality`; required tool absence is failure, and executed test counts/skips are recorded |
| OU-AC-15 | Additive non-installing Make targets; focused ordinary, ASan+UBSan, and Valgrind routes run all of `tests/test_openunlink.py`; clean full quality includes prior portfolio | Four non-writing targets, aggregate route wiring, ordinary override scrubbing, unchanged install/release surface | Makefile structure/dry-run tests, all focused targets, then clean complete quality and aggregate smoke |
| OU-AC-16 | Warning-free section-1 manual and matching README, CHANGELOG, openunlink guide, QUALITY, TESTING, and architecture; all required semantics and `SIXTH2-M2` disclaimer | Contract-derived manual and documentation updates only | `make man-check`, document token/section oracles, review for exact bytes/taxonomy/bounds/privacy/non-goals |
| OU-AC-17 | Dedicated standalone TEST AS USER linked/unlinked flow and independent review of contract, ownership, bounds, taxonomy, non-control posture, filesystem honesty, with no unresolved Medium+ mission finding | Governed smoke builds under temporary storage; review receives source, tests, docs, quality and smoke evidence | Smoke result records start/core true and empty blockers; independent verdict must pass or return to FIX and rerun all affected gates |

## Verification

Verification is evidence-producing work, not a substitute for implementation
or review. Record each exact command, exit code, executed test count, honest
skip count/reason, tool version when relevant, and temporary evidence path.
Never describe collection, a skipped capability, a byte-compilation check, a
focused `--help` probe, or an unrun command as a passing product gate.

### Focused red-to-green sequence

1. Author `tests/test_openunlink.py` and its real/seam fixtures before accepting
   CODE. Confirm its production and seam compile fixtures fail closed while
   `src/openunlink.c` is absent or behavior is incomplete.
2. Implement `src/openunlink.c` and the non-writing Make targets. Run
   `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
   tests/test_openunlink.py -q` and `make openunlink-test`.
3. Run `make openunlink`, strict direct GCC and Clang link/syntax checks with
   `-std=c17 -Wall -Wextra -Wpedantic -Werror`,
   `_POSIX_C_SOURCE=200809L`, and `_FILE_OFFSET_BITS=64`, followed by
   clang-format, clang-tidy warnings-as-errors, cppcheck error-exit, and
   `clang --analyze -analyzer-werror` for `src/openunlink.c`.
4. Run `make openunlink-sanitize` and `make openunlink-valgrind`. Both must run
   the complete focused module, including cap, taxonomy, allocation,
   ownership, and seam positive-control cases. Preserve logs proving ASan leak
   detection, UBSan halt-on-error, and Valgrind nonzero error-exit/full leak
   behavior.
5. Run `make man-check` after documentation lands. Compare exact help/version,
   taxonomy, statuses, limits, disclaimers, and non-goals across all named
   documents with the pytest documentation oracles.

Focused success is only an intermediate milestone. It is explicitly not the
definition of done.

### Shared Makefile blast radius and complete-suite gate

The Makefile is shared product infrastructure. Before acceptance, verify all
of the following in one clean integrated tree:

- existing `make`, `make sysdiff`, non-writing `make pathaudit`, and
  non-writing `make permguard` builds remain green beside non-writing
  `make openunlink`;
- all sysdiff shell/pytest, pathaudit, and permguard tests and their existing
  fixture semantics remain green, with no changed goldens, silent skip
  conversions, stale binary redirects, or ambient-environment bypasses;
- `man/sysdiff.1`, `man/pathaudit.1`, and `man/permguard.1` remain warning-free
  when `man/openunlink.1` joins `ALL_MANPAGES`;
- GCC and Clang strict lists, Clang syntax, clang-format `ALL_SRCS`,
  clang-tidy command list, cppcheck `ALL_SRCS`, and Clang analyzer list still
  compile/analyze sysdiff, pathaudit, and permguard as well as openunlink;
- aggregate ASan and UBSan recipes still build and execute all existing
  utilities/tests, preserve permguard's POSIX flag and all established
  sanitizer environment forwarding, and add correctly instrumented
  openunlink production/seam coverage;
- aggregate Valgrind still uses separate non-sanitized GCC debug binaries,
  keeps sysdiff/pathaudit/permguard wrappers and fixtures active, and adds
  complete openunlink coverage without descriptor leaks or double closes;
- `scripts/smoke.sh` still reaches `make test`, so the existing
  sysdiff-centered smoke remains aggregate portfolio regression evidence and
  transitively executes `tests/test_openunlink.py`; existing fixture files and
  smoke behavior are not weakened or relabeled as dedicated openunlink proof;
- install/uninstall, dist/distcheck, release, packaging members, default
  sysdiff binary behavior, and `clean` semantics remain unchanged. Openunlink
  is not installed, packaged, archived, published, tagged, or released.

The release-quality command is a fresh `make clean && make quality`. It must
exit `0` and execute the complete ordinary, ASan, UBSan, and Valgrind
portfolio, not merely `tests/test_openunlink.py`. Required GCC, Clang,
clang-format, clang-tidy, cppcheck, analyzer, groff, procfs, sanitizer runtime,
Valgrind, Python, or pytest unavailability is a loud failure for this governed
quality claim. The passing complete suite—not a passing focused test—is the
definition of done.

After the quality gate, run `./scripts/smoke.sh` separately and retain its
aggregate counts/status as regression evidence. Inspect `git status --short`
and `git diff --check`; confirm no binary, pytest cache, bytecode, generated
seam source, trace, fixture, temporary man output, or unrelated source/doc
change remains in the workspace.

### Dedicated TEST AS USER and independent REVIEW

The governed TEST AS USER step builds a standalone strict `openunlink` in a
temporary directory, starts a same-UID helper with one linked and one
open-then-unlinked regular file, waits for the ready handshake, and validates
the exact clean status-0 and finding-bearing status-1 flows. It records
successful application start, successful core flow, exact streams/statuses,
and empty blocking errors. It must not reuse the sysdiff-centered aggregate
smoke as its dedicated oracle, and it must not leave a workspace binary.

Independent REVIEW receives the authoritative contract, this plan,
`src/openunlink.c`, the complete focused tests, Makefile wiring, manual and
user/maintainer docs, fresh focused/static/memory evidence, the clean complete
`make quality` result, aggregate smoke, and dedicated smoke. Review must check
all 17 mapping rows, source/resource ownership, boundary arithmetic, errno and
taxonomy closure, no-content/no-control posture, filesystem honesty, and the
shared Makefile blast radius. Any Critical, High, or Medium mission finding
returns to TEST/FIX/DOCUMENT as applicable, followed by affected focused gates
and a fresh complete `make quality`; acceptance requires an independent pass
with no unresolved Medium-or-higher mission finding.

## Risks

The most dangerous semantic shortcut is treating procfs link text as truth.
A path literally ending in ` (deleted)` can remain linked, and NFS
silly-rename can keep a nonzero link count for an object users colloquially
call deleted. The real suffix fixture, synthetic nonzero-link fixture,
`SIXTH2-M2` documentation oracle, and independent filesystem-honesty review
keep the predicate anchored only to repeated stable metadata and final
`st_nlink == 0`.

The descriptor cap can accidentally turn bounded evidence into total failure
or select the numerically lowest descriptors rather than the first observed
subset. The 65,536/65,537 seam scenarios place distinct sentinels inside and
after the retained boundary, scramble observed order, and require the retained
finding plus one count advisory. They are intentionally run under ordinary,
sanitizer, and Valgrind focused routes despite their cost; a runtime-driven
skip would reopen `SIXTH2-M1`.

Procfs is inherently point-in-time. A descriptor can disappear, be reused, or
change identity/type between operations. Two metadata observations and the
closed churn mapping reduce false claims but cannot make the result race-free.
The helper freezes only test-owned lifetime, while the seam deterministically
exercises churn. Documentation must not present the result as authorization,
continuous monitoring, recovery advice, reclaimable bytes, or proof about all
deleted objects.

Ownership transfer among the original descriptor, duplicate, and `DIR *` is a
leak/double-close risk, especially on `fdopendir`, `closedir`, stdout flush,
and final-close failures. Explicit state flags, one cleanup path, seam
counters, three allocation-failure cases, compound cleanup cases, ASan, and
Valgrind provide overlapping evidence. A failed `closedir` must not prompt a
second close of the transferred descriptor, and a cleanup error must not
replace an earlier operational code.

The generated seam can produce false confidence if the implementation bypasses
a wrapper or if scenario setup consumes product counters. Each failure has a
paired success case and trace-based call-reachability assertion; the helper
uses real libc outside the source-local remapping. Static production builds
and call-surface audits confirm that the test macro and injected state are
absent. Because the seam uses Linux toolchain interposition/compile routing,
it is a Linux test mechanism consistent with the product support boundary,
not a portability claim.

The maximum escaped line is large enough to expose integer overflow,
off-by-one termination, partial-write, and expensive repeated-allocation
mistakes. Capacities are derived with checked `size_t` arithmetic, buffers are
allocated once, returned link length—not `strlen`—drives escaping, and tests
exercise embedded NUL, all high bytes, exact maximum length, output failure,
and no-loop-allocation counters. Signed `char` must never index or classify
procfs bytes.

Cross-stream ordering is not portable after caller-side merging. Tests capture
stdout and stderr separately and assert only the contract's per-stream order.
Best-effort stderr can be lost, so status `1` with empty stdout remains
advisory-only even if its explanatory write fails. The shell-style
`SIXTH2-M3` oracle guards callers from confusing that case with a
finding-bearing result.

Finally, additive Makefile edits have a broad regression surface. Adding one
source or environment override in the wrong place can drop permguard feature
flags, poison pathaudit routing, instrument Valgrind binaries with sanitizers,
skip existing fixtures, alter manuals, or change sysdiff install/release
behavior. Structural Makefile tests, dry runs, the explicit blast-radius
checklist, aggregate smoke, and the fresh complete quality suite are all
mandatory. No focused openunlink result can waive an existing sysdiff,
pathaudit, or permguard failure.
