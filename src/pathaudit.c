#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

/*
 * realpath(3), lstat(2), and readlink(2) are POSIX. Declare them explicitly
 * instead of enabling a feature-test macro: under -std=c17 those macros trip
 * clang-tidy's bugprone-reserved-identifier check, while the rest of
 * pathaudit compiles without feature macros (same pattern as HEAD before
 * --command).
 */
char *realpath(const char *path, char *resolved_path);
int lstat(const char *path, struct stat *buf);
ssize_t readlink(const char *path, char *buf, size_t bufsiz);

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
  HAZARD_UNSAFE_OWNER,
  HAZARD_CODE_COUNT
};

static const char *const HAZARD_NAMES[HAZARD_CODE_COUNT] = {
    "EMPTY_ROOT",     "RELATIVE_ROOT",  "MISSING_ROOT", "NON_DIRECTORY_ROOT",
    "GROUP_WRITABLE", "WORLD_WRITABLE", "UNSAFE_OWNER"};

struct Root {
  const char *text;
  size_t index;
  size_t len;
};

struct Finding {
  const char *root;
  char *owned_root; /* non-NULL when root is an owned realpath copy */
  size_t index;
  enum HazardCode code;
};

struct FindingBuffer {
  struct Finding *items;
  size_t len;
  size_t cap;
};

struct MatchBuffer {
  char **paths; /* owned realpath strings */
  size_t len;
  size_t cap;
};

/* First PATH-order regular executable for a command basename. */
struct WinnerEntry {
  char *command; /* owned basename */
  char *path;    /* owned realpath */
};

/*
 * Winner table plus open-addressing index by command basename. Empty index
 * slots hold SIZE_MAX. index_cap is 0 or a power of two so probes can mask.
 */
struct WinnerBuffer {
  struct WinnerEntry *items;
  size_t len;
  size_t cap;
  size_t *index_slots;
  size_t index_cap;
};

/* One shadowed executable against a first-PATH winner. */
struct ShadowRecord {
  char *command; /* owned basename */
  char *winner;  /* owned winner realpath */
  char *shadow;  /* owned shadowed realpath */
  size_t shadow_index;
};

/*
 * Shadow table plus open-addressing index by (command, shadow) bytes. Empty
 * slots hold SIZE_MAX. index_cap is 0 or a power of two so probes can mask.
 * Winner is fixed once a basename is won, so (command, shadow) uniquely
 * identifies an exact (command, winner, shadow) tuple for duplicate checks.
 * index_slots store positional indices into items; they become stale if items
 * are reordered and must be invalidated before any such permutation. After
 * invalidation, no further appends that rely on the index are permitted.
 */
struct ShadowBuffer {
  struct ShadowRecord *items;
  size_t len;
  size_t cap;
  size_t *index_slots;
  size_t index_cap;
};

struct PathComponents {
  char *storage;      /* owned PATH copy with ':' replaced by NUL */
  struct Root *roots; /* owned; text pointers alias into storage */
  size_t count;
};

static const char USAGE_TEXT[] = "usage: pathaudit [--] ROOT...\n"
                                 "   or: pathaudit --path\n"
                                 "   or: pathaudit --command NAME\n";
static const char HELP_TEXT[] = "usage: pathaudit [--] ROOT...\n"
                                "   or: pathaudit --path\n"
                                "   or: pathaudit --command NAME\n"
                                "Scan PATH directory roots for hazards.\n";
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

static char *owned_strdup(const char *text) {
  size_t len = strlen(text);
  char *copy = malloc(len + 1);
  if (copy == NULL) {
    return NULL;
  }
  memcpy(copy, text, len + 1);
  return copy;
}

/*
 * FNV-1a over unsigned basename bytes for the winner/shadow indexes.
 * Use width-correct constants so LP64 builds get FNV-1a-64 avalanche.
 */
static size_t hash_command_bytes(const char *text) {
  size_t hash;
  size_t prime;
  if (SIZE_MAX > 0xffffffffu) {
    hash = (size_t)14695981039346656037ull;
    prime = (size_t)1099511628211ull;
  } else {
    hash = (size_t)2166136261u;
    prime = (size_t)16777619u;
  }
  const unsigned char *p = (const unsigned char *)text;
  while (*p != '\0') {
    hash ^= (size_t)*p;
    hash *= prime;
    p++;
  }
  return hash;
}

/* Mix two C strings into one index key (command then shadow realpath). */
static size_t hash_command_shadow_pair(const char *command,
                                       const char *shadow) {
  size_t hash = hash_command_bytes(command);
  /* Domain separator so ("ab","c") and ("a","bc") do not collide by concat. */
  hash ^= (size_t)0x1fu;
  if (SIZE_MAX > 0xffffffffu) {
    hash *= (size_t)1099511628211ull;
  } else {
    hash *= (size_t)16777619u;
  }
  const unsigned char *p = (const unsigned char *)shadow;
  while (*p != '\0') {
    hash ^= (size_t)*p;
    if (SIZE_MAX > 0xffffffffu) {
      hash *= (size_t)1099511628211ull;
    } else {
      hash *= (size_t)16777619u;
    }
    p++;
  }
  return hash;
}

static void findings_free(struct FindingBuffer *buffer) {
  if (buffer->items != NULL) {
    for (size_t i = 0; i < buffer->len; i++) {
      free(buffer->items[i].owned_root);
      buffer->items[i].owned_root = NULL;
      buffer->items[i].root = NULL;
    }
  }
  free(buffer->items);
  buffer->items = NULL;
  buffer->len = 0;
  buffer->cap = 0;
}

static bool findings_reserve(struct FindingBuffer *buffer) {
  if (buffer->len != buffer->cap) {
    return true;
  }
  size_t new_cap = buffer->cap == 0 ? 16 : buffer->cap * 2;
  if (new_cap <= buffer->cap || new_cap > SIZE_MAX / sizeof(buffer->items[0])) {
    return false;
  }
  struct Finding *grown =
      realloc(buffer->items, new_cap * sizeof(buffer->items[0]));
  if (grown == NULL) {
    return false;
  }
  buffer->items = grown;
  buffer->cap = new_cap;
  return true;
}

static bool findings_append(struct FindingBuffer *buffer, const char *root,
                            size_t index, enum HazardCode code) {
  if (!findings_reserve(buffer)) {
    return false;
  }

  buffer->items[buffer->len].root = root;
  buffer->items[buffer->len].owned_root = NULL;
  buffer->items[buffer->len].index = index;
  buffer->items[buffer->len].code = code;
  buffer->len++;
  return true;
}

/*
 * Append a finding whose root is an owned copy of text (executable or
 * directory-ownership realpath). findings_free releases the copy. Used when
 * the finding root is not aliased into PATH component storage.
 */
static bool findings_append_owned(struct FindingBuffer *buffer,
                                  const char *text, size_t index,
                                  enum HazardCode code) {
  char *owned = owned_strdup(text);
  if (owned == NULL) {
    return false;
  }
  if (!findings_reserve(buffer)) {
    free(owned);
    return false;
  }

  buffer->items[buffer->len].root = owned;
  buffer->items[buffer->len].owned_root = owned;
  buffer->items[buffer->len].index = index;
  buffer->items[buffer->len].code = code;
  buffer->len++;
  return true;
}

/*
 * Trust policy shared by executable and PATH-directory ownership: only root
 * UID 0 and the invoking real UID from getuid() are trusted.
 */
static bool owner_uid_is_trusted(uid_t owner) {
  return owner == (uid_t)0 || owner == getuid();
}

/*
 * Record UNSAFE_OWNER for an owned realpath, deduplicating shared ancestors to
 * the lowest PATH index that observed the same offending path bytes.
 */
static bool findings_note_unsafe_owner(struct FindingBuffer *buffer,
                                       const char *realpath_text,
                                       size_t index) {
  for (size_t i = 0; i < buffer->len; i++) {
    if (buffer->items[i].code != HAZARD_UNSAFE_OWNER) {
      continue;
    }
    if (cmp_unsigned_bytes(buffer->items[i].root, realpath_text) != 0) {
      continue;
    }
    if (index < buffer->items[i].index) {
      buffer->items[i].index = index;
    }
    return true;
  }
  return findings_append_owned(buffer, realpath_text, index,
                               HAZARD_UNSAFE_OWNER);
}

/*
 * Truncate an absolute realpath buffer to its parent directory. Returns false
 * when path is already "/".
 */
static bool path_truncate_to_parent(char *path) {
  if (path[0] == '/' && path[1] == '\0') {
    return false;
  }
  char *slash = strrchr(path, '/');
  if (slash == NULL) {
    return false;
  }
  if (slash == path) {
    path[1] = '\0';
    return true;
  }
  *slash = '\0';
  return true;
}

/*
 * Walk path's realpath and each ancestor through "/" under the shared ownership
 * trust policy. Findings name the canonical offending directory realpath.
 * Missing, non-directory, and unresolvable inputs invent nothing. Shared
 * offending realpaths keep the lowest PATH index. Hostile/racy metadata is
 * skipped node-by-node without failing the scan.
 */
static int append_directory_chain_ownership(const char *path, size_t index,
                                            struct FindingBuffer *findings) {
  char *resolved = malloc(PATHAUDIT_MAX_ROOT_LENGTH + 1);
  if (resolved == NULL) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }

  errno = 0;
  if (realpath(path, resolved) == NULL) {
    int err = errno;
    free(resolved);
    if (err == ENOMEM) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    return 0;
  }

  struct stat st;
  if (stat(resolved, &st) != 0 || !S_ISDIR(st.st_mode)) {
    free(resolved);
    return 0;
  }

  for (;;) {
    if (stat(resolved, &st) == 0) {
      if (!owner_uid_is_trusted(st.st_uid)) {
        if (!findings_note_unsafe_owner(findings, resolved, index)) {
          free(resolved);
          emit_diag_reason("OUT_OF_MEMORY");
          return 2;
        }
      }
    }
    if (!path_truncate_to_parent(resolved)) {
      break;
    }
  }

  free(resolved);
  return 0;
}

static void matches_free(struct MatchBuffer *buffer) {
  if (buffer->paths != NULL) {
    for (size_t i = 0; i < buffer->len; i++) {
      free(buffer->paths[i]);
      buffer->paths[i] = NULL;
    }
  }
  free((void *)buffer->paths);
  buffer->paths = NULL;
  buffer->len = 0;
  buffer->cap = 0;
}

static bool matches_append(struct MatchBuffer *buffer, char *owned_path) {
  if (buffer->len == buffer->cap) {
    size_t new_cap = buffer->cap == 0 ? 8 : buffer->cap * 2;
    if (new_cap <= buffer->cap ||
        new_cap > SIZE_MAX / sizeof(buffer->paths[0])) {
      return false;
    }
    char **grown = (char **)realloc((void *)buffer->paths,
                                    new_cap * sizeof(buffer->paths[0]));
    if (grown == NULL) {
      return false;
    }
    buffer->paths = grown;
    buffer->cap = new_cap;
  }

  buffer->paths[buffer->len] = owned_path;
  buffer->len++;
  return true;
}

static void winners_free(struct WinnerBuffer *buffer) {
  if (buffer->items != NULL) {
    for (size_t i = 0; i < buffer->len; i++) {
      free(buffer->items[i].command);
      free(buffer->items[i].path);
      buffer->items[i].command = NULL;
      buffer->items[i].path = NULL;
    }
  }
  free(buffer->items);
  free(buffer->index_slots);
  buffer->items = NULL;
  buffer->index_slots = NULL;
  buffer->len = 0;
  buffer->cap = 0;
  buffer->index_cap = 0;
}

static bool winners_index_rehash(struct WinnerBuffer *buffer, size_t new_cap) {
  if (new_cap == 0 || (new_cap & (new_cap - 1)) != 0 ||
      new_cap > SIZE_MAX / sizeof(size_t)) {
    return false;
  }

  size_t *slots = malloc(new_cap * sizeof(*slots));
  if (slots == NULL) {
    return false;
  }
  for (size_t i = 0; i < new_cap; i++) {
    slots[i] = SIZE_MAX;
  }

  const size_t mask = new_cap - 1;
  for (size_t i = 0; i < buffer->len; i++) {
    size_t slot = hash_command_bytes(buffer->items[i].command) & mask;
    while (slots[slot] != SIZE_MAX) {
      slot = (slot + 1) & mask;
    }
    slots[slot] = i;
  }

  free(buffer->index_slots);
  buffer->index_slots = slots;
  buffer->index_cap = new_cap;
  return true;
}

/*
 * Insert the newest tail entry (items[len - 1]) into the winner index.
 * Caller must increment len before calling so growth-path rehash covers it.
 */
static bool winners_index_insert_tail(struct WinnerBuffer *buffer) {
  if (buffer->len == 0) {
    return false;
  }
  const size_t item_index = buffer->len - 1;

  /* Grow before load exceeds half the power-of-two table (overflow-safe). */
  if (buffer->index_cap == 0 || buffer->len > buffer->index_cap / 2) {
    size_t new_cap;
    if (buffer->index_cap == 0) {
      new_cap = (size_t)16;
    } else if (buffer->index_cap > SIZE_MAX / 2) {
      /* Reject before index_cap * 2 wraps; a wrapped 0 would spin forever. */
      return false;
    } else {
      new_cap = buffer->index_cap * 2;
    }
    while (new_cap / 2 < buffer->len) {
      if (new_cap > SIZE_MAX / 2) {
        return false;
      }
      new_cap *= 2;
    }
    return winners_index_rehash(buffer, new_cap);
  }

  const size_t mask = buffer->index_cap - 1;
  size_t slot = hash_command_bytes(buffer->items[item_index].command) & mask;
  while (buffer->index_slots[slot] != SIZE_MAX) {
    slot = (slot + 1) & mask;
  }
  buffer->index_slots[slot] = item_index;
  return true;
}

static const struct WinnerEntry *winners_find(const struct WinnerBuffer *buffer,
                                              const char *command) {
  if (buffer->index_cap == 0 || buffer->index_slots == NULL) {
    return NULL;
  }

  const size_t mask = buffer->index_cap - 1;
  size_t slot = hash_command_bytes(command) & mask;
  for (;;) {
    const size_t idx = buffer->index_slots[slot];
    if (idx == SIZE_MAX) {
      return NULL;
    }
    if (cmp_unsigned_bytes(buffer->items[idx].command, command) == 0) {
      return &buffer->items[idx];
    }
    slot = (slot + 1) & mask;
  }
}

static bool winners_append(struct WinnerBuffer *buffer, char *owned_command,
                           char *owned_path) {
  if (buffer->len == buffer->cap) {
    size_t new_cap = buffer->cap == 0 ? 16 : buffer->cap * 2;
    if (new_cap <= buffer->cap ||
        new_cap > SIZE_MAX / sizeof(buffer->items[0])) {
      return false;
    }
    struct WinnerEntry *grown =
        realloc(buffer->items, new_cap * sizeof(buffer->items[0]));
    if (grown == NULL) {
      return false;
    }
    buffer->items = grown;
    buffer->cap = new_cap;
  }

  const size_t new_index = buffer->len;
  buffer->items[new_index].command = owned_command;
  buffer->items[new_index].path = owned_path;
  buffer->len++;
  if (!winners_index_insert_tail(buffer)) {
    buffer->len--;
    buffer->items[new_index].command = NULL;
    buffer->items[new_index].path = NULL;
    return false;
  }
  return true;
}

static void shadows_free(struct ShadowBuffer *buffer) {
  if (buffer->items != NULL) {
    for (size_t i = 0; i < buffer->len; i++) {
      free(buffer->items[i].command);
      free(buffer->items[i].winner);
      free(buffer->items[i].shadow);
      buffer->items[i].command = NULL;
      buffer->items[i].winner = NULL;
      buffer->items[i].shadow = NULL;
    }
  }
  free(buffer->items);
  free(buffer->index_slots);
  buffer->items = NULL;
  buffer->index_slots = NULL;
  buffer->len = 0;
  buffer->cap = 0;
  buffer->index_cap = 0;
}

static bool shadows_index_rehash(struct ShadowBuffer *buffer, size_t new_cap) {
  if (new_cap == 0 || (new_cap & (new_cap - 1)) != 0 ||
      new_cap > SIZE_MAX / sizeof(size_t)) {
    return false;
  }

  size_t *slots = malloc(new_cap * sizeof(*slots));
  if (slots == NULL) {
    return false;
  }
  for (size_t i = 0; i < new_cap; i++) {
    slots[i] = SIZE_MAX;
  }

  const size_t mask = new_cap - 1;
  for (size_t i = 0; i < buffer->len; i++) {
    size_t slot = hash_command_shadow_pair(buffer->items[i].command,
                                           buffer->items[i].shadow) &
                  mask;
    while (slots[slot] != SIZE_MAX) {
      slot = (slot + 1) & mask;
    }
    slots[slot] = i;
  }

  free(buffer->index_slots);
  buffer->index_slots = slots;
  buffer->index_cap = new_cap;
  return true;
}

/*
 * Drop the positional (command, shadow) index. Required before reordering
 * items (qsort): slots name insertion positions and do not survive permute.
 * After this call, shadow_tuple_recorded returns false; do not append more
 * shadows that rely on duplicate suppression for the remainder of the run.
 */
static void shadows_index_invalidate(struct ShadowBuffer *buffer) {
  free(buffer->index_slots);
  buffer->index_slots = NULL;
  buffer->index_cap = 0;
}

/*
 * Insert the newest tail entry (items[len - 1]) into the shadow index.
 * Caller must increment len before calling so growth-path rehash covers it.
 */
static bool shadows_index_insert_tail(struct ShadowBuffer *buffer) {
  if (buffer->len == 0) {
    return false;
  }
  const size_t item_index = buffer->len - 1;

  if (buffer->index_cap == 0 || buffer->len > buffer->index_cap / 2) {
    size_t new_cap;
    if (buffer->index_cap == 0) {
      new_cap = (size_t)16;
    } else if (buffer->index_cap > SIZE_MAX / 2) {
      return false;
    } else {
      new_cap = buffer->index_cap * 2;
    }
    while (new_cap / 2 < buffer->len) {
      if (new_cap > SIZE_MAX / 2) {
        return false;
      }
      new_cap *= 2;
    }
    return shadows_index_rehash(buffer, new_cap);
  }

  const size_t mask = buffer->index_cap - 1;
  size_t slot = hash_command_shadow_pair(buffer->items[item_index].command,
                                         buffer->items[item_index].shadow) &
                mask;
  while (buffer->index_slots[slot] != SIZE_MAX) {
    slot = (slot + 1) & mask;
  }
  buffer->index_slots[slot] = item_index;
  return true;
}

static bool shadows_append(struct ShadowBuffer *buffer, char *owned_command,
                           char *owned_winner, char *owned_shadow,
                           size_t shadow_index) {
  if (buffer->len == buffer->cap) {
    size_t new_cap = buffer->cap == 0 ? 16 : buffer->cap * 2;
    if (new_cap <= buffer->cap ||
        new_cap > SIZE_MAX / sizeof(buffer->items[0])) {
      return false;
    }
    struct ShadowRecord *grown =
        realloc(buffer->items, new_cap * sizeof(buffer->items[0]));
    if (grown == NULL) {
      return false;
    }
    buffer->items = grown;
    buffer->cap = new_cap;
  }

  const size_t new_index = buffer->len;
  buffer->items[new_index].command = owned_command;
  buffer->items[new_index].winner = owned_winner;
  buffer->items[new_index].shadow = owned_shadow;
  buffer->items[new_index].shadow_index = shadow_index;
  buffer->len++;
  if (!shadows_index_insert_tail(buffer)) {
    buffer->len--;
    buffer->items[new_index].command = NULL;
    buffer->items[new_index].winner = NULL;
    buffer->items[new_index].shadow = NULL;
    return false;
  }
  return true;
}

static void path_components_free(struct PathComponents *components) {
  free(components->roots);
  free(components->storage);
  components->roots = NULL;
  components->storage = NULL;
  components->count = 0;
}

/*
 * PATH splits on every ASCII ':'. A real directory name may itself contain
 * ':', so a single filesystem operand can be shattered into ENOENT fragments
 * that never reach classify_root. When rejoining consecutive non-empty
 * fragments with ':' yields a definitive non-ENOENT lookup failure (ELOOP,
 * EACCES, ENOTDIR, ...), restore those separators so the inspection diagnostic
 * names — and quote-escapes — the original hostile operand text. Successful
 * lookups and pure-ENOENT joins stay split to preserve ordinary PATH semantics.
 * Empty fields are never crossed. Mutates owned storage only.
 */
static void
coalesce_inspection_path_fragments(struct PathComponents *components) {
  struct Root *roots = components->roots;
  size_t n = components->count;
  size_t out = 0;
  size_t i = 0;

  while (i < n) {
    if (roots[i].len == 0) {
      roots[out] = roots[i];
      roots[out].index = out;
      out++;
      i++;
      continue;
    }

    struct stat st;
    errno = 0;
    if (stat(roots[i].text, &st) == 0 || errno != ENOENT) {
      roots[out] = roots[i];
      roots[out].index = out;
      out++;
      i++;
      continue;
    }

    size_t orig_len = roots[i].len;
    size_t last_restored = i;
    bool accepted = false;

    for (size_t j = i + 1; j < n; j++) {
      if (roots[j].len == 0) {
        break;
      }

      /* Boundary byte is the NUL that replaced the original ':'. */
      char *sep = (char *)roots[j].text - 1;
      size_t merged_len =
          (size_t)((roots[j].text + roots[j].len) - roots[i].text);
      if (merged_len > PATHAUDIT_MAX_ROOT_LENGTH) {
        break;
      }

      *sep = ':';
      last_restored = j;
      roots[i].len = merged_len;

      errno = 0;
      if (stat(roots[i].text, &st) == 0) {
        /* Existing path: keep ordinary colon-split semantics. */
        break;
      }
      if (errno != ENOENT) {
        accepted = true;
        break;
      }
    }

    if (!accepted) {
      for (size_t j = i + 1; j <= last_restored; j++) {
        if (roots[j].len == 0) {
          break;
        }
        *((char *)roots[j].text - 1) = '\0';
      }
      roots[i].len = orig_len;
      roots[out] = roots[i];
      roots[out].index = out;
      out++;
      i++;
      continue;
    }

    roots[out].text = roots[i].text;
    roots[out].len = roots[i].len;
    roots[out].index = out;
    out++;
    i = last_restored + 1;
  }

  components->count = out;
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

static int compare_shadows(const void *left, const void *right) {
  const struct ShadowRecord *a = left;
  const struct ShadowRecord *b = right;
  int cmp = cmp_unsigned_bytes(a->command, b->command);
  if (cmp != 0) {
    return cmp;
  }
  if (a->shadow_index < b->shadow_index) {
    return -1;
  }
  if (a->shadow_index > b->shadow_index) {
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

/*
 * Command-search meaning of a PATH entry depends on the process cwd when the
 * entry is empty (POSIX treats "" as ".") or non-absolute (".", "..", "./bin",
 * "bin", ...). Detect those cases without rewriting the original entry text:
 * empty fields keep "" and report EMPTY_ROOT with no lookup; non-absolute
 * fields report RELATIVE_ROOT and are still looked up against the process cwd.
 * Absolute entries (first byte '/') are not cwd-dependent under this rule.
 */
static bool root_is_cwd_dependent(const struct Root *root) {
  return root->len == 0 || root->text[0] != '/';
}

/*
 * Classify one PATH/root component. When audit_directory_ownership is true
 * (--path), usable directories also walk the shared UNSAFE_OWNER policy across
 * the entry's realpath and ancestors through "/". Empty, missing, and
 * non-directory components invent no ownership findings. Explicit-root mode
 * passes false and stays ownership-blind.
 */
static int classify_root(const struct Root *root,
                         struct FindingBuffer *findings,
                         bool audit_directory_ownership) {
  if (root->len == 0) {
    /* Empty colon field: cwd-dependent for search; keep "" as EMPTY_ROOT. */
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_EMPTY_ROOT)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    return 0;
  }

  if (root_is_cwd_dependent(root)) {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_RELATIVE_ROOT)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
  }

  /*
   * Distinguish usable directories from non-directory and missing targets.
   * ENOENT -> MISSING_ROOT. ENOTDIR (a path component is not a directory)
   * or a successful lookup whose final target is not a directory (regular
   * file, symlink-to-file, FIFO, device node, etc.) -> NON_DIRECTORY_ROOT.
   * Only a successful S_ISDIR target may receive permission findings.
   * Other lookup failures remain operational errors (status 2), not hazard
   * codes. Explicit-root and --path always emit NON_DIRECTORY_ROOT for
   * these cases; --command applicability is filtered separately.
   */
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

  if (audit_directory_ownership) {
    return append_directory_chain_ownership(root->text, root->index, findings);
  }
  return 0;
}

static int emit_finding_lines(const struct FindingBuffer *findings) {
  for (size_t i = 0; i < findings->len; i++) {
    const struct Finding *item = &findings->items[i];
    if (fputs_checked(HAZARD_NAMES[item->code], stdout) != 0 ||
        fputc_checked('\t', stdout) != 0 ||
        put_escaped_quoted(stdout, item->root) != 0 ||
        fputc_checked('\n', stdout) != 0) {
      return emit_stdout_write_error();
    }
  }
  return 0;
}

static int emit_findings(const struct FindingBuffer *findings) {
  int write_status = emit_finding_lines(findings);
  if (write_status != 0) {
    return write_status;
  }
  return complete_stdout(findings->len == 0 ? 0 : 1);
}

static int run_audit(struct Root *roots, size_t root_count) {
  struct FindingBuffer findings = {0};

  qsort(roots, root_count, sizeof(roots[0]), compare_roots_by_bytes_then_index);

  for (size_t i = 0; i < root_count; i++) {
    /* Explicit roots stay ownership-blind. */
    int status = classify_root(&roots[i], &findings, false);
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

/*
 * Exclusive `pathaudit --path` mode and shared PATH component loading.
 *
 * Ownership: path_storage is a malloc'd copy of the PATH value with ':'
 * replaced by NULs so each component is a C string. roots[].text pointers
 * alias into path_storage and must not outlive it. Both path_storage and
 * roots are freed on every exit path from callers via path_components_free.
 * getenv("PATH") is called once; its returned pointer is treated as hostile
 * opaque bytes and is only read to compute length/count and to copy into
 * path_storage.
 *
 * Returns 0 on success. On failure, emits a diagnostic and returns 2 with
 * *components left zeroed / freed. On success, may rejoin colon-shattered
 * fragments that fail inspection only as a whole (see
 * coalesce_inspection_path_fragments) so stderr diagnostics can quote-escape
 * the original operand text.
 */
static int path_components_load(struct PathComponents *components) {
  components->storage = NULL;
  components->roots = NULL;
  components->count = 0;

  const char *path_env = getenv("PATH");
  if (path_env == NULL) {
    emit_diag_reason("PATH_UNSET");
    return 2;
  }

  size_t path_len = strlen(path_env);

  /* n colons yield n+1 components, including empty PATH as one empty entry. */
  size_t root_count = 1;
  for (size_t i = 0; i < path_len; i++) {
    if (path_env[i] == ':') {
      if (root_count >= PATHAUDIT_MAX_ROOT_COUNT) {
        emit_diag_reason("ROOT_COUNT_LIMIT");
        return 2;
      }
      root_count++;
    }
  }

  char *path_storage = malloc(path_len + 1);
  if (path_storage == NULL) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  memcpy(path_storage, path_env, path_len + 1);

  struct Root *roots = calloc(root_count, sizeof(*roots));
  if (roots == NULL) {
    free(path_storage);
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }

  size_t total_bytes = 0;
  size_t index = 0;
  char *start = path_storage;
  for (char *p = path_storage;; p++) {
    if (*p != ':' && *p != '\0') {
      continue;
    }

    bool at_end = (*p == '\0');
    size_t len = (size_t)(p - start);
    *p = '\0';

    if (len > PATHAUDIT_MAX_ROOT_LENGTH) {
      free(roots);
      free(path_storage);
      emit_diag_reason("ROOT_LENGTH_LIMIT");
      return 2;
    }

    size_t with_nul;
    if (!size_add_ok(len, 1, &with_nul) ||
        !size_add_ok(total_bytes, with_nul, &total_bytes)) {
      free(roots);
      free(path_storage);
      emit_diag_reason("ROOT_BYTES_LIMIT");
      return 2;
    }
    if (total_bytes > PATHAUDIT_MAX_ROOT_BYTES) {
      free(roots);
      free(path_storage);
      emit_diag_reason("ROOT_BYTES_LIMIT");
      return 2;
    }

    if (index >= root_count) {
      free(roots);
      free(path_storage);
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }

    roots[index].text = start;
    roots[index].index = index;
    roots[index].len = len;
    index++;

    if (at_end) {
      break;
    }
    start = p + 1;
  }

  if (index != root_count) {
    free(roots);
    free(path_storage);
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }

  components->storage = path_storage;
  components->roots = roots;
  components->count = root_count;
  coalesce_inspection_path_fragments(components);
  return 0;
}

static int run_path_mode(void);

static bool command_name_is_valid(const char *name) {
  if (name[0] == '\0') {
    return false;
  }
  for (const unsigned char *p = (const unsigned char *)name; *p != '\0'; p++) {
    if (*p == '/') {
      return false;
    }
  }
  return true;
}

/*
 * Build dir/command candidate path. Empty PATH components search the cwd via
 * the bare command name (POSIX empty-field-as-"." search). Caller owns *out
 * on success. Returns 0 on success, 2 on allocation failure.
 * On success with an overlong candidate, *out is NULL (treated as no match).
 */
static int build_command_candidate(const struct Root *root, const char *command,
                                   char **out) {
  *out = NULL;
  size_t cmd_len = strlen(command);

  if (root->len == 0) {
    if (cmd_len > PATHAUDIT_MAX_ROOT_LENGTH) {
      return 0;
    }
    char *candidate = malloc(cmd_len + 1);
    if (candidate == NULL) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    memcpy(candidate, command, cmd_len + 1);
    *out = candidate;
    return 0;
  }

  bool need_slash = root->text[root->len - 1] != '/';
  size_t slash = need_slash ? (size_t)1 : (size_t)0;
  size_t total;
  if (!size_add_ok(root->len, slash, &total) ||
      !size_add_ok(total, cmd_len, &total)) {
    return 0;
  }
  if (total > PATHAUDIT_MAX_ROOT_LENGTH) {
    return 0;
  }

  char *candidate = malloc(total + 1);
  if (candidate == NULL) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  memcpy(candidate, root->text, root->len);
  size_t pos = root->len;
  if (need_slash) {
    candidate[pos++] = '/';
  }
  memcpy(candidate + pos, command, cmd_len + 1);
  *out = candidate;
  return 0;
}

static int emit_inspection_error_on_path(int err, const char *path) {
  char reason[64];
  int written = snprintf(reason, sizeof(reason), "INSPECTION_ERROR_%d", err);
  if (written < 0 || (size_t)written >= sizeof(reason)) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  emit_diag_reason_root(reason, path);
  return 2;
}

/*
 * True when candidate is a symlink whose readlink target is the bare command
 * basename (self-loop such as tool -> tool). Mutual directory stub loops
 * (loop-a <-> loop-b) are not self-basename loops.
 */
static bool symlink_is_self_basename(const char *candidate,
                                     const char *command) {
  struct stat lst;
  if (lstat(candidate, &lst) != 0 || !S_ISLNK(lst.st_mode)) {
    return false;
  }

  char target[PATHAUDIT_MAX_ROOT_LENGTH + 1];
  ssize_t n = readlink(candidate, target, sizeof(target) - 1);
  if (n < 0 || (size_t)n >= sizeof(target)) {
    return false;
  }
  target[n] = '\0';
  return strchr(target, '/') == NULL &&
         cmp_unsigned_bytes(target, command) == 0;
}

/* True when the PATH component itself fails lookup with err. */
static bool root_lookup_fails_with(const struct Root *root, int err) {
  if (root->len == 0) {
    return false;
  }
  struct stat st;
  errno = 0;
  return stat(root->text, &st) != 0 && errno == err;
}

/*
 * Scripts (#!) and ELF images are PATH executable candidates. Owner-+x data
 * files without an executable image are not treated as commands (matches the
 * non-executable decoy contract while still accepting install_executable
 * shebang plants and ELF binaries). Execute-only files that cannot be read
 * still count as candidates: magic is unavailable but X_OK already passed.
 */
static int probe_exec_image(const char *path, bool *is_image) {
  *is_image = false;
  int fd = open(path, O_RDONLY);
  if (fd < 0) {
    int err = errno;
    if (err == EACCES) {
      *is_image = true;
      return 0;
    }
    return err;
  }

  unsigned char hdr[4];
  ssize_t n = read(fd, hdr, sizeof(hdr));
  int read_err = errno;
  if (close(fd) != 0 && n >= 0) {
    /* ignore close errors after a successful read */
  }
  if (n < 0) {
    return read_err;
  }

  const bool shebang =
      n >= 2 && hdr[0] == (unsigned char)'#' && hdr[1] == (unsigned char)'!';
  const bool elf = n >= 4 && hdr[0] == 0x7fU && hdr[1] == (unsigned char)'E' &&
                   hdr[2] == (unsigned char)'L' && hdr[3] == (unsigned char)'F';
  if (shebang || elf) {
    *is_image = true;
  }
  return 0;
}

/*
 * If root/command names a regular executable, set *match_out to an owned
 * realpath string, *mode_out to the followed-target mode bits, and *uid_out
 * to the followed-target owner. Otherwise *match_out is NULL. Returns 0, or
 * 2 on fatal allocation / unsafe inspection failure (diagnostics emitted).
 * ENOENT/ENOTDIR and non-executable targets are silent non-matches.
 * Candidate-specific EACCES and self-basename ELOOP reject-close with
 * INSPECTION_ERROR_N naming the candidate path. When the PATH component
 * itself is uninspectable with the same errno, return a silent non-match so
 * component classification owns the diagnostic.
 */
static int try_command_match(const struct Root *root, const char *command,
                             char **match_out, mode_t *mode_out,
                             uid_t *uid_out) {
  *match_out = NULL;

  char *candidate = NULL;
  int build_status = build_command_candidate(root, command, &candidate);
  if (build_status != 0) {
    return build_status;
  }
  if (candidate == NULL) {
    return 0;
  }

  struct stat st;
  if (stat(candidate, &st) != 0) {
    int err = errno;
    if (err == ENOENT || err == ENOTDIR) {
      free(candidate);
      return 0;
    }
    if (root_lookup_fails_with(root, err)) {
      free(candidate);
      return 0;
    }
    if (err == ELOOP && !symlink_is_self_basename(candidate, command)) {
      /* Mutual symlink cycles discovered via readdir are not executables. */
      free(candidate);
      return 0;
    }
    int status = emit_inspection_error_on_path(err, candidate);
    free(candidate);
    return status;
  }

  if (!S_ISREG(st.st_mode) || access(candidate, X_OK) != 0) {
    free(candidate);
    return 0;
  }

  bool is_image = false;
  int image_err = probe_exec_image(candidate, &is_image);
  if (image_err != 0) {
    if (image_err == ENOENT || image_err == ENOTDIR) {
      free(candidate);
      return 0;
    }
    if (root_lookup_fails_with(root, image_err)) {
      free(candidate);
      return 0;
    }
    if (image_err == ELOOP && !symlink_is_self_basename(candidate, command)) {
      free(candidate);
      return 0;
    }
    int status = emit_inspection_error_on_path(image_err, candidate);
    free(candidate);
    return status;
  }
  if (!is_image) {
    free(candidate);
    return 0;
  }

  char *resolved_buf = malloc(PATHAUDIT_MAX_ROOT_LENGTH + 1);
  if (resolved_buf == NULL) {
    free(candidate);
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }

  errno = 0;
  if (realpath(candidate, resolved_buf) == NULL) {
    int err = errno;
    if (err == ENOMEM) {
      free(candidate);
      free(resolved_buf);
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    if (err == EACCES || err == ELOOP) {
      if (root_lookup_fails_with(root, err) ||
          (err == ELOOP && !symlink_is_self_basename(candidate, command))) {
        free(candidate);
        free(resolved_buf);
        return 0;
      }
      int status = emit_inspection_error_on_path(err, candidate);
      free(candidate);
      free(resolved_buf);
      return status;
    }
    free(candidate);
    free(resolved_buf);
    /* ENAMETOOLONG and other resolution failures: no match. */
    return 0;
  }
  free(candidate);

  /*
   * realpath requires PATHAUDIT_MAX_ROOT_LENGTH+1 scratch; retain only the
   * exact canonical text (strlen + 1) as winner/shadow/MATCH ownership.
   */
  char *owned_resolved = owned_strdup(resolved_buf);
  free(resolved_buf);
  if (owned_resolved == NULL) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }

  *match_out = owned_resolved;
  *mode_out = st.st_mode;
  *uid_out = st.st_uid;
  return 0;
}

/*
 * Apply the shared directory trust model to a resolved executable target:
 * S_IWGRP / S_IWOTH reuse GROUP_WRITABLE / WORLD_WRITABLE with the executable
 * realpath as the finding root. Owner-only write stays silent.
 */
static int append_executable_writability(const char *resolved, size_t index,
                                         mode_t mode,
                                         struct FindingBuffer *findings) {
  if ((mode & S_IWGRP) != 0) {
    if (!findings_append_owned(findings, resolved, index,
                               HAZARD_GROUP_WRITABLE)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
  }
  if ((mode & S_IWOTH) != 0) {
    if (!findings_append_owned(findings, resolved, index,
                               HAZARD_WORLD_WRITABLE)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
  }
  return 0;
}

/*
 * Same ownership trust policy as PATH directories: only root UID 0 and the
 * invoking real UID from getuid() are trusted. Every other final-target
 * owner is UNSAFE_OWNER naming the executable realpath. Uses followed-target
 * metadata (same st_uid as the successful stat that accepted the regular
 * executable).
 */
static int append_executable_ownership(const char *resolved, size_t index,
                                       uid_t owner,
                                       struct FindingBuffer *findings) {
  if (owner_uid_is_trusted(owner)) {
    return 0;
  }
  if (!findings_append_owned(findings, resolved, index, HAZARD_UNSAFE_OWNER)) {
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  return 0;
}

/*
 * Shared writability and ownership checks for one resolved executable target.
 * Writability findings use the existing GROUP/WORLD codes; ownership adds
 * UNSAFE_OWNER after them via code rank. Each finding owns its root copy.
 */
static int append_executable_trust_findings(const char *resolved, size_t index,
                                            mode_t mode, uid_t owner,
                                            struct FindingBuffer *findings) {
  int status = append_executable_writability(resolved, index, mode, findings);
  if (status != 0) {
    return status;
  }
  return append_executable_ownership(resolved, index, owner, findings);
}

/*
 * True when an exact (command, winner, shadow) tuple is already recorded.
 * Repeated PATH components that resolve to the same non-winner realpath must
 * not append a duplicate SHADOWED row. Lookup is O(1) amortized via the
 * (command, shadow) open-addressing index; winner is confirmed on hit.
 */
static bool shadow_tuple_recorded(const struct ShadowBuffer *shadows,
                                  const char *command, const char *winner,
                                  const char *shadow) {
  if (shadows->index_cap == 0 || shadows->index_slots == NULL) {
    return false;
  }

  const size_t mask = shadows->index_cap - 1;
  size_t slot = hash_command_shadow_pair(command, shadow) & mask;
  for (;;) {
    const size_t idx = shadows->index_slots[slot];
    if (idx == SIZE_MAX) {
      return false;
    }
    const struct ShadowRecord *item = &shadows->items[idx];
    if (cmp_unsigned_bytes(item->command, command) == 0 &&
        cmp_unsigned_bytes(item->shadow, shadow) == 0 &&
        cmp_unsigned_bytes(item->winner, winner) == 0) {
      return true;
    }
    slot = (slot + 1) & mask;
  }
}

/*
 * Record one regular executable discovered under a PATH component.
 * First PATH-order hit for a basename becomes the winner; later hits with a
 * distinct realpath are shadowed once each. Identical winner realpaths
 * (repeated components) do not self-shadow. Exact duplicate
 * (command, winner, shadow) tuples are suppressed.
 */
static int record_executable_hit(const char *command, char *owned_resolved,
                                 size_t path_index,
                                 struct WinnerBuffer *winners,
                                 struct ShadowBuffer *shadows) {
  const struct WinnerEntry *winner = winners_find(winners, command);
  if (winner != NULL) {
    if (cmp_unsigned_bytes(winner->path, owned_resolved) == 0) {
      free(owned_resolved);
      return 0;
    }

    if (shadow_tuple_recorded(shadows, command, winner->path, owned_resolved)) {
      free(owned_resolved);
      return 0;
    }

    char *command_copy = owned_strdup(command);
    char *winner_copy = owned_strdup(winner->path);
    if (command_copy == NULL || winner_copy == NULL) {
      free(command_copy);
      free(winner_copy);
      free(owned_resolved);
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    if (!shadows_append(shadows, command_copy, winner_copy, owned_resolved,
                        path_index)) {
      free(command_copy);
      free(winner_copy);
      free(owned_resolved);
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    return 0;
  }

  char *command_copy = owned_strdup(command);
  if (command_copy == NULL) {
    free(owned_resolved);
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  if (!winners_append(winners, command_copy, owned_resolved)) {
    free(command_copy);
    free(owned_resolved);
    emit_diag_reason("OUT_OF_MEMORY");
    return 2;
  }
  return 0;
}

/*
 * Scan one PATH component for regular executables. Empty, missing,
 * non-directory, and unreadable components are skipped without inventing
 * shadows. Does not recurse into nested directories. Applies the shared
 * writability and ownership trust model to each resolved executable target.
 */
static int scan_root_executables(const struct Root *root,
                                 struct WinnerBuffer *winners,
                                 struct ShadowBuffer *shadows,
                                 struct FindingBuffer *findings) {
  if (root->len == 0) {
    return 0;
  }

  struct stat st;
  if (stat(root->text, &st) != 0 || !S_ISDIR(st.st_mode)) {
    return 0;
  }

  DIR *dir = opendir(root->text);
  if (dir == NULL) {
    /* Unreadable directory: skip shadowing for this component safely. */
    return 0;
  }

  for (;;) {
    errno = 0;
    const struct dirent *entry = readdir(dir);
    if (entry == NULL) {
      if (errno != 0) {
        int err = errno;
        closedir(dir);
        char reason[64];
        int written =
            snprintf(reason, sizeof(reason), "INSPECTION_ERROR_%d", err);
        if (written < 0 || (size_t)written >= sizeof(reason)) {
          emit_diag_reason("OUT_OF_MEMORY");
          return 2;
        }
        emit_diag_reason_root(reason, root->text);
        return 2;
      }
      break;
    }

    const char *name = entry->d_name;
    if (name[0] == '\0') {
      continue;
    }
    if (name[0] == '.' &&
        (name[1] == '\0' || (name[1] == '.' && name[2] == '\0'))) {
      continue;
    }
    if (strchr(name, '/') != NULL) {
      continue;
    }

    char *match_path = NULL;
    mode_t mode = 0;
    uid_t owner = 0;
    int match_status =
        try_command_match(root, name, &match_path, &mode, &owner);
    if (match_status != 0) {
      closedir(dir);
      return match_status;
    }
    if (match_path == NULL) {
      continue;
    }

    int trust_status = append_executable_trust_findings(match_path, root->index,
                                                        mode, owner, findings);
    if (trust_status != 0) {
      free(match_path);
      closedir(dir);
      return trust_status;
    }

    int record_status =
        record_executable_hit(name, match_path, root->index, winners, shadows);
    if (record_status != 0) {
      closedir(dir);
      return record_status;
    }
  }

  if (closedir(dir) != 0) {
    /* close errors do not invent shadow findings */
  }
  return 0;
}

static int emit_shadow_lines(const struct ShadowBuffer *shadows) {
  for (size_t i = 0; i < shadows->len; i++) {
    const struct ShadowRecord *item = &shadows->items[i];
    if (fputs_checked("SHADOWED", stdout) != 0 ||
        fputc_checked('\t', stdout) != 0 ||
        put_escaped_quoted(stdout, item->command) != 0 ||
        fputc_checked('\t', stdout) != 0 ||
        put_escaped_quoted(stdout, item->winner) != 0 ||
        fputc_checked('\t', stdout) != 0 ||
        put_escaped_quoted(stdout, item->shadow) != 0 ||
        fputc_checked('\n', stdout) != 0) {
      return emit_stdout_write_error();
    }
  }
  return 0;
}

/*
 * Exclusive `pathaudit --path` mode.
 *
 * Classifies each PATH component with the shared directory-hazard taxonomy
 * (including PATH-directory / ancestor UNSAFE_OWNER under the shared trust
 * policy), then detects executable shadowing and applies the shared
 * writability and ownership trust model to resolved executable targets across
 * distinct PATH directories in PATH order. Directory and executable hazard
 * lines precede SHADOWED lines. SHADOWED lines are ordered by command basename
 * bytes, then by PATH position of the shadowed executable. Exit status 1 when
 * any directory hazard, executable writability/ownership finding, or shadow
 * is reported.
 *
 * Ownership: PathComponents aliases feed directory finding roots for
 * non-ownership hazards; directory-ownership and executable finding roots are
 * owned realpath copies. WinnerBuffer and ShadowBuffer own their strings. All
 * heap state is freed on every exit path.
 */
static int run_path_mode(void) {
  struct PathComponents components;
  int load_status = path_components_load(&components);
  if (load_status != 0) {
    return load_status;
  }

  struct FindingBuffer findings = {0};
  struct WinnerBuffer winners = {0};
  struct ShadowBuffer shadows = {0};

  /* Preserve PATH order: do not sort roots before classification or scan. */
  for (size_t i = 0; i < components.count; i++) {
    int class_status = classify_root(&components.roots[i], &findings, true);
    if (class_status != 0) {
      findings_free(&findings);
      winners_free(&winners);
      shadows_free(&shadows);
      path_components_free(&components);
      return class_status;
    }
  }

  for (size_t i = 0; i < components.count; i++) {
    int scan_status = scan_root_executables(&components.roots[i], &winners,
                                            &shadows, &findings);
    if (scan_status != 0) {
      findings_free(&findings);
      winners_free(&winners);
      shadows_free(&shadows);
      path_components_free(&components);
      return scan_status;
    }
  }

  if (findings.len > 1) {
    qsort(findings.items, findings.len, sizeof(findings.items[0]),
          compare_findings);
  }
  if (shadows.len > 1) {
    /* Positional index_slots do not survive reordering; scanning is done. */
    shadows_index_invalidate(&shadows);
    qsort(shadows.items, shadows.len, sizeof(shadows.items[0]),
          compare_shadows);
  }

  int write_status = emit_finding_lines(&findings);
  if (write_status == 0) {
    write_status = emit_shadow_lines(&shadows);
  }

  int status;
  if (write_status != 0) {
    status = write_status;
  } else {
    status = complete_stdout((findings.len == 0 && shadows.len == 0) ? 0 : 1);
  }

  findings_free(&findings);
  winners_free(&winners);
  shadows_free(&shadows);
  path_components_free(&components);
  return status;
}

/*
 * Command-query hazard classification: same taxonomy as classify_root, but
 * only appends findings that are applicable to a bounded command search.
 * Cwd-dependent codes always apply. Absolute MISSING/NON_DIRECTORY are
 * suppressed. Permission findings apply when this component produced a MATCH
 * or when no earlier MATCH exists (plant risk before the winner). The shared
 * ownership trust policy walks usable directories (and empty -> ".") under the
 * same applicability gate; shared ancestor realpaths dedup to the lowest
 * PATH index.
 */
static int classify_command_component(const struct Root *root,
                                      bool permission_applicable,
                                      struct FindingBuffer *findings) {
  bool cwd_dependent = root_is_cwd_dependent(root);

  if (root->len == 0) {
    if (!findings_append(findings, root->text, root->index,
                         HAZARD_EMPTY_ROOT)) {
      emit_diag_reason("OUT_OF_MEMORY");
      return 2;
    }
    /*
     * Empty fields search cwd. When plant-risk applicable, audit cwd
     * ownership under the shared policy without inventing a synthetic
     * directory hazard for "".
     */
    if (permission_applicable) {
      return append_directory_chain_ownership(".", root->index, findings);
    }
    return 0;
  }

  if (cwd_dependent) {
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
      if (cwd_dependent) {
        if (!findings_append(findings, root->text, root->index,
                             HAZARD_MISSING_ROOT)) {
          emit_diag_reason("OUT_OF_MEMORY");
          return 2;
        }
      }
      return 0;
    }
    if (err == ENOTDIR) {
      if (cwd_dependent) {
        if (!findings_append(findings, root->text, root->index,
                             HAZARD_NON_DIRECTORY_ROOT)) {
          emit_diag_reason("OUT_OF_MEMORY");
          return 2;
        }
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
    if (cwd_dependent) {
      if (!findings_append(findings, root->text, root->index,
                           HAZARD_NON_DIRECTORY_ROOT)) {
        emit_diag_reason("OUT_OF_MEMORY");
        return 2;
      }
    }
    return 0;
  }

  if (permission_applicable) {
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
    return append_directory_chain_ownership(root->text, root->index, findings);
  }
  return 0;
}

static int emit_command_query(const struct MatchBuffer *matches,
                              const struct FindingBuffer *findings) {
  for (size_t i = 0; i < matches->len; i++) {
    if (fputs_checked("MATCH", stdout) != 0 ||
        fputc_checked('\t', stdout) != 0 ||
        put_escaped_quoted(stdout, matches->paths[i]) != 0 ||
        fputc_checked('\n', stdout) != 0) {
      return emit_stdout_write_error();
    }
  }

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

/*
 * Exclusive `pathaudit --command NAME` mode.
 *
 * Walks PATH components in resolution order. MATCH lines name realpath'd
 * regular executables for this basename only. Hazard lines use the existing
 * taxonomy but only when applicable to the query (cwd-dependent entries,
 * permission plant-risk before the first MATCH, and permission findings on
 * match-bearing directories), plus the shared writability and ownership trust
 * model on each resolved MATCH target and on applicable PATH directories /
 * ancestors. Absolute MISSING/NON_DIRECTORY noise is omitted.
 *
 * Ownership: PathComponents storage aliases into directory finding roots for
 * non-ownership hazards; directory-ownership and executable finding roots are
 * owned realpath copies; MatchBuffer owns realpath strings. All heap state is
 * freed on every exit path.
 */
static int run_command_mode(const char *command) {
  if (!command_name_is_valid(command)) {
    emit_diag_reason_root("INVALID_COMMAND", command);
    return 2;
  }

  struct PathComponents components;
  int load_status = path_components_load(&components);
  if (load_status != 0) {
    return load_status;
  }

  struct MatchBuffer matches = {0};
  struct FindingBuffer findings = {0};
  bool seen_match = false;

  for (size_t i = 0; i < components.count; i++) {
    const struct Root *root = &components.roots[i];
    char *match_path = NULL;
    mode_t mode = 0;
    uid_t owner = 0;
    int match_status =
        try_command_match(root, command, &match_path, &mode, &owner);
    if (match_status != 0) {
      matches_free(&matches);
      findings_free(&findings);
      path_components_free(&components);
      return match_status;
    }

    bool has_match = (match_path != NULL);
    bool permission_applicable = has_match || !seen_match;

    int class_status =
        classify_command_component(root, permission_applicable, &findings);
    if (class_status != 0) {
      free(match_path);
      matches_free(&matches);
      findings_free(&findings);
      path_components_free(&components);
      return class_status;
    }

    if (has_match) {
      int trust_status = append_executable_trust_findings(
          match_path, root->index, mode, owner, &findings);
      if (trust_status != 0) {
        free(match_path);
        matches_free(&matches);
        findings_free(&findings);
        path_components_free(&components);
        return trust_status;
      }
      if (!matches_append(&matches, match_path)) {
        free(match_path);
        matches_free(&matches);
        findings_free(&findings);
        path_components_free(&components);
        emit_diag_reason("OUT_OF_MEMORY");
        return 2;
      }
      seen_match = true;
    }
  }

  if (findings.len > 1) {
    qsort(findings.items, findings.len, sizeof(findings.items[0]),
          compare_findings);
  }

  int status = emit_command_query(&matches, &findings);
  matches_free(&matches);
  findings_free(&findings);
  path_components_free(&components);
  return status;
}

static int run_explicit_roots(int argc, char **argv, int argi,
                              bool end_of_options) {
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

  if (argc >= 2 && strcmp(argv[1], "--path") == 0) {
    if (argc != 2) {
      emit_usage_diag("USAGE");
      return 2;
    }
    return run_path_mode();
  }

  if (argc >= 2 && strcmp(argv[1], "--command") == 0) {
    if (argc != 3) {
      emit_usage_diag("USAGE");
      return 2;
    }
    return run_command_mode(argv[2]);
  }

  int argi = 1;
  bool end_of_options = false;
  if (argi < argc && strcmp(argv[argi], "--") == 0) {
    end_of_options = true;
    argi++;
  }

  return run_explicit_roots(argc, argv, argi, end_of_options);
}
