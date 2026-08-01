# `permguard` First Vertical-Slice Delivery Plan

Contract authority: `docs/permguard-first-vertical-slice-contract.md`.

This plan delivers the smallest contract-defined slice and reconciles the
existing bootstrap implementation with it. The slice answers only whether an
explicitly named directory entry is a world-writable regular file. It does not
add recursion, `PATH` lookup, ownership policy, directory hazards, set-ID
hazards, remediation, installation, packaging, or release publication.

## Architecture

`src/permguard.c` will remain one ISO C17 process with no worker processes,
threads, daemon, service, network access, configuration parser, database, or
third-party runtime library. Its only filesystem classification operation will
be one POSIX `lstat` call per validated operand. The implementation will use
`S_ISREG(st_mode)` and `S_IWOTH` directly; it will remove the former directory
and set-ID hazard classification, ranking, and portability scaffolding so the
executable agrees with the contract's closed one-code taxonomy. The superseded
bootstrap contract and implementation plan that asserted a four-code taxonomy
are removed from `docs/` and `plans/` rather than left unlabeled beside this
authority.

The processing pipeline will be explicit and reject-closed:

1. Parse the fixed CLI grammar without reading stdin, `PATH`, locale policy,
   configuration, or environment policy.
2. Validate operand count, each byte length, and aggregate bytes before
   metadata inspection or allocation. Check addition and multiplication before
   performing them.
3. Allocate one bounded observation array, then inspect operands in their
   original order. Capture `errno` immediately when `lstat` fails and stop at
   the first failed operand.
4. Emit no findings until every lookup succeeds. Then render at most one
   `WORLD_WRITABLE_FILE` record per operand in original order, including
   duplicates, and check every stdout write and final flush.
5. Free all process-owned storage through one cleanup path and return only
   `0`, `1`, or `2`.

Allocation ownership will be recorded next to the relevant declarations:
`argv` and each operand pointer are borrowed from the C runtime and are never
freed or modified; the observation array is exclusively owned by `run_scan`
from successful allocation until its single cleanup point; local `struct stat`,
`errno`, counters, and fixed diagnostic buffers have automatic storage and
never escape their scope. No pointer into a temporary buffer will be retained.
An allocation-size multiplication guard will precede `calloc`, even though the
operand-count limit already provides a tighter practical bound.

Path handling will be byte-preserving. `strlen` is valid because Linux argv
cannot contain embedded NUL, but paths will not be decoded, normalized,
canonicalized, opened, traversed, or replaced by symlink targets. One shared
quoted-byte writer will render stdout and stderr paths: printable ASCII is
literal except escaped quote and backslash; all other bytes become uppercase
`\xHH`. This bounds expansion to four output bytes per input byte plus quotes
and fixed tokens. Diagnostics will use fixed reason tokens and a fixed-size
buffer large enough for `INSPECTION_ERROR_` plus the unsigned decimal `errno`;
`snprintf` results will be checked, and neither `strerror` nor an
operand-sized diagnostic allocation will be introduced.

The implementation dependency boundary is libc/POSIX only: ISO C17 language
and library facilities plus Linux/POSIX `lstat`, mode macros, signals, and
stdio. The existing SIGPIPE handling may remain to turn a closed pipe into the
contracted `STDOUT_WRITE` result, but its failure must not be mislabeled as
out-of-memory. If that practically unreachable setup failure is retained, it
will receive an accurate bounded internal failure path documented by the
contract; otherwise the implementation will use a simpler checked-output
strategy that still makes the closed-pipe test deterministic. No new package
or optional runtime dependency is justified.

Concrete file changes:

- `src/permguard.c`: reduce the hazard representation to one boolean/bit,
  delete directory/sticky/set-ID policy and rank entries, preserve single
  `lstat`, checked limit arithmetic, pre-emission observations, shared escape
  writing, exact diagnostics, cleanup ownership, and checked stdout behavior.
- `Makefile`: keep `permguard` non-installing and additive; ensure strict GCC,
  strict Clang, sanitizer, Valgrind, and analyzer invocations use named
  `mktemp -d /tmp/permguard-...` directories with traps and never create
  `build/permguard`, top-level `permguard`, analyzer plists, object files, or
  logs in the workspace.
- `README.md`, `CHANGELOG.md`, and `man/permguard.1`: replace the existing
  four-code description with the one-code rule and explicitly describe clean
  directories, set-ID files, ownership, recursion, `PATH`, remediation,
  installation, packaging, and release as outside this slice.
- `docs/permguard-first-vertical-slice-contract.md`: remain normative; correct
  only ambiguities discovered while implementing tests, without expanding the
  taxonomy or weakening exact bytes, limits, ordering, ownership, or non-goals.

## Tests

`tests/test_permguard.py` will be one byte-oriented pytest module with four
coexisting layers rather than four disconnected harnesses. Shared helpers will
compile or select the binary, execute it with a controlled environment, render
expected escaping, capture complete stdout/stderr bytes, assert exit status,
and create modes explicitly after fixture creation. Tests will be named or
marked by layer so a focused failure is understandable while the normal
module run exercises all layers together.

- Unit-style cases will exercise externally visible pure rules through the
  binary: exact help/version/usage/unknown-option bytes, escaping of every
  hostile byte class, the regular-file-plus-`S_IWOTH` predicate, clean
  owner/group-only modes, limit arithmetic, and the `0`/`1`/`2` status matrix.
  Because production helpers remain `static`, tests will not expose internals
  or add a second C test-only API.
- Integration cases will combine CLI parsing, real `lstat`, ordering,
  pre-emission buffering, and stdio: `--`, leading-dash paths, duplicate and
  deliberately non-lexical operand order, multiple clean/hazard operands,
  hazardous-first-then-failing inspection, ambient `PATH`/stdin independence,
  and closed stdout.
- Regression cases will pin previously plausible failures: following final
  symlinks, emitting former directory or set-ID codes, raw control-byte or
  non-UTF-8 injection, localized `strerror`, lexical sorting, deduplication,
  partial findings before a later lookup error, inherited `PERMGUARD_BIN`
  routing, workspace binary creation, and nondeterministic repeated output.
- Filesystem-fixture cases will use `tmp_path` to cover private,
  owner-writable, group-writable, world-writable, and executable
  world-writable regular files; world-writable directories; FIFO and Unix
  socket where supported; live and dangling final symlinks; missing entries;
  `ENOTDIR` intermediates; intermediate symlink loops; and honestly
  capability-gated `EACCES`. Each mode-sensitive fixture will call `chmod`
  after creation and verify effective mode bits so umask or filesystem behavior
  cannot silently alter the oracle.

Acceptance-check traceability is explicit below. Each row names coverage in
`tests/test_permguard.py` and a deterministic focused command. All commands
run from the repository root with bytecode and pytest cache disabled.

| Check | `tests/test_permguard.py` coverage | Deterministic verification command |
|---|---|---|
| AC-01 | Session strict-build fixture plus `test_unit_exit_status_matrix` | `PYTHONDONTWRITEBYTECODE=1 CC=gcc python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'unit_exit_status_matrix' && PYTHONDONTWRITEBYTECODE=1 CC=clang python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'unit_exit_status_matrix'` |
| AC-02 | `test_fixture_*regular_file*`, `test_regression_world_writable_setid_emits_only_file_code`, and `test_regression_taxonomy_is_closed_one_code` | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'regular_file or world_writable_setid or taxonomy_is_closed'` |
| AC-03 | `test_fixture_*directory*`, FIFO/socket fixtures, and `test_*symlink*` | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'directory or fifo or socket or symlink'` |
| AC-04 | `test_unit_help*`, `test_unit_version*`, usage tests, and `test_integration_*operand*` / ordering cases | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'help or version or usage or option or double_dash or leading_dash or operand_order or duplicate_operands or enabling_flag'` |
| AC-05 | `test_hostile_*`, quote/backslash, non-UTF-8, tab/newline, and DEL cases | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'hostile or quote_and_backslash or non_utf8 or tab_and_newline or del_byte'` |
| AC-06 | `test_unit_limit_constants_match_contract` and all `test_integration_path_*limit*` cases | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'limit_constants or path_length or path_bytes or path_count'` |
| AC-07 | Missing-path, inaccessible-path, `ENOTDIR`, and intermediate-loop integration cases | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'missing_path or inaccessible_path or enotdir or symlink_loop'` |
| AC-08 | `test_integration_hazard_then_missing_rejects_closed` | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py::test_integration_hazard_then_missing_rejects_closed` |
| AC-09 | `test_integration_closed_stdout_pipe_reports_stdout_write` | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py::test_integration_closed_stdout_pipe_reports_stdout_write` |
| AC-10 | Repeat-run, duplicate-operand, and operand-order regression cases | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'repeat_run or duplicate_operands or operand_order'` |
| AC-11 | `test_regression_source_uses_lstat_not_stat_follow`, symlink, ambient-input, and mode-unchanged cases | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py -k 'source_uses_lstat or symlink or ambient_path or modes_unchanged'` |
| AC-12 | Former-code, substantive-heading, and Markdown taxonomy regressions; the full module supplies the dynamic workload | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_permguard.py && make format-check clang-tidy-check cppcheck-check clang-analyzer-check permguard-sanitize permguard-valgrind` |

Documentation changes will be tested as contract surfaces, not merely edited by
inspection. `README.md` will give a short operational example and link the
authoritative contract and man page. `CHANGELOG.md` will record an unreleased
one-code vertical slice without claiming installation or release.
`man/permguard.1` will match exact CLI/output/diagnostic/status semantics and
pass `groff -man` warnings-as-failures. Tests will remove or invert all
four-taxonomy expectations currently present in the module.

## Verification

Governed validation must not create undeclared workspace artifacts. Every
compiler binary, object, analyzer result, sanitizer executable, Valgrind log,
pytest base directory, and temporary fixture tree will be placed beneath a
unique `/tmp/permguard-...` directory and removed by a trap or pytest cleanup.
Do not rely on an unspecified `mktemp` default and do not write
`build/permguard`, `./permguard`, `.pytest_cache`, `__pycache__`, analyzer
plist files, coverage files, or temporary notes in the repository. Set
`PYTHONDONTWRITEBYTECODE=1`, disable pytest's cache provider, and use an
explicit `--basetemp=/tmp/permguard-pytest-...` path.

The implementation step will run, in order:

1. Strict direct GCC and Clang builds of `src/permguard.c` to separate
   `/tmp/permguard-gcc-.../permguard` and
   `/tmp/permguard-clang-.../permguard` binaries with
   `-std=c17 -Wall -Wextra -Wpedantic -Werror`.
2. `clang-format --dry-run --Werror`, clang-tidy with warnings as errors, and
   cppcheck with `--error-exitcode=1`. These tools must be configured not to
   emit workspace reports. Run Clang static analysis with its `-o` path inside
   `/tmp/permguard-analyzer-...`.
3. Focused pytest for `tests/test_permguard.py`, using an explicit `/tmp`
   basetemp and no cache/bytecode. Then run the full existing pytest suite with
   the same hygiene to prove the additive changes do not regress `sysdiff` or
   `pathaudit`; do not route the focused suite through a stale inherited
   `PERMGUARD_BIN`.
4. `make man-check` after ensuring its warning file is created under `/tmp`,
   plus dry-run seam checks that permguard compilation and analysis targets
   contain `/tmp/permguard-` and no workspace output path.
5. ASan and UBSan functional/hostile-input runs using binaries under `/tmp`,
   leak detection or halt-on-error settings as applicable, followed by the
   non-sanitized Valgrind gate with full leak checking and a nonzero error exit
   code. Exercise more than `--help`: include a clean file, hazardous hostile
   name, reject-closed lookup error, and output-failure path where the tool can
   support it.
6. A final workspace audit with `git status --short` and a targeted search for
   binaries, object files, analyzer reports, caches, and logs. Only the
   playbook-declared product/document changes may remain; validation residue is
   a failure to clean up.

Tool availability is evidence. Required GCC/Clang and pytest failures block the
slice. For optional host tools, the record will distinguish “passed,” “failed,”
and “not run because unavailable,” including the discovery command and reason.
No skipped filesystem case will be described as passed; the pytest skip reason
must state the unavailable host capability (for example inability to create an
AF_UNIX socket, preserve a set mode, construct argv beyond `ARG_MAX`, or
produce `EACCES` under the current identity).

Completion evidence will enumerate changed files and tie results back to the
traceability table. It will quote test counts and skipped counts without
overstating them, state that the utility remains unreleased and uninstalled,
and retain the contract as the normative source if summaries differ.

## Risks

The largest immediate risk is taxonomy drift: leaving a second identically
titled contract or plan that still asserts four findings beside the
authoritative one-code contract. Delivery must remove former hazard behavior
and claims consistently, including deleting or explicitly superseding any
bootstrap four-code docs. A mechanical forbidden-code check must scan every
`docs/permguard*.md` and `plans/permguard*.md` file and allow former-code
tokens only inside an explicitly superseded block.

Host process limits can prevent direct construction of a 65,536-byte operand,
65,536 operands, or a 1 MiB argv even though the program's bounds are correct.
Those cases require honest capability skips plus reviewable static checks of
constants, pre-addition overflow guards, validation order, and allocation
multiplication. Tests must not reduce product limits merely to make the host
exercise them, and a skip must never be counted as a pass.

Filesystem semantics vary by privilege, mount, and filesystem. Root can bypass
an intended permission-denial fixture; some filesystems clear set-ID bits or
reject sockets and unusual byte names. The suite will verify modes after
`chmod`, gate only the affected fixture, restore permissions in `finally`, and
keep the central regular-file cases unconditional. Tests must not infer
classification from Python's effective-access checks.

Output failure is timing-sensitive because SIGPIPE can terminate a process
before stdio reports an error. The design will preserve a deterministic
closed-pipe fixture and accurate diagnostic semantics without introducing a
heap buffer or a misleading setup-failure reason. Partial stdout is acceptable
only after an actual output failure; every validation, allocation, and
inspection failure must retain empty stdout.

The point-in-time `lstat` observation is inherently subject to filesystem races
before and after inspection. This slice does not claim authorization, locking,
or race-free enforcement. Avoiding `realpath`, target opening, directory walks,
and remediation keeps the race surface aligned with the contract, but the
README and manual must retain the limitation.

Finally, broad suite Makefile targets may historically create the ordinary
`build/sysdiff` binary even when permguard itself is temporary. Governed
validation for this slice must use the targeted `/tmp` recipes or refactor the
relevant gate before running it. Cleanup commands must target only validated
unique temporary directories; they must not erase unrelated user changes or
use a broad workspace deletion to manufacture a clean artifact audit.
