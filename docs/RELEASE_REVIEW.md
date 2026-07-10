# v0.1.0 Release Review

Reviewed on 2026-07-10 as the final pre-publication audit of the local release
candidate.

## Scope

- `src/sysdiff.c`: command dispatch, untrusted-input parsing, ownership,
  integer and resource bounds, deterministic comparison, terminal-safe
  rendering, diagnostics, and output-failure handling.
- `Makefile`, shell fixtures, pytest, sanitizers, static analyzers, and
  Valgrind composition.
- README, format specification, decisions, design, release notes, license,
  contribution/security guidance, AI-development disclosure, Ubuntu CI, and
  the section-1 man page.
- Public-seed curation: no private orchestration state, raw run artifacts,
  caches, build output, old review transcripts, or copied Git history.

## Adversarial findings and repairs

The last-stop review initially rejected publication with five Medium findings:

1. raw terminal-control bytes from untrusted values;
2. successful exit despite stdout failure (`/dev/full`);
3. aggregate inputs capable of multi-gigabyte memory pressure;
4. Valgrind and cppcheck gates that could miss findings; and
5. stale and contradictory public documentation.

All were repaired and regression-tested. Values and user-controlled diagnostic
text now render as printable ASCII with deterministic escaping. Every snapshot
has a 16 MiB total-byte cap in addition to line and entry caps. Stdio failures,
including closed Linux/POSIX pipes, return status `2`. Valgrind uses reserved
status `99` and fails on any non-empty error log; cppcheck findings now fail the
build. Public contracts and build instructions match the implementation.

Subsequent review iterations fixed C/POSIX details found by the strengthened
gates, including format-argument typing, byte-limit/NUL precedence, SIGPIPE
handling, and removal of unnecessary feature-test coupling. ASan leak detection
is enabled rather than suppressed.

## Verdict

No known Medium-or-higher finding remains in the local release candidate. It is
ready to become a public repository. Do not tag or publish the GitHub release
until the newly created repository's first Ubuntu Actions run has completed
successfully; that external CI run cannot exist before the remote exists.

## Accepted Low limitations

- Changed output is human-readable, not a reversible interchange format. A
  value containing ` -> ` makes the displayed old/new boundary ambiguous.
- Version 0.1.0 is Linux-focused and CI covers Ubuntu, not a distribution or
  architecture matrix.
- Packaging is source-first: there is no install target or package in 0.1.0.
  A section-1 man page is present at `man/sysdiff.1` and is checked by
  `make man-check` as part of `make quality`.
- `sysdiff` compares explicit snapshots only; it does not collect live system
  state.

## Evidence

The canonical local Linux gate is `make quality`: strict GCC and Clang,
clang-format, clang-tidy with warnings as errors, cppcheck with a failing error
status, man-page lint via groff (`make man-check`), shell fixtures, pytest,
ASan plus LeakSanitizer, UBSan, and Valgrind.
The curated public suite contains 32 passing product tests. (The governed source
repository also runs nine internal infrastructure tests; those are deliberately
absent from the public seed.) Ubuntu CI installs the declared tools, including
groff, and runs exactly the same command; `actions/checkout` is pinned to the
official immutable v6 tag SHA. Do not treat a GitHub Actions result as passed
until a remote exists and its first run completes successfully.
