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
- `2` for usage, file I/O, parse, duplicate-key, allocation, resource-limit,
  stdout write failure, or other runtime errors.

Diagnostics are written to stderr. Diff output and the `no changes` result are
written to stdout. Validation failures leave stdout empty. A stdout write or
flush failure on compare or informational output (`--help`, `--version`, or
no-argument usage) returns `2` with a `stdout write error: <strerror>`
diagnostic (using `EIO` when errno is unset) and may leave partial stdout.
On Linux, `SIGPIPE` is ignored so a closed stdout pipe becomes an `EPIPE`
stdio failure on that same path instead of terminating the process.

## Build and verify

Build the executable with the default target:

```sh
make
```

`make sysdiff` is an alias for the same build. The executable is written to
`build/sysdiff`. The default compiler is `cc`; set `CC` to select another C
compiler.

Run the functional test suite:

```sh
make test
```

Run the canonical full release quality gate:

```sh
make quality
```

`make check` is an alias for `make quality`. The quality gate runs strict GCC
and Clang checks, clang-format, clang-tidy, cppcheck (findings fail the build),
fixture and pytest suites, AddressSanitizer, UndefinedBehaviorSanitizer, and
Valgrind with a reserved error status that cannot collide with sysdiff exit
codes `0`, `1`, or `2`. Ubuntu CI runs exactly `make quality`.

For individual functional checks:

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

Resource limits per snapshot input are 65,536 bytes per line, 65,536 entries,
and 16 MiB total bytes read (including newlines, comments, and blank lines).

For changed snapshots, output is deterministic and sorted by key across both
files:

```text
- removed.key=old value
+ added.key=new value
~ changed.key: old value -> new value
```

Snapshot bytes remain opaque for comparison. Diff keys render unchanged. Diff
values and user-controlled paths or command arguments in diagnostics render as
printable ASCII: bytes `0x20`–`0x7e` except backslash are literal, backslash is
`\\`, and every other byte is uppercase `\xNN`.

For identical snapshots, stdout is exactly:

```text
no changes
```

## Project documents

- [Snapshot format specification](docs/sysdiff-snapshot-format-and-scope.md)
- [Design decisions](docs/DECISIONS.md)
- [Release notes](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [AI-assisted development safeguards](docs/AI_DEVELOPMENT.md)

## License

MIT License. Copyright (c) 2026 Lee Harrington. See [LICENSE](LICENSE).
