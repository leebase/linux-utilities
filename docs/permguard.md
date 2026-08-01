# permguard

`permguard` is a small, read-only permission-bit inspector. It checks only the
paths you name and reports four easily audited hazards against each
operand's own `lstat` mode bits:

- `GROUP_WRITABLE`
- `OTHER_WRITABLE`
- `SET_USER_ID`
- `SET_GROUP_ID`

It never changes permissions or ownership, never follows a final symbolic
link, and never invents sticky-bit, ownership, ACL, or file-type findings.

## Compile

From the repository root, pass the POSIX feature-test macro so
`<sys/stat.h>` owns the `lstat` prototype (the same flag Make and pytest use):

```sh
mkdir -p build
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -D_POSIX_C_SOURCE=200809L \
  -o build/permguard src/permguard.c
```

Source: [`src/permguard.c`](../src/permguard.c)  
Manual: [`man/permguard.1`](../man/permguard.1)  
Tests: [`tests/test_permguard.py`](../tests/test_permguard.py)  
Live product contract: [`permguard-bootstrap-contract.md`](permguard-bootstrap-contract.md)

## Use

Inspect one or more paths:

```sh
./build/permguard /etc/passwd /usr/local/bin/example
```

Use `--` when a path begins with a dash:

```sh
./build/permguard -- -unusual-name
```

Each finding is one tab-separated line:

```text
GROUP_WRITABLE	"/path/to/file"
OTHER_WRITABLE	"/path/to/file"
```

One path can produce multiple findings. Results remain in operand order and
then the fixed taxonomy rank shown above. Duplicate operands are inspected
and reported independently.

## Symlinks and errors

`permguard` uses `lstat(2)` exactly once per operand and does not follow the
final symbolic link. A final symlink is reported as `SYMBOLIC_LINK` on stderr
and makes the run exit with status `2`, even when its target exists.

After valid command-line parsing, inspection continues across missing,
inaccessible, or otherwise invalid operands so you receive diagnostics for
the complete list. Findings for successfully inspected hazardous operands
still stream; any operational error takes precedence in the final status.

Checked stdout write or flush failure reports `permguard: STDOUT_WRITE` on
stderr and exits `2`. The process ignores `SIGPIPE` so a closed stdout pipe
takes that same checked path instead of signal termination.

## Exit statuses

- `0`: all named paths were inspected and no hazards were found, or a
  successful sole-argument `--help` / `--version`.
- `1`: inspection completed and hazards were found; stderr is empty.
- `2`: usage, missing, inaccessible, symlink, other `lstat`, or checked
  stdout write/flush (`STDOUT_WRITE`) error.

Operational errors take precedence over hazard status in mixed runs. The
current no-heap implementation has no allocation or product-defined
input-limit failure class.

## Boundaries

`permguard` does not recurse, read `PATH`, inspect ACLs or capabilities,
evaluate ownership policy, or remediate anything. It is a point-in-time
mode-bit check, not a security lock or proof that a file is exploitable. The
source is currently published as a preview and is not included in
`make install`. This guide does not claim that `permguard` is released,
packaged, or that failed Medium-repair run `ba6dc2fdd199` passed.

## Hostile filesystem fixtures

Regression coverage in `tests/test_permguard.py` follows
`docs/permguard-hostile-filesystem-fixtures-contract.md`. It exercises
dangling and looping symbolic links, mode-000 metadata versus parent-search
`INACCESSIBLE`, sequential permission transitions, unusual escaped names,
deep existing paths, FIFOs (and optional AF_UNIX sockets) without opening
them, and deterministic replacement boundaries through a test-only `lstat`
seam. The public taxonomy, diagnostics, and exits `0`/`1`/`2` are unchanged.
Capability-gated cases may skip with an explicit reason. Concurrent
replacement stress is not a byte-stable oracle and is not a race-free
authorization claim. Character and block devices are out of fixture scope.
