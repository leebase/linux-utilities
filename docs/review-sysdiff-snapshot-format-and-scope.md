# Review: sysdiff Snapshot Format and Scope

**Reviewed file:** `docs/sysdiff-snapshot-format-and-scope.md`
**Reviewer:** Agent-Orch worker (step 04 — verify snapshot contract)
**Date:** 2026-07-08

## Summary

The documentation slice is internally consistent, implementable, and well-aligned with
the mission charter. It correctly scopes the first release slice to explicit file
comparison, explicitly excludes live system probing, and provides a solid foundation for
a future implementation worker. No High or Critical deficiencies were found. Three Medium
and one Low finding are recorded below; none prevent a pass verdict.

---

## Checks Run

| Command | Exit code | Summary |
|---|---|---|
| `python3 -m compileall .agent-orch docs scripts tests` | 0 | No Python source files found in the listed paths; tool exited cleanly with no errors. |

Smoke evidence (`scripts/smoke.sh`, exit 0) was reviewed as separate reference input and
is not re-executed here. The pinned smoke result confirms the build and both fixture test
scripts passed on attempt 2.

---

## Lens Notes

### security

**Finding F-001 (Medium):** Key syntax validation rules defined in the "Key Syntax"
section are not cross-referenced in "Security Constraints." An implementation worker
reading only the Security Constraints section would encounter checks for NUL bytes,
allocation failures, format-string injection, and filesystem path handling — but would
not see the requirement to reject keys containing disallowed bytes, `..` path-traversal
segments, a leading `/`, trailing `.`, spaces, or tabs. The rules exist (in the Key
Syntax section) but are not surfaced as validation requirements in the security section.
This creates a risk that an implementer fulfils the security checklist without enforcing
key validity, silently accepting hostile keys.

**Proposed fix:** Add a "Key validation" bullet to the Content handling sub-section of
Security Constraints, referencing the Key Syntax rules and stating that any key failing
those rules must be rejected with exit status `2` and a diagnostic to stderr.

**No other security findings.** The path handling constraints (no shell expansion, no
glob, open exactly two named files, no TOCTOU risk introduced, no terminal escapes in
diagnostics) are clearly stated and consistent with the implementation. The explicit
statement that `file.` keys are not filesystem paths to inspect is present in both the
Key Syntax section and the Security Constraints section.

---

### format-clarity

**Finding F-002 (Medium):** The key syntax rule "Must not contain `..` as a path
traversal segment" is ambiguous. The phrase "path traversal segment" is not defined. An
implementer needs to know whether the rule applies to:

- The literal two-byte substring `..` appearing anywhere in the key (e.g., `foo..bar`
  would fail)?
- `..` as a complete dot-delimited segment (e.g., `a..b` is segment `..` between `a`
  and `b`, so it fails)?
- Only a leading `..` prefix (filesystem path traversal convention)?

These interpretations differ: `a...b` contains `..` as a substring but has no clean
dot-delimited `..` segment; `a.b..c.d` may or may not contain a `..` segment depending
on the parsing model. Without an explicit example of an invalid key or a more precise
definition (e.g., "any dot-delimited field that equals `..`"), implementations will
diverge.

**Proposed fix:** Replace the current bullet with one of:
- "Must not contain `..` as a dot-delimited field (i.e., no two adjacent `.` bytes)."
  — This is simple and easily checked: reject any key containing the literal `..`.
- Or clarify with an explicit invalid key example such as `file.../etc/passwd.sha256`.

**Finding F-004 (Low):** The Snapshot Format example opens with a comment line
`# sysdiff snapshot v1` immediately before data records including `sysdiff.snapshot_version=1`.
A reader skimming the example might conflate the comment with a required file header or
interpret the comment as the version declaration, and miss that the comment is ignored
and `sysdiff.snapshot_version=1` is the actual machine-readable version indicator. The
Compatibility Rules section correctly describes `sysdiff.snapshot_version=1` as the
version record, but the example would benefit from a brief annotation (e.g., "optional
human-readable label; the version record below is machine-readable") or simply placing
the `sysdiff.snapshot_version` record first with the comment after it.

---

### test-coverage

**Finding F-003 (Medium):** The Acceptance Checks section includes the entry "Reject a
key with bytes outside the valid key syntax." However, the acceptance checks do not list
explicit fixture tests for the individual key syntax rejection cases that are most likely
to be missed:

- A key containing `..` (the path traversal rule from F-002).
- A key beginning with `/`.
- A key ending with `.`.
- A key containing no `.` separator.
- A key containing a space or tab character.

Without named fixture items for these cases, different implementation workers may cover
subsets of the rules, leading to divergence across builds. The section already defers
all fixture-backed checks to a later implementation worker, but individual rejection
items being named would make the work unambiguous.

**No other test-coverage findings.** The Acceptance Checks section correctly identifies
all comparison behavior cases (added, removed, changed, identical), all exit status
classes, the `no changes\n` exact output requirement, stdout emptiness on errors,
deterministic ordering, and the full resource prefix set (`os.`, `kernel.`, `package.`,
`service.`, `file.`, `sysdiff.`).

---

### correctness

No correctness findings. Spot-checks against the current implementation and
supporting documents:

- `\r\n` line-ending stripping: doc says "a single trailing `\r` before `\n` is part of
  the line ending and is removed"; implementation strips `\n` then checks for `\r`. ✓
- Duplicate-key detection after sort: doc says "Duplicate keys within one snapshot are
  invalid"; implementation sorts then checks adjacent entries. ✓
- Bytewise sort: doc says "Sorting is bytewise and locale-independent"; implementation
  uses `strcmp` on byte strings in a file opened with `rb`. ✓
- `no changes\n`: doc says "stdout is exactly: `no changes`" with each line ending in
  `\n`; implementation uses `puts("no changes")`. ✓
- Exit status `1` for differences: doc says `1` when "compare succeeded and at least one
  difference was found"; `emit_diff` returns `1` when `changed` is true. ✓
- Exit status `2` for errors: all error paths in `parse_snapshot` return `2`. ✓
- stdout empty on error: `emit_diff` is not called when either `parse_snapshot` fails. ✓
- README and architecture alignment: both documents are consistent with the spec. ✓

---

### implementability

No implementability findings. The format rules are precise enough to build from: one
record per line, first `=` separates key from value, bytewise sort, exact output
prefixes. The key syntax character set is an explicit allowlist. The compatibility rules
are additive and forward-only. The security constraints do not depend on platform-
specific APIs beyond standard POSIX file I/O. The non-goals section clearly rules out
features that would require external integrations.

---

### mission-alignment

No mission-alignment findings. The document:

- Restricts the implementation to C with no added runtime dependencies (consistent with
  AGENTS.md "Avoid unnecessary dependencies").
- Requires static allocation failure detection and explicit resource limits (consistent
  with "Treat warnings, undefined behavior, unsafe input handling... as defects").
- Keeps the tool plainly auditable: one command, two file arguments, line-oriented
  stdout (consistent with "Keep each utility intentionally small and auditable").
- Does not introduce networking, telemetry, background services, or persistence
  (consistent with AGENTS.md prohibitions).
- Defers live snapshot collection to a future slice, which prevents premature scope
  creep.
- Uses only plain text, not SQLite, for this slice (consistent with "Use plain text or
  SQLite only when persistence is needed" — and this slice needs no persistence).
