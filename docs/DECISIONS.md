# sysdiff Decisions

## Design Decisions

### Explicit Snapshot Comparison Only

The first `sysdiff` slice compares two user-provided snapshot files:

```sh
sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT
```

`sysdiff` does not capture live system state, walk directories, inspect package
databases, query service managers, hash files, persist snapshots, or run
background tasks.

### Plain Text `key=value` Format

Snapshot format `1` is a line-oriented plain text format with one `KEY=VALUE`
record per line. Keys identify resources and values are opaque bytes after
line-ending removal.

### Deterministic Map Diff

Snapshots are parsed as maps from key to value. Records are sorted by bytewise
key order before comparison. Output is independent of input record order, host
locale, timezone, current directory contents, environment variables, and user
identity.

### Validate Before Output

Both snapshots must be fully opened, read, parsed, validated, sorted, and
checked for duplicate keys before diff output is written. Compare validation
failures use exit status `2` and leave stdout empty. Stdout write or flush
failures also use status `2` with a `stdout write error: <strerror>` diagnostic
(`EIO` when errno is unset) and may leave partial stdout. Informational stdout
paths (`--help`, `--version`, and no-argument usage) use the same rule. On
Linux, `SIGPIPE` is ignored so a closed stdout pipe becomes `EPIPE` instead of
process termination.

### Opaque Values With Safe Display Escaping

Values are compared byte-for-byte. `sysdiff` does not normalize versions,
paths, booleans, whitespace, Unicode, timestamps, package names, or service
states. Display rendering escapes non-printable and non-ASCII value bytes, and
the same escaping applies to user-controlled paths and command arguments in
diagnostics. Trusted fixed diagnostic text and `strerror` messages print
normally.

### Narrow Key Validation

Format `1` keys are case-sensitive dot-separated names using only documented
safe bytes. They must contain at least one dot and must not contain spaces,
tabs, `=`, traversal-like `..` segments, a leading `/`, or a trailing `.`.

### Deterministic Resource Limits

The C implementation defines explicit maximums for line bytes (65,536),
snapshot entries (65,536), and total snapshot bytes read (16 MiB), counting
every byte including newlines, comments, and blank lines. Exceeding a limit is
an error, not truncation.

### Single Small C Executable

The current implementation remains one C17 source file built by `make`. This is
intentional while the command surface is small and the main need is auditability.

### Strict Local Quality Gates

The project treats warnings, unsafe input handling, undefined behavior, unclear
ownership, and missing deterministic tests as defects. Default `make` builds
`build/sysdiff`. `make test` runs the functional suite. `make quality` (aliased
by `check`) is the canonical full release gate: strict GCC/Clang, clang-format,
clang-tidy, cppcheck with failing findings, fixtures, pytest, ASan, UBSan, and
Valgrind using reserved error status `99`.

### v0.1.0 Release Contract

The first public release is version `0.1.0`. Its stable command surface is
`--help`, `--version`, and `compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`; its stable
comparison lines are `+ key=value`, `- key=value`, and
`~ key: old -> new`. The release intentionally leaves values opaque, so the
changed-line delimiter is presentation rather than a reversible serialization.

### Whitespace-Only Lines Are Blank

Format `1` ignores a line that contains only horizontal spaces and tabs, just
as it ignores an empty line. Leading horizontal whitespace before a comment is
used only to identify a whole-line comment; whitespace in records remains data.

## Alternatives Considered

### Live System Capture

`sysdiff` could have collected system facts directly from `/etc`, package
manager databases, service managers, and file metadata. This was rejected for
the first slice because it would add privilege, portability, dependency, and
host-state concerns before the comparison contract is proven.

### General Text Diff

The utility could compare arbitrary files like `diff(1)`. This was rejected
because the goal is a deterministic system-state record comparison, not a
general-purpose line diff.

### JSON, YAML, SQLite, or Binary Snapshots

Structured or binary formats could represent richer data. They were rejected
for the initial format because they add parser surface, dependency pressure, or
review complexity. Plain `key=value` records are enough for the first auditable
slice.

### Semantic Value Interpretation

The comparator could understand package versions, booleans, service state,
paths, file modes, or hashes. This was rejected for format `1`; values remain
opaque so comparison behavior is simple, predictable, and fixture-friendly.

### Locale-Aware or Natural Sorting

Human-friendly sort orders were considered unnecessary. Bytewise key ordering
is easier to specify, test, and reproduce across hosts.

### Emitting Partial Results Before Full Validation

Streaming diff output while reading snapshots could reduce memory use, but it
would make error handling and no-partial-output guarantees harder. The current
design validates both snapshots first. Output I/O failures after validation are
the only path that may leave partial stdout.

### Runtime Dependencies

Additional libraries or helper processes could reduce some implementation work.
They were rejected for this slice to preserve a small C source surface and keep
the utility easy to build and inspect.

## Rationale

The design favors trust and repeatability over feature breadth. Explicit input
files make behavior testable without special privileges or host-specific state.
Plain text records keep fixtures reviewable. Bytewise sorting and opaque values
make output deterministic and avoid hidden policy decisions.

Validating both snapshots before output keeps failure behavior clean: users can
rely on empty stdout for validation errors and can separate diagnostics from
diff data. Deterministic resource limits make hostile input behavior predictable
instead of depending on memory pressure. Safe display escaping keeps terminals
and logs free of raw control bytes from untrusted snapshot content.

Keeping the implementation as a small C17 executable matches the repository
mission: small Linux utilities with minimal dependencies, strict warning-free
builds, and auditable ownership. Future slices may split modules or add capture
features only after the explicit snapshot comparison contract and quality gates
remain stable.
