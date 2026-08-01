#!/usr/bin/env bash

set -euo pipefail

# This is intentionally absolute and narrow. Agent-Orch evidence lives in
# the sibling runs root and must never be removed by this cleanup.
readonly SCRATCH_ROOT=/home/lee/projects/linux-utilities-autonomous/.agent-orch-scratch
readonly RUNS_ROOT=/home/lee/projects/linux-utilities-agent-orch-runs
readonly RETENTION_DAYS=2

if [[ ! -d "$SCRATCH_ROOT" || -L "$SCRATCH_ROOT" ]]; then
    printf 'refusing scratch cleanup: missing or symlinked root: %s\n' "$SCRATCH_ROOT" >&2
    exit 1
fi
if [[ "$(realpath -e -- "$SCRATCH_ROOT")" != "$SCRATCH_ROOT" ]]; then
    printf 'refusing scratch cleanup: root resolves unexpectedly: %s\n' "$SCRATCH_ROOT" >&2
    exit 1
fi
if [[ ! -d "$RUNS_ROOT" || -L "$RUNS_ROOT" ]]; then
    printf 'refusing scratch cleanup: missing or symlinked evidence root: %s\n' "$RUNS_ROOT" >&2
    exit 1
fi

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
elif [[ $# -ne 0 ]]; then
    printf 'usage: %s [--dry-run]\n' "$0" >&2
    exit 2
fi

is_active_or_unknown() {
    local run_id=$1
    local metadata
    for metadata in "$RUNS_ROOT/$run_id/run.json" "$RUNS_ROOT/$run_id/progress.json"; do
        if [[ ! -f "$metadata" ]]; then
            return 0
        fi
        if grep -Eq '"status"[[:space:]]*:[[:space:]]*"(RUNNING|WAITING_APPROVAL)"' "$metadata"; then
            return 0
        fi
    done
    return 1
}

removed=0
skipped=0
retention_minutes=$((RETENTION_DAYS * 1440))
while IFS= read -r -d '' candidate; do
    run_id=${candidate##*/}
    if [[ ! "$run_id" =~ ^[0-9a-f]{12}$ ]]; then
        printf 'retaining non-run scratch directory: %s\n' "$candidate" >&2
        skipped=$((skipped + 1))
        continue
    fi
    if is_active_or_unknown "$run_id"; then
        printf 'retaining active or unverified run scratch: %s\n' "$candidate" >&2
        skipped=$((skipped + 1))
        continue
    fi
    if [[ $dry_run -eq 1 ]]; then
        printf 'would-remove %s\n' "$candidate"
    else
        printf 'remove %s\n' "$candidate"
        rm -rf -- "$candidate"
    fi
    removed=$((removed + 1))
done < <(find -P "$SCRATCH_ROOT" -mindepth 1 -maxdepth 1 -type d -mmin +"$retention_minutes" -print0)

if [[ $dry_run -eq 1 ]]; then
    printf 'scratch cleanup complete: %d candidates, %d retained\n' "$removed" "$skipped"
else
    printf 'scratch cleanup complete: %d removed, %d retained\n' "$removed" "$skipped"
fi
