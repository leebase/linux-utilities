# permguard

`permguard` is a small, read-only permission-bit inspector. It checks only the
paths you name and reports four easily audited hazards:

- `GROUP_WRITABLE`
- `OTHER_WRITABLE`
- `SET_USER_ID`
- `SET_GROUP_ID`

It never changes permissions or ownership.

## Compile

From the repository root:

```sh
mkdir -p build
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/permguard src/permguard.c
```

- Source: [`src/permguard.c`](../src/permguard.c)
- Manual: [`man/permguard.1`](../man/permguard.1)
- Tests: [`tests/test_permguard.py`](../tests/test_permguard.py)

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
then the fixed order shown above.

## Symlinks and errors

`permguard` uses `lstat(2)` exactly once per operand and does not follow the
final symbolic link. A final symlink is reported as `SYMBOLIC_LINK` on stderr
and makes the run exit with status `2`, even when its target exists.

After valid command-line parsing, inspection continues across missing,
inaccessible, or otherwise invalid operands so you receive diagnostics for
the complete list.

## Exit statuses

- `0`: all named paths were inspected and no hazards were found.
- `1`: inspection completed and hazards were found.
- `2`: usage, inspection, symlink, allocation, or output error.

Operational errors take precedence over hazard status in mixed runs.

## Boundaries

`permguard` does not recurse, read `PATH`, inspect ACLs or capabilities,
evaluate ownership policy, or remediate anything. It is a point-in-time
mode-bit check, not a security lock or proof that a file is exploitable. The
source is currently published as a preview and is not included in
`make install`.
