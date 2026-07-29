# Linux Utilities

Small, auditable command-line tools for Linux. Each utility is written in one
C17 source file, has no runtime dependencies, performs no networking or
telemetry, and does not run a background service.

| Utility | Purpose | Status |
| --- | --- | --- |
| [`sysdiff`](docs/sysdiff.md) | Compare two explicit `key=value` system snapshots | Released: v0.1.0 |
| [`pathaudit`](docs/pathaudit.md) | Find risky, missing, or shadowed entries in command search paths | Preview |
| [`permguard`](docs/permguard.md) | Report dangerous permission bits on explicitly named paths | Preview |

The preview tools are available as reviewed source with tests and manual
pages. They are intentionally not included in the `sysdiff` installation or
release package yet.

## Quick start

Clone the repository and compile all three tools:

```sh
git clone https://github.com/leebase/linux-utilities.git
cd linux-utilities
mkdir -p build

cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/sysdiff src/sysdiff.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/pathaudit src/pathaudit.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/permguard src/permguard.c
```

Try the built-in help:

```sh
./build/sysdiff --help
./build/pathaudit --help
./build/permguard --help
```

`make` remains the supported build and installation path for the released
`sysdiff` utility:

```sh
make
sudo make install
```

The default installation prefix is `/usr/local`. Use `DESTDIR` and `prefix`
for staged or custom installations.

## Learn each utility

- [sysdiff guide](docs/sysdiff.md) — snapshot format, examples, output, exit
  statuses, installation, and source.
- [pathaudit guide](docs/pathaudit.md) — explicit-root, full-PATH, and
  command-specific audits with examples.
- [permguard guide](docs/permguard.md) — permission checks, symlink behavior,
  examples, and limitations.

Traditional section-1 manual pages are also included:

```sh
man -l man/sysdiff.1
man -l man/pathaudit.1
man -l man/permguard.1
```

## Test and inspect

The ordinary test suite compiles temporary binaries and exercises all three
utilities:

```sh
make test
```

The complete Linux quality gate adds strict GCC and Clang builds, formatting,
static analysis, manual-page linting, sanitizers, Valgrind, regression tests,
and the `sysdiff` benchmark:

```sh
make quality
```

See [TESTING.md](TESTING.md) and [QUALITY.md](QUALITY.md) for the full tool
list and individual targets.

## Design principles

- One clear job per executable.
- Small C source surfaces that people can audit.
- Deterministic output and documented exit statuses.
- Read-only inspection unless a future tool explicitly says otherwise.
- No services, telemetry, hidden persistence, or network access.
- Fail closed on malformed input and operational errors.

Security reports should follow [SECURITY.md](SECURITY.md). Contributions are
welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## pathaudit

`pathaudit` is a preview ISO C17 scanner with three exclusive forms:
`pathaudit [--] ROOT...` (explicit roots; ignores `PATH`; ownership-blind),
`pathaudit --path` (split `PATH` on `:`; shared hazards plus executable
`SHADOWED` rows), and `pathaudit --command NAME` (one basename; PATH-ordered
`MATCH` rows, never `SHADOWED`). Sole-argument `--help` / `--version` remain
informational. Under `--path`, the first PATH-order executable realpath wins;
each later distinct realpath emits one
`SHADOWED<TAB>"COMMAND"<TAB>"WINNER"<TAB>"SHADOW"<LF>` row, and an exact
`(command, winner, shadow)` tuple emits at most once. Shared findings,
including directory and ancestor-chain `UNSAFE_OWNER` when the owner is
neither UID 0 nor the invoking real UID from `getuid()`, precede all
`SHADOWED` rows. Under `--path` that ownership walk applies to usable PATH
directories; under `--command` it is gated by the same match-or-plant-risk
rule as directory permission codes, and an empty PATH field may audit the
cwd chain (`.`) under that gate (`--path` does not). Exits stay `0` (clean),
`1` (hazard or unique shadow), and `2` (usage, unset `PATH`, limits,
allocation, or stdout failure). See `docs/pathaudit.md` and `man/pathaudit.1`.

### pathaudit Maintenance Repairs

Candidate maintenance repairs for `pathaudit-shadow-1/2/3` keep the public CLI
unchanged: retained winner/shadow realpaths use exact `strlen + 1` storage,
winner lookup uses a bounded basename index, shadow duplicate checks use a
bounded `(command, shadow)` index, and exact duplicate shadow tuples emit
once (`PATH=early:late:late` → one `SHADOWED`, status `1`, empty stderr).
Distinct later realpaths still each produce one row. Diagnostics such as
`PATH_UNSET`, `INVALID_COMMAND`, `OUT_OF_MEMORY`, and `STDOUT_WRITE` remain
stderr-only. Non-goals: no new modes, hazard codes, ownership policy,
remediation, packaging, or pathaudit release claim. Failed run
`6ca4cebc8527` is not treated as a passed delivery.

## License

MIT. See [LICENSE](LICENSE).
