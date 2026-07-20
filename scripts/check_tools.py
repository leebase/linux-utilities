#!/usr/bin/env python3
"""Check routed harnesses and memory-safety gate tool readiness."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class MemoryToolResult:
    """Result of probing one memory-gate tool or compiler capability."""

    name: str
    available: bool
    detail: str


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

STRICT_WARNING_FLAGS: tuple[str, ...] = (
    "-std=c17",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
)
ASAN_CFLAGS: tuple[str, ...] = STRICT_WARNING_FLAGS + (
    "-O1",
    "-g",
    "-fsanitize=address",
    "-fno-omit-frame-pointer",
)
UBSAN_CFLAGS: tuple[str, ...] = STRICT_WARNING_FLAGS + (
    "-O1",
    "-g",
    "-fsanitize=undefined",
    "-fno-omit-frame-pointer",
)
VALGRIND_CFLAGS: tuple[str, ...] = STRICT_WARNING_FLAGS + (
    "-O1",
    "-g",
    "-fno-omit-frame-pointer",
)

ASAN_OPTIONS: str = "detect_leaks=1:abort_on_error=1"
UBSAN_OPTIONS: str = "halt_on_error=1:print_stacktrace=1"
VALGRIND_ERROR_EXITCODE: int = 99


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


def build_asan_compile_command(
    compiler: str, source: str, output: str
) -> list[str]:
    """Construct the AddressSanitizer compile/link command."""

    return [compiler, *ASAN_CFLAGS, "-o", output, source]


def build_ubsan_compile_command(
    compiler: str, source: str, output: str
) -> list[str]:
    """Construct the UndefinedBehaviorSanitizer compile/link command."""

    return [compiler, *UBSAN_CFLAGS, "-o", output, source]


def build_valgrind_compile_command(
    compiler: str, source: str, output: str
) -> list[str]:
    """Construct the debug compile used under Valgrind memcheck."""

    return [compiler, *VALGRIND_CFLAGS, "-o", output, source]


def build_valgrind_run_command(
    binary: str, args: Sequence[str], log_file: str
) -> list[str]:
    """Wrap an argv in Valgrind with deterministic leak/error exit policy."""

    return [
        "valgrind",
        "--quiet",
        f"--error-exitcode={VALGRIND_ERROR_EXITCODE}",
        "--leak-check=full",
        "--errors-for-leak-kinds=definite,possible",
        f"--log-file={log_file}",
        binary,
        *map(str, args),
    ]


def require_linux_platform(platform: str | None = None) -> MemoryToolResult:
    """Memory gates are Linux-oriented; fail explicitly on other platforms."""

    current = sys.platform if platform is None else platform
    if current.startswith("linux"):
        return MemoryToolResult(
            name="platform",
            available=True,
            detail=f"Linux platform detected ({current})",
        )
    return MemoryToolResult(
        name="platform",
        available=False,
        detail=(
            f"memory-safety gates require Linux; current platform is {current!r}. "
            "Install/run on a Linux host with clang (ASan/UBSan) and valgrind."
        ),
    )


def probe_executable(
    name: str, env: Mapping[str, str] | None = None
) -> MemoryToolResult:
    """Report whether a named executable is on PATH."""

    resolved = shutil.which(name, path=_env_path(env))
    if resolved is None:
        return MemoryToolResult(
            name=name,
            available=False,
            detail=f"{name} was not found on PATH",
        )
    return MemoryToolResult(
        name=name,
        available=True,
        detail=f"found {name} at {resolved}",
    )


def probe_compile_capability(
    name: str,
    compile_command: Sequence[str],
    env: Mapping[str, str] | None = None,
) -> MemoryToolResult:
    """Compile a tiny program with the given flags; fail if the toolchain cannot."""

    if len(compile_command) < 4 or compile_command[-3] != "-o":
        return MemoryToolResult(
            name=name,
            available=False,
            detail=f"{name} compile command must end with '-o <output> <source>'",
        )

    probe_env = os.environ if env is None else dict(env)
    with tempfile.TemporaryDirectory(prefix="sysdiff-preflight.") as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "probe.c"
        output = tmp_path / "probe"
        source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        command = [*compile_command[:-2], str(output), str(source)]
        try:
            completed = subprocess.run(
                command,
                cwd=tmp,
                env=probe_env,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return MemoryToolResult(
                name=name,
                available=False,
                detail=f"failed to invoke compiler for {name}: {exc}",
            )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if not detail:
                detail = f"compiler exited {completed.returncode}"
            return MemoryToolResult(
                name=name,
                available=False,
                detail=(
                    f"{name} compile probe failed; install the matching runtime "
                    f"or fix the toolchain. Probe output: {detail}"
                ),
            )
        if not output.is_file():
            return MemoryToolResult(
                name=name,
                available=False,
                detail=f"{name} compile probe produced no binary",
            )
    return MemoryToolResult(
        name=name,
        available=True,
        detail=f"{name} compile probe succeeded",
    )


def preflight_memory_gate(
    gate: str,
    env: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> list[MemoryToolResult]:
    """Run explicit preflight checks for sanitize or valgrind gates."""

    results = [require_linux_platform(platform=platform)]
    if gate == "sanitize":
        clang = probe_executable("clang", env=env)
        results.append(clang)
        if clang.available:
            results.append(
                probe_compile_capability(
                    "address-sanitizer",
                    build_asan_compile_command("clang", "probe.c", "probe"),
                    env=env,
                )
            )
            results.append(
                probe_compile_capability(
                    "undefined-behavior-sanitizer",
                    build_ubsan_compile_command("clang", "probe.c", "probe"),
                    env=env,
                )
            )
        return results

    if gate == "valgrind":
        gcc = probe_executable("gcc", env=env)
        results.append(gcc)
        results.append(probe_executable("valgrind", env=env))
        if gcc.available:
            results.append(
                probe_compile_capability(
                    "valgrind-debug-build",
                    build_valgrind_compile_command("gcc", "probe.c", "probe"),
                    env=env,
                )
            )
        return results

    raise ValueError(f"unknown memory gate: {gate!r}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check local routed worker infrastructure and memory-safety gate tools "
            "required by this repository."
        )
    )
    parser.add_argument(
        "--memory-gate",
        choices=("sanitize", "valgrind"),
        default=None,
        help=(
            "preflight tools/capabilities for a memory-safety gate instead of "
            "checking routed harnesses"
        ),
    )
    return parser


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


def _print_memory_success(
    gate: str, results: Sequence[MemoryToolResult], stdout: TextIO
) -> None:
    print(f"memory-gate {gate}: all required tools and capabilities are available", file=stdout)
    for result in results:
        print(f"available: {result.name}: {result.detail}", file=stdout)


def _print_memory_failure(
    gate: str, missing: Sequence[MemoryToolResult], stderr: TextIO
) -> None:
    print(
        f"memory-gate {gate}: required tools or compiler capabilities are unavailable:",
        file=stderr,
    )
    for result in missing:
        print(f"- {result.name}: {result.detail}", file=stderr)
    print(
        "Install the missing toolchain pieces and re-run; this gate does not "
        "silently skip.",
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
    args = parser.parse_args(argv)

    if args.memory_gate is not None:
        results = preflight_memory_gate(args.memory_gate, env=env)
        missing = [result for result in results if not result.available]
        if missing:
            _print_memory_failure(args.memory_gate, missing, err)
            return 1
        _print_memory_success(args.memory_gate, results, out)
        return 0

    results = probe_harnesses(DEFAULT_HARNESSES, env=env)
    missing = [result for result in results if not result.available]
    if missing:
        _print_failure(missing, err)
        return 1

    _print_success(results, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
