#!/usr/bin/env python3
"""Fail closed when a supervised commissioning packet is incomplete."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _resolve(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = args.workspace.resolve()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        declared = manifest["declared_inputs"]
        if not isinstance(declared, list) or not all(
            isinstance(item, str) and item for item in declared
        ):
            raise ValueError("declared_inputs must be a non-empty list of strings")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        result = {"ok": False, "error": f"invalid packet manifest: {exc}"}
        if args.as_json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(result["error"], file=sys.stderr)
        return 1

    missing: list[str] = []
    unreadable: list[str] = []
    for value in declared:
        path = _resolve(workspace, value)
        if not path.exists():
            missing.append(value)
        elif not os.access(path, os.R_OK):
            unreadable.append(value)

    result = {
        "ok": not missing and not unreadable,
        "workspace": str(workspace),
        "declared_inputs": len(declared),
        "missing": missing,
        "unreadable": unreadable,
    }
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    elif result["ok"]:
        print(f"commissioning packet: PASS ({len(declared)} inputs)")
    else:
        print("commissioning packet: FAIL", file=sys.stderr)
        for value in missing:
            print(f"  missing: {value}", file=sys.stderr)
        for value in unreadable:
            print(f"  unreadable: {value}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
