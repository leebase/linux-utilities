"""Pytest configuration and environment setup for the linux-utilities suite."""

from __future__ import annotations

import os
import site
import sys
from pathlib import Path

# Ensure src/ is importable
_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = str(_ROOT / "src")
if _SRC_DIR not in sys.path and Path(_SRC_DIR).is_dir():
    sys.path.insert(0, _SRC_DIR)

# Propagate PYTHONPATH to child processes for sitecustomize support
_existing_pythonpath = os.environ.get("PYTHONPATH", "")
if _SRC_DIR not in _existing_pythonpath.split(os.pathsep):
    os.environ["PYTHONPATH"] = (
        f"{_SRC_DIR}{os.pathsep}{_existing_pythonpath}"
        if _existing_pythonpath
        else _SRC_DIR
    )

for _extra_path in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if Path(_extra_path).is_dir():
        if _extra_path.endswith("site-packages"):
            site.addsitedir(_extra_path)
        if _extra_path not in sys.path:
            sys.path.insert(0, _extra_path)
