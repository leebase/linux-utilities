#!/bin/sh
set -e
# Verify and ensure toolchain availability
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$SCRIPT_DIR/cppcheck" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/clang" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/clang-tidy" 2>/dev/null || true

# Verify tools can be invoked or wrappers exist
for tool in clang cppcheck clang-tidy; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        if [ ! -x "$SCRIPT_DIR/$tool" ]; then
            echo "error: $tool is not available on PATH or in $SCRIPT_DIR" >&2
            exit 1
        fi
    fi
done

echo "Toolchain dependencies verified."
exit 0
