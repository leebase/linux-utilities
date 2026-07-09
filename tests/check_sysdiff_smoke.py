"""Run the project smoke script from Agent-Orch's smoke_runner."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    completed = subprocess.run(
        ["bash", "scripts/smoke.sh"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
