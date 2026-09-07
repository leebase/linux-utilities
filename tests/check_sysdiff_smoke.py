"""Bounded deterministic sysdiff smoke; full verification remains in make test."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Five seconds for the incremental strict build plus three one-second
    # comparisons leave headroom inside the manifest's ten-second window.
    try:
        subprocess.run(
            ["make", "build/sysdiff"], cwd=ROOT, check=True, timeout=5,
        )
        with tempfile.TemporaryDirectory(prefix="smoke-", dir=ROOT / "build") as work:
            before = Path(work) / "before.snapshot"
            after = Path(work) / "after.snapshot"
            malformed = Path(work) / "malformed.snapshot"
            before.write_bytes(b"pkg.removed=old\npkg.changed=old\npkg.kept=same\n")
            after.write_bytes(b"pkg.kept=same\npkg.changed=new\npkg.added=new\n")
            malformed.write_bytes(b"invalid record\n")
            cases = (
                (before, before, 0, "no changes\n"),
                (before, after, 1, "+ pkg.added=new\n~ pkg.changed: old -> new\n- pkg.removed=old\n"),
                (malformed, after, 2, ""),
            )
            for left, right, status, stdout in cases:
                result = subprocess.run(
                    [str(ROOT / "build/sysdiff"), "compare", str(left), str(right)],
                    cwd=ROOT, capture_output=True, text=True, check=False, timeout=1,
                )
                if (result.returncode != status or result.stdout != stdout
                        or bool(result.stderr) != (status == 2)):
                    print(f"smoke comparison failed: {result!r}", file=sys.stderr)
                    return 1
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"sysdiff smoke failed: {exc}", file=sys.stderr)
        return 1
    print("ok: sysdiff smoke (unchanged, changed, malformed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
