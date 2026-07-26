# Project History

`sysdiff` began as the first utility in the `linux-utilities` suite: a small,
auditable C program for comparing explicit system snapshot files rather than
probing a live host. Early governed slices established the format-1
`key=value` contract, fixture-backed `compare` behavior, strict Makefile
quality targets, and AgentFlow memory for orchestration. Core parser and
comparer work landed through Agent-Orch runs that enforced validate-before-
output semantics, duplicate-key detection, opaque values, and deterministic
bytewise key ordering. Subsequent hardening added explicit line, entry, and
16 MiB total-byte limits, centralized parse cleanup, portable pytest compiler
selection, and an immediate smoke start helper. An adversarial last-stop audit
rejected the first public candidate, then drove terminal-safe escaping,
checked stdout/EPIPE handling, honest Valgrind/cppcheck failure semantics, and
leak-enabled ASan. A section-1 man page and warning-gated groff check joined
the gate before the curated seed was published. This history is product
evidence: append new cycles; do not erase prior engineering record.

## Engineering Timeline

- Snapshot-format and initial-scope contract authored for explicit
  `key=value` comparison only (`docs/sysdiff-snapshot-format-and-scope.md`).
- Minimal C quality-gate harness and fixture-backed comparison smoke path.
- Core parser/comparer slice: sorted map diff, empty stdout on validation
  errors, opaque values, CRLF/LF handling.
- Resource-limit and ownership hardening in `src/sysdiff.c` with Makefile
  sanitizer and Valgrind targets that clean/rebuild as required.
- Fixture acceptance coverage for status 0/1/2, ordering independence,
  comments/blanks, limits, and malformed after-path cases.
- C craftsmanship review passed at High/Critical before further features.
- 2026-07-10 release preparation: F001–F004 follow-ups resolved; Ubuntu CI
  wired to `make quality`; public docs and MIT license curated.
- Adversarial remediation of five Medium findings; governed suite expanded
  (41 tests in the private tree; curated public seed omits internal harness
  checks).
- Man page `man/sysdiff.1` plus `make man-check`; public repo
  `leebase/linux-utilities` pushed; CI run `29119972847` green on `fbdf071`.
- 2026-07-17: GitHub `v0.1.0` tag/release pointed at curated public commit
  `fbdf071` (public and private histories diverge by design).
- 2026-07-17/18 — Governed run `e7bbd28465b5`
  (`sysdiff_complete_release_documentation_set`) completed the root release
  documentation set: authored HISTORY, DECISIONS, QUALITY, TESTING, ROADMAP,
  and STATUS; reconciled README, CHANGELOG, architecture, and `man/sysdiff.1`
  against implemented behavior without running compilers or the full quality
  gate in the documentation-writing steps. Repair step corrected FILES
  open-mode wording, SIGPIPE/Linux support distinction, ownership notes,
  Valgrind-skip/`/dev/full`/`LC_ALL=C`/`SYSDIFF_BIN` portability notes, and
  quality-tool prerequisites. User smoke gate passed attempt 1
  (`artifacts/user-smoke/result.json`: `app_started` true,
  `core_flow_completed` true, `start_exit_code` 0, `check_exit_code` 0, empty
  `blocking_errors`). Independent review
  `code-reviews/sysdiff-release-documentation-review.verdict.json` is `pass`
  at the High/Critical threshold with two Low man-page findings (F1 NAME
  `\(em` vs ` \- `; F2 FILES directory open-vs-read wording). Allowlisted
  review check `python3 -m compileall tests/test_check_tools.py` exited 0.
  This cycle verifies documentation accuracy and smoke continuity; it does
  not itself re-execute `make quality` or assert a new product release gate.

## Release Preparation

Governed run `580b0f6ff811` (`prepare_sysdiff_release_package_and_notes`)
prepares the unpublished `sysdiff` **0.1.0** release candidate. Version
`0.1.0` is read from existing product evidence (`src/sysdiff.c` `--version`,
`man/sysdiff.1`, README, and the `0.1.0` changelog entry). The Makefile gains
a plain `release` target that stages intentional product files under `/tmp`,
writes `artifacts/sysdiff-release.tar.gz` with archive root
`sysdiff-release/`, and emits `artifacts/sysdiff-release.tar.gz.sha256` with
the archive basename so `(cd artifacts && sha256sum -c …)` succeeds (repair
for governed run `c847e01d15fe`, which failed when a nested `SHA256SUMS`
listed only a basename checked from another directory). Follow-up repair for
review findings REL-C847-001, REL-C847-002, and M1: member selection uses
`git ls-files` over `RELEASE_PATHSPECS` (tracked-only, matching `make dist`;
untracked scratch cannot ship), the live deliverable is regenerated from the
repaired recipe under `artifacts/`, and QUALITY.md **Release Verification**
re-derives the digest from that archive. Packaging includes source, Makefile,
license, user documentation, man pages, scripts, and tests while excluding Git
metadata, orchestration state, caches, compiled binaries, prior archives, and
temporary files. Attempt-2 repaired High H1: missing `RELEASE_PATHSPECS`
entries now fail closed in the parent shell (no process-substitution swallowed
`exit`), and staging asserts required tests/scripts/docs members before tar.
Pytest coverage pins fail-closed packaging, basename checksum co-location, and
tracked-only selection. RC-001 (bytewise key order for mixed-case keys such as
Alpha/alpha) is verified with pytest names containing `rc_001` plus existing
shell/fixture goldens; no compare-behavior change was required. This
preparation does not publish a GitHub release or claim Lee-authorized product
release.

## First Independent Release-Candidate Review Cycle

Governed run `8a3470eff7d3` (`sysdiff_first_independent_rc_review_cycle`)
recorded the first independent release-candidate review cycle for `sysdiff`
after closing the mixed-case ordering regression gap (RC-001) in tests and
fixtures. User smoke passed with start/check exit 0 and empty blocking errors;
smoke-bound pytest reported `127 passed in 10.58s`. Independent review
`code-reviews/sysdiff-rc-review-cycle-1.verdict.json` is `pass` (0
Medium/High/Critical, 7 Low F1–F7); allowlisted `python3 -m pytest tests/ -q`
exited 0 with `127 passed in 11.06s`. This cycle does not claim that `sysdiff`
is released or that the mission is complete. A second consecutive review cycle
with no release-blocking findings is still required before mission completion.

## Second Independent Release-Candidate Review Cycle

Governed run `c84986cf0c81`
(`sysdiff_second_independent_release_candidate_review_cycle`) recorded the
second independent release-candidate review cycle. User smoke passed with
start/check exit 0 and empty blocking errors; smoke-bound pytest reported
`127 passed in 10.84s`. Independent review
`code-reviews/sysdiff-rc-second-independent-cycle.verdict.json` is `pass`
under the Medium threshold (0 Medium/High/Critical, 9 Low L1–L9); allowlisted
`python3 -m pytest -p no:cacheprovider tests/ -q` exited 0 with
`127 passed in 10.96s`. RC-001 strcasecmp-mutant kill was re-verified
independently (behavioral divergence on mixed-case fixtures; robust to qsort
ties; full suite detects mutant return with 1 failed / 126 passed). Fresh
quality evidence this cycle covers step-1 non-writing validation plus
smoke/review pytest suites, not a fresh full `make quality` re-run.
Consecutive clean RC review cycles: 2. This cycle does not by itself declare
`sysdiff` released or authorize publication.

## 2026-07-24 — pathaudit vertical-slice bootstrap

Governed run `4dec475ef201` (`pathaudit_bootstrap_deterministic_scanner`)
delivered the second utility in the suite as an additive vertical slice:
`docs/pathaudit-contract.md`, ISO C17 `src/pathaudit.c`, `man/pathaudit.1`,
`tests/test_pathaudit.py` (26 deterministic contract tests), Makefile
quality/sanitizer/Valgrind wiring that preserves every existing `sysdiff`
command and artifact, and README/QUALITY/TESTING documentation. The scanner
inspects only explicitly supplied PATH directory roots; it never reads the
`PATH` environment variable, walks directory contents, or remediates. Step-3
validation recorded: GCC and Clang
`-std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only`; clang-format,
clang-tidy, cppcheck, and Clang `--analyze` clean; `pytest
tests/test_pathaudit.py` → 26 passed in 0.38s; full `pytest tests/` → 158
passed in 14.98s (132 prior + 26 pathaudit); ASan and Valgrind help probes
exited 0. Review confirmed the contract suite clean under ASan (leak
detection), UBSan (halt-on-error), and Valgrind memcheck. User smoke
(`artifacts/user-smoke/result.json`) passed with start/check exit 0 and empty
blocking errors; check.log pytest reported `158 passed in 12.88s`. The pinned
sysdiff smoke oracle (`tests/smoke_manifest.json`) does not directly exercise
pathaudit; pathaudit coverage is the dedicated pytest module. Independent
review `code-reviews/review-pathaudit-bootstrap.verdict.json` is `pass` at the
High threshold (0 Critical/High, 2 Medium PA-M1/PA-M2, 7 Low PA-L1–PA-L7).
This cycle does not claim that `pathaudit` is released, installable via
`make install`, or that a product release was published.

## 2026-07-26 — Detect writable resolved-executables through PATH

Governed run `574d06adfc2a` (`template_repair_before_review_feature_delivery`)
delivered Detect writable resolved-executables through PATH for
`pathaudit --path` and `pathaudit --command`. The slice extends the shared
directory trust model to final executable targets resolved through PATH:
owner-only write modes stay silent; `S_IWGRP` / `S_IWOTH` reuse
`GROUP_WRITABLE` / `WORLD_WRITABLE` on the executable `realpath`; symlink
resolution follows the final target; shebang/ELF probing keeps non-executable
same-basename decoys out of the candidate set; unsafe inspection reject-closes
via `INSPECTION_ERROR_N`; explicit-root mode still never searches executables;
writability findings sort with directory hazards and precede `SHADOWED`. Exact
deliverables: `tests/test_pathaudit.py`, `src/pathaudit.c`. Exact step-3
verification: `clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only
src/pathaudit.c` exited 0; `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p
no:cacheprovider tests/ -q` → 269 passed, 1 skipped. User smoke
(`artifacts/user-smoke/result.json`) passed with start/check exit 0 and empty
blocking errors; check.log pytest reported `269 passed, 1 skipped in 18.74s`.
The pinned sysdiff smoke oracle does not directly exercise
writable-executable `--path` / `--command` detection; pathaudit coverage is
`tests/test_pathaudit.py`. Independent review
`code-reviews/review-pathaudit-writable-executables.verdict.json` is `pass`
(0 Critical/High/Medium, 2 Low PA-W1/PA-W2). Allowlisted review check
`python3 -m pytest tests/ -q -p no:cacheprovider` → 269 passed, 1 skipped in
~18s. This cycle does not claim that `pathaudit` is released, installable via
`make install`, or that a product release was published.

## 2026-07-26 — Detect executables with unsafe ownership

Governed run `1d5eedc01202` (`template_repair_before_review_feature_delivery`)
delivered Detect executables with unsafe ownership for `pathaudit --path`
and `pathaudit --command`. The slice adds `UNSAFE_OWNER` on final
followed-target executable realpaths when `st_uid` is neither UID 0 nor the
invoking real UID from `getuid()` (not `geteuid`); ownership composes with
existing writability findings via shared code-rank sort (`UNSAFE_OWNER`
after `GROUP_WRITABLE`/`WORLD_WRITABLE`, before `SHADOWED`); shebang/ELF
probing keeps non-executable decoys out of the candidate set; candidates are
never executed; explicit-root mode never searches executables and never emits
`UNSAFE_OWNER`. Exact deliverables: `tests/test_pathaudit.py`,
`src/pathaudit.c`, `docs/pathaudit-contract.md`, `README.md`,
`man/pathaudit.1`, `CHANGELOG.md`, `architecture.md`. Exact step-4
verification: `make quality` exited 0; `clang -std=c17 -Wall -Wextra
-Wpedantic -Werror -fsyntax-only src/pathaudit.c` exited 0; `cppcheck
--quiet --enable=all --suppress=missingIncludeSystem --error-exitcode=1
src/pathaudit.c` exited 0; `python3 -m pytest -p no:cacheprovider tests/ -q`
→ 271 passed, 14 skipped in 19.02s. User smoke
(`artifacts/user-smoke/result.json`) passed with start/check exit 0 and empty
blocking errors; check.log pytest reported `271 passed, 14 skipped in
19.94s`. The pinned sysdiff smoke oracle does not directly exercise an
ownership-specific `--path` / `--command` user flow; pathaudit coverage is
`tests/test_pathaudit.py`. Independent review
`code-reviews/review-pathaudit-unsafe-executable-ownership.verdict.json` is
`pass` (0 Critical/High/Medium/Low formal findings; empty `findings`).
Allowlisted review check `python3 -m pytest tests/ -q -p no:cacheprovider`
→ 271 passed, 14 skipped in ~19s. The 14 skips are privilege-gated
foreign-owner / root-owner fixtures that honestly `pytest.skip` on this
non-root host. This cycle does not claim that `pathaudit` is released,
installable via `make install`, or that a product release was published.

## 2026-07-26 — Detect unsafe ownership of PATH directories

Governed run `50c0b4936d50` (`template_repair_before_review_feature_delivery`)
delivered Detect unsafe ownership of PATH directories for `pathaudit --path`
and `pathaudit --command`. The slice extends the executable ownership trust
rule to every usable PATH directory and each ancestor through `/`: emit
`UNSAFE_OWNER` naming the canonical offending directory `realpath` when the
final followed-target `st_uid` is neither UID 0 nor the invoking real UID
from `getuid()` (not `geteuid`); shared ancestor realpaths deduplicate to
the lowest PATH index; missing, empty, and non-directory components invent
no ownership lines; `owner_uid_is_trusted` is shared with executable
ownership so policy cannot drift; explicit-root mode stays ownership-blind
and never emits directory or ancestor `UNSAFE_OWNER`. Exact deliverables:
`tests/test_pathaudit.py`, `src/pathaudit.c`, `README.md`, `SECURITY.md`.
Exact step-2 verification: `make clean && make` exited 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/ -q`
→ 280 passed, 18 skipped in 26.84s. User smoke
(`artifacts/user-smoke/result.json`) passed with start/check exit 0 and empty
blocking errors; check.log pytest reported `280 passed, 18 skipped in
20.40s`. The pinned sysdiff smoke oracle does not directly exercise
directory-ownership `--path` / `--command` detection; pathaudit coverage is
`tests/test_pathaudit.py`. Independent review
`code-reviews/review-path-directory-ownership.verdict.json` is `pass`
(0 Critical/High/Medium, 1 Low path-dir-ownership-1: O(N²) linear dedup of
`UNSAFE_OWNER` findings under a hostile all-foreign-owned PATH; bounded by
input limits; non-blocking). Allowlisted review check
`python3 -m pytest -p no:cacheprovider tests/test_pathaudit.py -q` →
143 passed, 15 skipped in ~1.8s. The 15 skips are host-capability
self-skips (no distinct foreign UID / unprivileged `chown`, oversized-PATH
env rejection), not failures. This cycle does not claim that `pathaudit` is
released, installable via `make install`, or that a product release was
published.

## 2026-07-25 — Detect non-directory PATH entries

Governed run `35116f657f35` (`detect_non_directory_path_entries`) delivered
Detect non-directory PATH entries for `pathaudit --path` and explicit-root
modes. The slice authored regression coverage in `tests/test_pathaudit.py`,
clarified the existing `classify_root` non-directory branch with a
comment-only change in `src/pathaudit.c`, and documented
`NON_DIRECTORY_ROOT` in `README.md` and `man/pathaudit.1`. Runtime
`NON_DIRECTORY_ROOT` / `ENOTDIR` / `!S_ISDIR` logic already existed;
this cycle documents and pins it rather than changing output contracts.
Pinned behavior: regular-file, symlink-to-file, and ENOTDIR components
report `NON_DIRECTORY_ROOT` with exit status 1 and empty stderr;
`MISSING_ROOT` remains mutually exclusive; permission findings never
attach to non-directory roots; relative non-directory files keep
`RELATIVE_ROOT` and add `NON_DIRECTORY_ROOT`. Exact step-3 verification
(non-writing): `clang -std=c17 -Wall -Wextra -Wpedantic -Werror
-fsyntax-only src/pathaudit.c` exited 0; `cppcheck --quiet --enable=all
--suppress=missingIncludeSystem src/pathaudit.c` exited 0;
`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider
tests/ -q` → 234 passed, 1 skipped. User smoke
(`artifacts/user-smoke/result.json`) passed with start/check exit 0 and
empty blocking errors; check.log pytest reported
`234 passed, 1 skipped in 19.50s`. The pinned sysdiff smoke oracle does
not directly exercise non-directory `--path` detection; pathaudit
coverage is `tests/test_pathaudit.py`. Independent review
`code-reviews/review-detect-non-directory-path-entries.verdict.json` is
`pass` (0 Critical/High/Medium, 2 Low nondir-1/nondir-2). Allowlisted
review check `python3 -m pytest -p no:cacheprovider
tests/test_pathaudit.py -q` → 94 passed, 1 skipped in ~1.9s. This cycle
does not claim that `pathaudit` is released, installable via
`make install`, or that a product release was published.
