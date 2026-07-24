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
At startup, `SIGPIPE` is ignored (POSIX) so a closed stdout pipe becomes an
`EPIPE` stdio failure on that same path instead of terminating the process.
Supported runtime and CI focus is Linux (Ubuntu).

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

`make check` is an alias for `make quality`. The quality gate cleans, then runs
strict GCC and Clang link builds (`-Wall -Wextra -Wpedantic -Werror`),
clang-format, clang-tidy, cppcheck (findings fail the build), the Clang static
analyzer (`clang --analyze` with analyzer findings as errors), man-page lint via
`make man-check`, the shell and pytest suites (unit, integration, regression,
fixture, malformed-input fuzz, and benchmark contract tests), deterministic
benchmark validation (`benchmark-check`, temp-dir JSON only), AddressSanitizer,
UndefinedBehaviorSanitizer, and Valgrind with a reserved error status that
cannot collide with sysdiff exit codes `0`, `1`, or `2`. Ubuntu CI runs exactly
`make quality`.

View the section-1 manual page locally:

```sh
man -l man/sysdiff.1
```

The source is [man/sysdiff.1](man/sysdiff.1). `make man-check` runs groff with
all warnings enabled, fails if groff exits nonzero or emits any warning, prints
captured diagnostics on failure, and does not write tracked output.

For individual functional checks:

```sh
python3 -m pytest tests/ -q
bash tests/test_sysdiff_fixture.sh
./scripts/smoke.sh
```

## Performance Benchmarks

Run the deterministic Linux performance and resource harness with:

```sh
make benchmark
```

That target creates `artifacts/performance/` if needed and invokes
`python3 scripts/benchmark_sysdiff.py --output artifacts/performance/sysdiff-benchmark.json`.
The harness compiles `src/sysdiff.c` in a temporary directory (never the
workspace `build/`), writes fixed before/after snapshots, then samples the
metrics below. Compile and fixture setup are excluded from timed samples.
`SYSDIFF_BIN` and similar environment hints are ignored. Every measured child
must exit with an expected status (`--help` → 0; `compare` → 0 or 1); unexpected
exits fail the harness instead of recording a deceptively fast sample.

**Spawn baseline** (`baseline_ms_median`) is the median milliseconds of
`/bin/true` under the same spawn path, so startup and fixture medians can be
read net of Python fork/exec cost. **Startup time** (`startup_ms_median`) is
the median wall time, in milliseconds, of running the built binary with
`--help`, measured with a monotonic clock around the child only.
**Controlled-fixture runtime** (`fixture_ms_median`) is the median milliseconds
for `compare BEFORE AFTER` against a fixed 8000-entry deterministic snapshot
pair (mix of added, removed, changed, and unchanged `bench.kNNNNNN` keys),
sized so compare work exceeds the spawn floor. **Peak RSS** (`peak_rss_kib`) is
the per-run peak resident set size in kibibytes during that same compare; the
reported value is the maximum across samples. Measurement prefers GNU
`/usr/bin/time -f %M`, then a tiny C fork/exec wrapper that writes RSS and
child exit status to a dedicated report file while redirecting the measured
child's stdout/stderr to `/dev/null` (so compare/`--help` output cannot
collide with the report), so Python's fork-before-exec does not inflate
`ru_maxrss` to interpreter size.

Sampling is fixed: one untimed warmup of baseline, startup, and compare, then
five timed samples (odd count so the median is a single middle value). Release
thresholds fail the run when any gated measurement exceeds its inclusive limit:
`startup_ms_median` ≤ 200 ms, `fixture_ms_median` ≤ 100 ms, and
`peak_rss_kib` ≤ 32768 KiB (32 MiB). The JSON report uses schema version 1
with sorted keys and includes `measurements`, `thresholds`, `samples`,
`metadata` (including `work_dir_kind=tempdir`, not a host path), `passed`, and
`schema_version`. Exit status is 0 when `passed` is true and nonzero on
threshold failure or harness error.

Expect a Linux host with a C compiler (`cc`, `gcc`, or `clang`), Python 3,
and GNU `/usr/bin/time` on `PATH`. Results can vary with CPU load, thermal
throttling, cgroup memory limits, and scheduler noise; treat thresholds as
conservative release guardrails, not microbenchmark claims. If
`make benchmark` fails a threshold, inspect
`artifacts/performance/sysdiff-benchmark.json`: compare each measurement to
its threshold, subtract `baseline_ms_median` when judging startup/fixture
drift, review the raw `samples` lists for outliers, rerun on an idle machine,
and investigate recent changes that could inflate `--help` latency, compare
work, or peak memory before loosening limits.

## Installation and uninstallation

After `make` builds `build/sysdiff`, stage the executable and section-1 manual
page with optional `DESTDIR` and a configurable `prefix` (default
`/usr/local`):

```sh
make install DESTDIR=/path/to/stage prefix=/usr/local
```

That writes regular files `$(DESTDIR)$(prefix)/bin/sysdiff` mode `755` and
`$(DESTDIR)$(prefix)/share/man/man1/sysdiff.1` mode `644`. Re-running
`make install` with the same `DESTDIR` and `prefix` replaces those paths and,
when the build inputs are unchanged, leaves their installed bytes identical.
Remove only those installed files with:

```sh
make uninstall DESTDIR=/path/to/stage prefix=/usr/local
```

`make test` runs this install, documented `--help`/`--version`/`compare`
checks, idempotent reinstall, and byte-clean uninstall round trip inside a
temporary workspace `DESTDIR`. This is source Make staging only; the tree does
not produce `.deb`, `.rpm`, or other package-manager formats.

## Source releases

Create a deterministic source archive with `make dist` from the git work-tree
root. It writes `dist/sysdiff-source.tar.gz` and
`dist/sysdiff-source.tar.gz.sha256` from tracked release inputs only (source,
tests, Makefile metadata, docs, and license files) under a single `sysdiff/`
prefix, with sorted members and normalized timestamps, ownership, permissions,
and gzip headers. Untracked workspace state is never packaged. Nested copies
inside another repository (for example a disposable quality-floor tree under
scratch `TMPDIR`) are not a dist root; the suite skips those `make dist`
regressions there instead of treating the parent work tree as the package
source. Set `SOURCE_DATE_EPOCH` to a non-negative integer for bit-stable
rebuilds. Verify with `make distcheck`, which rebuilds at a fixed epoch,
compares digests, extracts outside the workspace, and runs `make` plus
`make test` on the clean tree. Inspect members with
`tar -tzf dist/sysdiff-source.tar.gz` or `sha256sum -c
dist/sysdiff-source.tar.gz.sha256` from `dist/`. Remove the artifact with
`rm -f dist/sysdiff-source.tar.gz dist/sysdiff-source.tar.gz.sha256` (or
`rm -rf dist`).

For a release-candidate package under `artifacts/` (distinct from `make dist`),
run `make release`. Like `make dist`, it selects tracked files only via
`git ls-files` over `RELEASE_PATHSPECS` (untracked scratch under `src/`,
`tests/`, or `scripts/` cannot ship), stages them under `/tmp`, writes
`artifacts/sysdiff-release.tar.gz` with a single `sysdiff-release/` archive
root, and records `artifacts/sysdiff-release.tar.gz.sha256` in standard
`sha256sum` form (archive basename beside the tarball; nested basename-only
checksums verified from another directory failed governed run
`c847e01d15fe`). Ordinary `make clean` removes only `build/` and does not
delete those release artifacts. Verify with
`(cd artifacts && sha256sum -c sysdiff-release.tar.gz.sha256)`, then extract
under `/tmp` and run `make -C …/sysdiff-release clean test`. This prepares an
unpublished candidate; it does not create a GitHub release or `.deb`/`.rpm`.
The release archive ships source, Makefile, license, root user docs, man page,
scripts, and tests; the deeper `docs/` contract tree and AgentFlow status
files remain repository-only. Packaged CLI behavior is documented in
`man/sysdiff.1` and the README summary below.

## Snapshot Format

The durable snapshot-format contract for the initial `sysdiff` vertical slice
is [docs/sysdiff-snapshot-format-and-scope.md](docs/sysdiff-snapshot-format-and-scope.md)
in the full git repository. Treat that document as the implementation source
of truth for snapshot syntax, deterministic comparison output, exit statuses,
resource scope, non-goals, security constraints, compatibility rules, and
acceptance checks. Recipients of `sysdiff-release.tar.gz` should use the
packaged man page and this README summary for CLI behavior; the `docs/` tree
is not a release-archive member. This README is only a quick usage summary of
the current fixture-backed behavior.

Snapshot fixtures are plain text files using one `key=value` entry per line:

```text
# optional comment
entry.name=value
another.entry=some value
empty.value=
```

Blank lines, including lines made only of spaces and tabs, and lines whose first
non-space character is `#` are ignored.
Keys are compared byte-for-byte and are not trimmed. Format-1 keys use only
`A–Z`, `a–z`, `0–9`, `.`, `_`, `-`, and `/`; they must contain at least one `.`,
must not contain consecutive dots (`..`), must not begin with `/`, and must not
end with `.`. Values are compared byte-for-byte after the trailing line ending
is removed. Duplicate keys in one snapshot are errors. When a total-byte limit
overflow coincides with a NUL byte, the byte-limit error is reported first.

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

## pathaudit

`pathaudit` 0.1.0 is a small ISO C17 scanner for hazards in explicitly named
PATH directory roots. Callers pass every root on the command line; the tool
never reads the `PATH` environment variable, walks directory contents, or
remediates anything. Lookup follows symbolic links like `stat(2)`. Findings use
a closed taxonomy (`EMPTY_ROOT`, `RELATIVE_ROOT`, `MISSING_ROOT`,
`NON_DIRECTORY_ROOT`, `GROUP_WRITABLE`, `WORLD_WRITABLE`) with deterministic
bytewise ordering. Exit status `0` means clean, `1` means hazards were found,
and `2` means usage, limit, inspection, or write failure (reject-closed). The
contract is [docs/pathaudit-contract.md](docs/pathaudit-contract.md); the
manual page is [man/pathaudit.1](man/pathaudit.1). Compile without writing a
workspace binary via `make pathaudit` (mktemp only), or let pytest build into
its temporary directory. Example: `pathaudit /tmp` or `pathaudit -- -dash-root`.

## Documentation

Release and maintainer documentation lives at the repository root alongside the
quick-start material above. Start with [STATUS.md](STATUS.md) for readiness and
[docs/sysdiff-quality-floor-clean-checkout.md](docs/sysdiff-quality-floor-clean-checkout.md)
for the declared `make quality` gate surface (Makefile order is the executable
contract; that doc mirrors it). [TESTING.md](TESTING.md) covers how shell
fixtures, pytest, smoke, sanitizers, and Valgrind compose.
[HISTORY.md](HISTORY.md) and [DECISIONS.md](DECISIONS.md) record engineering
timeline and durable product choices; [ROADMAP.md](ROADMAP.md) lists post-0.1.0
ideas without expanding current scope. Architecture detail is in
[architecture.md](architecture.md); user-facing CLI behavior is in
[man/sysdiff.1](man/sysdiff.1). The durable snapshot-format contract remains
[docs/sysdiff-snapshot-format-and-scope.md](docs/sysdiff-snapshot-format-and-scope.md).
Also see [CHANGELOG.md](CHANGELOG.md), [CONTRIBUTING.md](CONTRIBUTING.md),
[SECURITY.md](SECURITY.md), and [docs/AI_DEVELOPMENT.md](docs/AI_DEVELOPMENT.md).
When changing CLI semantics, key grammar, limits, exit statuses, or output
lines, update the man page, CHANGELOG, contract docs, and these root files in
the same change; do not leave README summaries or `man/sysdiff.1` behind the
implementation. Ownership of parse buffers and portability notes for binary
`fopen`, locale-independent sorting, and Linux-focused CI live in architecture
and TESTING—follow those before claiming a host or packaging target is covered.

## License

MIT License. Copyright (c) 2026 Lee Harrington. See [LICENSE](LICENSE).
