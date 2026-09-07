"""Child-interpreter path setup for repository tests."""

from __future__ import annotations

import site
import sys
from pathlib import Path

for _extra in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if Path(_extra).is_dir():
        if _extra.endswith("site-packages"):
            site.addsitedir(_extra)
        if _extra not in sys.path:
            sys.path.insert(0, _extra)
