# v0.1.0 Release Review

Reviewed on 2026-07-10 for the public release candidate.

## Scope reviewed

- `src/sysdiff.c`: parsing, bounds checks, ownership, deterministic merge, and
  diagnostics.
- `Makefile`: strict compilers, static analysis, sanitizers, Valgrind, and test
  composition.
- Shell fixtures, pytest coverage, and smoke scripts.
- User-facing documentation, snapshot specification, decisions, contribution
  guidance, license placeholder, changelog, and Ubuntu CI.

## Result

No Medium-or-higher findings remain after the release repairs. The previous
portable-compiler and smoke-start findings are verified resolved: pytest uses
`$CC` with `cc` fallback, and the smoke start helper exits immediately. The
previous whitespace-only-line contract mismatch is resolved by accepting
space/tab-only lines as blank. The unreachable `copy_range` `SIZE_MAX` guard
was removed; bounded input is enforced by the documented line limit and the
real allocation-growth overflow guards remain in place.

## Accepted Low limitation

Changed output is intentionally human-readable rather than reversible. A value
containing ` -> ` makes the displayed old/new boundary ambiguous to a parser.
Values remain opaque and this is documented in the changelog and decisions;
format `1` consumers should treat changed lines as display output, not a data
interchange format.

## Evidence

On Linux, `make quality` passed after this review. It runs GCC and Clang strict
checks, formatting, clang-tidy, cppcheck, shell fixtures, pytest, ASan, UBSan,
and Valgrind. The CI workflow installs the declared tools on Ubuntu and runs
the same canonical command.
