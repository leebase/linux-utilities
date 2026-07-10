# AI-Assisted Development

AI tools performed most implementation and review work on `sysdiff`. The human
owner set the product objective, approved the public behavior and copyright,
and retains publication authority. AI participation is not treated as evidence
of quality: the project keeps the utility deliberately narrow and anchors
behavior in the public snapshot-format specification.

The safeguards used for this release are concrete and reproducible:

- explicit scope, command, input, output, and exit-status contracts;
- strict C17 compilation with warnings treated as errors under GCC and Clang;
- clang-format, clang-tidy, cppcheck, and Clang static analysis;
- AddressSanitizer with leak detection, UndefinedBehaviorSanitizer, and
  Valgrind;
- deterministic shell fixtures and pytest coverage for normal and malformed
  input paths;
- an adversarial release review performed separately from the coding worker;
- Ubuntu CI that runs `make quality` unchanged.

The release process deliberately treated worker summaries as untrusted. A
separate planning/review agent inspected each diff, reran tests, rejected the
first release candidate, and returned concrete failures to a Cursor/Grok coding
agent until the strengthened gate passed. The public release review records the
findings and repairs without publishing private prompts or orchestration state.

AI-generated suggestions can still be wrong. Contributions should be judged by
the specification, code, tests, review, and reproducible checks—not by the
identity of the authoring tool. The code and tests are intentionally small
enough for a human C programmer to audit directly. This repository does not
publish private prompts, private orchestration records, or claims about model
behavior that cannot be independently verified.
