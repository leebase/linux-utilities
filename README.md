# sysdiff

`sysdiff` 0.1.0 is a small, auditable C17 command-line utility for comparing
explicit system snapshot files. It reads two user-provided plain-text
`key=value` snapshots, validates them fully, and prints a deterministic diff
sorted by key.

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

## Build and verify

Build only the executable:

```sh
make sysdiff
```

The executable is written to `build/sysdiff`. The default compiler is `cc`; set
`CC` to select another C compiler.

Run the release quality gate:

```sh
make quality
```

It runs strict GCC and Clang checks, clang-format, clang-tidy, cppcheck,
fixture and pytest suites, AddressSanitizer, UndefinedBehaviorSanitizer, and
Valgrind. Ubuntu CI runs the same command.

For the individual functional checks:

```sh
python3 -m pytest tests/ -q
bash tests/test_sysdiff_fixture.sh
./scripts/smoke.sh
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

Blank lines, including lines made only of spaces and tabs, and lines whose first
non-space character is `#` are ignored.
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

## Project documents

- [Snapshot format specification](docs/sysdiff-snapshot-format-and-scope.md)
- [Design decisions](docs/DECISIONS.md)
- [Release notes](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [AI-assisted development safeguards](docs/AI_DEVELOPMENT.md)
