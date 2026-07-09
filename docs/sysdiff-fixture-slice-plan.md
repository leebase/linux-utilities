# sysdiff Fixture Slice Plan

## Purpose

Deliver the smallest useful `sysdiff compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`
slice against deterministic fixture files. The implementation remains a single
C executable built from `src/sysdiff.c`, uses no new runtime dependencies, and
keeps `scripts/smoke.sh` unchanged as the user smoke oracle.

## Current Surface

- `Makefile` builds only `build/sysdiff` from `src/sysdiff.c` with
  `-std=c17 -Wall -Wextra -Wpedantic -Werror`.
- `make test` runs `./tests/test_sysdiff.sh`.
- `tests/test_sysdiff.sh` currently checks only `--help` and `--version`.
- `scripts/smoke.sh` runs `make test` and must remain unchanged.
- `src/sysdiff.c` currently has one entrypoint with `--help`, `--version`, and
  usage error behavior.

## Delivery Steps

1. Author fixture tests under `tests/`.
   - Add `tests/test_sysdiff_fixture.sh` for comparison, ordering, parsing, and
     error behavior.
   - Update `tests/test_sysdiff.sh` to keep the existing informational command
     checks and invoke `tests/test_sysdiff_fixture.sh`, so `make test` and the
     unchanged smoke script cover the new slice.
   - Use `mktemp -d` and shell-generated fixture files to keep fixtures small,
     deterministic, and self-cleaning. Static files under `tests/fixtures/` are
     acceptable only if they make expected data clearer.

2. Implement comparison in `src/sysdiff.c`.
   - Preserve `--help`, `--version`, no-argument help success, and existing
     version text.
   - Update usage text to include:
     `usage: sysdiff --help|--version|compare BEFORE_SNAPSHOT AFTER_SNAPSHOT`
   - Dispatch `compare` only when `argc == 4`; wrong counts and unknown
     commands return `2`.
   - Keep parsing, sorting/comparison, and formatting in separate static helper
     functions inside the single C source.

3. Document the user-visible slice.
   - Update `README.md` with the compare command and a minimal fixture example.
   - Keep `architecture.md` aligned with the separable parsing, comparison, and
     formatting direction.
   - Do not promise live snapshot capture in this slice.

4. Verify and repair.
   - Run `make clean`, `make`, `make test`, and `./scripts/smoke.sh`.
   - Run `CC=clang make clean test` when `clang` is available; otherwise record
     the unavailability in the governed run notes.
   - Keep smoke evidence outside source-controlled code unless the playbook
     explicitly allows an artifacts path.

## Architecture

Use only the C standard library.

Data model:

- `struct Entry { char *key; char *value; };`
- `struct Snapshot { struct Entry *items; size_t len; size_t cap; };`
- Own every allocated key and value in the snapshot; release through one
  cleanup function used on both success and error paths.

Parsing:

- Implement a bounded-by-memory dynamic line reader with `fgetc`, `realloc`,
  and checked capacity growth. Do not use POSIX `getline`, since the build is
  strict C17.
- Treat fixture bytes as text for line splitting only. Remove one trailing
  `\n`; if the remaining line ends in `\r`, remove that as part of the line
  ending.
- Ignore blank lines and lines whose first character after spaces or tabs is
  `#`.
- For entry lines, find the first `=`, reject missing `=`, reject empty keys,
  and duplicate the key and value into owned buffers.
- Reject embedded NUL bytes as malformed input, because the comparison and
  formatting helpers operate on owned C strings.
- Preserve key bytes exactly as written before `=`; do not trim keys.
- Preserve value bytes exactly after `=`, including spaces and empty values.
- Detect duplicate keys before returning a parsed snapshot and report the file
  path plus offending key to stderr.
- On file open, read, allocation, malformed line, or duplicate-key errors,
  return error status before producing any diff output.

Sorting and comparison:

- Sort each snapshot by key with `qsort` and `strcmp`, giving deterministic byte
  order for valid UTF-8-compatible fixture bytes.
- Reject duplicate keys either during insertion by linear lookup or after sort
  by adjacent-key comparison. Prefer after sort for simpler deterministic code.
- Compare sorted snapshots with two indices over the before and after arrays.
- For equal keys, compare values with `strcmp`; emit only a changed line when
  values differ.
- For keys present only in before, emit a removed line; for keys present only in
  after, emit an added line.
- Track whether any difference exists and return `1` when at least one
  difference is emitted, otherwise print exactly `no changes\n` and return `0`.

Output:

- Print diff lines only after both files parse and sort successfully.
- Use the exact formats with no space after the prefix:
  - `- removed.key=old value`
  - `+ added.key=new value`
  - `~ changed.key: old value -> new value`
- Write diagnostics only to stderr and include the path or argument that caused
  the failure.

## Tests

`tests/test_sysdiff_fixture.sh` should provide small helpers:

- `run_status EXPECTED command...` for status assertions without breaking
  `set -e`.
- `assert_file_equals EXPECTED ACTUAL` using `cmp -s` and readable failure
  output.
- `assert_empty FILE` for stdout on error paths.
- A temporary directory cleanup trap.

The fixture tests should create expected stdout/stderr files and assert exact
stdout where the contract requires it. Error diagnostics only need to prove
stderr is non-empty and contextual, unless a later review asks for exact
wording.

## Acceptance Mapping

| Acceptance check | Code work | Test work | Verification | Risk work |
| --- | --- | --- | --- | --- |
| Compare valid fixtures with unchanged, added, removed, and changed keys | Add `compare` dispatch, parser, sorted two-way comparison, and formatter | One changed fixture pair with all four cases | `make test`; exact stdout fixture | Ensure unchanged keys emit nothing and changed keys emit only `~` |
| Input order does not affect output order | Sort snapshots by key before comparing | Same logical data in unsorted order | Exact stdout order check | Use one comparator everywhere; avoid preserving insertion order in output |
| Comments, blank lines, and values containing spaces | Parser skips blank/comment lines and preserves value bytes after `=` | Fixture includes comments, blank lines, `key=value with spaces` | `make test` | Do not trim values or treat inline `#` as comments |
| Empty value | Parser accepts `key=` | Fixture includes added, removed, or changed empty value | Exact stdout check | Reject only empty keys, not empty values |
| Changed stdout exact | Formatter uses contract strings only | Compare stdout with expected file | `make test` | Avoid extra banners, debug text, or trailing spaces |
| Identical stdout exact | No-diff path prints exactly `no changes\n` | Identical fixture pair | `make test` | Do not return `1` for successful identical compare |
| Diff prefixes only `-`, `+`, `~` | Centralize diff formatting helpers | Expected output covers each prefix | `make test` | Avoid using unified-diff headers or file labels |
| Deterministic key order | `qsort` and merge-style comparison | Expected output sorted by key, independent of fixture order | `make test` | Byte-order comparison must be by key, not by whole line |
| Missing file exits `2` with stderr | `fopen` error path returns runtime error | Compare against nonexistent path; stdout empty; stderr non-empty and pathful | `make test` | Prevent partial stdout by parsing both files before printing |
| Wrong argument count exits `2` | `compare` requires exactly two paths | `sysdiff compare one` and/or too many args | `make test` | Keep no-argument help success unchanged |
| Unknown command exits `2` | Unknown dispatch path prints usage/diagnostic to stderr | `sysdiff nope` | `make test` | Distinguish unknown command from `--help` success |
| Malformed fixture line exits `2` | Reject missing `=`, empty key, and unsafe line/read failures | Fixture line without separator and stdout empty | `make test` | Include path and line number in diagnostic |
| Duplicate key exits `2` | Duplicate-key detection after sort or during insert | Fixture repeats a key | `make test` | Free all allocations on duplicate error |
| Error cases do not write partial diff stdout | Parse both snapshots before formatting | All error tests assert empty stdout | `make test` | Avoid streaming diff output during parse |
| `make clean` | Existing Makefile removes `build` | No test script change needed | Manual command in governed verification | Ensure generated fixtures stay in temp dirs |
| `make` | Existing Makefile strict-builds `src/sysdiff.c` | No test script change needed | Manual command in governed verification | Keep code C17 and warning-clean |
| `make test` | Existing test target remains entrypoint | `tests/test_sysdiff.sh` invokes fixture tests | Manual command and smoke command | Do not require environment-specific privileges |
| `./scripts/smoke.sh` | No code change to smoke script | Since smoke runs `make test`, fixture tests are covered | Manual command; record status and result path | Keep smoke oracle unchanged |
| `CC=clang make clean test` when available | Keep code portable across strict GCC/Clang | No compiler-specific tests | Manual command or record unavailable | Avoid GNU extensions such as `getline` |
| Smoke evidence recorded outside source code | No source change | Governed smoke runner writes allowed artifact | Inspect run evidence | Do not add smoke logs under tracked source paths |
| README compare command | Documentation step updates README | Review docs manually | `rg "sysdiff compare" README.md` | Avoid documenting future live capture behavior |
| README fixture example | Documentation step adds minimal example | Review docs manually | `rg "entry.name=value" README.md` or equivalent | Keep format narrower than general diff |
| Architecture separability remains stated | Documentation step preserves architecture direction | Review architecture manually | `rg "parsing, comparison, and formatting" architecture.md` | Do not overstate modules or add new binaries |
| Docs do not promise live capture | README wording limits scope to fixtures | Review docs manually | `rg` for live capture promises if needed | Existing README currently says snapshots system state; revise to fixture slice wording |

## Verification

Run these from the repository root after implementation and repair:

```sh
make clean
make
make test
./scripts/smoke.sh
if command -v clang >/dev/null 2>&1; then CC=clang make clean test; else echo "clang unavailable"; fi
```

The governed smoke gate must use the unchanged command:

```sh
./scripts/smoke.sh
```

It should record command, exit status, and result path in the run evidence
outside normal source-controlled code.

## Risks

- **Silent truncation:** avoid fixed-size line buffers; dynamically grow line
  storage with overflow checks and treat allocation failure as exit status `2`.
- **Partial output on errors:** parse and validate both snapshots fully before
  printing any diff output.
- **Ownership leaks on parse failure:** centralize snapshot cleanup and route all
  parse errors through cleanup before returning.
- **Non-deterministic output:** sort by key before comparison and test with
  intentionally unsorted input.
- **Shell `set -e` masking status checks:** capture expected nonzero statuses
  through helper functions instead of direct failing commands.
- **Smoke drift:** leave `scripts/smoke.sh` unchanged; expand coverage through
  `make test`.
