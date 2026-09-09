# `treehash` First-Slice Implementation Plan

Contract authority: [`docs/treehash-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash-first-slice-contract.md).

## Authority

[`docs/treehash-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash-first-slice-contract.md) is the sole normative authority for the first release-quality vertical slice of `treehash`. This document operationalizes that contract into concrete implementation steps, test definitions, verification gates, and risk mitigations. In accordance with [`AGENTS.md`](file:///home/lee/projects/linux-utilities-autonomous/AGENTS.md) and [`architecture.md`](file:///home/lee/projects/linux-utilities-autonomous/architecture.md), `treehash` is engineered as an intentionally small, auditable, dependency-free Linux utility in ISO C17 (`-std=c17`). It implements recursive directory traversal respecting hierarchical `.gitignore` rules, safe handling of symlinks and special files, canonical path normalization, deterministic SHA-256 regular-file content streaming, balanced binary Merkle tree root hash calculation, and sorted pin manifest emission.

All implementation, test authoring, verification, and documentation work strictly adheres to the scope and constraints set forth in the contract.

## Architecture

### 1. Portable C17 Design, Scope, and Standard Interfaces

In adherence to the Unix philosophy and the repository constraints established in [`AGENTS.md`](file:///home/lee/projects/linux-utilities-autonomous/AGENTS.md), `treehash` is kept intentionally small, focused, and auditable. The implementation resides in a single C17 translation unit: [`src/treehash.c`](file:///home/lee/projects/linux-utilities-autonomous/src/treehash.c). It is completely dependency-free, relying exclusively on standard ISO C17 library facilities and POSIX.1-2008 system interfaces (`opendir`, `readdir`, `closedir`, `lstat`, `open`, `read`, `close`). It embeds a self-contained, standard-compliant implementation of the SHA-256 cryptographic hash function (FIPS 180-4), eliminating external dependencies such as OpenSSL, libcrypto, or third-party libraries.

`treehash` does not perform background operations, run daemons, register inotify watchers, open network sockets or IPC channels, write temporary metadata files or caches to disk, or mutate file contents or permissions. It is an unprivileged, read-only inspection tool designed for autonomous environments, hermetic build systems, and reproducibility audits.

The command-line interface is strictly bounded:
```text
treehash [OPTIONS] [WORKSPACE_DIR]
```
- `WORKSPACE_DIR`: An optional single operand specifying the target workspace root directory. When omitted, it defaults to the current working directory (`.`). Supplying multiple directory operands, unexpected arguments, or unknown option flags fails closed with exit status `2`.
- Informational options: Sole-argument `--help` emits usage guidance to standard output and exits status `0`. Sole-argument `--version` emits version metadata (`treehash 0.1.0\n`) to standard output and exits status `0`.
- Combining informational options with other options or operands is a CLI syntax violation resulting in exit status `2`.

### 2. Deterministic Workspace Traversal and Gitignore Scoping

The execution pipeline starts at `WORKSPACE_DIR` and recursively navigates all accessible subdirectories using POSIX `opendir()`, `readdir()`, and `closedir()`:
1. **Unconditional `.git/` Pruning:** Any directory named `.git` is ignored unconditionally at the workspace root and at every nested subdirectory level. Traversal never descends into `.git/`, guaranteeing that internal Git metadata volatility (e.g. index locks, pack updates, reflogs) does not alter the computed workspace hash.
2. **Hierarchical `.gitignore` Discovery and Evaluation:** Traversal maintains an active stack of ignore rules. As the walker enters a directory, it checks for the presence of a `.gitignore` file within that directory. If present, it parses the file and pushes its rules onto the ignore stack, tagged with the directory depth. When the walker exits the directory, all rules associated with that depth are popped and released. Supported rule semantics include:
   - Blank lines and lines beginning with `#` are ignored as comments.
   - Trailing slashes (e.g., `build/`) constrain matching strictly to directory candidates.
   - Wildcards: `*` (matching zero or more characters except `/`), `?` (matching any single character except `/`), and bracket expressions `[...]`.
   - Anchored paths: Patterns with a leading slash (e.g., `/dist`) anchor matching to the specific directory level where the enclosing `.gitignore` file resides.
   - Negation rules: Patterns prefixed with `!` re-include previously excluded paths, allowing selective overrides.
   - Directory Pruning: When a directory matches an exclusion rule, the directory walker skips descending into it entirely, optimizing I/O and eliminating unnecessary recursion.

### 3. Symlink Safety and Special-File Policy

To safeguard against infinite recursion, boundary escapes, blocking I/O, and host side effects:
1. **Exclusive Use of `lstat()`:** All filesystem inspections use POSIX `lstat()` exclusively. The use of `stat()` is strictly forbidden throughout the codebase to ensure symbolic links are never traversed or resolved to their targets.
2. **Symbolic Links:** Evaluated via `S_ISLNK(st.st_mode)`. Symbolic links (whether pointing to files, directories, or missing targets) are never followed. Directory symlinks are never recursed into, preventing symlink loop vulnerabilities and out-of-workspace traversals. All symbolic links are excluded from regular-file content hashing and pin manifest generation.
3. **Special Files:** Character device nodes (`S_ISCHR`), block devices (`S_ISBLK`), named pipes/FIFOs (`S_ISFIFO`), and UNIX domain sockets (`S_ISSOCK`) are identified via POSIX file mode macros. They are never opened with `open()` or read, preventing process blocking or unintended device interaction. All special files are excluded from regular-file content hashing and pin manifest generation.
4. **Regular Files:** Only filesystem objects conforming to `S_ISREG(st.st_mode)` are accepted for cryptographic leaf hashing.

### 4. Canonical Path Normalization and Bytewise Lexicographic Sorting

1. **Path Normalization:** Discovered regular files have their paths normalized relative to `WORKSPACE_DIR`. The normalization pipeline strips redundant leading `./` sequences, collapses consecutive forward slashes (`//`) into a single slash (`/`), and canonicalizes path components without relative escapes (`.` or `..`). Any operand or discovered entry attempting to escape `WORKSPACE_DIR` fails closed with diagnostic `treehash: PATH_ESCAPE` and exit status `2`.
2. **Untrusted `readdir()` and Bytewise Sort:** Directory enumeration order emitted by `readdir()` is treated as untrusted and filesystem-dependent. All eligible regular file entries are accumulated into an in-memory dynamic array. Before computing leaf hashes and Merkle root reduction, the entries are sorted in strict bytewise lexicographic order using raw `strcmp()`, ensuring deterministic, locale-independent, and platform-reproducible ordering across all Linux environments.

### 5. SHA-256 Streaming, Merkle Tree Reduction, and Output Manifest

1. **Constant-Memory Streaming Hashing:** For each eligible regular file, its byte content is read and streamed through an embedded SHA-256 context in fixed 64 KiB chunks (`TREEHASH_IO_BUFFER_SIZE = 65536`). Files of any magnitude (from 0 bytes to multi-gigabyte files) are hashed with O(1) buffer allocation per file.
2. **Leaf Digest Computation:** For each sorted regular file, its 32-byte SHA-256 raw content digest is formatted as a 64-character lowercase hexadecimal string (`SHA256_hex(file_content)`). The leaf record digest $H_{\text{leaf}}$ is then computed by hashing the canonical manifest line:
   $$H_{\text{leaf}} = \text{SHA-256}\left(\text{SHA256\_hex}(file\_content) + \text{"  "} + relative\_path + \text{"\n"}\right)$$
3. **Balanced Binary Merkle Tree Reduction:** The sorted leaf digests form the initial level (Level 0) of a binary Merkle tree. Pairwise reduction proceeds level-by-level:
   - Consecutive adjacent pairs $(H_{2i}, H_{2i+1})$ in raw binary form are concatenated (64 bytes total) and hashed: $H_{\text{parent}} = \text{SHA-256}(H_{2i} \mathbin{\Vert} H_{2i+1})$.
   - At any level with an odd number of nodes, the lone rightmost node is promoted directly to the next level without duplicate hashing.
   - Reduction continues iteratively until a single 32-byte binary root digest is obtained, rendered as a 64-character lowercase hexadecimal string.
   - For an empty workspace containing zero eligible regular files, the root hash is the canonical SHA-256 digest of the empty string: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
4. **Standard Output Manifest:** Written strictly to standard output:
   ```text
   ROOT <64-hex-root-hash>
   <64-hex-file-hash>  <normalized-relative-path>
   ...
   ```
   The pin manifest lines are emitted in the exact bytewise path order determined by `strcmp()`.

### 6. Error Handling, Closed Hazard Taxonomy, and Exit Status Contract

`treehash` recognizes and classifies operational hazards according to an explicitly closed taxonomy of exactly 13 members:
1. `PATH_ESCAPE`: Path operand or entry contains relative directory traversal escapes (`..`) navigating outside the workspace.
2. `PATH_LENGTH_EXCEEDED`: Any constructed relative or absolute filesystem path exceeds `PATH_MAX` (4096 bytes).
3. `RECURSION_DEPTH_EXCEEDED`: Traversal recursion depth exceeds `TREEHASH_MAX_DEPTH` (256 levels).
4. `CYCLE_DETECTED`: Traversal encounters an active ancestor directory `(dev_t, ino_t)` tuple.
5. `UNKNOWN_OPTION`: An unrecognized option flag starting with `-` is passed on the command line.
6. `ARITY_VIOLATION`: More than one directory operand is supplied, or informational options are combined with arguments.
7. `EMPTY_OPERAND`: An empty string (`""`) is supplied as the workspace directory operand.
8. `ACCESS_DENIED`: Target workspace root or traversed directory/file cannot be accessed due to OS permission denial (`EACCES`).
9. `NOT_A_DIRECTORY`: The specified workspace target path exists but is not a directory.
10. `IO_ERROR`: An unrecoverable I/O read failure or directory stream reading error occurs during traversal.
11. `OUT_OF_MEMORY`: Dynamic memory allocation or reallocation fails (`calloc`/`realloc` returns NULL).
12. `BROKEN_PIPE`: Standard output write or flush fails (`EPIPE` under ignored `SIGPIPE`), or stdout reports an error.
13. `UNSAFE_FILE_TYPE`: Special filesystem objects or symbolic links encountered; safely excluded without following or blocking.

Deterministic exit status reduction:
- Status `0`: Clean success (workspace walked, files hashed, root hash and pin manifest emitted; or sole `--help` / `--version`).
- Status `1`: Reserved for verification notice or hash mismatch in future verification modes.
- Status `2`: Operational or usage failure (CLI syntax error, missing directory, permission denied, recursion limit exceeded, path length exceeded, cycle detected, allocation failure, or stdout write failure).

Signal handling:
- `signal(SIGPIPE, SIG_IGN)` is installed unconditionally at process startup. A broken stdout pipe surfaces as an explicit stdio write error (`EPIPE`), returning exit status `2` instead of terminating via signal.
- All standard output operations (`fputs`, `fwrite`, `fprintf`, `fflush`) have their return values checked. Write or flush failures produce exit status `2`.

### 7. Ownership Discipline and Resource Bounding

1. **Deterministic Resource Bounds:**
   - Maximum recursion depth: `TREEHASH_MAX_DEPTH = 256`. Exceeding this bound aborts traversal fail-closed with `treehash: RECURSION_DEPTH_EXCEEDED` and exit status `2`.
   - Maximum path length: `PATH_MAX = 4096`. Concatenated paths exceeding 4096 bytes fail closed with `treehash: PATH_LENGTH_EXCEEDED` and exit status `2`.
   - Ancestor directory cycle detection: Traversal tracks active ancestor directory `(dev_t, ino_t)` pairs on a fixed stack bounded by `TREEHASH_MAX_DEPTH`. Encountering an active ancestor aborts fail-closed with `treehash: CYCLE_DETECTED: "..."` and exit status `2`.
   - Streaming I/O buffer: Fixed 64 KiB buffer (`TREEHASH_IO_BUFFER_SIZE = 65536`).
2. **Allocation Ownership Discipline:**
   - Single-owner discipline: The traversal context `struct TreehashContext` owns all dynamic memory: the growable file entry array (`struct FileEntry *entries`), individual entry path strings, and the ignore rule stack (`struct IgnoreRule *rules`).
   - Checked integer arithmetic: Dynamic array reallocations check for integer multiplication and addition overflow before invoking `realloc()`. Any allocation exhaustion triggers fail-closed error handling with `treehash: OUT_OF_MEMORY` and exit status `2`.
   - Command-line arguments in `argv` are borrowed for the process lifetime; they are never modified or freed.
3. **Descriptor Ownership and Deterministic Cleanup:**
   - File descriptors and directory handles: Every opened `DIR *` stream is owned by its respective recursive call frame and closed with `closedir()` immediately upon directory exit or error return. Every regular file descriptor opened with `open(..., O_RDONLY|O_CLOEXEC)` is closed with `close()` immediately upon stream completion or read failure.
   - Unified cleanup routine: A centralized cleanup function `treehash_context_free(struct TreehashContext *ctx)` releases all dynamic memory structures (freeing all path strings, rule strings, entry arrays, and rule arrays) and resets context pointers. This cleanup is invoked on all exit paths (success, syntax error, limit exhaustion, I/O failure, and memory error).
4. **Filesystem Ownership:**
   - `treehash` operates as an unprivileged process, performs zero file modifications or temporary file writes, and ignores file ownership (UID/GID), timestamps, and permission modes during content hashing.

### 8. Hostile Input Hardening and Terminal Diagnostic Sanitization

1. **Diagnostic Sanitization:** All paths, arguments, and untrusted strings rendered to standard error in diagnostics are sanitized by escaping non-printable ASCII bytes (< `0x20` or > `0x7E`), backslashes (`\`), and double quotes (`"`) into uppercase `\xHH` hexadecimal sequences. This prevents ANSI terminal control sequence injection and terminal corruption.
2. **Arbitrary Filenames:** Filenames containing spaces, tabs, newlines, double quotes, backslashes, UTF-8 multibyte sequences, and arbitrary non-NUL bytes are processed safely.
3. **Loop Defense:** Recursive bind mounts, cyclic symlinks, and self-referential paths are intercepted before recursion via ancestor inode checking or `S_ISLNK` filtering, terminating fail-closed.

### 9. Build System Integration and Quality Gates

In accordance with [`Makefile`](file:///home/lee/projects/linux-utilities-autonomous/Makefile) design principles:
1. **Primary Executable Target:** The product binary is compiled from `src/treehash.c` into `build/treehash` via `make treehash` or default `make all`.
2. **Dedicated Platform Flags:** A dedicated Makefile variable `TREEHASH_POSIX_CFLAGS := -D_POSIX_C_SOURCE=200809L` is introduced (mirroring `PERMGUARD_POSIX_CFLAGS` and `OPENUNLINK_PLATFORM_CFLAGS`) to ensure callers overriding `CFLAGS` cannot drop the required POSIX.1-2008 platform prototypes.
3. **Source and Manpage Inventories:**
   - `TREEHASH_SRC := src/treehash.c`
   - `TREEHASH_MANPAGE := man/treehash.1`
   - Added to `ALL_SRCS` and `ALL_MANPAGES`.
4. **Dedicated Verification Targets:**
   - `treehash-test`: Compiles a temporary binary outside product paths under `/tmp/treehash-test.XXXXXX` via `mktemp -d`, installs an exit trap for cleanup, and runs [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py).
   - `treehash-sanitize`: Compiles instrumented binaries under temporary paths and runs AddressSanitizer and UndefinedBehaviorSanitizer suites.
   - `treehash-valgrind`: Compiles strict debug binary and runs Valgrind memcheck across fixture matrices.
5. **Quality Floor and Smoke Integration:**
   - Included in `make quality`, `make check`, `make format-check`, `make clang-tidy-check`, `make cppcheck-check`, `make clang-analyzer-check`, and `make man-check`.
   - Smoke script [`scripts/smoke.sh`](file:///home/lee/projects/linux-utilities-autonomous/scripts/smoke.sh) verifies basic execution and manifest formatting.

### 10. Acceptance Check Mapping Matrix

Every requirement in [`docs/treehash-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash-first-slice-contract.md) maps directly across seven concrete delivery dimensions:

| Acceptance Check | 1. Concrete C Source | 2. Independently Authored Regression Tests | 3. User Documentation | 4. Deterministic Verification | 5. Smoke Evidence | 6. User Simulation | 7. Independent Review |
|---|---|---|---|---|---|---|---|
| **AC-1:** Workspace Traversal, .gitignore Respect, Symlink/Special-File Safety, and Path Normalization | [`src/treehash.c`](file:///home/lee/projects/linux-utilities-autonomous/src/treehash.c): recursive walker (`treehash_walk_dir`), unconditional `.git/` skip, hierarchical rule stack (`parse_gitignore_file`, `match_gitignore_rule`), `lstat()`-only symlink/special-file filter, canonical path normalizer (`normalize_relative_path`). | [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py): empty/nested dirs, `.git/` exclusions, ignore comments, trailing slashes, wildcards, rooted patterns, negation, directory pruning, symlinks, FIFOs, devices, `./` stripping, path escape rejection. | [`man/treehash.1`](file:///home/lee/projects/linux-utilities-autonomous/man/treehash.1) & [`docs/treehash.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash.md): syntax, `.git/` exclusion, `.gitignore` semantics, symlink/special-file exclusion, canonical path normalization, error status `2`. | Strict GCC/Clang builds with `-Wall -Wextra -Wpedantic -Werror`, `clang-tidy`, `cppcheck`, Clang static analyzer, ASan/UBSan memory checks on path/rule allocations. | [`scripts/smoke.sh`](file:///home/lee/projects/linux-utilities-autonomous/scripts/smoke.sh) and smoke harness verify discovery of regular files, ignore filtering, and absence of `.git/` from output. | Autonomous user simulation script traversing complex test directory tree, verifying output paths match expected normalized relative paths. | Architectural review confirms zero `stat()` calls, robust `.git/` skipping, proper ignore rule scoping, no symlink recursion, and safe path normalization. |
| **AC-2:** Deterministic SHA-256 Leaf Hashing, Pin Manifest, and Balanced Merkle Tree Reduction | [`src/treehash.c`](file:///home/lee/projects/linux-utilities-autonomous/src/treehash.c): embedded SHA-256 implementation, 64 KiB buffer streaming (`hash_file_sha256`), `strcmp` entry sort, leaf digest formatting (`compute_leaf_digest`), binary Merkle tree reduction with odd promotion (`compute_merkle_root`), empty workspace digest. | [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py): NIST SHA-256 vectors, 0-byte to multi-MiB streaming, 64 KiB boundary cases, `readdir` permutation sorting, odd/even node Merkle reductions, empty workspace hash `e3b0c44...`, output formatting. | [`man/treehash.1`](file:///home/lee/projects/linux-utilities-autonomous/man/treehash.1) & [`docs/treehash.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash.md): pin manifest grammar (`ROOT <hash>` and `<hash>  <path>`), leaf digest calculation formula, binary Merkle reduction, odd promotion rule. | Python reference oracle (`hashlib.sha256`) validating identical root and leaf digests across arbitrary tree topologies. Valgrind memcheck verifying zero uninitialized reads. | Smoke test executes `treehash` on deterministic fixture directories, checking byte-exact match of `ROOT` hash and pin manifest lines. | User simulation verifies manifest against standard `sha256sum`, recomputes Merkle root independently, and confirms bitwise agreement. | Cryptographic and algorithmic review auditing SHA-256 constants, padding, big-endian byte-order handling, leaf composition, and odd-node promotion logic. |
| **AC-3:** Hostile Hardening, Exit Contract, Quality Floor, and Manifest Sync | [`src/treehash.c`](file:///home/lee/projects/linux-utilities-autonomous/src/treehash.c): `TREEHASH_MAX_DEPTH = 256`, `PATH_MAX = 4096`, ancestor `(dev, ino)` cycle check, checked allocation math, single-exit cleanup, `SIGPIPE` ignore, sanitized stderr escaping (`\xHH`), exit statuses 0/2; manifest sync logic. | [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py): depth limit (>256), path limit (>4096), cycle detection, simulated allocation failure, non-printable character escaping, closed stdout pipe (`EPIPE`), CLI syntax errors, manifest parity test. | [`man/treehash.1`](file:///home/lee/projects/linux-utilities-autonomous/man/treehash.1) & [`docs/treehash.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash.md): operational resource bounds, diagnostic format, exit codes 0/2, closed pipe behavior, non-goals, security considerations. | GCC/Clang strict builds, `make quality`, ASan with `detect_leaks=1`, UBSan with `halt_on_error=1`, Valgrind memcheck, manifest JSON schema validation. | [`scripts/smoke.sh`](file:///home/lee/projects/linux-utilities-autonomous/scripts/smoke.sh) passes cleanly; hostile and invalid CLI invocations verify expected exit status 2 and sanitized diagnostic messages. | User simulation exercises hostile inputs (control characters, cycles, deep trees, EPIPE) verifying fail-closed execution without crashes or terminal corruption. | Security and robustness review inspecting cycle detection table, checked integer arithmetic, unified cleanup on error returns, and 21 user journeys retention. |

### Concrete Implementation and Verification Work by Acceptance Check

| Check | Concrete Implementation Work in C17 | Independently Authored Test Coverage | Deterministic Verification Work |
|---|---|---|---|
| **AC-1** | Implement recursive directory traversal (`treehash_walk_dir`), unconditional `.git/` skipping, hierarchical `.gitignore` parser and rule matcher with depth-tagged scoping, `lstat()`-only symlink/special-file rejection, and path normalizer (`normalize_relative_path`). | Author tests for empty/deep trees, `.git/` exclusion at all levels, ignore comment/wildcard/root/negation/pruning rules, symlink loop immunity, non-blocking special-file handling, and path traversal escape rejection in [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py). | Execute GCC and Clang strict builds (`-Wall -Wextra -Wpedantic -Werror`), clang-tidy, cppcheck, and run pytest across parameterized filesystem fixtures verifying zero `stat()` calls and zero symlink dereferences. |
| **AC-2** | Embed self-contained standard SHA-256 implementation, implement 64 KiB buffer streaming file hasher, `strcmp` raw byte sort, leaf digest formatting, balanced binary Merkle tree reduction with lone odd promotion, and stdout pin manifest formatter. | Author NIST Known-Answer Tests, 0-byte to multi-MiB streaming tests, 64 KiB boundary cases, `readdir` permutation sorting tests, even/odd node Merkle tree reductions, and empty workspace hash tests against Python `hashlib` oracle. | Execute Python reference oracle verification, AddressSanitizer and UndefinedBehaviorSanitizer runs on Merkle tree reductions, and Valgrind memcheck to confirm zero uninitialized reads or buffer leaks. |
| **AC-3** | Enforce operational resource bounds (`TREEHASH_MAX_DEPTH = 256`, `PATH_MAX = 4096`), ancestor directory cycle detection table, checked integer multiplication on reallocations, unified context cleanup (`treehash_context_free`), `signal(SIGPIPE, SIG_IGN)`, sanitized stderr escaping (`\xHH`), exit status reducer (0/2), and preserve user journey manifests. | Author hostile path tests (spaces, quotes, newlines, control codes), depth limit overflow (>256), path limit overflow (>4096), cycle detection tests, closed stdout pipe (`EPIPE`) test, CLI syntax/arity tests, and manifest parity assertion for 21 user journeys. | Execute `make quality`, `./scripts/smoke.sh`, Valgrind leak checking, Clang static analyzer, schema validation on [`tests/user_journeys_manifest.json`](file:///home/lee/projects/linux-utilities-autonomous/tests/user_journeys_manifest.json) and [`journeys/user_journeys_manifest.json`](file:///home/lee/projects/linux-utilities-autonomous/journeys/user_journeys_manifest.json), and git status cleanliness check. |

## Tests

### Pytest Harness and Temporary Binary Compilation Outside Product Paths

To maintain repository hygiene, avoid workspace mutation, and prevent interference with existing product binaries in `build/`, the test suite strictly compiles all temporary binaries outside product paths:
1. **Isolated Compilation in Temporary Directories:** The pytest harness in [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py) uses pytest's `tmp_path` or `tempfile.mkdtemp(prefix="treehash-test-")` located under `/tmp`.
2. **Strict Compiler Invocation:** The test runner resolves the C compiler via `$CC` (defaulting to `cc` or `gcc`) and executes:
   ```bash
   $CC -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -O2 -o /tmp/.../treehash_test_bin src/treehash.c
   ```
   No binary is emitted to `build/treehash` or the workspace root during test execution. Missing source fails closed immediately with `pytest.fail()`.
3. **Sealed Test Environment:** Child processes running the compiled temporary binary execute within a sealed environment: `LC_ALL=C`, `LANG=C`, and `PYTHONDONTWRITEBYTECODE=1`. Ambient environment variables that could alter process behavior are stripped.
4. **Automatic Teardown and Cleanup:** All temporary directories, test filesystems, and temporary binaries are registered with pytest fixture teardown routines and removed immediately upon test completion.
5. **Makefile Phony Targets:** Additive Makefile targets (`treehash-test`, `treehash-sanitize`, `treehash-valgrind`) create a unique temporary directory via `mktemp -d /tmp/treehash-test.XXXXXX`, install an `EXIT`/`HUP`/`INT`/`TERM` shell trap to ensure directory removal, compile the temporary binary there, run pytest/sanitizers/Valgrind against that temporary binary, and clean up automatically.

### Automated Regression Test Suites

The test suite in [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py) organizes coverage into three exhaustive test families corresponding to the acceptance checks:

#### 1. Traversal, Gitignore, and Path Normalization Suite (AC-1)
- **Empty and Minimal Workspaces:** Verifies traversal on an empty directory and single-file directories.
- **Hierarchical Directory Navigation:** Deeply nested subdirectories with mixed regular files, validating full recursive discovery.
- **Unconditional `.git/` Rejection:** Workspaces with `.git/` directories at root level and nested within subdirectories; confirms `.git/` is never traversed and no `.git/` paths appear in the manifest.
- **Hierarchical `.gitignore` Rules:**
  - Comments (`#`) and empty lines ignored.
  - Trailing slash directory rules (e.g. `build/`) matching only directories and pruning traversal.
  - Wildcards: `*.o`, `cache?`, `temp[0-9]`.
  - Rooted rules: `/root_only.txt` matching only at the `.gitignore` level, not in subdirectories.
  - Negation rules: `*.log` with `!important.log` correctly re-including `important.log`.
  - Multi-level ignore inheritance: parent `.gitignore` rules applied to subdirectories unless overridden.
- **Symlink Non-Traversing Safety:**
  - Symlinks to regular files, directories, and missing paths.
  - Circular symlink loops (`link -> .` or `link_a -> link_b -> link_a`).
  - Confirms `lstat()` is used, no symlinks are recursed, and no symlink paths appear in output.
- **Special-File Safety:**
  - FIFOs created with `mkfifo`, UNIX domain sockets, and character/block device fixtures.
  - Confirms special files are never opened, avoiding blocking I/O, and are omitted from manifest.
- **Path Normalization and Escape Defense:**
  - Redundant `./` and `//` sequences properly normalized.
  - Traversal escapes (`../outside`) rejected fail-closed with diagnostic `treehash: PATH_ESCAPE` and status `2`.

#### 2. Deterministic Hashing and Merkle Root Suite (AC-2)
- **SHA-256 Known-Answer Tests (KAT):** Verifies the embedded SHA-256 implementation against NIST standard test vectors (empty string, "abc", multi-block strings).
- **Streaming Buffer Boundaries:**
  - 0-byte regular files (hash: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
  - Exactly 65,535 bytes, 65,536 bytes (`TREEHASH_IO_BUFFER_SIZE`), and 65,537 bytes.
  - Multi-megabyte files (1 MiB, 10 MiB) verifying constant memory buffer streaming.
- **Bytewise Lexicographic Sort Ordering:**
  - Workspace with files whose natural `readdir()` order differs from `strcmp()` order.
  - Unicode/high-byte path comparisons verifying raw unsigned byte `strcmp()` behavior.
- **Leaf Digest Synthesis:**
  - Verifies exact leaf digest calculation $H_{\text{leaf}} = \text{SHA-256}(\text{SHA256\_hex} + \text{"  "} + \text{path} + \text{"\n"})$.
- **Merkle Tree Reduction Logic:**
  - 0 files: Canonical empty workspace hash `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  - 1 file: Root hash equals the single leaf digest $H_{\text{leaf}}$.
  - Even file counts (2, 4, 8): Pairwise binary reduction verified against Python reference implementation.
  - Odd file counts (3, 5, 7): Lone rightmost node promotion verified against reference implementation.
- **Manifest Formatting:**
  - Exact `ROOT <64-hex>` line followed by `<64-hex>  <path>` lines.

#### 3. Hardening, Resource Limits, and Exit Contract Suite (AC-3)
- **CLI Options and Syntax:**
  - `--help` and `--version` as sole arguments returning status `0`.
  - Unknown options (e.g. `--invalid`) and extra operands returning status `2`.
  - Target path does not exist or is not a directory returning status `2`.
  - Target directory root without read/execute permissions returning status `2`.
- **Recursion Depth Limit:**
  - Fixture directory hierarchy nested to 257 levels; asserts exit status `2` with stderr containing `treehash: RECURSION_DEPTH_EXCEEDED`.
- **Path Length Limit:**
  - Path exceeding 4096 bytes; asserts exit status `2` with stderr containing `treehash: PATH_LENGTH_EXCEEDED`.
- **Directory Cycle Detection:**
  - Recursive directory bind mount or loop; asserts exit status `2` with stderr containing `treehash: CYCLE_DETECTED`.
- **Sanitized Diagnostics:**
  - Filenames containing spaces, quotes (`"`), backslashes (`\`), newlines (`\n`), tabs (`\t`), terminal escape codes (`\x1b[31m`), and non-ASCII bytes; asserts that stderr diagnostics escape hostile bytes to `\xHH` format.
- **SIGPIPE and Closed Stdout:**
  - Invoking `treehash` piped to a consumer that closes immediately (e.g. `head -n 1`); asserts exit status `2` via checked stdio write failure without abnormal termination.
- **Manifest Synchronization:**
  - Verifies that [`tests/user_journeys_manifest.json`](file:///home/lee/projects/linux-utilities-autonomous/tests/user_journeys_manifest.json) and [`journeys/user_journeys_manifest.json`](file:///home/lee/projects/linux-utilities-autonomous/journeys/user_journeys_manifest.json) exist, parse cleanly, are byte-for-byte identical, and retain all 21 user journeys with complete acceptance check traceability.

## Verification

### Deterministic Verification Gates

Verification is evidence-producing work executed systematically. Every gate must be executed, with commands, exit codes, and test counts recorded:

1. **Strict Compiler Builds:**
   Compile `src/treehash.c` with zero warnings or errors using both GCC and Clang:
   ```bash
   gcc -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -O2 -o /tmp/treehash-gcc src/treehash.c
   clang -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -O2 -o /tmp/treehash-clang src/treehash.c
   ```
2. **Static Analysis Suite:**
   - Code formatting: `clang-format --dry-run --Werror src/treehash.c`
   - Static linter: `clang-tidy src/treehash.c -- -std=c17 -D_POSIX_C_SOURCE=200809L`
   - Cppcheck: `cppcheck --enable=warning,style,performance,portability --error-exitcode=1 --std=c17 -D_POSIX_C_SOURCE=200809L src/treehash.c`
   - Clang Analyzer: `clang --analyze -Xanalyzer -analyzer-output=text -Werror -std=c17 -D_POSIX_C_SOURCE=200809L src/treehash.c`
3. **Dynamic Memory and Behavior Analysis:**
   - AddressSanitizer (ASan) with leak detection:
     ```bash
     clang -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -fsanitize=address -fno-omit-frame-pointer -g -O1 -o /tmp/treehash-asan src/treehash.c
     ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 python3 -m pytest -p no:cacheprovider tests/test_treehash_first_slice.py
     ```
   - UndefinedBehaviorSanitizer (UBSan):
     ```bash
     clang -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -fsanitize=undefined -fno-omit-frame-pointer -g -O1 -o /tmp/treehash-ubsan src/treehash.c
     UBSAN_OPTIONS=halt_on_error=1 python3 -m pytest -p no:cacheprovider tests/test_treehash_first_slice.py
     ```
   - Valgrind Memcheck:
     ```bash
     gcc -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -g -O1 -o /tmp/treehash-valgrind src/treehash.c
     valgrind --leak-check=full --show-leak-kinds=all --track-fds=yes --error-exitcode=1 /tmp/treehash-valgrind <fixture_dir>
     ```
4. **Focused Test Execution:**
   Execute the dedicated pytest module with bytecode and cache generation disabled:
   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_treehash_first_slice.py -v
   ```
5. **Full Quality Floor and Smoke Suite:**
   Run the repository's aggregate quality and smoke targets to ensure zero regressions across existing utilities (`sysdiff`, `pathaudit`, `permguard`, `openunlink`):
   ```bash
   make clean && make quality
   ./scripts/smoke.sh
   ```
6. **Workspace Cleanliness Audit:**
   Verify no untracked binaries, caches, or test remnants remain:
   ```bash
   git status --short
   git diff --check
   ```

### User Simulation and Smoke Evidence

1. **Smoke Evidence Capture:**
   Dedicated smoke verification executes `treehash` against representative fixtures:
   - Clean workspace with regular files: asserts exit code `0`, verifies `ROOT <hash>` line, verifies pin manifest.
   - Workspace with `.git/` and `.gitignore`: asserts ignored files and git metadata are absent.
   - Hostile input / nonexistent path: asserts exit code `2` with sanitized stderr.
   All stdout, stderr, and exit codes are recorded as verifiable evidence.
2. **End-to-End User Simulation:**
   A standalone user simulation script models an operator verifying workspace integrity in a CI/CD pipeline:
   - Steps:
     1. Operator checks out a repository.
     2. Runs `treehash` to compute initial state root hash and saves manifest: `treehash . > initial.manifest`.
     3. Operator makes modifications to an ignored file (e.g. `build/temp.o`) and re-runs `treehash`: asserts root hash is identical.
     4. Operator modifies a tracked source file and re-runs `treehash`: asserts root hash differs.
     5. Operator inspects diff between manifests to identify exact file drift.
   - Confirms that `treehash` satisfies real-world operator requirements cleanly without unexpected side effects.

### Independent Review

Independent review verifies the implementation against [`docs/treehash-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/treehash-first-slice-contract.md):
1. **Contract Traceability:** Validates that every AC-1, AC-2, and AC-3 criterion is fully realized in `src/treehash.c` and tested in [`tests/test_treehash_first_slice.py`](file:///home/lee/projects/linux-utilities-autonomous/tests/test_treehash_first_slice.py).
2. **Cryptographic Integrity:** Verifies SHA-256 implementation, byte ordering, leaf formatting, Merkle tree reduction, odd-node promotion, and empty-workspace handling.
3. **Memory Safety & Resource Audit:** Confirms checked allocation math, single-owner context cleanup, bounded recursion (`TREEHASH_MAX_DEPTH`), bounded paths (`PATH_MAX`), and closed file descriptors.
4. **API Surface Audit:** Verifies zero calls to forbidden functions (`stat`, `system`, `popen`, sockets, threads, fork/exec).
5. **Clean Quality Verdict:** Requires passing verdicts across all quality gates with zero unresolved High or Critical findings.

## Risks

### 1. Unbounded Recursion and Stack Exhaustion
- **Risk:** Traversing deeply nested directory structures can cause stack overflow in recursive functions.
- **Mitigation:** Traversal depth is strictly tracked in the traversal context. If the current depth reaches `TREEHASH_MAX_DEPTH = 256`, traversal terminates immediately fail-closed with diagnostic `treehash: RECURSION_DEPTH_EXCEEDED` and exit status `2`.

### 2. Filesystem Cycles and Symlink Loops
- **Risk:** Circular directory symlinks or directory bind mounts can trap traversal in infinite loops, exhausting memory and CPU.
- **Mitigation:**
  - Symlinks are never traversed; `lstat()` is used exclusively and symlink directory entries are skipped.
  - Traversal maintains an ancestor directory set of `(dev_t, ino_t)` tuples. Before entering any directory, the device and inode numbers from `lstat()` are compared against all ancestors. If a match is detected, traversal aborts fail-closed with `treehash: CYCLE_DETECTED: "..."` and exit status `2`.

### 3. Path Buffer Overflows and Truncation
- **Risk:** Concatenating deeply nested directory and file names can exceed fixed-size path buffers, risking buffer overflows or silent truncation.
- **Mitigation:** All path concatenations enforce strict length bounds against `PATH_MAX = 4096`. If a concatenated path would exceed 4096 bytes (including null terminator), the operation fails closed with `treehash: PATH_LENGTH_EXCEEDED` and exit status `2`. No path is ever silently truncated.

### 4. Memory Exhaustion on Massive Workspaces
- **Risk:** Workspaces with hundreds of thousands of files could exhaust system memory when buffering entries or reading file contents.
- **Mitigation:**
  - File contents are hashed using a fixed 64 KiB buffer (`TREEHASH_IO_BUFFER_SIZE = 65536`), guaranteeing O(1) memory per file regardless of file size.
  - Dynamic array allocations for file entries and ignore rules use checked integer multiplication and addition. Allocation failures trigger fail-closed cleanup via `treehash_context_free` and exit status `2` with `treehash: OUT_OF_MEMORY`.

### 5. Blocking I/O and Process Hangs on Special Files
- **Risk:** Opening named pipes (FIFOs), UNIX domain sockets, or character/block devices can block process execution indefinitely.
- **Mitigation:** Prior to opening any file, `lstat()` checks the file type using `S_ISREG()`. Any non-regular file (FIFOs, sockets, character/block devices) is skipped without opening a file descriptor.

### 6. Terminal Control Sequence Injection via Stderr
- **Risk:** Hostile workspaces containing filenames with ANSI escape sequences or control characters could corrupt operator terminals or execute injected control codes when errors are printed.
- **Mitigation:** All diagnostic strings emitted to standard error pass through a diagnostic sanitizer that escapes non-printable ASCII bytes (< `0x20` or > `0x7E`), double quotes (`"`), and backslashes (`\`) into uppercase `\xHH` hexadecimal escape sequences.

### 7. Endianness and Architecture Hashing Variations
- **Risk:** Differences in CPU endianness (little-endian vs. big-endian) could cause SHA-256 digests or Merkle tree reduction to produce differing root hashes across architectures.
- **Mitigation:** The embedded SHA-256 implementation explicitly handles big-endian byte-swapping for length padding and word conversions. Merkle tree concatenation combines raw 32-byte binary digests directly. Tests assert bit-exact matches against standard NIST test vectors and Python `hashlib.sha256`.

### 8. SIGPIPE Termination on Broken Stdout Pipes
- **Risk:** When `treehash` output is piped to tools like `head` that close the pipe early, the default `SIGPIPE` signal terminates the process abruptly without proper cleanup.
- **Mitigation:** `signal(SIGPIPE, SIG_IGN)` is configured at startup. Output functions check stdio return codes; write errors produce a controlled exit status `2` and trigger full context cleanup.

### 9. Locale-Dependent Path Sorting Divergence
- **Risk:** Systems configured with differing locale settings (`LC_COLLATE`) could sort file paths differently if using standard collation functions, breaking cross-platform hash determinism.
- **Mitigation:** Entry paths are sorted strictly using raw byte comparison via `strcmp()`, guaranteeing identical lexicographic ordering across all operating systems, distributions, and locale configurations.

### 10. Git Metadata Volatility
- **Risk:** Internal `.git/` repository files (commit logs, index locks, loose objects) mutate frequently during standard developer activities, causing root hash instability if included.
- **Mitigation:** Any directory named `.git` is skipped unconditionally during directory traversal at the workspace root and at all subdirectory levels, isolating the workspace hash from Git version control state.
