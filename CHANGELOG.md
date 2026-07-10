# Changelog

## 0.1.0 — 2026-07-10

Initial public release candidate of `sysdiff`.

- Compares two explicit `key=value` snapshot files without inspecting the live
  system.
- Emits deterministic sorted added (`+`), removed (`-`), and changed (`~`)
  records; reports `no changes` for identical snapshots.
- Validates keys, duplicate records, embedded NUL bytes, line, entry, and
  total-byte limits, and avoids partial stdout on validation failures.
- Renders diff values and untrusted diagnostic paths/commands as printable
  ASCII with `\\` and `\xNN` escaping; comparison remains raw and opaque.
- Detects stdout write/flush failures on compare and informational paths,
  including closed stdout pipes (`EPIPE`) after ignoring `SIGPIPE` on Linux,
  returns status `2` with a `stdout write error: <strerror>` diagnostic (`EIO`
  if errno is unset), and may leave partial stdout in that case only.
- Accepts LF, CRLF, final lines without a newline, comments, and blank or
  whitespace-only space/tab lines.
- Provides strict compiler, formatting, static-analysis, sanitizer, Valgrind,
  fixture, pytest, smoke, and Ubuntu CI configuration. Default `make` builds
  the binary; `make test` runs functional tests; `make quality` is the full
  gate.
- Ships a section-1 manual page at `man/sysdiff.1`, linted by `make man-check`
  (part of `make quality`) with groff warnings enabled.

Known limitations: values are opaque text and changed records use a human
readable `old -> new` presentation, so that line format is not reversible when
values themselves contain ` -> `. `sysdiff` does not collect live snapshots.
There is no install target or packaged distribution yet.
