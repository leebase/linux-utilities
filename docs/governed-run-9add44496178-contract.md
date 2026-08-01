# Governed Run `9add44496178` Rendering Repair Contract

## Overview

This document is the normative FRAME artifact for the narrowly scoped
`sysdiff` rendering repair recovered from governed run `9add44496178`. It
closes the long-recorded format-1 presentation defect in which opaque values
can visually reproduce the changed-record separator. It does not reclassify
the failed origin run as passed, finish or repair `openunlink`, or authorize a
new `sysdiff` feature. Existing snapshot parsing, bytewise comparison, key
ordering, limits, diagnostics, commands, and status meanings remain in force.
For all values that do not contain the raw byte sequence described below, the
observable comparison output remains byte-for-byte compatible with the
current `+ key=value`, `- key=value`, and `~ key: old -> new` surface.

## Problem

Format 1 currently renders every printable value byte literally, including a
value's four-byte ASCII sequence ` -> `. A changed line such as
`~ demo.key: a -> b -> c\n` consequently has two valid interpretations:
old `a` with new `b -> c`, or old `a -> b` with new `c`. Escaping backslashes
and unsafe bytes does not resolve this printable delimiter collision, and an
old value ending in the three raw bytes ` ->` can form the same collision with
the separator's leading space. The repair must make the one fixed old/new
separator mechanically unique without changing the raw bytes used for
comparison, rejecting formerly valid input, or replacing the approved
human-readable changed-line shape.

## CLI Surface

The observable command surface stays closed at `sysdiff`, `sysdiff --help`,
`sysdiff --version`, and
`sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`. No arguments and sole
`--help` write exactly
`usage: sysdiff --help|--version|compare BEFORE_SNAPSHOT AFTER_SNAPSHOT\n`
to stdout and return `0`; sole `--version` writes exactly
`sysdiff 0.1.0\n` to stdout and returns `0`. `compare` requires exactly two
explicit snapshot paths. Bad arity and unknown commands remain usage errors
on stderr with empty stdout and status `2`. This repair adds no option,
environment variable, configuration file, alternate format selector, live
capture path, or machine-readable output mode.

Successful comparison output remains sorted by bytewise key order and uses
exactly these newline-terminated forms, where `VALUE`, `OLD`, and `NEW` use
the value-rendering rule below:

```text
+ key=VALUE
- key=VALUE
~ key: OLD -> NEW
no changes
```

The first three forms are diff records; `no changes\n` is emitted alone only
when the validated maps are identical. There are no headers, path names,
counts, timestamps, colors, terminal controls, or explanatory lines.

Value rendering is byte-oriented and deterministic. Backslash (`0x5C`)
renders as `\\`; any byte outside printable ASCII `0x20` through `0x7E`
renders as uppercase `\xNN`; other printable bytes normally render literally.
The sole added rule is delimiter shielding: when a raw value contains the
three consecutive bytes space, hyphen, greater-than (`0x20 0x2D 0x3E`, shown
as ` ->`), that greater-than byte renders as `\x3E`. This applies to values in
added, removed, and changed records, including ` ->` at the end of a value and
every occurrence in a value. Thus raw `left -> right` renders as
`left -\x3E right`, while raw unspaced `left->right` is unchanged. Diagnostic
argument and path escaping is not altered by this repair.

For example, old `a` and new `b -> c` render exactly as
`~ demo.key: a -> b -\x3E c\n`; old `a -> b` and new `c` render exactly as
`~ demo.key: a -\x3E b -> c\n`. A rendered value can therefore contain no
literal ` ->` prefix, including one completed across the old-value boundary,
and the changed line contains exactly one literal ` -> ` separator. Because a
raw backslash is still doubled, decoding `\x3E` is lossless and cannot be
confused with an input spelling of backslash followed by `x3E`.

## Exit Statuses

The exit-status contract remains exactly `0`, `1`, or `2`. Status `0` means an
informational command succeeded or both valid snapshots compare equal; equal
snapshots write exactly `no changes\n` and empty stderr. Status `1` means both
snapshots were fully validated and at least one added, removed, or changed
record was emitted; stderr is empty on this successful diff path. Status `2`
means usage, open/read/close, malformed input, duplicate key, allocation,
resource-limit, unsafe-input, stdout write/flush, or other operational failure.
Validation failures occur before diff emission and leave stdout empty. A
stdout failure may leave a partial line or prior lines, emits the established
`sysdiff: stdout write error: <strerror>\n` diagnostic, and returns `2`;
ignored `SIGPIPE` continues to route a closed pipe through the same EPIPE path.
Delimiter shielding itself never changes whether a comparison returns `0` or
`1`.

## Hazard Taxonomy

For this contract, “hazard” is a closed observable diff classification, not a
security severity or permission-policy judgment. `ADDED` is a key present only
after comparison and is represented solely by the `+ ` prefix. `REMOVED` is a
key present only before comparison and is represented solely by the `- `
prefix. `CHANGED` is a key present in both maps with byte-different values and
is represented solely by the `~ ` prefix plus the unique old/new separator.
An unchanged key is suppressed and is not a fourth hazard; when every key is
unchanged the sole clean summary is `no changes`. Parse and operational errors
are failures, not hazards, and must not invent a diff record. No additional
prefix, named code, severity, policy interpretation, or hazard family may be
introduced by this repair.

## Acceptance Checks

Acceptance requires exact byte oracles, not substring-only checks. A dedicated
regression must construct the formerly colliding pairs `(old=a, new=b -> c)`
and `(old=a -> b, new=c)` and prove they now produce the two distinct lines
shown in CLI Surface, each with exactly one literal ` -> ` separator. Focused
cases must also cover the sequence in both old and new values, multiple
occurrences, an old value ending exactly in ` ->`, added and removed values,
a raw unspaced `->` that remains literal, a raw `\x3E` spelling whose
backslash remains doubled, empty values, and an identical snapshot containing
the sequence that still returns `0` with `no changes\n`. An independent test
decoder should split a changed line at its sole separator, undo `\\` and
uppercase `\xNN`, and recover the original old and new byte strings.

The regressions must also prove that ordinary values preserve every existing
golden, key order remains bytewise and input-order independent, comparison is
still raw rather than display-based, and ESC, tab, CR, backslash, DEL, and
non-ASCII bytes remain terminal-safe. Existing status `0`/`1`/`2`, empty
stdout on validation errors, `/dev/full`, closed-pipe/EPIPE, resource-limit,
LF/CRLF, malformed-input, fixture, and smoke checks must continue to pass.
Verification must include a strict C17 warnings-as-errors compile with GCC and
Clang when available, the focused governed regression module, the existing
sysdiff pytest and shell fixture suites, formatting and applicable static
analysis, ASan/UBSan, Valgrind, and the pinned aggregate smoke path. No check
may call a skipped or uncollected test set a pass.

## Non-Goals

This repair does not add snapshot version 2, JSON, CSV, NUL-delimited output,
length-prefixed fields, quoted records, a general interchange parser, live
system collection, directory traversal, package or service inspection,
filtering, policy evaluation, remediation, persistence, networking, telemetry,
or background work. It does not change valid key syntax, comment/blank-line
handling, LF/CRLF normalization, duplicate rejection, bytewise sorting,
resource ceilings, ownership, allocation, stdout failure semantics, help or
version bytes, installation paths, packaging, tags, publication, or release
claims. It does not repair unrelated `pathaudit`, `permguard`, or `openunlink`
findings and does not convert origin run `9add44496178` into a passed delivery.
Diagnostic text remains on its established escaping rules; the only product
behavior change authorized here is delimiter shielding while rendering
snapshot values in existing sysdiff diff records.
