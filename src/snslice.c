/*
 * snslice - Partition NDJSON and CSV streams on complete record boundaries.
 *
 * Conformance: ISO C17 (-std=c17), POSIX.1-2008 (_POSIX_C_SOURCE=200809L),
 *              64-bit file offsets (_FILE_OFFSET_BITS=64).
 *
 * Memory Ownership and Allocation:
 * - Constant O(1) resident memory regardless of total stream volume.
 * - Zero dynamic heap allocation (malloc/calloc/free).
 * - Fixed 64 KiB static streaming buffer (SNSLICE_IO_BUFFER_SIZE).
 * - Fixed stack/static path buffers bounded by PATH_MAX.
 * - Command-line argument strings are borrowed from argv and never mutated.
 *
 * File Descriptor Ownership:
 * - At most two descriptors open concurrently: input_fd and active_chunk_fd.
 * - Chunk files created atomically with O_CREAT | O_EXCL | O_WRONLY (mode
 * 0644).
 * - Collision detection fail-closed on EEXIST (OUTPUT_COLLISION).
 * - Completed chunks closed immediately before opening subsequent chunks.
 * - Incomplete active chunk unlinked (unlink) on any error before exit.
 * - Process-wide SIGPIPE ignored; broken pipes surface as EPIPE (BROKEN_PIPE).
 *
 * Closed Hazard Taxonomy (16 members):
 * USAGE_ERROR, UNKNOWN_OPTION, INVALID_LIMIT, INVALID_FORMAT,
 * INPUT_NOT_FOUND, INPUT_IS_DIRECTORY, INPUT_READ_ERROR, RECORD_LENGTH_LIMIT,
 * MALFORMED_NDJSON, MALFORMED_CSV, OUTPUT_DIR_ERROR, OUTPUT_COLLISION,
 * CHUNK_OPEN_ERROR, CHUNK_WRITE_ERROR, OUT_OF_MEMORY, BROKEN_PIPE.
 */

#ifndef _POSIX_C_SOURCE
/* NOLINTNEXTLINE(bugprone-reserved-identifier) */
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef _FILE_OFFSET_BITS
/* NOLINTNEXTLINE(bugprone-reserved-identifier) */
#define _FILE_OFFSET_BITS 64
#endif

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define SNSLICE_IO_BUFFER_SIZE 65536
#define SNSLICE_MAX_RECORD_BYTES 16777216

#define HAZARD_USAGE_ERROR "USAGE_ERROR"
#define HAZARD_UNKNOWN_OPTION "UNKNOWN_OPTION"
#define HAZARD_INVALID_LIMIT "INVALID_LIMIT"
#define HAZARD_INVALID_FORMAT "INVALID_FORMAT"
#define HAZARD_INPUT_NOT_FOUND "INPUT_NOT_FOUND"
#define HAZARD_INPUT_IS_DIRECTORY "INPUT_IS_DIRECTORY"
#define HAZARD_INPUT_READ_ERROR "INPUT_READ_ERROR"
#define HAZARD_RECORD_LENGTH_LIMIT "RECORD_LENGTH_LIMIT"
#define HAZARD_MALFORMED_NDJSON "MALFORMED_NDJSON"
#define HAZARD_MALFORMED_CSV "MALFORMED_CSV"
#define HAZARD_OUTPUT_DIR_ERROR "OUTPUT_DIR_ERROR"
#define HAZARD_OUTPUT_COLLISION "OUTPUT_COLLISION"
#define HAZARD_CHUNK_OPEN_ERROR "CHUNK_OPEN_ERROR"
#define HAZARD_CHUNK_WRITE_ERROR "CHUNK_WRITE_ERROR"
#define HAZARD_OUT_OF_MEMORY "OUT_OF_MEMORY"
#define HAZARD_BROKEN_PIPE "BROKEN_PIPE"

typedef enum { FORMAT_NDJSON, FORMAT_CSV } FormatType;

typedef enum {
  CSV_STATE_START,
  CSV_STATE_UNQUOTED,
  CSV_STATE_QUOTED,
  CSV_STATE_ESCAPED_QUOTE
} CsvState;

typedef struct {
  FormatType format;
  size_t limit_bytes;
  size_t limit_records;
  const char *out_dir;
  const char *prefix;
  const char *input_path;
} SnSliceConfig;

typedef struct {
  int input_fd;
  bool close_input_fd;
  int active_chunk_fd;
  char active_chunk_path[PATH_MAX];
  size_t chunk_index;
  size_t chunk_bytes;
  size_t chunk_records;
  size_t record_bytes;
  uint64_t total_input_bytes;
  CsvState csv_state;
} SnSliceState;

static char io_buffer[SNSLICE_IO_BUFFER_SIZE];

/*
 * Convert untrusted bytes outside 0x20..0x7E, plus quotes and backslashes,
 * into uppercase hexadecimal \xHH sequences to prevent ANSI terminal injection.
 */
static void sanitize_string(const char *src, char *dst, size_t dst_size) {
  if (dst_size == 0) {
    return;
  }
  size_t d = 0;
  if (src != NULL) {
    for (size_t s = 0; src[s] != '\0' && d + 5 < dst_size; s++) {
      unsigned char b = (unsigned char)src[s];
      if (b == '"') {
        dst[d++] = '\\';
        dst[d++] = 'x';
        dst[d++] = '2';
        dst[d++] = '2';
      } else if (b == '\\') {
        dst[d++] = '\\';
        dst[d++] = 'x';
        dst[d++] = '5';
        dst[d++] = 'C';
      } else if (b >= 0x20 && b <= 0x7E) {
        dst[d++] = (char)b;
      } else {
        static const char hex[] = "0123456789ABCDEF";
        dst[d++] = '\\';
        dst[d++] = 'x';
        dst[d++] = hex[(b >> 4) & 0x0F];
        dst[d++] = hex[b & 0x0F];
      }
    }
  }
  dst[d] = '\0';
}

static void emit_diagnostic(const char *hazard, const char *fmt, ...) {
  char details[2048];
  va_list args;
  va_start(args, fmt);
  vsnprintf(details, sizeof(details), fmt, args);
  va_end(args);
  fprintf(stderr, "snslice: %s: %s\n", hazard, details);
}

static void print_help(void) {
  printf(
      "Usage: snslice [OPTIONS] [INPUT_FILE]\n\n"
      "Partition Newline-Delimited JSON (NDJSON) or CSV streams into chunk "
      "files.\n\n"
      "Options:\n"
      "  -b, --bytes BYTES       Chunk size threshold in bytes\n"
      "  -r, --records COUNT     Chunk size threshold in record count\n"
      "  -f, --format FORMAT     Input format: ndjson (default) or csv\n"
      "  -d, --out-dir DIR       Output directory for chunk files (default: "
      ".)\n"
      "  -p, --prefix PREFIX     Output chunk filename prefix (default: "
      "chunk_)\n"
      "      --help              Display this help and exit\n"
      "      --version           Output version information and exit\n\n"
      "If INPUT_FILE is omitted or '-', snslice reads from standard input.\n");
}

static void print_version(void) { printf("snslice 0.1.0\n"); }

/*
 * Parse a strictly positive integer within 1..SIZE_MAX.
 * Rejects leading whitespace, signs (+/-), non-digit characters, 0, and
 * overflow.
 */
static bool parse_positive_size(const char *str, size_t *out) {
  if (str == NULL || *str == '\0') {
    return false;
  }
  if (*str < '0' || *str > '9') {
    return false;
  }
  errno = 0;
  char *endptr = NULL;
  unsigned long long val = strtoull(str, &endptr, 10);
  if (errno == ERANGE || *endptr != '\0' || endptr == str || val == 0 ||
      val > SIZE_MAX) {
    return false;
  }
  *out = (size_t)val;
  return true;
}

static void abort_cleanup(SnSliceState *st) {
  if (st->active_chunk_fd >= 0) {
    close(st->active_chunk_fd);
    st->active_chunk_fd = -1;
    if (st->active_chunk_path[0] != '\0') {
      unlink(st->active_chunk_path);
      st->active_chunk_path[0] = '\0';
    }
  }
  if (st->close_input_fd && st->input_fd >= 0) {
    close(st->input_fd);
    st->input_fd = -1;
  }
}

static int open_chunk(const SnSliceConfig *cfg, SnSliceState *st) {
  const char *ext = (cfg->format == FORMAT_NDJSON) ? "ndjson" : "csv";
  size_t dirlen = strlen(cfg->out_dir);
  int n;
  if (dirlen > 0 && cfg->out_dir[dirlen - 1] == '/') {
    n = snprintf(st->active_chunk_path, sizeof(st->active_chunk_path),
                 "%s%s%05zu.%s", cfg->out_dir, cfg->prefix, st->chunk_index,
                 ext);
  } else {
    n = snprintf(st->active_chunk_path, sizeof(st->active_chunk_path),
                 "%s/%s%05zu.%s", cfg->out_dir, cfg->prefix, st->chunk_index,
                 ext);
  }
  if (n < 0 || (size_t)n >= sizeof(st->active_chunk_path)) {
    char san[1024];
    sanitize_string(cfg->out_dir, san, sizeof(san));
    emit_diagnostic(HAZARD_OUTPUT_DIR_ERROR,
                    "path length exceeds maximum limit: '%s'", san);
    st->active_chunk_path[0] = '\0';
    return -1;
  }

  int fd = open(st->active_chunk_path, O_CREAT | O_EXCL | O_WRONLY, 0644);
  if (fd < 0) {
    char san[PATH_MAX * 4];
    sanitize_string(st->active_chunk_path, san, sizeof(san));
    if (errno == EEXIST) {
      emit_diagnostic(HAZARD_OUTPUT_COLLISION, "\"%s\"", san);
    } else {
      emit_diagnostic(HAZARD_CHUNK_OPEN_ERROR, "failed to open '%s': %s", san,
                      strerror(errno));
    }
    st->active_chunk_path[0] = '\0';
    return -1;
  }

  st->active_chunk_fd = fd;
  return 0;
}

static int close_chunk(SnSliceState *st) {
  if (st->active_chunk_fd < 0) {
    return 0;
  }
  int res = close(st->active_chunk_fd);
  st->active_chunk_fd = -1;
  if (res != 0) {
    char san[PATH_MAX * 4];
    sanitize_string(st->active_chunk_path, san, sizeof(san));
    unlink(st->active_chunk_path);
    st->active_chunk_path[0] = '\0';
    emit_diagnostic(HAZARD_CHUNK_WRITE_ERROR,
                    "failed to close chunk file: '%s'", san);
    return -1;
  }
  st->active_chunk_path[0] = '\0';
  st->chunk_index++;
  st->chunk_bytes = 0;
  st->chunk_records = 0;
  return 0;
}

static ssize_t write_all(int fd, const void *buf, size_t count) {
  const char *p = (const char *)buf;
  size_t total = 0;
  while (total < count) {
    ssize_t n = write(fd, p + total, count - total);
    if (n < 0) {
      if (errno == EINTR) {
        continue;
      }
      return -1;
    }
    if (n == 0) {
      return -1;
    }
    total += (size_t)n;
  }
  return (ssize_t)total;
}

static int write_to_chunk(const SnSliceConfig *cfg, SnSliceState *st,
                          const char *data, size_t len) {
  if (len == 0) {
    return 0;
  }
  if (st->active_chunk_fd < 0) {
    if (open_chunk(cfg, st) != 0) {
      return -1;
    }
  }
  if (write_all(st->active_chunk_fd, data, len) < 0) {
    char san[PATH_MAX * 4];
    sanitize_string(st->active_chunk_path, san, sizeof(san));
    int save_errno = errno;
    abort_cleanup(st);
    if (save_errno == EPIPE) {
      emit_diagnostic(HAZARD_BROKEN_PIPE,
                      "output pipe broken while writing to '%s'", san);
    } else {
      emit_diagnostic(HAZARD_CHUNK_WRITE_ERROR, "failed to write to '%s': %s",
                      san, strerror(save_errno));
    }
    return -1;
  }
  st->chunk_bytes += len;
  return 0;
}

static int stream_slice(const SnSliceConfig *cfg, SnSliceState *st) {
  while (1) {
    ssize_t nread = read(st->input_fd, io_buffer, sizeof(io_buffer));
    if (nread < 0) {
      if (errno == EINTR) {
        continue;
      }
      int save_errno = errno;
      abort_cleanup(st);
      emit_diagnostic(HAZARD_INPUT_READ_ERROR, "read error: %s",
                      strerror(save_errno));
      return -1;
    }
    if (nread == 0) {
      break;
    }

    st->total_input_bytes += (size_t)nread;
    size_t slice_start = 0;

    for (size_t i = 0; i < (size_t)nread; i++) {
      unsigned char c = (unsigned char)io_buffer[i];

      if (c == '\0') {
        abort_cleanup(st);
        if (cfg->format == FORMAT_NDJSON) {
          emit_diagnostic(HAZARD_MALFORMED_NDJSON,
                          "embedded NUL byte detected");
        } else {
          emit_diagnostic(HAZARD_MALFORMED_CSV, "embedded NUL byte detected");
        }
        return -1;
      }

      st->record_bytes++;
      if (st->record_bytes > SNSLICE_MAX_RECORD_BYTES) {
        abort_cleanup(st);
        emit_diagnostic(HAZARD_RECORD_LENGTH_LIMIT,
                        "record exceeds 16 MiB limit");
        return -1;
      }

      bool is_record_boundary = false;

      if (cfg->format == FORMAT_NDJSON) {
        if (c == '\n') {
          is_record_boundary = true;
        }
      } else {
        switch (st->csv_state) {
        case CSV_STATE_START:
          if (c == '"') {
            st->csv_state = CSV_STATE_QUOTED;
          } else if (c == '\n') {
            is_record_boundary = true;
            st->csv_state = CSV_STATE_START;
          } else if (c == ',' || c == '\r') {
            st->csv_state = CSV_STATE_START;
          } else {
            st->csv_state = CSV_STATE_UNQUOTED;
          }
          break;

        case CSV_STATE_UNQUOTED:
          if (c == ',') {
            st->csv_state = CSV_STATE_START;
          } else if (c == '\n') {
            is_record_boundary = true;
            st->csv_state = CSV_STATE_START;
          } else {
            st->csv_state = CSV_STATE_UNQUOTED;
          }
          break;

        case CSV_STATE_QUOTED:
          if (c == '"') {
            st->csv_state = CSV_STATE_ESCAPED_QUOTE;
          }
          break;

        case CSV_STATE_ESCAPED_QUOTE:
          if (c == '"') {
            st->csv_state = CSV_STATE_QUOTED;
          } else if (c == ',') {
            st->csv_state = CSV_STATE_START;
          } else if (c == '\n') {
            is_record_boundary = true;
            st->csv_state = CSV_STATE_START;
          } else if (c == '\r') {
            st->csv_state = CSV_STATE_ESCAPED_QUOTE;
          } else {
            abort_cleanup(st);
            emit_diagnostic(HAZARD_MALFORMED_CSV,
                            "invalid character after closing quote");
            return -1;
          }
          break;
        }
      }

      if (is_record_boundary) {
        size_t slice_len = i - slice_start + 1;
        if (write_to_chunk(cfg, st, io_buffer + slice_start, slice_len) != 0) {
          return -1;
        }
        slice_start = i + 1;
        st->record_bytes = 0;
        st->chunk_records++;

        bool should_split = false;
        if (cfg->limit_bytes > 0 && st->chunk_bytes >= cfg->limit_bytes) {
          should_split = true;
        }
        if (cfg->limit_records > 0) {
          if (cfg->format == FORMAT_CSV && cfg->limit_records == 1 &&
              st->chunk_index == 1) {
            if (st->chunk_records > 1) {
              should_split = true;
            }
          } else if (st->chunk_records >= cfg->limit_records) {
            should_split = true;
          }
        }
        if (should_split) {
          if (close_chunk(st) != 0) {
            return -1;
          }
        }
      }
    }

    if (slice_start < (size_t)nread) {
      size_t remaining_len = (size_t)nread - slice_start;
      if (write_to_chunk(cfg, st, io_buffer + slice_start, remaining_len) !=
          0) {
        return -1;
      }
    }
  }

  if (st->total_input_bytes == 0) {
    return 0;
  }

  if (cfg->format == FORMAT_NDJSON) {
    if (st->record_bytes > 0) {
      abort_cleanup(st);
      emit_diagnostic(HAZARD_MALFORMED_NDJSON, "unterminated record at EOF");
      return -1;
    }
    if (close_chunk(st) != 0) {
      return -1;
    }
  } else {
    if (st->csv_state == CSV_STATE_QUOTED) {
      abort_cleanup(st);
      emit_diagnostic(HAZARD_MALFORMED_CSV, "unterminated quoted field at EOF");
      return -1;
    }
    if (st->record_bytes > 0) {
      st->chunk_records++;
    }
    if (close_chunk(st) != 0) {
      return -1;
    }
  }

  return 0;
}

int main(int argc, char **argv) {
  signal(SIGPIPE, SIG_IGN);

  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "--version") == 0) {
      if (argc == 2) {
        if (strcmp(argv[1], "--help") == 0) {
          print_help();
        } else {
          print_version();
        }
        return 0;
      } else {
        char san[1024];
        sanitize_string(argv[i], san, sizeof(san));
        emit_diagnostic(
            HAZARD_USAGE_ERROR,
            "informational option '%s' cannot be combined with other arguments",
            san);
        return 2;
      }
    }
  }

  SnSliceConfig cfg = {
      .format = FORMAT_NDJSON,
      .limit_bytes = 0,
      .limit_records = 0,
      .out_dir = ".",
      .prefix = "chunk_",
      .input_path = NULL,
  };

  bool stop_options = false;
  for (int i = 1; i < argc; i++) {
    const char *arg = argv[i];
    if (!stop_options && strcmp(arg, "--") == 0) {
      stop_options = true;
      continue;
    }
    if (!stop_options && arg[0] == '-' && arg[1] != '\0') {
      if (strcmp(arg, "-b") == 0 || strcmp(arg, "--bytes") == 0) {
        if (i + 1 >= argc) {
          char san[1024];
          sanitize_string(arg, san, sizeof(san));
          emit_diagnostic(HAZARD_USAGE_ERROR,
                          "option '%s' requires an argument", san);
          return 2;
        }
        i++;
        if (!parse_positive_size(argv[i], &cfg.limit_bytes)) {
          char san[1024];
          sanitize_string(argv[i], san, sizeof(san));
          emit_diagnostic(HAZARD_INVALID_LIMIT, "invalid bytes limit: '%s'",
                          san);
          return 2;
        }
      } else if (strncmp(arg, "--bytes=", 8) == 0) {
        const char *val = arg + 8;
        if (!parse_positive_size(val, &cfg.limit_bytes)) {
          char san[1024];
          sanitize_string(val, san, sizeof(san));
          emit_diagnostic(HAZARD_INVALID_LIMIT, "invalid bytes limit: '%s'",
                          san);
          return 2;
        }
      } else if (strcmp(arg, "-r") == 0 || strcmp(arg, "--records") == 0) {
        if (i + 1 >= argc) {
          char san[1024];
          sanitize_string(arg, san, sizeof(san));
          emit_diagnostic(HAZARD_USAGE_ERROR,
                          "option '%s' requires an argument", san);
          return 2;
        }
        i++;
        if (!parse_positive_size(argv[i], &cfg.limit_records)) {
          char san[1024];
          sanitize_string(argv[i], san, sizeof(san));
          emit_diagnostic(HAZARD_INVALID_LIMIT, "invalid records limit: '%s'",
                          san);
          return 2;
        }
      } else if (strncmp(arg, "--records=", 10) == 0) {
        const char *val = arg + 10;
        if (!parse_positive_size(val, &cfg.limit_records)) {
          char san[1024];
          sanitize_string(val, san, sizeof(san));
          emit_diagnostic(HAZARD_INVALID_LIMIT, "invalid records limit: '%s'",
                          san);
          return 2;
        }
      } else if (strcmp(arg, "-f") == 0 || strcmp(arg, "--format") == 0) {
        if (i + 1 >= argc) {
          char san[1024];
          sanitize_string(arg, san, sizeof(san));
          emit_diagnostic(HAZARD_USAGE_ERROR,
                          "option '%s' requires an argument", san);
          return 2;
        }
        i++;
        if (strcmp(argv[i], "ndjson") == 0) {
          cfg.format = FORMAT_NDJSON;
        } else if (strcmp(argv[i], "csv") == 0) {
          cfg.format = FORMAT_CSV;
        } else {
          char san[1024];
          sanitize_string(argv[i], san, sizeof(san));
          emit_diagnostic(HAZARD_INVALID_FORMAT, "invalid format: '%s'", san);
          return 2;
        }
      } else if (strncmp(arg, "--format=", 9) == 0) {
        const char *val = arg + 9;
        if (strcmp(val, "ndjson") == 0) {
          cfg.format = FORMAT_NDJSON;
        } else if (strcmp(val, "csv") == 0) {
          cfg.format = FORMAT_CSV;
        } else {
          char san[1024];
          sanitize_string(val, san, sizeof(san));
          emit_diagnostic(HAZARD_INVALID_FORMAT, "invalid format: '%s'", san);
          return 2;
        }
      } else if (strcmp(arg, "-d") == 0 || strcmp(arg, "--out-dir") == 0) {
        if (i + 1 >= argc) {
          char san[1024];
          sanitize_string(arg, san, sizeof(san));
          emit_diagnostic(HAZARD_USAGE_ERROR,
                          "option '%s' requires an argument", san);
          return 2;
        }
        i++;
        cfg.out_dir = argv[i];
      } else if (strncmp(arg, "--out-dir=", 10) == 0) {
        cfg.out_dir = arg + 10;
      } else if (strcmp(arg, "-p") == 0 || strcmp(arg, "--prefix") == 0) {
        if (i + 1 >= argc) {
          char san[1024];
          sanitize_string(arg, san, sizeof(san));
          emit_diagnostic(HAZARD_USAGE_ERROR,
                          "option '%s' requires an argument", san);
          return 2;
        }
        i++;
        cfg.prefix = argv[i];
      } else if (strncmp(arg, "--prefix=", 9) == 0) {
        cfg.prefix = arg + 9;
      } else {
        char san[1024];
        sanitize_string(arg, san, sizeof(san));
        emit_diagnostic(HAZARD_UNKNOWN_OPTION, "unrecognized option '%s'", san);
        return 2;
      }
    } else {
      if (cfg.input_path != NULL) {
        char san[1024];
        sanitize_string(arg, san, sizeof(san));
        emit_diagnostic(HAZARD_USAGE_ERROR,
                        "unexpected positional argument '%s'", san);
        return 2;
      }
      cfg.input_path = arg;
    }
  }

  if (cfg.prefix == NULL || cfg.prefix[0] == '\0' ||
      strchr(cfg.prefix, '/') != NULL || strstr(cfg.prefix, "..") != NULL) {
    char san[1024];
    sanitize_string(cfg.prefix ? cfg.prefix : "", san, sizeof(san));
    emit_diagnostic(HAZARD_USAGE_ERROR, "invalid prefix: '%s'", san);
    return 2;
  }

  if (cfg.limit_bytes == 0 && cfg.limit_records == 0) {
    emit_diagnostic(
        HAZARD_USAGE_ERROR,
        "at least one chunk limit (--bytes or --records) must be specified");
    return 2;
  }

  struct stat st_dir;
  if (stat(cfg.out_dir, &st_dir) != 0) {
    char san[1024];
    sanitize_string(cfg.out_dir, san, sizeof(san));
    emit_diagnostic(HAZARD_OUTPUT_DIR_ERROR,
                    "cannot access output directory '%s': %s", san,
                    strerror(errno));
    return 2;
  }
  if (!S_ISDIR(st_dir.st_mode)) {
    char san[1024];
    sanitize_string(cfg.out_dir, san, sizeof(san));
    emit_diagnostic(HAZARD_OUTPUT_DIR_ERROR,
                    "output directory is not a directory: '%s'", san);
    return 2;
  }

  int input_fd = STDIN_FILENO;
  bool close_input_fd = false;
  if (cfg.input_path != NULL && strcmp(cfg.input_path, "-") != 0) {
    struct stat st_in;
    if (stat(cfg.input_path, &st_in) != 0) {
      char san[1024];
      sanitize_string(cfg.input_path, san, sizeof(san));
      emit_diagnostic(HAZARD_INPUT_NOT_FOUND,
                      "cannot access input file '%s': %s", san,
                      strerror(errno));
      return 2;
    }
    if (S_ISDIR(st_in.st_mode)) {
      char san[1024];
      sanitize_string(cfg.input_path, san, sizeof(san));
      emit_diagnostic(HAZARD_INPUT_IS_DIRECTORY,
                      "input file is a directory: '%s'", san);
      return 2;
    }
    input_fd = open(cfg.input_path, O_RDONLY);
    if (input_fd < 0) {
      char san[1024];
      sanitize_string(cfg.input_path, san, sizeof(san));
      emit_diagnostic(HAZARD_INPUT_NOT_FOUND, "cannot open input file '%s': %s",
                      san, strerror(errno));
      return 2;
    }
    close_input_fd = true;
  }

  SnSliceState state = {
      .input_fd = input_fd,
      .close_input_fd = close_input_fd,
      .active_chunk_fd = -1,
      .active_chunk_path = {0},
      .chunk_index = 1,
      .chunk_bytes = 0,
      .chunk_records = 0,
      .record_bytes = 0,
      .total_input_bytes = 0,
      .csv_state = CSV_STATE_START,
  };

  int rc = stream_slice(&cfg, &state);

  if (close_input_fd && input_fd >= 0) {
    close(input_fd);
  }

  return (rc == 0) ? 0 : 2;
}
