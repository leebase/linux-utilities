# `permguard` Bootstrap Implementation Plan

Contract authority: `docs/permguard-bootstrap-contract.md`.

## Authority

`docs/permguard-bootstrap-contract.md` is the sole live contract for this
delivery. The four-code taxonomy (`GROUP_WRITABLE`, `OTHER_WRITABLE`,
`SET_USER_ID`, `SET_GROUP_ID`), symlink rejection, streaming per-operand
emission, and continue-after-error mixed status `2` semantics in that file are
the implementation target.

`docs/permguard-first-vertical-slice-contract.md` and
`plans/permguard-first-vertical-slice-plan.md` are superseded historical
drafts. They must not drive `src/permguard.c` or `tests/test_permguard.py`.
In particular, ignore any claim in those drafts that four-code bootstrap
docs were removed from `docs/` and `plans/`—this bootstrap contract and plan
are the current authority and remain present. AgentFlow closeout
(`context.md`, `STATUS.md`, and related handoff files) must name this
bootstrap contract after review; until then, prefer this plan and the
bootstrap contract over stale one-code handoff prose.

## Architecture

Implement the bootstrap as a single, auditable ISO C17 translation unit for
`permguard`, with a narrow parse-inspect-render pipeline. CLI parsing accepts
one or more explicit operands and a conventional `--` terminator. After
successful parsing, iterate through the borrowed `argv` path pointers exactly
once and call `lstat` exactly once for each. Capture `errno` immediately after
failure. A successful final-link result is detected with `S_ISLNK` and becomes
the specified symbolic-link operational error; the implementation must never
fall back to `stat`, `realpath`, `access`, target opening, or traversal.

Represent each successful non-link observation with the original operand
index and a four-bit hazard mask. Set the mask using `S_IWGRP`, `S_IWOTH`,
`S_ISUID`, and `S_ISGID`, then render set bits in the contract's fixed rank.
Process operands in their original order and retain no data that could reorder
or deduplicate them. Mixed-success processing continues after errors and sets
an operational-error flag; the final decision is `2` if that flag is set,
otherwise `1` if any hazard was emitted, otherwise `0`.

Use one shared byte-escaping writer for stdout findings and stderr diagnostics.
It must quote the original operand, escape hostile bytes deterministically,
check write and flush results, and never use localized `strerror` output.
Keep ownership explicit: `argv` remains borrowed, any observation storage is
process-owned and freed through a single cleanup path, and fixed mode/error
values stay automatic. The implementation is read-only and introduces no
recursion, state file, configuration parser, privilege operation, package
hook, service, networking, or third-party runtime dependency.

Acceptance mapping: AC-01 drives parsing, strict-build compatibility, and the
absence of mutation calls; AC-02 and AC-03 drive the mode-mask classifier;
AC-04 drives index-preserving storage and fixed-rank emission; AC-05 through
AC-07 drive per-operand error recording and error precedence; AC-08 drives the
single final status reducer and exact diagnostic writer; AC-09 drives the
one-`lstat` loop and prohibited-API review.

## Tests

Add byte-oriented automated coverage, preferably in the existing
`tests/test_permguard.py` surface or a clearly named bootstrap module, with a
helper that captures complete stdout, stderr, and numeric exit status. Every
filesystem case uses a unique temporary directory. File and directory
fixtures are created first and then explicitly `chmod`ed; tests verify the
effective mode so the host umask cannot silently change the expected result.
They also record content and mode before scanning and confirm both afterward.

The acceptance checks map to concrete work as follows:

| Check | Test work | Implementation work |
|---|---|---|
| AC-01 | Exact cases for no operand, bare `--`, unknown option, and a leading-dash path after `--`; strict GCC/Clang compile; before/after mode and content assertions | Implement fixed grammar and usage diagnostic; keep mutation APIs absent and C17 warnings clean |
| AC-02 | Temporary regular-file and directory fixtures with explicit clean, group-writable, other-writable, set-user-ID, and set-group-ID modes | Classify the successful `lstat` result without type-specific suppression |
| AC-03 | Parameterize all four single bits plus representative two- and three-bit masks and the four-bit mask; compare exact line order | Build an independent four-bit mask using the standard mode macros and fixed taxonomy rank |
| AC-04 | Pass multiple clean/hazardous file and directory operands in non-lexical order, repeat an operand, and rerun unchanged fixtures for byte-identical output | Preserve operand indices, emit duplicates, and prohibit sorting or deduplication |
| AC-05 | Test a missing path unconditionally and an `EACCES` path when the current identity/filesystem can produce one; pin escaped stderr and status `2` | Capture `errno` immediately, select stable `MISSING`, `INACCESSIBLE`, or numeric inspection diagnostics, and continue |
| AC-06 | Create symlinks to safe and hazardous targets plus a dangling symlink; assert identical link rejection and no target-derived finding | Use only `lstat`, reject `S_ISLNK`, and never perform a target lookup |
| AC-07 | One invocation containing hazardous, missing, clean, symlink, and hazardous operands; assert complete ordered stdout/stderr and final `2` | Continue after per-operand failures while retaining hazard and operational flags; give errors final precedence |
| AC-08 | Pin exact results for clean `0`, hazard `1`, usage `2`, missing `2`, symlink `2`, and mixed `2`; repeat stable cases | Centralize status reduction and exact output/diagnostic rendering, including checked flushes |
| AC-09 | Static source assertions and symlink behavior checks for one `lstat` loop and absence of `stat`, `realpath`, `access`, open-on-operand, traversal, and mutation calls | Keep the filesystem surface to one metadata attempt per operand and the finding vocabulary to four tokens |

Hostile-path cases should include spaces, quotes, backslashes, tabs, newlines,
DEL, and non-UTF-8 bytes where the host interface supports them. Their purpose
is to prove diagnostics and findings remain one printable line per record.
Inaccessible fixtures must be capability-gated honestly because root or some
filesystems may bypass directory permissions. A skip records missing evidence;
the missing-path and symlink cases remain unconditional.

## Verification

First run direct strict builds with both GCC and Clang using
`-std=c17 -Wall -Wextra -Wpedantic -Werror`. Then run the focused permguard
test module with pytest bytecode and cache generation disabled and fixtures in
a unique temporary base directory. Run the full repository test suite
afterward to detect additive regressions. Capture commands, return codes,
test counts, and honest skip reasons rather than summarizing an unrun or
skipped gate as passing.

Run the repository's applicable formatting and static-analysis gates:
clang-format, clang-tidy, cppcheck, and the Clang static analyzer. Exercise
representative clean, four-hazard, symlink, missing, mixed-success, hostile
path, and multi-operand flows under AddressSanitizer, UndefinedBehaviorSanitizer,
and Valgrind when available. Output checks compare full bytes, not prefixes,
and repeat the non-lexical multi-operand case to establish stable ordering.

Finish with a source audit for prohibited calls and taxonomy drift, then
inspect repository status for unexpected generated artifacts. Verification
must demonstrate all three statuses: `0` from clean temporary file/directory
fixtures, `1` from a hazard-only mode fixture, and `2` separately from usage,
missing, inaccessible when supported, symlink, and mixed runs. Record that a
safe-target symlink and hazardous-target symlink are indistinguishable at the
classification boundary because neither target was followed.

## Risks

Mode-sensitive fixtures are vulnerable to umask behavior, privilege, mount
options, and filesystems that clear set-ID bits. Tests mitigate this by
calling `chmod` after creation, reading the resulting mode back, and skipping
only the specific unsupported capability with a precise reason. Directory
search restrictions may not produce `EACCES` for root, so inaccessible-path
coverage must never be faked or conflated with an unconditional missing-path
pass.

The greatest semantic risks are accidentally following symlinks, suppressing
set-ID or writability hazards based on file type, and returning `1` instead of
`2` when hazards coexist with operational errors. Dedicated safe-target,
hazardous-target, dangling-link, multi-bit, and mixed-success fixtures pin
those boundaries. Static checks for `stat`, `realpath`, `access`, traversal,
and target opening supplement behavior checks without replacing them.

Two output streams cannot provide a portable total order once a caller merges
them. The contract therefore promises operand order independently within
stdout and stderr, and tests capture the streams separately. Hostile operand
bytes and output failures can expose escaping or checked-I/O mistakes, so the
shared writer needs focused tests and sanitizer coverage. Point-in-time
`lstat` observations remain inherently racy; this scanner is an audit aid,
not an authorization primitive or continuous enforcement mechanism.

## Non-Goals

Implementation work must not add recursion, permission repair, configuration
files, privilege escalation, package integration, ACL interpretation, or
extended-attribute interpretation. It also must not enumerate directory
contents, walk ancestors, read `PATH`, resolve command names, canonicalize or
deduplicate operands, interpret ownership, inspect Linux capabilities, parse
file contents, add a daemon or watch mode, use networking, or emit telemetry.

No install target, distribution package, package-manager hook, release claim,
policy language, JSON mode, remediation recommendation, interactive prompt,
or persistent scan database belongs in this bootstrap. Sole-argument `--help`
and `--version` are defined by the contract (matching suite quality-floor
probes); no other informational options are invented during implementation.
Future taxonomy or CLI additions require their own approved contract revision,
tests, and documentation rather than opportunistic expansion of this bounded
slice.
