# Linux Utilities

Small, auditable Linux utilities built under the autonomous
`linux-utilities` mission.

## Description

The first utility is `sysdiff`: a lightweight C program for comparing
explicit system snapshot files. The snapshot comparison feature delivered by
the current slice is `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`, which
reads two user-provided plain-text `key=value` snapshots, validates them, and
prints a deterministic diff sorted by key.

This slice is intentionally narrow. It compares only explicit snapshot files in
the supported format; it is not a replacement for `diff(1)`, does not scan
directories, does not persist snapshots, and does not perform live system
capture.

## Usage

Show help or version information:

```sh
./build/sysdiff --help
./build/sysdiff --version
```

Compare two snapshot fixture files:

```sh
./build/sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT
```

The compare command exits with:

- `0` when the command succeeds and no differences are found.
- `1` when the command succeeds and at least one difference is found.
- `2` for usage, file I/O, parse, duplicate-key, allocation, or other runtime
  errors.

Diagnostics are written to stderr. Diff output and the `no changes` result are
written to stdout.

## Building

Build the executable from the repository root:

```sh
make
```

The build writes the utility to `build/sysdiff`. The default build uses the
configured `CC` with strict C17 warning flags.

Run the current tests from the repository root:

```sh
make test
bash tests/test_sysdiff_fixture.sh
./scripts/smoke.sh
```

For broader local checks, use:

```sh
make make-quality
```

## Snapshot Format

The durable snapshot-format contract for the initial `sysdiff` vertical slice
is [docs/sysdiff-snapshot-format-and-scope.md](docs/sysdiff-snapshot-format-and-scope.md).
Treat that document as the implementation source of truth for snapshot syntax,
deterministic comparison output, exit statuses, resource scope, non-goals,
security constraints, compatibility rules, and acceptance checks. This README
is only a quick usage summary of the current fixture-backed behavior.

Snapshot fixtures are plain text files using one `key=value` entry per line:

```text
# optional comment
entry.name=value
another.entry=some value
empty.value=
```

Blank lines and lines whose first non-space character is `#` are ignored.
Keys are compared byte-for-byte and are not trimmed. Values are compared
byte-for-byte after the trailing line ending is removed. Duplicate keys in one
snapshot are errors.

For changed snapshots, output is deterministic and sorted by key across both
files:

```text
- removed.key=old value
+ added.key=new value
~ changed.key: old value -> new value
```

For identical snapshots, stdout is exactly:

```text
no changes
```

## Tool Availability Check

Before authoring or launching governed Agent-Orch work, use the repository-local
tool availability check to confirm that the routed worker harnesses expected by
this project are discoverable on `PATH`:

```sh
python3 scripts/check_tools.py
```

The script currently verifies `codex_cli` for the `implementation_worker` route
through the `codex` executable and `claude_code` for the `slice_reviewer` route
through the `claude` executable. It is a read-only local preflight: it reports
missing routed worker infrastructure early, but it does not launch workflows,
start model sessions, install tools, repair routes, contact the network, or
change `sysdiff` behavior. See
[docs/tool-availability-check.md](docs/tool-availability-check.md) for usage,
output, exit status, and limitation details.

## Engineering Standard

- One executable per utility.
- Plain C, preferably C17 or C23.
- Minimal dependencies.
- `make` first; CMake only when it clearly simplifies the project.
- Automated quality gates for compiler warnings, formatting, static analysis,
  sanitizers, Valgrind, unit tests, integration tests, regression tests, and
  fixtures.
