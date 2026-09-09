# `snslice` First-Slice Implementation Plan

Contract authority: [`docs/snslice-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/snslice-first-slice-contract.md).

## Authority

[`docs/snslice-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/snslice-first-slice-contract.md) is the sole normative authority for the first release-quality vertical slice of `snslice`. This implementation plan operationalizes every normative requirement, architectural invariant, resource boundary, and quality gate established in the contract and its governing foundations in [`AGENTS.md`](file:///home/lee/projects/linux-utilities-autonomous/AGENTS.md), [`product-definition.md`](file:///home/lee/projects/linux-utilities-autonomous/product-definition.md), and [`architecture.md`](file:///home/lee/projects/linux-utilities-autonomous/architecture.md).

In strict adherence to the Unix philosophy and repository engineering constraints, `snslice` is designed as an intentionally small, auditable, dependency-free command-line utility implemented in ISO C17 (`-std=c17`) with POSIX.1-2008 system interfaces (`_POSIX_C_SOURCE=200809L`) and 64-bit file offsets (`_FILE_OFFSET_BITS=64`). It partitions structured Newline-Delimited JSON (NDJSON) and Comma-Separated Values (CSV) streams into bounded, deterministically named chunk files strictly on complete record boundaries without loading entire files into memory.

All source authoring, unit and integration test creation, user journey synchronization, documentation, and verification activities described in this plan strictly adhere to the declared write scope (`plans/` for planning; governed source, test, and documentation locations during subsequent delivery steps).

---

## Architecture

The architecture of `snslice` is centered on a strictly bounded, constant-memory streaming pipeline engineered in ISO C17 that processes gigabyte- and terabyte-scale structured streams with zero third-party dependencies, zero dynamic framework overhead, and zero heap-based dataset buffering. Standard coreutils `split` corrupts RFC 4180 CSV records because line splitting bisects fields enclosing embedded newlines, while general-purpose tools like `jq` or Python runtimes exhaust system memory on large datasets. `snslice` solves both problems by coupling a fixed 64 KiB I/O streaming buffer with a deterministic finite state machine (FSM) that detects true record boundaries, enforces strict resource bounds, creates chunk files atomically with collision prevention, provides atomic or fail-safe output handling, and cleans up partial state transactionally on failure.

### 1. Portable C17 Design, Scope, and Standard Interfaces

`snslice` is implemented in a single, auditable C17 translation unit located at `src/snslice.c`. The executable is compiled to `build/snslice` for release and `tmp/snslice` during validation and test suites:
- **Standards Conformance:** Strictly ISO C17 (`-std=c17`). No GNU C language extensions or non-portable compiler builtins are utilized.
- **Platform Interfaces:** Strictly POSIX.1-2008 interfaces (`read`, `write`, `open`, `close`, `stat`, `lstat`, `unlink`, `signal`). No non-standard Linux-specific syscalls or glibc extensions are permitted.
- **Mandatory Feature-Test Macros:**
  ```c
  #define _POSIX_C_SOURCE 200809L
  #define _FILE_OFFSET_BITS 64
  ```
  These macros are passed on all compiler and analyzer invocations via the dedicated Makefile variable `SNSLICE_PLATFORM_CFLAGS` to ensure large file support (>2 GiB streams) and standard POSIX declarations remain intact even when callers override `CFLAGS`.
- **Zero Third-Party Dependencies:** No external JSON parsers (e.g. cJSON, Jansson), CSV parsing libraries, regular expression engines, IPC, networking, or multithreading libraries are linked. The utility links solely against the standard ISO C libc runtime.
- **Operational Scope:** `snslice` is an unprivileged, deterministic stream partitioner. It does not run background daemons, register inotify watchers, spawn worker threads, decompress data (delegated to standard pipelines like `gzip -dc | snslice`), or modify input files in place.

### 2. Command-Line Interface (CLI Surface), Grammar, and Arity Rules

The command-line grammar is strictly bounded:
```text
snslice [OPTIONS] [INPUT_FILE]
```
The command dispatch and option parser adhere to the following normative invariants:
1. **Positional Operand (`INPUT_FILE`):**
   - At most one positional argument is permitted.
   - If `INPUT_FILE` is omitted or passed as `-`, `snslice` streams from standard input (`STDIN_FILENO`).
   - Supplying two or more positional arguments constitutes an arity violation resulting in `snslice: USAGE_ERROR: unexpected positional argument\n` on `stderr` and exit status `2`.
2. **Option Terminator (`--`):**
   - The double-dash token `--` terminates option processing. Any subsequent argument is treated as the positional `INPUT_FILE`.
3. **Informational Options:**
   - `--help`: Sole argument. Emits usage synopsis and option documentation to `stdout`, leaves `stderr` empty, and exits status `0`.
   - `--version`: Sole argument. Emits `snslice 0.1.0\n` to `stdout`, leaves `stderr` empty, and exits status `0`.
   - Combining `--help` or `--version` with any other option or operand is a usage error resulting in diagnostic `snslice: USAGE_ERROR: ...` and exit status `2`.
4. **Format Selection:**
   - `--format <ndjson|csv>` or `-f <ndjson|csv>`: Sets stream parsing mode. Defaults to `ndjson` if omitted.
   - Supplying any value other than `ndjson` or `csv` immediately fails closed with `snslice: INVALID_FORMAT: "..."` and exit status `2`.
5. **Chunk Sizing Limits (Thresholds):**
   - `--bytes <BYTES>` or `-b <BYTES>`: Specifies chunk byte threshold. Must be a positive integer in `1..SIZE_MAX`.
   - `--records <COUNT>` or `-r <COUNT>`: Specifies chunk record threshold. Must be a positive integer in `1..SIZE_MAX`.
   - At least one limit (`--bytes` or `--records`) must be specified. Omitting both is a usage error resulting in `snslice: USAGE_ERROR: at least one chunk limit (--bytes or --records) must be specified` and exit status `2`.
   - If both limits are specified, a chunk boundary is cut as soon as either limit is reached or exceeded on a complete record boundary.
6. **Output Directory and Prefix:**
   - `--out-dir <DIR>` or `-d <DIR>`: Destination directory for chunk files. Defaults to `.` (current working directory).
   - `--prefix <PREFIX>` or `-p <PREFIX>`: Filename prefix for chunks. Defaults to `chunk_`.
   - Prefix security validation: `--prefix` must not be empty, must not contain directory separators (`/`), and must not contain directory traversal tokens (`..`). Violations fail closed with `snslice: USAGE_ERROR: prefix cannot contain path separators or traversal tokens` and exit status `2`.

### 3. Safe Path and Size Parsing

1. **Integer Limit Parsing (`parse_positive_size`):**
   - Safe path and size parsing is enforced across all CLI inputs.
   - Parsing integers for `--bytes` and `--records` is protected against overflow, non-digits, zero, and signed negative representations.
   - Digits are parsed using `strtoull` with strict validation:
     ```c
     errno = 0;
     char *endptr = NULL;
     unsigned long long val = strtoull(arg, &endptr, 10);
     if (errno == ERANGE || *endptr != '\0' || endptr == arg || val == 0 || val > SIZE_MAX) {
         emit_diagnostic(HAZARD_INVALID_LIMIT, arg);
         return 2;
     }
     ```
   - Rejects negative values (`-10`), zero (`0`), empty strings (`""`), alphabetic suffix corruptions (`10M`, `5k`), and values exceeding `SIZE_MAX`.
2. **Output Directory Validation (`validate_output_directory`):**
   - Before processing input bytes, `--out-dir` is inspected using `stat(out_dir, &st)`:
     - If `stat` fails (`ENOENT`, `EACCES`), fail closed with `snslice: OUTPUT_DIR_ERROR: ...` and exit status `2`.
     - If `!S_ISDIR(st.st_mode)`, fail closed with `snslice: OUTPUT_DIR_ERROR: not a directory` and exit status `2`.
     - Output directory path length is verified against `PATH_MAX` (`4096`). If `strlen(out_dir) + strlen(prefix) + 16 >= PATH_MAX`, fail closed with `OUTPUT_DIR_ERROR`.
3. **Safe Chunk Filename Construction:**
   - Formatted using `snprintf` into a stack-allocated buffer:
     ```c
     char chunk_path[PATH_MAX];
     int n;
     if (out_dir[strlen(out_dir) - 1] == '/') {
         n = snprintf(chunk_path, sizeof(chunk_path), "%s%s%05zu.%s",
                      out_dir, prefix, chunk_index, ext);
     } else {
         n = snprintf(chunk_path, sizeof(chunk_path), "%s/%s%05zu.%s",
                      out_dir, prefix, chunk_index, ext);
     }
     if (n < 0 || (size_t)n >= sizeof(chunk_path)) {
         emit_diagnostic(HAZARD_OUTPUT_DIR_ERROR, "constructed chunk path exceeds PATH_MAX");
         return 2;
     }
     ```
   - Counter `%05zu` starts at `1` (`00001`) and increments sequentially (`00002`, `00003`, ...) without skipping indices.

### 4. Bounded-Memory Streaming Design for NDJSON and RFC-4180-Style CSV Record Recognition

The core bounded-memory streaming design for NDJSON and RFC-4180-style CSV record recognition guarantees strictly constant resident memory consumption ($O(1)$) regardless of total input size:
1. **Fixed Streaming Buffer:**
   - Input is read in fixed chunks using a static buffer: `char io_buffer[SNSLICE_IO_BUFFER_SIZE]` where `SNSLICE_IO_BUFFER_SIZE = 65536` (64 KiB).
   - Bytes are consumed sequentially from the buffer. The engine maintains no growable heap buffer for the whole stream or for entire chunks.
2. **Record Length Safety Bound:**
   - `SNSLICE_MAX_RECORD_BYTES = 16777216` (16 MiB).
   - If a single record accumulates more than 16 MiB without encountering a valid record delimiter, `snslice` immediately aborts fail-closed with `snslice: RECORD_LENGTH_LIMIT: record exceeds 16 MiB limit` and exit status `2`. This prevents denial-of-service from malformed streams lacking newlines.
3. **NDJSON Streaming Recognition:**
   - **Record Delimiter:** Newline byte LF (`\n`, `0x0A`). CRLF (`\r\n`) endings are handled seamlessly; the `\r` is part of the line data or delimiter, and `\n` marks the record completion.
   - **State Invariants:**
     - Blank lines (empty lines containing only `\n` or `\r\n`) are treated as valid complete NDJSON records per contract and preserved without modification.
     - Embedded NUL bytes (`0x00`) are illegal in NDJSON text streams and trigger immediate fail-closed termination with `snslice: MALFORMED_NDJSON: embedded NUL byte detected` and exit status `2`.
     - Unterminated Line at EOF: If the input stream reaches EOF and the current record has accumulated one or more bytes without a terminating `\n`, the input is invalid NDJSON -> fails closed with `snslice: MALFORMED_NDJSON: unterminated record at EOF` and exit status `2`.
4. **RFC-4180-Style CSV Streaming Record Recognition:**
   - Implements a deterministic finite state machine with five distinct states:
     - `CSV_STATE_START`: Beginning of a record or field.
     - `CSV_STATE_UNQUOTED`: Inside an unquoted field.
     - `CSV_STATE_QUOTED`: Inside a double-quoted field (`"..."`).
     - `CSV_STATE_ESCAPED_QUOTE`: Immediately following a double quote inside a quoted field. If the next character is `"`, it represents an escaped quote (`""`) and transitions back to `CSV_STATE_QUOTED`. If followed by comma (`,`), CR (`\r`), LF (`\n`), or EOF, transitions out of the quoted field. Any other character violates RFC 4180 and triggers `MALFORMED_CSV`.
     - `CSV_STATE_CR`: Encountered `\r` outside of quotes, expecting `\n`.
   - **Multiline Field Preservation:**
     - Inside `CSV_STATE_QUOTED`, physical newline bytes (`\n` and `\r\n`) and commas (`,`) are treated strictly as field payload data. They NEVER trigger field or record delimiters.
     - Multiline CSV rows (e.g. database text dumps, stack traces, embedded markdown) remain intact within the same chunk file.
   - **State Invariants:**
     - Embedded NUL bytes (`0x00`) trigger immediate fail-closed termination with `snslice: MALFORMED_CSV: embedded NUL byte detected` and exit status `2`.
     - Unterminated Quoted Field at EOF: If the stream terminates (EOF) while the FSM is in `CSV_STATE_QUOTED` or expecting an escaped quote resolution, the CSV stream is malformed -> fails closed with `snslice: MALFORMED_CSV: unterminated quoted field at EOF` and exit status `2`.
     - True record boundaries occur if and only if an unquoted LF (`\n`) is encountered outside quoted fields.

```
       [CSV State Machine Diagram]

             +-----------------------------------------+
             |                                         |
             v                                         |
    +-----------------+        '"'        +------------------+
    | CSV_STATE_START | ----------------> | CSV_STATE_QUOTED | <----+
    +-----------------+                   +------------------+      |
       |           |                             |                  |
       | non-quote |                             | '"'              |
       | non-delim |                             v                  | '"'
       |           |                    +--------------------+      | (escaped
       v           v                    | CSV_STATE_ESCAPED_ | -----+  quote)
+--------------------+                  |       QUOTE        |
| CSV_STATE_UNQUOTED |                  +--------------------+
+--------------------+                             |
       |         |                                 | ',', '\n', '\r'
       | ','     | '\n'                            v
       v         |                      [Field / Record Delim]
[Field Delim]    v
         [Record Boundary] (Unquoted '\n')
```

### 5. Atomic or Fail-Safe Output Handling, Collision Protection, and Slicing Logic

`snslice` enforces atomic or fail-safe output handling at every stage of chunk generation:
1. **Lazy Output Chunk Initialization:**
   - For empty input streams (0 bytes read from file or stdin), `snslice` does NOT create `chunk_00001` upon startup.
   - The first chunk file is opened lazily upon reading the first valid byte of the first record. If the input stream produces 0 bytes total, `snslice` cleanly exits status `0` without creating any files on disk, leaving stdout and stderr empty.
2. **Atomic Creation via `O_CREAT | O_EXCL`:**
   - Every chunk file is created using:
     ```c
     int fd = open(chunk_path, O_CREAT | O_EXCL | O_WRONLY, 0644);
     ```
   - If `open()` returns `-1` with `errno == EEXIST`, `snslice` immediately aborts fail-closed:
     ```text
     snslice: OUTPUT_COLLISION: "..."
     ```
     Exit status is `2`. Pre-existing files are never truncated, opened, or overwritten. This provides kernel-enforced atomic collision defense.
   - Any other open error (e.g. `EACCES`, `ENOSPC`) triggers `CHUNK_OPEN_ERROR` and exit status `2`.
3. **Record Boundary Slicing Policy:**
   - Bytes from the input buffer are streamed directly into the active chunk file descriptor.
   - The engine tracks:
     - `chunk_bytes`: cumulative bytes written to the current chunk.
     - `chunk_records`: cumulative complete records written to the current chunk.
   - When the FSM signals that a complete record has just ended (after the terminating `\n`):
     - Check thresholds:
       ```c
       bool threshold_reached = false;
       if (limit_bytes > 0 && chunk_bytes >= limit_bytes) threshold_reached = true;
       if (limit_records > 0 && chunk_records >= limit_records) threshold_reached = true;
       ```
     - If `threshold_reached` is true, the active chunk is completed:
       1. Flush / `close(active_chunk_fd)`.
       2. Clear `active_chunk_fd = -1` and reset `active_chunk_path[0] = '\0'`.
       3. Increment `chunk_index++`.
       4. Reset `chunk_bytes = 0` and `chunk_records = 0`.
     - The subsequent record will trigger opening a new atomic chunk file `<prefix>%05zu.<ext>`.
   - Invariant: A record is NEVER split across chunk files. If a single record exceeds `--bytes`, it occupies the chunk in its entirety and the chunk closes immediately after that record finishes.

### 6. Cleanup Ownership and Transactional Error Recovery

Clear cleanup ownership ensures that no descriptors or corrupted files leak under any failure mode:
1. **Single-Owner Execution Context (`SnSliceContext`):**
   - The entire runtime lifecycle is encapsulated in a single structure:
     ```c
     typedef struct {
         int input_fd;
         bool close_input;
         int active_chunk_fd;
         char active_chunk_path[PATH_MAX];
         size_t chunk_index;
         size_t chunk_bytes;
         size_t chunk_records;
         size_t record_bytes;
         FormatType format;
         size_t limit_bytes;
         size_t limit_records;
         const char *out_dir;
         const char *prefix;
     } SnSliceContext;
     ```
2. **File Descriptor Discipline:**
   - At most two file descriptors are open concurrently at any time: `input_fd` and `active_chunk_fd`.
   - When completing a chunk, `active_chunk_fd` is closed before opening the next chunk descriptor.
3. **Transactional Unlink on Failure:**
   - If an operational error occurs during execution (e.g. disk exhaustion `ENOSPC`, write failure, read failure `EIO`, format violation `MALFORMED_NDJSON`/`MALFORMED_CSV`, or record limit `RECORD_LENGTH_LIMIT`):
     ```c
     void snslice_abort_cleanup(SnSliceContext *ctx) {
         if (ctx->active_chunk_fd >= 0) {
             close(ctx->active_chunk_fd);
             ctx->active_chunk_fd = -1;
             if (ctx->active_chunk_path[0] != '\0') {
                 unlink(ctx->active_chunk_path);
                 ctx->active_chunk_path[0] = '\0';
             }
         }
         if (ctx->close_input && ctx->input_fd >= 0) {
             close(ctx->input_fd);
             ctx->input_fd = -1;
         }
     }
     ```
   - Any incomplete, partially written active chunk file is immediately removed from disk via `unlink()`.
   - Completed, previously closed chunks (e.g. `chunk_00001.ndjson`) are preserved intact.
4. **Memory Ownership:**
   - Command-line arguments in `argv` are borrowed for the process duration and never modified or freed.
   - Internal buffers use static or automatic stack storage (`PATH_MAX`, `64 KiB`). Zero heap memory allocations are required for regular streaming, completely eliminating memory leak vulnerabilities.

### 7. Deterministic Diagnostics and Closed Hazard Taxonomy

Deterministic diagnostics prevent ambiguity and protect operators from terminal corruption:
1. **Diagnostic Formatting Standard:**
   - All error messages emitted to `stderr` follow the strict pattern:
     ```text
     snslice: <HAZARD_CODE>: <details>\n
     ```
2. **Hostile Byte Sanitization (`snslice_sanitize_string`):**
   - Untrusted strings (file paths, option arguments, malformed byte tokens) rendered in diagnostics are sanitized against ANSI terminal escape injection:
     - Characters in printable ASCII range `0x20` through `0x7E` (excluding `"` and `\`) are emitted as-is.
     - Double quote (`"`, `0x22`) and backslash (`\`, `0x5C`) are escaped as `\x22` and `\x5C`.
     - Control characters, escape characters (`\x1b`), newlines, tabs, and non-ASCII bytes (< `0x20` or > `0x7E`) are converted to uppercase hexadecimal sequences: `\xHH`.
3. **Closed Hazard Taxonomy (16 Members):**
   Every operational or usage failure maps deterministically to one of the 16 contract members:
   1. `USAGE_ERROR`: CLI syntax error, arity violation, missing limits, invalid prefix tokens.
   2. `UNKNOWN_OPTION`: Unrecognized option flag starting with `-`.
   3. `INVALID_LIMIT`: `--bytes` or `--records` is non-numeric, `<= 0`, or overflows `SIZE_MAX`.
   4. `INVALID_FORMAT`: `--format` is neither `ndjson` nor `csv`.
   5. `INPUT_NOT_FOUND`: Input file operand does not exist or cannot be accessed (`ENOENT`, `EACCES`).
   6. `INPUT_IS_DIRECTORY`: Input file operand points to a directory (`EISDIR`).
   7. `INPUT_READ_ERROR`: Operating system I/O read failure on input stream (`EIO`).
   8. `RECORD_LENGTH_LIMIT`: A single record exceeds `SNSLICE_MAX_RECORD_BYTES` (16 MiB).
   9. `MALFORMED_NDJSON`: Unterminated line at EOF without trailing newline, or embedded NUL.
   10. `MALFORMED_CSV`: Unterminated quote at EOF, bad quote escape, or embedded NUL.
   11. `OUTPUT_DIR_ERROR`: Output directory does not exist, is not a directory, or lacks permissions.
   12. `OUTPUT_COLLISION`: Output chunk file already exists (preventing overwrite under `O_EXCL`).
   13. `CHUNK_OPEN_ERROR`: OS error opening chunk file (other than `EEXIST`).
   14. `CHUNK_WRITE_ERROR`: Write failure or flush failure on chunk file (e.g. `ENOSPC`).
   15. `OUT_OF_MEMORY`: Dynamic memory allocation failure (`calloc`/`malloc` returns NULL).
   16. `BROKEN_PIPE`: Output stream pipe closed prematurely (`EPIPE` under ignored `SIGPIPE`).

### 8. Exit Status Reduction and Signal Handling

- **Exit Status `0`:** Clean completion. Input stream consumed, all complete records partitioned into valid chunk files, descriptors cleanly closed; or sole informational option (`--help`, `--version`).
- **Exit Status `1`:** Reserved for notice/hazard in future vertical slices.
- **Exit Status `2`:** Operational or usage failure. All 16 hazard taxonomy conditions exit with status `2`.
- **Signal Handling:**
  ```c
  signal(SIGPIPE, SIG_IGN);
  ```
  Installed unconditionally at process entry. Prevents closed output pipes from terminating the process abruptly without unlinking partial chunks; write failures surface as checked stdio `EPIPE` returning exit status `2`.

### 9. Build System Integration and Quality Floor Alignment

1. **Target Compilation in Makefile:**
   - Product binary compiled from `src/snslice.c` into `build/snslice` via `make snslice` or `make all`.
   - Dedicated platform flags:
     ```makefile
     SNSLICE_PLATFORM_CFLAGS := -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64
     ```
   - Non-writing temporary test binary compiled under `/tmp/snslice-build.XXXXXX` via `mktemp -d` for tests and static analyzers.
2. **Quality Target Integration:**
   - Source inventory: `SNSLICE_SRC := src/snslice.c` added to `ALL_SRCS`.
   - Manpage inventory: `SNSLICE_MANPAGE := man/snslice.1` added to `ALL_MANPAGES`.
   - Verification recipes: `snslice-test`, `snslice-sanitize`, `snslice-valgrind`.
   - Integrated into `make quality`, `make check`, `make gcc-strict`, `make clang-strict`, `make clang-tidy-check`, `make cppcheck-check`, `make clang-analyzer-check`, and `make man-check`.

### 10. Acceptance Check Mapping Matrix

Every enumerated requirement in [`docs/snslice-first-slice-contract.md`](file:///home/lee/projects/linux-utilities-autonomous/docs/snslice-first-slice-contract.md) maps across the complete seven-dimension software delivery lifecycle:

| Acceptance Check | 1. Concrete C Source | 2. Independently Authored Tests | 3. User Documentation | 4. Deterministic Verification | 5. Smoke Evidence | 6. User Simulation | 7. Independent Review |
|---|---|---|---|---|---|---|---|
| **AC-1:** CLI Surface, Option Parsing, Grammar, Arity, and Informational Options | `src/snslice.c`: `parse_arguments`, sole-arg `--help`/`--version`, `--` terminator, arity check, limit requirement check, safe integer parsing (`parse_positive_size`), format validation, prefix safety validation. | `tests/test_snslice.py` Suite 1: `--help`, `--version`, combined args rejection, unrecognized flags, missing limits, multiple positional operands, `--` option terminator, prefix traversal checks. | `man/snslice.1` & `docs/snslice.md`: CLI synopsis, option descriptions, exit codes 0 and 2, prefix syntax constraints. | Strict GCC/Clang builds with `-Wall -Wextra -Wpedantic -Werror`, `clang-tidy`, `cppcheck`, exit code verification. | `scripts/smoke.sh` runs `snslice --help` and `--version` verifying exit 0 and canonical stdout byte streams. | Simulation verifies CLI invocation parsing with diverse flags, combined flag rejections, and option terminator `--`. | Code review verifies argument parsing loop, arity enforcement, and fail-closed syntax handling. |
| **AC-2:** Bounded-Memory Streaming, Record Boundary Preservation, NDJSON Chunking, and RFC 4180 CSV Multiline Integrity | `src/snslice.c`: Fixed 64 KiB `io_buffer`, O(1) resident memory, constant-memory FSM without heap allocation for input records, 16 MiB record length bound (`RECORD_LENGTH_LIMIT`), NDJSON LF/CRLF/blank-line recognizer, RFC 4180 CSV FSM tracking quoted states, embedded newlines, commas, and escaped quotes (`""`), lazy 0-byte input handling. | `tests/test_snslice.py` Suite 2: 100+ MB streaming RSS test, 64 KiB buffer boundary tests, NDJSON line boundary tests by bytes/records, CRLF/blank-line tests, RFC 4180 multiline CSV tests with `csv.reader` oracle, empty 0-byte input tests, malformed format rejection tests (unterminated quotes, unterminated lines, embedded NULs). | `man/snslice.1` & `docs/snslice.md`: Architecture section documenting constant memory footprint, 64 KiB buffer, NDJSON line preservation, RFC 4180 multiline CSV rules, and 0-byte input handling. | Memory profiling under Valgrind memcheck and ASan asserting zero growth during large stream ingestion; Python `csv.reader` and `json.loads` oracles. | Smoke runs streaming test on multi-megabyte fixture and multiline CSV fixture. | Data engineering simulation streams large log files and multiline CSV exports through pipeline, verifying row count preservation. | Memory audit confirming absence of growable heap buffers for stream payloads, and FSM transition audit for RFC 4180 conformance. |
| **AC-3:** Deterministic Output Chunk Naming, Atomic File Creation, Closed Hazard Taxonomy, Transactional Fault Cleanup, Quality Floor, and Manifest Synchronization | `src/snslice.c`: `snprintf` path builder with `%05zu`, counter starting at 1, custom `--prefix` and `--out-dir` handling, atomic `open(..., O_CREAT \| O_EXCL \| O_WRONLY, 0644)` with `OUTPUT_COLLISION` abort, `snslice_abort_cleanup` unlinking active chunk on error, `snslice_sanitize_string` escaping non-printable ASCII, `"` and `\` to `\xHH`, 16-member closed hazard taxonomy, `signal(SIGPIPE, SIG_IGN)`, `Makefile` targets. | `tests/test_snslice.py` Suite 3: Sequential chunk naming tests, collision prevention tests (asserting exit 2 and file preservation), simulated write failure tests (asserting partial chunk unlinked and prior chunks kept), hostile argument sanitization tests, exhaustive 16-code taxonomy tests, `SIGPIPE` tests, manifest sync tests. | `man/snslice.1` & `docs/snslice.md`: Chunk naming `<out-dir>/<prefix>%05zu.<ext>`, collision protection, transactional cleanup, 16-code taxonomy catalog, exit codes 0 and 2. | Directory scans asserting regex `^chunk_[0-9]{5}\.(ndjson\|csv)$`, `make quality`, `clang-format --dry-run --Werror`, `clang-tidy`, `cppcheck`, `clang --analyze`, ASan, UBSan, Valgrind, manifest schema validation. | Smoke script asserts created files match `chunk_00001.ndjson`, captures collision abort, and verifies user journey manifest integrity. | Pipeline simulation partitions log streams, simulates disk exhaustion/collision, and verifies clean exit status 2 and disk state. | Security review checking TOCTOU avoidance via `O_EXCL`, signal safety, diagnostic sanitization, and 21 user journey preservation. |

### 11. Concrete Implementation and Verification Work by Acceptance Check

| Check | Concrete C17 Source Implementation Work | Independently Authored Test Coverage | Deterministic Verification Work |
|---|---|---|---|
| **AC-1** | Author CLI parser in `src/snslice.c` with sole-arg `--help`/`--version`, `--` terminator, arity validation, format parsing (`ndjson`/`csv`), threshold parsing (`parse_positive_size` for `--bytes` and `--records`), required limit check, and directory/prefix validation. | Author CLI tests in `tests/test_snslice.py` testing `--help`, `--version`, combined flags, missing limits, invalid prefixes (with `/` or `..`), extra positional operands, non-numeric/overflowing limits, and unknown option flags. | Run GCC/Clang strict builds, verify exit codes 0 and 2, verify stderr empty on `--help`/`--version`, verify diagnostic error formatting against standard grammar. |
| **AC-2** | Implement fixed 64 KiB `io_buffer` streaming reader loop with constant O(1) resident set size and zero dataset heap buffering. Implement 16 MiB record safety limit (`SNSLICE_MAX_RECORD_BYTES`). Implement NDJSON streaming FSM (LF/CRLF/blank lines). Implement RFC 4180 CSV FSM tracking quoted states, commas, and escaped quotes (`""`). Implement lazy 0-byte input handling. | Author streaming benchmark test feeding 100+ MB dataset through pipe while sampling `/proc/$PID/statm` to verify resident memory remains flat. Test 64 KiB boundaries, NDJSON line integrity, CSV multiline preservation, empty file/stdin handling, and malformed stream rejection. | Profile execution under Valgrind memcheck and ASan with leak detection; assert peak heap allocation is invariant to input stream volume. Validate chunk contents with Python `json.loads` and `csv.reader` oracles. |
| **AC-3** | Implement deterministic path formatting `<out-dir>/<prefix>%05zu.<ext>`, 1-indexed counter, atomic creation via `open(..., O_CREAT \| O_EXCL \| O_WRONLY, 0644)`, transactional cleanup in `snslice_abort_cleanup` unlinking active chunk on error, `snslice_sanitize_string` escaping hostile diagnostic bytes to `\xHH`, closed 16-code hazard taxonomy, `SIGPIPE` ignore, and Makefile quality integration. | Author tests for sequential naming (`chunk_00001.ndjson`), collision prevention against pre-existing files, transactional unlinking of partial chunks on simulated write errors, hostile terminal escape sanitization on stderr, exhaustive 16-code taxonomy invocation, and manifest synchronization. | Execute `make quality`, `./scripts/smoke.sh`, Valgrind memcheck verifying zero leaks and zero file descriptor leaks, static analysis (`clang-tidy`, `cppcheck`, `clang --analyze`), and manifest schema validation against `USER_JOURNEYS_MANIFEST_SCHEMA`. |

---

## Tests

The testing strategy for `snslice` enforces comprehensive functional, regression, resource-bounding, and adversarial validation across all three normative acceptance criteria (`AC-1`, `AC-2`, and `AC-3`). All tests compile and execute against temporary binaries isolated outside repository product paths to prevent contamination of `build/` artifacts or tracked files.

### 1. Pytest Test Harness & Isolated Temporary Binary Compilation

To ensure repository cleanliness, hermeticity, and strict adherence to build boundaries:
1. **Isolated Compilation in Temporary Directories:**
   - The test module `tests/test_snslice.py` dynamically resolves the compiler via `$CC` (defaulting to `cc` or `gcc`).
   - Compilation produces a temporary binary under `/tmp/snslice-test-XXXXXX/snslice_test_bin`:
     ```bash
     $CC -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 -O2 -o /tmp/snslice-test-XXXXXX/snslice_test_bin src/snslice.c
     ```
   - No binaries are created in `build/` or the repository root during test runs. Missing source fails closed immediately with `pytest.fail()`.
2. **Sealed Test Environment:**
   - Test child processes run with sanitized environment variables: `LC_ALL=C`, `LANG=C`, and `PYTHONDONTWRITEBYTECODE=1`.
3. **Automatic Teardown:**
   - Fixture teardown and `atexit` handlers guarantee immediate deletion of temporary directories, temporary binaries, and generated chunk files.
4. **Makefile Phony Targets:**
   - Additive targets `snslice-test`, `snslice-sanitize`, and `snslice-valgrind` mirror this isolation pattern using `mktemp -d /tmp/snslice-build.XXXXXX` with trap handlers.

### 2. Automated Regression Test Suites Structured by Acceptance Check

The test suite in `tests/test_snslice.py` organizes test coverage into three exhaustive test families corresponding to the acceptance checks:

#### Suite 1: CLI Surface, Option Parsing, Grammar, and Arity (AC-1)
- **Informational Options:**
  - `test_cli_help_sole_argument`: Invokes `snslice --help`; asserts exit code `0`, usage text on `stdout`, empty `stderr`.
  - `test_cli_version_sole_argument`: Invokes `snslice --version`; asserts exit code `0`, `stdout == "snslice 0.1.0\n"`, empty `stderr`.
  - `test_cli_help_combined_fails`: Combines `--help` with other flags (e.g. `snslice --help --bytes 1000`); asserts exit code `2`, stderr `USAGE_ERROR`.
  - `test_cli_version_combined_fails`: Combines `--version` with other flags; asserts exit code `2`, stderr `USAGE_ERROR`.
- **Threshold & Parameter Validation:**
  - `test_cli_missing_limits_fails`: Invokes `snslice input.ndjson` without `--bytes` or `--records`; asserts exit code `2`, stderr `USAGE_ERROR`.
  - `test_cli_invalid_limits`: Tests `--bytes 0`, `--bytes -1`, `--records abc`, and values overflowing `SIZE_MAX`; asserts exit code `2`, stderr `INVALID_LIMIT`.
  - `test_cli_invalid_format`: Invokes `--format xml`; asserts exit code `2`, stderr `INVALID_FORMAT`.
- **Arity, Options, and Grammar:**
  - `test_cli_multiple_positional_operands_fails`: Invokes `snslice -b 1000 file1 file2`; asserts exit code `2`, stderr `USAGE_ERROR`.
  - `test_cli_option_terminator`: Invokes `snslice -b 1000 -- -weird-file-name`; verifies `-weird-file-name` is treated as input path.
  - `test_cli_unrecognized_option`: Invokes `snslice --invalid-flag`; asserts exit code `2`, stderr `UNKNOWN_OPTION`.
- **Prefix and Path Safety:**
  - `test_cli_invalid_prefix_slash`: Invokes `snslice -b 1000 --prefix "sub/dir"`; asserts exit code `2`, stderr `USAGE_ERROR`.
  - `test_cli_invalid_prefix_traversal`: Invokes `snslice -b 1000 --prefix "../escape"`; asserts exit code `2`, stderr `USAGE_ERROR`.
  - `test_cli_invalid_output_directory`: Invokes `snslice -b 1000 --out-dir /nonexistent/dir`; asserts exit code `2`, stderr `OUTPUT_DIR_ERROR`.

#### Suite 2: Bounded-Memory Streaming, Record Boundary Preservation, and Format Integrity (AC-2)
- **Bounded-Memory Streaming:**
  - `test_bounded_memory_large_stream`: Streams a 100 MB NDJSON dataset through `stdin` into `snslice -b 10485760` while sampling resident memory via `/proc/<pid>/statm`.
    - Asserts resident set size (RSS) remains strictly bounded (< 10 MiB resident memory) throughout the entire run.
    - Confirms zero linear growth of memory relative to input volume.
  - `test_io_buffer_boundaries`: Feeds inputs sized exactly at buffer boundaries (65,535, 65,536, and 65,537 bytes) to verify buffer transition correctness.
- **NDJSON Record Integrity:**
  - `test_ndjson_line_boundary_by_bytes`: Splits a dataset of variable-length JSON objects with `--bytes 500`. Verifies every emitted chunk file contains valid JSON objects parsable by `json.loads`.
  - `test_ndjson_line_boundary_by_records`: Splits with `--records 10`. Verifies each chunk contains exactly 10 complete lines (except the final chunk).
  - `test_ndjson_both_thresholds`: Slices with both `--bytes` and `--records`; verifies chunks break on whichever threshold is reached first.
  - `test_ndjson_crlf_handling`: Feeds NDJSON with CRLF (`\r\n`) endings; verifies records are preserved and line endings do not corrupt record recognition.
  - `test_ndjson_empty_lines_preserved`: Verifies empty lines (`\n`) are preserved as valid line records without desynchronizing chunk metrics.
- **RFC 4180 CSV Quoted Record Integrity:**
  - `test_csv_multiline_fields_preserved`: Feeds CSV rows where fields contain embedded newlines (`"line1\nline2\nline3"`), commas, and carriage returns.
    - Verifies that multiline rows are NEVER cut across chunk files.
    - Validates using Python's `csv.reader` that the parsed row count and field values match the original dataset.
  - `test_csv_escaped_quotes`: Feeds CSV fields containing escaped double quotes (`"He said, ""Hello!"""`). Confirms escaped quotes do not prematurely trigger unquoted state.
  - `test_csv_crlf_records`: Slices CSV streams using RFC 4180 standard CRLF record terminators.
  - `test_csv_split_by_record_count`: Splits multiline CSV with `--records 5`; confirms each chunk contains exactly 5 logical records despite physical line counts exceeding 5.
- **Empty Stream Handling:**
  - `test_empty_file_input`: Runs `snslice -b 1000 empty.ndjson`. Asserts exit code `0`, zero chunk files created in output directory, and empty stdout/stderr.
  - `test_empty_stdin_input`: Pipes `/dev/null` to `snslice -b 1000`. Confirms identical exit code 0 and zero files created.
- **Malformed Input and Resource Bounds:**
  - `test_malformed_csv_unterminated_quote`: Feeds CSV ending with unclosed quote `"unterminated field at EOF`. Asserts exit code `2` and stderr `snslice: MALFORMED_CSV: ...`.
  - `test_malformed_ndjson_unterminated_line`: Feeds NDJSON ending without newline `{"key": "value"}` at EOF. Asserts exit code `2` and stderr `snslice: MALFORMED_NDJSON: ...`.
  - `test_record_length_limit_exceeded`: Feeds a single line/record exceeding 16 MiB (`16777217` bytes). Asserts exit code `2` and stderr `snslice: RECORD_LENGTH_LIMIT: ...`.
  - `test_embedded_nul_byte_rejected`: Feeds input containing `\x00`; asserts exit code `2` and malformed format diagnostic.

#### Suite 3: Deterministic Naming, Atomic File Creation, Closed Hazard Taxonomy, Transactional Cleanup, Quality Floor, and Manifest Synchronization (AC-3)
- **Deterministic Output Chunk Naming:**
  - `test_chunk_naming_default`: Verifies output chunk filenames follow `chunk_00001.ndjson`, `chunk_00002.ndjson`, etc.
  - `test_chunk_naming_custom_prefix_and_dir`: Configures `--out-dir /tmp/.../out --prefix data_`; verifies files match `data_00001.csv`, `data_00002.csv`.
  - `test_chunk_index_continuity`: Verifies indices are strictly continuous and monotonic without skipped numbers.
- **Atomic File Creation & Collision Prevention:**
  - `test_collision_prevention_fail_closed`: Pre-creates `chunk_00001.ndjson` with canary content. Runs `snslice -b 1000`.
    - Asserts exit code `2`.
    - Asserts stderr contains `snslice: OUTPUT_COLLISION: "..."`.
    - Asserts canary content of pre-existing file is completely unaltered.
- **Transactional Fault Cleanup:**
  - `test_write_failure_unlinks_partial_chunk`: Slices a multi-chunk dataset into an output directory mounted on a full filesystem or read-only tree (or using a simulated write failure).
    - Asserts exit code `2` with `CHUNK_WRITE_ERROR`.
    - Asserts that the active partial chunk is deleted (`unlink()`).
    - Asserts that any previously completed chunk remains intact and valid.
- **Hostile Byte Sanitization & Terminal Safety:**
  - `test_diagnostic_sanitization_ansi_escapes`: Triggers an error using an input path containing ANSI terminal escape sequences (`\x1b[31;1m`).
    - Asserts stderr renders escaped hexadecimal representation (`\x1B[31;1m`).
    - Asserts raw escape bytes are never written to stderr.
  - `test_diagnostic_sanitization_control_chars`: Tests carriage returns, tabs, backslashes, and non-printable bytes; verifies all convert to `\xHH`.
- **Closed Hazard Taxonomy & Signal Safety:**
  - `test_closed_hazard_taxonomy_membership`: Parameterized test covering all 16 taxonomy members:
    - Asserts every operational failure emits `snslice: <HAZARD_CODE>: <details>\n`.
    - Asserts exit code is strictly `2`.
  - `test_sigpipe_broken_pipe_handling`: Invokes `snslice` piped to `head -n 1`; asserts exit code `2` via checked stdio `EPIPE` without signal crash.
- **Quality Floor & Manifest Synchronization:**
  - `test_quality_floor_clean_build`: Asserts `snslice` compiles cleanly under GCC and Clang with zero warnings.
  - `test_sanitizers_clean`: Runs test suite under ASan and UBSan verifying zero defects.
  - `test_user_journeys_manifest_sync`: Asserts `journeys/user_journeys_manifest.json` and `tests/user_journeys_manifest.json` exist and are identical parsed objects.
  - `test_user_journeys_schema_compliance`: Validates manifest against `USER_JOURNEYS_MANIFEST_SCHEMA`.
  - `test_user_journeys_coverage_completeness`: Asserts that all acceptance criteria AC-1 through AC-3 are referenced in journey `traces_to` fields, and all 21 repository baseline user journeys are preserved.

---

## Verification

Verification of `snslice` is an exhaustive, deterministic, evidence-producing protocol. Every gate must be executed systematically, and exact commands, compiler invocations, test counts, and exit codes must be documented in verification artifacts.

### 1. Deterministic Verification Gates

1. **Strict Multi-Compiler Compilation:**
   Compile `src/snslice.c` with zero warnings and zero errors under both GCC and Clang:
   ```bash
   gcc -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 -O2 -o /tmp/snslice-gcc src/snslice.c
   clang -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 -O2 -o /tmp/snslice-clang src/snslice.c
   ```
2. **Static Analysis Gate:**
   - Formatting check:
     ```bash
     clang-format --dry-run --Werror src/snslice.c
     ```
   - Clang-Tidy static linter:
     ```bash
     clang-tidy src/snslice.c -- -std=c17 -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64
     ```
   - Cppcheck static code analysis:
     ```bash
     cppcheck --enable=warning,style,performance,portability --error-exitcode=1 --std=c17 -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 src/snslice.c
     ```
   - Clang Static Analyzer:
     ```bash
     clang --analyze -Xanalyzer -analyzer-output=text -Werror -std=c17 -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 src/snslice.c
     ```
3. **Dynamic Memory and Sanitizer Verification:**
   - AddressSanitizer (ASan) with leak detection:
     ```bash
     clang -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 -fsanitize=address -fno-omit-frame-pointer -g -O1 -o /tmp/snslice-asan src/snslice.c
     ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 python3 -m pytest -p no:cacheprovider tests/test_snslice.py
     ```
   - UndefinedBehaviorSanitizer (UBSan):
     ```bash
     clang -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 -fsanitize=undefined -fno-omit-frame-pointer -g -O1 -o /tmp/snslice-ubsan src/snslice.c
     UBSAN_OPTIONS=halt_on_error=1 python3 -m pytest -p no:cacheprovider tests/test_snslice.py
     ```
   - Valgrind Memcheck:
     ```bash
     gcc -std=c17 -Wall -Wextra -Wpedantic -Werror -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 -g -O1 -o /tmp/snslice-valgrind src/snslice.c
     valgrind --leak-check=full --show-leak-kinds=all --track-fds=yes --error-exitcode=1 /tmp/snslice-valgrind --help
     ```
4. **Dedicated Pytest Execution:**
   Execute the dedicated regression test suite with cache generation disabled:
   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_snslice.py -v
   ```
5. **Full Repository Quality Floor and Smoke Verification:**
   Run the repository's aggregate quality and smoke verification suites:
   ```bash
   make clean && make quality
   ./scripts/smoke.sh
   ```
6. **Workspace Cleanliness Audit:**
   Ensure no untracked binaries, caches, or temporary directories remain in the git tree:
   ```bash
   git status --short
   git diff --check
   ```

### 2. User Simulation and Smoke Evidence

1. **Smoke Evidence Protocol:**
   The repository smoke harness verifies core functionality:
   - Invocations of `snslice --help` and `snslice --version` verifying status `0` and exact stdout byte outputs.
   - Slicing a sample NDJSON log fixture with `--records 5` and verifying that output chunks parse cleanly.
   - Slicing a multiline CSV fixture with `--bytes 2000` and verifying record integrity.
   - Invoking `snslice` with invalid arguments to confirm status `2` and sanitized diagnostic emission.
2. **End-to-End User Simulation Script:**
   An automated user journey simulation executes realistic operator scenarios:
   - Scenario 1: Data ingestion pipeline consumes a 50 MB NDJSON server log stream via stdin and partitions it into 5 MB chunks, verifying that downstream `jq` can parse every individual chunk.
   - Scenario 2: Data engineer partitions a customer address export containing multiline quoted address fields, verifying that row counts across all sliced chunk files match the original database export row count.
   - Scenario 3: Automated job encounters a pre-existing chunk file; verifies immediate fail-closed termination with `OUTPUT_COLLISION` without data loss.

### 3. Independent Review Protocol

Independent craftsmanship and architectural review verifies the slice against all normative contract boundaries:
1. **Contract Traceability:** Verify that all three acceptance checks `AC-1`, `AC-2`, and `AC-3` are fully satisfied in source code and backed by regression tests.
2. **RFC 4180 State Machine Verification:** Audit quote transitions, escaped quote pairs, and delimiter recognition logic to confirm multiline record safety.
3. **Memory and I/O Audit:** Confirm $O(1)$ resident memory, fixed 64 KiB buffer usage, absence of dynamic buffer reallocation, and single-owner descriptor cleanup.
4. **Atomicity and Security Audit:** Confirm `O_CREAT | O_EXCL` flags, safe path formatting without buffer overflows, diagnostic sanitization of hostile control bytes, and transactional unlinking of partial chunks.
5. **Quality Gate Verdict:** Require zero warnings across GCC, Clang, clang-tidy, cppcheck, ASan, UBSan, and Valgrind memcheck.

---

## Risks

The implementation of `snslice` handles hostile, malformed, or massive data streams. The table and detailed sections below establish the key technical risks and their deterministic architectural mitigations:

| # | Risk Description | Severity | Concrete Architectural Mitigation |
|---|---|---|---|
| **1** | Multiline Quoted CSV Field Splitting | Critical | RFC 4180 finite state machine treats embedded newlines inside balanced quotes as literal field bytes; chunk boundaries cut strictly on complete record boundaries outside quotes. |
| **2** | Memory Exhaustion on Massive Streams | High | Fixed 64 KiB streaming buffer (`SNSLICE_IO_BUFFER_SIZE = 65536`) with zero heap buffering of full streams or chunks; guarantees constant O(1) resident memory. |
| **3** | Oversized Record Denial-of-Service | High | Hard compile-time record length limit `SNSLICE_MAX_RECORD_BYTES = 16777216` (16 MiB); streams exceeding limit abort fail-closed with `RECORD_LENGTH_LIMIT`. |
| **4** | Output Collision and Data Overwrite | High | Atomically create chunk files via `open(path, O_CREAT \| O_EXCL \| O_WRONLY, 0644)`; existing target aborts fail-closed with `OUTPUT_COLLISION` without file mutation. |
| **5** | Corrupted Partial Chunk Lingering on Failure | High | Centralized transactional cleanup closes and immediately unlinks (`unlink()`) the active partial chunk on any error or signal; prior closed chunks remain intact. |
| **6** | Path Traversal via `--prefix` or `--out-dir` | High | Prefix validation rejects `/` and `..`; output directory validated with `stat()`; chunk path construction uses `snprintf` with strict `PATH_MAX` bounds checking. |
| **7** | Integer Overflow in Chunk Counters | Medium | Threshold parsing uses `strtoull` with `SIZE_MAX` bounds and `ERANGE` checking; arithmetic increments checked against integer overflow. |
| **8** | Terminal Escape Sequence Injection via Stderr | Medium | All untrusted strings passed to diagnostics pass through `snslice_sanitize_string`, escaping non-printable ASCII, `"`, and `\` into hexadecimal `\xHH`. |
| **9** | Abrupt Process Termination via Broken Pipes | Medium | Process unconditionally installs `signal(SIGPIPE, SIG_IGN)` at entry; broken stdout pipe surfaces as checked stdio `EPIPE` returning exit status `2`. |
| **10** | Resource and File Descriptor Leaks on Error | Medium | Single-owner execution context maintains at most two open descriptors (`input_fd`, `active_chunk_fd`); single exit cleanup releases all descriptors on all return paths. |

### 1. Multiline Quoted CSV Field Splitting and State Desynchronization
- **Risk:** Standard coreutils tools split CSV files on physical newline characters (`\n`), severing multiline records (e.g. fields containing embedded newlines or quotes) into disjoint files and corrupting downstream parsers.
- **Mitigation:** `snslice` implements a dedicated RFC 4180 finite state machine. Inside quoted fields (`CSV_STATE_QUOTED`), newline characters (`\n` and `\r\n`) and commas (`,`) are recognized purely as field content and never trigger record boundaries. Chunk splitting occurs exclusively at true record boundaries outside quoted fields.

### 2. Memory Exhaustion via Massive Streams or Deep JSON Payloads
- **Risk:** Ingesting multi-gigabyte or terabyte streams into general-purpose parsers (e.g. `jq` or Python) allocates entire ASTs in heap memory, causing Linux OOM killer termination.
- **Mitigation:** `snslice` never parses JSON into an AST and never loads whole streams into memory. It streams input through a fixed 64 KiB buffer (`SNSLICE_IO_BUFFER_SIZE = 65536`) and maintains an $O(1)$ resident memory footprint across inputs of arbitrary magnitude.

### 3. Giant Record Denial-of-Service Attack
- **Risk:** Malicious or corrupted inputs lacking newline characters could cause a streaming tool to buffer bytes indefinitely, exhausting memory or disk space.
- **Mitigation:** `snslice` enforces an explicit, hard compile-time limit `SNSLICE_MAX_RECORD_BYTES = 16777216` (16 MiB). If any record exceeds 16 MiB without reaching a delimiter, `snslice` immediately aborts fail-closed with diagnostic `snslice: RECORD_LENGTH_LIMIT: record exceeds 16 MiB limit` and exit status `2`.

### 4. Output Collision and Silent File Overwrite
- **Risk:** Concurrent processes or accidental invocations could overwrite existing chunk files, destroying valuable data silently.
- **Mitigation:** Every chunk file is opened with POSIX `open()` using atomic flags `O_CREAT | O_EXCL | O_WRONLY` and mode `0644`. If the file exists, the call fails with `EEXIST` at the kernel level, and `snslice` immediately terminates with `OUTPUT_COLLISION` and status `2`. Pre-existing files are never truncated or modified.

### 5. Corrupted Partial Chunks Lingering After Crash or Disk Full
- **Risk:** If an operational failure occurs mid-write (e.g. disk space exhausted `ENOSPC`), an incomplete, truncated chunk file remains on disk, corrupting downstream processing.
- **Mitigation:** The runtime tracks the active chunk descriptor and filepath in `SnSliceContext`. On any error or operational abort, `snslice_abort_cleanup()` closes the active descriptor and invokes `unlink(active_chunk_path)`, purging the incomplete file. Previously closed chunks remain intact.

### 6. Buffer Truncation or Path Traversal via `--prefix` or `--out-dir`
- **Risk:** Path traversal tokens (`..`) or excessively long prefixes could escape the destination directory or cause buffer overflow during filename formatting.
- **Mitigation:** `--prefix` is strictly validated: any occurrence of `/` or `..` triggers `USAGE_ERROR` and status `2`. Destination directory path length is checked against `PATH_MAX` (`4096`). Chunk path construction uses `snprintf` with explicit return-length checking to ensure no path is ever truncated.

### 7. Integer Overflow in Byte and Record Count Accounting
- **Risk:** Extremely large threshold arguments or counter increments could wrap around integer types, leading to premature or skipped chunk cuts.
- **Mitigation:** All thresholds and counters are represented as unsigned 64-bit integers (`size_t` / `uint64_t`). Threshold arguments are parsed using `strtoull` with strict range checks against `SIZE_MAX`. Additive metrics are checked before addition to prevent overflow.

### 8. Terminal Control Sequence Injection via Stderr Diagnostics
- **Risk:** Malicious filenames or input bytes containing ANSI escape sequences could compromise operator terminal emulators when printed to stderr.
- **Mitigation:** All diagnostic strings pass through `snslice_sanitize_string()`. Characters outside printable ASCII (`0x20`–`0x7E`), double quotes (`"`), and backslashes (`\`) are converted to uppercase hexadecimal sequences (`\xHH`), preventing escape sequence injection.

### 9. Abrupt Process Termination via Broken Pipes (`SIGPIPE`)
- **Risk:** When piped to downstream consumers that exit early (e.g. `head -n 10`), the default `SIGPIPE` signal terminates the process abruptly without running cleanup handlers and leaving corrupted chunk files.
- **Mitigation:** `snslice` installs `signal(SIGPIPE, SIG_IGN)` at startup. Output pipe closures surface as checked stdio `EPIPE` errors, triggering clean transactional teardown and exit status `2`.

### 10. Resource and File Descriptor Leaks on Operational Error Paths
- **Risk:** Early return paths during parsing or file I/O could leak open file descriptors or allocated buffers.
- **Mitigation:** `snslice` maintains at most two open file descriptors (`input_fd` and `active_chunk_fd`). A centralized exit routine guarantees that both descriptors are cleanly closed on all success and error return paths.
