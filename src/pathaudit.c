#include <errno.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define PATHAUDIT_MAX_ROOT_COUNT ((size_t)65536)
#define PATHAUDIT_MAX_ROOT_LENGTH ((size_t)65536)
#define PATHAUDIT_MAX_ROOT_BYTES ((size_t)(1024 * 1024))

enum HazardCode {
  HAZARD_EMPTY_ROOT = 0,
  HAZARD_RELATIVE_ROOT,
  HAZARD_MISSING_ROOT,
  HAZARD_NON_DIRECTORY_ROOT,
  HAZARD_GROUP_WRITABLE,
  HAZARD_WORLD_WRITABLE,
  HAZARD_CODE_COUNT
};

static const char *const HAZARD_NAMES[HAZARD_CODE_COUNT] = {
    "EMPTY_ROOT",         "RELATIVE_ROOT",  "MISSING_ROOT",
    "NON_DIRECTORY_ROOT", "GROUP_WRITABLE", "WORLD_WRITABLE"};

struct Root {
  const char *text;
  size_t index;
  size_t len;
};

struct Finding {
  const char *root;
  size_t index;
  enum HazardCode code;
};

struct FindingBuffer {
  struct Finding *items;
  size_t len;
  size_t cap;
};

static const char USAGE_TEXT[] = "usage: pathaudit [--] ROOT...\n";
static const char HELP_TEXT[] =
    "usage: pathaudit [--] ROOT...\n"
    "Scan explicitly supplied PATH directory roots.\n";
static const char VERSION_TEXT[] = "pathaudit 0.1.0\n";

static int fputc_checked(int ch, FILE *stream) {
  return fputc(ch, stream) == EOF ? -1 : 0;
}

static int fputs_checked(const char *text, FILE *stream) {
  return fputs(text, stream) == EOF ? -1 : 0;
}

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
  fputs("pathaudit: STDOUT_WRITE\n", stderr);
  return 2;
}

static int complete_stdout(int status) {
  if (fflush(stdout) != 0 || ferror(stdout)) {
    return emit_stdout_write_error();
  }
  return status;
}

static void emit_diag_reason(const char *reason) {
  fprintf(stderr, "pathaudit: %s\n", reason);
}

static int ignore_sigpipe_for_stdout(void) {
  if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  return 0;
}

static void emit_diag_reason_root(const char *reason, const char *root) {
  fprintf(stderr, "pathaudit: %s: ", reason);
  (void)put_escaped_quoted(stderr, root);
  fputc('\n', stderr);
}

static void emit_usage_diag(const char *reason) {
  emit_diag_reason(reason);
  (void)fputs_checked(USAGE_TEXT, stderr);
}

static int cmp_unsigned_bytes(const char *left, const char *right) {
  const unsigned char *a = (const unsigned char *)left;
  const unsigned char *b = (const unsigned char *)right;
  while (*a == *b) {
    if (*a == '\0') {
      return 0;
    }
    a++;
    b++;
  }
  return (*a < *b) ? -1 : 1;
}

static void findings_free(struct FindingBuffer *buffer) {
  free(buffer->items);
  buffer->items = NULL;
  buffer->len = 0;
  buffer->cap = 0;
}

static bool findings_append(struct FindingBuffer *buffer, const char *root,
                            size_t index, enum HazardCode code) {
  if (buffer->len == buffer->cap) {
    size_t new_cap = buffer->cap == 0 ? 16 : buffer->cap * 2;
    if (new_cap <= buffer->cap ||
        new_cap > SIZE_MAX / sizeof(buffer->items[0])) {
      return false;
    }
    struct Finding *grown =
        realloc(buffer->items, new_cap * sizeof(buffer->items[0]));
    if (grown == NULL) {
      return false;
    }
    buffer->items = grown;
    buffer->cap = new_cap;
  }

  buffer->items[buffer->len].root = root;
  buffer->items[buffer->len].index = index;
  buffer->items[buffer->len].code = code;
  buffer->len++;
  return true;
}

static int compare_roots_by_bytes_then_index(const void *left,
                                             const void *right) {
  const struct Root *a = left;
  const struct Root *b = right;
  int cmp = cmp_unsigned_bytes(a->text, b->text);
  if (cmp != 0) {
    return cmp;
  }
  if (a->index < b->index) {
    return -1;
  }
  if (a->index > b->index) {
    return 1;
  }
  return 0;
}

static int compare_findings(const void *left, const void *right) {
  const struct Finding *a = left;
  const struct Finding *b = right;
  int cmp = cmp_unsigned_bytes(a->root, b->root);
  if (cmp != 0) {
    return cmp;
  }
  if (a->index < b->index) {
    return -1;
  }
  if (a->index > b->index) {
    return 1;
  }
  if ((int)a->code < (int)b->code) {
    return -1;
  }
  if ((int)a->code > (int)b->code) {
    return 1;
  }
  return 0;
}

static bool size_add_ok(size_t a, size_t b, size_t *out) {
  if (a > SIZE_MAX - b) {
    return false;
  }
  *out = a + b;
  return true;
}

static int classify_root(const struct Root *root,
                         struct FindingBuffer *findings) {
  if (root->len == 0) {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_EMPTY_ROOT)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    return 0;
  }

  if (root->text[0] != '/') {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_RELATIVE_ROOT)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
  }

  struct stat st;
  if (stat(root->text, &st) != 0) {
    int err = errno;
    if (err == ENOENT) {
      if (!findings_append(findings, root->text, root->index,
                           HAZARD_MISSING_ROOT)) {
        emit_diag_reason("OUT_OF_MEMORY");
        return 2;
      }
      return 0;
    }
    if (err == ENOTDIR) {
      if (!findings_append(findings, root->text, root->index,
                           HAZARD_NON_DIRECTORY_ROOT)) {
        emit_diag_reason("OUT_OF_MEMORY");
        return 2;
      }
      return 0;
    }

    char reason[64];
    int written = snprintf(reason, sizeof(reason), "INSPECTION_ERROR_%d", err);
    if (written < 0 || (size_t)written >= sizeof(reason)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    emit_diag_reason_root(reason, root->text);
    return 2;
  }

  if (!S_ISDIR(st.st_mode)) {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_NON_DIRECTORY_ROOT)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    return 0;
  }

  if ((st.st_mode & S_IWGRP) != 0) {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_GROUP_WRITABLE)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
  }
  if ((st.st_mode & S_IWOTH) != 0) {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_WORLD_WRITABLE)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
  }
  return 0;
}

static int emit_findings(const struct FindingBuffer *findings) {
  for (size_t i = 0; i < findings->len; i++) {
    const struct Finding *item = &findings->items[i];
    if (fputs_checked(HAZARD_NAMES[item->code], stdout) != 0 ||
        fputc_checked('\t', stdout) != 0 ||
        put_escaped_quoted(stdout, item->root) != 0 ||
        fputc_checked('\n', stdout) != 0) {
      return emit_stdout_write_error();
    }
  }
  return complete_stdout(findings->len == 0 ? 0 : 1);
}

static int run_audit(struct Root *roots, size_t root_count) {
  struct FindingBuffer findings = {0};

  qsort(roots, root_count, sizeof(roots[0]), compare_roots_by_bytes_then_index);

  for (size_t i = 0; i < root_count; i++) {
    int status = classify_root(&roots[i], &findings);
    if (status != 0) {
      findings_free(&findings);
      return status;
    }
  }

  if (findings.len > 1) {
    qsort(findings.items, findings.len, sizeof(findings.items[0]),
          compare_findings);
  }

  int status = emit_findings(&findings);
  findings_free(&findings);
  return status;
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

int main(int argc, char **argv) {
  if (argc < 1) {
    emit_usage_diag("USAGE");
    return 2;
  }

  {
    int sigpipe_status = ignore_sigpipe_for_stdout();
    if (sigpipe_status != 0) {
      return sigpipe_status;
    }
  }

  if (argc >= 2 && strcmp(argv[1], "--help") == 0) {
    if (argc != 2) {
      emit_usage_diag("USAGE");
      return 2;
    }
    return handle_help();
  }

  if (argc >= 2 && strcmp(argv[1], "--version") == 0) {
    if (argc != 2) {
      emit_usage_diag("USAGE");
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

  if (argi >= argc) {
    emit_usage_diag("USAGE");
    return 2;
  }

  if (!end_of_options) {
    for (int i = argi; i < argc; i++) {
      if (argv[i][0] == '-') {
        emit_usage_diag("UNKNOWN_OPTION");
        return 2;
      }
    }
  }

  size_t root_count = (size_t)(argc - argi);
  if (root_count > PATHAUDIT_MAX_ROOT_COUNT) {
    emit_diag_reason("ROOT_COUNT_LIMIT");
    return 2;
  }

  struct Root *roots = calloc(root_count, sizeof(*roots));
  if (roots == NULL) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }

  size_t total_bytes = 0;
  for (size_t i = 0; i < root_count; i++) {
    const char *text = argv[argi + (int)i];
    size_t len = strlen(text);
    if (len > PATHAUDIT_MAX_ROOT_LENGTH) {
      free(roots);
      emit_diag_reason("ROOT_LENGTH_LIMIT");
      return 2;
    }

    size_t with_nul;
    if (!size_add_ok(len, 1, &with_nul) ||
        !size_add_ok(total_bytes, with_nul, &total_bytes)) {
      free(roots);
      emit_diag_reason("ROOT_BYTES_LIMIT");
      return 2;
    }
    if (total_bytes > PATHAUDIT_MAX_ROOT_BYTES) {
      free(roots);
      emit_diag_reason("ROOT_BYTES_LIMIT");
      return 2;
    }

    roots[i].text = text;
    roots[i].index = i;
    roots[i].len = len;
  }

  int status = run_audit(roots, root_count);
  free(roots);
  return status;
}
