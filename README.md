# Linux Utilities

Small, auditable command-line tools for Linux. Each utility is written in one
C17 source file, has no runtime dependencies, performs no networking or
telemetry, and does not run a background service.

| Utility | Purpose | Status |
| --- | --- | --- |
| [`sysdiff`](docs/sysdiff.md) | Compare two explicit `key=value` system snapshots | Released: v0.1.0 |
| [`pathaudit`](docs/pathaudit.md) | Find risky, missing, or shadowed entries in command search paths | Preview |
| [`permguard`](docs/permguard.md) | Report dangerous permission bits on explicitly named paths | Preview |
| [`openunlink`](docs/openunlink.md) | Report stable zero-link regular files held open by one process | Preview |

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
  -D_POSIX_C_SOURCE=200809L \
  -o build/permguard src/permguard.c
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 \
  -o build/openunlink src/openunlink.c
```

Try the built-in help:

```sh
./build/sysdiff --help
./build/pathaudit --help
./build/permguard --help
./build/openunlink --help
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
- [openunlink guide](docs/openunlink.md) — one-process descriptor scans,
  zero-link semantics, output, and limitations.

Traditional section-1 manual pages are also included:

```sh
man -l man/sysdiff.1
man -l man/pathaudit.1
man -l man/permguard.1
man -l man/openunlink.1
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

### Pathaudit Maintenance Repairs

Open repair `PA-W1` keeps the public CLI byte-compatible while shrinking the
`ELOOP` self-basename discriminator: `symlink_is_self_basename` no longer
reserves a `PATHAUDIT_MAX_ROOT_LENGTH` automatic `readlink` buffer. It
allocates only `strlen(command) + 1` temporary bytes (the extra byte detects
truncation), frees that storage on every return, and never executes link text.
A bare self link such as `tool -> tool` stays reject-closed: empty stdout,
status `2`, and one escaped `INSPECTION_ERROR_<ELOOP>` naming the candidate
under `--path` and `--command`. Slash-bearing payloads (`tool -> ./tool`) and
byte-different mutual loops remain non-candidates and invent no `MATCH` or
`SHADOWED` row. Allocator failure in the helper emits stderr-only
`OUT_OF_MEMORY` and status `2` rather than a silent non-match. Prior shadow
index repairs (`pathaudit-shadow-1/2/3`) stay in force. Non-goals: no new
modes, hazard codes, ownership policy, remediation, packaging, or release
claim. Authority: `docs/pathaudit-open-repairs-contract.md`.

## permguard

`permguard` is a preview ISO C17 explicit-path scanner:
`permguard [--] PATH...`, plus sole-argument `--help` / `--version`. Each
operand receives exactly one `lstat`; a final symbolic link is rejected as
`SYMBOLIC_LINK` (status `2`) and never followed. Successful non-symbolic
objects emit zero or more of the closed four-code taxonomy in fixed rank:
`GROUP_WRITABLE` (`S_IWGRP`), `OTHER_WRITABLE` (`S_IWOTH`), `SET_USER_ID`
(`S_ISUID`), and `SET_GROUP_ID` (`S_ISGID`), without file-type or sticky-bit
heuristics. Findings stream on stdout as `HAZARD<TAB>"ESCAPED_PATH"` while
inspection continues after operand errors; exits are `0` (clean or
informational), `1` (hazard-only, empty stderr), and `2` (usage, missing,
inaccessible, symlink, other `lstat`, or checked `STDOUT_WRITE` /
ignored-`SIGPIPE` output failure). Non-goals: no recursion, `PATH` lookup,
remediation, ownership/ACL policy, install wiring, packaging, or release
claim. See `docs/permguard.md` and `man/permguard.1`.

### Permguard Hostile Filesystem Fixtures

Additive fixture coverage under
`docs/permguard-hostile-filesystem-fixtures-contract.md` exercises the live
bootstrap against dangling and looping symbolic links, mode-000 metadata
versus parent-search `INACCESSIBLE`, verified permission transitions, unusual
escaped filenames, deep existing paths, FIFO (and optional AF_UNIX) special
files without opening them, and deterministic replacement boundaries via a
test-only `lstat` seam. Public findings remain the four mode-bit codes;
diagnostics remain `SYMBOLIC_LINK`, `MISSING`, `INACCESSIBLE`, and
`INSPECTION_ERROR_N`; exits stay `0`/`1`/`2`. Portability limits:
capability-gated `EACCES` and over-limit deep paths may skip explicitly;
concurrent replacement is neither a filesystem lock nor a race-free
authorization claim; character and block device nodes stay out of scope.
Product authority remains `docs/permguard-bootstrap-contract.md`; the
hostile-fixture contract is acceptance evidence only and does not install,
package, or release `permguard`.

## openunlink

`openunlink` is a preview ISO C17/Linux utility with the single form
`openunlink PID`, plus sole-argument `--help` and `--version`. It scans only
the fixed `/proc/PID/fd` directory and reports descriptors whose followed
targets are observed as stable regular files with final `st_nlink == 0`.
`OPEN_UNLINKED` output includes the final `st_size` as observation context;
the first `65536` valid descriptors are retained in observed order and a
`65537`th produces one `FD_COUNT_LIMIT` advisory. A status-0 result does not
exclude NFS silly-rename or other cases where unlink-like behavior leaves a
nonzero link count. The utility is read-only, does not open target contents,
does not terminate processes, and is not installed or packaged by this
preview. See [`docs/openunlink.md`](docs/openunlink.md),
[`man/openunlink.1`](man/openunlink.1), and the authority contract in
[`docs/sixth-utility-capability-contract.md`](docs/sixth-utility-capability-contract.md).

## License

MIT. See [LICENSE](LICENSE).
