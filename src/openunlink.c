/*
 * openunlink — report zero-link regular-file descriptors for one Linux PID.
 *
 * Contract: docs/sixth-utility-capability-contract.md
 *
 * Ownership and allocation (scan path):
 * - argv and its strings are borrowed for the process lifetime; never modified
 *   or freed.
 * - The original process-directory descriptor (dir_fd) is owned by the scanner
 *   and closed exactly once.
 * - Before a successful fdopendir, the duplicate (dup_fd) is scanner-owned;
 *   after success, DIR * exclusively owns it and closedir is its only close.
 *   A failed fdopendir leaves the duplicate with the scanner for cleanup.
 * - Each readdir name is borrowed only until the next directory operation; only
 *   the parsed numeric value is retained.
 * - No descriptor target is opened; the scanner never owns a target-content
 *   descriptor.
 * - Exactly three heap allocations: a 65536-element descriptor-number array,
 *   a 65537-byte reusable link-text buffer, and one reusable finding-line
 *   buffer. Each has one owner and one cleanup site. No realloc or
 *   per-finding allocation.
 */

#ifndef _POSIX_C_SOURCE
/* NOLINTNEXTLINE(bugprone-reserved-identifier) */
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef _FILE_OFFSET_BITS
/* NOLINTNEXTLINE(bugprone-reserved-identifier) */
#define _FILE_OFFSET_BITS 64
#endif

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#ifdef OPENUNLINK_TEST_SEAM
/* cppcheck-suppress missingInclude */
#include "openunlink_test_seam.h"
#endif

#if CHAR_BIT != 8
#error "openunlink requires CHAR_BIT == 8"
#endif

_Static_assert(CHAR_BIT == 8, "openunlink requires eight-bit bytes");
_Static_assert(sizeof(off_t) >= 8, "openunlink requires at least 64-bit off_t");
_Static_assert(sizeof(uintmax_t) >= sizeof(off_t),
               "uintmax_t must hold nonnegative off_t values");

enum { FD_RETAIN_CAP = 65536, TARGET_LEN_CAP = 65536, TARGET_BUF_SIZE = 65537 };

/* Digit bounds without terminator; see contract size_t arithmetic rules. */
#define INT_DECIMAL_BOUND (3u * sizeof(int))
#define UINTMAX_DECIMAL_BOUND (3u * sizeof(uintmax_t))

static const char HELP_TEXT[] =
    "Usage: openunlink PID\n"
    "       openunlink --help\n"
    "       openunlink --version\n"
    "Report zero-link regular-file descriptors for one Linux process.\n";

static const char VERSION_TEXT[] = "openunlink 0.1.0\n";

enum OpCode {
  OP_NONE = 0,
  OP_USAGE,
  OP_PROCESS_NOT_FOUND,
  OP_PROCESS_ACCESS,
  OP_PROCESS_SCAN,
  OP_MEMORY,
  OP_STDOUT_WRITE
};

struct ScanState {
  int pid;
  int dir_fd;     /* original /proc/PID/fd; -1 when closed or not opened */
  int dup_fd;     /* scanner-owned duplicate; -1 when transferred or unused */
  DIR *dir;       /* owns transferred duplicate when non-NULL */
  int *fds;       /* owned 65536-element array, or NULL */
  char *link_buf; /* owned 65537-byte sentinel buffer, or NULL */
  char *line_buf; /* owned finding-line buffer, or NULL */
  size_t line_cap;
  size_t fd_count;
  int fd_count_limit; /* true when 65537th valid entry observed */
  int had_finding;
  int had_advisory;
  enum OpCode op;
};

static int size_add(size_t a, size_t b, size_t *out) {
  if (a > SIZE_MAX - b) {
    return -1;
  }
  *out = a + b;
  return 0;
}

static int size_mul(size_t a, size_t b, size_t *out) {
  if (a != 0 && b > SIZE_MAX / a) {
    return -1;
  }
  *out = a * b;
  return 0;
}

static size_t finding_line_capacity(void) {
  /*
   * "OPEN_UNLINKED\tpid=\tfd=\tsize=\ttarget=\"\"\n"
   * + two INT_DECIMAL_BOUND fields + one UINTMAX_DECIMAL_BOUND field
   * + four output bytes per of 65536 target bytes + NUL.
   */
  static const char fixed[] = "OPEN_UNLINKED\tpid=\tfd=\tsize=\ttarget=\"\"\n";
  size_t cap = sizeof(fixed) - 1u; /* exclude compile-time NUL in literal */
  size_t tmp;

  if (size_add(cap, INT_DECIMAL_BOUND, &tmp) != 0) {
    return 0;
  }
  cap = tmp;
  if (size_add(cap, INT_DECIMAL_BOUND, &tmp) != 0) {
    return 0;
  }
  cap = tmp;
  if (size_add(cap, UINTMAX_DECIMAL_BOUND, &tmp) != 0) {
    return 0;
  }
  cap = tmp;
  if (size_mul((size_t)TARGET_LEN_CAP, 4u, &tmp) != 0) {
    return 0;
  }
  if (size_add(cap, tmp, &tmp) != 0) {
    return 0;
  }
  cap = tmp;
  if (size_add(cap, 1u, &tmp) != 0) { /* terminating NUL */
    return 0;
  }
  return tmp;
}

static size_t process_path_capacity(void) {
  /* Bytes in "/proc//fd" plus INT_DECIMAL_BOUND digits plus one NUL. */
  static const char fixed[] = "/proc//fd";
  size_t cap = sizeof(fixed) - 1u;
  size_t tmp;

  if (size_add(cap, INT_DECIMAL_BOUND, &tmp) != 0) {
    return 0;
  }
  if (size_add(tmp, 1u, &tmp) != 0) {
    return 0;
  }
  return tmp;
}

static void ignore_sigpipe(void) { (void)signal(SIGPIPE, SIG_IGN); }

static void set_op(struct ScanState *st, enum OpCode code) {
  if (st->op == OP_NONE) {
    st->op = code;
  }
}

static const char *op_name(enum OpCode code) {
  switch (code) {
  case OP_USAGE:
    return "USAGE";
  case OP_PROCESS_NOT_FOUND:
    return "PROCESS_NOT_FOUND";
  case OP_PROCESS_ACCESS:
    return "PROCESS_ACCESS";
  case OP_PROCESS_SCAN:
    return "PROCESS_SCAN";
  case OP_MEMORY:
    return "MEMORY";
  case OP_STDOUT_WRITE:
    return "STDOUT_WRITE";
  case OP_NONE:
  default:
    return NULL;
  }
}

static int is_pid_owned_op(enum OpCode code) {
  return code == OP_PROCESS_NOT_FOUND || code == OP_PROCESS_ACCESS ||
         code == OP_PROCESS_SCAN;
}

static void emit_operational(const struct ScanState *st) {
  const char *name;

  if (st->op == OP_NONE) {
    return;
  }
  name = op_name(st->op);
  if (name == NULL) {
    return;
  }
  if (is_pid_owned_op(st->op)) {
    (void)fprintf(stderr, "openunlink: %s: pid=%d\n", name, st->pid);
  } else {
    (void)fprintf(stderr, "openunlink: %s\n", name);
  }
}

static void emit_usage(void) { (void)fprintf(stderr, "openunlink: USAGE\n"); }

static void emit_fd_advisory(struct ScanState *st, const char *code, int fd) {
  (void)fprintf(stderr, "openunlink: %s: pid=%d fd=%d\n", code, st->pid, fd);
  st->had_advisory = 1;
}

static void emit_count_advisory(struct ScanState *st) {
  (void)fprintf(stderr, "openunlink: FD_COUNT_LIMIT: pid=%d\n", st->pid);
  st->had_advisory = 1;
}

static int write_stdout_bytes(const void *buf, size_t len) {
  if (len == 0u) {
    return 0;
  }
  if (fwrite(buf, 1, len, stdout) != len) {
    return -1;
  }
  return 0;
}

static int parse_canonical_int(const char *text, int allow_zero, int *out) {
  const unsigned char *p;
  unsigned long acc;
  int digits;

  if (text == NULL || text[0] == '\0') {
    return -1;
  }
  p = (const unsigned char *)text;
  if (p[0] == (unsigned char)'0') {
    if (!allow_zero || p[1] != '\0') {
      return -1;
    }
    *out = 0;
    return 0;
  }
  if (p[0] < (unsigned char)'1' || p[0] > (unsigned char)'9') {
    return -1;
  }
  acc = 0ul;
  digits = 0;
  for (; *p != '\0'; p++) {
    unsigned char ch = *p;
    unsigned digit;

    if (ch < (unsigned char)'0' || ch > (unsigned char)'9') {
      return -1;
    }
    digit = (unsigned)(ch - (unsigned char)'0');
    if (acc > (unsigned long)INT_MAX / 10ul) {
      return -1;
    }
    acc = acc * 10ul + (unsigned long)digit;
    if (acc > (unsigned long)INT_MAX) {
      return -1;
    }
    digits++;
    if (digits > (int)INT_DECIMAL_BOUND) {
      return -1;
    }
  }
  if (acc < 1ul) {
    return -1;
  }
  *out = (int)acc;
  return 0;
}

static int parse_pid(const char *text, int *out) {
  return parse_canonical_int(text, 0, out);
}

static int parse_fd_name(const char *text, int *out) {
  return parse_canonical_int(text, 1, out);
}

static int fd_cmp(const void *a, const void *b) {
  const int ia = *(const int *)a;
  const int ib = *(const int *)b;

  if (ia < ib) {
    return -1;
  }
  if (ia > ib) {
    return 1;
  }
  return 0;
}

static int format_fd_name(char *buf, size_t cap, int fd) {
  int n = snprintf(buf, cap, "%d", fd);

  if (n < 0 || (size_t)n >= cap) {
    return -1;
  }
  return 0;
}

static int escape_append(char *dst, size_t cap, size_t *used,
                         const unsigned char *src, size_t len) {
  size_t i;

  for (i = 0; i < len; i++) {
    unsigned char ch = src[i];
    size_t need;
    size_t pos = *used;

    if (ch == (unsigned char)'"' || ch == (unsigned char)'\\') {
      need = 2u;
      if (pos > cap || need > cap - pos) {
        return -1;
      }
      dst[pos] = '\\';
      dst[pos + 1u] = (char)ch;
      *used = pos + need;
    } else if (ch >= 0x20u && ch <= 0x7eu) {
      need = 1u;
      if (pos > cap || need > cap - pos) {
        return -1;
      }
      dst[pos] = (char)ch;
      *used = pos + need;
    } else {
      need = 4u;
      if (pos > cap || need > cap - pos) {
        return -1;
      }
      if (snprintf(dst + pos, cap - pos, "\\x%02X", (unsigned)ch) != 4) {
        return -1;
      }
      *used = pos + need;
    }
  }
  return 0;
}

static int emit_finding(struct ScanState *st, int fd, uintmax_t size,
                        const unsigned char *target, size_t target_len) {
  size_t used = 0;
  int n;
  size_t remain;

  if (st->line_buf == NULL || st->line_cap == 0u) {
    return -1;
  }
  n = snprintf(st->line_buf, st->line_cap,
               "OPEN_UNLINKED\tpid=%d\tfd=%d\tsize=%" PRIuMAX "\ttarget=\"",
               st->pid, fd, size);
  if (n < 0 || (size_t)n >= st->line_cap) {
    return -1;
  }
  used = (size_t)n;
  if (escape_append(st->line_buf, st->line_cap, &used, target, target_len) !=
      0) {
    return -1;
  }
  remain = st->line_cap - used;
  if (remain < 3u) { /* "\"\n" + NUL */
    return -1;
  }
  st->line_buf[used++] = '"';
  st->line_buf[used++] = '\n';
  st->line_buf[used] = '\0';
  if (write_stdout_bytes(st->line_buf, used) != 0) {
    return -1;
  }
  st->had_finding = 1;
  return 0;
}

static int map_fstatat_errno(int err) {
  return (err == ENOENT || err == ENOTDIR || err == ESTALE) ? 1 : 0;
}

static int map_readlinkat_errno(int err) {
  return (err == ENOENT || err == ENOTDIR || err == ESTALE || err == EINVAL)
             ? 1
             : 0;
}

static int convert_size(off_t value, uintmax_t *out) {
  uintmax_t converted;

  if (value < 0) {
    return -1;
  }
#ifdef OPENUNLINK_TEST_SEAM
  if (openunlink_test_force_size_range() != 0) {
    return -1;
  }
#endif
  converted = (uintmax_t)value;
  if ((off_t)converted != value) {
    return -1;
  }
  *out = converted;
  return 0;
}

static int inspect_one(struct ScanState *st, int fd) {
  char name[INT_DECIMAL_BOUND + 1u];
  struct stat first;
  struct stat second;
  ssize_t link_rc;
  int saved;
  uintmax_t size;

  if (format_fd_name(name, sizeof(name), fd) != 0) {
    set_op(st, OP_PROCESS_SCAN);
    return -1;
  }

  errno = 0;
  if (fstatat(st->dir_fd, name, &first, 0) != 0) {
    saved = errno;
    if (map_fstatat_errno(saved)) {
      emit_fd_advisory(st, "FD_UNSTABLE", fd);
    } else {
      emit_fd_advisory(st, "FD_UNREADABLE", fd);
    }
    return 0;
  }

  if (!S_ISREG(first.st_mode)) {
    return 0;
  }

  errno = 0;
  link_rc = readlinkat(st->dir_fd, name, st->link_buf, (size_t)TARGET_BUF_SIZE);
  if (link_rc < 0) {
    saved = errno;
    if (map_readlinkat_errno(saved)) {
      emit_fd_advisory(st, "FD_UNSTABLE", fd);
    } else {
      emit_fd_advisory(st, "FD_UNREADABLE", fd);
    }
    return 0;
  }
  if (link_rc == (ssize_t)TARGET_BUF_SIZE) {
    emit_fd_advisory(st, "TARGET_LENGTH_LIMIT", fd);
    return 0;
  }
  if ((size_t)link_rc > (size_t)TARGET_LEN_CAP) {
    emit_fd_advisory(st, "TARGET_LENGTH_LIMIT", fd);
    return 0;
  }

  errno = 0;
  if (fstatat(st->dir_fd, name, &second, 0) != 0) {
    saved = errno;
    if (map_fstatat_errno(saved)) {
      emit_fd_advisory(st, "FD_UNSTABLE", fd);
    } else {
      emit_fd_advisory(st, "FD_UNREADABLE", fd);
    }
    return 0;
  }

  if (first.st_dev != second.st_dev || first.st_ino != second.st_ino ||
      !S_ISREG(second.st_mode)) {
    emit_fd_advisory(st, "FD_UNSTABLE", fd);
    return 0;
  }

  if (second.st_nlink != 0) {
    return 0;
  }

  /*
   * Finding size= is the final followed st_size (contract BYTES), never the
   * readlinkat byte count. Link text is escaped display context only.
   */
  if (convert_size(second.st_size, &size) != 0) {
    emit_fd_advisory(st, "FD_SIZE_RANGE", fd);
    return 0;
  }

  if (emit_finding(st, fd, size, (const unsigned char *)st->link_buf,
                   (size_t)link_rc) != 0) {
    set_op(st, OP_STDOUT_WRITE);
    return -1;
  }
  return 0;
}

static void cleanup_scan(struct ScanState *st) {
  if (st->dir != NULL) {
    /* DIR * owns the duplicate; closedir is the only close even on failure. */
    (void)closedir(st->dir);
    st->dir = NULL;
    st->dup_fd = -1;
  }
  if (st->dup_fd >= 0) {
    (void)close(st->dup_fd);
    st->dup_fd = -1;
  }
  if (st->dir_fd >= 0) {
    (void)close(st->dir_fd);
    st->dir_fd = -1;
  }
  if (st->fds != NULL) {
    free(st->fds);
    st->fds = NULL;
  }
  if (st->link_buf != NULL) {
    free(st->link_buf);
    st->link_buf = NULL;
  }
  if (st->line_buf != NULL) {
    free(st->line_buf);
    st->line_buf = NULL;
  }
}

static int allocate_scan_buffers(struct ScanState *st) {
  size_t fds_bytes;
  size_t line_cap;

  if (size_mul((size_t)FD_RETAIN_CAP, sizeof(int), &fds_bytes) != 0) {
    set_op(st, OP_MEMORY);
    return -1;
  }
  line_cap = finding_line_capacity();
  if (line_cap == 0u) {
    set_op(st, OP_MEMORY);
    return -1;
  }
  st->line_cap = line_cap;

  st->fds = (int *)malloc(fds_bytes);
  if (st->fds == NULL) {
    set_op(st, OP_MEMORY);
    return -1;
  }
  memset(st->fds, 0, fds_bytes);
  st->link_buf = (char *)malloc((size_t)TARGET_BUF_SIZE);
  if (st->link_buf == NULL) {
    set_op(st, OP_MEMORY);
    return -1;
  }
  st->line_buf = (char *)malloc(line_cap);
  if (st->line_buf == NULL) {
    set_op(st, OP_MEMORY);
    return -1;
  }
  return 0;
}

static int enumerate_fds(struct ScanState *st) {
  for (;;) {
    struct dirent *ent;
    int fd;
    const char *name;

    errno = 0;
    ent = readdir(st->dir);
    if (ent == NULL) {
      if (errno != 0) {
        set_op(st, OP_PROCESS_SCAN);
        return -1;
      }
      break;
    }
    name = ent->d_name;
    if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
      continue;
    }
    if (parse_fd_name(name, &fd) != 0) {
      set_op(st, OP_PROCESS_SCAN);
      return -1;
    }
    if (st->fd_count >= (size_t)FD_RETAIN_CAP) {
      st->fd_count_limit = 1;
      break;
    }
    st->fds[st->fd_count++] = fd;
  }
  return 0;
}

static int sort_and_check_duplicates(struct ScanState *st) {
  size_t i;

  if (st->fd_count > 1u) {
    qsort(st->fds, st->fd_count, sizeof(st->fds[0]), fd_cmp);
  }
  for (i = 1u; i < st->fd_count; i++) {
    if (st->fds[i] == st->fds[i - 1u]) {
      set_op(st, OP_PROCESS_SCAN);
      return -1;
    }
  }
  return 0;
}

static int run_scan(struct ScanState *st) {
  /*
   * Fixed stack buffer covers "/proc/" + INT_DECIMAL_BOUND + "/fd" + NUL.
   * Derived capacity is checked so a surprising int width fails closed.
   */
  char path_buf[sizeof("/proc/") + INT_DECIMAL_BOUND + sizeof("/fd")];
  size_t path_cap;
  int npath;
  int open_rc;
  int saved;
  size_t i;

  path_cap = process_path_capacity();
  if (path_cap == 0u || path_cap > sizeof(path_buf)) {
    set_op(st, OP_PROCESS_SCAN);
    return -1;
  }
  npath = snprintf(path_buf, path_cap, "/proc/%d/fd", st->pid);
  if (npath < 0 || (size_t)npath >= path_cap) {
    set_op(st, OP_PROCESS_SCAN);
    return -1;
  }

  errno = 0;
  open_rc = open(path_buf, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (open_rc < 0) {
    saved = errno;
    if (saved == ENOENT || saved == ENOTDIR) {
      set_op(st, OP_PROCESS_NOT_FOUND);
    } else if (saved == EACCES || saved == EPERM) {
      set_op(st, OP_PROCESS_ACCESS);
    } else {
      set_op(st, OP_PROCESS_SCAN);
    }
    return -1;
  }
  st->dir_fd = open_rc;

  errno = 0;
  st->dup_fd = dup(st->dir_fd);
  if (st->dup_fd < 0) {
    set_op(st, OP_PROCESS_SCAN);
    return -1;
  }

  if (allocate_scan_buffers(st) != 0) {
    return -1;
  }

  errno = 0;
  st->dir = fdopendir(st->dup_fd);
  if (st->dir == NULL) {
    set_op(st, OP_PROCESS_SCAN);
    return -1;
  }
  /* Ownership of dup_fd transferred to DIR *. */
  st->dup_fd = -1;

  if (enumerate_fds(st) != 0) {
    return -1;
  }

  errno = 0;
  if (closedir(st->dir) != 0) {
    saved = errno;
    st->dir = NULL;
    set_op(st, OP_PROCESS_SCAN);
    (void)saved;
    return -1;
  }
  st->dir = NULL;

  if (sort_and_check_duplicates(st) != 0) {
    return -1;
  }

  if (st->fd_count_limit) {
    emit_count_advisory(st);
  }

  for (i = 0; i < st->fd_count; i++) {
    if (inspect_one(st, st->fds[i]) != 0) {
      return -1;
    }
  }

  if (fflush(stdout) != 0 || ferror(stdout)) {
    set_op(st, OP_STDOUT_WRITE);
    return -1;
  }

  errno = 0;
  if (close(st->dir_fd) != 0) {
    saved = errno;
    st->dir_fd = -1;
    set_op(st, OP_PROCESS_SCAN);
    (void)saved;
    return -1;
  }
  st->dir_fd = -1;
  return 0;
}

static int finish_status(const struct ScanState *st) {
  if (st->op != OP_NONE) {
    return 2;
  }
  if (st->had_finding || st->had_advisory) {
    return 1;
  }
  return 0;
}

static int handle_help(void) {
  ignore_sigpipe();
  if (write_stdout_bytes(HELP_TEXT, sizeof(HELP_TEXT) - 1u) != 0) {
    (void)fprintf(stderr, "openunlink: STDOUT_WRITE\n");
    return 2;
  }
  if (fflush(stdout) != 0 || ferror(stdout)) {
    (void)fprintf(stderr, "openunlink: STDOUT_WRITE\n");
    return 2;
  }
  return 0;
}

static int handle_version(void) {
  ignore_sigpipe();
  if (write_stdout_bytes(VERSION_TEXT, sizeof(VERSION_TEXT) - 1u) != 0) {
    (void)fprintf(stderr, "openunlink: STDOUT_WRITE\n");
    return 2;
  }
  if (fflush(stdout) != 0 || ferror(stdout)) {
    (void)fprintf(stderr, "openunlink: STDOUT_WRITE\n");
    return 2;
  }
  return 0;
}

int main(int argc, char **argv) {
  struct ScanState st;
  int status;

  memset(&st, 0, sizeof(st));
  st.dir_fd = -1;
  st.dup_fd = -1;

  if (argc == 2 && strcmp(argv[1], "--help") == 0) {
    return handle_help();
  }
  if (argc == 2 && strcmp(argv[1], "--version") == 0) {
    return handle_version();
  }
  if (argc != 2 || parse_pid(argv[1], &st.pid) != 0) {
    emit_usage();
    return 2;
  }

  ignore_sigpipe();
  (void)run_scan(&st);
  status = finish_status(&st);
  emit_operational(&st);
  cleanup_scan(&st);
  return status;
}
