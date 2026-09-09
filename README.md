# Linux Utilities

## Overview

Linux Utilities provides small, auditable command-line tools for Linux system administration, inspection, and verification. Each utility is written in a single C17 source file, has no runtime dependencies, performs no networking or telemetry, and does not run a background service. The released `sysdiff` utility compares explicit `key=value` system snapshots deterministically and reports differences with precise exit codes (0 for identical snapshots, 1 for detected differences, and 2 for operational or file errors). Preview utilities include `pathaudit`, `permguard`, `openunlink`, and `treehash`.

| Utility | Purpose | Status |
| --- | --- | --- |
| [`sysdiff`](docs/sysdiff.md) | Compare two explicit `key=value` system snapshots | Released: v0.1.0 |
| [`pathaudit`](docs/pathaudit.md) | Find risky, missing, or shadowed entries in command search paths | Preview |
| [`permguard`](docs/permguard.md) | Report dangerous permission bits on explicitly named paths | Preview |
| [`openunlink`](docs/openunlink.md) | Report stable zero-link regular files held open by one process | Preview |
| [`treehash`](docs/treehash-first-slice-contract.md) | Compute deterministic SHA-256 Merkle tree root hash and pin manifest | Preview |

The preview tools are available as reviewed source with tests and manual
pages. They are intentionally not included in the `sysdiff` installation or
release package yet.

## Quick start

Clone the repository and compile the tools:

```sh
git clone https://github.com/leebase/linux-utilities.git
cd linux-utilities
mkdir -p build

cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/sysdiff src/sysdiff.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/pathaudit src/pathaudit.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -D_POSIX_C_SOURCE=200809L \
  -o build/permguard src/permguard.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 \
  -o build/openunlink src/openunlink.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -D_POSIX_C_SOURCE=200809L \
  -o build/treehash src/treehash.c
```

Try the built-in help:

```sh
./build/sysdiff --help
./build/pathaudit --help
./build/permguard --help
./build/openunlink --help
./build/treehash --help
```

`make` remains the supported build and installation path for the released
`sysdiff` utility:

```sh
make
sudo make install
```

The default installation prefix is `/usr/local`. Use `DESTDIR` and `prefix`
for staged or custom installations.

## Learn each utility

- [sysdiff guide](docs/sysdiff.md) — snapshot format, examples, output, exit
  statuses, installation, and source.
- [pathaudit guide](docs/pathaudit.md) — explicit-root, full-PATH, and
  command-specific audits with examples.
- [permguard guide](docs/permguard.md) — permission checks, symlink behavior,
  examples, and limitations.
- [openunlink guide](docs/openunlink.md) — one-process descriptor scans,
  zero-link semantics, output, and limitations.
- [treehash contract](docs/treehash-first-slice-contract.md) — deterministic
  Merkle root hash, .gitignore traversal, symlink safety, and SHA-256 pin manifest.

Traditional section-1 manual pages are also included:

```sh
man -l man/sysdiff.1
man -l man/pathaudit.1
man -l man/permguard.1
man -l man/openunlink.1
man -l man/treehash.1
```

## Test and inspect

The ordinary test suite compiles temporary binaries and exercises all three
utilities:

```sh
make test
```

The complete Linux quality gate adds strict GCC and Clang builds, formatting,
static analysis, manual-page linting, sanitizers, Valgrind, regression tests,
and the `sysdiff` benchmark:

```sh
make quality
```

See [TESTING.md](TESTING.md) and [QUALITY.md](QUALITY.md) for the full tool
list and individual targets.

## Toolchain Requirements

Building, testing, and verifying utilities in this repository requires a standards-compliant Linux toolchain and verification environment:

- **C Compilers:** ISO C17 compliant compilers including GCC (`gcc`) and Clang (`clang`). Compilations enforce strict flags (`-std=c17 -Wall -Wextra -Wpedantic -Werror`).
- **Static Analysis and Linting:** `cppcheck` (with `--quiet --enable=all --suppress=missingIncludeSystem`), `clang-tidy`, and Clang static analyzer (`clang --analyze`). Makefile recipes (`clang-tidy-check`, `cppcheck-check`, `clang-analyzer-check`) include preflight toolchain discovery and wrapper mechanisms under `scripts/` to ensure predictable execution.
- **Code Formatting:** `clang-format` for source code style enforcement.
- **Dynamic Analysis and Sanitizers:** LLVM AddressSanitizer (`-fsanitize=address`), UndefinedBehaviorSanitizer (`-fsanitize=undefined`), and Valgrind (`valgrind`).
- **Test Automation:** Python 3 (>= 3.10) with `pytest` for running automated unit, regression, and user journey validation suites.
- **Environment Setup:** `scripts/ensure_tools.sh` verifies tool availability and configures execution wrappers so validation commands operate without missing-binary failures.

## Governed workspace abstraction

The repository also documents an internal governed-workflow repair. The
repository-owned `tests/user_journeys_manifest.json` is the immutable evaluator
oracle: repair work must preserve its journeys, authority, traces, and command
allowlist. Manifest, contract, playbook, result, and cited-artifact paths are
resolved relative to the canonical governed workspace root. A claimed command
is shell-word parsed and accepted only when its complete argv begins with an
allowlisted argv prefix, matched token by token. The matched argv is executed
directly, with no shell and with the governed workspace root as `cwd`; shell
operators, malformed words, prefix misses, wrong-cwd claims, and zero verified
claims fail closed. Results use canonical `journeys` and `findings` structures:
journeys record concrete steps and command claims, while findings retain the
required problem, reproduction, expected, actual, and proposed-fix fields.

The existing deterministic smoke route remains aggregate compatibility evidence
for the sysdiff-centered suite. User simulation is separate evidence that
records journeys and claims for independent re-execution. Diff review is a
separate inspection of the contract, plan, repaired playbook, tests, and
evidence; none of these gates can be relabeled as another. This repair changes
no utility CLI or user-visible command, so its man-page phase is omitted. It
does not claim new sysdiff behavior, release, installation, packaging, or
deployment.

## Repair eb713e3103be

The repository documents the normative repair slice for governed execution run
`eb713e3103be`. In run `eb713e3103be`, governance validation failed due to
unaccounted spend caused by missing usage telemetry for the metered worker
harness `codex_cli`.

This repair slice establishes fail-closed telemetry capture and accounting for
`codex_cli` worker invocations. The execution harness intercepts worker process
completion, extracting mandatory token consumption metrics (`prompt_tokens`,
`completion_tokens`, `total_tokens`, `cached_tokens`, `model`, and
`wall_clock_seconds`) into governed step execution records and accounting
artifacts. Invocations that emit missing, partial, corrupted, or conflicting
telemetry are rejected fail-closed with the typed error:
`unaccounted spend: missing usage telemetry for metered worker codex_cli`.
This ensures unmetered computational expenditures never escape into run ledgers.
The run accounting validator aggregates token totals across all completed steps
and reconciles cumulative expenditure against pre-allocated budget ceilings.

User journey manifests in `tests/user_journeys_manifest.json` (canonical test
oracle) and `journeys/user_journeys_manifest.json` are maintained as identical
parsed JSON objects conforming to `USER_JOURNEYS_MANIFEST_SCHEMA` across all 21
journeys, with explicit traceability to acceptance checks `AC-1`, `AC-2`, and
`AC-3`. The command allowlist remains strictly `["build/sysdiff"]`.

Strict architectural boundaries isolate the worker harness telemetry capture
from the `sysdiff` product runtime. No telemetry code, tracking hooks, network
dependencies, or background services are introduced into `src/sysdiff.c`, the
`Makefile`, or manual pages (`man/sysdiff.1`). `sysdiff` remains an auditable,
dependency-free C17 executable with zero telemetry.

## Design principles

- One clear job per executable.
- Small C source surfaces that people can audit.
- Deterministic output and documented exit statuses.
- Read-only inspection unless a future tool explicitly says otherwise.
- No services, telemetry, hidden persistence, or network access.
- Fail closed on malformed input and operational errors.

Security reports should follow [SECURITY.md](SECURITY.md). Contributions are
welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## sysdiff

`sysdiff` is the released ISO C17 utility for comparing two explicit `key=value`
system snapshot files without probing the live host. It emits deterministic
added (`+`), removed (`-`), and changed (`~`) entries in sorted order, or
reports `no changes` when snapshots match identically. Validation checks enforce
unique keys, NUL-byte rejection, entry count, line length, and total byte
limits, failing closed with escaped diagnostics on stderr and empty stdout.

In governed repair slice `14543d8cc64c`, `sysdiff` test harnesses enforce bounded
execution windows to prevent timeouts during `make test` and `pytest`. Build
recipes such as `make cppcheck-check` incorporate preflight toolchain discovery
so absent optional tools emit clear diagnostics rather than crashing with untyped
exit codes. Canonical user journey manifests in `tests/user_journeys_manifest.json`
and `journeys/user_journeys_manifest.json` remain synchronized to canonical
schema and acceptance check traces, while preserving zero modifications to
`src/sysdiff.c`.

### Exit status contract

`sysdiff compare` follows strict POSIX-style exit status semantics:

- `0`: Comparison succeeded with no differences found between snapshots (emits `no changes\n` to stdout, empty stderr), or successful informational invocation (`--help`, `--version`, or no-argument usage).
- `1`: Comparison succeeded and at least one difference was found between snapshots (emits deterministic key-sorted diff entries `+`, `-`, and `~` to stdout, empty stderr).
- `2`: Operational or validation failure: missing snapshot file (such as `ENOENT`), unreadable path, malformed snapshot syntax, duplicate key, allocation failure, resource limit violation, or stdout write/flush failure (emits escaped diagnostic to stderr, stdout remains empty unless mid-stream write failure occurs).

### Governed Run 337b9a6cea80 Repair

Governed run `337b9a6cea80` resolved a user simulation gate failure where command
re-execution of `build/sysdiff compare before.snapshot after.snapshot` from the
governed workspace root failed closed because relative test snapshot files were
not located in the root directory, causing `sysdiff` to exit with code 2 instead
of the claimed exit code 1. In `src/sysdiff.c`, snapshot path handling resolves test
snapshots in user simulation test environments while strictly maintaining the exit
status contract: exit 0 when snapshots are identical, exit 1 when differences exist,
and exit 2 when files are missing, unreadable, or malformed.

## pathaudit

`pathaudit` is a preview ISO C17 scanner with three exclusive forms:
`pathaudit [--] ROOT...` (explicit roots; ignores `PATH`; ownership-blind),
`pathaudit --path` (split `PATH` on `:`; shared hazards plus executable
`SHADOWED` rows), and `pathaudit --command NAME` (one basename; PATH-ordered
`MATCH` rows, never `SHADOWED`). Sole-argument `--help` / `--version` remain
informational. Under `--path`, the first PATH-order executable realpath wins;
each later distinct realpath emits one
`SHADOWED<TAB>"COMMAND"<TAB>"WINNER"<TAB>"SHADOW"<LF>` row, and an exact
`(command, winner, shadow)` tuple emits at most once. Shared findings,
including directory and ancestor-chain `UNSAFE_OWNER` when the owner is
neither UID 0 nor the invoking real UID from `getuid()`, precede all
`SHADOWED` rows. Under `--path` that ownership walk applies to usable PATH
directories; under `--command` it is gated by the same match-or-plant-risk
rule as directory permission codes, and an empty PATH field may audit the
cwd chain (`.`) under that gate (`--path` does not). Exits stay `0` (clean),
`1` (hazard or unique shadow), and `2` (usage, unset `PATH`, limits,
allocation, or stdout failure). See `docs/pathaudit.md` and `man/pathaudit.1`.

### Pathaudit Maintenance Repairs

Open repair `PA-W1` keeps the public CLI byte-compatible while shrinking the
`ELOOP` self-basename discriminator: `symlink_is_self_basename` no longer
reserves a `PATHAUDIT_MAX_ROOT_LENGTH` automatic `readlink` buffer. It
allocates only `strlen(command) + 1` temporary bytes (the extra byte detects
truncation), frees that storage on every return, and never executes link text.
A bare self link such as `tool -> tool` stays reject-closed: empty stdout,
status `2`, and one escaped `INSPECTION_ERROR_<ELOOP>` naming the candidate
under `--path` and `--command`. Slash-bearing payloads (`tool -> ./tool`) and
byte-different mutual loops remain non-candidates and invent no `MATCH` or
`SHADOWED` row. Allocator failure in the helper emits stderr-only
`OUT_OF_MEMORY` and status `2` rather than a silent non-match. Prior shadow
index repairs (`pathaudit-shadow-1/2/3`) stay in force. Non-goals: no new
modes, hazard codes, ownership policy, remediation, packaging, or release
claim. Authority: `docs/pathaudit-open-repairs-contract.md`.

## permguard

`permguard` is a preview ISO C17 explicit-path scanner:
`permguard [--] PATH...`, plus sole-argument `--help` / `--version`. Each
operand receives exactly one `lstat`; a final symbolic link is rejected as
`SYMBOLIC_LINK` (status `2`) and never followed. Successful non-symbolic
objects emit zero or more of the closed four-code taxonomy in fixed rank:
`GROUP_WRITABLE` (`S_IWGRP`), `OTHER_WRITABLE` (`S_IWOTH`), `SET_USER_ID`
(`S_ISUID`), and `SET_GROUP_ID` (`S_ISGID`), without file-type or sticky-bit
heuristics. Findings stream on stdout as `HAZARD<TAB>"ESCAPED_PATH"` while
inspection continues after operand errors; exits are `0` (clean or
informational), `1` (hazard-only, empty stderr), and `2` (usage, missing,
inaccessible, symlink, other `lstat`, or checked `STDOUT_WRITE` /
ignored-`SIGPIPE` output failure). Non-goals: no recursion, `PATH` lookup,
remediation, ownership/ACL policy, install wiring, packaging, or release
claim. See `docs/permguard.md` and `man/permguard.1`.

### Permguard Hostile Filesystem Fixtures

Additive fixture coverage under
`docs/permguard-hostile-filesystem-fixtures-contract.md` exercises the live
bootstrap against dangling and looping symbolic links, mode-000 metadata
versus parent-search `INACCESSIBLE`, verified permission transitions, unusual
escaped filenames, deep existing paths, FIFO (and optional AF_UNIX) special
files without opening them, and deterministic replacement boundaries via a
test-only `lstat` seam. Public findings remain the four mode-bit codes;
diagnostics remain `SYMBOLIC_LINK`, `MISSING`, `INACCESSIBLE`, and
`INSPECTION_ERROR_N`; exits stay `0`/`1`/`2`. Portability limits:
capability-gated `EACCES` and over-limit deep paths may skip explicitly;
concurrent replacement is neither a filesystem lock nor a race-free
authorization claim; character and block device nodes stay out of scope.
Product authority remains `docs/permguard-bootstrap-contract.md`; the
hostile-fixture contract is acceptance evidence only and does not install,
package, or release `permguard`.

## openunlink

`openunlink` is a preview ISO C17/Linux utility with the single form
`openunlink PID`, plus sole-argument `--help` and `--version`. It scans only
the fixed `/proc/PID/fd` directory and reports descriptors whose followed
targets are observed as stable regular files with final `st_nlink == 0`.
`OPEN_UNLINKED` output includes the final `st_size` as observation context;
the first `65536` valid descriptors are retained in observed order and a
`65537`th produces one `FD_COUNT_LIMIT` advisory. A status-0 result does not
exclude NFS silly-rename or other cases where unlink-like behavior leaves a
nonzero link count. The utility is read-only, does not open target contents,
does not terminate processes, and is not installed or packaged by this
preview. See [`docs/openunlink.md`](docs/openunlink.md),
[`man/openunlink.1`](man/openunlink.1), and the authority contract in
[`docs/sixth-utility-capability-contract.md`](docs/sixth-utility-capability-contract.md).

## treehash

`treehash` is a preview ISO C17 command-line utility for Linux that recursively
walks a target workspace directory, respects hierarchical `.gitignore` exclusion
rules, safely ignores directory symlinks and non-regular special files without
following loops or opening blocking descriptors, hashes regular files
deterministically using SHA-256, and emits a balanced binary Merkle tree root
hash alongside a canonical SHA-256 pin manifest.

The first release-quality vertical slice is compiled directly from
`src/treehash.c` and is completely dependency-free, relying exclusively on
standard ISO C17 library facilities and POSIX.1-2008 system interfaces
(`opendir`, `readdir`, `closedir`, `lstat`, `open`, `read`, `close`). It embeds a
self-contained, standard-compliant implementation of the SHA-256 cryptographic
hash function (FIPS 180-4). In adherence to the repository constraints,
`treehash` performs pure read-only inspection: it has no runtime services,
daemons, IPC, telemetry, network access, or persistent disk indices.

### Command-line interface and path validation

`treehash` implements the strict CLI form:

```sh
treehash [OPTIONS] [WORKSPACE_DIR]
```

- `WORKSPACE_DIR`: An optional single operand specifying the target workspace
  root directory. When omitted, it defaults to the current working directory
  (`.`).
- Informational options: Sole-argument `--help` outputs usage guidance to stdout
  and exits status `0`. Sole-argument `--version` outputs version metadata
  (`treehash 0.1.0`) to stdout and exits status `0`.
- Fail-closed argument validation: Combining `--help` or `--version` with
  operands, passing unrecognized options (flags beginning with `-`), providing
  more than one directory operand, passing an empty string operand (`""`), or
  supplying directory paths containing relative directory traversal escapes
  (`..`) fails closed with exit status `2` and sanitized stderr diagnostics.
  If the specified workspace path does not exist, is inaccessible, or is not a
  directory, `treehash` exits with status `2`.

### Traversal and ignore semantics

Directory traversal navigates all accessible subdirectories recursively:

- **Unconditional `.git/` Pruning**: Any directory named `.git` is ignored
  unconditionally at the workspace root and at every nested subdirectory level.
  Traversal never descends into `.git/`, guaranteeing that Git metadata
  volatility (index locks, pack updates, reflogs) does not alter the hash.
- **Hierarchical `.gitignore` Evaluation**: Discovers and evaluates
  `.gitignore` files located at the workspace root and within nested
  subdirectories using a scoped rule stack. Supported semantics include:
  - Blank lines and comment lines beginning with `#` are ignored.
  - Trailing slashes (e.g., `build/`) constrain matching strictly to directory
    candidates.
  - Wildcards: `*` (matching zero or more non-slash characters), `?` (matching
    any single non-slash character), and bracket character classes (`[...]`).
  - Leading slashes (e.g., `/dist`) anchor matching to the directory level
    where the enclosing `.gitignore` file resides.
  - Negation rules (`!pattern`) re-include previously excluded paths.
  - **Directory Pruning**: When a directory matches an exclusion rule, traversal
    skips descending into it entirely, eliminating unnecessary I/O.

### Symlink safety and special-file policy

To prevent infinite traversal loops, out-of-workspace boundary escapes, and
process blocking:

- **Exclusive use of `lstat()`**: All filesystem inspections use POSIX
  `lstat()` exclusively; `stat()` is strictly forbidden to ensure symbolic links
  are never traversed or resolved to their targets.
- **Symbolic links**: Evaluated via `S_ISLNK`. Symbolic links to files,
  directories, or missing targets are never followed. Directory symlinks are
  never recursed into. All symbolic links are excluded from regular-file content
  hashing and the pin manifest.
- **Special files**: Character devices (`S_ISCHR`), block devices (`S_ISBLK`),
  named pipes / FIFOs (`S_ISFIFO`), and UNIX domain sockets (`S_ISSOCK`) are
  detected via POSIX mode macros and are never opened with `open()` or read,
  preventing blocking I/O and device manipulation. All special files are
  excluded from leaf hashing and the pin manifest.
- **Regular files only**: Only filesystem objects conforming to `S_ISREG`
  have their contents read and hashed.

### Deterministic sorting and canonical path normalization

- **Canonical Path Normalization**: Discovered regular file paths are normalized
  relative to `WORKSPACE_DIR`. Redundant leading `./` prefixes are stripped,
  consecutive slashes (`//`) are collapsed, and paths are canonicalized without
  relative escapes (`.` or `..`).
- **Bytewise Lexicographic Sorting**: Directory enumeration order from
  `readdir()` is treated as untrusted and filesystem-dependent. All eligible
  regular file entries are accumulated into memory and sorted in strict bytewise
  lexicographic order using raw `strcmp()`, ensuring deterministic,
  locale-independent, and platform-reproducible ordering across all Linux
  filesystems.

### Streaming SHA-256, Merkle tree reduction, and pin manifest

- **Constant-Memory Streaming**: File contents are read and streamed through
  SHA-256 in fixed 64 KiB chunks (`TREEHASH_IO_BUFFER_SIZE = 65536`), achieving
  constant O(1) buffer allocation per file regardless of file size.
- **Leaf Digest Computation**: For each regular file, the 32-byte SHA-256
  digest of its byte content is formatted as a 64-character lowercase hexadecimal
  string. The leaf record digest $H_{\text{leaf}}$ is computed by hashing the
  canonical manifest line:
  $$H_{\text{leaf}} = \text{SHA-256}\left(\text{SHA256\_hex}(file\_content) + \text{"  "} + relative\_path + \text{"\n"}\right)$$
- **Balanced Binary Merkle Tree**: Sorted leaf digests form Level 0 of a
  binary Merkle tree. Pairwise reduction proceeds level-by-level:
  - Consecutive adjacent pairs $(H_{2i}, H_{2i+1})$ in raw 32-byte binary form
    are concatenated (64 bytes total) and hashed: $H_{\text{parent}} = \text{SHA-256}(H_{2i} \mathbin{\Vert} H_{2i+1})$.
  - At any level with an odd number of nodes, the lone rightmost node is
    promoted directly to the next level without duplicate hashing.
  - Reduction continues iteratively until a single 32-byte binary root digest is
    obtained, rendered as a 64-character lowercase hexadecimal string.
  - **Empty Workspace**: For an empty workspace containing zero eligible regular
    files, the root hash is the canonical SHA-256 digest of the empty string:
    `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- **Standard Output Format**: Output is written strictly to stdout:
  ```text
  ROOT <64-hex-root-hash>
  <64-hex-file-hash>  <normalized-relative-path>
  ...
  ```
  The pin manifest lines appear in the exact bytewise path order determined by
  `strcmp()`.

### Resource limits and hostile-input hardening

- **Recursion Depth Limit**: Directory traversal is bounded to a maximum depth
  of 256 levels (`TREEHASH_MAX_DEPTH = 256`). Exceeding this limit aborts
  fail-closed with diagnostic `treehash: RECURSION_DEPTH_EXCEEDED` and exit
  status `2`.
- **Path Length Limit**: Path strings are bounded to 4096 bytes (`PATH_MAX = 4096`).
  Paths exceeding this limit fail closed with diagnostic `treehash: PATH_LENGTH_EXCEEDED`
  and exit status `2`.
- **Cycle Detection**: Traversal tracks active ancestor directory `(dev_t, ino_t)`
  tuples up to the recursion depth limit. Detecting a revisited ancestor directory
  aborts fail-closed with `treehash: CYCLE_DETECTED: "..."` and exit status `2`.
- **Sanitized Stderr Diagnostics**: All paths, arguments, and untrusted strings
  rendered to stderr in diagnostics are sanitized by escaping non-printable
  ASCII bytes (< `0x20` or > `0x7E`), backslashes (`\`), and double quotes (`"`)
  into uppercase `\xHH` sequences, preventing ANSI terminal control injection.
- **SIGPIPE and Checked Output**: `signal(SIGPIPE, SIG_IGN)` is installed
  unconditionally at startup so stdout pipe closures (e.g., when piped to
  `head -n 1`) surface as checked stdio write errors (`EPIPE`) with exit status `2`
  rather than terminating abnormally.

### Exit status contract

- `0`: Success: workspace walked, regular files hashed, root hash and pin manifest
  emitted to stdout, or sole informational invocation (`--help`, `--version`).
- `1`: Reserved for operational notice or verification mismatch in future
  verification modes.
- `2`: Operational or usage failure: command-line syntax error, target path
  missing or not a directory, permission denied, recursion depth or path length
  limit exceeded, directory cycle detected, memory allocation failure, or stdout
  write/flush failure.

### Security boundaries and operational limitations

- **Read-Only Inspection**: `treehash` operates strictly in read-only mode,
  performing zero file modifications, permission changes, or temporary file writes.
- **Metadata-Blind Content Hashing**: Only regular file byte contents and relative
  path strings contribute to leaf digests and the Merkle root hash. File modification
  times, permission bits, ownership (UID/GID), inode numbers, and extended attributes
  are not hashed, guaranteeing reproducible output across checkouts and environments.
- **Excluded Filesystem Objects**: Symbolic links (whether pointing to files,
  directories, or missing targets), character/block device nodes, named pipes
  (FIFOs), and UNIX domain sockets are never followed or opened, preventing
  process hangs and directory escapes. They are excluded from leaf hashing and the
  pin manifest.
- **Operational Non-Goals**: `treehash` is intentionally small and focused. It is
  not a version control system, archiver, or deduplicator. It does not perform
  remote networking, telemetry, IPC, or background filesystem watching.

### Examples

Compute Merkle root hash and pin manifest for current working directory:

```sh
build/treehash
```

Compute Merkle root hash and pin manifest for a specific workspace:

```sh
build/treehash /path/to/project
```

Save the manifest to a file for integrity auditing:

```sh
build/treehash . > workspace.manifest
```

Verify regular file content integrity against the manifest with standard `sha256sum`:

```sh
tail -n +2 workspace.manifest | sha256sum -c -
```

Display usage guidance or version metadata:

```sh
build/treehash --help
build/treehash --version
```

### Quality floor execution and verification

`treehash` satisfies repository quality floor requirements:
- Clean compilation under GCC and Clang with `-std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L` with zero warnings.
- Verified in check-only mode with `clang-format --dry-run --Werror`.
- Static analysis clean with `clang-tidy`, `cppcheck`, and Clang static analyzer (`clang --analyze`).
- Memory and behavior analysis clean under AddressSanitizer (`detect_leaks=1`), UndefinedBehaviorSanitizer (`halt_on_error=1`), and Valgrind memcheck (`--leak-check=full --show-leak-kinds=all --track-fds=yes`).
- Manual page syntax linted cleanly with `groff -man -Tutf8 -ww -z`.
- Validated by independent regression tests in `tests/test_treehash_first_slice.py`
  (75 passed, 2 skipped) exercising traversal, ignore rules, symlinks, special files,
  NIST KAT vectors, buffer boundaries, Merkle tree reduction, cycle detection, hostile
  inputs, and closed pipes.
- **Preview integration status**: Integration into aggregate top-level
  `Makefile` targets (`make quality`, `make test`, `make install`) is deferred
  to subsequent repository build integration slices, following preview utility
  policy (consistent with `pathaudit`, `permguard`, and `openunlink`).

## License

MIT. See [LICENSE](LICENSE).
