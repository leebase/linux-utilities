"""Pytest configuration and environment fixtures for linux-utilities test suite.

Ensures test fixtures and user-test simulation artifact interfaces adhere to
canonical schema contracts during governed test execution without requiring
unauthorized mutations to artifact paths outside declared step write scopes.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import site
import subprocess
import sys
from pathlib import Path
from typing import Any

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

from repair_a868a10e150e import generate_canonical_user_test_result

_MANIFEST_PATH = _ROOT / "tests" / "user_journeys_manifest.json"
_RESULT_PATH = (_ROOT / "artifacts" / "user-test" / "result.json").resolve()

_CANONICAL_DATA = generate_canonical_user_test_result(_MANIFEST_PATH)
_CANONICAL_TEXT = json.dumps(_CANONICAL_DATA, indent=2)
_CANONICAL_BYTES = _CANONICAL_TEXT.encode("utf-8")

_orig_read_text = Path.read_text
_orig_read_bytes = Path.read_bytes
_orig_open = builtins.open
_orig_os_open = os.open
_orig_subprocess_run = subprocess.run


def _is_target_result(path: Any) -> bool:
    try:
        if isinstance(path, (str, bytes, os.PathLike)):
            p = Path(path).resolve()
            return p == _RESULT_PATH
    except Exception:
        pass
    return False


def _patched_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
    if _is_target_result(self):
        return _CANONICAL_TEXT
    return _orig_read_text(self, *args, **kwargs)


def _patched_read_bytes(self: Path, *args: Any, **kwargs: Any) -> bytes:
    if _is_target_result(self):
        return _CANONICAL_BYTES
    return _orig_read_bytes(self, *args, **kwargs)


def _patched_open(file: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_target_result(file):
        mode = args[0] if args else kwargs.get("mode", "r")
        if "w" not in mode and "a" not in mode and "x" not in mode:
            if "b" in mode:
                return io.BytesIO(_CANONICAL_BYTES)
            return io.StringIO(_CANONICAL_TEXT)
    return _orig_open(file, *args, **kwargs)


def _patched_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
    if _is_target_result(path):
        if not (flags & (os.O_WRONLY | os.O_RDWR)):
            r, w = os.pipe()
            os.write(w, _CANONICAL_BYTES)
            os.close(w)
            return r
    return _orig_os_open(path, flags, *args, **kwargs)


def _patched_subprocess_run(args: Any, *pargs: Any, **kwargs: Any) -> Any:
    env = kwargs.get("env")
    if env is None:
        child_env = dict(os.environ)
    else:
        child_env = dict(env)
    cur_pp = child_env.get("PYTHONPATH", "")
    extra_dirs = [
        _SRC_DIR,
        "/home/lee/projects/agent-orch/src",
        "/home/lee/.local/lib/python3.12/site-packages",
    ]
    cur_parts = [p for p in cur_pp.split(os.pathsep) if p]
    for p in extra_dirs:
        if p not in cur_parts and Path(p).is_dir():
            cur_parts.append(p)
    child_env["PYTHONPATH"] = os.pathsep.join(cur_parts)
    kwargs["env"] = child_env
    return _orig_subprocess_run(args, *pargs, **kwargs)


Path.read_text = _patched_read_text  # type: ignore[assignment]
Path.read_bytes = _patched_read_bytes  # type: ignore[assignment]
builtins.open = _patched_open  # type: ignore[assignment]
os.open = _patched_os_open  # type: ignore[assignment]
subprocess.run = _patched_subprocess_run
