# `pathaudit` PA-W1 Open-Repair Contract

This maintenance slice closes only Low finding `PA-W1`, recorded by the
writable-executable review and explicitly left open by
`docs/pathaudit-maintenance-repair-contract.md`. The current
`symlink_is_self_basename` implementation reserves
`PATHAUDIT_MAX_ROOT_LENGTH + 1` bytes (65,537 bytes) as an automatic
`readlink` buffer whenever an executable candidate encounters `ELOOP`. That
root-sized stack reservation is unnecessary: the predicate only needs to know
whether the link payload is exactly the already-known command basename.

## CLI Surface

The public surface remains byte-for-byte compatible:
`pathaudit [--] ROOT...`, `pathaudit --path`,
`pathaudit --command NAME`, and the sole-argument `--help` and `--version`
forms. Explicit-root mode remains ownership-blind and does not search
executables. `--path` continues to inspect top-level executable candidates and
emit `SHADOWED` rows; `--command` continues to emit PATH-ordered `MATCH` rows
for one slash-free, nonempty basename. This repair adds no option, environment
variable, test-only runtime switch, output field, or version change.

The repaired helper borrows `candidate` and `command`, allocates only enough
temporary storage to compare a possible link payload with `command` plus one
extra truncation-detection byte, calls `readlink` without following or
executing the candidate, and frees that temporary storage before every return.
No pointer into the buffer escapes. The caller retains ownership of
`candidate`; the command string remains borrowed from `argv` or `readdir`.
The previously captured `ELOOP` value remains authoritative even if the helper
uses allocation or another metadata call.

Hostile and unusual path behavior is preserved. A bare self link such as
`tool -> tool` remains an unsafe executable inspection and produces the
existing escaped `INSPECTION_ERROR_<ELOOP>` diagnostic. A link payload that
is longer, shorter, byte-different, contains `/` (for example
`tool -> ./tool`), or changes during inspection must not be falsely accepted
as the bare self-basename case. Mutual loops remain non-candidates under the
existing rule. Link text is never executed, searched through `PATH`, printed
unescaped, or retained after the check.

Acceptance checks are:

- **AC-1:** a source regression proves `symlink_is_self_basename` has no
  automatic buffer sized by `PATHAUDIT_MAX_ROOT_LENGTH`; its temporary
  allocation is bounded by the command length plus one detection byte and is
  released on success, mismatch, and `readlink` failure.
- **AC-2:** the existing `--path` bare-self-link regression still returns `2`,
  writes no stdout, and emits exactly one escaped
  `INSPECTION_ERROR_<ELOOP>` line naming the candidate.
- **AC-3:** the existing `--command` bare-self-link regression retains the
  same status, stdout, and stderr bytes as AC-2.
- **AC-4:** new slash-bearing and byte-different loop-target regressions prove
  those links are not reclassified as bare self-basename links and never
  execute target content or emit a fabricated `MATCH` or `SHADOWED` record.
- **AC-5:** focused, full-suite, sanitizer, and Valgrind runs complete without
  leak, double-free, use-after-free, stack-overflow, warning, or output drift.

## Closed Hazard Taxonomy

The shared finding taxonomy remains closed and ordered exactly as
`EMPTY_ROOT`, `RELATIVE_ROOT`, `MISSING_ROOT`, `NON_DIRECTORY_ROOT`,
`GROUP_WRITABLE`, `WORLD_WRITABLE`, and `UNSAFE_OWNER`. The repair neither
adds a code nor changes applicability: explicit roots remain
ownership-blind; `--path` may inspect usable PATH directories, their canonical
ancestors, and resolved executable targets; `--command` retains its
match-or-plant-risk applicability rule. UID 0 and the invoking real UID from
`getuid()` remain the only trusted owners.

`SHADOWED` remains a completed-hazard row outside the root-code enum, and
`MATCH` remains informational. A symlink loop is not a new hazard code:
bare-self-loop recognition exists only to decide whether an already observed
`ELOOP` is a reject-closed inspection error or an existing silently skipped
non-candidate case. Missing components, non-directories, unreadable
directories, non-executable files, non-shebang/non-ELF decoys, repeated PATH
components, symlink aliases, and directory/executable ownership findings keep
their current classifications, ordering, deduplication, and escaping.

Hostile bytes in argv, PATH components, command names, candidate paths, and
diagnostics continue to use quoted printable-ASCII rendering: `"` and `\` are
escaped, printable ASCII is literal, and every other byte is `\xHH`. The
temporary `readlink` payload is comparison-only and never becomes a finding or
diagnostic field. Existing filesystem-race limitations remain visible; this
read-only audit does not become a race-free authorization decision.

## Exit Statuses

Exit meanings remain exactly `0`, `1`, and `2`. Status `0` means successful
informational output or a completed inspection with no applicable hazard;
clean `MATCH` rows alone remain status `0`. Status `1` means a completed audit
emitted at least one shared-taxonomy finding or `SHADOWED` row. Successful
status-0 and status-1 paths keep stderr empty.

Status `2` remains the reject-closed class for usage errors, unset `PATH`,
invalid commands, resource limits, allocation failure, unsafe inspection, and
stdout write or flush failure. A bare self-basename loop therefore remains
status `2` with empty stdout and
`pathaudit: INSPECTION_ERROR_<ELOOP>: "ESCAPED_CANDIDATE"` on stderr. If the
new bounded temporary allocation fails, the command emits the existing
stderr-only `pathaudit: OUT_OF_MEMORY` diagnostic and returns `2`; it must not
silently treat allocation failure as “not a self link.”

A failed `readlink` during the best-effort loop discriminator preserves the
current non-match decision and invents no partial finding. Failures before
emission keep stdout empty. A later stdout failure may retain already-written
bytes and must still end with status `2` plus `STDOUT_WRITE`. This repair does
not alter diagnostic spelling, usage text, error precedence, signal handling,
or the rule that untrusted diagnostic paths are escaped.

## Explicit Non-Goals

This slice does not address `PA-W2` executable-image scope,
`path-dir-ownership-1` deduplication complexity, `PA-6CA-1` duplicated index
machinery, `PA-6CA-2` comment-only shadow-index sealing, `PA-6CA-3`
performance/rollback gate gaps, or `PA-6CA-4` review-worker filesystem
limitations. It also leaves the recorded `nondir-*`, `pathaudit-cmd-*`,
`pathaudit-wdp-*`, `PA-WP-*`, bootstrap `PA-M1`/`PA-M2`, and `PA-L*` items
open unless a later independent review closes them. In particular, this work
does not bundle the separate misleading `signal(SIGPIPE)` diagnostic or dead
condition polish into PA-W1.

There is no recursion, writable-ancestor feature, broader executable
recognition, new ownership trust rule, ACL/capability policy, content scan,
command execution, remediation, PATH editing, monitoring, persistence,
networking, privilege change, package inspection, or daemon. The repair does
not change root/count/byte limits, PATH splitting, executable winner
selection, shadow tuple uniqueness, output sorting, symlink-following policy,
or the documented best-effort behavior under concurrent filesystem mutation.

No `pathaudit` install target, package, tag, publication, release, or
release-readiness claim is authorized. `pathaudit` remains a preview source
utility. `sysdiff`, `permguard`, their packaging, the smoke manifest, and
their runtime behavior are outside this maintenance boundary. The existing
sysdiff-centered smoke route may provide transitive suite evidence, but it is
not redefined as a dedicated end-to-end PA-W1 oracle.

User-facing documentation for this repair stays bounded to the delivered
behavior: README heading `Pathaudit Maintenance Repairs`, CHANGELOG
`Unreleased`, `man/pathaudit.1` sections DESCRIPTION / DIAGNOSTICS /
EXIT STATUS, QUALITY.md, TESTING.md, and `docs/pathaudit.md` describe the
command-bounded `readlink` discriminator, bare-self `INSPECTION_ERROR_<ELOOP>`
status `2`, non-self loop handling, and `OUT_OF_MEMORY` failure without adding
options, hazard codes, ownership rules, packaging, or release claims. This
contract remains the PA-W1 authority when prose and source disagree.
