#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SYSDIFF_MAX_LINE_BYTES ((size_t)65536)
#define SYSDIFF_MAX_SNAPSHOT_ENTRIES ((size_t)65536)

struct Entry {
  char *key;
  char *value;
};

struct Snapshot {
  struct Entry *items;
  size_t len;
  size_t cap;
};

enum LineStatus {
  LINE_OK,
  LINE_EOF,
  LINE_EMBEDDED_NUL,
  LINE_TOO_LONG,
  LINE_READ_ERROR,
  LINE_ALLOC_ERROR
};

enum AppendStatus { APPEND_OK, APPEND_ENTRY_LIMIT, APPEND_ALLOC_ERROR };

static void print_usage(FILE *stream) {
  fputs("usage: sysdiff --help|--version|compare BEFORE_SNAPSHOT "
        "AFTER_SNAPSHOT\n",
        stream);
}

static void snapshot_free(struct Snapshot *snapshot) {
  for (size_t i = 0; i < snapshot->len; i++) {
    free(snapshot->items[i].key);
    free(snapshot->items[i].value);
  }
  free(snapshot->items);
  snapshot->items = NULL;
  snapshot->len = 0;
  snapshot->cap = 0;
}

static char *copy_range(const char *text, size_t len) {
  if (len > SIZE_MAX - 1) {
    return NULL;
  }

  char *copy = malloc(len + 1);
  if (copy == NULL) {
    return NULL;
  }

  memcpy(copy, text, len);
  copy[len] = '\0';
  return copy;
}

static enum LineStatus read_line(FILE *file, char **out, size_t *out_len) {
  char *line = NULL;
  size_t len = 0;
  size_t cap = 0;

  for (;;) {
    int ch = fgetc(file);
    if (ch == EOF) {
      if (ferror(file)) {
        free(line);
        return LINE_READ_ERROR;
      }
      if (len == 0) {
        free(line);
        return LINE_EOF;
      }
      break;
    }

    if (ch == '\0') {
      free(line);
      return LINE_EMBEDDED_NUL;
    }

    if (ch != '\n' && len >= SYSDIFF_MAX_LINE_BYTES) {
      free(line);
      return LINE_TOO_LONG;
    }

    if (cap - len <= 1) {
      size_t new_cap = cap == 0 ? 128 : cap * 2;
      if (new_cap <= cap || new_cap > SIZE_MAX / sizeof(line[0])) {
        free(line);
        return LINE_ALLOC_ERROR;
      }

      char *new_line = realloc(line, new_cap * sizeof(line[0]));
      if (new_line == NULL) {
        free(line);
        return LINE_ALLOC_ERROR;
      }
      line = new_line;
      cap = new_cap;
    }

    line[len++] = (char)ch;
    if (ch == '\n') {
      break;
    }
  }

  line[len] = '\0';
  *out = line;
  *out_len = len;
  return LINE_OK;
}

static bool is_comment_line(const char *line) {
  size_t i = 0;

  while (line[i] == ' ' || line[i] == '\t') {
    i++;
  }

  return line[i] == '#';
}

static bool is_key_byte(unsigned char ch) {
  return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
         (ch >= '0' && ch <= '9') || ch == '.' || ch == '_' || ch == '-' ||
         ch == '/';
}

static bool is_valid_key(const char *key, size_t key_len) {
  bool saw_dot = false;

  if (key_len == 0 || key[0] == '/' || key[key_len - 1] == '.') {
    return false;
  }

  for (size_t i = 0; i < key_len; i++) {
    unsigned char ch = (unsigned char)key[i];
    if (!is_key_byte(ch)) {
      return false;
    }
    if (ch == '.') {
      saw_dot = true;
      if (i > 0 && key[i - 1] == '.') {
        return false;
      }
    }
  }

  return saw_dot;
}

static enum AppendStatus snapshot_append(struct Snapshot *snapshot, char *key,
                                         char *value) {
  if (snapshot->len >= SYSDIFF_MAX_SNAPSHOT_ENTRIES) {
    return APPEND_ENTRY_LIMIT;
  }

  if (snapshot->len == snapshot->cap) {
    size_t new_cap = snapshot->cap == 0 ? 8 : snapshot->cap * 2;
    if (new_cap > SYSDIFF_MAX_SNAPSHOT_ENTRIES) {
      new_cap = SYSDIFF_MAX_SNAPSHOT_ENTRIES;
    }
    if (new_cap <= snapshot->cap ||
        new_cap > SIZE_MAX / sizeof(snapshot->items[0])) {
      return APPEND_ALLOC_ERROR;
    }

    struct Entry *new_items =
        realloc(snapshot->items, new_cap * sizeof(snapshot->items[0]));
    if (new_items == NULL) {
      return APPEND_ALLOC_ERROR;
    }

    snapshot->items = new_items;
    snapshot->cap = new_cap;
  }

  snapshot->items[snapshot->len].key = key;
  snapshot->items[snapshot->len].value = value;
  snapshot->len++;
  return APPEND_OK;
}

static int compare_entries_by_key(const void *left, const void *right) {
  const struct Entry *left_entry = left;
  const struct Entry *right_entry = right;

  return strcmp(left_entry->key, right_entry->key);
}

static bool validate_no_duplicates(const char *path,
                                   const struct Snapshot *snapshot) {
  for (size_t i = 1; i < snapshot->len; i++) {
    if (strcmp(snapshot->items[i - 1].key, snapshot->items[i].key) == 0) {
      fprintf(stderr, "%s: duplicate key: %s\n", path, snapshot->items[i].key);
      return false;
    }
  }

  return true;
}

static int parse_snapshot(const char *path, struct Snapshot *snapshot) {
  FILE *file = fopen(path, "rb");
  if (file == NULL) {
    fprintf(stderr, "%s: cannot open: %s\n", path, strerror(errno));
    return 2;
  }

  size_t line_no = 0;
  for (;;) {
    char *line = NULL;
    size_t line_len = 0;
    enum LineStatus status = read_line(file, &line, &line_len);

    if (status == LINE_EOF) {
      break;
    }
    if (status == LINE_EMBEDDED_NUL) {
      fprintf(stderr, "%s:%zu: embedded NUL byte\n", path, line_no + 1);
      goto cleanup;
    }
    if (status == LINE_TOO_LONG) {
      fprintf(stderr,
              "%s:%zu: line length limit exceeded (maximum %zu bytes)\n", path,
              line_no + 1, SYSDIFF_MAX_LINE_BYTES);
      goto cleanup;
    }
    if (status == LINE_READ_ERROR) {
      fprintf(stderr, "%s:%zu: read error\n", path, line_no + 1);
      goto cleanup;
    }
    if (status == LINE_ALLOC_ERROR) {
      fprintf(stderr, "%s:%zu: allocation failure\n", path, line_no + 1);
      goto cleanup;
    }

    line_no++;
    if (line_len > 0 && line[line_len - 1] == '\n') {
      line[--line_len] = '\0';
      if (line_len > 0 && line[line_len - 1] == '\r') {
        line[--line_len] = '\0';
      }
    }

    if (line[0] == '\0' || is_comment_line(line)) {
      free(line);
      continue;
    }

    char *separator = strchr(line, '=');
    if (separator == NULL) {
      free(line);
      fprintf(stderr, "%s:%zu: missing '=' separator\n", path, line_no);
      goto cleanup;
    }
    if (separator == line) {
      free(line);
      fprintf(stderr, "%s:%zu: empty key\n", path, line_no);
      goto cleanup;
    }

    size_t key_len = (size_t)(separator - line);
    size_t value_len = line_len - key_len - 1;
    if (!is_valid_key(line, key_len)) {
      free(line);
      fprintf(stderr, "%s:%zu: invalid key syntax\n", path, line_no);
      goto cleanup;
    }

    char *key = copy_range(line, key_len);
    char *value = copy_range(separator + 1, value_len);
    free(line);

    if (key == NULL || value == NULL) {
      free(key);
      free(value);
      fprintf(stderr, "%s:%zu: allocation failure\n", path, line_no);
      goto cleanup;
    }

    enum AppendStatus append_status = snapshot_append(snapshot, key, value);
    if (append_status != APPEND_OK) {
      free(key);
      free(value);
      if (append_status == APPEND_ENTRY_LIMIT) {
        fprintf(stderr,
                "%s:%zu: snapshot entry limit exceeded (maximum %zu entries)\n",
                path, line_no, SYSDIFF_MAX_SNAPSHOT_ENTRIES);
      } else {
        fprintf(stderr, "%s:%zu: allocation failure\n", path, line_no);
      }
      goto cleanup;
    }
  }

  if (fclose(file) != 0) {
    fprintf(stderr, "%s: close failed: %s\n", path, strerror(errno));
    file = NULL;
    goto cleanup;
  }
  file = NULL;

  if (snapshot->len > 1) {
    qsort(snapshot->items, snapshot->len, sizeof(snapshot->items[0]),
          compare_entries_by_key);
  }

  if (!validate_no_duplicates(path, snapshot)) {
    goto cleanup;
  }

  return 0;

cleanup:
  if (file != NULL) {
    (void)fclose(file);
  }
  snapshot_free(snapshot);
  return 2;
}

static int emit_diff(const struct Snapshot *before,
                     const struct Snapshot *after) {
  size_t before_i = 0;
  size_t after_i = 0;
  bool changed = false;

  while (before_i < before->len || after_i < after->len) {
    if (before_i == before->len) {
      printf("+ %s=%s\n", after->items[after_i].key,
             after->items[after_i].value);
      after_i++;
      changed = true;
      continue;
    }

    if (after_i == after->len) {
      printf("- %s=%s\n", before->items[before_i].key,
             before->items[before_i].value);
      before_i++;
      changed = true;
      continue;
    }

    int cmp = strcmp(before->items[before_i].key, after->items[after_i].key);
    if (cmp == 0) {
      if (strcmp(before->items[before_i].value, after->items[after_i].value) !=
          0) {
        printf("~ %s: %s -> %s\n", before->items[before_i].key,
               before->items[before_i].value, after->items[after_i].value);
        changed = true;
      }
      before_i++;
      after_i++;
    } else if (cmp < 0) {
      printf("- %s=%s\n", before->items[before_i].key,
             before->items[before_i].value);
      before_i++;
      changed = true;
    } else {
      printf("+ %s=%s\n", after->items[after_i].key,
             after->items[after_i].value);
      after_i++;
      changed = true;
    }
  }

  if (!changed) {
    puts("no changes");
    return 0;
  }

  return 1;
}

static int compare_snapshots(const char *before_path, const char *after_path) {
  struct Snapshot before = {0};
  struct Snapshot after = {0};

  int status = parse_snapshot(before_path, &before);
  if (status != 0) {
    return status;
  }

  status = parse_snapshot(after_path, &after);
  if (status != 0) {
    snapshot_free(&before);
    return status;
  }

  status = emit_diff(&before, &after);
  snapshot_free(&before);
  snapshot_free(&after);
  return status;
}

int main(int argc, char **argv) {
  if (argc == 1) {
    print_usage(stdout);
    return 0;
  }

  if (argc == 2 && strcmp(argv[1], "--help") == 0) {
    print_usage(stdout);
    return 0;
  }
  if (argc == 2 && strcmp(argv[1], "--version") == 0) {
    puts("sysdiff 0.1.0");
    return 0;
  }

  if (strcmp(argv[1], "compare") == 0) {
    if (argc != 4) {
      fputs("sysdiff: compare requires BEFORE_SNAPSHOT and "
            "AFTER_SNAPSHOT\n",
            stderr);
      print_usage(stderr);
      return 2;
    }

    return compare_snapshots(argv[2], argv[3]);
  }

  fprintf(stderr, "sysdiff: unknown command: %s\n", argv[1]);
  print_usage(stderr);
  return 2;
}
