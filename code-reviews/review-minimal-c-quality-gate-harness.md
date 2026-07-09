# Code Review: Minimal C Quality-Gate Harness

**Scope:** `src/sysdiff.c`, `Makefile`, `scripts/smoke.sh`,
`tests/test_sysdiff.sh`, `tests/test_sysdiff_fixture.sh`
**Prior context:** sysdiff-fixture-slice review (High: fixture tests unreachable from smoke)
**Verdict:** PASS — no High or Critical findings

---

## Checks Run

| Command | Exit | Notes |
|---------|------|-------|
| `python3 -m compileall tests scripts` | 0 | Both directories contain only shell scripts; no Python source files. compileall listed the directories and exited cleanly. |

The smoke oracle artifact at `.agent-orch/user-smoke/result.json` records `exit_code: 0` for `bash scripts/smoke.sh`, with SHA-256 pins on the three key files. That result is discussed in prose below; the smoke command itself is not reproduced in `checks_run` per the gate allowlist.

---

## Checks Run: User-Smoke Discussion

`result.json` confirms:

- `scripts/smoke.sh` delegates to `make test`, which builds `build/sysdiff` from `src/sysdiff.c` and then runs `tests/test_sysdiff.sh`.
- `tests/test_sysdiff.sh` (line 7–9) now exercises `--help`, `--version`, and calls `tests/test_sysdiff_fixture.sh`. This closes the High finding from the prior review.
- The fixture suite (184 lines) runs six independent scenarios: normal multi-key diff with exact stdout check, no-change case, missing-file error, wrong argument count, unknown command, malformed line, and duplicate-key detection.

The prior review's F001 (fixture tests unreachable from smoke) is resolved.

---

## Lens Notes

### Correctness

The two-pointer sorted merge in `emit_diff` (sysdiff.c:297–341) is correct for the sorted, deduped inputs produced by `parse_snapshot`. All three output prefixes (`+`, `-`, `~`) fire on the right branch. The exit-code contract — 0 for no changes, 1 for changes, 2 for error — is consistent throughout, and the fixture test verifies the 0/1/2 returns directly with `run_status`.

**F-01 (Medium):** The `~` changed-line format at line 317 uses ` -> ` as the separator:

```
~ net.ipv4.tcp_rmem: old -> new
```

If a value contains the literal substring ` -> `, the output is ambiguous and cannot be parsed unambiguously by downstream tools. The `+` and `-` lines are safe (key charset excludes `=`, so `+ key=value` is always unambiguous), but the `~` format has no escape mechanism. For current sysctl/proc values this is unlikely to trigger in practice, but the format makes a silent contract assumption that is not documented or enforced.

Proposed fix: either document the constraint in a format spec and reject values containing ` -> ` at parse time, or switch the `~` line to a format that includes raw `key=value` pairs (e.g., two lines prefixed `<` and `>` in the style of diff(1)).

### Memory Safety

`read_line` grows its buffer dynamically. The two guard expressions before `realloc` are correct:
- `new_cap <= cap` catches `size_t` wraparound when `cap * 2` overflows.
- `new_cap - len <= 1` ensures the new allocation provides room for the current character plus a null terminator.

`snapshot_append` guards the `new_cap * sizeof(...)` multiplication with `new_cap > (size_t)-1 / sizeof(snapshot->items[0])` before the `realloc` call. This is correct.

All error paths in `parse_snapshot` call `fclose` and `snapshot_free` before returning; the post-loop `fclose` return value is checked. `snapshot_free` zeroes `items`, `len`, and `cap` after freeing, preventing double-free on a second call.

**F-02 (Low):** The guard `if (len == (size_t)-1) return NULL` in `copy_range` (line 38) is dead code. Both call sites derive `len` from `key_len` and `value_len`, which are bounded by actual buffer lengths far below `SIZE_MAX`. The check makes allocation-failure NULL (the interesting case) indistinguishable from the sentinel-triggered NULL (unreachable), and misleads readers into thinking callers may pass `SIZE_MAX` as a sentinel. Remove it; if the caller contract needs commentary, a single inline note is clearer.

### Security

No vulnerabilities found.

- All `fprintf`/`printf` calls use fixed format strings; user-supplied strings always appear as `%s` arguments with no format-string injection surface.
- `fopen` uses binary mode (`"rb"`), preventing platform-specific line-ending expansion from corrupting binary content.
- NUL byte detection (`ch == '\0'` at line 71) causes `LINE_INVALID`, cleanly rejecting binary files before any parsing proceeds.
- Input file paths are argv strings passed directly to `fopen`; no shell interpolation, no command injection surface.

### Test Coverage

The fixture suite covers the main acceptance paths well:

- Exact stdout for the multi-key diff (sorted order, all three prefix types, empty values)
- Exact stdout for the no-change path ("no changes")
- Error cases: missing file, wrong arg count, unknown command, malformed line (no `=`), duplicate key
- Stderr-only on error (stdout is asserted empty for all 2-exit cases)

Paths not covered but low-risk given format constraints:

- NUL byte in snapshot file (exercises `LINE_INVALID` in `read_line`)
- CRLF line endings (handled by the `\r` strip at lines 220–222, but not exercised by a test)
- Value containing ` -> ` (the F-01 ambiguity)
- `too-many-args` for `compare` (five argv elements instead of four) — a Minor gap carried forward from the prior review's F003

### Build and Process

Compilation flags (`-std=c17 -Wall -Wextra -Wpedantic -Werror -O2`) are strong. The `CC ?= cc` and `CFLAGS ?=` override pattern is clean for cross-compiler and CI use.

**F-03 (Low):** AGENTS.md mandates AddressSanitizer, UBSan, clang-tidy, cppcheck, and Clang static analyzer for release-quality work. The Makefile has no targets for any of these. For a minimal slice this is expected, but without an `asan` or `tidy` target the quality gate cannot be considered release-ready per the project's own definition. Add:

```makefile
asan: src/sysdiff.c
	$(CC) $(CFLAGS) -fsanitize=address,undefined -o build/sysdiff-asan $<

tidy: src/sysdiff.c
	clang-tidy $< -- $(CFLAGS)
```

and run both under `make ci`.

---

## Summary

The prior High finding (fixture tests unreachable from smoke) is resolved. The current harness is functionally correct, memory-safe, and passes all fixture assertions. Three findings remain, all Low or Medium:

| ID | Severity | File | Summary |
|----|----------|------|---------|
| F-01 | Medium | src/sysdiff.c:317 | `~` changed-line format ambiguous when value contains ` -> ` |
| F-02 | Low | src/sysdiff.c:38 | Dead SIZE_MAX sentinel in `copy_range` |
| F-03 | Low | Makefile:2 | No ASan / UBSan / tidy targets despite AGENTS.md mandate |

None of these meet the High threshold; the gate verdict is **PASS**.
