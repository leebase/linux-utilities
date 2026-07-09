# Snapshot Format Decision

## Snapshot Format

`sysdiff` format `1` snapshots are deterministic plain-text byte streams made
of one resource record per line, encoded as `key=value`. Blank lines and
whole-line comments are ignored, the first `=` separates the key from the value,
keys are validated as case-sensitive dot-separated resource names, and values
are opaque bytes after line-ending removal. The comparison command reads exactly
the two snapshot files named by the user, validates both fully, rejects malformed
or duplicate records before producing output, then compares the parsed snapshots
as maps from key to value. Diff output is sorted by bytewise key order across
the union of both key sets, so the same logical snapshots produce the same
stdout regardless of input ordering, host locale, current directory, clock,
environment, or local system state. This decision follows the canonical contract
in `docs/sysdiff-snapshot-format-and-scope.md`.

## Rationale

The selected format keeps the first `sysdiff` slice small, auditable, fixture
friendly, and easy to review with ordinary Unix tools. A narrow line-oriented
text format avoids parser dependencies, hidden runtime behavior, locale-sensitive
collation, and live host inspection while still representing operating system,
kernel, package, service, file-metadata, and snapshot metadata records in a
stable way.
