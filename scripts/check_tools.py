#!/usr/bin/env python3
"""Check local availability of routed Agent-Orch worker harnesses."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, TextIO


@dataclass(frozen=True)
class HarnessRequirement:
    """A routed harness that must be discoverable before governed work runs."""

    name: str
    role: str
    executables: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class HarnessProbeResult:
    """Result of checking one routed harness requirement."""

    requirement: HarnessRequirement
    available: bool
    executable: str | None
    path: str | None
    reason: str

    @property
    def name(self) -> str:
        return self.requirement.name


DEFAULT_HARNESSES: tuple[HarnessRequirement, ...] = (
    HarnessRequirement(
        name="codex_cli",
        role="implementation_worker",
        executables=("codex",),
        description="primary implementation worker harness",
    ),
    HarnessRequirement(
        name="claude_code",
        role="slice_reviewer",
        executables=("claude",),
        description="review worker harness",
    ),
)


def _env_path(env: Mapping[str, str] | None) -> str:
    if env is None:
        return os.environ.get("PATH", "")
    return env.get("PATH", "")


def probe_harness(
    requirement: HarnessRequirement, env: Mapping[str, str] | None = None
) -> HarnessProbeResult:
    """Probe a single harness by finding one of its configured executables."""

    search_path = _env_path(env)
    for executable in requirement.executables:
        resolved = shutil.which(executable, path=search_path)
        if resolved is not None:
            return HarnessProbeResult(
                requirement=requirement,
                available=True,
                executable=executable,
                path=resolved,
                reason=f"found {executable} on PATH",
            )

    executables = ", ".join(requirement.executables)
    return HarnessProbeResult(
        requirement=requirement,
        available=False,
        executable=None,
        path=None,
        reason=f"none of the required executables were found on PATH: {executables}",
    )


def probe_harnesses(
    requirements: Iterable[HarnessRequirement],
    env: Mapping[str, str] | None = None,
) -> list[HarnessProbeResult]:
    """Probe all required routed harnesses and return every result."""

    return [probe_harness(requirement, env=env) for requirement in requirements]


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Check local routed worker infrastructure required by this repository."
        )
    )


def _print_success(results: Sequence[HarnessProbeResult], stdout: TextIO) -> None:
    for result in results:
        print(
            f"available: {result.name} ({result.requirement.role}) "
            f"via {result.executable} at {result.path}",
            file=stdout,
        )


def _print_failure(missing: Sequence[HarnessProbeResult], stderr: TextIO) -> None:
    print(
        "Missing routed worker infrastructure for required Agent-Orch harnesses:",
        file=stderr,
    )
    for result in missing:
        executables = ", ".join(result.requirement.executables)
        print(
            f"- {result.name} ({result.requirement.role}, "
            f"{result.requirement.description}) is unavailable: {result.reason}. "
            f"Expected executable(s): {executables}",
            file=stderr,
        )


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """CLI entrypoint. Return a process status instead of exiting directly."""

    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = _build_parser()
    parser.parse_args(argv)

    results = probe_harnesses(DEFAULT_HARNESSES, env=env)
    missing = [result for result in results if not result.available]
    if missing:
        _print_failure(missing, err)
        return 1

    _print_success(results, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
