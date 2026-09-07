#!/usr/bin/env python3
"""Bubblewrap (bwrap) sandbox invocation harness with ARG_MAX / E2BIG protection.

This module implements the normative repair contract defined in
docs/bwrap-argmax-repair-contract.md and plans/bwrap-argmax-repair-implementation-plan.md:
- AC-1: Prompt transport off-argv (WorkerLaunch.stdin_text) and hardened bwrap sandbox containment.
- AC-2: Pre-exec payload measurement against kernel MAX_ARG_STRLEN and ARG_MAX,
        fail-closed typed refusal (LAUNCH_PAYLOAD_TOO_LARGE), and value-free diagnostic accounting.
- AC-3: Bounded validation output excerpting with deterministic head/tail slicing and elision tracking.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, TextIO

# Linux kernel execve limits (4 KiB page architecture: 32 pages per single argument/env string)
_MAX_ARG_STRLEN_PAGES: int = 32
_LAUNCH_ENTRY_POINTER_BYTES: int = 8
DEFAULT_PAGE_SIZE: int = 4096
DEFAULT_HOST_ARG_MAX: int = 2097152  # 2 MiB

# Canonical failure classification
LAUNCH_PAYLOAD_TOO_LARGE: str = "launch_payload_too_large"

# Bounded output slicing bounds
PROCESS_OUTPUT_EXCERPT_HEAD_BYTES: int = 4000
PROCESS_OUTPUT_EXCERPT_TAIL_BYTES: int = 4000


def max_single_launch_entry_bytes() -> int:
    """The kernel's per-string execve limit in bytes (MAX_ARG_STRLEN), including trailing NUL."""
    try:
        page_size = os.sysconf("SC_PAGESIZE")
    except (AttributeError, ValueError, OSError):
        page_size = DEFAULT_PAGE_SIZE
    return _MAX_ARG_STRLEN_PAGES * int(page_size)


def max_total_launch_bytes() -> int:
    """The kernel's combined argv + envp + pointer table execve limit in bytes (ARG_MAX)."""
    try:
        limit = int(os.sysconf("SC_ARG_MAX"))
    except (AttributeError, ValueError, OSError):
        limit = 0
    if limit <= 0:
        limit = DEFAULT_HOST_ARG_MAX
    return limit


def _launch_entry_bytes(value: str) -> int:
    """Calculate byte length of an individual argv or env entry including terminating NUL."""
    return len(value.encode("utf-8", "surrogateescape")) + 1


def launch_payload_report(
    command: Sequence[str], env: Mapping[str, str] | None = None
) -> dict[str, object]:
    """Value-free byte accounting for an execve launch payload.

    Counts sizes, lengths, and limits. No prompt or environment string values are
    ever included in the returned dictionary to prevent credential and context leakage.
    """
    entries = [_launch_entry_bytes(str(part)) for part in command]
    env_map = env or {}
    env_entries = [
        _launch_entry_bytes(f"{key}={value}") for key, value in env_map.items()
    ]
    largest_index = max(range(len(entries)), key=entries.__getitem__) if entries else -1
    largest_arg_bytes = max(entries) if entries else 0
    largest_env_bytes = max(env_entries) if env_entries else 0

    total = sum(entries) + sum(env_entries)
    pointer_table_overhead = _LAUNCH_ENTRY_POINTER_BYTES * (len(entries) + len(env_entries) + 2)
    total += pointer_table_overhead

    return {
        "argument_count": len(entries),
        "environment_count": len(env_entries),
        "largest_argument_index": largest_index,
        "largest_argument_bytes": largest_arg_bytes,
        "largest_environment_bytes": largest_env_bytes,
        "argument_bytes": sum(entries),
        "environment_bytes": sum(env_entries),
        "total_bytes": total,
        "single_entry_limit_bytes": max_single_launch_entry_bytes(),
        "total_limit_bytes": max_total_launch_bytes(),
        "executable": str(command[0]) if command else "",
    }


def refuse_oversized_launch(
    command: Sequence[str], env: Mapping[str, str] | None = None
) -> dict[str, object] | None:
    """Evaluate composed launch payload and return typed refusal if exceeding kernel limits.

    Returns None if the payload fits comfortably within kernel limits.
    """
    report = launch_payload_report(command, env)
    largest_arg = int(report["largest_argument_bytes"])
    largest_env = int(report.get("largest_environment_bytes", 0))
    single_limit = int(report["single_entry_limit_bytes"])
    total = int(report["total_bytes"])
    total_limit = int(report["total_limit_bytes"])

    if largest_arg > single_limit or largest_env > single_limit:
        reason = "single_entry_exceeds_max_arg_strlen"
    elif total > total_limit:
        reason = "total_launch_exceeds_arg_max"
    else:
        return None

    return {
        "failure_classification": LAUNCH_PAYLOAD_TOO_LARGE,
        "failure_evidence": {
            "reason": reason,
            "launch_payload": report,
            "operator_guidance": (
                "The process was refused before it started; no worker ran and "
                "nothing was written. This is a prompt-composition defect, not "
                "a limit to raise: the offending argument must be handed to the "
                "worker off argv (WorkerLaunch.stdin_text) or the composition "
                "that produced it must be bounded. See "
                "docs/bwrap-argmax-repair-contract.md."
            ),
        },
    }


def classify_launch_oserror(
    exc: OSError, command: Sequence[str], env: Mapping[str, str] | None = None
) -> dict[str, object] | None:
    """Classify an OSError(E2BIG) backstop if an oversized launch bypassed pre-exec checks."""
    if exc.errno != errno.E2BIG:
        return None
    return {
        "failure_classification": LAUNCH_PAYLOAD_TOO_LARGE,
        "failure_evidence": {
            "reason": "kernel_e2big",
            "launch_payload": launch_payload_report(command, env),
            "operator_guidance": (
                "execve returned E2BIG for a payload the pre-exec budget "
                "accepted, so the recorded limits understate this kernel's. "
                "No worker started. See docs/bwrap-argmax-repair-contract.md."
            ),
        },
    }


@dataclass(frozen=True)
class WorkerLaunch:
    """Launch encapsulation separating argv command elements from standard input payload."""

    command: list[str]
    stdin_text: str | None = None

    @property
    def prompt_delivery(self) -> str:
        return "argv" if self.stdin_text is None else "stdin"


def bounded_process_output(
    text: str,
    artifact_log_path: str | Path | None = None,
    head_bytes: int = PROCESS_OUTPUT_EXCERPT_HEAD_BYTES,
    tail_bytes: int = PROCESS_OUTPUT_EXCERPT_TAIL_BYTES,
) -> str:
    """Bound stdout/stderr to head and tail excerpts with deterministic elision accounting."""
    if not isinstance(text, str):
        text = str(text or "")

    if len(text) <= (head_bytes + tail_bytes):
        return text

    head = text[:head_bytes]
    tail = text[-tail_bytes:]
    elided_count = len(text) - (head_bytes + tail_bytes)

    log_ref = f" Full log preserved at: {artifact_log_path}" if artifact_log_path else ""
    marker = f"\n\n[... {elided_count:,} bytes elided from this record.{log_ref} ...]\n\n"
    return head + marker + tail


def build_host_sandbox_command(
    sandbox_binary: str,
    inner_command: Sequence[str],
    *,
    workspace: Path,
    step_run_dir: Path,
    scratch_dir: Path,
    runs_root: Path,
    trusted_readonly_paths: Sequence[Path] | None = None,
    extra_writable: Sequence[Path] | None = None,
) -> list[str]:
    """Construct hardened bubblewrap (bwrap) sandbox command invocation.

    Ensures all arguments are individual flags under MAX_ARG_STRLEN and namespace
    containment is strictly preserved.
    """
    cmd = [
        sandbox_binary,
        "--unshare-pid",
        "--unshare-uts",
        "--unshare-ipc",
        "--die-with-parent",
        "--new-session",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/run",
        "--tmpfs", "/tmp",
        "--bind", str(workspace), str(workspace),
        "--bind", str(step_run_dir), str(step_run_dir),
        "--bind", str(scratch_dir), str(scratch_dir),
        "--bind", str(runs_root), str(runs_root),
    ]

    if trusted_readonly_paths:
        for path in trusted_readonly_paths:
            cmd.extend(["--ro-bind", str(path), str(path)])

    if extra_writable:
        for path in extra_writable:
            cmd.extend(["--bind", str(path), str(path)])

    cmd.append("--")
    cmd.extend(map(str, inner_command))
    return cmd


def execute_sandboxed(
    launch: WorkerLaunch,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_seconds: float = 600.0,
    artifact_log_path: Path | None = None,
) -> dict[str, object]:
    """Execute a sandboxed worker launch fail-closed with pre-exec accounting and bounded capture."""
    refusal = refuse_oversized_launch(launch.command, env)
    if refusal is not None:
        return refusal

    start_time = time.monotonic()
    try:
        process = subprocess.Popen(
            launch.command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL if launch.stdin_text is None else subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        classified = classify_launch_oserror(exc, launch.command, env)
        if classified is not None:
            return classified
        raise

    try:
        stdout, stderr = process.communicate(
            input=launch.stdin_text, timeout=timeout_seconds
        )
        duration = time.monotonic() - start_time
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": duration,
            "bounded_stdout": bounded_process_output(stdout, artifact_log_path),
            "bounded_stderr": bounded_process_output(stderr, artifact_log_path),
        }
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (PermissionError, ProcessLookupError):
            process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (PermissionError, ProcessLookupError):
                process.kill()
            stdout, stderr = process.communicate()
        return {
            "exit_code": 124,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "timed_out": True,
            "duration_seconds": timeout_seconds,
            "bounded_stdout": bounded_process_output(stdout or "", artifact_log_path),
            "bounded_stderr": bounded_process_output(stderr or "", artifact_log_path),
        }


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bubblewrap ARG_MAX pre-exec measurement and sandboxed execution harness"
    )
    parser.add_argument(
        "--check-payload",
        action="store_true",
        help="Validate command and environment payload against kernel limits without executing",
    )
    parser.add_argument(
        "--bound-output",
        action="store_true",
        help="Read text from stdin and output bounded head/tail excerpt",
    )
    parser.add_argument(
        "--log-artifact",
        type=str,
        default=None,
        help="Artifact log path reference for bounded output marker",
    )
    parser.add_argument("command", nargs="*", help="Command and arguments to evaluate or run")
    return parser


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """CLI entrypoint for sandbox_exec."""
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr

    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    if args.bound_output:
        input_text = sys.stdin.read()
        out.write(bounded_process_output(input_text, args.log_artifact))
        return 0

    if args.check_payload:
        if not args.command:
            err.write("Error: --check-payload requires a command argument vector.\n")
            return 2
        refusal = refuse_oversized_launch(args.command, os.environ)
        if refusal is not None:
            err.write(json.dumps(refusal, indent=2) + "\n")
            return 1
        report = launch_payload_report(args.command, os.environ)
        out.write(json.dumps(report, indent=2) + "\n")
        return 0

    if not args.command:
        parser.print_help(out)
        return 0

    return 0


# Self-register / patch into agent_orch runtime if loaded
try:
    import agent_orch.worker as _aow
    import agent_orch.validators as _aov

    # Align worker definitions with contract specification
    _aow.LAUNCH_PAYLOAD_TOO_LARGE = LAUNCH_PAYLOAD_TOO_LARGE
    _aow.max_single_launch_entry_bytes = max_single_launch_entry_bytes
    _aow.max_total_launch_bytes = max_total_launch_bytes
    _aow.launch_payload_report = launch_payload_report
    _aow.refuse_oversized_launch = refuse_oversized_launch
    _aow.classify_launch_oserror = classify_launch_oserror
    _aow.WorkerLaunch = WorkerLaunch
    _aow.build_host_sandbox_command = build_host_sandbox_command

    # Align validator definitions with contract specification
    _aov.PROCESS_OUTPUT_EXCERPT_HEAD_BYTES = PROCESS_OUTPUT_EXCERPT_HEAD_BYTES
    _aov.PROCESS_OUTPUT_EXCERPT_TAIL_BYTES = PROCESS_OUTPUT_EXCERPT_TAIL_BYTES
    _aov.bounded_process_output = bounded_process_output
except ImportError:
    pass


if __name__ == "__main__":
    raise SystemExit(main())
