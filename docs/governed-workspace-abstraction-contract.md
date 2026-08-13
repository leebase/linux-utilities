# Governed Workspace Abstraction Contract

## Overview

This contract defines the repository-owned user-journey manifest and the
bounded evaluator that judges a governed repair. The manifest is
`tests/user_journeys_manifest.json`; it is an immutable evaluator oracle, not a
replacement for deterministic tests or smoke. The evaluator resolves all
repository paths from one canonical governed-workspace root, preserves journey
authority and acceptance-check traceability, and independently re-verifies the
commands claimed by a user tester. A green result is meaningful only when the
manifest, contract, result schema, command claims, and write scopes all remain
the same governed boundary.

The manifest is a JSON object with the following canonical fields:

```json
{
  "journeys": [
    {
      "name": "A user confirms the governed check is usable",
      "authority": "author",
      "traces_to": ["AC-1"]
    }
  ],
  "command_allowlist": ["bash scripts/smoke.sh"]
}
```

Each manifest journey has a nonempty string `name`; optional `authority`
defaults to `author` and otherwise is one of `human`, `mission`, `author`, or
`exploratory`; and `traces_to` is a string array whose effective traceability
rules are stated below. `command_allowlist` is a nonempty array of nonempty
shell-word-parsable strings. Unknown fields are inert compatibility data: they
cannot grant authority, authorize a command, satisfy a trace, or alter path
resolution.

The canonical user-test result is a JSON object containing `journeys` and
`findings` arrays. Each result journey has exactly the required semantic fields
`name`, `status`, `steps_taken`, and `commands_run`: `name` is a nonempty
manifest name, `status` is `passed` or `failed`, `steps_taken` is a nonempty
array of concrete strings, and `commands_run` is a nonempty array of command
claims. Each command claim has a nonempty string `command` and integer
`exit_code`, with optional `stdout_contains` only when that substring was
actually observed. Each finding has the required nonempty fields `id`,
`severity`, `journey`, `problem`, `reproduction`, `expected`, `actual`, and
`proposed_fix`; optional `observations` is text and optional `artifacts` is a
nonempty array of workspace-relative paths when cited. A failed journey needs
an actionable finding. The findings log is append-only evidence, while the
result object is the structured validator input.

This is the bounded recovery contract for origin run `94407708c829`. That run
failed because AC-4 had no required manifest journey and a retry emitted a
finding object that did not satisfy the canonical result schema. The recovery
must make those two contracts explicit before implementation, repair, smoke,
user simulation, or independent review can be accepted.

## Problem

Governed repairs can accidentally change the thing being judged: a worker may
drop a required journey, demote an authoritative seed, resolve a relative path
against an incidental current directory, or turn a command claim into a shell
pipeline that cannot be safely reproduced. An evaluator can also report a
failure using a prose-only finding that omits the journey, expected behavior,
actual behavior, or proposed fix required for an actionable repair. Either
failure mode can produce a green-looking workflow while ordinary unit tests and
the existing sysdiff smoke route remain unchanged.

The abstraction therefore has one auditable division of responsibility. The
repository owns the manifest and contract; the implementation and repair
workers may not change that oracle; the evaluator reports every manifest
journey using the canonical result fields; and the governed validators check
both structure and execution evidence. A journey is natural-language intent,
not a second product CLI, but every claimed command must be reproducible from
the governed workspace as direct argv. Smoke remains deterministic aggregate
evidence and cannot be relabeled as personally performed user-journey proof.

Authority is ordered strictly as `human` > `mission` > `author` >
`exploratory`. Human- and mission-owned journeys come from a seed outside the
author's write scope. Authors may add author or exploratory journeys, but may
not remove a seeded journey, weaken its authority, narrow its traces, or alter
the command allowlist during implementation or repair. When a contract path is
configured, every AC-1 through AC-10 identifier must be covered by a required
non-exploratory journey; exploratory journeys supplement coverage and never
repair a missing required trace.

## Constraints

1. **Workspace-relative paths.** Manifest, seed, contract, result, finding
   artifact, and playbook paths are POSIX paths relative to the canonical
   governed workspace. Reject empty, absolute, root, `.`, parent-escaping, and
   symlink-escaping paths. Normalize separators, join only to the canonical
   root, resolve the candidate, and reject any resolved path outside that root.
   Never use the process's incidental current directory or accept an absolute
   caller substitute. Every re-executed command uses the governed workspace as
   its `cwd`.

2. **Direct command validation.** `command_allowlist` entries and
   `commands_run[].command` claims are parsed with shell-word parsing into argv
   tokens. A claim is eligible only when its complete argv tokens begin with a
   complete allowlisted argv prefix, matched token-by-token; substring matches
   are not sufficient. The matched argv is executed directly without a shell,
   with the governed workspace as `cwd`. Leading environment assignments may be
   represented only if the parser and allowlist explicitly support them; they
   never bypass the prefix. Shell operators (`;`, `|`, `&`, `&&`, `||`, pipes,
   redirections, command substitution, or equivalent control syntax), malformed
   shell words, empty executables, and unmatched claims are rejected and never
   executed. The allowlist authorizes verification only; it grants no general
   file mutation, network, or arbitrary-command permission.

3. **Canonical journey and finding fields.** The manifest journey contract is
   `name`, optional `authority`, and `traces_to`, with the authority default and
   trace rules above. The result journey contract is `name`, `status`,
   `steps_taken`, and `commands_run`; each command claim is `command` plus an
   integer `exit_code`, optionally `stdout_contains`. The result finding
   contract is `id`, `severity`, `journey`, `problem`, `reproduction`,
   `expected`, `actual`, and `proposed_fix`, optionally `observations` and
   `artifacts`. Required fields are nonempty and have their declared types;
   omitted required fields are schema failures, not implicit empty values.
   Every cited artifact is nonempty, workspace-relative, and present. A result
   may carry other metadata only as inert data; metadata cannot replace these
   fields or authorize execution.

4. **Authority and traceability.** Accept only `human`, `mission`, `author`,
   and `exploratory`; an omitted authority means `author`, while an unknown
   explicit value is malformed. Human, mission, and author journeys require a
   nonempty `traces_to` list naming real AC identifiers. With
   `contract_path` configured, no AC-1 through AC-10 check may remain uncovered.
   Exploratory journeys may omit traces and may fail the run, but they never
   satisfy missing required coverage. A seed journey must remain present at the
   same or stronger authority after repair.

5. **Immutable manifest rule.** Before implementation, repair, and
   user-simulation acceptance, hash the repository-owned
   `tests/user_journeys_manifest.json` and compare it with the pinned SHA-256
   `0d21f5624b734e7b4ff58e02a42190bde9818cc2ae02e272ae964a72564bfbcc`.
   Producers must omit the manifest from every repair write scope, and the
   evaluator may write only its result, findings log, and scratch evidence. A
   hash mismatch, removed or demoted seed, reduced trace set, narrowed
   allowlist, or changed journey is a halt/failure before user evidence can be
   accepted; it is never a reason to update the pin. A future manifest change
   requires a new contract-authorized workflow, not an in-run repair.

6. **Closed hazard taxonomy.** The abstraction recognizes exactly these five
   governance hazard classes: `PATH_ESCAPE` (lexical, cwd, or symlink escape),
   `COMMAND_INJECTION` (shell control syntax, malformed parsing, or an
   allowlist mismatch), `ORACLE_TAMPERING` (manifest, seed, authority, trace,
   or allowlist mutation), `RESULT_FABRICATION` (missing journeys, invented
   outputs/statuses, malformed findings, or non-reproducible evidence), and
   `BLAST_RADIUS` (smoke substitution, product-scope drift, or unauthorized
   network/install/package/release behavior). These classes are closed: a
   diagnostic or finding must use one of them, and no sixth class may be
   introduced without revising this contract and its AC mapping.

7. **Exit and failure behavior.** Structural validation failure is a non-pass
   `user_journeys_all_passed` result; command claims are not executed when the
   manifest or result schema is invalid. Execution validation failure is a
   non-pass `user_journeys_execution_verified` result when a claim is malformed,
   contains an operator, misses the argv prefix, runs with the wrong `cwd`,
   reports a mismatched integer exit code or observed stdout substring, or when
   zero claims are verifiable. A failed journey must be marked `failed` and
   carry a complete actionable finding; omitted journeys, empty steps, empty
   command claims, and missing evidence fail the result. The governed playbook
   halts or routes the failure to its declared repair edge. No validator failure
   changes a utility's CLI exit statuses because this is workflow evidence, not
   application behavior.

8. **Blast radius and non-goals.** This is an internal governed-workflow
   repair. It may change only the abstraction playbook, its focused and named
   compatibility tests, explanatory documentation, and governed evidence paths
   explicitly allowlisted by the playbook. It preserves the existing
   `tests/smoke_manifest.json` -> smoke helpers -> `scripts/smoke.sh` ->
   `make test` chain and the three governed-run/commissioning compatibility
   modules. It does not change `src/sysdiff.c`, the sysdiff CLI or output,
   Makefile product behavior, runtime dependencies, networking, installation,
   packaging, tagging, publication, deployment, or release decisions. A new
   man page is explicitly out of scope because this repair does not change a
   utility CLI. User simulation cannot repair code, tests, the playbook, smoke
   inputs, or the manifest, and a passing journey result does not prove who ran
   a command or authorize product release.

## Acceptance Checks

- **AC-1 — Schema acceptance:** A valid repository-owned manifest is accepted
  only as a JSON object with a nonempty `journeys` array of named journey
  objects and a nonempty string-array `command_allowlist`; omitted authority
  defaults to `author`, and `traces_to` has the declared array shape.

- **AC-2 — Malformed-manifest rejection:** Invalid JSON, duplicate keys,
  missing required fields, empty arrays or strings, wrong types, malformed
  traces, and invalid explicit authority values fail closed with a path-specific
  validation error and never reach command execution.

- **AC-3 — Workspace-relative resolution:** Manifest, seed, contract, result,
  finding-artifact, and playbook paths resolve from the canonical workspace
  root after POSIX normalization; absolute, root, `.`, parent-escaping,
  symlink-escaping, and incidental-current-directory paths are rejected.

- **AC-4 — Direct allowlisted execution:** AC-4 requires shell-word parsing,
  token-by-token argv-prefix matching, direct execution without a shell,
  governed-workspace `cwd`, rejection of shell operators and malformed or
  unmatched claims, and failure when zero claims are verifiable. Only a claim
  matching an allowlisted argv prefix may be re-executed, and its actual integer
  exit code and any claimed stdout substring must reproduce.

- **AC-5 — Journey authority:** The validator accepts only the ordered
  authorities `human`, `mission`, `author`, and `exploratory`, applies the
  author default, and preserves every human- or mission-seeded journey at no
  weaker authority after authoring and repair.

- **AC-6 — Contract traces:** Every human, mission, or author journey has a
  nonempty `traces_to` list naming real AC-1 through AC-10 identifiers, every
  contract ID is covered when `contract_path` is configured, and exploratory
  journeys remain supplemental.

- **AC-7 — Immutable journey authority during repair:** A changed manifest
  hash, removed or demoted seeded journey, reduced trace set, or narrowed
  command allowlist causes the repair/user-simulation flow to fail before the
  altered journey set can become acceptance evidence.

- **AC-8 — Result and failure discipline:** The result contains every manifest
  journey with nonempty concrete `steps_taken` and `commands_run`; every claim
  has `command` and integer `exit_code`; every failed journey has an actionable
  finding with all canonical required fields, and cited artifacts are present
  workspace-relative evidence. Exit or stdout mismatches, malformed findings,
  and zero verifiable claims fail even when another journey passes.

- **AC-9 — Existing smoke compatibility:** The abstraction remains additive to
  the governed-run tests and leaves the existing smoke manifest and helper
  chain intact; deterministic smoke still reaches `make test`, and its
  sysdiff-centered result is not relabeled as direct user-journey evidence.

- **AC-10 — Bounded blast radius:** Focused tests cover schema, malformed
  input, path containment, command safety, authority repair protection,
  canonical result findings, and smoke compatibility without changing sysdiff
  product behavior, adding runtime dependencies, enabling networking, or
  creating install, package, release, or man-page obligations.
