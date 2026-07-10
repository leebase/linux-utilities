#!/usr/bin/env bash
# Deterministic fixture acceptance suite for `sysdiff compare`.
# Covers contract status classes 0/1/2, exact sorted stdout, ordering
# independence, parsing edge cases, and empty stdout on errors.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${SYSDIFF_BIN:-$ROOT/build/sysdiff}"
WORKDIR=""
export LC_ALL=C

fail() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

if [ ! -x "$BIN" ]; then
    printf 'skip: sysdiff binary not found or not executable: %s\n' "$BIN" >&2
    exit 77
fi

WORKDIR="$(mktemp -d -t sysdiff-fixture.XXXXXXXXXX)"
cleanup() {
    rm -rf "$WORKDIR"
}
trap cleanup EXIT HUP INT TERM

run_status() {
    local expected_status="$1"
    local stdout="$2"
    local stderr="$3"
    local status
    local vg_log=""
    shift 3

    set +e
    if [ "${SYSDIFF_UNDER_VALGRIND:-0}" = "1" ]; then
        vg_log="$WORKDIR/valgrind.log"
        : >"$vg_log"
        valgrind --quiet --error-exitcode=99 --leak-check=full \
            --errors-for-leak-kinds=definite,possible \
            --log-file="$vg_log" "$@" >"$stdout" 2>"$stderr"
    else
        "$@" >"$stdout" 2>"$stderr"
    fi
    status="$?"
    set -e

    if [ -n "$vg_log" ] && { [ "$status" -eq 99 ] || [ -s "$vg_log" ]; }; then
        printf 'valgrind reported errors (status %s) for:' "$status" >&2
        printf ' %s' "$@" >&2
        printf '\n' >&2
        if [ -s "$vg_log" ]; then
            printf 'valgrind log:\n' >&2
            sed 's/^/  /' "$vg_log" >&2
        fi
        exit 1
    fi

    if [ "$status" -ne "$expected_status" ]; then
        printf 'expected status %s, got %s for:' "$expected_status" "$status" >&2
        printf ' %s' "$@" >&2
        printf '\nstdout:\n' >&2
        sed 's/^/  /' "$stdout" >&2
        printf 'stderr:\n' >&2
        sed 's/^/  /' "$stderr" >&2
        if [ -n "$vg_log" ] && [ -s "$vg_log" ]; then
            printf 'valgrind log:\n' >&2
            sed 's/^/  /' "$vg_log" >&2
        fi
        exit 1
    fi
}

assert_file_equals() {
    local expected="$1"
    local actual="$2"

    if ! cmp -s "$expected" "$actual"; then
        printf 'expected output:\n' >&2
        sed 's/^/  /' "$expected" >&2
        printf 'actual output:\n' >&2
        sed 's/^/  /' "$actual" >&2
        exit 1
    fi
}

assert_empty() {
    local path="$1"

    if [ -s "$path" ]; then
        printf 'expected empty file, got:\n' >&2
        sed 's/^/  /' "$path" >&2
        exit 1
    fi
}

assert_nonempty() {
    local path="$1"

    if [ ! -s "$path" ]; then
        fail "expected non-empty file: $path"
    fi
}

assert_contains() {
    local path="$1"
    local needle="$2"

    if ! grep -Fq "$needle" "$path"; then
        printf 'expected %s to contain %s, got:\n' "$path" "$needle" >&2
        sed 's/^/  /' "$path" >&2
        exit 1
    fi
}

assert_diff_prefixes() {
    local path="$1"
    local line

    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^[\+\-]\ [A-Za-z0-9._/-]+=.*$ ]]; then
            continue
        fi
        if [[ "$line" =~ ^~\ [A-Za-z0-9._/-]+:\ .*\ -\>\ .*$ ]]; then
            continue
        fi
        fail "unexpected diff line shape: $line"
    done <"$path"
}

before="$WORKDIR/before.snapshot"
after="$WORKDIR/after.snapshot"
expected_diff="$WORKDIR/expected.diff.golden"
expected_no_changes="$WORKDIR/expected-no-changes.golden"
stdout="$WORKDIR/stdout"
stderr="$WORKDIR/stderr"
printf 'no changes\n' >"$expected_no_changes"

# --- Status 1: valid changed snapshots with exact sorted stdout for added,
# removed, and changed keys. Unchanged keys emit nothing. Also covers
# comments, blank lines, values containing spaces, and empty values.
cat >"$before" <<'EOF'
# before snapshot
z.changed=old value
same.keep=stable

   # comment with leading spaces
space.value=old value with spaces
removed.empty=
removed.key=gone
m.changed=before
hash.value=old # note
eq.value=old=hash
EOF

cat >"$after" <<'EOF'
same.keep=stable
added.key=new value
space.value=new value with spaces

# after snapshot
z.changed=new value
m.changed=after
added.empty=
hash.value=new # note
eq.value=new=hash
EOF

cat >"$expected_diff" <<'EOF'
+ added.empty=
+ added.key=new value
~ eq.value: old=hash -> new=hash
~ hash.value: old # note -> new # note
~ m.changed: before -> after
- removed.empty=
- removed.key=gone
~ space.value: old value with spaces -> new value with spaces
~ z.changed: old value -> new value
EOF

run_status 1 "$stdout" "$stderr" "$BIN" compare "$before" "$after"
assert_file_equals "$expected_diff" "$stdout"
assert_empty "$stderr"
assert_diff_prefixes "$stdout"
# Unchanged keys must not appear in diff output.
if grep -Fq 'same.keep' "$stdout"; then
    fail "unchanged key same.keep must not appear in diff stdout"
fi

# --- Status 0: identical snapshots print exactly "no changes".
run_status 0 "$stdout" "$stderr" "$BIN" compare "$before" "$before"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

run_status 0 "$stdout" "$stderr" "$BIN" compare "$after" "$after"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

# Identical entry sets that differ only by comments and blank lines.
comments_a="$WORKDIR/comments-a.snapshot"
comments_b="$WORKDIR/comments-b.snapshot"
cat >"$comments_a" <<'EOF'
# first layout
a.key=one

b.key=two
EOF
cat >"$comments_b" <<'EOF'
b.key=two
	# tab-indented comment

a.key=one
# trailing
EOF
run_status 0 "$stdout" "$stderr" "$BIN" compare "$comments_a" "$comments_b"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

# --- Empty values: added empty, removed empty, and empty <-> non-empty change.
empty_before="$WORKDIR/empty-before.snapshot"
empty_after="$WORKDIR/empty-after.snapshot"
expected_empty="$WORKDIR/expected.empty.golden"
cat >"$empty_before" <<'EOF'
keep.empty=
gone.empty=
flip.empty=
flip.full=text
EOF
cat >"$empty_after" <<'EOF'
keep.empty=
added.empty=
flip.empty=text
flip.full=
EOF
printf '%s\n' \
    '+ added.empty=' \
    '~ flip.empty:  -> text' \
    '~ flip.full: text -> ' \
    '- gone.empty=' >"$expected_empty"
run_status 1 "$stdout" "$stderr" "$BIN" compare "$empty_before" "$empty_after"
assert_file_equals "$expected_empty" "$stdout"
assert_empty "$stderr"
assert_diff_prefixes "$stdout"

# --- Ordering independence: same logical entries in different input order
# must produce the same sorted stdout.
order_a="$WORKDIR/order-a.snapshot"
order_b="$WORKDIR/order-b.snapshot"
order_c="$WORKDIR/order-c.snapshot"
order_d="$WORKDIR/order-d.snapshot"
expected_order="$WORKDIR/expected.order.golden"
stdout_order_ab="$WORKDIR/stdout.order.ab"
stdout_order_cd="$WORKDIR/stdout.order.cd"

cat >"$order_a" <<'EOF'
# unsorted before
c.key=three
a.key=one
b.key=two
EOF

cat >"$order_b" <<'EOF'
b.key=TWO
a.key=ONE
d.key=four
EOF

# Same logical content as order_a / order_b, different line order and comments.
cat >"$order_c" <<'EOF'
a.key=one

b.key=two
# trailing comment
c.key=three
EOF

cat >"$order_d" <<'EOF'
d.key=four
a.key=ONE
b.key=TWO
EOF

cat >"$expected_order" <<'EOF'
~ a.key: one -> ONE
~ b.key: two -> TWO
- c.key=three
+ d.key=four
EOF

run_status 1 "$stdout_order_ab" "$stderr" "$BIN" compare "$order_a" "$order_b"
assert_file_equals "$expected_order" "$stdout_order_ab"
assert_empty "$stderr"
assert_diff_prefixes "$stdout_order_ab"

run_status 1 "$stdout_order_cd" "$stderr" "$BIN" compare "$order_c" "$order_d"
assert_file_equals "$expected_order" "$stdout_order_cd"
assert_empty "$stderr"
assert_file_equals "$stdout_order_ab" "$stdout_order_cd"

# --- Status 2: missing files. Empty stdout, non-empty contextual stderr.
missing="$WORKDIR/does-not-exist.snapshot"
run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$missing"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$missing"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$missing" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$missing"

# --- Status 2: wrong argument counts. Empty stdout, contextual stderr.
run_status 2 "$stdout" "$stderr" "$BIN" compare
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "compare"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$before"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "compare"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$after" "$WORKDIR/extra.snapshot"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "compare"

# --- Status 2: unknown command. Empty stdout, contextual stderr.
run_status 2 "$stdout" "$stderr" "$BIN" unknown-command
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "unknown-command"

run_status 2 "$stdout" "$stderr" "$BIN" nope
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "nope"

# --- Status 2: malformed lines (missing '=', empty key). Empty stdout.
malformed="$WORKDIR/malformed.snapshot"
cat >"$malformed" <<'EOF'
valid.key=value
missing separator
EOF

run_status 2 "$stdout" "$stderr" "$BIN" compare "$malformed" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$malformed"
assert_contains "$stderr" "${malformed}:2"

# Malformed after path must not emit partial diff stdout.
malformed_after="$WORKDIR/malformed-after.snapshot"
cat >"$malformed_after" <<'EOF'
a.key=new
also missing separator
EOF
run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$malformed_after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$malformed_after"
assert_contains "$stderr" "${malformed_after}:2"

empty_key="$WORKDIR/empty-key.snapshot"
cat >"$empty_key" <<'EOF'
=value-without-key
EOF

run_status 2 "$stdout" "$stderr" "$BIN" compare "$empty_key" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$empty_key"
assert_contains "$stderr" "${empty_key}:1"

# Whitespace-only space/tab lines are blank entries and are ignored.
ws_only="$WORKDIR/ws-only.snapshot"
printf ' \t \n\t\t\n' >"$ws_only"
run_status 0 "$stdout" "$stderr" "$BIN" compare "$ws_only" "$ws_only"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

# Embedded NUL bytes are malformed input (empty stdout, contextual stderr).
embedded_nul="$WORKDIR/embedded-nul.snapshot"
printf 'good.key=ok\nbad\0.key=value\n' >"$embedded_nul"
run_status 2 "$stdout" "$stderr" "$BIN" compare "$embedded_nul" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$embedded_nul"
assert_contains "$stderr" "embedded NUL"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$embedded_nul"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$embedded_nul"
assert_contains "$stderr" "embedded NUL"

# --- Status 2: duplicate keys. Empty stdout, contextual stderr with key.
duplicate="$WORKDIR/duplicate.snapshot"
cat >"$duplicate" <<'EOF'
dup.key=first
other.key=value
dup.key=second
EOF

run_status 2 "$stdout" "$stderr" "$BIN" compare "$duplicate" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$duplicate"
assert_contains "$stderr" "dup.key"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$duplicate"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$duplicate"
assert_contains "$stderr" "dup.key"

# --- CRLF equivalence: CRLF-terminated snapshots compare like LF ones.
crlf_before="$WORKDIR/crlf-before.snapshot"
crlf_after="$WORKDIR/crlf-after.snapshot"
lf_before="$WORKDIR/lf-before.snapshot"
lf_after="$WORKDIR/lf-after.snapshot"
expected_crlf="$WORKDIR/expected.crlf.golden"
stdout_crlf="$WORKDIR/stdout.crlf"
stdout_lf="$WORKDIR/stdout.lf"

printf 'same.keep=stable\r\nz.changed=old value\r\nremoved.key=gone\r\n' >"$crlf_before"
printf 'same.keep=stable\r\nz.changed=new value\r\nadded.key=new\r\n' >"$crlf_after"
printf 'same.keep=stable\nz.changed=old value\nremoved.key=gone\n' >"$lf_before"
printf 'same.keep=stable\nz.changed=new value\nadded.key=new\n' >"$lf_after"
cat >"$expected_crlf" <<'EOF'
+ added.key=new
- removed.key=gone
~ z.changed: old value -> new value
EOF

run_status 1 "$stdout_crlf" "$stderr" "$BIN" compare "$crlf_before" "$crlf_after"
assert_file_equals "$expected_crlf" "$stdout_crlf"
assert_empty "$stderr"
assert_diff_prefixes "$stdout_crlf"

run_status 1 "$stdout_lf" "$stderr" "$BIN" compare "$lf_before" "$lf_after"
assert_file_equals "$expected_crlf" "$stdout_lf"
assert_empty "$stderr"
assert_file_equals "$stdout_crlf" "$stdout_lf"

run_status 0 "$stdout" "$stderr" "$BIN" compare "$crlf_before" "$lf_before"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

# Mixed endings within one file still parse to the same logical entries.
mixed_endings="$WORKDIR/mixed-endings.snapshot"
printf 'a.key=one\r\nb.key=two\n' >"$mixed_endings"
lf_mixed="$WORKDIR/lf-mixed.snapshot"
printf 'a.key=one\nb.key=two\n' >"$lf_mixed"
run_status 0 "$stdout" "$stderr" "$BIN" compare "$mixed_endings" "$lf_mixed"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

# --- Resource limits: line length and entry count (exit 2, empty stdout).
MAX_LINE_BYTES=65536
MAX_SNAPSHOT_ENTRIES=65536

line_at_limit="$WORKDIR/line-at-limit.snapshot"
line_over_limit="$WORKDIR/line-over-limit.snapshot"
line_crlf_at_limit="$WORKDIR/line-crlf-at-limit.snapshot"
python3 - "$line_at_limit" "$line_over_limit" "$line_crlf_at_limit" "$MAX_LINE_BYTES" <<'PY'
import sys

at_limit, over_limit, crlf_at_limit, max_bytes_s = sys.argv[1:5]
max_bytes = int(max_bytes_s)
prefix = b"a.key="
pad = max_bytes - len(prefix)
if pad < 0:
    raise SystemExit("MAX_LINE_BYTES too small for test prefix")
content = prefix + (b"x" * pad)
open(at_limit, "wb").write(content + b"\n")
open(over_limit, "wb").write(content + b"y\n")
open(crlf_at_limit, "wb").write(content + b"\r\n")
PY

run_status 0 "$stdout" "$stderr" "$BIN" compare "$line_at_limit" "$line_at_limit"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

# CRLF at the content-length boundary must match LF (fixes prior off-by-one).
run_status 0 "$stdout" "$stderr" "$BIN" compare "$line_at_limit" "$line_crlf_at_limit"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$line_over_limit" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$line_over_limit"
assert_contains "$stderr" "line length limit"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$line_over_limit"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$line_over_limit"
assert_contains "$stderr" "line length limit"

# Parsing 65536 entries under Valgrind is prohibitively slow; keep full
# coverage on the normal and sanitizer paths that make test already runs.
if [ "${SYSDIFF_UNDER_VALGRIND:-0}" != "1" ]; then
    entries_at_limit="$WORKDIR/entries-at-limit.snapshot"
    entries_over_limit="$WORKDIR/entries-over-limit.snapshot"
    python3 - "$entries_at_limit" "$entries_over_limit" "$MAX_SNAPSHOT_ENTRIES" <<'PY'
import sys

at_limit, over_limit, max_entries_s = sys.argv[1:4]
max_entries = int(max_entries_s)
with open(at_limit, "w", encoding="utf-8") as fh:
    for i in range(max_entries):
        fh.write(f"k.{i}=v\n")
with open(over_limit, "w", encoding="utf-8") as fh:
    for i in range(max_entries + 1):
        fh.write(f"k.{i}=v\n")
PY

    run_status 0 "$stdout" "$stderr" "$BIN" compare "$entries_at_limit" "$entries_at_limit"
    assert_file_equals "$expected_no_changes" "$stdout"
    assert_empty "$stderr"

    run_status 2 "$stdout" "$stderr" "$BIN" compare "$entries_over_limit" "$after"
    assert_empty "$stdout"
    assert_nonempty "$stderr"
    assert_contains "$stderr" "$entries_over_limit"
    assert_contains "$stderr" "entry limit"

    run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$entries_over_limit"
    assert_empty "$stdout"
    assert_nonempty "$stderr"
    assert_contains "$stderr" "$entries_over_limit"
    assert_contains "$stderr" "entry limit"
fi

# --- Safe value rendering: ESC, tab, CR, backslash, DEL, non-ASCII.
safe_before="$WORKDIR/safe-before.snapshot"
safe_after="$WORKDIR/safe-after.snapshot"
expected_safe="$WORKDIR/expected.safe.golden"
python3 - "$safe_before" "$safe_after" "$expected_safe" <<'PY'
from pathlib import Path
import sys

before_path, after_path, expected_path = map(Path, sys.argv[1:4])
before_path.write_bytes(b"a.key=plain\nb.key=old\n")
after_path.write_bytes(
    b"a.key=plain\x1b\t\r\\\x7f\xc3\xa9\nb.key=old\nc.key=new\x1b\n"
)
expected_path.write_text(
    "~ a.key: plain -> plain\\x1B\\x09\\x0D\\\\\\x7F\\xC3\\xA9\n"
    "+ c.key=new\\x1B\n",
    encoding="ascii",
)
PY
run_status 1 "$stdout" "$stderr" "$BIN" compare "$safe_before" "$safe_after"
assert_file_equals "$expected_safe" "$stdout"
assert_empty "$stderr"
if grep -a $'\x1b' "$stdout" >/dev/null || grep -a $'\x7f' "$stdout" >/dev/null; then
    fail "stdout must not contain raw ESC or DEL bytes"
fi
assert_diff_prefixes "$stdout"

# Diagnostic path/command escaping for ESC bytes.
esc_cmd=$'bad\x1bcmd'
run_status 2 "$stdout" "$stderr" "$BIN" "$esc_cmd"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" 'bad\x1Bcmd'
if grep -a $'\x1b' "$stderr" >/dev/null; then
    fail "stderr must not contain raw ESC from unknown command"
fi

# --- Output write failure: informational and compare paths to /dev/full.
if [ -w /dev/full ]; then
    assert_write_error_to_full() {
        local label="$1"
        shift
        set +e
        "$@" >/dev/full 2>"$stderr"
        local full_status=$?
        set -e
        if [ "$full_status" -ne 2 ]; then
            fail "expected status 2 for $label to /dev/full, got $full_status"
        fi
        assert_contains "$stderr" "stdout write error:"
    }

    assert_write_error_to_full "no-arg usage" "$BIN"
    assert_write_error_to_full "--help" "$BIN" --help
    assert_write_error_to_full "--version" "$BIN" --version
    assert_write_error_to_full "compare" "$BIN" compare "$before" "$before"
fi

# --- Closed stdout pipe: EPIPE via stdio, status 2, no SIGPIPE death.
assert_closed_stdout_pipe() {
    local label="$1"
    shift
    python3 - "$label" "$BIN" "$@" <<'PY'
import errno as errno_mod
import os
import subprocess
import sys

label = sys.argv[1]
cmd = sys.argv[2:]
epipe_message = os.strerror(errno_mod.EPIPE).encode()
read_fd, write_fd = os.pipe()
os.close(read_fd)
proc = subprocess.Popen(cmd, stdout=write_fd, stderr=subprocess.PIPE)
os.close(write_fd)
_, err = proc.communicate()
if proc.returncode != 2:
    raise SystemExit(
        f"{label}: expected status 2, got {proc.returncode} (signal death "
        f"would be negative)"
    )
if proc.returncode < 0:
    raise SystemExit(f"{label}: unexpected signal termination")
if b"stdout write error:" not in err:
    raise SystemExit(f"{label}: missing stdout write error diagnostic: {err!r}")
if epipe_message not in err:
    raise SystemExit(
        f"{label}: expected platform EPIPE text {epipe_message!r} in {err!r}"
    )
PY
}

assert_closed_stdout_pipe "--help" --help
assert_closed_stdout_pipe "changed-compare" compare "$before" "$after"

# --- Aggregate snapshot byte limit (16 MiB), including comment-only bypass.
MAX_SNAPSHOT_BYTES=16777216
if [ "${SYSDIFF_UNDER_VALGRIND:-0}" != "1" ]; then
    bytes_at_limit="$WORKDIR/bytes-at-limit.snapshot"
    bytes_over_limit="$WORKDIR/bytes-over-limit.snapshot"
    comments_over_limit="$WORKDIR/comments-over-limit.snapshot"
    nul_over_limit="$WORKDIR/nul-over-limit.snapshot"
    python3 - "$bytes_at_limit" "$bytes_over_limit" "$comments_over_limit" \
        "$nul_over_limit" "$MAX_SNAPSHOT_BYTES" <<'PY'
import sys
from pathlib import Path

at_limit, over_limit, comments_over, nul_over, max_bytes_s = sys.argv[1:6]
max_bytes = int(max_bytes_s)
Path(at_limit).write_bytes(b"#\n" * (max_bytes // 2))
Path(over_limit).write_bytes(b"#\n" * (max_bytes // 2) + b"\n")
Path(comments_over).write_bytes(b"\n" * max_bytes + b"#")
Path(nul_over).write_bytes(b"\n" * max_bytes + b"\0")
PY

    run_status 0 "$stdout" "$stderr" "$BIN" compare "$bytes_at_limit" "$bytes_at_limit"
    assert_file_equals "$expected_no_changes" "$stdout"
    assert_empty "$stderr"

    run_status 2 "$stdout" "$stderr" "$BIN" compare "$bytes_over_limit" "$after"
    assert_empty "$stdout"
    assert_nonempty "$stderr"
    assert_contains "$stderr" "$bytes_over_limit"
    assert_contains "$stderr" "snapshot byte limit exceeded"

    run_status 2 "$stdout" "$stderr" "$BIN" compare "$comments_over_limit" "$after"
    assert_empty "$stdout"
    assert_nonempty "$stderr"
    assert_contains "$stderr" "$comments_over_limit"
    assert_contains "$stderr" "snapshot byte limit exceeded"

    # NUL as byte 16,777,217 is a byte-limit failure, not embedded-NUL.
    run_status 2 "$stdout" "$stderr" "$BIN" compare "$nul_over_limit" "$after"
    assert_empty "$stdout"
    assert_nonempty "$stderr"
    assert_contains "$stderr" "$nul_over_limit"
    assert_contains "$stderr" "snapshot byte limit exceeded"
    if grep -Fq "embedded NUL" "$stderr"; then
        fail "NUL beyond the byte limit must not be classified as embedded NUL"
    fi
fi

printf 'ok: sysdiff fixture acceptance tests passed\n'
