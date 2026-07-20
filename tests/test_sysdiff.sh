#!/usr/bin/env bash
# Top-level sysdiff shell suite: informational commands, packaging, fixtures.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${SYSDIFF_BIN:-$ROOT/build/sysdiff}"

if [ "${1:-}" = "--bin" ]; then
    if [ "$#" -lt 2 ]; then
        printf 'error: --bin requires a path to a sysdiff binary\n' >&2
        exit 1
    fi
    BIN="$2"
    export SYSDIFF_BIN="$BIN"
    shift 2
fi

if [ ! -x "$BIN" ]; then
    printf 'error: sysdiff binary not found or not executable: %s\n' "$BIN" >&2
    exit 1
fi

run_sysdiff() {
    if [ "${SYSDIFF_UNDER_VALGRIND:-0}" = "1" ]; then
        local vg_log status
        vg_log="$(mktemp "${TMPDIR:-/tmp}/sysdiff-valgrind.XXXXXXXXXX")"
        set +e
        valgrind --quiet --error-exitcode=99 --leak-check=full \
            --errors-for-leak-kinds=definite,possible \
            --log-file="$vg_log" "$BIN" "$@"
        status=$?
        set -e
        if [ "$status" -eq 99 ] || [ -s "$vg_log" ]; then
            printf 'valgrind reported errors (status %s)\n' "$status" >&2
            if [ -s "$vg_log" ]; then
                sed 's/^/  /' "$vg_log" >&2
            fi
            rm -f "$vg_log"
            return 99
        fi
        rm -f "$vg_log"
        return "$status"
    else
        "$BIN" "$@"
    fi
}

run_sysdiff --help | grep -q "usage: sysdiff"
run_sysdiff --help | grep -q "compare"
run_sysdiff --version | grep -q "sysdiff 0.1.0"

# No arguments keeps non-error help behavior (status 0, usage on stdout).
noarg_out="$(mktemp "${TMPDIR:-/tmp}/sysdiff-noarg.XXXXXXXXXX")"
cleanup_noarg() {
    rm -f "$noarg_out"
}
trap cleanup_noarg EXIT HUP INT TERM
set +e
run_sysdiff >"$noarg_out"
noarg_status=$?
set -e
if [ "$noarg_status" -ne 0 ]; then
    printf 'expected status 0 for no-arg help, got %s\n' "$noarg_status" >&2
    exit 1
fi
grep -q "usage: sysdiff" "$noarg_out"
grep -q "compare" "$noarg_out"
rm -f "$noarg_out"
trap - EXIT HUP INT TERM

# Workspace-confined DESTDIR install / reinstall / uninstall packaging checks.
# Packaging always stages the ordinary Makefile install target (build/sysdiff).
# Skip when an alternate/instrumented binary is under test so ASan/UBSan/Valgrind
# gates do not silently re-run uninstrumented install coverage.
ORDINARY_BIN="$ROOT/build/sysdiff"
if [ "$BIN" = "$ORDINARY_BIN" ] && [ "${SYSDIFF_UNDER_VALGRIND:-0}" != "1" ]; then
mkdir -p "$ROOT/build"
PKG_WORKDIR="$(mktemp -d "$ROOT/build/sysdiff-pkg.XXXXXXXXXX")"
cleanup_pkg() {
    rm -rf "$PKG_WORKDIR"
}
trap cleanup_pkg EXIT HUP INT TERM

PKG_PREFIX="/opt/sysdiff-packaging-check"
PKG_DESTDIR="$PKG_WORKDIR/destdir"
PKG_BIN="$PKG_DESTDIR$PKG_PREFIX/bin/sysdiff"
PKG_MAN="$PKG_DESTDIR$PKG_PREFIX/share/man/man1/sysdiff.1"
EXPECTED_MANIFEST="$(printf '%s\n' \
    "${PKG_PREFIX#/}/bin/sysdiff" \
    "${PKG_PREFIX#/}/share/man/man1/sysdiff.1")"

make -C "$ROOT" sysdiff
make -C "$ROOT" install DESTDIR="$PKG_DESTDIR" prefix="$PKG_PREFIX"

actual_manifest="$(
    find "$PKG_DESTDIR" \( -type f -o -type l \) -printf '%P\n' | LC_ALL=C sort
)"
if [ "$actual_manifest" != "$EXPECTED_MANIFEST" ]; then
    printf 'unexpected installed manifest\nexpected:\n%s\nactual:\n%s\n' \
        "$EXPECTED_MANIFEST" "$actual_manifest" >&2
    exit 1
fi

if [ ! -f "$PKG_BIN" ] || [ -L "$PKG_BIN" ]; then
    printf 'installed sysdiff must be a regular file: %s\n' "$PKG_BIN" >&2
    exit 1
fi
if [ ! -f "$PKG_MAN" ] || [ -L "$PKG_MAN" ]; then
    printf 'installed man page must be a regular file: %s\n' "$PKG_MAN" >&2
    exit 1
fi

bin_mode="$(stat -c '%a' "$PKG_BIN")"
man_mode="$(stat -c '%a' "$PKG_MAN")"
if [ "$bin_mode" != "755" ]; then
    printf 'expected mode 755 for installed sysdiff, got %s\n' "$bin_mode" >&2
    exit 1
fi
if [ "$man_mode" != "644" ]; then
    printf 'expected mode 644 for installed man page, got %s\n' "$man_mode" >&2
    exit 1
fi

"$PKG_BIN" --help | grep -q "usage: sysdiff"
"$PKG_BIN" --help | grep -q "compare"
"$PKG_BIN" --version | grep -q "sysdiff 0.1.0"

printf 'os.hostname=before\nkernel.release=1.0\n' >"$PKG_WORKDIR/before.snapshot"
printf 'os.hostname=after\nkernel.release=1.0\nextra.flag=1\n' \
    >"$PKG_WORKDIR/after.snapshot"
pkg_stdout="$PKG_WORKDIR/compare.out"
pkg_stderr="$PKG_WORKDIR/compare.err"
set +e
"$PKG_BIN" compare "$PKG_WORKDIR/before.snapshot" "$PKG_WORKDIR/after.snapshot" \
    >"$pkg_stdout" 2>"$pkg_stderr"
pkg_status=$?
set -e
if [ "$pkg_status" -ne 1 ]; then
    printf 'expected status 1 from installed compare, got %s\n' "$pkg_status" >&2
    sed 's/^/  /' "$pkg_stdout" >&2
    sed 's/^/  /' "$pkg_stderr" >&2
    exit 1
fi
grep -qx '+ extra.flag=1' "$pkg_stdout"
grep -qx '~ os.hostname: before -> after' "$pkg_stdout"
if [ -s "$pkg_stderr" ]; then
    printf 'installed compare wrote unexpected stderr\n' >&2
    sed 's/^/  /' "$pkg_stderr" >&2
    exit 1
fi

cp -a "$PKG_BIN" "$PKG_WORKDIR/sysdiff.before"
cp -a "$PKG_MAN" "$PKG_WORKDIR/sysdiff.1.before"
make -C "$ROOT" install DESTDIR="$PKG_DESTDIR" prefix="$PKG_PREFIX"
if ! cmp -s "$PKG_WORKDIR/sysdiff.before" "$PKG_BIN"; then
    printf 'reinstall changed installed sysdiff bytes\n' >&2
    exit 1
fi
if ! cmp -s "$PKG_WORKDIR/sysdiff.1.before" "$PKG_MAN"; then
    printf 'reinstall changed installed man page bytes\n' >&2
    exit 1
fi
reinstall_manifest="$(
    find "$PKG_DESTDIR" \( -type f -o -type l \) -printf '%P\n' | LC_ALL=C sort
)"
if [ "$reinstall_manifest" != "$EXPECTED_MANIFEST" ]; then
    printf 'reinstall produced unexpected manifest\nexpected:\n%s\nactual:\n%s\n' \
        "$EXPECTED_MANIFEST" "$reinstall_manifest" >&2
    exit 1
fi

make -C "$ROOT" uninstall DESTDIR="$PKG_DESTDIR" prefix="$PKG_PREFIX"
leftovers="$(find "$PKG_DESTDIR" \( -type f -o -type l \) -print || true)"
if [ -n "$leftovers" ]; then
    printf 'uninstall left files or symlinks in DESTDIR:\n%s\n' "$leftovers" >&2
    exit 1
fi

rm -rf "$PKG_WORKDIR"
trap - EXIT HUP INT TERM
fi

"$ROOT/tests/test_sysdiff_fixture.sh"
