#!/usr/bin/env bash
# Top-level sysdiff shell suite: informational commands plus fixture acceptance.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${SYSDIFF_BIN:-$ROOT/build/sysdiff}"

run_sysdiff() {
    if [ "${SYSDIFF_UNDER_VALGRIND:-0}" = "1" ]; then
        local vg_log status
        vg_log="$(mktemp -t sysdiff-valgrind.XXXXXXXXXX)"
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
noarg_out="$(mktemp -t sysdiff-noarg.XXXXXXXXXX)"
set +e
run_sysdiff >"$noarg_out"
noarg_status=$?
set -e
if [ "$noarg_status" -ne 0 ]; then
    printf 'expected status 0 for no-arg help, got %s\n' "$noarg_status" >&2
    rm -f "$noarg_out"
    exit 1
fi
grep -q "usage: sysdiff" "$noarg_out"
grep -q "compare" "$noarg_out"
rm -f "$noarg_out"

"$ROOT/tests/test_sysdiff_fixture.sh"
