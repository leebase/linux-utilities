# Overview

This document establishes the authoritative contract for the first vertical slice of `snslice`. `snslice` is an intentionally small, auditable, dependency-free ISO C17 command-line utility for Linux systems that partitions structured streaming datasets—specifically Newline-Delimited JSON (NDJSON) and Comma-Separated Values (CSV)—into bounded, deterministically named chunk files on complete record boundaries without retaining the entire input or individual chunks in memory.

In accordance with the repository mission established in `AGENTS.md`, `product-definition.md`, and `architecture.md`, `snslice` adheres strictly to the Unix philosophy: doing one job cleanly, predictably, and auditably, without hidden background services, daemons, IPC, telemetry, networking, or dynamic runtime dependencies beyond standard ISO C17 libc and POSIX.1-2008 system interfaces (`read`, `write`, `open`, `close`, `stat`, `lstat`, `unlink`). The utility is engineered for automated pipelines, containerized execution, data engineering workflows, and resource-constrained environments where gigabyte- or terabyte-scale structured streams must be sliced into manageable files while strictly preserving record integrity and RFC 4180 compliance.

The first vertical slice provides the command-line interface `snslice [OPTIONS] [INPUT_FILE]`, compiled from `src/snslice.c` into `build/snslice` (and `tmp/snslice` during validation) via `make`. When `INPUT_FILE` is omitted or provided as `-`, `snslice` streams from standard input (`stdin`). The execution pipeline reads input in fixed 64 KiB streaming chunks (`SNSLICE_IO_BUFFER_SIZE = 65536`), passes bytes through a deterministic streaming finite state machine that identifies true record boundaries, tracks cumulative metrics per chunk against configurable byte limits (`--bytes`) or record count limits (`--records`), and emits sequential, zero-padded chunk files (`<prefix>%05zu.<ext>`) into a specified output directory (`--out-dir`).

Critically, `snslice` guarantees that no record is ever split across chunk boundaries. For NDJSON, record boundaries match logical line delimiters. For CSV, the utility tracks double-quoted fields per RFC 4180: newlines embedded within quotes are treated as literal field data rather than record delimiters, guaranteeing that multiline CSV records remain contiguous within a single chunk file. The utility maintains an O(1) resident memory footprint regardless of total stream volume. To maintain strict scope discipline and auditability, this initial slice intentionally omits compression formats (such as gzip or zstd) and cloud staging/Snowflake integrations, delegating stream transformations to standard external Unix pipelines.

This slice also establishes and maintains complete synchronization with the repository-owned user journey manifest in `journeys/user_journeys_manifest.json`. All 18 user journeys adhere strictly to the canonical schema defined in `agent_orch.user_journeys.USER_JOURNEYS_MANIFEST_SCHEMA` and ensure every enumerated acceptance check (`AC-1` through `AC-13`) is fully traceable to non-exploratory user journeys.

# Problem

Modern autonomous engineering workflows, distributed data processing systems, and machine learning data loaders routinely ingest massive structured datasets formatted as NDJSON logs or CSV dumps. These datasets frequently exceed available host memory or the maximum payload limits of downstream services and language models. However, standard Linux command-line tools and scripting language interpreters exhibit severe failure modes when applied to this task:

1. **Destructive Severing of Records by Standard `split`:**
   The standard coreutils `split` utility provides `-b` (byte-based) and `-l` (line-based) splitting. Slicing by byte count blindly bisects JSON objects and CSV rows. Slicing by line count splits on raw newline (`\n`) bytes; while this suffices for flat text, it completely corrupts RFC 4180 CSV files where fields enclose newlines within balanced quotes (e.g. multiline address fields, log stack traces, embedded markdown). The severed lines produce unparseable fragments in two separate files, corrupting data pipelines.
2. **Unbounded Memory Consumption in General-Purpose Tools:**
   Standard data processing tools such as `jq`, `pandas`, or ad-hoc Node.js/Python scripts construct complete abstract syntax trees (ASTs) or in-memory tables. Processing a 50 GB dataset using such tools requires tens of gigabytes of RAM, triggering Linux out-of-memory (OOM) killer terminations in containerized or resource-bounded environments.
3. **Absence of Atomic Chunking and Overwrite Hazards:**
   Ad-hoc shell scripts frequently overwrite pre-existing files without collision checks, leak file descriptors on errors, leave corrupted partial chunks on disk when storage is exhausted, and fail silently or report non-deterministic exit statuses.
4. **Hostile Paths, Unsafe Paths, and Terminal Injection:**
   When reading malformed or hostile input containing non-printable ASCII control characters or terminal escape sequences, naive utilities dump raw bytes to `stderr`, exposing operators and terminal emulators to escape-injection vulnerabilities. Furthermore, unvalidated output file prefixes or unsafe paths can lead to directory traversal attacks and unintended filesystem writes.

`snslice` resolves these deficiencies by delivering a hardened, single-file C17 utility with bounded streaming memory, stateful RFC 4180 multiline CSV boundary detection, atomic chunk creation, clean transactional error recovery, sanitized diagnostics, and an explicitly closed hazard taxonomy.

# Constraints

The first release-quality vertical slice of `snslice` is governed by the following normative technical constraints:

1. **Language Standard and Platform Interfaces:**
   The implementation is strictly written in ISO C17 (`-std=c17`), relying exclusively on standard C library facilities and POSIX.1-2008 system interfaces (`read`, `write`, `open`, `close`, `stat`, `lstat`, `unlink`). Feature-test macros `_POSIX_C_SOURCE=200809L` and `_FILE_OFFSET_BITS=64` are required across all compilation routes. No external third-party libraries, JSON parser frameworks, CSV libraries, networking libraries, or non-standard kernel extensions are permitted.

2. **Command-Line Interface (CLI Surface):**
   - Operational syntax: `snslice [OPTIONS] [INPUT_FILE]`
   - Positional operand: `INPUT_FILE` specifies the input file path. If omitted or passed as `-`, `snslice` reads from standard input (`stdin`). Supplying more than one positional argument is an arity violation resulting in exit status `2`.
   - Option terminator: `--` terminates option processing; any subsequent argument is treated as `INPUT_FILE`.
   - Format specification:
     - `--format <ndjson|csv>` or `-f <ndjson|csv>`: Sets the parsing mode. Valid values are strictly `ndjson` or `csv`. If omitted, `--format` defaults to `ndjson`. Any other value triggers `INVALID_FORMAT` and exit status `2`.
   - Chunk sizing thresholds (at least one threshold must be specified):
     - `--bytes <BYTES>` or `-b <BYTES>`: Specifies the chunk size limit in bytes as a positive integer in `1..SIZE_MAX`.
     - `--records <COUNT>` or `-r <COUNT>`: Specifies the chunk record count limit as a positive integer in `1..SIZE_MAX`.
     - If both `--bytes` and `--records` are specified, a chunk boundary is triggered as soon as either limit is reached or exceeded on a complete record boundary.
     - Omitting both `--bytes` and `--records` is a usage error resulting in exit status `2`.
   - Output destination and naming:
     - `--out-dir <DIR>` or `-d <DIR>`: Directory where output chunks are created. Defaults to `.` (current working directory). If the directory does not exist, is not a directory, or lacks write/search permissions, `snslice` fails closed with `OUTPUT_DIR_ERROR` and exit status `2`.
     - `--prefix <PREFIX>` or `-p <PREFIX>`: Chunk filename prefix. Defaults to `chunk_`. The prefix must not contain path separators (`/`) or directory traversal tokens (`..`); violations fail closed with `USAGE_ERROR` and exit status `2`.
     - Chunk naming format: `<out-dir>/<prefix>%05zu.<ext>`, where `%05zu` is a 1-indexed, five-digit zero-padded decimal counter (`00001`, `00002`, ...), and `<ext>` is `ndjson` for NDJSON and `csv` for CSV.
   - Informational options:
     - Sole-argument `--help`: Emits usage guidance to stdout, leaves stderr empty, and exits status `0`.
     - Sole-argument `--version`: Emits `snslice 0.1.0\n` to stdout, leaves stderr empty, and exits status `0`.
     - Combining `--help` or `--version` with any other option or operand is a usage error resulting in exit status `2`.

3. **Ownership and Streaming Model:**
   - **Memory Ownership:** `argv` string pointers are borrowed from the runtime and never modified or freed. Internal heap allocations (path buffers, diagnostic error formatting) follow single-owner discipline and are released on all success and error return paths via a unified cleanup procedure.
   - **Bounded Streaming Model:** Input is streamed through a fixed-size buffer of 64 KiB (`SNSLICE_IO_BUFFER_SIZE = 65536`). Files and streams of arbitrary length (e.g. 100 GB) are processed without loading the entire input or whole chunks into memory. The resident memory footprint is constant O(1).
   - **File Descriptor Ownership:** At most two descriptors are open concurrently: the input stream descriptor and exactly one active output chunk descriptor. When a chunk is finished, its descriptor is flushed and closed before the next chunk is opened.
   - **Filesystem State Ownership:** Each chunk file is created atomically using `open(path, O_CREAT | O_EXCL | O_WRONLY, 0644)`. If an intended chunk file already exists, `snslice` immediately aborts fail-closed with `OUTPUT_COLLISION` and exit status `2`, preventing silent overwrites. On fatal operational errors during chunk generation (e.g. disk space exhausted `ENOSPC`, read error, malformed input), the active partial chunk file is closed and unlinked (`unlink()`) before process exit, while previously completed chunks remain preserved.

4. **Format Parsing and Record Preservation:**
   - **NDJSON Record Boundaries:**
     - A record is a single line terminated by LF (`\n`) or CRLF (`\r\n`).
     - Record boundaries occur strictly upon encountering the `\n` delimiter.
     - Chunk splitting occurs immediately after the terminating `\n`.
     - Blank lines (empty lines containing only newline characters) are valid NDJSON lines and are preserved without modification.
   - **CSV Quoted Record Boundaries (RFC 4180):**
     - Fields may be enclosed in double quotes (`"`).
     - The state machine tracks whether parsing is currently inside or outside quotes.
     - Inside quotes, literal newlines (`\n` and `\r\n`) and commas (`,`) do not signify record or field delimiters.
     - An escaped double quote is represented by two consecutive double quotes (`""`).
     - A record boundary is recognized if and only if an unquoted LF (`\n`) or CRLF (`\r\n`) is encountered outside quoted fields.
     - A chunk boundary is cut exclusively at a complete record boundary.
   - **Empty Input Handling:**
     - If the input stream contains 0 bytes (empty file or empty stdin), `snslice` exits cleanly with status `0`, writes zero chunk files to disk, and produces empty stdout and stderr.

5. **Closed Hazard Taxonomy:**
   The `snslice` utility classifies all operational and usage failures into an explicitly closed taxonomy. No ad-hoc, unclassified error conditions exist:
   - `USAGE_ERROR`: Invalid command-line syntax, arity violation, missing threshold options, prefix containing directory separators, or combining informational options with arguments.
   - `UNKNOWN_OPTION`: Unrecognized option flag starting with `-`.
   - `INVALID_LIMIT`: `--bytes` or `--records` argument is non-numeric, <= 0, or exceeds integer/size limits.
   - `INVALID_FORMAT`: `--format` argument is neither `ndjson` nor `csv`.
   - `INPUT_NOT_FOUND`: Input file operand does not exist or cannot be accessed (`ENOENT`, `EACCES`).
   - `INPUT_IS_DIRECTORY`: Input file operand references a directory (`EISDIR`).
   - `INPUT_READ_ERROR`: Operating system I/O read failure on input stream (`EIO`).
   - `RECORD_LENGTH_LIMIT`: A single record exceeds maximum allowed length (`SNSLICE_MAX_RECORD_BYTES = 16777216`, 16 MiB) without encountering a record boundary.
   - `MALFORMED_NDJSON`: Unterminated line at end-of-file without trailing newline, or presence of an embedded NUL byte.
   - `MALFORMED_CSV`: Unterminated quoted field reaching end-of-file while still in quoted state, or embedded NUL byte.
   - `OUTPUT_DIR_ERROR`: Output directory does not exist, is not a directory, or lacks write/execute permissions.
   - `OUTPUT_COLLISION`: Output chunk file already exists (preventing overwrite under `O_EXCL`).
   - `CHUNK_OPEN_ERROR`: Operating system failure when creating a chunk file (other than `EEXIST`).
   - `CHUNK_WRITE_ERROR`: Write failure or flush failure when emitting bytes to chunk file (e.g. `ENOSPC`, disk full).
   - `OUT_OF_MEMORY`: Dynamic memory allocation or reallocation failure (`calloc`/`malloc` returns NULL).
   - `BROKEN_PIPE`: Output stream pipe closed prematurely (`EPIPE` under ignored `SIGPIPE`).

6. **Exit Statuses:**
   - `0` (Success): Input stream completely consumed, all complete records partitioned into valid chunk files, and all chunk files cleanly flushed and closed; or sole informational option (`--help`, `--version`) executed.
   - `1` (Notice / Data Hazard): Reserved for non-fatal findings or advisory modes in future extensions.
   - `2` (Operational / Usage Failure): Any usage error, CLI violation, malformed input syntax, limit violation, file collision, I/O error, write failure, or memory exhaustion.
   - POSIX `SIGPIPE` is ignored unconditionally at startup via `signal(SIGPIPE, SIG_IGN)` so pipe closures surface as checked `EPIPE` failures with status `2` (`BROKEN_PIPE`) rather than uncontrolled process termination.

7. **Security Constraints, Unsafe Paths, and Diagnostic Sanitization:**
   - **Unsafe Paths and Directory Traversal Protection:** `--prefix` must not contain `/` or `..`. Output chunk paths are strictly constructed within `--out-dir`. Unsafe paths attempting directory traversal or unauthorized filesystem manipulation are rejected fail-closed with `USAGE_ERROR` or `OUTPUT_DIR_ERROR`.
   - **Permission Hardening:** Chunk files are created with mode `0644` using `O_CREAT | O_EXCL | O_WRONLY`.
   - **Diagnostic Sanitization:** All untrusted paths, filenames, or input byte sequences rendered in `stderr` diagnostics are sanitized by escaping non-printable ASCII bytes (outside `0x20`–`0x7E`), double quotes (`"`), and backslashes (`\`) into uppercase `\xHH` hexadecimal sequences, eliminating ANSI escape sequence injection.
   - **Bounded Memory:** Memory consumption is constant O(1) with respect to input file size; input is never loaded entirely into memory.
   - **Privilege Discipline:** Operates with standard unprivileged user permissions; requires no capabilities or elevated rights.

8. **Risks and Mitigations:**
   - **Risk 1: Massive single records exhausting memory.** If a malformed stream lacks newlines or closing quotes, a naive parser might buffer indefinitely.
     *Mitigation:* Enforce `SNSLICE_MAX_RECORD_BYTES = 16777216` (16 MiB). If a record exceeds this bound without finding a record boundary, fail closed immediately with `RECORD_LENGTH_LIMIT` and exit status `2`.
   - **Risk 2: Hostile path traversal, unsafe paths, and output overwrite.** Malicious `--prefix` or `--out-dir` inputs could use unsafe paths to escape directory boundaries or overwrite system files.
     *Mitigation:* Validate that `--prefix` contains zero path separators (`/`) and no traversal tokens (`..`). Use `open()` with `O_CREAT | O_EXCL` so existing files trigger `OUTPUT_COLLISION` without truncation.
   - **Risk 3: Filesystem exhaustion (ENOSPC) leaving corrupt partial files.** Slicing large files may fill disk partitions, leaving unusable broken chunk files.
     *Mitigation:* Check all `write()` return codes. Upon any write error, immediately close and `unlink()` the active incomplete chunk file before exiting status `2`, leaving completed prior chunks intact.
   - **Risk 4: RFC 4180 multiline CSV edge cases.** Embedded newlines, commas, and escaped quotes (`""`) inside quotes can confuse simple parsers into splitting records across chunks.
     *Mitigation:* Maintain an explicit quote-state finite automaton. Treat newlines and commas inside quotes strictly as literal data, advancing chunk boundaries only at unquoted newlines.
   - **Risk 5: Premature pipe closure and process abort.** Downstream utilities closing reading pipes can cause default `SIGPIPE` process kills without cleanup.
     *Mitigation:* Set `signal(SIGPIPE, SIG_IGN)` at startup and handle `EPIPE` through standard transactional error cleanup.
   - **Risk 6: Terminal and log injection via hostile input.** Malformed inputs containing ANSI escape codes can manipulate terminal displays or corrupt audit logs.
     *Mitigation:* All error diagnostics sanitize path, filename, and input text by escaping bytes outside `0x20`–`0x7E` into `\xHH` hexadecimal representations.

9. **Test Strategy:**
   - **Unit and Boundary Tests:** Test 1-byte limits, exact 64 KiB buffer boundaries (`SNSLICE_IO_BUFFER_SIZE`), boundary crossings, and option terminator `--`.
   - **Streaming Memory Verification:** Stream 100+ MB input files while verifying that resident memory (RSS) remains strictly bounded and constant O(1).
   - **Format and Delimiter Tests:** Verify NDJSON with LF and CRLF line endings, preserved blank lines, and CSV with RFC 4180 quotes, multiline fields, commas, and escaped quotes (`""`).
   - **Hostile and Malformed Input Tests:** Verify rejection of unterminated CSV quotes at EOF, unclosed NDJSON lines at EOF, embedded NUL bytes, and oversized records exceeding 16 MiB.
   - **Operational Fault Injection:** Test collision handling against pre-existing files, write failure simulation, partial chunk unlinking, unsafe paths defense, and invalid directory paths.
   - **Diagnostic Verification:** Verify exact taxonomy error codes and hexadecimal sanitization of non-printable bytes on stderr.
   - **User Journey Simulation:** Test all 18 user journeys in `journeys/user_journeys_manifest.json` against real execution instances.

10. **Verification Plan:**
    - Strict warning-free compilation under GCC and Clang with `-std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L`.
    - Static analysis: `clang-tidy`, `cppcheck`, and Clang static analyzer (`clang --analyze`).
    - Dynamic sanitizers: AddressSanitizer (ASan with leak detection `detect_leaks=1`) and UndefinedBehaviorSanitizer (UBSan with `halt_on_error=1`).
    - Memory analysis: Valgrind memcheck verifying zero leaks, zero uninitialized memory reads, and zero file descriptor leaks.
    - Formatting compliance: `clang-format --dry-run --Werror`.
    - Manifest and traceability verification with `USER_JOURNEYS_MANIFEST_SCHEMA`.

11. **Explicit Non-Goals:**
    - `snslice` is NOT a full JSON schema validator, linter, or DOM parser; it does not construct an in-memory JSON object tree.
    - `snslice` is NOT a CSV dialect converter, SQL engine, or spreadsheet calculator; it does not alter column definitions or perform data transformations.
    - `snslice` does NOT decompress or compress input/output streams (e.g. gzip, zstd); streaming compression is cleanly delegated to external standard pipelines (e.g. `gzip -dc input.gz | snslice ...`).
    - `snslice` does NOT perform Snowflake staging, cloud storage uploads, or network communication; cloud loading is cleanly handled by downstream tooling.
    - `snslice` does NOT run background daemons, watch directories, or provide network interfaces.
    - `snslice` does NOT load entire files into memory.
    - `snslice` does NOT overwrite existing files or mutate the input file in place.
    - `snslice` does NOT implement multithreading or parallel background workers in the first slice.

12. **User Journey Manifest Synchronization:**
    - The user journeys manifest is maintained in `journeys/user_journeys_manifest.json`.
    - Conforms strictly to the canonical schema defined in `agent_orch.user_journeys.USER_JOURNEYS_MANIFEST_SCHEMA`.
    - Defines `command_allowlist` containing `["build/snslice", "tmp/snslice"]`.
    - Enforces that every natural-language journey specifies an authority of `human`, `mission`, `author`, or `exploratory`.
    - Enforces that every non-exploratory journey cites valid `AC-N` identifiers in `traces_to`, with 100% coverage across acceptance checks `AC-1` through `AC-13`.

# Acceptance Checks

Every criterion below is normative and must be satisfied by the implementation, tests, and verification gates:

- **AC-1** — **CLI Surface, Grammar, Arity, and Informational Options:**
  `snslice` parses command-line arguments strictly according to the specified CLI surface. Sole-argument `--help` prints usage guidance to standard output and exits with status `0`. Sole-argument `--version` prints `snslice 0.1.0\n` to standard output and exits with status `0`. Combining informational flags with other options or operands, supplying unrecognized options, supplying multiple positional file operands, or omitting both `--bytes` and `--records` chunking limits fails closed with informative stderr diagnostics and exit status `2`. The option terminator `--` is supported.

- **AC-2** — **Bounded-Memory Streaming and Resource Safety:**
  `snslice` reads and processes the input stream using a fixed-size 64 KiB buffer (`SNSLICE_IO_BUFFER_SIZE = 65536`) and a constant-memory finite state machine. Resident set size (RSS) memory consumption remains constant (O(1)) and strictly bounded regardless of whether the input stream is 1 KiB, 100 MiB, or 100 GiB. The implementation never loads the entire input or an entire chunk into heap memory.

- **AC-3** — **NDJSON Line Boundary and Complete Record Chunking:**
  When operating under `--format ndjson` (or default format), `snslice` treats each line terminated by LF (`\n`) or CRLF (`\r\n`) as an atomic record. Chunk splitting occurs strictly on complete line boundaries once the chunk byte size (`--bytes`) or record count (`--records`) threshold is reached. JSON records are never severed or truncated mid-object across chunk files. Empty lines are preserved as valid line records.

- **AC-4** — **CSV Quoted Records Spanning Physical Lines (RFC 4180):**
  When operating under `--format csv`, `snslice` tracks RFC 4180 double-quoted field states. Physical newline characters (`\n` and `\r\n`) and commas occurring inside balanced double quotes (`"..."`) are treated as literal field data rather than record boundaries. Consecutive double quotes (`""`) are handled as escaped quotes within quoted fields. A chunk boundary is cut exclusively at a true record boundary outside quoted fields. Multiline CSV records are never severed across chunk files.

- **AC-5** — **Deterministic Chunk Naming and Output Slicing:**
  Output chunk files are created in the directory specified by `--out-dir` (defaulting to `.`) with filenames formatted deterministically as `<prefix>%05zu.<ext>`, where `%05zu` is a five-digit zero-padded integer counter starting at `00001` (e.g. `chunk_00001.ndjson`, `chunk_00002.ndjson`), and `<ext>` matches the input format (`ndjson` or `csv`). Chunk files are emitted sequentially without missing or skipped index numbers.

- **AC-6** — **Chunk Collision Prevention and Atomic File Creation:**
  All chunk files are created atomically using `open()` with flags `O_CREAT | O_EXCL | O_WRONLY` and mode `0644`. If an intended chunk file already exists on disk, `snslice` immediately aborts fail-closed with diagnostic `snslice: OUTPUT_COLLISION: "..."` and exit status `2`, without modifying, truncating, or overwriting existing files.

- **AC-7** — **Empty Input Stream Handling:**
  When `snslice` receives an empty input stream (0 bytes read from a file or stdin), it exits cleanly with status `0`, emits nothing to stdout or stderr, and creates zero chunk files on disk, avoiding the generation of spurious empty files.

- **AC-8** — **Malformed Input and Unterminated Record Rejection:**
  Inputs violating format invariants are rejected fail-closed with exit status `2` and descriptive diagnostics. For CSV, an unclosed double quote reaching end-of-file triggers `MALFORMED_CSV`. For NDJSON, input ending without a terminating newline triggers `MALFORMED_NDJSON`. Records exceeding `SNSLICE_MAX_RECORD_BYTES` (16 MiB) trigger `RECORD_LENGTH_LIMIT`. Input containing embedded NUL bytes is rejected.

- **AC-9** — **Chunk Write Failures and Operational I/O Safety:**
  If an operational error occurs while writing to a chunk file (e.g. disk space exhausted `ENOSPC`, filesystem write failure, or I/O read failure), `snslice` aborts fail-closed with exit status `2`. The active partial chunk file is closed and immediately unlinked (`unlink()`) so no corrupted partial chunk lingers on disk. Any previously completed and closed chunks remain preserved.

- **AC-10** — **CLI Diagnostics, Unsafe Paths, and Hostile Byte Sanitization:**
  All diagnostic messages on `stderr` follow the standard format `snslice: <HAZARD_CODE>: <details>\n`. Unsafe paths attempting directory escape or traversal are rejected fail-closed. Any untrusted path, filename, or hostile input byte sequence rendered in diagnostics is escaped: bytes outside printable ASCII (`0x20`–`0x7E`), double quotes (`"`), and backslashes (`\`) are converted to uppercase `\xHH` hexadecimal sequences, preventing terminal escape sequence injection.

- **AC-11** — **Closed Hazard Taxonomy and Exit Status Integrity:**
  Every operational and usage failure maps deterministically to a member of the closed hazard taxonomy (`USAGE_ERROR`, `UNKNOWN_OPTION`, `INVALID_LIMIT`, `INVALID_FORMAT`, `INPUT_NOT_FOUND`, `INPUT_IS_DIRECTORY`, `INPUT_READ_ERROR`, `RECORD_LENGTH_LIMIT`, `MALFORMED_NDJSON`, `MALFORMED_CSV`, `OUTPUT_DIR_ERROR`, `OUTPUT_COLLISION`, `CHUNK_OPEN_ERROR`, `CHUNK_WRITE_ERROR`, `OUT_OF_MEMORY`, `BROKEN_PIPE`). Normal execution yields status `0` for success and status `2` for operational/usage failure. Status `1` is reserved.

- **AC-12** — **Repository Build, Hardening, and Quality Floor Compatibility:**
  The `snslice` utility builds cleanly under GCC and Clang with `-std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L`. It adheres to repository formatting rules verified by `clang-format --dry-run --Werror`, passes static analysis with `clang-tidy` and `cppcheck`, and runs cleanly under AddressSanitizer, UndefinedBehaviorSanitizer, and Valgrind memcheck with zero leaks or invalid memory operations.

- **AC-13** — **User Journey Manifest Synchronization and Acceptance Check Traceability:**
  The user journeys manifest in `journeys/user_journeys_manifest.json` conforms strictly to the canonical schema defined in `agent_orch.user_journeys.USER_JOURNEYS_MANIFEST_SCHEMA`. The manifest defines a `command_allowlist` containing `["build/snslice", "tmp/snslice"]`. Every natural-language journey specifies an authority of `human`, `mission`, `author`, or `exploratory`. Every non-exploratory journey cites valid `AC-N` identifiers in `traces_to`, and collectively all journeys provide 100% coverage across acceptance checks `AC-1` through `AC-13`.
