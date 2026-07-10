# AI-Assisted Development

AI tools participated in developing `sysdiff`. That fact is not a substitute
for evidence: the project keeps the utility deliberately narrow and anchors
behavior in the public snapshot-format specification.

The safeguards used for this release are concrete and reproducible:

- explicit scope, command, input, output, and exit-status contracts;
- strict C17 compilation with warnings treated as errors under GCC and Clang;
- clang-format, clang-tidy, cppcheck, and Clang static analysis;
- AddressSanitizer, UndefinedBehaviorSanitizer, and Valgrind;
- deterministic shell fixtures and pytest coverage for normal and malformed
  input paths;
- a release-focused human-readable review and Ubuntu CI that runs
  `make quality`.

AI-generated suggestions can still be wrong. Contributions should be judged by
the specification, code, tests, review, and reproducible checks—not by the
identity of the authoring tool. This repository intentionally does not publish
private prompts, private orchestration records, or claims about model behavior
that cannot be independently verified.
