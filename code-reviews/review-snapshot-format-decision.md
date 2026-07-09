# Review: docs/snapshot-format-decision.md

**Subject**: `docs/snapshot-format-decision.md`  
**Canonical contract**: `docs/sysdiff-snapshot-format-and-scope.md`  
**Implementation**: `src/sysdiff.c`  
**Verdict**: PASS (one Low finding; no Critical or High findings)

---

## Summary

The decision document is a concise design summary that correctly defers to
`docs/sysdiff-snapshot-format-and-scope.md` as the authoritative contract. All
major claims are accurate and consistent with both the canonical spec and the
current implementation in `src/sysdiff.c`.

---

## Checks Run

| Command | Exit Code | Notes |
|---|---|---|
| `python3 -m compileall src tests` | 0 | No Python source files present; compileall found nothing to compile and exited cleanly. Advisory check run per orchestrator contract. |
| `grep -n 'strchr' src/sysdiff.c` | 0 | Confirms the implementation uses `strchr` to find the first `=` on line 230, matching the decision doc claim that "the first `=` separates the key from the value." |

---

## Lens Notes

### doc-accuracy

The decision doc's core claims hold against the canonical spec:

- **"deterministic plain-text byte streams made of one resource record per line, encoded as `key=value`"** — exact match with the canonical spec's format section.
- **"Blank lines and whole-line comments are ignored"** — matches spec sections *Line Handling* and the implementation's `is_ignored_line` (`src/sysdiff.c:104`), which skips lines that are empty or whose first non-space/tab byte is `#`.
- **"the first `=` separates the key from the value"** — confirmed by `strchr(line, '=')` at `src/sysdiff.c:230`.
- **"values are opaque bytes after line-ending removal"** — matches spec; implementation strips `\n` and optional leading `\r` (`src/sysdiff.c:218-222`).
- **"Diff output is sorted by bytewise key order across the union of both key sets"** — confirmed by `qsort` + `compare_entries_by_key` using `strcmp` (locale-independent, unsigned byte comparison) and the merge walk in `emit_diff` (`src/sysdiff.c:168-173`, `src/sysdiff.c:291-342`).
- **"the same logical snapshots produce the same stdout regardless of input ordering, host locale, current directory, clock, environment, or local system state"** — verified: `strcmp` is not locale-sensitive (unlike `strcoll`), no environment variables are read, no filesystem inspection occurs.

One Low imprecision is noted below (F001); it does not undermine correctness.

### contract-consistency

The decision doc correctly defers to the canonical contract with the sentence "This decision follows the canonical contract in `docs/sysdiff-snapshot-format-and-scope.md`." All properties claimed in the decision doc — validation before output, bytewise sorted diff, map-based comparison — are present in the canonical spec. No claims contradict the spec.

One subtle implementation point: `compare_snapshots` (`src/sysdiff.c:344`) parses `BEFORE_SNAPSHOT` first; if it fails, `AFTER_SNAPSHOT` is never opened. The canonical spec says "Both files must be fully opened, read, parsed, and validated," which could be read strictly as requiring both to be parsed before either is rejected. The decision doc phrase "validates both fully, rejects malformed or duplicate records before producing output" is compatible with the implementation's sequential-then-stop behavior because no partial diff output is ever produced and each file is individually validated in full. This is not a defect in the decision doc, but implementors should be aware that the canonical spec's phrasing is slightly stricter and the intent is "no partial diff," not necessarily "parse both concurrently."

### impl-consistency

All decision doc claims are borne out by the implementation:

- Both snapshots are parsed and sorted before `emit_diff` is called — no partial output risk.
- Duplicate detection runs after sorting via `validate_no_duplicates` (`src/sysdiff.c:175`), which catches adjacent-equal keys in the sorted array.
- Output format (- / + / ~) is determined inside `emit_diff` and matches the canonical contract; the decision doc does not contradict this.

### security

The decision doc does not introduce security commitments beyond what the canonical spec mandates. The rationale correctly frames the choice as favoring small, auditable, dependency-free operation. The implementation rejects NUL bytes (the `LINE_INVALID` branch in `read_line`), uses fixed format strings in all `printf` calls (user data only appears as `%s` arguments), and opens files in binary mode (`fopen(..., "rb")`). No findings.

### rationale

The stated rationale — "small, auditable, fixture friendly, and easy to review with ordinary Unix tools" — is accurate and well-supported. The format avoids parser libraries, binary encoding, locale-sensitive collation, and live-system inspection. The format-1 versioning scheme and unknown-key forward-compatibility rule are sensible and correctly described.

---

## Findings

### F001 — Low

**File**: `docs/snapshot-format-decision.md`  
**Location**: Snapshot Format section, sentence beginning "keys are validated"  
**Problem**: The phrase "dot-separated resource names" understates the allowed key byte set. Per the canonical spec, keys may also contain `_`, `-`, and `/`. The `file.` prefix illustrates this directly: the example `file./etc/passwd.sha256` in the canonical spec contains `/` inside the key, which "dot-separated" does not suggest. A reader relying only on the decision doc without following the canonical-contract link might omit `_`, `-`, or `/` from fixture keys, or assume keys like `file./etc/passwd.sha256` are invalid.  
**Proposed fix**: Expand the phrase to read: "keys are validated as case-sensitive names whose bytes are restricted to `A-Za-z0-9._-/`, required to contain at least one `.`, not beginning with `/`, not ending with `.`, and not containing `..`."
