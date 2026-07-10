# sysdiff Snapshot Format and Scope

## Overview

This document is the durable contract for the first release-oriented `sysdiff`
slice. It defines the explicit snapshot file format, deterministic comparison
rules, initial resource scope, non-goals, compatibility expectations, security
constraints, and acceptance checks.

This slice is documentation-only. It describes behavior for an implementation
worker to build against; it does not require source, tests, scripts, Makefile,
or playbook changes in this step.

## Release Slice

The first `sysdiff` release slice compares two user-provided snapshot files:

```sh
sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT
```

`sysdiff` reads only the two paths named on the command line. It does not scan
the running system, discover files, inspect package databases, call service
managers, write snapshots, or persist state.

The comparison result is a deterministic line-oriented diff over named resource
records. The same two logical snapshots must produce the same stdout regardless
of input record order, host locale, current directory contents, wall clock time,
user id, or environment variables.

## Snapshot Format

Snapshot files are plain text byte streams. The format is intentionally narrow:
one resource record per line, encoded as `key=value`.

Example:

```text
# sysdiff snapshot v1
os.id=debian
os.version_id=12
kernel.release=6.1.0-21-amd64
package.openssh-server.version=1:9.2p1-2+deb12u3
service.ssh.enabled=true
file./etc/ssh/sshd_config.sha256=3b7f6f...
```

### Line Handling

- A line is terminated by `\n` or by end of file.
- A single trailing `\r` before `\n` is part of the line ending and is removed.
- A final line without a trailing newline is valid.
- Empty lines, including lines made only of spaces and tabs, are ignored.
- Lines whose first byte after leading spaces or tabs is `#` are comments and
  are ignored.
- Inline comments are not supported. A `#` byte inside a key or value is data.
- Horizontal spaces before a comment marker are ignored only for comment
  detection. Spaces are otherwise data.

### Record Syntax

Each non-empty, non-comment line is one record:

```text
KEY=VALUE
```

Rules:

- The first `=` byte separates key from value.
- The key must be non-empty.
- The value may be empty.
- Keys are not trimmed.
- Values are not trimmed.
- Duplicate keys within one snapshot are invalid.
- A line with no `=` separator is invalid.
- A line whose first byte is `=` is invalid because the key is empty.
- Embedded NUL bytes are invalid.

### Key Syntax

Keys identify resources. A key is a dot-separated resource name:

```text
RESOURCE.FIELD
```

Valid format `1` keys:

- Must use only these bytes: `A-Z`, `a-z`, `0-9`, `.`, `_`, `-`, and `/`.
- Must contain at least one `.` separator.
- Must not contain spaces or tabs.
- Must not contain `=`.
- Must not contain `..` as a path traversal segment.
- Must not begin with `/`.
- Must not end with `.`.
- Are case-sensitive.

The first release slice documents these top-level resource prefixes:

- `os.` for operating system release fields.
- `kernel.` for kernel identity fields.
- `package.` for installed package records supplied by the snapshot.
- `service.` for service records supplied by the snapshot.
- `file.` for explicit file metadata records supplied by the snapshot.
- `sysdiff.` for metadata about the snapshot itself.

Unknown valid keys may be compared as opaque data for forward compatibility,
but release fixtures for this slice must stay within the documented prefixes
above.

The `file.` namespace describes explicit file metadata as data inside the
snapshot. It does not authorize `sysdiff` to open those named files. For
example, `file./etc/passwd.sha256=...` is a record key, not a path to read.

### Value Syntax

Values are opaque byte strings after line-ending removal, subject to the safety
limits below.

Rules:

- Values are compared byte-for-byte.
- Empty values are valid.
- Spaces and tabs in values are significant.
- A `#` byte in a value is significant.
- A second `=` byte in a value is significant.
- Values must not contain embedded NUL bytes.

Release fixtures should prefer printable UTF-8-compatible values so expected
output is reviewable in plain text. The comparison contract does not normalize
Unicode, whitespace, timestamps, versions, booleans, paths, or package names.

## Deterministic Comparison

`sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT` compares the two parsed
snapshots as maps from key to value.

Before diffing:

- Both files must be fully opened, read, parsed, and validated.
- Duplicate-key checks must complete for both files.
- No diff output may be written until both snapshots are valid.

Ordering:

- Diff output is sorted by key across the union of keys.
- Sorting is bytewise and locale-independent.
- Sorting must not depend on input order.

For each key in sorted order:

- If the key exists only in `BEFORE_SNAPSHOT`, it is removed.
- If the key exists only in `AFTER_SNAPSHOT`, it is added.
- If the key exists in both snapshots with different values, it is changed.
- If the key exists in both snapshots with identical values, it emits nothing.

## Output Contract

All comparison output goes to stdout. All diagnostics go to stderr.

For removed records:

```text
- key=old value
```

For added records:

```text
+ key=new value
```

For changed records:

```text
~ key: old value -> new value
```

For identical snapshots, stdout is exactly:

```text
no changes
```

Each stdout line ends with `\n`. Changed comparisons emit only diff lines; they
do not include headers, file names, counts, timestamps, colors, terminal escape
sequences, or explanatory prose.

## Exit Status

- `0`: command succeeded and no differences were found, or an informational
  command such as `--help` or `--version` succeeded.
- `1`: `compare` succeeded and at least one difference was found.
- `2`: usage error, file I/O error, malformed snapshot, duplicate key,
  allocation failure, unsafe input, or other runtime error.

On exit status `2`, stdout must be empty for `compare` failures. Stderr must
include enough context to identify the failed argument, path, line, or key.

## Initial Scope

The first release slice tracks only records present in explicit snapshot files.
The documented resource scope is the set of keys in those files that use the
prefix list above. Unknown valid keys may still be compared as opaque data, but
they are outside the acceptance fixture scope for this slice.

Fixture authors may use these fields:

- `sysdiff.snapshot_version`: snapshot contract version, expected value `1`.
- `os.id`: operating system identifier from a fixture source.
- `os.version_id`: operating system version identifier from a fixture source.
- `kernel.release`: kernel release string from a fixture source.
- `package.NAME.version`: package version for package `NAME`.
- `package.NAME.arch`: package architecture for package `NAME`.
- `service.NAME.enabled`: `true`, `false`, or an empty value if unknown.
- `service.NAME.active`: `true`, `false`, or an empty value if unknown.
- `file.PATH.type`: `regular`, `directory`, `symlink`, `missing`, or unknown
  text supplied by the snapshot.
- `file.PATH.mode`: symbolic or octal mode text supplied by the snapshot.
- `file.PATH.owner`: owner text supplied by the snapshot.
- `file.PATH.group`: group text supplied by the snapshot.
- `file.PATH.size`: decimal byte count text supplied by the snapshot.
- `file.PATH.sha256`: lowercase hex digest text supplied by the snapshot.

`NAME` and `PATH` are part of the key string. `sysdiff` does not parse package
names or file paths in this slice except as bytes used for ordering and
duplicate-key detection.

## Explicit Non-Goals

This slice does not provide:

- Live system snapshot collection.
- Directory recursion.
- General-purpose text diff behavior.
- Binary snapshot files.
- JSON, YAML, SQLite, or compressed snapshot formats.
- Package manager integration.
- systemd, init, or service-manager integration.
- File hashing by `sysdiff`.
- Permission, ownership, or metadata probing by `sysdiff`.
- Network access.
- Background services, scheduled jobs, telemetry, or hidden runtime behavior.
- Snapshot persistence or a local database.
- Semantic version comparison.
- Path normalization.
- Locale-aware collation.
- Colorized or terminal-dependent output.

## Compatibility Rules

The first stable snapshot format version is `1`. A fixture may include:

```text
sysdiff.snapshot_version=1
```

Version handling rules:

- If `sysdiff.snapshot_version` is absent, the file is treated as format `1`.
- If it is present more than once, duplicate-key handling applies.
- If it is present with value `1`, the file is accepted if all other records are
  valid.
- Future implementations may reject unsupported non-`1` values with exit status
  `2`.

Forward compatibility rules:

- Unknown valid keys are data and may be compared.
- Unknown valid values are data and may be compared.
- Existing output line formats, exit statuses, and duplicate-key behavior must
  remain stable for format `1`.
- Future format versions must not silently reinterpret format `1` snapshots.
- Future live-capture features must produce records that can be represented in
  this explicit snapshot format or must document a new format version.

Backward compatibility rules:

- A format `1` implementation must not require live host state to compare two
  explicit snapshots.
- A format `1` implementation must not make stdout depend on local package
  manager state, service state, file metadata, timezone, locale, or hostname.
- A format `1` implementation must continue to accept final lines without a
  trailing newline.

## Security Constraints

Snapshot paths and file contents are untrusted.

Path handling:

- Treat `BEFORE_SNAPSHOT` and `AFTER_SNAPSHOT` as opaque command-line paths.
- Do not invoke a shell, expand globs, perform command substitution, or
  interpret path bytes as options after dispatch.
- Open exactly the two named snapshot files for reading.
- Do not create, overwrite, delete, rename, chmod, chown, or execute files.
- Do not recursively walk directories.
- If a supplied path names a directory or unreadable file, fail with exit status
  `2`.
- Diagnostics may include the supplied path, but must not emit terminal escape
  sequences intentionally.

Content handling:

- Reject embedded NUL bytes.
- Reject malformed records before producing diff output.
- Detect allocation and integer-overflow failures.
- Do not silently truncate lines, keys, values, paths, diagnostics, or output.
- Do not use fixed-size input buffers in a way that permits truncation to be
  mistaken for valid data.
- Do not write partial diff output if either snapshot is invalid.
- Do not treat `file.` keys as filesystem paths to inspect.
- Do not interpret values as commands, regular expressions, format strings, or
  paths to open.

Resource limits:

- Implementations may impose documented maximums for line length, key length,
  value length, record count, and total input bytes.
- If a maximum is exceeded, the command must fail with exit status `2`.
- Limits must be deterministic and must fail closed; they must not produce a
  partial comparison.

## Acceptance Checks

A later implementation worker must provide fixture-backed checks for all items
in this section.

Format parsing:

- Accept a valid file containing `sysdiff.snapshot_version=1`.
- Accept a valid file without `sysdiff.snapshot_version`.
- Accept blank lines (including whitespace-only space/tab lines) and whole-line
  comments.
- Accept a final record without trailing newline.
- Accept an empty value such as `service.ssh.active=`.
- Preserve spaces, `#`, and extra `=` bytes inside values.
- Reject a line with no `=`.
- Reject an empty key.
- Reject a key with bytes outside the valid key syntax.
- Reject embedded NUL bytes.
- Reject duplicate keys in one snapshot.

Comparison behavior:

- Report added, removed, and changed records.
- Suppress unchanged records.
- Print exactly `no changes\n` for identical snapshots.
- Return `0` for identical snapshots.
- Return `1` for changed snapshots.
- Return `2` for usage, file, parse, duplicate-key, and unsafe-input errors.
- Keep stdout empty on `compare` errors.

Determinism:

- Prove that different input order produces identical diff output.
- Prove that output is sorted by bytewise key order.
- Prove that comments and blank lines do not affect output.
- Prove that host locale and timezone are not required by the tests.
- Prove that acceptance fixtures cover `os.`, `kernel.`, `package.`,
  `service.`, `file.`, and `sysdiff.` keys.

Security and hostile input:

- Missing snapshot path returns `2` with contextual stderr.
- Directory path returns `2` with contextual stderr.
- Malformed before snapshot returns `2` and writes no stdout.
- Malformed after snapshot returns `2` and writes no stdout.
- Duplicate key in either snapshot returns `2` and writes no stdout.
- A `file.` key that looks like an absolute path is treated as data and does
  not cause `sysdiff` to open that file.

Documentation consistency:

- README or user documentation names the compare command.
- User documentation states that this slice compares explicit snapshots only.
- Architecture documentation preserves the separation between parsing,
  comparison, and output formatting.
- No documentation for this slice promises live system capture.
