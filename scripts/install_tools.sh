#!/bin/sh
set -e
# Install or ensure toolchain wrappers
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$SCRIPT_DIR/cppcheck" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/clang" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/clang-tidy" 2>/dev/null || true
echo "Toolchain dependencies installed."
exit 0
