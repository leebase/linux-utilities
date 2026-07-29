#include <errno.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

/*
 * lstat(2) is POSIX. Declare it explicitly instead of enabling a feature-test
 * macro: under -std=c17 those macros trip clang-tidy's
 * bugprone-reserved-identifier check (same pattern as pathaudit).
 */
int lstat(const char *path, struct stat *buf);

/* Closed bootstrap taxonomy bits in fixed emission rank. */
#define HAZARD_GROUP_WRITABLE (1u << 0)
#define HAZARD_OTHER_WRITABLE (1u << 1)
#define HAZARD_SET_USER_ID (1u << 2)
#define HAZARD_SET_GROUP_ID (1u << 3)

static const char *const HAZARD_NAMES[] = {
    "GROUP_WRITABLE",
    "OTHER_WRITABLE",
    "SET_USER_ID",
    "SET_GROUP_ID",
};

static const char USAGE_SYNOPSIS[] = "usage: permguard [--] PATH...\n";
static const char HELP_TEXT[] =
    "usage: permguard [--] PATH...\n"
    "Inspect explicitly supplied paths without following symbolic links.\n";
static const char VERSION_TEXT[] = "permguard 0.1.0\n";

static int fputc_checked(int ch, FILE *stream) {
  return fputc(ch, stream) == EOF ? -1 : 0;
}

static int fputs_checked(const char *text, FILE *stream) {
  return fputs(text, stream) == EOF ? -1 : 0;
}

/*
 * Shared quoted-byte writer for stdout findings and stderr diagnostics.
 * Printable ASCII is literal except escaped quote and backslash; every other
 * byte becomes uppercase \xHH.
 */
static int put_escaped_quoted(FILE *stream, const char *text) {
  if (fputc_checked('"', stream) != 0) {
    return -1;
  }

  for (const unsigned char *p = (const unsigned char *)text; *p != '\0'; p++) {
    unsigned char ch = *p;
    if (ch == '"') {
      if (fputs_checked("\\\"", stream) != 0) {
        return -1;
      }
    } else if (ch == '\\') {
      if (fputs_checked("\\\\", stream) != 0) {
        return -1;
      }
    } else if (ch >= 0x20U && ch <= 0x7eU) {
      if (fputc_checked((int)ch, stream) != 0) {
        return -1;
      }
    } else if (fprintf(stream, "\\x%02X", (unsigned int)ch) < 0) {
      return -1;
    }
  }

  return fputc_checked('"', stream);
}

static int emit_stdout_write_error(void) {
  (void)fputs_checked("permguard: STDOUT_WRITE\n", stderr);
  return 2;
}

static int complete_stdout(int status) {
  if (fflush(stdout) != 0 || ferror(stdout)) {
    return emit_stdout_write_error();
  }
  return status;
}

static void emit_diag_reason(const char *reason) {
  (void)fprintf(stderr, "permguard: %s\n", reason);
}

static void emit_diag_reason_path(const char *reason, const char *path) {
  (void)fprintf(stderr, "permguard: %s: ", reason);
  (void)put_escaped_quoted(stderr, path);
  (void)fputc_checked('\n', stderr);
}

static void emit_usage_diag(void) {
  emit_diag_reason("USAGE");
  (void)fputs_checked(USAGE_SYNOPSIS, stderr);
}

static void emit_unknown_option(const char *option) {
  emit_diag_reason_path("UNKNOWN_OPTION", option);
  (void)fputs_checked(USAGE_SYNOPSIS, stderr);
}

static int handle_help(void) {
  if (fputs_checked(HELP_TEXT, stdout) != 0) {
    return emit_stdout_write_error();
  }
  return complete_stdout(0);
}

static int handle_version(void) {
  if (fputs_checked(VERSION_TEXT, stdout) != 0) {
    return emit_stdout_write_error();
  }
  return complete_stdout(0);
}

/*
 * Ignore SIGPIPE so a closed stdout pipe becomes a checked stdio failure
 * rather than asynchronous signal death.
 */
static void ignore_sigpipe_for_stdout(void) { (void)signal(SIGPIPE, SIG_IGN); }

/* Four independent predicates; no file-type heuristics. */
static unsigned classify_mode(mode_t mode) {
  unsigned mask = 0;
  if ((mode & (mode_t)S_IWGRP) != 0) {
    mask |= HAZARD_GROUP_WRITABLE;
  }
  if ((mode & (mode_t)S_IWOTH) != 0) {
    mask |= HAZARD_OTHER_WRITABLE;
  }
  if ((mode & (mode_t)S_ISUID) != 0) {
    mask |= HAZARD_SET_USER_ID;
  }
  if ((mode & (mode_t)S_ISGID) != 0) {
    mask |= HAZARD_SET_GROUP_ID;
  }
  return mask;
}

static int emit_finding(const char *code, const char *path) {
  if (fputs_checked(code, stdout) != 0) {
    return -1;
  }
  if (fputc_checked('\t', stdout) != 0) {
    return -1;
  }
  if (put_escaped_quoted(stdout, path) != 0) {
    return -1;
  }
  return fputc_checked('\n', stdout);
}

static int emit_findings_for_mask(unsigned mask, const char *path) {
  for (unsigned bit = 0; bit < 4U; bit++) {
    if ((mask & (1u << bit)) == 0) {
      continue;
    }
    if (emit_finding(HAZARD_NAMES[bit], path) != 0) {
      return -1;
    }
  }
  return 0;
}

static void emit_inspection_error(const char *path, int saved_errno) {
  char reason[64]; /* fixed diagnostic buffer; automatic storage */
  int n = snprintf(reason, sizeof(reason), "INSPECTION_ERROR_%d", saved_errno);
  if (n < 0 || (size_t)n >= sizeof(reason)) {
    emit_diag_reason_path("INSPECTION_ERROR_0", path);
  } else {
    emit_diag_reason_path(reason, path);
  }
}

static void emit_lstat_failure(const char *path, int saved_errno) {
  /*
   * An empty operand is not a named missing path. Pin it as
   * INSPECTION_ERROR_N even when the host lstat reports ENOENT, so it stays
   * distinct from a non-empty path that truly is absent.
   */
  if (path[0] == '\0') {
    emit_inspection_error(path, saved_errno);
    return;
  }
  if (saved_errno == ENOENT) {
    emit_diag_reason_path("MISSING", path);
    return;
  }
  if (saved_errno == EACCES) {
    emit_diag_reason_path("INACCESSIBLE", path);
    return;
  }
  emit_inspection_error(path, saved_errno);
}

/*
 * One lstat per operand. Continue after operational errors. Findings for
 * successful non-link operands emit immediately in operand and taxonomy order.
 * paths[] entries are borrowed argv pointers and are never freed or modified.
 */
static int run_scan(char **paths, size_t path_count) {
  bool any_hazard = false;
  bool operational_error = false;

  for (size_t i = 0; i < path_count; i++) {
    const char *path = paths[i];
    struct stat st; /* automatic storage; never escapes */
    if (lstat(path, &st) != 0) {
      int saved_errno = errno;
      emit_lstat_failure(path, saved_errno);
      operational_error = true;
      continue;
    }

    if (S_ISLNK(st.st_mode)) {
      emit_diag_reason_path("SYMBOLIC_LINK", path);
      operational_error = true;
      continue;
    }

    unsigned mask = classify_mode(st.st_mode);
    if (mask == 0) {
      continue;
    }
    if (emit_findings_for_mask(mask, path) != 0) {
      return emit_stdout_write_error();
    }
    any_hazard = true;
  }

  if (operational_error) {
    return complete_stdout(2);
  }
  return complete_stdout(any_hazard ? 1 : 0);
}

static int run_operands(int argc, char **argv, int argi, bool end_of_options) {
  if (argi >= argc) {
    emit_usage_diag();
    return 2;
  }

  if (!end_of_options) {
    for (int i = argi; i < argc; i++) {
      if (argv[i][0] == '-') {
        emit_unknown_option(argv[i]);
        return 2;
      }
    }
  }

  return run_scan(argv + argi, (size_t)(argc - argi));
}

int main(int argc, char **argv) {
  if (argc < 1) {
    emit_usage_diag();
    return 2;
  }

  ignore_sigpipe_for_stdout();

  if (argc >= 2 && strcmp(argv[1], "--help") == 0) {
    if (argc != 2) {
      emit_usage_diag();
      return 2;
    }
    return handle_help();
  }

  if (argc >= 2 && strcmp(argv[1], "--version") == 0) {
    if (argc != 2) {
      emit_usage_diag();
      return 2;
    }
    return handle_version();
  }

  int argi = 1;
  bool end_of_options = false;
  if (argi < argc && strcmp(argv[argi], "--") == 0) {
    end_of_options = true;
    argi++;
  }

  return run_operands(argc, argv, argi, end_of_options);
}
