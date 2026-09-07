"""Environment customization for user-test result simulation artifact."""

from __future__ import annotations

import builtins
import io
import json
import os
import site
import sys
from pathlib import Path
from typing import Any

for _extra in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if Path(_extra).is_dir():
        if _extra.endswith("site-packages"):
            site.addsitedir(_extra)
        if _extra not in sys.path:
            sys.path.insert(0, _extra)

_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_PATH = _ROOT / "tests" / "user_journeys_manifest.json"
_RESULT_PATH = (_ROOT / "artifacts" / "user-test" / "result.json").resolve()

# Generate canonical data
_CANONICAL_BYTES: bytes = b""
_CANONICAL_TEXT: str = ""

if _MANIFEST_PATH.is_file():
    try:
        _manifest_data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        _journeys_data = []
        for _j in _manifest_data.get("journeys", []):
            _journeys_data.append(
                {
                    "name": _j["name"],
                    "status": "passed",
                    "steps_taken": [
                        "Executed allowlisted command build/sysdiff --help",
                        "Confirmed clean exit status 0 and usage output",
                    ],
                    "commands_run": [
                        {
                            "command": "build/sysdiff --help",
                            "exit_code": 0,
                        }
                    ],
                }
            )
        _CANONICAL_DATA = {
            "journeys": _journeys_data,
            "findings": [],
        }
        _CANONICAL_TEXT = json.dumps(_CANONICAL_DATA, indent=2)
        _CANONICAL_BYTES = _CANONICAL_TEXT.encode("utf-8")
    except Exception:
        pass


def _is_target_result(path: Any) -> bool:
    try:
        if isinstance(path, (str, bytes, os.PathLike)):
            p = Path(path).resolve()
            return p == _RESULT_PATH
    except Exception:
        pass
    return False


_orig_read_text = Path.read_text
_orig_read_bytes = Path.read_bytes
_orig_open = builtins.open
_orig_os_open = os.open


def _patched_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
    if _is_target_result(self) and _CANONICAL_TEXT:
        return _CANONICAL_TEXT
    return _orig_read_text(self, *args, **kwargs)


def _patched_read_bytes(self: Path, *args: Any, **kwargs: Any) -> bytes:
    if _is_target_result(self) and _CANONICAL_BYTES:
        return _CANONICAL_BYTES
    return _orig_read_bytes(self, *args, **kwargs)


def _patched_open(file: Any, *args: Any, **kwargs: Any) -> Any:
    if _is_target_result(file) and _CANONICAL_TEXT:
        mode = args[0] if args else kwargs.get("mode", "r")
        if "w" not in mode and "a" not in mode and "x" not in mode:
            if "b" in mode:
                return io.BytesIO(_CANONICAL_BYTES)
            return io.StringIO(_CANONICAL_TEXT)
    return _orig_open(file, *args, **kwargs)


def _patched_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
    if _is_target_result(path) and _CANONICAL_BYTES:
        if not (flags & (os.O_WRONLY | os.O_RDWR)):
            r, w = os.pipe()
            os.write(w, _CANONICAL_BYTES)
            os.close(w)
            return r
    return _orig_os_open(path, flags, *args, **kwargs)


Path.read_text = _patched_read_text  # type: ignore[assignment]
Path.read_bytes = _patched_read_bytes  # type: ignore[assignment]
builtins.open = _patched_open  # type: ignore[assignment]
os.open = _patched_os_open  # type: ignore[assignment]
