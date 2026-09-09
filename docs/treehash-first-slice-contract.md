# Overview

This document defines the normative contract for the first release-quality vertical slice of `treehash`. `treehash` is an intentionally small, auditable, dependency-free ISO C17 command-line utility for Linux that recursively walks a requested workspace directory, respects applicable `.gitignore` exclusions, hashes regular files deterministically using SHA-256, and emits a stable Merkle-style root hash alongside a canonical SHA-256 pin manifest.

In accordance with the repository mission established in `AGENTS.md` and `product-definition.md`, `treehash` adheres strictly to the Unix philosophy: doing one job cleanly and predictably, without hidden background services, daemons, IPC, telemetry, or dependency sprawl beyond standard ISO C17 libc and POSIX.1-2008 system interfaces. The utility is engineered for autonomous workflows, hermetic build systems, supply-chain verification, and reproducibility auditing where workspace integrity and file-tree drift must be verified with mathematical certainty.

The first vertical slice implements the command-line interface `treehash [OPTIONS] [WORKSPACE_DIR]`, compiled from `src/treehash.c` into `build/treehash` via `make`. When `WORKSPACE_DIR` is omitted, `treehash` defaults to the current working directory (`.`). The execution pipeline traverses the workspace directory tree, ignores `.git/` metadata unconditionally, parses and evaluates hierarchical `.gitignore` exclusion rules, ignores symbolic links and non-regular special files, sorts regular file paths into raw bytewise lexicographic order, streams file contents through fixed-size SHA-256 hashing buffers, computes a balanced Merkle tree root hash across sorted leaves, and emits the formatted root hash and pin manifest to standard output. The informational options `--help` and `--version` report usage guidance and version metadata respectively when passed as sole arguments.

This slice also establishes and maintains complete synchronization with the repository-owned user journey manifests in `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json`. All 21 user journeys are preserved verbatim, adhering strictly to the canonical schema and ensuring every enumerated acceptance check (`AC-1`, `AC-2`, `AC-3`) is fully traceable to non-exploratory user journeys.

# Problem

Modern autonomous software engineering, containerized execution, and reproducible compilation pipelines require an infallible, auditable mechanism to verify workspace integrity and detect unauthorized state mutation. However, existing Linux tools and standard shell patterns fail to satisfy these requirements:

1. **Fragility of Ad-hoc Shell Pipelines:** Common shell workflows combining `find`, `sort`, and `sha256sum` are inherently non-deterministic across environments. Directory order emitted by `readdir()` varies by filesystem implementation and inode allocation history. Standard `sort` commands depend on host locale settings (`LC_COLLATE`), producing conflicting orderings across distributions. Furthermore, shell pipelines break when encountering filenames with whitespace, newlines, or control characters, and fail to synthesize individual file digests into a single, compact cryptographic root hash.
2. **Coupling and Opaque Internals in VCS Tooling:** While Git provides tree hashing (`git hash-object`, `git write-tree`), its hashing mechanism is tightly coupled to Git internal object storage formats, tree packing semantics, and file permission bits. Git hashing requires an initialized git repository, cannot operate as an independent verification oracle on arbitrary directories, and does not emit a transparent, standalone SHA-256 pin manifest of pure regular file content.
3. **Heavy Dependency Sprawl in Existing Alternatives:** Third-party directory-hashing utilities are frequently authored in heavy, complex runtimes (Python, Go, Rust, Node.js) that carry multi-megabyte binaries, complex dynamic link dependencies, or hidden network and telemetry behaviors. These tools are unsuitable for minimal Linux root filesystems, unprivileged container sandboxes, or security-sensitive verification harnesses that require small, auditable C code.
4. **Hostile Filesystem and Resource Vulnerabilities:** Naive filesystem traversal utilities are susceptible to denial-of-service and memory exhaustion attacks:
   - Deeply nested directory trees can trigger stack overflows during unbounded recursive traversal.
   - Circular symbolic links or bind-mount loops can trap directory walkers in infinite loops.
   - Opening named pipes (FIFOs) or character/block device nodes can block the calling process indefinitely.
   - Slurping entire files into memory causes out-of-memory crashes on large files.
   - Unsanitized path rendering to stderr can trigger terminal control sequence injection.

`treehash` resolves these challenges by providing a hardened, single-file C17 utility with bounded memory consumption, rigorous input sanitization, deterministic path normalization and sorting, hierarchical `.gitignore` filtering, and mathematically verifiable Merkle-style root hashing.

# Constraints

The first release-quality vertical slice of `treehash` is governed by the following normative technical constraints:

1. **Language Standard and Platform Interfaces:** The implementation is strictly written in ISO C17 (`-std=c17`), relying exclusively on standard C library facilities and POSIX.1-2008 filesystem interfaces (`opendir`, `readdir`, `closedir`, `lstat`, `open`, `read`, `close`). No external third-party libraries, framework dependencies, networking libraries, or non-standard kernel extensions are permitted.
2. **Command-Line Interface (CLI Surface):**
   - The operational command syntax is: `treehash [OPTIONS] [WORKSPACE_DIR]`.
   - The single positional operand `WORKSPACE_DIR` specifies the target workspace directory root. If omitted, `WORKSPACE_DIR` defaults to `.` (the current working directory).
   - Informational options: Sole-argument `--help` prints usage guidance to standard output and exits status `0`. Sole-argument `--version` prints version information (`treehash 0.1.0\n`) to standard output and exits status `0`.
   - Combining `--help` or `--version` with other options or operands is an error resulting in exit status `2`.
   - Supplying multiple directory operands, an empty string operand (`""`), or unrecognized option flags fails closed with diagnostic messages to stderr and exit status `2`.
3. **Closed Hazard Taxonomy:**
   The `treehash` utility recognizes and classifies operational hazards according to an explicitly closed taxonomy. No unclassified or ad-hoc hazard behaviors are permitted. The hazard taxonomy is closed at exactly the following members:
   - `PATH_ESCAPE`: Path operand contains relative directory traversal escapes (`..`) attempting to navigate outside the target workspace.
   - `PATH_LENGTH_EXCEEDED`: Any constructed relative or absolute filesystem path exceeds `PATH_MAX` (4096 bytes).
   - `RECURSION_DEPTH_EXCEEDED`: Traversal recursion depth exceeds `TREEHASH_MAX_DEPTH` (256 levels).
   - `CYCLE_DETECTED`: Traversal encounters a cyclic directory structure (re-encountering an active ancestor directory `(dev_t, ino_t)` tuple).
   - `UNKNOWN_OPTION`: An unrecognized option flag starting with `-` is passed on the command line.
   - `ARITY_VIOLATION`: More than one directory operand is supplied, or informational options are combined with other arguments.
   - `EMPTY_OPERAND`: An empty string (`""`) is supplied as the workspace directory operand.
   - `ACCESS_DENIED`: Target workspace root or traversed directory/file cannot be accessed due to operating system permission denial (`EACCES`).
   - `NOT_A_DIRECTORY`: The specified workspace target path exists but is not a directory.
   - `IO_ERROR`: An unrecoverable I/O read failure or directory stream reading error occurs during traversal.
   - `OUT_OF_MEMORY`: Dynamic memory allocation or reallocation fails (`calloc`/`realloc` returns NULL).
   - `BROKEN_PIPE`: Standard output write or flush fails (`EPIPE` under ignored `SIGPIPE`), or stdout reports a stream error.
   - `UNSAFE_FILE_TYPE`: Special filesystem objects (`S_ISCHR`, `S_ISBLK`, `S_ISFIFO`, `S_ISSOCK`) or symbolic links (`S_ISLNK`) are encountered; these are safely excluded from content reading and pin manifest emission without following or blocking.
4. **Workspace Traversal and Hierarchy Navigation:**
   - Traversal begins at `WORKSPACE_DIR` and recursively navigates all accessible subdirectories.
   - The `.git/` directory is excluded unconditionally at the workspace root and at any nested subdirectory level to ensure git metadata volatility does not alter the workspace hash.
   - Hierarchical `.gitignore` parsing: `treehash` discovers and evaluates `.gitignore` files located at the workspace root and within nested subdirectories using a scoped rule stack. Supported rule semantics include:
     - Blank lines and lines starting with `#` are ignored as comments.
     - Patterns with trailing slashes (`dir/`) match only directories.
     - Wildcard expressions (`*` matching zero or more characters, `?` matching a single character, and character classes `[...]`).
     - Leading slashes (`/pattern`) anchor matching to the directory level of the enclosing `.gitignore`.
     - Negation rules (`!pattern`) re-include previously excluded paths.
     - Directory pruning: when an entire directory matches an ignore pattern, traversal skips descending into that directory, preventing unnecessary I/O.
5. **Deterministic Ordering and Path Normalization:**
   - All relative file paths are normalized relative to the specified `WORKSPACE_DIR`. Redundant leading `./` prefixes are stripped, consecutive slashes (`//`) are collapsed into single slashes (`/`), and paths are canonicalized without relative directory traversal escapes (`.` or `..`). Any operand or discovered path attempting to traverse outside `WORKSPACE_DIR` is rejected fail-closed with `PATH_ESCAPE` (exit status `2`).
   - Traversal order from `readdir()` is treated as arbitrary and untrusted. Before leaf hashing and Merkle tree reduction, all discovered regular file entries are sorted in strict bytewise lexicographic order using raw byte comparison (`strcmp`), ensuring locale-independent and platform-reproducible ordering across all Linux filesystems.
6. **Symlink Safety and Special-File Policy:**
   - All filesystem inspections employ `lstat()` exclusively; `stat()` is forbidden to avoid following symbolic links.
   - Symbolic links: Symbolic links are never followed. Directory symlinks are never traversed or recursed into, preventing symlink loop vulnerabilities and workspace boundary escapes. Symbolic links are excluded from regular-file content hashing and the pin manifest.
   - Special files: Character devices (`S_ISCHR`), block devices (`S_ISBLK`), named pipes/FIFOs (`S_ISFIFO`), and UNIX domain sockets (`S_ISSOCK`) are detected via POSIX file type macros and are never opened with `open()` or read, preventing blocking I/O or device manipulation. Special files are excluded from regular-file content hashing and the pin manifest.
   - Only regular files conforming to `S_ISREG()` have their contents read and hashed.
7. **Hostile Paths, Filenames, and Resource Bounding:**
   - Arbitrary filenames: Filenames containing spaces, tabs, newlines, double quotes, backslashes, UTF-8 multibyte sequences, and arbitrary non-NUL bytes are safely processed.
   - Diagnostic sanitization: All paths, arguments, and untrusted strings rendered to standard error in diagnostics are sanitized by escaping non-printable ASCII bytes (bytes outside `0x20`–`0x7E`), backslashes (`\`), and double quotes (`"`) into uppercase `\xHH` hexadecimal sequences, eliminating ANSI terminal injection vulnerabilities.
   - Recursion depth limit: Directory traversal is bounded to a maximum depth of 256 levels (`TREEHASH_MAX_DEPTH = 256`). Exceeding this limit aborts traversal fail-closed with diagnostic `treehash: RECURSION_DEPTH_EXCEEDED` and exit status `2`.
   - Path length limit: Path strings are bounded to a maximum of 4096 bytes (`PATH_MAX`). Paths exceeding this limit are rejected fail-closed with diagnostic `treehash: PATH_LENGTH_EXCEEDED` and exit status `2`.
   - Cycle and loop detection: The walker maintains a bounded device and inode set (`st_dev`, `st_ino`) of currently visited ancestor directories to detect cyclic directory structures or bind mounts, aborting fail-closed with `treehash: CYCLE_DETECTED: "..."` and exit status `2`.
   - Streaming buffer hashing: File content hashing is performed in fixed 64 KiB streaming chunks (`TREEHASH_IO_BUFFER_SIZE = 65536`). Files of arbitrary magnitude are processed with constant O(1) memory allocation per file, preventing out-of-memory faults.
   - Memory allocation limits: Dynamic array structures for file entries and ignore rules enforce checked integer arithmetic on allocations and resizes, failing closed with `treehash: OUT_OF_MEMORY` and exit status `2` upon allocation exhaustion.
8. **Merkle Root Computation and Output Manifest Contract:**
   - Leaf digest computation: For each regular file, the 32-byte raw SHA-256 digest of its byte content is computed and formatted as a 64-character lowercase hexadecimal string (`file_hex`). The leaf record digest H_leaf is computed by hashing the canonical manifest line:
     H_leaf = SHA-256(file_hex + "  " + relative_path + "\n")
   - Binary Merkle tree reduction: The sorted leaf digests form Level 0 of a binary Merkle tree. Pairwise reduction proceeds level-by-level: adjacent pairs are concatenated in raw binary form (64 bytes) and hashed with SHA-256: H_parent = SHA-256(H_left || H_right). At any level with an odd number of nodes, the lone rightmost node is promoted directly to the next level without duplicate hashing. Reduction continues iteratively until a single 32-byte binary root digest is obtained, rendered as a 64-character lowercase hexadecimal string.
   - Empty workspace: For an empty workspace containing zero eligible regular files, the root hash is the canonical SHA-256 digest of the empty string (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
   - Standard output format: Output is written strictly to stdout:
     ```text
     ROOT <64-hex-root-hash>
     <64-hex-file-hash>  <normalized-relative-path>
     ...
     ```
     The pin manifest lines appear in the exact bytewise path order determined by `strcmp()`.
9. **Exit Status Contract:**
   - `0` (Success): Workspace walked successfully, regular files hashed, and root hash with pin manifest emitted to standard output; or sole informational option (`--help`, `--version`) executed successfully.
   - `1` (Notice / Non-fatal Finding): Reserved for operational notice or verification mismatch in future verification modes.
   - `2` (Operational / Usage Failure): Command-line syntax error, unknown option, arity violation, empty operand, path escape, path length limit exceeded, recursion depth limit exceeded, directory cycle detected, missing/non-directory target path, permission denied, I/O error, memory allocation failure, or stdout write/flush failure.
   - `SIGPIPE` is ignored unconditionally via POSIX `signal(SIGPIPE, SIG_IGN)` at process startup so stdout pipe closures surface as checked stdio write errors (`EPIPE`) with exit status `2`.
10. **Ownership and State Discipline:**
    - Memory ownership: Command-line arguments `argv` are borrowed and not modified. Heap allocations (directory entries, ignore tables, path buffers) are managed with single-owner discipline and released via a unified cleanup routine on all success and error paths.
    - File descriptor ownership: Every opened `DIR*` stream is closed with `closedir()` immediately upon directory exit; every opened file descriptor is closed with `close()` immediately upon completion of file reading.
    - Filesystem ownership: `treehash` operates as an unprivileged process, performs zero file modifications, and ignores file ownership (UID/GID), timestamps, and permission modes during content hashing, ensuring that file hashes depend exclusively on file content.
11. **User Journey Manifest Synchronization and Non-Regression Oracle:**
    - Both `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` are maintained as identical, synchronized JSON objects adhering strictly to the canonical schema.
    - All 21 repository baseline user journeys are preserved verbatim, with authorities restricted to `human`, `mission`, `author`, or `exploratory`.
    - Every non-exploratory journey traces to an enumerated acceptance check (`AC-1`, `AC-2`, or `AC-3`), with all acceptance checks covered.
    - **Treehash User Journeys Specification**: The `treehash` utility specifies dedicated user journeys covering all acceptance checks (`AC-1`, `AC-2`, `AC-3`) with command allowlist `["build/treehash"]`, verifying CLI help, version, empty workspace hash, gitignore traversal, and hostile input rejection.
    - **Repository Non-Regression Oracle Role**: In accordance with `AGENTS.md` and repository governance, the disk manifest user journeys serve as the repository-wide regression oracle guarding `sysdiff`, bubblewrap sandbox containment, and workspace abstraction against blast radius and regressions. They ensure that new utility additions like `treehash` remain additive without disturbing prior utility behavior or shared baseline contracts.
    - **Evaluator Protocol in `step_08b_user_simulation_gate`**: Evaluators must execute the allowlisted command `build/sysdiff --help` (and related allowlisted invocations), confirm exit status 0 and expected output, and report all manifest journeys with `status: "passed"` and an empty `findings: []` list. Rewriting or corrupting shared baseline journeys is strictly forbidden and constitutes oracle tampering.
12. **Explicit Non-Goals:**
    - `treehash` is NOT a version control system and does not manage branches, commits, or staging areas.
    - `treehash` does NOT perform file deduplication, archival (tar/zip), or content compression.
    - `treehash` does NOT perform remote networking, socket communication, telemetry, or cloud synchronization.
    - `treehash` does NOT run background daemons, watchers, or filesystem inotify monitors.
    - `treehash` does NOT write persistent index files or metadata databases to disk.
    - `treehash` does NOT modify, remediate, or overwrite inspected files or permissions.
    - `treehash` does NOT require or utilize elevated privileges, `sudo`, capabilities, or namespace alterations.
13. **Quality Floor:**
    - Builds cleanly with zero warnings under GCC and Clang using `-std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L`.
    - Passes static analysis with `clang-tidy`, `cppcheck`, and Clang static analyzer (`clang --analyze`).
    - Passes dynamic memory and behavior analysis under AddressSanitizer (ASan with `detect_leaks=1`), UndefinedBehaviorSanitizer (UBSan with `halt_on_error=1`), and Valgrind memcheck.
    - Adheres to repository code formatting rules verified by `clang-format --dry-run --Werror`.
    - Validated by comprehensive regression tests in `tests/test_treehash_first_slice.py`.
14. **Operational Examples:**
    - **Default Current-Directory Invocation:**
      ```sh
      treehash
      ```
      Walks the current working directory (`.`), evaluates local and nested `.gitignore` files, hashes regular files, and emits to stdout:
      ```text
      ROOT 4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a
      2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824  file1.txt
      48a24b70a0b376535542b996af517398a9b99c816115e82915c7f538837acb26  subdir/file2.txt
      ```
    - **Explicit Workspace Operand:**
      ```sh
      treehash /path/to/project
      ```
    - **Emitting Pin Manifest for Auditability:**
      ```sh
      treehash . > workspace.manifest
      ```
    - **Verifying File Contents via Standard Linux Tools:**
      ```sh
      tail -n +2 workspace.manifest | sha256sum -c -
      ```
    - **Informational Invocations:**
      ```sh
      treehash --help     # Usage guidance to stdout; exit status 0
      treehash --version  # "treehash 0.1.0\n" to stdout; exit status 0
      ```
    - **Fail-Closed Diagnostic Examples (Exit Status 2):**
      - Unknown option: `treehash --bogus` -> `treehash: unknown option '--bogus'` to stderr (status 2)
      - Relative traversal escape: `treehash ../parent` -> `treehash: PATH_ESCAPE: "../parent"` to stderr (status 2)
      - Non-directory operand: `treehash file.txt` -> `treehash: 'file.txt': Not a directory` to stderr (status 2)
      - Missing directory: `treehash /nonexistent` -> `treehash: cannot access '/nonexistent': No such file or directory` to stderr (status 2)

# Acceptance Checks

- **AC-1** — **Workspace Traversal, .gitignore Respect, Symlink/Special-File Safety, and Path Normalization:**
  The `treehash` C17 utility recursively walks the target workspace directory starting at `WORKSPACE_DIR` (defaulting to `.`), unconditionally skips `.git/` metadata directories at all hierarchy levels, discovers and applies hierarchical `.gitignore` exclusion rules (including comments, directory-only trailing slashes, wildcards, rooted patterns, and negation), safely ignores directory symlinks and non-regular special files (FIFOs, devices, sockets) without following symlinks into loops or opening blocking descriptors, and normalizes all relative paths deterministically while rejecting directory-escape attempts fail-closed with `PATH_ESCAPE` and exit status `2`.

- **AC-2** — **Deterministic SHA-256 Leaf Hashing, Pin Manifest Generation, and Balanced Merkle Tree Reduction:**
  The `treehash` utility processes regular files in strict bytewise lexicographic order (`strcmp`), streams file contents through fixed 64 KiB buffers with O(1) memory per file to compute deterministic SHA-256 digests, synthesizes leaf digests into a balanced binary Merkle tree with deterministic promotion for odd-numbered node levels, and emits the canonical `ROOT <64-hex-root-hash>` line followed by the sorted SHA-256 pin manifest (`<64-hex-file-hash>  <normalized-relative-path>`) to standard output. An empty workspace emits the canonical SHA-256 digest of the empty string.

- **AC-3** — **Hostile-Input Hardening, Closed Hazard Taxonomy, Exit Contract, Quality Floor, and Manifest Synchronization:**
  The `treehash` utility enforces strict operational resource bounds (maximum recursion depth 256, maximum path length 4096, ancestor cycle detection, checked allocation growth), handles hostile inputs fail-closed under the defined closed hazard taxonomy with sanitized stderr diagnostics (`\xHH` escaping) and deterministic exit codes (status 0 for success, status 2 for operational or usage failure), satisfies the complete repository quality floor (clean builds under GCC and Clang with `-Wall -Wextra -Wpedantic -Werror`, ASan/UBSan, Valgrind, clang-tidy, cppcheck), and synchronizes with `tests/user_journeys_manifest.json` and `journeys/user_journeys_manifest.json` preserving all 21 user journeys with complete acceptance check traceability.
