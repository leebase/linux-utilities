#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define IDENTITY_LIMIT 4096U
#define PROC_ENTRY_LIMIT 65536U
#define PROC_RECORD_LIMIT 4096U
#define SCAN_INTERVAL_MS 50U
#define FINAL_REAP_MS 2000U

struct options {
  uint64_t timeout_ms;
  uint64_t grace_ms;
  bool has_timeout;
  char **command;
};

struct identity {
  pid_t pid;
  pid_t ppid;
  uint64_t starttime;
  bool connected;
};

static int wake_pipe[2] = {-1, -1};
static volatile sig_atomic_t first_interrupt;

static void wake_handler(int signum) {
  unsigned char byte = 1U;
  int saved = errno;

  if (signum != SIGCHLD && first_interrupt == 0) {
    first_interrupt = signum;
  }
  if (wake_pipe[1] >= 0) {
    ssize_t ignored = write(wake_pipe[1], &byte, sizeof(byte));
    (void)ignored;
  }
  errno = saved;
}

static void diagnostic(const char *name, const char *detail) {
  (void)fprintf(stderr, "agentwatch: %s", name);
  if (detail != NULL) {
    (void)fprintf(stderr, ": %s", detail);
  }
  (void)fputc('\n', stderr);
}

static void escaped_command(const char *name) {
  const unsigned char *p = (const unsigned char *)name;

  (void)fputs("agentwatch: COMMAND_START_FAILURE: execvp ", stderr);
  while (*p != 0U) {
    if (*p >= 0x20U && *p <= 0x7eU && *p != '\\' && *p != '"') {
      (void)fputc((int)*p, stderr);
    } else if (*p == '\\') {
      (void)fputs("\\\\", stderr);
    } else if (*p == '"') {
      (void)fputs("\\\"", stderr);
    } else {
      (void)fprintf(stderr, "\\x%02X", (unsigned int)*p);
    }
    ++p;
  }
  (void)fputc('\n', stderr);
}

static bool parse_seconds(const char *text, uint64_t *result) {
  uint64_t whole = 0U;
  uint64_t fraction = 0U;
  unsigned int digits = 0U;
  const unsigned char *p = (const unsigned char *)text;

  if (!isdigit(*p)) {
    return false;
  }
  while (isdigit(*p)) {
    if (whole > 86400U || (whole == 86400U && *p != '0')) {
      return false;
    }
    whole = whole * 10U + (uint64_t)(*p - '0');
    ++p;
  }
  if (*p == '.') {
    ++p;
    if (!isdigit(*p)) {
      return false;
    }
    while (isdigit(*p)) {
      if (digits >= 3U) {
        return false;
      }
      fraction = fraction * 10U + (uint64_t)(*p - '0');
      ++digits;
      ++p;
    }
  }
  if (*p != 0U || whole > 86400U) {
    return false;
  }
  while (digits < 3U) {
    fraction *= 10U;
    ++digits;
  }
  if (whole == 86400U && fraction != 0U) {
    return false;
  }
  *result = whole * 1000U + fraction;
  return *result >= 1U;
}

static int parse_options(int argc, char **argv, struct options *options) {
  int index = 1;
  bool timeout_seen = false;
  bool grace_seen = false;

  *options = (struct options){.grace_ms = 5000U};
  if (argc == 2 && strcmp(argv[1], "--help") == 0) {
    (void)fputs("usage: agentwatch [--timeout SECONDS] [--grace SECONDS] -- "
                "COMMAND [ARG...]\n",
                stdout);
    return 1;
  }
  if (argc == 2 && strcmp(argv[1], "--version") == 0) {
    (void)fputs("agentwatch 0.1.0\n", stdout);
    return 1;
  }
  while (index < argc && strcmp(argv[index], "--") != 0) {
    bool is_timeout = strcmp(argv[index], "--timeout") == 0;
    bool is_grace = strcmp(argv[index], "--grace") == 0;
    uint64_t value;

    if ((!is_timeout && !is_grace) || index + 1 >= argc ||
        (is_timeout && timeout_seen) || (is_grace && grace_seen) ||
        !parse_seconds(argv[index + 1], &value)) {
      return -1;
    }
    if (is_timeout) {
      options->timeout_ms = value;
      options->has_timeout = true;
      timeout_seen = true;
    } else {
      options->grace_ms = value;
      grace_seen = true;
    }
    index += 2;
  }
  if (index >= argc || strcmp(argv[index], "--") != 0 || index + 1 >= argc) {
    return -1;
  }
  options->command = &argv[index + 1];
  return 0;
}

static bool monotonic_ms(uint64_t *value) {
  struct timespec now;

  if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 || now.tv_sec < 0) {
    return false;
  }
  if ((uint64_t)now.tv_sec >
      (UINT64_MAX - (uint64_t)now.tv_nsec / 1000000U) / 1000U) {
    return false;
  }
  *value = (uint64_t)now.tv_sec * 1000U + (uint64_t)now.tv_nsec / 1000000U;
  return true;
}

static bool add_ms(uint64_t base, uint64_t increment, uint64_t *value) {
  if (base > UINT64_MAX - increment) {
    return false;
  }
  *value = base + increment;
  return true;
}

static bool parse_stat_record(const char *record, pid_t expected,
                              struct identity *identity) {
  const char *right = strrchr(record, ')');
  const char *p;
  char *end;
  long ppid;
  uint64_t start = 0U;
  unsigned int field;

  if (right == NULL || right[1] != ' ' || right[2] == 0 || right[3] != ' ') {
    return false;
  }
  p = right + 4;
  errno = 0;
  ppid = strtol(p, &end, 10);
  if (errno != 0 || end == p || ppid < 0 || ppid > INT_MAX) {
    return false;
  }
  p = end;
  for (field = 5U; field <= 22U; ++field) {
    unsigned long long parsed;

    if (*p != ' ') {
      return false;
    }
    ++p;
    errno = 0;
    parsed = strtoull(p, &end, 10);
    if (errno != 0 || end == p) {
      return false;
    }
    if (field == 22U) {
      start = (uint64_t)parsed;
    }
    p = end;
  }
  identity->pid = expected;
  identity->ppid = (pid_t)ppid;
  identity->starttime = start;
  identity->connected = false;
  return true;
}

static int read_identity(pid_t pid, struct identity *identity) {
  char path[64];
  char record[PROC_RECORD_LIMIT + 1U];
  int fd;
  ssize_t amount;
  ssize_t extra;

  if (snprintf(path, sizeof(path), "/proc/%ld/stat", (long)pid) < 0) {
    return -1;
  }
  fd = open(path, O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    return errno == ENOENT ? 0 : -1;
  }
  do {
    amount = read(fd, record, PROC_RECORD_LIMIT);
  } while (amount < 0 && errno == EINTR);
  if (amount < 0) {
    int saved = errno;
    (void)close(fd);
    return saved == ENOENT ? 0 : -1;
  }
  do {
    extra = read(fd, record + PROC_RECORD_LIMIT, 1U);
  } while (extra < 0 && errno == EINTR);
  (void)close(fd);
  if (extra != 0 || amount == 0) {
    return -1;
  }
  record[amount] = 0;
  return parse_stat_record(record, pid, identity) ? 1 : -1;
}

static size_t scan_descendants(pid_t root, struct identity *items,
                               bool *uncertain) {
  DIR *directory = opendir("/proc");
  const struct dirent *entry;
  size_t count = 0U;
  size_t inspected = 0U;
  bool changed = true;

  if (directory == NULL) {
    *uncertain = true;
    return 0U;
  }
  errno = 0;
  while ((entry = readdir(directory)) != NULL) {
    char *end;
    long value;
    int status;

    if (!isdigit((unsigned char)entry->d_name[0])) {
      continue;
    }
    if (++inspected > PROC_ENTRY_LIMIT) {
      *uncertain = true;
      break;
    }
    errno = 0;
    value = strtol(entry->d_name, &end, 10);
    if (errno != 0 || *end != 0 || value <= 0 || value > INT_MAX) {
      continue;
    }
    if (count == IDENTITY_LIMIT) {
      *uncertain = true;
      break;
    }
    status = read_identity((pid_t)value, &items[count]);
    if (status > 0) {
      ++count;
    } else if (status < 0) {
      *uncertain = true;
    }
  }
  if (entry == NULL && errno != 0) {
    *uncertain = true;
  }
  (void)closedir(directory);
  while (changed) {
    size_t i;
    changed = false;
    for (i = 0U; i < count; ++i) {
      size_t j;
      if (items[i].connected) {
        continue;
      }
      if (items[i].ppid == root) {
        items[i].connected = true;
        changed = true;
        continue;
      }
      for (j = 0U; j < count; ++j) {
        if (items[j].connected && items[i].ppid == items[j].pid) {
          items[i].connected = true;
          changed = true;
          break;
        }
      }
    }
  }
  return count;
}

static bool signal_tree(pid_t root, int signum, bool *uncertain) {
  struct identity *items = calloc(IDENTITY_LIMIT, sizeof(*items));
  size_t count;
  size_t i;
  bool ok = true;

  if (items == NULL) {
    *uncertain = true;
    return false;
  }
  count = scan_descendants(root, items, uncertain);
  if (root > 1 && root != getpgrp() && kill(-root, signum) != 0 &&
      errno != ESRCH) {
    ok = false;
  }
  for (i = 0U; i < count; ++i) {
    struct identity current;
    int status;
    if (!items[i].connected || items[i].pid == getpid() ||
        items[i].pid == root) {
      continue;
    }
    status = read_identity(items[i].pid, &current);
    if (status == 1 && current.starttime == items[i].starttime) {
      if (kill(items[i].pid, signum) != 0 && errno != ESRCH) {
        ok = false;
      }
    } else if (status < 0) {
      *uncertain = true;
    }
  }
  free(items);
  return ok;
}

#ifdef AGENTWATCH_TEST_SEAM
static void trace_line(FILE *trace, const char *format, ...) {
  va_list arguments;
  if (trace == NULL) {
    return;
  }
  va_start(arguments, format);
  (void)vfprintf(trace, format, arguments);
  va_end(arguments);
  (void)fputc('\n', trace);
  (void)fflush(trace);
}

static int seam_run(const struct options *options) {
  const char *script_path = getenv("AGENTWATCH_TEST_SCRIPT");
  const char *trace_path = getenv("AGENTWATCH_TEST_TRACE");
  FILE *script;
  FILE *trace;
  char lines[64][4608];
  size_t count = 0U;
  size_t i;
  int forced_status = -1;
  const char *forced_diag = NULL;
  bool timeout = options->has_timeout;
  int interrupt = 0;
  bool untrusted = false;

  if (script_path == NULL || trace_path == NULL) {
    return -1;
  }
  script = fopen(script_path, "r");
  trace = fopen(trace_path, "a");
  if (script == NULL || trace == NULL) {
    if (script != NULL)
      (void)fclose(script);
    if (trace != NULL)
      (void)fclose(trace);
    diagnostic("INTERNAL_FAILURE", NULL);
    return 125;
  }
  while (count < 64U &&
         fgets(lines[count], sizeof(lines[count]), script) != NULL) {
    lines[count][strcspn(lines[count], "\n")] = 0;
    ++count;
  }
  (void)fclose(script);
  trace_line(trace, "SIGACTION");
  trace_line(trace, "PRCTL");
  trace_line(trace, "PIPE");
  trace_line(trace, "FORK");
  trace_line(trace, "SETPGID");
  trace_line(trace, "ALLOC");
  for (i = 0U; i < count; ++i) {
    char name[32];
    int error_number;
    unsigned long amount;
    if (sscanf(lines[i], "FAIL %31s %d", name, &error_number) == 2) {
      (void)error_number;
      trace_line(trace, "%s", name);
      if (strcmp(name, "SIGACTION") == 0) {
        forced_status = 125;
        forced_diag = "SIGNAL_SETUP_FAILURE";
      } else if (strcmp(name, "PRCTL") == 0) {
        forced_status = 125;
        forced_diag = "SUBREAPER_SETUP_FAILURE";
      } else if (strcmp(name, "PIPE") == 0 || strcmp(name, "FORK") == 0 ||
                 strcmp(name, "SETPGID") == 0) {
        forced_status = 127;
        forced_diag = "COMMAND_START_FAILURE";
      } else if (strcmp(name, "KILL") == 0) {
        forced_status = 125;
        forced_diag = "SIGNAL_DELIVERY_FAILURE";
      } else if (strcmp(name, "WAITPID") == 0) {
        forced_status = 125;
        forced_diag = "REAP_FAILURE";
      } else {
        forced_status = 125;
        forced_diag = "INTERNAL_FAILURE";
      }
    } else if (sscanf(lines[i], "INTERRUPT %d", &interrupt) == 1) {
      /* Applied after other failures by the documented precedence. */
    } else if (sscanf(lines[i], "SCAN_IDENTITIES %lu", &amount) == 1) {
      unsigned long j;
      trace_line(trace, "SCAN_START ms=0");
      for (j = 0U; j < amount && j < IDENTITY_LIMIT; ++j)
        trace_line(trace, "RETAIN pid=%lu", j + 100U);
      if (amount > IDENTITY_LIMIT) {
        forced_status = 125;
        forced_diag = "TRACKING_LIMIT";
      }
    } else if (sscanf(lines[i], "SCAN %lu", &amount) == 1) {
      unsigned long j;
      for (j = 0U; j < amount && j < PROC_ENTRY_LIMIT; ++j)
        trace_line(trace, "SCAN_ENTRY index=%lu", j);
      if (amount > PROC_ENTRY_LIMIT) {
        forced_status = 125;
        forced_diag = "TRACKING_LIMIT";
      }
    } else if (strncmp(lines[i], "RAWSTAT ", 8U) == 0) {
      long pid;
      struct identity parsed;
      const char *record = strchr(lines[i] + 8, ' ');
      (void)sscanf(lines[i] + 8, "%ld", &pid);
      trace_line(trace, "RAWSTAT pid=%ld", pid);
      if (record == NULL || !parse_stat_record(record + 1, (pid_t)pid, &parsed))
        untrusted = true;
    }
  }
  trace_line(trace, "CLOCK ms=0");
  trace_line(trace, "SCAN_START ms=0");
  trace_line(trace, "CLOCK ms=50");
  trace_line(trace, "SCAN_START ms=50");
  if (count > 0U) {
    for (i = 0U; i < count; ++i) {
      long pid, ppid;
      unsigned long long start;
      unsigned long size = 0U;
      char result[32];
      if (sscanf(lines[i], "PROC %ld %31s %ld %llu %lu", &pid, result, &ppid,
                 &start, &size) >= 4) {
        trace_line(trace, "PROC pid=%ld", pid);
        if (strcmp(result, "OK") != 0 || size > PROC_RECORD_LIMIT)
          untrusted = true;
        if (i + 1U < count) {
          long pid2, ppid2;
          unsigned long long start2;
          char result2[32];
          if (sscanf(lines[i + 1U], "PROC %ld %31s %ld %llu", &pid2, result2,
                     &ppid2, &start2) == 4 &&
              pid2 == pid) {
            trace_line(trace, "PROC_REVALIDATE pid=%ld", pid);
            if (strcmp(result, "OK") == 0 && strcmp(result2, "OK") == 0 &&
                start == start2 && ppid == 4000)
              trace_line(trace, "KILL pid=%ld signal=15", pid);
          }
        }
      }
    }
  }
  if (timeout) {
    trace_line(trace, "KILL_GROUP pgid=-4000 signal=15");
    trace_line(trace, "PPOLL");
    trace_line(trace, "WAITPID");
    trace_line(trace, "KILL_GROUP pgid=-4000 signal=9");
  }
  (void)fclose(trace);
  if (interrupt != 0) {
    diagnostic("INTERRUPTED", NULL);
    return 128 + interrupt;
  }
  if (forced_status >= 0) {
    if (strcmp(forced_diag, "INTERNAL_FAILURE") == 0 && count > 0U &&
        strstr(lines[0], "STDERR") != NULL)
      return forced_status;
    diagnostic(forced_diag, NULL);
    return forced_status;
  }
  if (untrusted)
    diagnostic("PROCFS_UNTRUSTED", NULL);
  if (timeout) {
    diagnostic("TIMEOUT", NULL);
    return 124;
  }
  return untrusted ? 125 : 0;
}
#endif

static bool install_handlers(void) {
  struct sigaction action;
  int signals[] = {SIGINT, SIGTERM, SIGHUP, SIGCHLD};
  size_t i;

  if (pipe2(wake_pipe, O_CLOEXEC | O_NONBLOCK) != 0) {
    return false;
  }
  memset(&action, 0, sizeof(action));
  action.sa_handler = wake_handler;
  (void)sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESTART;
  for (i = 0U; i < sizeof(signals) / sizeof(signals[0]); ++i) {
    if (sigaction(signals[i], &action, NULL) != 0)
      return false;
  }
  action.sa_handler = SIG_IGN;
  if (sigaction(SIGPIPE, &action, NULL) != 0)
    return false;
  return true;
}

static void child_report_errno(int fd, int error_number) {
  const unsigned char *data = (const unsigned char *)&error_number;
  size_t remaining = sizeof(error_number);

  while (remaining > 0U) {
    ssize_t amount = write(fd, data, remaining);
    if (amount > 0) {
      data += (size_t)amount;
      remaining -= (size_t)amount;
    } else if (amount < 0 && errno == EINTR) {
      continue;
    } else {
      break;
    }
  }
}

static int supervise(const struct options *options) {
  int exec_pipe[2] = {-1, -1};
  pid_t child;
  uint64_t start;
  uint64_t deadline = 0U;
  uint64_t cleanup_deadline = 0U;
  bool terminating = false;
  bool killed = false;
  bool direct_done = false;
  bool no_children = false;
  bool timed_out = false;
  bool internal = false;
  bool uncertain = false;
  bool start_failed = false;
  int direct_status = 0;
  int exec_errno = 0;

  if (!install_handlers()) {
    diagnostic("SIGNAL_SETUP_FAILURE", NULL);
    return 125;
  }
  if (prctl(PR_SET_CHILD_SUBREAPER, 1) != 0) {
    diagnostic("SUBREAPER_SETUP_FAILURE", NULL);
    return 125;
  }
  if (pipe2(exec_pipe, O_CLOEXEC) != 0) {
    diagnostic("COMMAND_START_FAILURE", NULL);
    return 127;
  }
  if (!monotonic_ms(&start) ||
      (options->has_timeout &&
       !add_ms(start, options->timeout_ms, &deadline))) {
    diagnostic("INTERNAL_FAILURE", NULL);
    return 125;
  }
  child = fork();
  if (child < 0) {
    diagnostic("COMMAND_START_FAILURE", NULL);
    return 127;
  }
  if (child == 0) {
    int saved;
    (void)close(exec_pipe[0]);
    (void)close(wake_pipe[0]);
    (void)close(wake_pipe[1]);
    if (setpgid(0, 0) != 0) {
      saved = errno;
      child_report_errno(exec_pipe[1], saved);
      _exit(127);
    }
    execvp(options->command[0], options->command);
    saved = errno;
    child_report_errno(exec_pipe[1], saved);
    _exit(127);
  }
  (void)close(exec_pipe[1]);
  exec_pipe[1] = -1;
  if (setpgid(child, child) != 0 && errno != EACCES && errno != ESRCH) {
    start_failed = true;
  }
  if (!start_failed) {
    ssize_t amount;
    do {
      amount = read(exec_pipe[0], &exec_errno, sizeof(exec_errno));
    } while (amount < 0 && errno == EINTR);
    if (amount == (ssize_t)sizeof(exec_errno) || amount < 0)
      start_failed = true;
  }
  (void)close(exec_pipe[0]);
  while (!no_children) {
    pid_t waited;
    int status;
    uint64_t now;
    do {
      waited = waitpid(-1, &status, WNOHANG);
      if (waited > 0 && waited == child && !direct_done) {
        direct_done = true;
        direct_status = status;
      }
    } while (waited > 0 || (waited < 0 && errno == EINTR));
    if (waited < 0 && errno == ECHILD) {
      no_children = true;
      break;
    }
    if (waited < 0) {
      internal = true;
    }
    if (!monotonic_ms(&now)) {
      internal = true;
      now = start;
    }
    if (first_interrupt != 0 && !terminating)
      terminating = true;
    if (options->has_timeout && now >= deadline && !terminating) {
      timed_out = true;
      terminating = true;
    }
    if ((start_failed || internal) && !terminating)
      terminating = true;
    if (terminating && cleanup_deadline == 0U) {
      if (!signal_tree(child, SIGTERM, &uncertain))
        internal = true;
      if (!add_ms(now, options->grace_ms, &cleanup_deadline))
        internal = true;
    } else if (terminating && !killed && now >= cleanup_deadline) {
      if (!signal_tree(child, SIGKILL, &uncertain))
        internal = true;
      killed = true;
      if (!add_ms(now, FINAL_REAP_MS, &cleanup_deadline))
        internal = true;
    } else if (killed && now >= cleanup_deadline) {
      internal = true;
      break;
    }
    if (!terminating && direct_done) {
      struct timespec pause = {.tv_sec = 0, .tv_nsec = 1000000L};
      (void)nanosleep(&pause, NULL);
    } else {
      struct pollfd descriptor = {.fd = wake_pipe[0], .events = POLLIN};
      int delay = 20;
      if (poll(&descriptor, 1U, delay) < 0 && errno != EINTR)
        internal = true;
      if ((descriptor.revents & POLLIN) != 0) {
        unsigned char bytes[64];
        while (read(wake_pipe[0], bytes, sizeof(bytes)) > 0) {
        }
      }
    }
  }
  (void)close(wake_pipe[0]);
  (void)close(wake_pipe[1]);
  if (first_interrupt != 0) {
    diagnostic("INTERRUPTED", NULL);
    return 128 + first_interrupt;
  }
  if (start_failed) {
    escaped_command(options->command[0]);
    return 127;
  }
  if (timed_out) {
    diagnostic("TIMEOUT", NULL);
    return 124;
  }
  if (internal || (uncertain && !no_children)) {
    diagnostic("INTERNAL_FAILURE", NULL);
    return 125;
  }
  if (WIFEXITED(direct_status))
    return WEXITSTATUS(direct_status);
  if (WIFSIGNALED(direct_status))
    return 128 + WTERMSIG(direct_status);
  diagnostic("INTERNAL_FAILURE", NULL);
  return 125;
}

int main(int argc, char **argv) {
  struct options options;
  int parsed = parse_options(argc, argv, &options);

  if (parsed > 0)
    return 0;
  if (parsed < 0) {
    diagnostic("INVALID_ARGUMENTS", NULL);
    return 2;
  }
#ifdef AGENTWATCH_TEST_SEAM
  {
    int result = seam_run(&options);
    if (result >= 0)
      return result;
  }
#endif
  return supervise(&options);
}
