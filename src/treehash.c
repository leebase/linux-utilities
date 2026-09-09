#ifndef _POSIX_C_SOURCE
/* NOLINTNEXTLINE(bugprone-reserved-identifier) */
#define _POSIX_C_SOURCE 200809L
#endif

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <fnmatch.h>
#include <limits.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#define TREEHASH_MAX_DEPTH 256
#define TREEHASH_IO_BUFFER_SIZE 65536

/* -------------------------------------------------------------------------
 * Embedded SHA-256 Implementation (FIPS 180-4)
 * ------------------------------------------------------------------------- */

typedef struct {
  uint32_t state[8];
  uint64_t count;
  uint8_t buffer[64];
} SHA256_CTX;

static const uint32_t K[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU,
    0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U, 0xd807aa98U, 0x12835b01U,
    0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U,
    0xc19bf174U, 0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU, 0x983e5152U,
    0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U,
    0x06ca6351U, 0x14292967U, 0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU,
    0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U,
    0xd6990624U, 0xf40e3585U, 0x106aa070U, 0x19a4c116U, 0x1e376c08U,
    0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU,
    0x682e6ff3U, 0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTR(x, 2) ^ ROTR(x, 13) ^ ROTR(x, 22))
#define EP1(x) (ROTR(x, 6) ^ ROTR(x, 11) ^ ROTR(x, 25))
#define SIG0(x) (ROTR(x, 7) ^ ROTR(x, 18) ^ ((x) >> 3))
#define SIG1(x) (ROTR(x, 17) ^ ROTR(x, 19) ^ ((x) >> 10))

static void sha256_transform(SHA256_CTX *ctx, const uint8_t data[64]) {
  uint32_t a = ctx->state[0];
  uint32_t b = ctx->state[1];
  uint32_t c = ctx->state[2];
  uint32_t d = ctx->state[3];
  uint32_t e = ctx->state[4];
  uint32_t f = ctx->state[5];
  uint32_t g = ctx->state[6];
  uint32_t h = ctx->state[7];
  uint32_t m[64];

  for (size_t i = 0; i < 16; i++) {
    m[i] = ((uint32_t)data[i * 4] << 24) | ((uint32_t)data[i * 4 + 1] << 16) |
           ((uint32_t)data[i * 4 + 2] << 8) | ((uint32_t)data[i * 4 + 3]);
  }
  for (size_t i = 16; i < 64; i++) {
    m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];
  }
  for (size_t i = 0; i < 64; i++) {
    uint32_t t1 = h + EP1(e) + CH(e, f, g) + K[i] + m[i];
    uint32_t t2 = EP0(a) + MAJ(a, b, c);
    h = g;
    g = f;
    f = e;
    e = d + t1;
    d = c;
    c = b;
    b = a;
    a = t1 + t2;
  }

  ctx->state[0] += a;
  ctx->state[1] += b;
  ctx->state[2] += c;
  ctx->state[3] += d;
  ctx->state[4] += e;
  ctx->state[5] += f;
  ctx->state[6] += g;
  ctx->state[7] += h;
}

static void sha256_init(SHA256_CTX *ctx) {
  ctx->state[0] = 0x6a09e667U;
  ctx->state[1] = 0xbb67ae85U;
  ctx->state[2] = 0x3c6ef372U;
  ctx->state[3] = 0xa54ff53aU;
  ctx->state[4] = 0x510e527fU;
  ctx->state[5] = 0x9b05688cU;
  ctx->state[6] = 0x1f83d9abU;
  ctx->state[7] = 0x5be0cd19U;
  ctx->count = 0;
}

static void sha256_update(SHA256_CTX *ctx, const void *data, size_t len) {
  const uint8_t *p = (const uint8_t *)data;
  size_t buffer_idx = (size_t)(ctx->count % 64);
  ctx->count += len;

  if (buffer_idx > 0) {
    size_t needed = 64 - buffer_idx;
    if (len < needed) {
      memcpy(&ctx->buffer[buffer_idx], p, len);
      return;
    }
    memcpy(&ctx->buffer[buffer_idx], p, needed);
    sha256_transform(ctx, ctx->buffer);
    p += needed;
    len -= needed;
  }

  while (len >= 64) {
    sha256_transform(ctx, p);
    p += 64;
    len -= 64;
  }

  if (len > 0) {
    memcpy(ctx->buffer, p, len);
  }
}

static void sha256_final(uint8_t hash[32], SHA256_CTX *ctx) {
  uint64_t total_bits = ctx->count * 8;
  size_t buffer_idx = (size_t)(ctx->count % 64);

  ctx->buffer[buffer_idx++] = 0x80;
  if (buffer_idx > 56) {
    memset(&ctx->buffer[buffer_idx], 0, 64 - buffer_idx);
    sha256_transform(ctx, ctx->buffer);
    memset(ctx->buffer, 0, 56);
  } else {
    memset(&ctx->buffer[buffer_idx], 0, 56 - buffer_idx);
  }

  for (size_t i = 0; i < 8; i++) {
    ctx->buffer[56 + i] = (uint8_t)((total_bits >> ((7 - i) * 8)) & 0xffU);
  }
  sha256_transform(ctx, ctx->buffer);

  for (size_t i = 0; i < 8; i++) {
    hash[i * 4] = (uint8_t)((ctx->state[i] >> 24) & 0xffU);
    hash[i * 4 + 1] = (uint8_t)((ctx->state[i] >> 16) & 0xffU);
    hash[i * 4 + 2] = (uint8_t)((ctx->state[i] >> 8) & 0xffU);
    hash[i * 4 + 3] = (uint8_t)(ctx->state[i] & 0xffU);
  }
}

/* -------------------------------------------------------------------------
 * Diagnostic Sanitization
 * ------------------------------------------------------------------------- */

static void print_sanitized(FILE *stream, const char *str) {
  if (!str)
    return;
  for (const unsigned char *p = (const unsigned char *)str; *p != '\0'; p++) {
    if (*p < 0x20 || *p > 0x7E || *p == '\\' || *p == '"') {
      fprintf(stream, "\\x%02X", *p);
    } else {
      fputc(*p, stream);
    }
  }
}

static void print_diag_path(const char *prefix, const char *path,
                            const char *suffix) {
  fputs(prefix, stderr);
  print_sanitized(stderr, path);
  fputs(suffix, stderr);
}

/* -------------------------------------------------------------------------
 * Data Structures & Context
 * ------------------------------------------------------------------------- */

struct FileEntry {
  char *rel_path;
  char hex[65];
};

struct FileEntryArray {
  struct FileEntry *items;
  size_t count;
  size_t capacity;
};

struct IgnoreRule {
  char *pattern;
  char *dir_rel;
  int depth;
  bool is_negated;
  bool is_dir_only;
  bool is_anchored;
};

struct IgnoreRuleArray {
  struct IgnoreRule *items;
  size_t count;
  size_t capacity;
};

struct AncestorNode {
  dev_t dev;
  ino_t ino;
};

struct TreehashContext {
  struct FileEntryArray entries;
  struct IgnoreRuleArray rules;
  struct AncestorNode ancestors[TREEHASH_MAX_DEPTH];
  size_t ancestor_count;
  uint8_t io_buffer[TREEHASH_IO_BUFFER_SIZE];
};

static void treehash_context_free(struct TreehashContext *ctx) {
  if (!ctx)
    return;
  for (size_t i = 0; i < ctx->entries.count; i++) {
    free(ctx->entries.items[i].rel_path);
  }
  free(ctx->entries.items);
  for (size_t i = 0; i < ctx->rules.count; i++) {
    free(ctx->rules.items[i].pattern);
    free(ctx->rules.items[i].dir_rel);
  }
  free(ctx->rules.items);
  free(ctx);
}

static int add_file_entry(struct FileEntryArray *arr, const char *rel_path,
                          const char *hex) {
  if (arr->count >= arr->capacity) {
    size_t new_cap = arr->capacity == 0 ? 64 : arr->capacity * 2;
    if (new_cap <= arr->capacity ||
        new_cap > SIZE_MAX / sizeof(struct FileEntry)) {
      return -1;
    }
    struct FileEntry *new_items =
        realloc(arr->items, new_cap * sizeof(struct FileEntry));
    if (!new_items) {
      return -1;
    }
    arr->items = new_items;
    arr->capacity = new_cap;
  }
  char *p = strdup(rel_path);
  if (!p) {
    return -1;
  }
  arr->items[arr->count].rel_path = p;
  memcpy(arr->items[arr->count].hex, hex, 65);
  arr->count++;
  return 0;
}

static int add_ignore_rule(struct IgnoreRuleArray *arr, const char *pattern,
                           const char *dir_rel, int depth, bool is_negated,
                           bool is_dir_only, bool is_anchored) {
  if (arr->count >= arr->capacity) {
    size_t new_cap = arr->capacity == 0 ? 32 : arr->capacity * 2;
    if (new_cap <= arr->capacity ||
        new_cap > SIZE_MAX / sizeof(struct IgnoreRule)) {
      return -1;
    }
    struct IgnoreRule *new_items =
        realloc(arr->items, new_cap * sizeof(struct IgnoreRule));
    if (!new_items) {
      return -1;
    }
    arr->items = new_items;
    arr->capacity = new_cap;
  }
  char *p = strdup(pattern);
  if (!p)
    return -1;
  char *d = strdup(dir_rel);
  if (!d) {
    free(p);
    return -1;
  }
  arr->items[arr->count].pattern = p;
  arr->items[arr->count].dir_rel = d;
  arr->items[arr->count].depth = depth;
  arr->items[arr->count].is_negated = is_negated;
  arr->items[arr->count].is_dir_only = is_dir_only;
  arr->items[arr->count].is_anchored = is_anchored;
  arr->count++;
  return 0;
}

static void pop_rules(struct TreehashContext *ctx, int depth) {
  size_t i = ctx->rules.count;
  while (i > 0) {
    if (ctx->rules.items[i - 1].depth == depth) {
      free(ctx->rules.items[i - 1].pattern);
      free(ctx->rules.items[i - 1].dir_rel);
      ctx->rules.count--;
      i--;
    } else {
      break;
    }
  }
}

static int compare_file_entries(const void *a, const void *b) {
  const struct FileEntry *fa = (const struct FileEntry *)a;
  const struct FileEntry *fb = (const struct FileEntry *)b;
  return strcmp(fa->rel_path, fb->rel_path);
}

static bool has_dotdot_segment(const char *path) {
  const char *p = path;
  while (*p) {
    if (p[0] == '.' && p[1] == '.') {
      if ((p == path || p[-1] == '/') && (p[2] == '/' || p[2] == '\0')) {
        return true;
      }
    }
    p++;
  }
  return false;
}

/* -------------------------------------------------------------------------
 * Hashing and Merkle Tree Reduction
 * ------------------------------------------------------------------------- */

static int hash_file_sha256(struct TreehashContext *ctx, const char *path,
                            char hex_out[65]) {
  int fd;
  do {
    fd = open(path, O_RDONLY | O_CLOEXEC);
  } while (fd < 0 && errno == EINTR);

  if (fd < 0) {
    return -1;
  }

  SHA256_CTX sctx;
  sha256_init(&sctx);

  while (1) {
    ssize_t n;
    do {
      n = read(fd, ctx->io_buffer, sizeof(ctx->io_buffer));
    } while (n < 0 && errno == EINTR);

    if (n < 0) {
      int save_errno = errno;
      close(fd);
      errno = save_errno;
      return -1;
    }
    if (n == 0) {
      break;
    }
    sha256_update(&sctx, ctx->io_buffer, (size_t)n);
  }

  if (close(fd) < 0) {
    return -1;
  }

  uint8_t hash[32];
  sha256_final(hash, &sctx);
  for (size_t i = 0; i < 32; i++) {
    sprintf(&hex_out[i * 2], "%02x", hash[i]);
  }
  hex_out[64] = '\0';
  return 0;
}

static void compute_leaf_digest(const char *file_hex, const char *rel_path,
                                uint8_t leaf_digest[32]) {
  SHA256_CTX sctx;
  sha256_init(&sctx);
  sha256_update(&sctx, file_hex, 64);
  sha256_update(&sctx, "  ", 2);
  sha256_update(&sctx, rel_path, strlen(rel_path));
  sha256_update(&sctx, "\n", 1);
  sha256_final(leaf_digest, &sctx);
}

static int compute_merkle_root(const struct FileEntryArray *entries,
                               char root_hex[65]) {
  if (entries->count == 0) {
    memcpy(root_hex,
           "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
           65);
    return 0;
  }

  size_t count = entries->count;
  if (count > SIZE_MAX / 32) {
    fputs("treehash: OUT_OF_MEMORY\n", stderr);
    return -1;
  }

  uint8_t(*current)[32] = malloc(count * 32);
  if (!current) {
    fputs("treehash: OUT_OF_MEMORY\n", stderr);
    return -1;
  }

  for (size_t i = 0; i < count; i++) {
    compute_leaf_digest(entries->items[i].hex, entries->items[i].rel_path,
                        current[i]);
  }

  while (count > 1) {
    size_t next_count = (count + 1) / 2;
    if (next_count > SIZE_MAX / 32) {
      free(current);
      fputs("treehash: OUT_OF_MEMORY\n", stderr);
      return -1;
    }
    uint8_t(*next_level)[32] = malloc(next_count * 32);
    if (!next_level) {
      free(current);
      fputs("treehash: OUT_OF_MEMORY\n", stderr);
      return -1;
    }

    size_t out_idx = 0;
    for (size_t i = 0; i < count; i += 2) {
      if (i + 1 < count) {
        SHA256_CTX sctx;
        sha256_init(&sctx);
        sha256_update(&sctx, current[i], 32);
        sha256_update(&sctx, current[i + 1], 32);
        sha256_final(next_level[out_idx], &sctx);
      } else {
        memcpy(next_level[out_idx], current[i], 32);
      }
      out_idx++;
    }

    free(current);
    current = next_level;
    count = next_count;
  }

  for (size_t i = 0; i < 32; i++) {
    sprintf(&root_hex[i * 2], "%02x", current[0][i]);
  }
  root_hex[64] = '\0';
  free(current);
  return 0;
}

/* -------------------------------------------------------------------------
 * Gitignore Parsing and Evaluation
 * ------------------------------------------------------------------------- */

static int load_gitignore(struct TreehashContext *ctx,
                          const char *gitignore_path, const char *rel_dir,
                          int depth) {
  FILE *f = fopen(gitignore_path, "r");
  if (!f) {
    if (errno == ENOENT) {
      return 0;
    }
    print_diag_path("treehash: cannot open '", gitignore_path, "': ");
    fputs(strerror(errno), stderr);
    fputc('\n', stderr);
    return 2;
  }

  char *line = NULL;
  size_t linecap = 0;
  ssize_t linelen;

  while ((linelen = getline(&line, &linecap, f)) >= 0) {
    while (linelen > 0 &&
           (line[linelen - 1] == '\r' || line[linelen - 1] == '\n' ||
            line[linelen - 1] == ' ' || line[linelen - 1] == '\t')) {
      line[--linelen] = '\0';
    }

    const char *trimmed = line;
    while (*trimmed == ' ' || *trimmed == '\t') {
      trimmed++;
    }
    if (*trimmed == '#' || *trimmed == '\0') {
      continue;
    }

    bool is_negated = false;
    const char *pat = line;
    if (*pat == '!') {
      is_negated = true;
      pat++;
    }

    size_t pat_len = strlen(pat);
    if (pat_len == 0) {
      continue;
    }

    char *pat_copy = malloc(pat_len + 1);
    if (!pat_copy) {
      free(line);
      fclose(f);
      fputs("treehash: OUT_OF_MEMORY\n", stderr);
      return -1;
    }
    memcpy(pat_copy, pat, pat_len + 1);

    bool is_dir_only = false;
    if (pat_copy[pat_len - 1] == '/') {
      is_dir_only = true;
      pat_copy[pat_len - 1] = '\0';
      pat_len--;
    }

    if (pat_len == 0) {
      free(pat_copy);
      continue;
    }

    bool is_anchored = false;
    const char *final_pat = pat_copy;
    if (pat_copy[0] == '/') {
      is_anchored = true;
      final_pat = pat_copy + 1;
    } else if (strchr(pat_copy, '/') != NULL) {
      is_anchored = true;
    }

    if (add_ignore_rule(&ctx->rules, final_pat, rel_dir, depth, is_negated,
                        is_dir_only, is_anchored) != 0) {
      free(pat_copy);
      free(line);
      fclose(f);
      fputs("treehash: OUT_OF_MEMORY\n", stderr);
      return -1;
    }
    free(pat_copy);
  }

  free(line);
  fclose(f);
  return 0;
}

static bool match_rule(const struct IgnoreRule *r, const char *cand_path,
                       bool cand_is_dir) {
  if (r->is_dir_only && !cand_is_dir) {
    return false;
  }

  const char *rel;
  if (r->dir_rel[0] != '\0') {
    size_t dlen = strlen(r->dir_rel);
    if (strncmp(cand_path, r->dir_rel, dlen) != 0) {
      return false;
    }
    if (cand_path[dlen] != '/' && cand_path[dlen] != '\0') {
      return false;
    }
    rel = (cand_path[dlen] == '/') ? cand_path + dlen + 1 : cand_path + dlen;
  } else {
    rel = cand_path;
  }

  if (rel[0] == '\0') {
    return false;
  }

  if (r->is_anchored) {
    if (fnmatch(r->pattern, rel, FNM_PATHNAME) == 0) {
      return true;
    }
  } else {
    const char *slash = strrchr(rel, '/');
    const char *base = slash ? slash + 1 : rel;
    if (fnmatch(r->pattern, base, 0) == 0) {
      return true;
    }
    if (fnmatch(r->pattern, rel, FNM_PATHNAME) == 0) {
      return true;
    }
  }

  return false;
}

static bool is_path_ignored(const struct TreehashContext *ctx,
                            const char *cand_path, bool cand_is_dir) {
  bool ignored = false;
  for (size_t i = 0; i < ctx->rules.count; i++) {
    if (match_rule(&ctx->rules.items[i], cand_path, cand_is_dir)) {
      ignored = !ctx->rules.items[i].is_negated;
    }
  }
  return ignored;
}

/* -------------------------------------------------------------------------
 * Directory Traversal Walker
 * ------------------------------------------------------------------------- */

static int walk_dir(struct TreehashContext *ctx, const char *disk_dir,
                    const char *rel_dir, int depth) {
  if (depth >= TREEHASH_MAX_DEPTH) {
    fputs("treehash: RECURSION_DEPTH_EXCEEDED\n", stderr);
    return 2;
  }

  struct stat dir_st;
  if (lstat(disk_dir, &dir_st) != 0) {
    print_diag_path("treehash: cannot access '", disk_dir, "': ");
    fputs(strerror(errno), stderr);
    fputc('\n', stderr);
    return 2;
  }
  if (!S_ISDIR(dir_st.st_mode)) {
    print_diag_path("treehash: '", disk_dir, "': Not a directory\n");
    return 2;
  }

  for (size_t i = 0; i < ctx->ancestor_count; i++) {
    if (ctx->ancestors[i].dev == dir_st.st_dev &&
        ctx->ancestors[i].ino == dir_st.st_ino) {
      print_diag_path("treehash: CYCLE_DETECTED: \"", disk_dir, "\"\n");
      return 2;
    }
  }

  ctx->ancestors[ctx->ancestor_count].dev = dir_st.st_dev;
  ctx->ancestors[ctx->ancestor_count].ino = dir_st.st_ino;
  ctx->ancestor_count++;

  DIR *dir = opendir(disk_dir);
  if (!dir) {
    print_diag_path("treehash: cannot open directory '", disk_dir, "': ");
    fputs(strerror(errno), stderr);
    fputc('\n', stderr);
    ctx->ancestor_count--;
    return 2;
  }

  char gitignore_path[PATH_MAX];
  int g_len = snprintf(gitignore_path, sizeof(gitignore_path), "%s/.gitignore",
                       disk_dir);
  if (g_len < 0 || g_len >= (int)sizeof(gitignore_path)) {
    closedir(dir);
    ctx->ancestor_count--;
    fputs("treehash: PATH_LENGTH_EXCEEDED\n", stderr);
    return 2;
  }

  struct stat gi_st;
  if (lstat(gitignore_path, &gi_st) == 0 && S_ISREG(gi_st.st_mode)) {
    int gres = load_gitignore(ctx, gitignore_path, rel_dir, depth);
    if (gres != 0) {
      closedir(dir);
      ctx->ancestor_count--;
      return gres;
    }
  }

  const struct dirent *entry;
  errno = 0;
  while ((entry = readdir(dir)) != NULL) {
    const char *name = entry->d_name;
    if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
      continue;
    }
    if (strcmp(name, ".git") == 0) {
      continue;
    }

    char child_disk[PATH_MAX];
    int d_len =
        snprintf(child_disk, sizeof(child_disk), "%s/%s", disk_dir, name);
    if (d_len < 0 || d_len >= (int)sizeof(child_disk)) {
      closedir(dir);
      pop_rules(ctx, depth);
      ctx->ancestor_count--;
      fputs("treehash: PATH_LENGTH_EXCEEDED\n", stderr);
      return 2;
    }

    char child_rel[PATH_MAX];
    int r_len;
    if (rel_dir[0] == '\0') {
      r_len = snprintf(child_rel, sizeof(child_rel), "%s", name);
    } else {
      r_len = snprintf(child_rel, sizeof(child_rel), "%s/%s", rel_dir, name);
    }
    if (r_len < 0 || r_len >= (int)sizeof(child_rel)) {
      closedir(dir);
      pop_rules(ctx, depth);
      ctx->ancestor_count--;
      fputs("treehash: PATH_LENGTH_EXCEEDED\n", stderr);
      return 2;
    }

    struct stat st;
    if (lstat(child_disk, &st) != 0) {
      print_diag_path("treehash: cannot access '", child_disk, "': ");
      fputs(strerror(errno), stderr);
      fputc('\n', stderr);
      closedir(dir);
      pop_rules(ctx, depth);
      ctx->ancestor_count--;
      return 2;
    }

    if (S_ISLNK(st.st_mode)) {
      continue;
    }

    if (S_ISDIR(st.st_mode)) {
      if (is_path_ignored(ctx, child_rel, true)) {
        continue;
      }
      int ret = walk_dir(ctx, child_disk, child_rel, depth + 1);
      if (ret != 0) {
        closedir(dir);
        pop_rules(ctx, depth);
        ctx->ancestor_count--;
        return ret;
      }
    } else if (S_ISREG(st.st_mode)) {
      if (is_path_ignored(ctx, child_rel, false)) {
        continue;
      }
      char hex[65];
      if (hash_file_sha256(ctx, child_disk, hex) != 0) {
        print_diag_path("treehash: cannot read '", child_disk, "': ");
        fputs(strerror(errno), stderr);
        fputc('\n', stderr);
        closedir(dir);
        pop_rules(ctx, depth);
        ctx->ancestor_count--;
        return 2;
      }
      if (add_file_entry(&ctx->entries, child_rel, hex) != 0) {
        fputs("treehash: OUT_OF_MEMORY\n", stderr);
        closedir(dir);
        pop_rules(ctx, depth);
        ctx->ancestor_count--;
        return 2;
      }
    }
    errno = 0;
  }

  if (errno != 0) {
    print_diag_path("treehash: cannot read directory '", disk_dir, "': ");
    fputs(strerror(errno), stderr);
    fputc('\n', stderr);
    closedir(dir);
    pop_rules(ctx, depth);
    ctx->ancestor_count--;
    return 2;
  }

  closedir(dir);
  pop_rules(ctx, depth);
  ctx->ancestor_count--;
  return 0;
}

/* -------------------------------------------------------------------------
 * Usage Guidance and Entry Point
 * ------------------------------------------------------------------------- */

static void print_usage(void) {
  printf(
      "Usage: treehash [OPTIONS] [WORKSPACE_DIR]\n"
      "\n"
      "Compute deterministic SHA-256 Merkle tree root hash and pin manifest.\n"
      "\n"
      "Options:\n"
      "  --help     Display this help and exit\n"
      "  --version  Output version information and exit\n");
}

static void print_version(void) { printf("treehash 0.1.0\n"); }

int main(int argc, char **argv) {
  signal(SIGPIPE, SIG_IGN);

  const char *raw_operand = NULL;

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--help") == 0) {
      if (argc == 2) {
        print_usage();
        return 0;
      }
      fputs(
          "treehash: cannot combine '--help' with operands or other options\n",
          stderr);
      return 2;
    }
    if (strcmp(argv[i], "--version") == 0) {
      if (argc == 2) {
        print_version();
        return 0;
      }
      fputs("treehash: cannot combine '--version' with operands or other "
            "options\n",
            stderr);
      return 2;
    }
    if (argv[i][0] == '-') {
      print_diag_path("treehash: unknown option '", argv[i], "'\n");
      return 2;
    }
    if (!raw_operand) {
      raw_operand = argv[i];
    } else {
      fputs("treehash: too many arguments; expected at most one workspace "
            "directory\n",
            stderr);
      return 2;
    }
  }

  if (!raw_operand) {
    raw_operand = ".";
  }

  if (raw_operand[0] == '\0') {
    fputs("treehash: invalid empty workspace directory\n", stderr);
    return 2;
  }

  if (has_dotdot_segment(raw_operand)) {
    print_diag_path("treehash: PATH_ESCAPE: \"", raw_operand, "\"\n");
    return 2;
  }

  char norm_dir[PATH_MAX];
  size_t op_len = strlen(raw_operand);
  if (op_len >= sizeof(norm_dir)) {
    fputs("treehash: PATH_LENGTH_EXCEEDED\n", stderr);
    return 2;
  }
  memcpy(norm_dir, raw_operand, op_len + 1);

  size_t nlen = op_len;
  while (nlen > 1) {
    if (norm_dir[nlen - 1] == '/') {
      norm_dir[nlen - 1] = '\0';
      nlen--;
    } else if (norm_dir[nlen - 2] == '/' && norm_dir[nlen - 1] == '.') {
      norm_dir[nlen - 2] = '\0';
      nlen -= 2;
    } else {
      break;
    }
  }
  if (nlen == 0) {
    strcpy(norm_dir, ".");
  }

  struct stat root_st;
  if (lstat(norm_dir, &root_st) != 0) {
    print_diag_path("treehash: cannot access '", raw_operand, "': ");
    fputs(strerror(errno), stderr);
    fputc('\n', stderr);
    return 2;
  }
  if (!S_ISDIR(root_st.st_mode)) {
    print_diag_path("treehash: '", raw_operand, "': Not a directory\n");
    return 2;
  }

  struct TreehashContext *ctx = calloc(1, sizeof(*ctx));
  if (!ctx) {
    fputs("treehash: OUT_OF_MEMORY\n", stderr);
    return 2;
  }

  int walk_res = walk_dir(ctx, norm_dir, "", 0);
  if (walk_res != 0) {
    treehash_context_free(ctx);
    return 2;
  }

  if (ctx->entries.count > 0) {
    qsort(ctx->entries.items, ctx->entries.count, sizeof(struct FileEntry),
          compare_file_entries);
  }

  char root_hex[65];
  if (compute_merkle_root(&ctx->entries, root_hex) != 0) {
    treehash_context_free(ctx);
    return 2;
  }

  if (printf("ROOT %s\n", root_hex) < 0) {
    treehash_context_free(ctx);
    return 2;
  }

  for (size_t i = 0; i < ctx->entries.count; i++) {
    if (printf("%s  %s\n", ctx->entries.items[i].hex,
               ctx->entries.items[i].rel_path) < 0) {
      treehash_context_free(ctx);
      return 2;
    }
  }

  if (fflush(stdout) != 0 || ferror(stdout)) {
    treehash_context_free(ctx);
    return 2;
  }

  treehash_context_free(ctx);
  return 0;
}
