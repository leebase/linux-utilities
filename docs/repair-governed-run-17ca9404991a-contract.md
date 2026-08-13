# Overview

This is the bounded repair contract for the trusted failure in governed run
`17ca9404991a`, playbook `template_repair_before_review_feature_delivery`.
The origin run is **FAILED**, not a passed delivery: its `step_05_implement_slice`
validator ran `python3 -m pytest tests/ -q`, and both attempts ended with the
same three failures. The repair concerns the governed-workspace user-journey
abstraction and its compatibility oracles. It is not a new `sysdiff` feature,
and it must not promote the origin run's candidate state or worker exit code to
product evidence. The whole pytest suite, the existing hash-pinned smoke path,
and every pinned user journey remain the definition of done.

# Problem

The preserved run evidence records attempt 1 as exit status `1` with `3 failed,
584 passed, 19 skipped` in 113.82 seconds, and attempt 2 as exit status `1`
with the same `3 failed, 584 passed, 19 skipped` in 117.59 seconds. The failed
tests were `test_workspace_rule_paths_fail_closed_for_symlink_escape`, which
received a result-schema error instead of the required `inside the workspace`
containment failure for a symlink escape; `test_commands_use_token_prefixes_and_direct_argv`,
which rejected a direct allowlisted `python3 -c` argv claim because operator
characters inside a quoted argument were misclassified; and
`test_blast_radius_is_additive_and_non_product`, whose forbidden-operation
source scan matched a literal listed by its own assertion. These are observable
full-suite failures, not evidence that a focused test or a worker exit code was
enough. The repair must restore fail-closed path handling, faithful direct-argv
verification, and a non-self-defeating scope oracle without weakening any
security or governance rule.

# Constraints

The repair must resolve result, manifest, contract, seed, finding, and other
governed paths from the canonical workspace root before opening or validating
their contents; lexical, absolute, parent, current-directory, and symlink
escapes must fail closed with a containment diagnostic. Shell-word parsing and
token-by-token allowlist-prefix matching remain mandatory, and accepted claims
must execute as direct argv with the governed workspace as `cwd`; actual shell
control syntax, malformed claims, prefix misses, wrong-cwd evidence, and zero
verifiable claims remain failures. The pinned user-journey manifest, its hash,
the existing smoke manifest and helper hashes, and all required journey names
and traces are immutable acceptance inputs. Tests are authored before
implementation. Repairs may update existing callers, fixtures, and tests that
encode superseded behavior, but only when the intended contract is preserved;
removing a regression, narrowing an allowlist, hiding a journey, or converting
a security assertion into a skip is not a repair. The validator's workflow
failure is non-pass evidence and does not alter any utility CLI exit status.

The closed hazard taxonomy is exactly: `PATH_ESCAPE` for lexical, cwd, or
symlink containment failures; `COMMAND_INJECTION` for shell-control syntax,
unsafe parsing, or allowlist mismatch; `ORACLE_TAMPERING` for changes to pinned
journeys, traces, authorities, smoke inputs, or command allowlists;
`RESULT_FABRICATION` for missing or malformed journeys, findings, claims, or
unreproducible evidence; and `BLAST_RADIUS` for unrelated product changes,
scope substitution, networking, installation, packaging, publication, release
behavior, or a misleading test oracle. Every relevant hazard must map to one
of these five classes. No sixth hazard class may be invented during repair.

# Delivery Plan

1. Preserve the run evidence and reproduce the three named failures with the
   new focused regression first. The regression must pin the symlink-escape
   ordering, quoted-argument direct execution, and scope-oracle behavior; it
   must also prove that rejected commands do not run and that the canonical
   workspace is used as `cwd`.

2. Keep the regression red against the defective behavior, then implement the
   smallest repair in the governed-workspace path and journey-validation
   helpers. Resolve and contain paths before schema loading, make shell syntax
   detection aware of parsed quoting while still rejecting real control
   operators, and retain direct argv execution plus exact exit/output checks.
   If the blast-radius test inspects source text, revise its fixture or oracle
   so the assertion does not match its own forbidden-token inventory while it
   continues to reject the forbidden behavior. Update affected callers only
   where their interfaces encode the corrected contract; preserve all existing
   fixtures and tests unless they explicitly encode superseded behavior.

3. Run the focused regression and every affected existing test, then run the
   complete `python3 -m pytest tests/ -q` suite from the governed workspace.
   A focused green result is insufficient. Recheck changed paths against the
   allowlist and inspect that no product CLI, smoke input, pinned journey, or
   unrelated test was weakened. Run the existing hash-pinned smoke gate and
   independently replay every pinned user journey only after the complete
   suite is green; record actual statuses and counts rather than inferred
   success. The whole suite is the definition of done, together with the
   smoke and journey gates below.

# Acceptance Checks

- **AC-1 — Regression and affected-test closure:** The new regression covering
  symlink containment, quoted direct-argv execution, and the corrected
  non-product scope oracle must pass, and all affected existing path,
  validator, user-journey, and compatibility tests must pass. The check is
  successful only with exit status `0`; any failed test, unexpected error, or
  test suppression is a failure. Its evidence must identify the exact focused
  command, affected existing tests, pass/skip counts, and the changed-path
  audit. A passing regression alone cannot satisfy this check or imply that
  the origin run has been rewritten.

- **AC-2 — Complete-suite closure:** `python3 -m pytest tests/ -q` must pass
  as a complete suite, not merely the new regression or the abstraction test
  module. The command must exit `0`, with all expected tests collected and no
  unexpected failures, collection errors, or newly hidden cases. Any nonzero
  exit, timeout, or claim that a filtered or focused invocation is equivalent
  fails AC-2. This complete-suite result is the authoritative definition of
  done for the repair and must be recorded with its real counts and status.

- **AC-3 — Pinned user-facing gates:** The existing hash-pinned smoke path,
  including its unchanged manifest and helper chain, must pass with its
  required start/check success and no blocking errors, and every journey in
  the pinned user-journey manifest must pass the structural and direct-command
  verification gates. The smoke and user-journey commands must exit `0`; a
  skipped, unverified, substituted, or newly edited journey does not count.
  Their evidence must preserve the pinned hashes, actual command exit codes,
  observed output checks, journey coverage, and workspace containment. AC-3 is
  required in addition to AC-1 and AC-2, and no prior run artifact may be used
  to manufacture a pass.

## Repair Record

The root cause was three compatibility defects at the Agent-Orch governed-workspace boundary: an escaping symlink could be opened before containment was reported, raw operator-character scanning rejected quoted command data that should have remained a direct argv argument, and the blast-radius oracle matched the forbidden-token inventory embedded in its own assertion. The affected implementation boundary is the validator and workspace-validation layer: canonical path resolution and containment before schema or artifact use, quote-aware allowlist parsing with direct execution in the governed workspace, and a non-self-matching scope oracle. `src/sysdiff.c`, its CLI, pinned manifests, smoke inputs, and user-facing behavior are outside this repair.

The regression coverage exercises escaping result, manifest, contract, seed, and finding paths; quoted operator-looking data with governed `cwd` and literal argv preservation; rejection of pipelines, redirections, malformed claims, and prefix misses without sentinel creation; and blast-radius traceability while retaining AC-1, AC-2, and AC-3. Preserved validator evidence records `python3 -m compileall tests/test_governed_run_17ca9404991a_repair.py` exiting `0`, and the focused pytest command exiting `0` with `9 passed`, `0 failed`, and `0 skipped`; these are preserved results, not reruns in this documentation step. The compatibility implication is additive fail-closed validation and faithful direct-argv verification, with the failed origin run still distinct from product evidence. No README, man-page, or CHANGELOG change is required because this repair adds no user-facing command or option and changes no sysdiff feature or interface.
