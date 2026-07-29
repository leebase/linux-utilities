# sysdiff

`sysdiff` compares two explicit plain-text system snapshots and prints a
deterministic, key-sorted difference. It does not capture live system state:
you choose what to record and provide both files.

This is useful for comparing configuration inventories, package lists, kernel
settings, service states, or any other data you can express as stable
`key=value` records.

## Compile

From the repository root:

```sh
mkdir -p build
cc -std=c17 -Wall -Wextra -Wpedantic -Werror -O2 \
  -o build/sysdiff src/sysdiff.c
```

The supported Make build is:

```sh
make sysdiff
```

Source: [`src/sysdiff.c`](../src/sysdiff.c)  
Manual: [`man/sysdiff.1`](../man/sysdiff.1)  
Tests: [`tests/test_sysdiff.py`](../tests/test_sysdiff.py)

## Snapshot format

Snapshots contain one `key=value` record per line. Blank lines and comments
whose first non-space character is `#` are ignored.

```text
# before.snapshot
kernel.release=6.8.0
service.ssh=enabled
package.openssl=3.0.13
```

Keys are compared byte-for-byte. Duplicate or malformed keys are rejected
before any diff is printed.

## Use

```sh
./build/sysdiff compare before.snapshot after.snapshot
```

Example output:

```text
- service.old=enabled
+ service.new=enabled
~ package.openssl: 3.0.13 -> 3.0.14
```

Identical snapshots print:

```text
no changes
```

Exit statuses:

- `0`: comparison succeeded and the snapshots are identical.
- `1`: comparison succeeded and differences were found.
- `2`: usage, input, parsing, resource, or output error.

Diagnostics go to stderr. Input validation errors leave stdout empty.

## Install

`sysdiff` is the released utility in this repository:

```sh
make
sudo make install
```

The default prefix is `/usr/local`. A staged installation is supported:

```sh
make install DESTDIR=/tmp/sysdiff-stage prefix=/usr/local
```

## Boundaries

`sysdiff` is not a replacement for general-purpose `diff(1)`. It does not
scan directories, collect system state, persist snapshots, or run in the
background. Snapshot values are treated as opaque bytes after their line
ending is removed.
