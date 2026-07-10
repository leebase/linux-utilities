# Code Review: Makefile Quality Gates

## Verdict

Pass at the High/Critical routing threshold. The repair adds the missing
`check` target, keeps `make-quality` available, and preserves the existing
`clean` target. The Makefile repair is narrow and consistent with the requested
quality-gate surface.

## Findings

| ID | Severity | File | Location | Problem |
| --- | --- | --- | --- | --- |
| F001 | Medium | `Makefile` | `valgrind-test`, lines 49-59 | `valgrind-test` still reuses the current `build/sysdiff` binary. `make-quality` rebuilds with GCC before Valgrind, but a standalone `make valgrind-test` after `make sanitizer-test` can still run Valgrind against an ASan/UBSan binary. |

Proposed fix for F001: make `valgrind-test` force a clean non-sanitized build
before invoking Valgrind, or encode the standalone precondition clearly in the
Makefile so it is not mistaken for a robust post-sanitizer quality gate.

## Checks Run

| Command | Exit | Notes |
| --- | ---: | --- |
| `grep -q 'make-quality' Makefile` | 0 | Confirmed the required aggregate quality target remains present. |
| `make -n make-quality 2>&1` | 0 | Confirmed the aggregate quality target is dry-runnable and expands the intended command sequence. |

These checks are the re-executable Makefile validation checks from the governed
repair step. They verify the required `make-quality` target exists and that the
aggregate quality target can be invoked in dry-run mode without a Makefile
parse or dependency-resolution failure.

## Lens Notes

Target contract: `make-quality`, `check`, and `clean` are all present. The new
`check: test-suite` alias delegates to the existing shell and pytest gate rather
than introducing a separate weaker test path.

Dry-run behavior: `make -n make-quality` exits 0 and expands the expected clean
GCC build, clean Clang build, test-suite, sanitizer-test, clean GCC rebuild,
and valgrind-test sequence.

Quality-gate robustness: the aggregate `make-quality` path avoids the known
sanitizer-to-Valgrind conflict by rebuilding before Valgrind. The standalone
`valgrind-test` target still depends only on `build/sysdiff`, so F001 remains
open as a Medium inherited Makefile concern.
