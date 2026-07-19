# Reproducible Source Archive — Isolated Build Verification

Isolated verification of the repository `make dist` reproducible-source-archive
recipe and the full transitive `make quality` gate surface, executed entirely
outside the governed workspace except for this report file.

## Artifact Identity

Tracked git revision used for archive generation (working-tree bytes of tracked
`DIST_PATHSPECS` members as selected by `git ls-files`, per Makefile `dist`):

- Revision (full): `a69423e2a1cfa4b30c199797aaa10cead4879370`
- Revision (short): `a69423e`
- Archive recipe: GNU Make target `dist` (not a second packaging format)
- Command form: `make dist SOURCE_DATE_EPOCH=946684800 DIST_DIR=<external>`
- Controlled epoch: `SOURCE_DATE_EPOCH=946684800` (same integer for both builds)
- Archive basename: `sysdiff-source.tar.gz`
- Companion checksum basename: `sysdiff-source.tar.gz.sha256` (basename-only digest)
- Prefix inside archive: `sysdiff/`
- First archive path: `/tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/sysdiff-source.first.tar.gz`
- Second archive path: `/tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/sysdiff-source.second.tar.gz`
- First staging dir: `/tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/first/`
- Second staging dir: `/tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/second/`
- Archive size: 89851 bytes (both copies)
- SHA-256 (first): `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`
- SHA-256 (second): `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`
- Checksum file contents: `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544  sysdiff-source.tar.gz`
- Checksum verification: `(cd .../archives/first && sha256sum -c sysdiff-source.tar.gz.sha256)` → OK, exit 0
- Member count (`tar -tvzf`): 44 lines (directories and files under `sysdiff/`)
- Required members present include `sysdiff/Makefile`, `sysdiff/LICENSE`,
  `sysdiff/README.md`, `sysdiff/CHANGELOG.md`, `sysdiff/src/sysdiff.c`,
  `sysdiff/man/sysdiff.1`, `sysdiff/tests/test_sysdiff.sh`,
  `sysdiff/tests/test_sysdiff.py`, plus scripts, docs, and remaining tests

Tool versions recorded under controlled PATH:

- gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
- Ubuntu clang version 18.1.3 (1ubuntu1)
- Ubuntu clang-format version 18.1.3 (1ubuntu1)
- Ubuntu LLVM version 18.1.3 (`clang-tidy`)
- Cppcheck 2.13.0
- GNU groff version 1.23.0
- valgrind-3.22.0
- Python 3.12.3 / pytest 8.4.2 (isolated venv under verify root)
- GNU Make 4.3, tar (GNU tar) 1.35, gzip 1.12, sha256sum (GNU coreutils) 9.4

## Isolation Procedure

Verification root (external): `/tmp/sysdiff-isolated-verify.29IMEZSdXh`.
Scratch notes only: `/home/lee/projects/linux-utilities/.agent-orch-scratch/939ee21b0d76/step_01_execute_isolated_archive_verification/attempt-1`.
Governed workspace builds were not used; `DIST_DIR` pointed at the external
tree so `make dist` did not write the verification archives into workspace
`dist/`. Extract and all compile/test/install activity used fresh directories under
the verify root.

Controlled environment applied identically for both archive generations and for
extracted-tree gates:

```sh
export SOURCE_DATE_EPOCH=946684800
export LC_ALL=C LANG=C TZ=UTC
export HOME=/tmp/sysdiff-controlled-home.9UBumK3gou
umask 0022
# Final controlled PATH (system tools + isolated pytest venv):
export PATH=/tmp/sysdiff-isolated-verify.29IMEZSdXh/venv/bin:/usr/bin:/bin
```

Archive generation (exit 0 both times), from workspace git tree with external
`DIST_DIR` only:

```sh
make dist SOURCE_DATE_EPOCH=946684800 \
  DIST_DIR=/tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/first
# exit 0 → wrote .../first/sysdiff-source.tar.gz{,.sha256}

make dist SOURCE_DATE_EPOCH=946684800 \
  DIST_DIR=/tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/second
# exit 0 → wrote .../second/sysdiff-source.tar.gz{,.sha256}
```

Extraction into a second fresh directory outside the workspace:

```sh
tar -xzf .../sysdiff-source.first.tar.gz \
  -C /tmp/sysdiff-isolated-verify.29IMEZSdXh/extract/tree
# sourcedir=/tmp/sysdiff-isolated-verify.29IMEZSdXh/extract/tree/sysdiff
```

Pytest prerequisite: system `/usr/bin/python3` has no pytest module. An isolated
venv was created at `/tmp/sysdiff-isolated-verify.29IMEZSdXh/venv` and
`pytest==8.4.2` was installed there so required gates were not skipped. Initial
`make test-suite` / malformed-fuzz attempts under `PATH=/usr/bin:/bin` alone
failed with `No module named pytest` (exit 2 / 1); after venv provisioning the
same commands exited 0. That is tool provisioning in the external tree, not a
skipped gate.

Workspace mutation check: `find` inventory of the governed tree (excluding
`.git` and `.agent-orch-scratch`) before gates versus after all builds/tests
produced an empty diff (`diff -u` → 0 lines). Sole intentional workspace write
is this report file. Benchmark JSON was redirected to
`/tmp/sysdiff-isolated-verify.29IMEZSdXh/benchmark-out/sysdiff-benchmark.json`.

Cleanup evidence (external trees removed after report authoring):

```sh
rm -rf /tmp/sysdiff-isolated-verify.29IMEZSdXh \
       /tmp/sysdiff-controlled-home.9UBumK3gou
# verify: test ! -d /tmp/sysdiff-isolated-verify.29IMEZSdXh → true after cleanup
```

## Quality Gate Results

All gates below ran from the extracted source tree
`/tmp/sysdiff-isolated-verify.29IMEZSdXh/extract/tree/sysdiff` using the Makefile
targets exposed by `quality` (plus explicit shell/fixture/fuzz invocations).
No required gate was skipped; no sanitizer or Valgrind findings were reported.

| Gate | Command | Exit |
|------|---------|------|
| gcc-strict | `make gcc-strict` | 0 |
| clang-strict | `make clang-strict` | 0 |
| format-check | `make format-check` | 0 |
| clang-tidy-check | `make clang-tidy-check` | 0 |
| cppcheck-check | `make cppcheck-check` | 0 |
| clang-analyzer-check | `make clang-analyzer-check` | 0 |
| man-check | `make man-check` | 0 |
| build | `make` / `make clean all` | 0 |
| test-suite | `make test-suite` | 0 |
| test_sysdiff.sh | `./tests/test_sysdiff.sh` | 0 |
| test_sysdiff_fixture.sh | `bash tests/test_sysdiff_fixture.sh` | 0 |
| malformed-fuzz | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_sysdiff_malformed_fuzz.py -q` | 0 |
| benchmark-check | `python3 scripts/benchmark_sysdiff.py --output <external>/sysdiff-benchmark.json` | 0 |
| test-asan | `make test-asan` | 0 |
| test-ubsan | `make test-ubsan` | 0 |
| test-valgrind | `make test-valgrind` | 0 |

Test counts and notes:

- `make test-suite` pytest: **118 passed, 6 skipped** (shell suite included;
  packaging install/uninstall round-trip inside extract `build/` temp DESTDIR;
  fixture acceptance: `ok: sysdiff fixture acceptance tests passed`)
- Malformed-input fuzz: **41 passed** in 0.18s
- Standalone `./tests/test_sysdiff.sh`: exit 0 (help/version/packaging/fixtures)
- Standalone `bash tests/test_sysdiff_fixture.sh`: exit 0
- ASan (`make test-asan`): shell + pytest **118 passed, 6 skipped** in ~13.10s, exit 0
- UBSan (`make test-ubsan`): shell + pytest **118 passed, 6 skipped** in ~3.96s, exit 0
- Valgrind (`make test-valgrind`): shell + pytest **118 passed, 6 skipped** in ~72.36s, exit 0
- Benchmark JSON `passed: true` with medians under thresholds
  (`startup_ms_median` ≈ 1.24 ms, `fixture_ms_median` ≈ 7.40 ms,
  `peak_rss_kib` = 2540; limits 200 / 100 / 32768)

Static-analysis and warning-as-error surfaces exercised exactly as Makefile
defines them: GCC/Clang `-std=c17 -Wall -Wextra -Wpedantic -Werror` link builds
in mktemp bins; `clang-format --dry-run --Werror`; `clang-tidy` with
warnings-as-errors; `cppcheck --error-exitcode=1`; `clang --analyze` with
`-analyzer-werror`; `groff -man -Tutf8 -ww -z` man lint.

## Reproducibility Evidence

Byte-for-byte identity across two `make dist` invocations at the same controlled
epoch, locale, timezone, umask, HOME, and PATH:

```sh
cmp -s \
  /tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/sysdiff-source.first.tar.gz \
  /tmp/sysdiff-isolated-verify.29IMEZSdXh/archives/sysdiff-source.second.tar.gz
# cmp_exit=0
```

SHA-256 digests (identical):

- first:  `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`
- second: `5de5b3d720f3871861593d270ad93966475b6c5e1ee00bf8c7d06560e9251544`

Archive-member metadata comparison:

```sh
tar -tvzf .../sysdiff-source.first.tar.gz  > members-first.txt
tar -tvzf .../sysdiff-source.second.tar.gz > members-second.txt
diff -u members-first.txt members-second.txt
# members_diff_exit=0 (empty diff)
```

Representative member metadata (owner/group 0/0, mtime `2000-01-01 00:00`
corresponding to epoch 946684800, normalized modes): directories `drwxr-xr-x`,
regular files `-rw-r--r--`, shell scripts `-rwxr-xr-x` (for example
`sysdiff/scripts/smoke.sh`, `sysdiff/tests/test_sysdiff.sh`,
`sysdiff/tests/test_sysdiff_fixture.sh`). Full 44-line listings matched exactly
between archives. Recipe details confirmed in use: `tar --format=ustar
--sort=name --mtime=@$epoch --owner=0 --group=0 --numeric-owner
--mode='u=rwX,go=rX'` piped to `gzip -n -9`. No inventing of a second archive
format; only Makefile `dist` was used.

## Install and Uninstall Evidence

Staged install from the extracted tree with DESTDIR rooted only under the
external verify root:

```sh
make install DESTDIR=/tmp/sysdiff-isolated-verify.29IMEZSdXh/install-stage-final \
  prefix=/usr/local
# install_exit=0
```

Installed paths and modes:

- `/tmp/sysdiff-isolated-verify.29IMEZSdXh/install-stage-final/usr/local/bin/sysdiff` mode `755`, size 21384
- `/tmp/sysdiff-isolated-verify.29IMEZSdXh/install-stage-final/usr/local/share/man/man1/sysdiff.1` mode `644`, size 7191
- SHA-256 bin: `b7940db0a7af05bdb9423340669a5f63f033629be4d67bb76a40ffe5b303e3ac`
- SHA-256 man: `2504d8ca4356efc30bb397a9b600508bda8434f4b25d597f1540c14826b56db1`

Installed executable checks (dotted keys required by snapshot syntax):

- `"$BIN" --version` → exit 0, stdout `sysdiff 0.1.0`
- `"$BIN" --help` → exit 0, usage text present
- compare differing snapshots → exit 1, stdout `+ extra.flag=1` and
  `~ host.name: old -> new`
- compare identical snapshots → exit 0, stdout `no changes`
- man page header present: `.TH SYSDIFF 1 "2026-07-17" "sysdiff 0.1.0"`

Uninstall:

```sh
make uninstall DESTDIR=/tmp/sysdiff-isolated-verify.29IMEZSdXh/install-stage-final \
  prefix=/usr/local
# uninstall_exit=0
```

Residue check: `find "$DESTDIR" -type f` counted **2** staged files before
uninstall and **0** after. Both `bin/sysdiff` and `man1/sysdiff.1` were absent
after uninstall (`uninstall_targets_gone=yes`). Empty directory scaffolding from
`install -d` may remain (bin/man1 parents); uninstall removes only the two
installed files per Makefile, with no leftover staged file residue.

## Remaining Risks

This PASS covers isolated reproduction of `make dist` byte identity and a full
extracted-tree exercise of the Makefile quality surface. Residual risks that do
not fail this gate but remain relevant for release operators:

- `make dist` packages current working-tree bytes of tracked `DIST_PATHSPECS`
  paths (via `git ls-files` then `cp`), so a dirty tree can embed uncommitted
  content while still hashing stably across same-epoch rebuilds; commit
  provenance is not encoded in the tarball name or checksum filename.
- Root AgentFlow docs such as `STATUS.md` / `QUALITY.md` / `TESTING.md` /
  `HISTORY.md` / `DECISIONS.md` / `ROADMAP.md` / `architecture.md` are outside
  `DIST_PATHSPECS` and are not in the archive (known Medium packaging review
  theme).
- Pytest is not vendored; hosts without pytest must provision it (here: isolated
  venv under `/tmp/.../venv`) or gates fail rather than skip.
- Empty DESTDIR directories after uninstall are expected with the current
  `rm -f`-only uninstall rule; operators staging into shared prefixes should
  account for leftover empty dirs.
- Performance numbers are host-load sensitive; thresholds passed here but are
  not microbenchmark guarantees.
- Prior workspace `dist/` artifacts (mtime unrelated to this run) were not used
  as inputs; verification archives lived only under `/tmp/sysdiff-isolated-verify.29IMEZSdXh`.

Overall Result: PASS
