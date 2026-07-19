# Malformed Snapshot Fuzz Regression Contract

## Overview

This contract defines a bounded, reproducible malformed-snapshot regression
corpus for `sysdiff`. The corpus exercises the real snapshot parser in
`src/sysdiff.c` through the existing `sysdiff compare BEFORE_SNAPSHOT
AFTER_SNAPSHOT` command surface. It does not expand product scope: there is no
live system capture, directory scanning, networking, persistence, new CLI
verbs, or alternative snapshot encodings. Every case is a plain-text byte
stream derived from the format-1 grammar in
`docs/sysdiff-snapshot-format-and-scope.md`, then deliberately truncated,
corrupted, or otherwise made invalid so rejection paths are forced. Generation
must be deterministic; where pseudorandom mutation helps explore hostile
variants, generators must use fixed, documented seeds so the same corpus bytes
are reproduced across hosts and CI runs. Each case carries a per-case timeout
and enough reproduction detail that a failing assertion can be re-run without
guesswork. The required safety assertions are that malformed input must not
crash, trip AddressSanitizer or UndefinedBehaviorSanitizer, hang past the
case timeout, or be accepted successfully when the grammar and resource limits
require rejection with empty compare stdout and exit status `2`.

## Problem

Valid-fixture coverage proves that well-formed snapshots compare correctly, but
it does not systematically prove that hostile or truncated inputs fail closed.
The format-1 parser accepts only `key=value` records with a narrow key grammar,
rejects embedded NUL bytes, rejects duplicates, and enforces line, entry, and
total-byte limits without silent truncation. Adversarial inputs that omit the
separator, empty the key, inject consecutive dots, embed NULs, cut mid-line,
overflow limits by one byte, or scramble otherwise-valid prefixes can still
reach `parse_snapshot`. Without a bounded regression corpus driven by the real
executable under sanitizers and timeouts, defects such as buffer over-reads,
leaks on early cleanup, infinite loops on pathological line endings, or
accidental acceptance of invalid keys can slip past happy-path tests. The
project needs a durable contract that keeps fuzz-style malformed coverage
reproducible and scoped to the existing snapshot grammar, rather than an open
ended mutator that invents new product behavior or non-deterministic flakes.

## Constraints

- Scope remains explicit-snapshot-only: corpus cases are files fed to
  `sysdiff compare`; no new commands, capture modes, or formats.
- Corpus size and per-file byte budgets must stay bounded so local and CI runs
  finish predictably; prefer a fixed catalog of named cases plus a small
  seeded-mutation set over unbounded online fuzzing in the default gate.
- Case generation must be deterministic. Hand-authored fixtures use fixed
  bytes. Pseudorandom truncation, byte flips, insertions, and deletions must
  use documented fixed seeds, fixed mutation budgets, and stable naming so
  regenerating the corpus yields identical paths and contents.
- Hostile truncation and corruption must be derived from the actual snapshot
  grammar: start from valid `key=value` lines (including comments, blanks,
  CRLF/LF endings, empty values, and documented resource prefixes), then apply
  grammar-aware attacks such as removing `=`, emptying keys, inserting `..`,
  leading `/`, trailing `.`, illegal key bytes, embedded NUL, duplicate keys,
  mid-record cuts, over-limit lines/entries/total bytes, and partial final
  lines without inventing unrelated binary formats.
- Each case declares an expected rejection outcome (exit status `2`, empty
  stdout on compare validation failure) and a per-case wall-clock timeout
  short enough to catch hangs without masking legitimate parse work.
- Failure reports must be actionable: case id, generator seed (if any), input
  path(s), exact command line, observed exit status, sanitizer/signal status,
  timeout flag, and a pointer to the corpus bytes or regeneration recipe.
- Assertions must forbid crash (non-zero signal / abort), ASan/UBSan failure,
  hang past the per-case timeout, and successful acceptance (exit `0` or `1`
  with parsed-as-valid behavior) when rejection is required.
- Keep implementation aligned with existing quality gates (`make test`,
  sanitizer-test, valgrind where practical) and do not add runtime dependencies.

## Acceptance Checks

- A documented, versioned corpus (or deterministic generator recipe) produces
  the same malformed snapshot bytes on every host when seeds and mutation
  budgets are unchanged.
- Every corpus case is exercised by invoking the real `build/sysdiff` compare
  path (not a stub parser), with one operand malformed when testing single-file
  rejection, or with grammar-derived pairs when both sides must validate.
- Grammar-derived truncation and corruption categories above are each
  represented by at least one deterministic case; seeded pseudorandom cases
  record their fixed seeds in the corpus metadata or generator source.
- Every case has an explicit per-case timeout; exceeding it fails the check as
  a hang, not as a pass.
- On required-rejection cases, the harness asserts exit status `2`, empty
  compare stdout, no fatal signal, no ASan/UBSan diagnostic, and completion
  before the timeout.
- On harness failure, output includes actionable reproduction details: case
  identifier, seed if used, snapshot path(s), full command, exit code, timeout
  or sanitizer outcome, and how to regenerate or locate the exact input bytes.
- The corpus and harness remain within the existing product and test surface:
  no live probing, no new snapshot format, and no expansion of CLI scope beyond
  what `docs/sysdiff-snapshot-format-and-scope.md` already defines.
- Passing this contract means malformed input cannot crash, sanitizer-fail,
  hang, or be successfully accepted when the snapshot grammar and resource
  limits require rejection.
