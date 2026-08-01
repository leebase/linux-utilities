"""Contract tests for the openunlink initial vertical slice.

Encodes docs/sixth-utility-capability-contract.md and
plans/openunlink-implementation-plan.md. Builds src/openunlink.c into a
pytest-owned directory under /tmp (never the workspace). Missing source
fails closed with pytest.fail, never skip. Real same-UID fixtures cover
linked, unlinked, duplicated, literal `` (deleted)`` suffix, and
non-regular descriptors without root. Synthetic cases use a deterministic
test-only seam with positive controls for every injector.

Coverage maps to OU-AC-01..OU-AC-17: exact CLI/stream bytes, canonical PID
parsing, fixture findings and silence, numeric ordering, escaping,
65,536/65,537 descriptor and target-length boundaries, closed errno
mappings, allocation/cleanup/stdio/syscall seams, SIGPIPE behavior,
no-content/no-control source audits, fixed procfs scope, and compiler
feature macros.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import stat as stat_mod
import struct
import subprocess
import sys
import tempfile
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "openunlink.c"
MAKEFILE = ROOT / "Makefile"
CONTRACT = ROOT / "docs" / "sixth-utility-capability-contract.md"
MANPAGE = ROOT / "man" / "openunlink.1"
DOCS_OPENUNLINK = ROOT / "docs" / "openunlink.md"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
QUALITY = ROOT / "QUALITY.md"
TESTING = ROOT / "TESTING.md"
ARCHITECTURE = ROOT / "architecture.md"

STRICT_WARNING_FLAGS = ("-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror")
PLATFORM_CFLAGS = ("-D_POSIX_C_SOURCE=200809L", "-D_FILE_OFFSET_BITS=64")
SEAM_MACRO = "-DOPENUNLINK_TEST_SEAM"

FD_RETAIN_CAP = 65536
FD_LIMIT_TRIGGER = 65537
TARGET_LEN_CAP = 65536
TARGET_LEN_LIMIT = 65537
INT_MAX = 2147483647

HELP_STDOUT = (
    b"Usage: openunlink PID\n"
    b"       openunlink --help\n"
    b"       openunlink --version\n"
    b"Report zero-link regular-file descriptors for one Linux process.\n"
)
VERSION_STDOUT = b"openunlink 0.1.0\n"

STATUS_OK = 0
STATUS_RESULT = 1
STATUS_ERROR = 2

FINDING_CODES = frozenset({"OPEN_UNLINKED"})
ADVISORY_CODES = frozenset(
    {
        "FD_COUNT_LIMIT",
        "FD_UNSTABLE",
        "FD_UNREADABLE",
        "FD_SIZE_RANGE",
        "TARGET_LENGTH_LIMIT",
    }
)
OPERATIONAL_CODES = frozenset(
    {
        "USAGE",
        "PROCESS_NOT_FOUND",
        "PROCESS_ACCESS",
        "PROCESS_SCAN",
        "MEMORY",
        "STDOUT_WRITE",
    }
)
PID_OWNED_OPERATIONAL = frozenset(
    {"PROCESS_NOT_FOUND", "PROCESS_ACCESS", "PROCESS_SCAN"}
)
GLOBAL_OPERATIONAL = frozenset({"USAGE", "MEMORY", "STDOUT_WRITE"})

SANITIZER_ENV_KEYS = (
    "ASAN_OPTIONS",
    "UBSAN_OPTIONS",
    "LSAN_OPTIONS",
    "ASAN_SYMBOLIZER_PATH",
)

S_IFREG = 0o100000
S_IFIFO = 0o010000
S_IFSOCK = 0o140000

_LAST_OPENUNLINK_COMPILE_ARGV: list[str] = []
_SESSION_BUILD_DIRS: list[Path] = []


def escape_target(data: bytes) -> bytes:
    out = bytearray()
    for byte in data:
        if byte == ord('"'):
            out.extend(b'\\"')
        elif byte == ord("\\"):
            out.extend(b"\\\\")
        elif 0x20 <= byte <= 0x7E:
            out.append(byte)
        else:
            out.extend(f"\\x{byte:02X}".encode("ascii"))
    return bytes(out)


def finding_line(pid: int, fd: int, size: int, target_bytes: bytes) -> bytes:
    return (
        f"OPEN_UNLINKED\tpid={pid}\tfd={fd}\tsize={size}\ttarget=\"".encode("ascii")
        + escape_target(target_bytes)
        + b'"\n'
    )


def advisory_fd(code: str, pid: int, fd: int) -> bytes:
    if code not in ADVISORY_CODES - {"FD_COUNT_LIMIT"}:
        raise ValueError(code)
    return f"openunlink: {code}: pid={pid} fd={fd}\n".encode("ascii")


def advisory_count(pid: int) -> bytes:
    return f"openunlink: FD_COUNT_LIMIT: pid={pid}\n".encode("ascii")


def diagnostic_pid(code: str, pid: int) -> bytes:
    if code not in PID_OWNED_OPERATIONAL:
        raise ValueError(code)
    return f"openunlink: {code}: pid={pid}\n".encode("ascii")


def diagnostic_global(code: str) -> bytes:
    if code not in GLOBAL_OPERATIONAL:
        raise ValueError(code)
    return f"openunlink: {code}\n".encode("ascii")


def assert_no_raw_unsafe_bytes(data: bytes) -> None:
    for index, byte in enumerate(data):
        if byte in (0x09, 0x0A) or 0x20 <= byte <= 0x7E:
            continue
        raise AssertionError(f"unsafe raw byte 0x{byte:02X} at offset {index}")


def mk_outside_build_dir(prefix: str = "openunlink-build.") -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp"))
    resolved = path.resolve()
    if resolved == ROOT.resolve() or ROOT.resolve() in resolved.parents:
        shutil.rmtree(path, ignore_errors=True)
        raise AssertionError(f"build dir resolved inside workspace: {resolved}")
    _SESSION_BUILD_DIRS.append(path)
    return path


def _u16(value: int) -> bytes:
    return struct.pack("<H", value)


def _u32(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)


def _i32(value: int) -> bytes:
    return struct.pack("<i", value)


def _u64(value: int) -> bytes:
    return struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)


def _i64(value: int) -> bytes:
    return struct.pack("<q", value)


def make_stat(
    *,
    dev: int = 1,
    ino: int = 1,
    mode: int = S_IFREG | 0o600,
    nlink: int = 1,
    size: int = 0,
) -> dict[str, int]:
    return {
        "dev": int(dev),
        "ino": int(ino),
        "mode": int(mode),
        "nlink": int(nlink),
        "size": int(size),
    }


def make_entry(
    name: str | bytes,
    *,
    first: Mapping[str, int] | None = None,
    second: Mapping[str, int] | None = None,
    link: bytes = b"/tmp/x",
    first_rc: int = 0,
    first_errno: int = 0,
    second_rc: int = 0,
    second_errno: int = 0,
    link_rc: int | None = None,
    link_errno: int = 0,
) -> dict[str, Any]:
    first_stat = dict(first or make_stat(nlink=0, size=len(link)))
    second_stat = dict(second or first_stat)
    payload = bytes(link)
    return {
        "name": name if isinstance(name, bytes) else name.encode("ascii"),
        "first_rc": first_rc,
        "first_errno": first_errno,
        "first": first_stat,
        "second_rc": second_rc,
        "second_errno": second_errno,
        "second": second_stat,
        "link_rc": len(payload) if link_rc is None else link_rc,
        "link_errno": link_errno,
        "link": payload,
    }


def encode_scenario(
    *,
    entries: Sequence[Mapping[str, Any]] | None = None,
    open_errno: int = 0,
    dup_errno: int = 0,
    fdopendir_errno: int = 0,
    closedir_errno: int = 0,
    close_errno: int = 0,
    readdir_errno: int = 0,
    malloc_fail_call: int = 0,
    fwrite_fail_call: int = 0,
    fflush_errno: int = 0,
    stderr_errno: int = 0,
    force_size_range: int = 0,
) -> bytes:
    """Encode little-endian OU01 scenario consumed by SEAM_HELPER_C."""

    items = list(entries or ())
    out = bytearray(b"OU01")
    out += _u16(1)  # version
    out += _u16(0)  # reserved
    for value in (
        open_errno,
        dup_errno,
        fdopendir_errno,
        closedir_errno,
        close_errno,
        readdir_errno,
        malloc_fail_call,
        fwrite_fail_call,
        fflush_errno,
        stderr_errno,
        force_size_range,
        len(items),
    ):
        out += _u32(value)
    for entry in items:
        name = entry["name"]
        if isinstance(name, str):
            name = name.encode("ascii")
        name = bytes(name)
        if len(name) > 255:
            raise ValueError("descriptor name exceeds dirent.d_name budget")
        out += _u16(len(name))
        out += name
        out += _i32(int(entry.get("first_rc", 0)))
        out += _i32(int(entry.get("first_errno", 0)))
        first = entry.get("first") or make_stat()
        out += _u64(int(first["dev"]))
        out += _u64(int(first["ino"]))
        out += _u32(int(first["mode"]))
        out += _u64(int(first["nlink"]))
        out += _i64(int(first["size"]))
        out += _i32(int(entry.get("second_rc", 0)))
        out += _i32(int(entry.get("second_errno", 0)))
        second = entry.get("second") or first
        out += _u64(int(second["dev"]))
        out += _u64(int(second["ino"]))
        out += _u32(int(second["mode"]))
        out += _u64(int(second["nlink"]))
        out += _i64(int(second["size"]))
        link = bytes(entry.get("link", b""))
        link_rc = entry.get("link_rc")
        if link_rc is None:
            link_rc = len(link)
        out += _i32(int(link_rc))
        out += _i32(int(entry.get("link_errno", 0)))
        out += _u32(len(link))
        out += link
    return bytes(out)


@dataclass
class Trace:
    lines: list[str] = field(default_factory=list)

    def calls(self, name: str) -> list[str]:
        prefix = f"CALL {name}"
        return [line for line in self.lines if line.startswith(prefix)]

    def count_calls(self, name: str) -> int:
        return len(self.calls(name))

    def saw_call(self, name: str) -> bool:
        return self.count_calls(name) > 0

    def owns(self) -> list[str]:
        return [line for line in self.lines if line.startswith("OWN ")]

    @property
    def malloc_count(self) -> int:
        return self.count_calls("malloc")

    @property
    def realloc_count(self) -> int:
        return sum(1 for line in self.lines if line.startswith("CALL realloc"))


def parse_trace(text: str) -> Trace:
    return Trace(lines=[line for line in text.splitlines() if line.strip()])


def write_scenario(path: Path, blob: bytes) -> Path:
    path.write_bytes(blob)
    return path



SEAM_HEADER_C = '#ifndef OPENUNLINK_TEST_SEAM_H\n#define OPENUNLINK_TEST_SEAM_H\n\n#ifdef OPENUNLINK_TEST_SEAM\n#include <dirent.h>\n#include <fcntl.h>\n#include <stddef.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <sys/stat.h>\n#include <sys/types.h>\n#include <unistd.h>\n\nint openunlink_test_open(const char *path, int flags, ...);\nint openunlink_test_dup(int fd);\nDIR *openunlink_test_fdopendir(int fd);\nstruct dirent *openunlink_test_readdir(DIR *dirp);\nint openunlink_test_closedir(DIR *dirp);\nint openunlink_test_fstatat(int dirfd, const char *path, struct stat *st, int flags);\nssize_t openunlink_test_readlinkat(int dirfd, const char *path, char *buf, size_t bufsiz);\nint openunlink_test_close(int fd);\nvoid *openunlink_test_malloc(size_t size);\nvoid openunlink_test_free(void *ptr);\nsize_t openunlink_test_fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream);\nint openunlink_test_fflush(FILE *stream);\nint openunlink_test_fputc(int c, FILE *stream);\nint openunlink_test_fprintf(FILE *stream, const char *fmt, ...);\nint openunlink_test_force_size_range(void);\n\n#define open(path, flags) openunlink_test_open((path), (flags))\n#define dup(fd) openunlink_test_dup((fd))\n#define fdopendir(fd) openunlink_test_fdopendir((fd))\n#define readdir(dirp) openunlink_test_readdir((dirp))\n#define closedir(dirp) openunlink_test_closedir((dirp))\n#define fstatat(dirfd, path, st, flags) openunlink_test_fstatat((dirfd), (path), (st), (flags))\n#define readlinkat(dirfd, path, buf, bufsiz) openunlink_test_readlinkat((dirfd), (path), (buf), (bufsiz))\n#define close(fd) openunlink_test_close((fd))\n#define malloc(size) openunlink_test_malloc((size))\n#define free(ptr) openunlink_test_free((ptr))\n#define fwrite(ptr, size, nmemb, stream) openunlink_test_fwrite((ptr), (size), (nmemb), (stream))\n#define fflush(stream) openunlink_test_fflush((stream))\n#define fputc(c, stream) openunlink_test_fputc((c), (stream))\n#define fprintf openunlink_test_fprintf\n#endif /* OPENUNLINK_TEST_SEAM */\n\n#endif /* OPENUNLINK_TEST_SEAM_H */\n'

SEAM_HELPER_C = '#define _POSIX_C_SOURCE 200809L\n#define _FILE_OFFSET_BITS 64\n\n#include <dirent.h>\n#include <errno.h>\n#include <stdarg.h>\n#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <sys/stat.h>\n#include <sys/types.h>\n#include <unistd.h>\n\nenum { OU_VERSION = 1, OU_FD = 10000, OU_DUP_FD = 10001, OU_MAX_ENTRIES = 70000 };\n\nstruct ou_stat {\n    uint64_t dev;\n    uint64_t ino;\n    uint32_t mode;\n    uint64_t nlink;\n    int64_t size;\n};\n\nstruct ou_entry {\n    char *name;\n    int32_t stat_rc[2];\n    int32_t stat_errno[2];\n    struct ou_stat stats[2];\n    int32_t link_rc;\n    int32_t link_errno;\n    uint32_t link_len;\n    unsigned char *link;\n    unsigned stat_calls;\n};\n\nstruct ou_scenario {\n    uint32_t open_errno, dup_errno, fdopendir_errno, closedir_errno;\n    uint32_t close_errno, readdir_errno, malloc_fail_call, fwrite_fail_call;\n    uint32_t fflush_errno, stderr_errno, force_size_range, entry_count;\n    struct ou_entry *entries;\n};\n\nstatic struct ou_scenario g;\nstatic int g_loaded;\nstatic unsigned g_malloc_calls, g_fwrite_calls, g_next_entry;\nstatic int g_open_owned, g_dup_owned, g_dir_owned;\nstatic struct dirent g_dirent;\nstatic int g_fake_dir;\nstatic int g_readdir_failed;\n\nstatic void tracef(const char *fmt, ...)\n{\n    const char *path = getenv("OPENUNLINK_SEAM_TRACE");\n    FILE *fp;\n    va_list ap;\n    if (path == NULL || *path == \'\\0\')\n        return;\n    fp = fopen(path, "a");\n    if (fp == NULL)\n        return;\n    va_start(ap, fmt);\n    (void)vfprintf(fp, fmt, ap);\n    va_end(ap);\n    (void)fputc(\'\\n\', fp);\n    (void)fclose(fp);\n}\n\nstatic uint16_t get16(const unsigned char **p, const unsigned char *end, int *ok)\n{\n    uint16_t v;\n    if (!*ok || (size_t)(end - *p) < 2U) {\n        *ok = 0;\n        return 0;\n    }\n    v = (uint16_t)((uint16_t)(*p)[0] | ((uint16_t)(*p)[1] << 8));\n    *p += 2;\n    return v;\n}\n\nstatic uint32_t get32(const unsigned char **p, const unsigned char *end, int *ok)\n{\n    uint32_t v;\n    if (!*ok || (size_t)(end - *p) < 4U) {\n        *ok = 0;\n        return 0;\n    }\n    v = (uint32_t)(*p)[0] | ((uint32_t)(*p)[1] << 8) | ((uint32_t)(*p)[2] << 16) |\n        ((uint32_t)(*p)[3] << 24);\n    *p += 4;\n    return v;\n}\n\nstatic uint64_t get64(const unsigned char **p, const unsigned char *end, int *ok)\n{\n    uint64_t lo, hi;\n    if (!*ok || (size_t)(end - *p) < 8U) {\n        *ok = 0;\n        return 0;\n    }\n    lo = get32(p, end, ok);\n    hi = get32(p, end, ok);\n    return lo | (hi << 32);\n}\n\nstatic void read_stat(struct ou_stat *st, const unsigned char **p,\n                      const unsigned char *end, int *ok)\n{\n    st->dev = get64(p, end, ok);\n    st->ino = get64(p, end, ok);\n    st->mode = get32(p, end, ok);\n    st->nlink = get64(p, end, ok);\n    st->size = (int64_t)get64(p, end, ok);\n}\n\nstatic int read_scenario(void)\n{\n    const char *path = getenv("OPENUNLINK_SEAM_SCENARIO");\n    FILE *fp;\n    long len;\n    unsigned char *raw;\n    const unsigned char *p, *end;\n    int ok = 1;\n    uint16_t version, reserved;\n    uint32_t i;\n\n    if (path == NULL || *path == \'\\0\') {\n        errno = EINVAL;\n        return -1;\n    }\n    fp = fopen(path, "rb");\n    if (fp == NULL)\n        return -1;\n    if (fseek(fp, 0, SEEK_END) != 0 || (len = ftell(fp)) < 0 ||\n        fseek(fp, 0, SEEK_SET) != 0) {\n        (void)fclose(fp);\n        errno = EINVAL;\n        return -1;\n    }\n    raw = (unsigned char *)malloc((size_t)len);\n    if (raw == NULL) {\n        (void)fclose(fp);\n        return -1;\n    }\n    if (fread(raw, 1, (size_t)len, fp) != (size_t)len) {\n        free(raw);\n        (void)fclose(fp);\n        errno = EINVAL;\n        return -1;\n    }\n    (void)fclose(fp);\n    p = raw;\n    end = raw + (size_t)len;\n    if ((size_t)(end - p) < 8U || memcmp(p, "OU01", 4) != 0)\n        ok = 0;\n    p += ok ? 4 : 0;\n    version = get16(&p, end, &ok);\n    reserved = get16(&p, end, &ok);\n    (void)reserved;\n    if (!ok || version != OU_VERSION) {\n        free(raw);\n        errno = EINVAL;\n        return -1;\n    }\n#define OU_FIELD(field) g.field = get32(&p, end, &ok)\n    OU_FIELD(open_errno);\n    OU_FIELD(dup_errno);\n    OU_FIELD(fdopendir_errno);\n    OU_FIELD(closedir_errno);\n    OU_FIELD(close_errno);\n    OU_FIELD(readdir_errno);\n    OU_FIELD(malloc_fail_call);\n    OU_FIELD(fwrite_fail_call);\n    OU_FIELD(fflush_errno);\n    OU_FIELD(stderr_errno);\n    OU_FIELD(force_size_range);\n    OU_FIELD(entry_count);\n#undef OU_FIELD\n    if (!ok || g.entry_count > (uint32_t)OU_MAX_ENTRIES) {\n        free(raw);\n        errno = EINVAL;\n        return -1;\n    }\n    if (g.entry_count != 0U) {\n        g.entries = (struct ou_entry *)calloc(g.entry_count, sizeof(*g.entries));\n        if (g.entries == NULL) {\n            free(raw);\n            return -1;\n        }\n    }\n    for (i = 0; i < g.entry_count && ok; ++i) {\n        uint16_t n = get16(&p, end, &ok);\n        uint32_t link_len;\n        if (!ok || (size_t)(end - p) < n) {\n            ok = 0;\n            break;\n        }\n        g.entries[i].name = (char *)malloc((size_t)n + 1U);\n        if (g.entries[i].name == NULL) {\n            ok = 0;\n            break;\n        }\n        memcpy(g.entries[i].name, p, n);\n        g.entries[i].name[n] = \'\\0\';\n        p += n;\n        g.entries[i].stat_rc[0] = (int32_t)get32(&p, end, &ok);\n        g.entries[i].stat_errno[0] = (int32_t)get32(&p, end, &ok);\n        read_stat(&g.entries[i].stats[0], &p, end, &ok);\n        g.entries[i].stat_rc[1] = (int32_t)get32(&p, end, &ok);\n        g.entries[i].stat_errno[1] = (int32_t)get32(&p, end, &ok);\n        read_stat(&g.entries[i].stats[1], &p, end, &ok);\n        g.entries[i].link_rc = (int32_t)get32(&p, end, &ok);\n        g.entries[i].link_errno = (int32_t)get32(&p, end, &ok);\n        link_len = get32(&p, end, &ok);\n        g.entries[i].link_len = link_len;\n        if (!ok || (size_t)(end - p) < link_len) {\n            ok = 0;\n            break;\n        }\n        if (link_len != 0U) {\n            g.entries[i].link = (unsigned char *)malloc(link_len);\n            if (g.entries[i].link == NULL) {\n                ok = 0;\n                break;\n            }\n            memcpy(g.entries[i].link, p, link_len);\n        }\n        p += link_len;\n    }\n    free(raw);\n    if (!ok || p != end) {\n        errno = EINVAL;\n        return -1;\n    }\n    return 0;\n}\n\nstatic int ensure_loaded(void)\n{\n    if (!g_loaded) {\n        if (read_scenario() != 0)\n            return -1;\n        g_loaded = 1;\n        tracef("OWN scenario loaded entries=%u", g.entry_count);\n    }\n    return 0;\n}\n\nstatic struct ou_entry *entry_for(const char *name)\n{\n    uint32_t i;\n    for (i = 0; i < g.entry_count; ++i) {\n        if (strcmp(g.entries[i].name, name) == 0)\n            return &g.entries[i];\n    }\n    return NULL;\n}\n\nstatic void fill_stat(struct stat *st, const struct ou_stat *src)\n{\n    if (st == NULL)\n        return;\n    memset(st, 0, sizeof(*st));\n    st->st_dev = (dev_t)src->dev;\n    st->st_ino = (ino_t)src->ino;\n    st->st_mode = (mode_t)src->mode;\n    st->st_nlink = (nlink_t)src->nlink;\n    st->st_size = (off_t)src->size;\n}\n\nint openunlink_test_open(const char *path, int flags, ...)\n{\n    (void)flags;\n    if (ensure_loaded() != 0) {\n        tracef("CALL open path=%s rc=-1 errno=%d", path, errno);\n        return -1;\n    }\n    if (g.open_errno != 0U) {\n        errno = (int)g.open_errno;\n        tracef("CALL open path=%s rc=-1 errno=%d", path, errno);\n        return -1;\n    }\n    g_open_owned = 1;\n    tracef("CALL open path=%s rc=%d errno=0", path, OU_FD);\n    tracef("OWN open fd=%d", OU_FD);\n    return OU_FD;\n}\n\nint openunlink_test_dup(int fd)\n{\n    if (ensure_loaded() != 0) {\n        tracef("CALL dup fd=%d rc=-1 errno=%d", fd, errno);\n        return -1;\n    }\n    if (g.dup_errno != 0U) {\n        errno = (int)g.dup_errno;\n        tracef("CALL dup fd=%d rc=-1 errno=%d", fd, errno);\n        return -1;\n    }\n    g_dup_owned = 1;\n    tracef("CALL dup fd=%d rc=%d errno=0", fd, OU_DUP_FD);\n    tracef("OWN dup fd=%d", OU_DUP_FD);\n    return OU_DUP_FD;\n}\n\nDIR *openunlink_test_fdopendir(int fd)\n{\n    if (ensure_loaded() != 0) {\n        tracef("CALL fdopendir fd=%d rc=NULL errno=%d", fd, errno);\n        return NULL;\n    }\n    if (g.fdopendir_errno != 0U) {\n        errno = (int)g.fdopendir_errno;\n        tracef("CALL fdopendir fd=%d rc=NULL errno=%d", fd, errno);\n        return NULL;\n    }\n    g_dir_owned = 1;\n    g_dup_owned = 0;\n    tracef("CALL fdopendir fd=%d rc=fake errno=0", fd);\n    tracef("OWN dir takes-fd=%d", fd);\n    return (DIR *)(void *)&g_fake_dir;\n}\n\nstruct dirent *openunlink_test_readdir(DIR *dirp)\n{\n    const char *name;\n    (void)dirp;\n    if (ensure_loaded() != 0)\n        return NULL;\n    if (g.readdir_errno != 0U && !g_readdir_failed &&\n        g_next_entry >= g.entry_count) {\n        /* Fall through: inject after exhausting scripted names, or: */\n    }\n    if (g.readdir_errno != 0U && !g_readdir_failed && g_next_entry == 0U &&\n        g.entry_count == 0U) {\n        g_readdir_failed = 1;\n        errno = (int)g.readdir_errno;\n        tracef("CALL readdir rc=NULL errno=%d", errno);\n        return NULL;\n    }\n    if (g.readdir_errno != 0U && !g_readdir_failed &&\n        g_next_entry >= g.entry_count) {\n        g_readdir_failed = 1;\n        errno = (int)g.readdir_errno;\n        tracef("CALL readdir rc=NULL errno=%d", errno);\n        return NULL;\n    }\n    if (g_next_entry >= g.entry_count) {\n        errno = 0;\n        tracef("CALL readdir rc=NULL errno=0");\n        return NULL;\n    }\n    /* Optional mid-stream readdir failure: readdir_errno with sentinel name. */\n    name = g.entries[g_next_entry].name;\n    if (g.readdir_errno != 0U && !g_readdir_failed &&\n        strcmp(name, "__READDIR_FAIL__") == 0) {\n        g_readdir_failed = 1;\n        errno = (int)g.readdir_errno;\n        tracef("CALL readdir rc=NULL errno=%d", errno);\n        return NULL;\n    }\n    g_next_entry++;\n    memset(&g_dirent, 0, sizeof(g_dirent));\n    (void)snprintf(g_dirent.d_name, sizeof(g_dirent.d_name), "%s", name);\n    errno = 0;\n    tracef("CALL readdir name=%s rc=entry errno=0", name);\n    return &g_dirent;\n}\n\nint openunlink_test_closedir(DIR *dirp)\n{\n    (void)dirp;\n    g_dir_owned = 0;\n    if (ensure_loaded() != 0) {\n        tracef("CALL closedir rc=-1 errno=%d", errno);\n        return -1;\n    }\n    if (g.closedir_errno != 0U) {\n        errno = (int)g.closedir_errno;\n        tracef("CALL closedir rc=-1 errno=%d", errno);\n        tracef("OWN dir released");\n        return -1;\n    }\n    tracef("CALL closedir rc=0 errno=0");\n    tracef("OWN dir released");\n    return 0;\n}\n\nint openunlink_test_fstatat(int dirfd, const char *path, struct stat *st, int flags)\n{\n    struct ou_entry *e;\n    unsigned n;\n\n    if (ensure_loaded() != 0) {\n        tracef("CALL fstatat fd=%d path=%s flags=%d rc=-1 errno=%d", dirfd, path,\n               flags, errno);\n        return -1;\n    }\n    e = entry_for(path);\n    if (e == NULL) {\n        errno = ENOENT;\n        tracef("CALL fstatat fd=%d path=%s flags=%d rc=-1 errno=%d", dirfd, path,\n               flags, errno);\n        return -1;\n    }\n    n = e->stat_calls;\n    if (n > 1U)\n        n = 1U;\n    e->stat_calls++;\n    if (e->stat_rc[n] < 0) {\n        errno = (int)e->stat_errno[n];\n        tracef("CALL fstatat fd=%d path=%s flags=%d rc=-1 errno=%d", dirfd, path,\n               flags, errno);\n        return -1;\n    }\n    fill_stat(st, &e->stats[n]);\n    tracef("CALL fstatat fd=%d path=%s flags=%d rc=0 errno=0 mode=%u nlink=%llu size=%lld",\n           dirfd, path, flags, (unsigned)e->stats[n].mode,\n           (unsigned long long)e->stats[n].nlink, (long long)e->stats[n].size);\n    return 0;\n}\n\nssize_t openunlink_test_readlinkat(int dirfd, const char *path, char *buf,\n                                   size_t bufsiz)\n{\n    struct ou_entry *e;\n    size_t n;\n\n    if (ensure_loaded() != 0) {\n        tracef("CALL readlinkat fd=%d path=%s rc=-1 errno=%d", dirfd, path, errno);\n        return -1;\n    }\n    e = entry_for(path);\n    if (e == NULL || e->link_rc < 0) {\n        errno = e == NULL ? ENOENT : (int)e->link_errno;\n        tracef("CALL readlinkat fd=%d path=%s rc=-1 errno=%d", dirfd, path, errno);\n        return -1;\n    }\n    n = (size_t)e->link_rc;\n    if (n > bufsiz)\n        n = bufsiz;\n    if (n != 0U) {\n        size_t copy = n;\n        if (copy > (size_t)e->link_len)\n            copy = (size_t)e->link_len;\n        if (copy != 0U && e->link != NULL)\n            memcpy(buf, e->link, copy);\n        if (copy < n)\n            memset(buf + copy, \'X\', n - copy);\n    }\n    tracef("CALL readlinkat fd=%d path=%s rc=%zu errno=0", dirfd, path, n);\n    return (ssize_t)n;\n}\n\nint openunlink_test_close(int fd)\n{\n    if (fd == OU_FD)\n        g_open_owned = 0;\n    if (fd == OU_DUP_FD)\n        g_dup_owned = 0;\n    if (ensure_loaded() != 0) {\n        tracef("CALL close fd=%d rc=-1 errno=%d", fd, errno);\n        return -1;\n    }\n    if (g.close_errno != 0U) {\n        errno = (int)g.close_errno;\n        tracef("CALL close fd=%d rc=-1 errno=%d", fd, errno);\n        tracef("OWN close fd=%d", fd);\n        return -1;\n    }\n    tracef("CALL close fd=%d rc=0 errno=0", fd);\n    tracef("OWN close fd=%d", fd);\n    return 0;\n}\n\nvoid *openunlink_test_malloc(size_t size)\n{\n    void *p;\n    (void)ensure_loaded();\n    ++g_malloc_calls;\n    if (g.malloc_fail_call != 0U && g_malloc_calls == g.malloc_fail_call) {\n        errno = ENOMEM;\n        tracef("CALL malloc size=%zu rc=NULL errno=%d", size, errno);\n        return NULL;\n    }\n    p = malloc(size);\n    tracef("CALL malloc size=%zu rc=%p errno=0", size, p);\n    return p;\n}\n\nvoid openunlink_test_free(void *ptr)\n{\n    tracef("CALL free ptr=%p", ptr);\n    tracef("OWN free ptr=%p", ptr);\n    free(ptr);\n}\n\nsize_t openunlink_test_fwrite(const void *ptr, size_t size, size_t nmemb,\n                              FILE *stream)\n{\n    size_t rc;\n    if (ensure_loaded() != 0)\n        return 0;\n    if (stream == stdout) {\n        ++g_fwrite_calls;\n        if (g.fwrite_fail_call != 0U && g_fwrite_calls == g.fwrite_fail_call) {\n            errno = EIO;\n            tracef("CALL fwrite stream=stdout size=%zu nmemb=%zu rc=0 errno=%d",\n                   size, nmemb, errno);\n            return 0;\n        }\n    }\n    if (stream == stderr && g.stderr_errno != 0U) {\n        errno = (int)g.stderr_errno;\n        tracef("CALL fwrite stream=stderr size=%zu nmemb=%zu rc=0 errno=%d", size,\n               nmemb, errno);\n        return 0;\n    }\n    rc = fwrite(ptr, size, nmemb, stream);\n    tracef("CALL fwrite stream=%s size=%zu nmemb=%zu rc=%zu errno=0",\n           stream == stdout ? "stdout" : (stream == stderr ? "stderr" : "other"),\n           size, nmemb, rc);\n    return rc;\n}\n\nint openunlink_test_fflush(FILE *stream)\n{\n    int rc;\n    if (ensure_loaded() == 0 && stream == stdout && g.fflush_errno != 0U) {\n        errno = (int)g.fflush_errno;\n        tracef("CALL fflush stream=stdout rc=-1 errno=%d", errno);\n        return -1;\n    }\n    rc = fflush(stream);\n    tracef("CALL fflush stream=%s rc=%d errno=%d",\n           stream == stdout ? "stdout" : "other", rc, rc == 0 ? 0 : errno);\n    return rc;\n}\n\nint openunlink_test_fputc(int c, FILE *stream)\n{\n    int rc;\n    if (ensure_loaded() == 0 && stream == stderr && g.stderr_errno != 0U) {\n        errno = (int)g.stderr_errno;\n        tracef("CALL fputc stream=stderr c=%d rc=EOF errno=%d", c, errno);\n        return EOF;\n    }\n    rc = fputc(c, stream);\n    tracef("CALL fputc stream=%s c=%d rc=%d errno=%d",\n           stream == stderr ? "stderr" : "other", c, rc, rc == EOF ? errno : 0);\n    return rc;\n}\n\nint openunlink_test_fprintf(FILE *stream, const char *fmt, ...)\n{\n    int rc;\n    va_list ap;\n    if (ensure_loaded() == 0 && stream == stderr && g.stderr_errno != 0U) {\n        errno = (int)g.stderr_errno;\n        tracef("CALL fprintf stream=stderr rc=-1 errno=%d", errno);\n        return -1;\n    }\n    if (ensure_loaded() == 0 && stream == stdout && g.fwrite_fail_call != 0U) {\n        ++g_fwrite_calls;\n        if (g_fwrite_calls == g.fwrite_fail_call) {\n            errno = EIO;\n            tracef("CALL fprintf stream=stdout rc=-1 errno=%d", errno);\n            return -1;\n        }\n    }\n    va_start(ap, fmt);\n    rc = vfprintf(stream, fmt, ap);\n    va_end(ap);\n    tracef("CALL fprintf stream=%s rc=%d errno=%d",\n           stream == stdout ? "stdout" : (stream == stderr ? "stderr" : "other"),\n           rc, rc < 0 ? errno : 0);\n    return rc;\n}\n\nint openunlink_test_force_size_range(void)\n{\n    (void)ensure_loaded();\n    tracef("OWN state open=%d dup=%d dir=%d", g_open_owned, g_dup_owned,\n           g_dir_owned);\n    tracef("CALL force_size_range rc=%u", g.force_size_range != 0U);\n    return g.force_size_range != 0U;\n}\n'

def _base_child_env(extra: Mapping[str, str | None] | None = None) -> dict[str, str]:
    run_env: dict[str, str] = {
        "PATH": "/openunlink-tests-must-not-search-here",
        "LC_ALL": "C",
        "LANG": "C",
    }
    for key in SANITIZER_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None:
            run_env[key] = value
    if extra:
        for key, value in extra.items():
            if value is None:
                run_env.pop(key, None)
            else:
                run_env[key] = value
    return run_env


def _valgrind_command(cmd: list[str]):
    if os.environ.get("OPENUNLINK_UNDER_VALGRIND") != "1":
        return cmd, None
    valgrind = shutil.which("valgrind")
    if valgrind is None:
        raise AssertionError(
            "OPENUNLINK_UNDER_VALGRIND=1 but valgrind was not found on PATH"
        )
    fd, vg_log = tempfile.mkstemp(prefix="openunlink-valgrind.", dir="/tmp")
    os.close(fd)
    wrapped = [
        valgrind,
        "--quiet",
        "--error-exitcode=99",
        "--leak-check=full",
        "--show-leak-kinds=all",
        "--track-fds=yes",
        f"--log-file={vg_log}",
        *cmd,
    ]
    return wrapped, vg_log


def _finish_valgrind(result, vg_log):
    if vg_log is None:
        return result
    try:
        log_size = os.path.getsize(vg_log)
        if result.returncode == 99 or log_size > 0:
            with open(vg_log, "rb") as handle:
                detail = handle.read().decode("utf-8", errors="replace")
            raise AssertionError(
                f"valgrind reported errors (status {result.returncode}):\n{detail}"
            )
    finally:
        os.unlink(vg_log)
    return result


def resolve_openunlink_override(env_bin: str) -> Path:
    resolved = Path(env_bin).expanduser().resolve()
    if not resolved.is_absolute():
        raise ValueError(f"OPENUNLINK_BIN did not resolve absolute: {env_bin!r}")
    return resolved


def _compile_argv(output: Path, *sources: Path, seam: bool = False) -> list[str]:
    if seam:
        include_dir = output.parent
        argv = [
            os.environ.get("CC", "cc"),
            *STRICT_WARNING_FLAGS,
            *PLATFORM_CFLAGS,
            SEAM_MACRO,
            f"-I{include_dir}",
            "-o",
            str(output),
            *[str(src) for src in sources],
        ]
    else:
        argv = [
            os.environ.get("CC", "cc"),
            *STRICT_WARNING_FLAGS,
            *PLATFORM_CFLAGS,
            "-o",
            str(output),
            *[str(src) for src in sources],
        ]
    extra = os.environ.get("OPENUNLINK_SEAM_CFLAGS", "").strip()
    if extra:
        o_index = argv.index("-o")
        argv[o_index:o_index] = extra.split()
    return argv


def _require_source() -> None:
    if not SRC.is_file():
        pytest.fail(
            f"{SRC} is missing; openunlink contract suite requires the source"
        )


def run_openunlink(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str | None] | None = None,
    scenario: Path | None = None,
    trace: Path | None = None,
    timeout: float | None = 60.0,
):
    argv: list[str] = [str(binary)]
    for arg in args:
        if isinstance(arg, bytes):
            argv.append(os.fsdecode(arg))
        else:
            argv.append(os.fspath(arg))
    extra = dict(env) if env else {}
    if scenario is not None:
        extra["OPENUNLINK_SEAM_SCENARIO"] = str(scenario)
    if trace is not None:
        if trace.exists():
            trace.unlink()
        extra["OPENUNLINK_SEAM_TRACE"] = str(trace)
    cmd, vg_log = _valgrind_command(argv)
    result = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        cwd=None if cwd is None else os.fspath(cwd),
        env=_base_child_env(extra),
        timeout=timeout,
    )
    return _finish_valgrind(result, vg_log)


def _argv_for(binary: Path, *args: bytes | str | os.PathLike[str]) -> list[str]:
    argv = [str(binary)]
    for arg in args:
        if isinstance(arg, bytes):
            argv.append(os.fsdecode(arg))
        else:
            argv.append(os.fspath(arg))
    return argv


def run_with_closed_stdout_pipe(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    env: Mapping[str, str | None] | None = None,
    scenario: Path | None = None,
    trace: Path | None = None,
):
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    extra = dict(env) if env else {}
    if scenario is not None:
        extra["OPENUNLINK_SEAM_SCENARIO"] = str(scenario)
    if trace is not None:
        if trace.exists():
            trace.unlink()
        extra["OPENUNLINK_SEAM_TRACE"] = str(trace)
    cmd, vg_log = _valgrind_command(_argv_for(binary, *args))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=write_fd,
            stderr=subprocess.PIPE,
            env=_base_child_env(extra),
        )
    finally:
        os.close(write_fd)
    _, stderr = proc.communicate(timeout=60)
    _finish_valgrind(types.SimpleNamespace(returncode=proc.returncode), vg_log)
    return proc.returncode, stderr


def run_with_closed_stderr_pipe(
    binary: Path,
    *args: bytes | str | os.PathLike[str],
    env: Mapping[str, str | None] | None = None,
    scenario: Path | None = None,
    trace: Path | None = None,
):
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    extra = dict(env) if env else {}
    if scenario is not None:
        extra["OPENUNLINK_SEAM_SCENARIO"] = str(scenario)
    if trace is not None:
        if trace.exists():
            trace.unlink()
        extra["OPENUNLINK_SEAM_TRACE"] = str(trace)
    cmd, vg_log = _valgrind_command(_argv_for(binary, *args))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=write_fd,
            env=_base_child_env(extra),
        )
    finally:
        os.close(write_fd)
    stdout, _ = proc.communicate(timeout=60)
    _finish_valgrind(types.SimpleNamespace(returncode=proc.returncode), vg_log)
    return proc.returncode, stdout


_FIXTURE_CHILD = """
import hashlib, json, os, socket, sys, tempfile
root = tempfile.mkdtemp(prefix="openunlink-fixture-", dir="/tmp")
os.chmod(root, 0o700)

def hold(name, data, unlink=False):
    path = os.path.join(root, name)
    with open(path, "wb") as handle:
        handle.write(data)
    fd = os.open(path, os.O_RDONLY)
    if unlink:
        os.unlink(path)
    return path, fd

linked_path, linked_fd = hold("linked", b"linked-payload\\n")
unlinked_path, unlinked_fd = hold("unlinked", b"unlinked-payload\\n", True)
dup_fd = os.dup(unlinked_fd)
deleted_name_path, deleted_name_fd = hold("literal (deleted)", b"still-linked\\n")
pipe_r, pipe_w = os.pipe()
sock_a, sock_b = socket.socketpair()
fds = {
    "linked": linked_fd,
    "unlinked": unlinked_fd,
    "unlinked_dup": dup_fd,
    "literal_deleted": deleted_name_fd,
    "pipe_r": pipe_r,
    "pipe_w": pipe_w,
    "sock_a": sock_a.fileno(),
    "sock_b": sock_b.fileno(),
}
print(json.dumps({"pid": os.getpid(), "fds": fds, "root": root}), flush=True)

def details():
    out = {}
    for name, fd in fds.items():
        try:
            st = os.fstat(fd)
            data = b""
            if name in ("linked", "unlinked", "unlinked_dup", "literal_deleted"):
                data = os.pread(fd, st.st_size if st.st_size > 0 else 0, 0)
            out[name] = {
                "dev": st.st_dev,
                "ino": st.st_ino,
                "mode": st.st_mode,
                "nlink": st.st_nlink,
                "size": st.st_size,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        except OSError as exc:
            out[name] = {"errno": exc.errno}
    return out

for line in sys.stdin:
    if line == "SNAP\\n":
        print(json.dumps({"snapshot": details()}), flush=True)
    elif line == "RELEASE\\n":
        break

for fd in (linked_fd, unlinked_fd, dup_fd, deleted_name_fd, pipe_r, pipe_w):
    try:
        os.close(fd)
    except OSError:
        pass
sock_a.close()
sock_b.close()
for path in (linked_path, deleted_name_path):
    try:
        os.unlink(path)
    except OSError:
        pass
try:
    os.rmdir(root)
except OSError:
    pass
"""


class FrozenFdFixture:
    """Handshake-controlled same-UID child holding linked/unlinked/non-regular FDs."""

    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.pid: int | None = None
        self.fds: dict[str, int] = {}
        self.root: str | None = None

    def __enter__(self) -> "FrozenFdFixture":
        self.process = subprocess.Popen(
            [sys.executable, "-c", _FIXTURE_CHILD],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_base_child_env(),
        )
        assert self.process.stdout is not None
        line = self.process.stdout.readline()
        if not line:
            err = self.process.stderr.read() if self.process.stderr else ""
            self.process.wait(timeout=5)
            raise RuntimeError(f"fixture child failed before handshake: {err}")
        ready = json.loads(line)
        self.pid = int(ready["pid"])
        self.fds = {name: int(fd) for name, fd in ready["fds"].items()}
        self.root = ready.get("root")
        return self

    def snapshot(self) -> dict[str, Any]:
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.stdout is None
        ):
            raise RuntimeError("fixture inactive")
        self.process.stdin.write("SNAP\n")
        self.process.stdin.flush()
        reply = json.loads(self.process.stdout.readline())
        return reply["snapshot"]

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.process is None:
            return
        try:
            if self.process.poll() is None and self.process.stdin is not None:
                self.process.stdin.write("RELEASE\n")
                self.process.stdin.flush()
                self.process.stdin.close()
            self.process.wait(timeout=10)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        finally:
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.stderr is not None:
                self.process.stderr.close()


def install_seam_sources(build_dir: Path) -> tuple[Path, Path]:
    header = build_dir / "openunlink_test_seam.h"
    helper = build_dir / "openunlink_test_seam.c"
    header.write_text(SEAM_HEADER_C, encoding="utf-8")
    helper.write_text(SEAM_HELPER_C, encoding="utf-8")
    return header, helper


def compile_production_binary(build_dir: Path) -> Path:
    _require_source()
    binary = build_dir / "openunlink"
    argv = _compile_argv(binary, SRC, seam=False)
    compiled = subprocess.run(argv, capture_output=True, check=False)
    if compiled.returncode != 0:
        detail = compiled.stderr.decode("utf-8", errors="replace")
        pytest.fail(f"failed to compile production {SRC}:\n{detail}")
    assert binary.is_file() and os.access(binary, os.X_OK)
    if str(binary.resolve()).startswith(str(ROOT.resolve()) + os.sep):
        pytest.fail(f"binary landed inside workspace: {binary}")
    _LAST_OPENUNLINK_COMPILE_ARGV[:] = list(argv)
    return binary


def compile_seam_binary(build_dir: Path) -> Path:
    _require_source()
    install_seam_sources(build_dir)
    src_text = SRC.read_text(encoding="utf-8")
    if "OPENUNLINK_TEST_SEAM" not in src_text or "openunlink_test_seam.h" not in src_text:
        pytest.fail(
            f"{SRC} must include openunlink_test_seam.h under OPENUNLINK_TEST_SEAM "
            "so the deterministic seam can remap boundary calls"
        )
    binary = build_dir / "openunlink-seam"
    helper = build_dir / "openunlink_test_seam.c"
    argv = _compile_argv(binary, SRC, helper, seam=True)
    compiled = subprocess.run(argv, capture_output=True, check=False)
    if compiled.returncode != 0:
        detail = compiled.stderr.decode("utf-8", errors="replace")
        pytest.fail(f"failed to compile seam {SRC}:\n{detail}")
    assert binary.is_file() and os.access(binary, os.X_OK)
    if str(binary.resolve()).startswith(str(ROOT.resolve()) + os.sep):
        pytest.fail(f"seam binary landed inside workspace: {binary}")
    return binary


@pytest.fixture(scope="session")
def openunlink_bin():
    env_bin = os.environ.get("OPENUNLINK_BIN")
    if env_bin:
        binary = resolve_openunlink_override(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"OPENUNLINK_BIN is not an executable file: {env_bin}")
        _LAST_OPENUNLINK_COMPILE_ARGV.clear()
        return binary
    build_dir = mk_outside_build_dir("openunlink-prod.")
    try:
        return compile_production_binary(build_dir)
    except Exception:
        shutil.rmtree(build_dir, ignore_errors=True)
        raise


@pytest.fixture(scope="session")
def openunlink_seam_bin():
    build_dir = mk_outside_build_dir("openunlink-seam.")
    try:
        return compile_seam_binary(build_dir)
    except Exception:
        shutil.rmtree(build_dir, ignore_errors=True)
        raise


@pytest.fixture
def seam_workdir():
    path = mk_outside_build_dir("openunlink-case.")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def status1_caller_class(returncode: int, stdout: bytes) -> str:
    """Shell-style SIXTH2-M3 discriminator."""

    if returncode != STATUS_RESULT:
        return "not-status-1"
    if len(stdout) > 0:
        return "finding-bearing"
    return "advisory-only"


# ---------------------------------------------------------------------------
# CLI oracles (OU-AC-03)
# ---------------------------------------------------------------------------


def test_help_exact_bytes(openunlink_bin):
    result = run_openunlink(openunlink_bin, "--help")
    assert result.returncode == STATUS_OK
    assert result.stdout == HELP_STDOUT
    assert result.stderr == b""


def test_version_exact_bytes(openunlink_bin):
    result = run_openunlink(openunlink_bin, "--version")
    assert result.returncode == STATUS_OK
    assert result.stdout == VERSION_STDOUT
    assert result.stderr == b""


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("",),
        ("0",),
        ("01",),
        ("001",),
        ("+1",),
        ("-1",),
        ("1 ",),
        (" 1",),
        ("1\n",),
        ("1a",),
        ("a1",),
        ("1.0",),
        ("0x10",),
        (str(INT_MAX + 1),),
        ("2147483648",),
        ("999999999999999999999",),
        ("--help", "1"),
        ("1", "--help"),
        ("--version", "1"),
        ("--help", "--version"),
        ("--foo",),
        ("-h",),
        ("-v",),
        ("1", "2"),
        ("--", "1"),
        ("--",),
    ],
)
def test_usage_rejects_invalid_cli(openunlink_bin, args):
    result = run_openunlink(openunlink_bin, *args)
    assert result.returncode == STATUS_ERROR
    assert result.stdout == b""
    assert result.stderr == diagnostic_global("USAGE")


def test_canonical_pid_int_max_accepted_or_maps_process_error(openunlink_bin):
    """PID INT_MAX is grammatically valid; absent process maps operationally."""

    result = run_openunlink(openunlink_bin, str(INT_MAX))
    assert result.returncode == STATUS_ERROR
    assert result.stdout == b""
    assert result.stderr in (
        diagnostic_pid("PROCESS_NOT_FOUND", INT_MAX),
        diagnostic_pid("PROCESS_ACCESS", INT_MAX),
        diagnostic_pid("PROCESS_SCAN", INT_MAX),
    )


def test_canonical_pid_one_grammatically_valid(openunlink_bin):
    result = run_openunlink(openunlink_bin, "1")
    assert result.returncode in (STATUS_OK, STATUS_RESULT, STATUS_ERROR)
    if result.returncode == STATUS_ERROR:
        assert result.stdout == b""
        assert (
            result.stderr.startswith(b"openunlink: PROCESS_")
            or result.stderr == diagnostic_global("MEMORY")
            or result.stderr == diagnostic_global("STDOUT_WRITE")
        )


# ---------------------------------------------------------------------------
# Real same-UID fixtures (OU-AC-02, OU-AC-04, OU-AC-05)
# ---------------------------------------------------------------------------


def test_real_fixture_unlinked_duplicates_nonregular_and_suffix(openunlink_bin):
    """OU-AC-02/04/05: handshake fixture covers linked/unlinked/dup/non-regular/suffix."""

    with FrozenFdFixture() as fix:
        before = fix.snapshot()
        assert before["linked"]["nlink"] >= 1
        assert before["literal_deleted"]["nlink"] >= 1
        assert before["unlinked"]["nlink"] == 0
        assert before["unlinked_dup"]["nlink"] == 0
        result = run_openunlink(openunlink_bin, str(fix.pid))
        after = fix.snapshot()
        assert fix.alive()
        assert before == after
        assert result.returncode in (STATUS_OK, STATUS_RESULT, STATUS_ERROR)
        assert_no_raw_unsafe_bytes(result.stdout)
        assert_no_raw_unsafe_bytes(result.stderr)
        if result.returncode == STATUS_ERROR:
            # Restricted/absent procfs must map to the closed operational set.
            assert result.stdout == b""
            assert result.stderr in (
                diagnostic_pid("PROCESS_NOT_FOUND", fix.pid),
                diagnostic_pid("PROCESS_ACCESS", fix.pid),
                diagnostic_pid("PROCESS_SCAN", fix.pid),
            )
            return
        unlinked_fd = fix.fds["unlinked"]
        dup_fd = fix.fds["unlinked_dup"]
        size = before["unlinked"]["size"]
        if result.returncode == STATUS_OK:
            assert result.stdout == b""
            assert result.stderr == b""
            return
        assert result.returncode == STATUS_RESULT
        lines = result.stdout.splitlines(keepends=True)
        assert len(lines) >= 1
        assert all(line.startswith(b"OPEN_UNLINKED\t") for line in lines)
        fds_seen = []
        for line in lines:
            match = re.search(rb"\tfd=(\d+)\t", line)
            assert match is not None
            fds_seen.append(int(match.group(1)))
        assert fds_seen == sorted(fds_seen)
        assert unlinked_fd in fds_seen
        assert dup_fd in fds_seen
        assert fds_seen.count(unlinked_fd) == 1
        assert fds_seen.count(dup_fd) == 1
        for name in (
            "pipe_r",
            "pipe_w",
            "sock_a",
            "sock_b",
            "linked",
            "literal_deleted",
        ):
            assert fix.fds[name] not in fds_seen
        for line in lines:
            if (
                f"fd={unlinked_fd}".encode("ascii") in line
                or f"fd={dup_fd}".encode("ascii") in line
            ):
                assert f"size={size}".encode("ascii") in line
        assert status1_caller_class(result.returncode, result.stdout) == (
            "finding-bearing"
        )


def test_repeat_scan_byte_identical(openunlink_bin):
    with FrozenFdFixture() as fix:
        first = run_openunlink(openunlink_bin, str(fix.pid))
        second = run_openunlink(openunlink_bin, str(fix.pid))
        assert first.returncode == second.returncode
        assert first.stdout == second.stdout
        assert first.stderr == second.stderr


def test_fixture_survives_and_no_control_action(openunlink_bin):
    with FrozenFdFixture() as fix:
        before = fix.snapshot()
        run_openunlink(openunlink_bin, str(fix.pid))
        after = fix.snapshot()
        assert fix.alive()
        assert before == after


# ---------------------------------------------------------------------------
# Seam helpers for classification scenarios
# ---------------------------------------------------------------------------


def _zero_link_entry(
    name: str, *, ino: int, size: int | None = None, link: bytes = b"abc"
):
    # OPEN_UNLINKED prints the final st_size, so the seam fixture defaults to
    # the payload length and only uses an explicit size for boundary cases.
    if size is None:
        size = len(link)
    st = make_stat(dev=10, ino=ino, mode=S_IFREG | 0o600, nlink=0, size=size)
    return make_entry(name, first=st, second=st, link=link)


def _nonzero_link_entry(name: str, *, ino: int, link: bytes = b"/tmp/x (deleted)"):
    st = make_stat(dev=10, ino=ino, mode=S_IFREG | 0o600, nlink=1, size=len(link))
    return make_entry(name, first=st, second=st, link=link)


def _nonreg_entry(name: str, *, mode: int, ino: int):
    st = make_stat(dev=10, ino=ino, mode=mode, nlink=1, size=0)
    return make_entry(name, first=st, second=st, link=b"ignored")


def test_seam_single_finding(openunlink_seam_bin, seam_workdir):
    pid = 4242
    entry = _zero_link_entry("7", ino=99, size=3, link=b"abc")
    # Include . and .. which must be ignored before descriptor-name parsing.
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[
                make_entry(".", first=make_stat(mode=S_IFREG), link=b"."),
                make_entry("..", first=make_stat(mode=S_IFREG), link=b".."),
                entry,
            ]
        ),
    )
    trace = seam_workdir / "t.txt"
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, trace=trace
    )
    assert result.returncode == STATUS_RESULT
    assert result.stdout == finding_line(pid, 7, 3, b"abc")
    assert result.stderr == b""
    tr = parse_trace(trace.read_text(encoding="utf-8"))
    assert tr.saw_call("open")
    assert any(f"path=/proc/{pid}/fd" in line for line in tr.calls("open"))
    assert tr.saw_call("fstatat")
    assert tr.saw_call("readlinkat")
    assert status1_caller_class(result.returncode, result.stdout) == "finding-bearing"


def test_seam_linked_nonzero_silent(openunlink_seam_bin, seam_workdir):
    pid = 7
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_nonzero_link_entry("3", ino=1)]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_OK
    assert result.stdout == b""
    assert result.stderr == b""


def test_seam_literal_deleted_suffix_nonzero_silent(openunlink_seam_bin, seam_workdir):
    pid = 9
    link = b"/var/tmp/name (deleted)"
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_nonzero_link_entry("4", ino=2, link=link)]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_OK
    assert result.stdout == b""
    assert result.stderr == b""


def test_seam_nfs_silly_rename_nonzero_silent(openunlink_seam_bin, seam_workdir):
    pid = 11
    link = b"/.nfsDEADBEEF"
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_nonzero_link_entry("5", ino=3, link=link)]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_OK
    assert result.stdout == b""


def test_seam_nonregular_silent(openunlink_seam_bin, seam_workdir):
    pid = 12
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[
                _nonreg_entry("8", mode=S_IFIFO | 0o600, ino=4),
                _nonreg_entry("9", mode=S_IFSOCK | 0o600, ino=5),
            ]
        ),
    )
    trace = seam_workdir / "t.txt"
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, trace=trace
    )
    assert result.returncode == STATUS_OK
    assert result.stdout == b""
    assert result.stderr == b""
    tr = parse_trace(trace.read_text(encoding="utf-8"))
    # First non-regular must not issue readlinkat.
    assert tr.count_calls("readlinkat") == 0


def test_seam_numeric_ordering_and_duplicates(openunlink_seam_bin, seam_workdir):
    pid = 13
    # Observed order scrambled; findings must emit ascending fd numbers.
    e3 = _zero_link_entry("3", ino=30, link=b"a")
    e10 = _zero_link_entry("10", ino=30, link=b"a")  # same inode, separate lines
    e2 = _zero_link_entry("2", ino=22, link=b"b")
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[e10, e3, e2]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == (
        finding_line(pid, 2, 1, b"b")
        + finding_line(pid, 3, 1, b"a")
        + finding_line(pid, 10, 1, b"a")
    )


# ---------------------------------------------------------------------------
# Escaping (OU-AC-08)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,escaped",
    [
        (b" ", b" "),
        (b'"', br"\""),
        (b"\\", br"\\"),
        (b"\t", br"\x09"),
        (b"\n", br"\x0A"),
        (b"\r", br"\x0D"),
        (b"\x00", br"\x00"),
        (b"\x01", br"\x01"),
        (b"\x7f", br"\x7F"),
        (b"\x80", br"\x80"),
        (b"\xff", br"\xFF"),
    ],
)
def test_escape_helper_contract_bytes(raw, escaped):
    assert escape_target(raw) == escaped


def test_seam_escaping_exhaustive_corpus(openunlink_seam_bin, seam_workdir):
    pid = 14
    corpus = bytes(range(256))
    # Keep payload within target cap.
    assert len(corpus) <= TARGET_LEN_CAP
    st = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=len(corpus))
    entry = make_entry("1", first=st, second=st, link=corpus)
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == finding_line(pid, 1, len(corpus), corpus)
    assert_no_raw_unsafe_bytes(result.stdout)


def test_seam_target_length_65536_accepted(openunlink_seam_bin, seam_workdir):
    pid = 15
    payload = b"Z" * TARGET_LEN_CAP
    st = make_stat(dev=1, ino=2, mode=S_IFREG | 0o600, nlink=0, size=TARGET_LEN_CAP)
    entry = make_entry("2", first=st, second=st, link=payload)
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == finding_line(pid, 2, TARGET_LEN_CAP, payload)


def test_seam_target_length_65537_advisory(openunlink_seam_bin, seam_workdir):
    pid = 16
    # link_rc forces 65537-byte result; payload can be shorter in the file.
    payload = b"Y" * 16
    st = make_stat(dev=1, ino=3, mode=S_IFREG | 0o600, nlink=0, size=0)
    entry = make_entry(
        "3", first=st, second=st, link=payload, link_rc=TARGET_LEN_LIMIT
    )
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == b""
    assert result.stderr == advisory_fd("TARGET_LENGTH_LIMIT", pid, 3)
    assert status1_caller_class(result.returncode, result.stdout) == "advisory-only"


# ---------------------------------------------------------------------------
# Descriptor count boundaries SIXTH2-M1 (OU-AC-06)
# ---------------------------------------------------------------------------


def test_seam_fd_count_65536_no_advisory(openunlink_seam_bin, seam_workdir):
    pid = 17
    # First 65536 valid names, last retained is a finding sentinel.
    entries = []
    for i in range(FD_RETAIN_CAP - 1):
        entries.append(_nonzero_link_entry(str(i), ino=1000 + i))
    entries.append(_zero_link_entry(str(FD_RETAIN_CAP - 1), ino=9999, link=b"cap"))
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=entries))
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, timeout=180.0
    )
    assert result.returncode == STATUS_RESULT
    assert result.stderr == b""
    assert result.stdout == finding_line(pid, FD_RETAIN_CAP - 1, 3, b"cap")


def test_seam_fd_count_65537_preserves_retained_finding(openunlink_seam_bin, seam_workdir):
    pid = 18
    # Observed order: high numbers first so first-observed subset != lowest.
    # Retained first 65536 in observed order include sentinel "900000" early,
    # and excluded 65537th is "1" with a distinct finding that must be omitted.
    retained_finding = _zero_link_entry("900000", ino=1, link=b"keep")
    filler = [_nonzero_link_entry(str(100000 + i), ino=2000 + i) for i in range(FD_RETAIN_CAP - 1)]
    excluded = _zero_link_entry("1", ino=3, link=b"omit")
    entries = [retained_finding, *filler, excluded]
    assert len(entries) == FD_LIMIT_TRIGGER
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=entries))
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, timeout=180.0
    )
    assert result.returncode == STATUS_RESULT
    assert result.stderr == advisory_count(pid)
    assert result.stdout == finding_line(pid, 900000, 4, b"keep")
    assert b"omit" not in result.stdout
    assert b"fd=1\t" not in result.stdout
    assert status1_caller_class(result.returncode, result.stdout) == "finding-bearing"


# ---------------------------------------------------------------------------
# Closed errno mappings (OU-AC-07, OU-AC-09)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("err", [errno.ENOENT, errno.ENOTDIR, errno.ESTALE])
def test_seam_first_fstatat_unstable(openunlink_seam_bin, seam_workdir, err):
    pid = 20
    st = make_stat(nlink=0)
    entry = make_entry("4", first=st, second=st, link=b"x", first_rc=-1, first_errno=err)
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == b""
    assert result.stderr == advisory_fd("FD_UNSTABLE", pid, 4)


@pytest.mark.parametrize(
    "err",
    [
        errno.EACCES,
        errno.EPERM,
        errno.EIO,
        errno.ENOMEM,
        errno.EBADF,
    ],
)
def test_seam_first_fstatat_unreadable(openunlink_seam_bin, seam_workdir, err):
    pid = 21
    st = make_stat(nlink=0)
    entry = make_entry("5", first=st, second=st, link=b"x", first_rc=-1, first_errno=err)
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == b""
    assert result.stderr == advisory_fd("FD_UNREADABLE", pid, 5)


@pytest.mark.parametrize(
    "err", [errno.ENOENT, errno.ENOTDIR, errno.ESTALE, errno.EINVAL]
)
def test_seam_readlinkat_unstable(openunlink_seam_bin, seam_workdir, err):
    pid = 22
    st = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=0)
    entry = make_entry(
        "6", first=st, second=st, link=b"", link_rc=-1, link_errno=err
    )
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stderr == advisory_fd("FD_UNSTABLE", pid, 6)


@pytest.mark.parametrize("err", [errno.EACCES, errno.EIO, errno.EPERM])
def test_seam_readlinkat_unreadable(openunlink_seam_bin, seam_workdir, err):
    pid = 23
    st = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=0)
    entry = make_entry(
        "7", first=st, second=st, link=b"", link_rc=-1, link_errno=err
    )
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stderr == advisory_fd("FD_UNREADABLE", pid, 7)


@pytest.mark.parametrize("err", [errno.ENOENT, errno.ENOTDIR, errno.ESTALE])
def test_seam_second_fstatat_unstable(openunlink_seam_bin, seam_workdir, err):
    pid = 24
    st = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=1)
    entry = make_entry(
        "8",
        first=st,
        second=st,
        link=b"z",
        second_rc=-1,
        second_errno=err,
    )
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stderr == advisory_fd("FD_UNSTABLE", pid, 8)


def test_seam_identity_churn_unstable(openunlink_seam_bin, seam_workdir):
    pid = 25
    first = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=1)
    second = make_stat(dev=1, ino=2, mode=S_IFREG | 0o600, nlink=0, size=1)
    entry = make_entry("9", first=first, second=second, link=b"z")
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stderr == advisory_fd("FD_UNSTABLE", pid, 9)


def test_seam_negative_size_range(openunlink_seam_bin, seam_workdir):
    pid = 26
    st = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=-1)
    entry = make_entry("1", first=st, second=st, link=b"z")
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == b""
    assert result.stderr == advisory_fd("FD_SIZE_RANGE", pid, 1)


def test_seam_force_unrepresentable_size_range(openunlink_seam_bin, seam_workdir):
    pid = 27
    st = make_stat(dev=1, ino=1, mode=S_IFREG | 0o600, nlink=0, size=4)
    entry = make_entry("2", first=st, second=st, link=b"abcd")
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[entry], force_size_range=1),
    )
    trace = seam_workdir / "t.txt"
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, trace=trace
    )
    assert result.returncode == STATUS_RESULT
    assert result.stderr == advisory_fd("FD_SIZE_RANGE", pid, 2)
    tr = parse_trace(trace.read_text(encoding="utf-8"))
    assert tr.saw_call("force_size_range")


def test_seam_mixed_finding_and_advisory(openunlink_seam_bin, seam_workdir):
    pid = 28
    good = _zero_link_entry("2", ino=1, link=b"ok")
    bad_st = make_stat(dev=1, ino=2, mode=S_IFREG | 0o600, nlink=0, size=0)
    bad = make_entry(
        "5", first=bad_st, second=bad_st, link=b"", link_rc=-1, link_errno=errno.EIO
    )
    scenario = write_scenario(
        seam_workdir / "s.bin", encode_scenario(entries=[bad, good])
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == finding_line(pid, 2, 2, b"ok")
    assert result.stderr == advisory_fd("FD_UNREADABLE", pid, 5)
    assert status1_caller_class(result.returncode, result.stdout) == "finding-bearing"


# ---------------------------------------------------------------------------
# Process open / scan operational codes (OU-AC-09)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("err", [errno.ENOENT, errno.ENOTDIR])
def test_seam_process_not_found(openunlink_seam_bin, seam_workdir, err):
    pid = 30
    scenario = write_scenario(
        seam_workdir / "s.bin", encode_scenario(open_errno=err, entries=[])
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stdout == b""
    assert result.stderr == diagnostic_pid("PROCESS_NOT_FOUND", pid)


@pytest.mark.parametrize("err", [errno.EACCES, errno.EPERM])
def test_seam_process_access(openunlink_seam_bin, seam_workdir, err):
    pid = 31
    scenario = write_scenario(
        seam_workdir / "s.bin", encode_scenario(open_errno=err, entries=[])
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stderr == diagnostic_pid("PROCESS_ACCESS", pid)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"open_errno": errno.EIO},
        {"dup_errno": errno.EMFILE},
        {"fdopendir_errno": errno.ENOMEM},
        {"closedir_errno": errno.EIO},
        {"readdir_errno": errno.EIO},
    ],
)
def test_seam_process_scan_paths(openunlink_seam_bin, seam_workdir, kwargs):
    pid = 32
    entries = []
    if "readdir_errno" in kwargs:
        entries = [_nonzero_link_entry("1", ino=1)]
    scenario = write_scenario(
        seam_workdir / "s.bin", encode_scenario(entries=entries, **kwargs)
    )
    # For closedir failure after successful enumeration of one linked entry.
    if "closedir_errno" in kwargs:
        scenario = write_scenario(
            seam_workdir / "s.bin",
            encode_scenario(entries=[_nonzero_link_entry("1", ino=1)], **kwargs),
        )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stdout == b""
    assert result.stderr == diagnostic_pid("PROCESS_SCAN", pid)


def test_seam_malformed_entry_process_scan(openunlink_seam_bin, seam_workdir):
    pid = 33
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_nonzero_link_entry("01", ino=1)]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stderr == diagnostic_pid("PROCESS_SCAN", pid)


def test_seam_duplicate_retained_name_process_scan(openunlink_seam_bin, seam_workdir):
    pid = 34
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[
                _nonzero_link_entry("3", ino=1),
                _nonzero_link_entry("3", ino=2),
            ]
        ),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stderr == diagnostic_pid("PROCESS_SCAN", pid)


@pytest.mark.parametrize(
    "bad_name",
    ["", "+", "1x", "x", "00", "01", str(INT_MAX + 1), "999999999999999999999"],
)
def test_seam_bad_descriptor_names_process_scan(
    openunlink_seam_bin, seam_workdir, bad_name
):
    pid = 39
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_nonzero_link_entry(bad_name, ino=1)]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stdout == b""
    assert result.stderr == diagnostic_pid("PROCESS_SCAN", pid)


def test_seam_descriptor_zero_is_valid_name(openunlink_seam_bin, seam_workdir):
    """Descriptor name exactly ``0`` is canonical and retainable."""

    pid = 45
    entry = _zero_link_entry("0", ino=1, link=b"z")
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == finding_line(pid, 0, 1, b"z")


def test_seam_embedded_nul_link_length_authoritative(
    openunlink_seam_bin, seam_workdir
):
    pid = 44
    payload = b"ab\x00cd"
    st = make_stat(dev=1, ino=8, mode=S_IFREG | 0o600, nlink=0, size=5)
    entry = make_entry("6", first=st, second=st, link=payload)
    scenario = write_scenario(seam_workdir / "s.bin", encode_scenario(entries=[entry]))
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_RESULT
    assert result.stdout == finding_line(pid, 6, 5, payload)
    assert b"\\x00" in result.stdout


@pytest.mark.parametrize("which", [1, 2, 3])
def test_seam_malloc_failure(openunlink_seam_bin, seam_workdir, which):
    pid = 35
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[_zero_link_entry("1", ino=1)],
            malloc_fail_call=which,
        ),
    )
    trace = seam_workdir / "t.txt"
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, trace=trace
    )
    assert result.returncode == STATUS_ERROR
    assert result.stdout == b""
    assert result.stderr == diagnostic_global("MEMORY")
    tr = parse_trace(trace.read_text(encoding="utf-8"))
    assert tr.saw_call("malloc")
    assert tr.malloc_count >= which


def test_seam_no_realloc_on_successful_scan(openunlink_seam_bin, seam_workdir):
    pid = 36
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_zero_link_entry("1", ino=1, link=b"x")]),
    )
    trace = seam_workdir / "t.txt"
    result = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=scenario, trace=trace
    )
    assert result.returncode == STATUS_RESULT
    tr = parse_trace(trace.read_text(encoding="utf-8"))
    assert tr.realloc_count == 0
    assert tr.malloc_count == 3


def test_seam_final_close_failure_preserves_findings(openunlink_seam_bin, seam_workdir):
    pid = 37
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[_zero_link_entry("1", ino=1, link=b"x")],
            close_errno=errno.EIO,
        ),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stdout == finding_line(pid, 1, 1, b"x")
    assert result.stderr == diagnostic_pid("PROCESS_SCAN", pid)


def test_seam_first_operational_error_controls(openunlink_seam_bin, seam_workdir):
    pid = 38
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(open_errno=errno.ENOENT, dup_errno=errno.EMFILE, entries=[]),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stderr == diagnostic_pid("PROCESS_NOT_FOUND", pid)
    assert result.stderr.count(b"\n") == 1


# ---------------------------------------------------------------------------
# Stdout / stderr / SIGPIPE (OU-AC-11)
# ---------------------------------------------------------------------------


def test_closed_stdout_help_is_stdout_write_not_sigpipe(openunlink_bin):
    status, stderr = run_with_closed_stdout_pipe(openunlink_bin, "--help")
    assert status == STATUS_ERROR
    assert status != -signal.SIGPIPE
    assert status != 141
    assert stderr == diagnostic_global("STDOUT_WRITE")


def test_closed_stdout_version_is_stdout_write(openunlink_bin):
    status, stderr = run_with_closed_stdout_pipe(openunlink_bin, "--version")
    assert status == STATUS_ERROR
    assert stderr == diagnostic_global("STDOUT_WRITE")


def test_seam_fwrite_failure_stdout_write(openunlink_seam_bin, seam_workdir):
    pid = 40
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[_zero_link_entry("1", ino=1, link=b"x")],
            fwrite_fail_call=1,
        ),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stderr == diagnostic_global("STDOUT_WRITE")


def test_seam_fflush_failure_stdout_write(openunlink_seam_bin, seam_workdir):
    pid = 41
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[_zero_link_entry("1", ino=1, link=b"x")],
            fflush_errno=errno.EIO,
        ),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    assert result.returncode == STATUS_ERROR
    assert result.stderr == diagnostic_global("STDOUT_WRITE")


def test_seam_stderr_failure_does_not_change_status(openunlink_seam_bin, seam_workdir):
    pid = 42
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(
            entries=[
                make_entry(
                    "1",
                    first=make_stat(mode=S_IFREG | 0o600, nlink=0, size=0),
                    second=make_stat(mode=S_IFREG | 0o600, nlink=0, size=0),
                    link=b"",
                    first_rc=-1,
                    first_errno=errno.ENOENT,
                )
            ],
            stderr_errno=errno.EIO,
        ),
    )
    result = run_openunlink(openunlink_seam_bin, str(pid), scenario=scenario)
    # Advisory may be lost; status remains 1 advisory-only.
    assert result.returncode == STATUS_RESULT
    assert result.stdout == b""
    assert b"STDERR_WRITE" not in result.stderr


def test_closed_stderr_pipe_preserves_finding_status(openunlink_seam_bin, seam_workdir):
    pid = 43
    scenario = write_scenario(
        seam_workdir / "s.bin",
        encode_scenario(entries=[_zero_link_entry("1", ino=1, link=b"x")]),
    )
    status, stdout = run_with_closed_stderr_pipe(
        openunlink_seam_bin, str(pid), scenario=scenario
    )
    assert status == STATUS_RESULT
    assert stdout == finding_line(pid, 1, 1, b"x")


# ---------------------------------------------------------------------------
# Positive controls for every injector (OU-AC-01)
# ---------------------------------------------------------------------------


INJECTORS = (
    ("open", {"open_errno": errno.EIO}, "PROCESS_SCAN"),
    ("dup", {"dup_errno": errno.EMFILE}, "PROCESS_SCAN"),
    ("fdopendir", {"fdopendir_errno": errno.ENOMEM}, "PROCESS_SCAN"),
    ("closedir", {"closedir_errno": errno.EIO}, "PROCESS_SCAN"),
    ("close", {"close_errno": errno.EIO}, "PROCESS_SCAN"),
    ("readdir", {"readdir_errno": errno.EIO}, "PROCESS_SCAN"),
    ("malloc", {"malloc_fail_call": 1}, "MEMORY"),
    ("fwrite", {"fwrite_fail_call": 1}, "STDOUT_WRITE"),
    ("fflush", {"fflush_errno": errno.EIO}, "STDOUT_WRITE"),
)


@pytest.mark.parametrize("call_name,inject,code", INJECTORS)
def test_injector_positive_control_paired_success(
    openunlink_seam_bin, seam_workdir, call_name, inject, code
):
    """Each failure injector is paired with a successful control path."""

    pid = 50
    entries = [_zero_link_entry("1", ino=1, link=b"x")]
    # Success control
    ok_scenario = write_scenario(
        seam_workdir / f"{call_name}-ok.bin", encode_scenario(entries=entries)
    )
    ok_trace = seam_workdir / f"{call_name}-ok.trace"
    ok = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=ok_scenario, trace=ok_trace
    )
    assert ok.returncode == STATUS_RESULT
    assert ok.stdout == finding_line(pid, 1, 1, b"x")
    ok_tr = parse_trace(ok_trace.read_text(encoding="utf-8"))
    if call_name == "fwrite":
        assert ok_tr.saw_call("fwrite") or ok_tr.saw_call("fprintf")
    elif call_name == "malloc":
        assert ok_tr.saw_call("malloc")
    elif call_name == "fflush":
        assert ok_tr.saw_call("fflush")
    else:
        assert ok_tr.saw_call(call_name)

    # Failure injection
    fail_entries = entries
    if call_name == "open":
        fail_entries = []
    fail_scenario = write_scenario(
        seam_workdir / f"{call_name}-fail.bin",
        encode_scenario(entries=fail_entries, **inject),
    )
    fail_trace = seam_workdir / f"{call_name}-fail.trace"
    fail = run_openunlink(
        openunlink_seam_bin, str(pid), scenario=fail_scenario, trace=fail_trace
    )
    assert fail.returncode == STATUS_ERROR
    if code in GLOBAL_OPERATIONAL:
        assert fail.stderr == diagnostic_global(code)
    else:
        assert fail.stderr == diagnostic_pid(code, pid)
    # Final-close failure preserves already flushed findings.
    if call_name == "close":
        assert fail.stdout == finding_line(pid, 1, 1, b"x")
    elif call_name != "fflush" and call_name != "fwrite":
        assert fail.stdout == b""
    fail_tr = parse_trace(fail_trace.read_text(encoding="utf-8"))
    if call_name == "fwrite":
        assert fail_tr.saw_call("fwrite") or fail_tr.saw_call("fprintf")
    else:
        assert fail_tr.saw_call(call_name)


def test_positive_control_defective_bypass_detected(seam_workdir):
    """A stub that never calls remapped open fails the open-reachability oracle."""

    install_seam_sources(seam_workdir)
    stub = seam_workdir / "defective.c"
    stub.write_text(
        """
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
int main(void) {
    /* Defective: never opens /proc/PID/fd; prints fake success. */
    return 0;
}
""",
        encoding="utf-8",
    )
    binary = seam_workdir / "defective"
    compiled = subprocess.run(
        ["cc", *STRICT_WARNING_FLAGS, "-o", str(binary), str(stub)],
        capture_output=True,
        check=False,
    )
    assert compiled.returncode == 0
    scenario = write_scenario(
        seam_workdir / "s.bin", encode_scenario(open_errno=errno.EIO, entries=[])
    )
    trace = seam_workdir / "t.txt"
    result = run_openunlink(binary, "1", scenario=scenario, trace=trace)
    # Defective stub returns 0 and writes no trace open call.
    assert result.returncode == 0
    if trace.exists():
        tr = parse_trace(trace.read_text(encoding="utf-8"))
        assert not tr.saw_call("open")
    else:
        tr = Trace()
        assert not tr.saw_call("open")
    # The contract oracle for PROCESS_SCAN injection would fail this stub:
    assert result.stderr != diagnostic_pid("PROCESS_SCAN", 1)


# ---------------------------------------------------------------------------
# Source audits (OU-AC-12, OU-AC-13)
# ---------------------------------------------------------------------------


FORBIDDEN_SOURCE_PATTERNS = (
    (r"\bfork\s*\(", "fork"),
    (r"\bvfork\s*\(", "vfork"),
    (r"\bexecl\s*\(", "execl"),
    (r"\bexecv\s*\(", "execv"),
    (r"\bexecve\s*\(", "execve"),
    (r"\bsystem\s*\(", "system"),
    (r"\bpopen\s*\(", "popen"),
    (r"\bsocket\s*\(", "socket"),
    (r"\bconnect\s*\(", "connect"),
    (r"\bkill\s*\(", "kill"),
    (r"\bptrace\s*\(", "ptrace"),
    (r"\bunlink(?:at)?\s*\(", "unlink"),
    (r"\brename(?:at)?\s*\(", "rename"),
    (r"\bchmod\s*\(", "chmod"),
    (r"\bfchmod\s*\(", "fchmod"),
    (r"\bchown\s*\(", "chown"),
    (r"\bdlopen\s*\(", "dlopen"),
)


def test_source_exists_or_fail_closed():
    if not SRC.is_file():
        pytest.fail(f"{SRC} is missing; openunlink contract suite requires the source")


def test_source_feature_macros_before_headers():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    posix = text.find("_POSIX_C_SOURCE")
    fileoff = text.find("_FILE_OFFSET_BITS")
    first_include = text.find("#include")
    assert posix != -1 and fileoff != -1 and first_include != -1
    assert posix < first_include
    assert fileoff < first_include
    assert "200809L" in text
    assert re.search(r"_FILE_OFFSET_BITS\s+64", text)


def test_source_uses_platform_headers_and_priumax():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    for header in (
        "<dirent.h>",
        "<fcntl.h>",
        "<inttypes.h>",
        "<signal.h>",
        "<stdio.h>",
        "<stdlib.h>",
        "<sys/stat.h>",
        "<unistd.h>",
    ):
        assert header in text, f"missing {header}"
    assert "PRIuMAX" in text
    # No hand-written syscall prototypes.
    assert not re.search(
        r"^\s*(extern\s+)?(int|ssize_t|DIR\s*\*)\s+(open|dup|fdopendir|readdir|"
        r"closedir|fstatat|readlinkat|close)\s*\(",
        text,
        re.MULTILINE,
    )


def test_source_fixed_procfs_path_only():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    assert "/proc/" in text
    assert "fd" in text
    # Must not accept caller-controlled proc root.
    assert "PROC_ROOT" not in text
    assert "getenv" not in text or "OPENUNLINK_TEST" in text
    # Production path construction should use fixed "/proc/" literal.
    assert '"/proc/' in text or '"/proc/"' in text


def test_source_no_content_no_control_surface():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    for pattern, label in FORBIDDEN_SOURCE_PATTERNS:
        assert re.search(pattern, text) is None, f"forbidden call surface: {label}"
    # Target content must not be opened: only directory open of /proc/PID/fd.
    # Allow open( for the process directory; forbid openat on targets for reading.
    assert "O_RDWR" not in text
    assert "O_WRONLY" not in text


def test_source_unsigned_byte_escaping_no_signed_ctype():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    assert "isprint" not in text
    assert "isalnum" not in text
    assert "isdigit" not in text
    assert "<ctype.h>" not in text


def test_source_seam_guard_present():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    assert "OPENUNLINK_TEST_SEAM" in text
    assert "openunlink_test_seam.h" in text
    assert "openunlink_test_force_size_range" in text


def test_production_compile_supplies_platform_cflags(openunlink_bin):
    if not _LAST_OPENUNLINK_COMPILE_ARGV:
        # Override path — still require source-level macros.
        _require_source()
        return
    argv = _LAST_OPENUNLINK_COMPILE_ARGV
    for flag in PLATFORM_CFLAGS:
        assert flag in argv
    assert SEAM_MACRO not in argv


def test_source_char_bit_and_off_t_assertions():
    _require_source()
    text = SRC.read_text(encoding="utf-8")
    assert "CHAR_BIT" in text
    assert "sizeof(off_t)" in text or "off_t" in text
    assert "static_assert" in text or "_Static_assert" in text


# ---------------------------------------------------------------------------
# Documentation / Makefile structural oracles (OU-AC-15, OU-AC-16)
# ---------------------------------------------------------------------------


def test_makefile_openunlink_targets_and_flags():
    text = MAKEFILE.read_text(encoding="utf-8")
    for token in (
        "OPENUNLINK_SRC",
        "OPENUNLINK_MANPAGE",
        "OPENUNLINK_PLATFORM_CFLAGS",
        "openunlink-test",
        "openunlink-sanitize",
        "openunlink-valgrind",
    ):
        assert token in text, f"Makefile missing {token}"
    assert "src/openunlink.c" in text
    assert "man/openunlink.1" in text
    assert "_POSIX_C_SOURCE=200809L" in text
    assert "_FILE_OFFSET_BITS=64" in text
    assert "tests/test_openunlink.py" in text
    # Ordinary test-suite must scrub openunlink overrides.
    assert "OPENUNLINK_BIN" in text
    assert "OPENUNLINK_UNDER_VALGRIND" in text
    # Non-writing focused targets use /tmp.
    assert "/tmp/openunlink" in text or "openunlink-build" in text or "mktemp" in text


def test_makefile_openunlink_is_phony_and_non_installing():
    text = MAKEFILE.read_text(encoding="utf-8")
    phony = re.search(r"^\.PHONY:\s*(.+)$", text, re.MULTILINE)
    assert phony is not None
    phony_line = phony.group(1)
    for target in (
        "openunlink",
        "openunlink-test",
        "openunlink-sanitize",
        "openunlink-valgrind",
    ):
        assert target in phony_line or target in text
    # install remains sysdiff-only.
    install = re.search(r"^install:.*(?:\n(?:\t.*|\s*$.*))+", text, re.MULTILINE)
    assert install is not None
    assert "openunlink" not in install.group(0)


def test_documentation_status0_nfs_disclaimer():
    missing = [p for p in (MANPAGE, DOCS_OPENUNLINK, README) if not p.is_file()]
    if missing:
        pytest.fail(
            "openunlink documentation missing (DOCUMENT phase required): "
            + ", ".join(str(p) for p in missing)
        )
    for path in (MANPAGE, DOCS_OPENUNLINK, README):
        text = path.read_text(encoding="utf-8")
        assert "silly-rename" in text or "silly rename" in text.lower() or "NFS" in text
        assert "st_nlink" in text or "nlink" in text.lower() or "link count" in text.lower()


def test_contract_authority_file_present():
    assert CONTRACT.is_file()
    text = CONTRACT.read_text(encoding="utf-8")
    assert "OPEN_UNLINKED" in text
    assert "FD_COUNT_LIMIT" in text
    assert "65536" in text
    assert "65537" in text
