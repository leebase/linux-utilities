# Commissioning validator ownership and provenance

Every validator the final supervised commissioning playbook invokes must
resolve from a committed baseline: the governed Linux Utilities worktree
(`/home/lee/projects/linux-utilities-autonomous`, branch `main`), the Agent-Orch
baseline, or the Auto-Orch baseline. Nothing may be read from the separate
interactive checkout at `/home/lee/projects/linux-utilities`.

## The defect this replaces

`playbooks/final_supervised_commissioning_20260802.yaml` previously declared and
executed two validators through the interactive checkout:

- `/home/lee/projects/linux-utilities/scripts/check_repository_identity.py`
- `/home/lee/projects/linux-utilities/scripts/prune-agent-orch-scratch.sh`

Both scripts were added by commit `34e4a4a` on the branch
`agent/public-utility-guides` and are **absent from that checkout's `main`**.
The commissioning run therefore only reproduced while a mutable external
checkout happened to sit on one branch. `commissioning/check_packet.py`
resolves absolute declared inputs directly, so packet completeness passed for
the same accidental reason. Checking that sibling out to `main` — an ordinary
action — would have failed packet completeness and both system validators.

This is the same class of failure previously found with missing launch inputs
and commissioning packets: a governed run depending on ungoverned state.

## Ownership decisions

### Scratch retention — platform-owned (Agent-Orch)

`prune-agent-orch-scratch.sh` was a mission-local reimplementation of a
capability Agent-Orch already owns. The platform exposes `scratch-report` and
`scratch-clean`, documented in `docs/platform-commissioning-contract.md`, with
the same semantics the script hand-rolled:

| Script behaviour | Platform equivalent |
| --- | --- |
| discover `.agent-orch-scratch` under the workspace | conventional scratch-root discovery |
| protect `RUNNING` / `WAITING_APPROVAL` runs | `--runs-dir` protected-run set |
| protect runs with missing/unreadable metadata | protected, fail-closed, plus `*` when the runs root is unreadable |
| `--dry-run` default, delete only when asked | dry run unless `--apply` |
| `RETENTION_DAYS=2` | `--retention-days 2` |

The platform set is equal or stronger: it also protects every candidate when the
runs root cannot be read. The script is **not** carried onto governed `main`;
copying it would duplicate platform authority. The playbook now runs:

```text
agent-orch scratch-clean --workspace <workspace> --runs-dir <runs> --retention-days 2 --json
```

`--retention-days 2` preserves the mission's tighter window instead of the
30-day platform default, and the absence of `--apply` keeps it a planning-only
check that never deletes evidence during commissioning.

The former `bash -n` syntax check disappears with the script it checked.

### Repository identity — platform-owned, with a narrow mission policy

`check_repository_identity.py` mixed two concerns.

**Platform-owned (the bulk, ~90% of its 426 lines).** Git metadata resolution,
worktree-admin layout, nested-repository scanning, and `GIT_*` redirect
sanitising all duplicate `agent_orch.repository_identity`. The platform captures
identity before the worker, after worker execution, and after validation, and
any drift fails the `repository_identity_unchanged` rule. `agent-orch commission`
reports the same facts as its `repository readiness` domain. `auto-orch
check-commissioning` additionally names `repository_identity` a
platform-supplied evidence class that **must not** be declared as a workspace
input. None of this is reimplemented in the mission, and the script is not
carried onto `main`.

**Mission-owned (small).** The platform deliberately asserts only that the
workspace is a structurally valid and *stable* repository. It records the origin
remote and checked-out branch as evidence but does not assert what they ought to
be, and Auto-Orch's mission config pins neither. Drift detection alone cannot
catch a run that *started* on the wrong branch or against the wrong remote.

That expectation is Linux Utilities policy, so it lives in the governed
worktree as `commissioning/check_repository_expectations.py`. It obtains its
facts from the documented `agent-orch commission --json` contract rather than
re-deriving them, keeping Agent-Orch the single authority on identity facts, and
asserts only:

- classification is `valid_root_linked_worktree_git_file`;
- the platform inspected the expected governed workspace;
- no nested Git metadata;
- exactly one remote, `origin`, at `git@github.com:leebase/linux-utilities.git`;
- the governed worktree is on `refs/heads/main`, not detached, not prunable.

It fails closed on every one of those, and when the platform reports
`repository readiness` as anything but `ready`, or when the Agent-Orch CLI
cannot be located.

### Deliberately dropped: `--protect --dry-run`

The old playbook also ran `check_repository_identity.py --protect --dry-run`.
With `--dry-run` that applies no `chattr +i`; it only listed the identity paths
and asserted they were regular files — which the platform's `git_entry` and
metadata-stat evidence already establishes. Nothing verified is lost. Applying
immutability remains a deliberate operator action and is not a commissioning
step.

## Resulting validator set

| Concern | Owner | Invocation |
| --- | --- | --- |
| packet completeness | mission | `commissioning/check_packet.py` |
| repository expectations | mission policy over platform facts | `commissioning/check_repository_expectations.py` |
| repository identity + drift | Agent-Orch | `commission`, runtime `repository_identity_unchanged` |
| scratch retention | Agent-Orch | `agent-orch scratch-clean` |
| product suites | mission | `pytest` |

Absolute paths into the Agent-Orch and Auto-Orch baselines remain, which is
intended: those are authoritative committed baselines. Absolute paths into
`/home/lee/projects/linux-utilities` are prohibited and are pinned by
`tests/test_commissioning_dependencies.py`.

## Not modified

`commissioning/post-hardening-commissioning-packet.{json,md}` still names the
old script paths. That packet is the historical record of an earlier, superseded
commissioning attempt; superseded evidence is preserved rather than rewritten.
It is not referenced by the final playbook and cannot affect a future run.

## Packaging

Moving the validators into the governed worktree removed the external-checkout
dependency but created a second one: `tests/test_commissioning_dependencies.py`
ships in the source distribution while the files it loads did not. The extract
then failed collection with `FileNotFoundError` on
`commissioning/check_repository_expectations.py` even though the source tree
passed, because `DIST_PATHSPECS` in the `Makefile` listed neither
`commissioning/` nor the playbook.

The distribution now carries the whole dependency closure of that test:

| Shipped path | Why |
| --- | --- |
| `commissioning/` | validator modules plus the packets the test reads |
| `playbooks/final_supervised_commissioning_20260802.yaml` | the playbook whose validators the test resolves |
| `AGENTS.md` | declared packet input the test asserts resolves |

Two scoping rules apply. `commissioning/` ships as a directory because every
tracked file in it is mission-contract material, and because `make dist`
selects members through `git ls-files` — run output, evidence, caches, and
credentials cannot enter the archive even while they sit in a packaged
directory. `playbooks/` ships as one exact file rather than the directory,
because only the final supervised commissioning playbook is part of the shipped
contract; `playbooks/templates/` and `playbooks/starter_proof.yaml` are
orchestration authoring surfaces and stay development-tree-only under the same
rule as `plans/`.

`tests/test_sysdiff.py` previously banned the `playbooks/` prefix from the
archive outright. That ban was widened rather than dropped: the fragment list
now names `playbooks/templates/` and `playbooks/starter_proof.yaml`, and
`test_dist_archive_layout_and_normalized_metadata` asserts the exact membership
of both shipped directories — one playbook, six commissioning files — so
nothing else can leak in behind the directory pathspec.

The correct repair is inclusion, not exemption. Skipping the test when
`commissioning/` is absent, or special-casing extracted trees, would let the
distribution keep claiming a commissioning contract it cannot execute.
`tests/test_sysdiff.py::test_dist_extracts_builds_and_tests_outside_workspace`
runs `make test` inside the extract, so it is the standing regression guard for
this whole class of packaging omission.

The release archive is a separate surface. `RELEASE_PATHSPECS` is unchanged and
still excludes `playbooks/`, `plans/`, and `AGENTS.md`: it carries the product
only, and does not ship the commissioning test.
