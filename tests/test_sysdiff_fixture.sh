#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/build/sysdiff"
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
    shift 3

    set +e
    "$@" >"$stdout" 2>"$stderr"
    status="$?"
    set -e

    if [ "$status" -ne "$expected_status" ]; then
        printf 'expected status %s, got %s for:' "$expected_status" "$status" >&2
        printf ' %s' "$@" >&2
        printf '\nstdout:\n' >&2
        sed 's/^/  /' "$stdout" >&2
        printf 'stderr:\n' >&2
        sed 's/^/  /' "$stderr" >&2
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

cat >"$before" <<'EOF'
# before snapshot
z.changed=old value
same.keep=stable

   # comment with leading spaces
space.value=old value with spaces
removed.empty=
removed.key=gone
m.changed=before
EOF

cat >"$after" <<'EOF'
same.keep=stable
added.key=new value
space.value=new value with spaces

# after snapshot
z.changed=new value
m.changed=after
added.empty=
EOF

cat >"$expected_diff" <<'EOF'
+ added.empty=
+ added.key=new value
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

run_status 0 "$stdout" "$stderr" "$BIN" compare "$before" "$before"
printf 'no changes\n' >"$expected_no_changes"
assert_file_equals "$expected_no_changes" "$stdout"
assert_empty "$stderr"

missing="$WORKDIR/does-not-exist.snapshot"
run_status 2 "$stdout" "$stderr" "$BIN" compare "$before" "$missing"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$missing"

run_status 2 "$stdout" "$stderr" "$BIN" compare "$before"
assert_empty "$stdout"
assert_nonempty "$stderr"

run_status 2 "$stdout" "$stderr" "$BIN" unknown-command
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "unknown-command"

malformed="$WORKDIR/malformed.snapshot"
cat >"$malformed" <<'EOF'
valid.key=value
missing separator
EOF

run_status 2 "$stdout" "$stderr" "$BIN" compare "$malformed" "$after"
assert_empty "$stdout"
assert_nonempty "$stderr"
assert_contains "$stderr" "$malformed"

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
