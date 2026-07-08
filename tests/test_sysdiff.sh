#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/build/sysdiff"

"$BIN" --help | grep -q "usage: sysdiff"
"$BIN" --version | grep -q "sysdiff 0.1.0"
