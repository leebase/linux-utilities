# openunlink

`openunlink` is a small, read-only Linux utility that inspects one explicitly
supplied process ID and reports retained descriptors whose followed targets are
observed as stable regular files with a final `st_nlink` of zero. It reports
descriptor observations; it does not recover files, estimate reclaimable
storage, terminate processes, or open target contents.

## Compile

From the repository root:

```sh
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -D_POSIX_C_SOURCE=200809L -D_FILE_OFFSET_BITS=64 \
  -o /tmp/openunlink src/openunlink.c
```

The repository's `make openunlink` target performs the same strict compile in
a temporary directory. The focused contract suite is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_openunlink.py -q
```

## Use

Scan one process that is visible in the caller's current PID and mount
namespaces:

```sh
/tmp/openunlink PID
```

The only other accepted forms are sole-argument `--help` and `--version`.
`/proc` must be mounted at its conventional path, and normal credential or
`hidepid` policy applies. The utility does not accept an alternate procfs root,
environment configuration, stdin input, or multiple PIDs.

## Output and status

Each finding is one tab-separated stdout line:

```text
OPEN_UNLINKED<TAB>pid=PID<TAB>fd=FD<TAB>size=BYTES<TAB>target="ESCAPED_TARGET"
```

`BYTES` is the lossless final `st_size` observation, not the link-text length,
physical allocation, or reclaim estimate. Procfs link bytes are escaped for
display; the cosmetic ` (deleted)` suffix is not used as the deletion test.

- `0`: no retained descriptor produced a finding, or a successful informational
  command was used.
- `1`: at least one `OPEN_UNLINKED` finding was emitted, possibly with
  per-descriptor advisories.
- `2`: usage, process, scan, memory, size, or checked output failure.

The scanner retains the first `65536` valid descriptor names in observed
enumeration order and sorts those names numerically before inspection. The
`65537`th valid name stops enumeration and emits one `FD_COUNT_LIMIT` advisory;
findings already retained are not discarded.

## Link-count boundary

The predicate is the final followed metadata observation `st_nlink == 0`, after
the target identity and regular-file type remain stable around link-text
inspection. A status-0 result therefore means only that no retained,
successfully inspected descriptor met that narrow observation. NFS silly-rename
and other filesystem or stacking behavior can leave a nonzero link count after
an unlink-like operation, so those cases are intentionally silent. A literal
` (deleted)` suffix in procfs text is also only display context.

## Scope and non-goals

`openunlink` reads only `/proc/PID/fd` through directory-relative metadata and
link inspection. It never follows a caller-provided path, opens a target,
changes the process or filesystem, groups descriptors by inode, uses a daemon,
stores state, contacts a network, or claims physical storage recovery. The
utility is a reviewed source preview and is not included in `make install`.

Authority: [`sixth-utility-capability-contract.md`](sixth-utility-capability-contract.md).
Manual: [`../man/openunlink.1`](../man/openunlink.1).
Tests: [`../tests/test_openunlink.py`](../tests/test_openunlink.py).
