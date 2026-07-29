# pathaudit

`pathaudit` is a read-only scanner for command-search-path hazards. It can
inspect paths supplied directly, audit the current `PATH`, or explain the
risk around one command name.

The utility reports findings; it never edits `PATH`, permissions, ownership,
or files.

## Compile

From the repository root:

```sh
mkdir -p build
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/pathaudit src/pathaudit.c
```

Source: [`src/pathaudit.c`](../src/pathaudit.c)  
Manual: [`man/pathaudit.1`](../man/pathaudit.1)  
Tests: [`tests/test_pathaudit.py`](../tests/test_pathaudit.py)

## Audit explicit paths

```sh
./build/pathaudit /usr/local/bin /usr/bin
```

Explicit-root mode checks only the named roots. It does not read `PATH` or
search for executables.

## Audit the current PATH

```sh
./build/pathaudit --path
```

This checks every PATH component and its ownership chain. It also reports
executable shadowing when the same command name resolves to different files
at different positions in the search order.

Typical findings include:

- `EMPTY_ROOT` — an empty PATH component.
- `RELATIVE_ROOT` — a component depends on the working directory.
- `MISSING_ROOT` — the component does not exist.
- `NON_DIRECTORY_ROOT` — the component is not a directory.
- `GROUP_WRITABLE` / `WORLD_WRITABLE` — unsafe write permissions.
- `UNSAFE_OWNER` — an executable or directory is owned by neither root nor
  the invoking user.
- `SHADOWED` — a later executable has the same command name as an earlier one.

## Inspect one command

```sh
./build/pathaudit --command python3
```

This walks `PATH` in resolution order for that basename, reports each matching
regular executable, and applies the same writability and ownership checks.
The command is never executed.

## Exit statuses

- `0`: inspection completed with no findings.
- `1`: inspection completed and one or more findings were reported.
- `2`: usage, environment, resource, metadata, or output error.

Findings are a point-in-time metadata observation. Filesystem state can change
immediately afterward.

## Boundaries

`pathaudit` does not inspect packages, processes, services, ACLs,
capabilities, or mount policy. It does not recursively scan directory trees
and does not remediate findings. The source is currently published as a
preview and is not included in `make install`.
