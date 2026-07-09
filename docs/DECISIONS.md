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
checked for duplicate keys before diff output is written. Compare failures use
exit status `2` and leave stdout empty.

### Opaque Values

Values are compared byte-for-byte. `sysdiff` does not normalize versions,
paths, booleans, whitespace, Unicode, timestamps, package names, or service
states.

### Narrow Key Validation

Format `1` keys are case-sensitive dot-separated names using only documented
safe bytes. They must contain at least one dot and must not contain spaces,
tabs, `=`, traversal-like `..` segments, a leading `/`, or a trailing `.`.

### Deterministic Resource Limits

The C implementation defines explicit maximums for line bytes and snapshot
entries. Exceeding a limit is an error, not truncation.

### Single Small C Executable

The current implementation remains one C17 source file built by `make`. This is
intentional while the command surface is small and the main need is auditability.

### Strict Local Quality Gates

The project treats warnings, unsafe input handling, undefined behavior, unclear
ownership, and missing deterministic tests as defects. The build and test
surface is centered on strict GCC/Clang builds, fixture tests, smoke tests,
sanitizers, Valgrind when available, and static-analysis-oriented follow-up
work.

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
design validates both snapshots first.

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
rely on empty stdout for compare errors and can separate diagnostics from diff
data. Deterministic resource limits make hostile input behavior predictable
instead of depending on memory pressure.

Keeping the implementation as a small C17 executable matches the repository
mission: small Linux utilities with minimal dependencies, strict warning-free
builds, and auditable ownership. Future slices may split modules or add capture
features only after the explicit snapshot comparison contract and quality gates
remain stable.
