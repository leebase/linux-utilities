# Decision Log

This log records durable product and engineering choices for `sysdiff` 0.1.0
and the surrounding `linux-utilities` repository. Entries summarize why the
implementation looks the way it does so later maintainers can avoid re-litigating
settled trade-offs. Detailed narrative also exists in `docs/DECISIONS.md` and
`docs/snapshot-format-decision.md`; keep those files aligned when changing
behavior, and append here rather than silently rewriting past rationale.
Rejected alternatives (live capture, general `diff(1)` semantics, JSON/YAML
snapshots, semantic value interpretation, locale-aware sorting, streaming
partial output, and extra runtime libraries) remain documented so the narrow
explicit-snapshot scope stays intentional. Lee approved format-1 diff lines
`+ key=value`, `- key=value`, and `~ key: old -> new` on 2026-07-09; treat that
as the stable presentation contract unless an explicit versioned change is
made.

## 2026-07-30 — Sixth Utility Mission Selection

- Commit exactly **Bootstrap `openunlink` explicit-process zero-link regular-file descriptor reporting**
  as the sixth mission. Its one purpose is
  to report, for one explicit Linux PID, descriptors whose followed target is
  a regular file with `st_nlink == 0`; procfs target text is non-authoritative
  escaped context.
- Bound the first slice to `--help`, `--version`, or one PID; fixed
  `/proc/PID/fd`; numeric descriptor ordering; repeated directory-relative
  metadata; one `OPEN_UNLINKED` finding form; visible per-descriptor
  advisories; exact statuses; a manual; focused fixtures; strict quality
  evidence; dedicated smoke; and review. Exclude all-PID discovery, content
  access, inode grouping, reclaim estimates, control/remediation, monitoring,
  installation, packaging, publication, and release.
- Accept the selection evidence from governed run `787b9bb3d830`: independent
  verdict `pass`, no Critical/High, with Medium `SIXTH2-M1`, `SIXTH2-M2`, and
  `SIXTH2-M3`, plus Low `SIXTH2-L1`, `SIXTH2-L2`, and `SIXTH2-L3`. The
  evidence proves only discovery and selection; its allowlisted Python
  byte-compilation and sysdiff-centered aggregate smoke do not prove that
  `openunlink` builds, tests, or ships.
- Keep the live repair-before-expansion rule. The next executable
  `openunlink` action is a separately governed implementation playbook only
  after that gate and prior sequencing clear; its first deliverable must be a
  normative contract resolving the descriptor-cap behavior (`SIXTH2-M1`),
  filesystem link-count disclaimer (`SIXTH2-M2`), and status-1 caller
  discriminator (`SIXTH2-M3`) before CODE. Preserve the Low findings until a
  later review closes them.

## Current Decisions

- Explicit snapshot comparison only: `sysdiff compare BEFORE AFTER` reads two
  user-provided files and does not capture live system state, walk trees,
  query packages/services, persist data, or use the network. Paths are opened
  with `fopen` mode `rb`; there is no separate regular-file classification.
- Format 1 is line-oriented plain text with one `key=value` record per line;
  values are opaque after line-ending removal; keys use documented safe bytes
  with at least one `.`, no `..`, no leading `/`, and no trailing `.`.
- Both snapshots must fully validate before any diff stdout; validation errors
  exit `2` with empty stdout; stdout I/O failures also exit `2` and may leave
  partial output. At startup `SIGPIPE` is ignored (POSIX) so closed pipes
  become `EPIPE`; Linux (Ubuntu) is the supported and CI-gated runtime.
- Diff values and untrusted diagnostic paths/commands render as printable
  ASCII (`\\` and `\xNN`); comparison remains raw bytes and is unaffected by
  display escaping.
- Deterministic limits per snapshot: 65,536 bytes/line, 65,536 entries, and
  16 MiB total bytes read (including comments and blanks); oversize input fails
  closed rather than truncating. When the overflowing byte is NUL, the
  byte-limit diagnostic precedes the embedded-NUL diagnostic.
- Ownership: `parse_snapshot` frees all partial state on error and transfers a
  fully built `Snapshot` only on success; callers must `snapshot_free` after
  comparison. Maintainers treat unclear ownership as a defect.
- Single small C17 translation unit built by `make`; `make quality` (aliased by
  `check`) is the canonical release gate including man-check, sanitizers, and
  Valgrind status `99`. Sorting uses bytewise `strcmp` (locale-independent);
  shell fixtures set `LC_ALL=C`.
- Whitespace-only space/tab lines are ignored as blanks; whole-line `#`
  comments allow leading spaces/tabs; inline `#` is data.
- Accepted Low limitation: changed-line ` -> ` delimiter is human-readable and
  not a reversible interchange format when values contain that sequence.
