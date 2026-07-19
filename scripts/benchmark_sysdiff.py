#!/usr/bin/env python3
"""Deterministic Linux performance and resource benchmark for sysdiff.

Standard-library only. Builds sysdiff in a temporary directory, times startup
and a fixed controlled-fixture compare workload, measures per-run peak RSS,
and emits a stable JSON report. Compilation and fixture setup are never part
of timed samples. Environment variables and caller-supplied binary paths are
not trusted for the CLI entry point.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

SCHEMA_VERSION = 1

MEASUREMENT_BASELINE = "baseline_ms_median"
MEASUREMENT_STARTUP = "startup_ms_median"
MEASUREMENT_FIXTURE = "fixture_ms_median"
MEASUREMENT_PEAK_RSS = "peak_rss_kib"

DEFAULT_WARMUPS = 1
DEFAULT_SAMPLE_COUNT = 5

# Fixed controlled-fixture size: large enough that compare work exceeds the
# Python fork/exec spawn floor recorded as baseline_ms_median.
CONTROLLED_FIXTURE_ENTRY_COUNT = 8000

# Conservative release guardrails for this small C utility (visible in --help).
# Fixture limit re-derived for the 8000-entry workload (~4 ms median on an
# idle Linux host); still a crash/regression guardrail, not a microbenchmark.
DEFAULT_THRESHOLDS: dict[str, float] = {
    MEASUREMENT_STARTUP: 200.0,  # ms
    MEASUREMENT_FIXTURE: 100.0,  # ms (scaled fixture; was 1000 for 5-line pair)
    MEASUREMENT_PEAK_RSS: 32768.0,  # KiB (32 MiB)
}

DEFAULT_CHILD_TIMEOUT_S = 30.0
COMPILE_FLAGS: tuple[str, ...] = (
    "-std=c17",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
    "-O2",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src" / "sysdiff.c"

SPAWN_BASELINE_ARGV: tuple[str, ...] = ("/bin/true",)


def aggregate_samples(samples: Sequence[float]) -> float:
    """Return a deterministic median (mean of center pair when length is even)."""

    if not samples:
        raise ValueError("samples must be non-empty")
    ordered = sorted(float(value) for value in samples)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def thresholds_passed(
    measurements: Mapping[str, float],
    thresholds: Mapping[str, float],
) -> bool:
    """Return True when every measurement is within its threshold (inclusive)."""

    for key, limit in thresholds.items():
        if key not in measurements:
            return False
        if float(measurements[key]) > float(limit):
            return False
    return True


def report_exit_status(report: Mapping[str, Any]) -> int:
    return 0 if bool(report.get("passed")) else 1


def encode_report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_report(
    *,
    measurements: Mapping[str, float],
    thresholds: Mapping[str, float],
    samples: Mapping[str, Sequence[float]],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    measurement_map = {
        MEASUREMENT_STARTUP: float(measurements[MEASUREMENT_STARTUP]),
        MEASUREMENT_FIXTURE: float(measurements[MEASUREMENT_FIXTURE]),
        MEASUREMENT_PEAK_RSS: float(measurements[MEASUREMENT_PEAK_RSS]),
    }
    if MEASUREMENT_BASELINE in measurements:
        measurement_map[MEASUREMENT_BASELINE] = float(measurements[MEASUREMENT_BASELINE])
    threshold_map = {
        MEASUREMENT_STARTUP: float(thresholds[MEASUREMENT_STARTUP]),
        MEASUREMENT_FIXTURE: float(thresholds[MEASUREMENT_FIXTURE]),
        MEASUREMENT_PEAK_RSS: float(thresholds[MEASUREMENT_PEAK_RSS]),
    }
    sample_map = {key: [float(v) for v in values] for key, values in samples.items()}
    meta = dict(metadata)
    return {
        "metadata": meta,
        "measurements": measurement_map,
        "passed": thresholds_passed(measurement_map, threshold_map),
        "samples": sample_map,
        "schema_version": SCHEMA_VERSION,
        "thresholds": threshold_map,
    }


def generate_controlled_snapshot_texts(
    entry_count: int = CONTROLLED_FIXTURE_ENTRY_COUNT,
) -> tuple[str, str]:
    """Build deterministic before/after snapshot bodies of fixed entry counts.

    Mix per decade of keys: changed (0), removed (1), added (2), unchanged (3-9).
    Keys use valid ``bench.kNNNNNN`` syntax (must contain a dot).
    """

    if entry_count < 1:
        raise ValueError("entry_count must be >= 1")
    before_lines: list[str] = []
    after_lines: list[str] = []
    for index in range(entry_count):
        key = f"bench.k{index:06d}"
        slot = index % 10
        if slot == 0:
            before_lines.append(f"{key}=old")
            after_lines.append(f"{key}=new")
        elif slot == 1:
            before_lines.append(f"{key}=gone")
        elif slot == 2:
            after_lines.append(f"{key}=added")
        else:
            before_lines.append(f"{key}=same")
            after_lines.append(f"{key}=same")
    return ("\n".join(before_lines) + "\n", "\n".join(after_lines) + "\n")


def prepare_controlled_fixtures(directory: Path | str) -> tuple[Path, Path]:
    """Write the fixed before/after snapshots used by the fixture workflow."""

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    before = root / "before.snapshot"
    after = root / "after.snapshot"
    before_text, after_text = generate_controlled_snapshot_texts()
    before.write_text(before_text, encoding="utf-8")
    after.write_text(after_text, encoding="utf-8")
    return before, after


def _terminate_process(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass
    if proc.poll() is not None:
        return
    try:
        if hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
        else:
            proc.kill()
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass


def _normalize_expected_statuses(expected_statuses: Sequence[int]) -> frozenset[int]:
    if not expected_statuses:
        raise ValueError("expected_statuses must be non-empty")
    return frozenset(int(status) for status in expected_statuses)


def _assert_exit_status(
    returncode: int | None,
    expected_statuses: Sequence[int],
    argv: Sequence[str],
) -> None:
    allowed = _normalize_expected_statuses(expected_statuses)
    status = -1 if returncode is None else int(returncode)
    if status not in allowed:
        allowed_text = ", ".join(str(value) for value in sorted(allowed))
        raise RuntimeError(
            f"child exited with status {status}, expected one of [{allowed_text}]: "
            f"{' '.join(argv)}"
        )


def measure_runtime_ms(
    argv: Sequence[str],
    *,
    expected_statuses: Sequence[int] = (0,),
    timeout_s: float | None = DEFAULT_CHILD_TIMEOUT_S,
) -> float:
    """Time only the child process with a monotonic clock; clean up on timeout.

    ``expected_statuses`` rejects unexpected exits so a crashing or rejecting
    binary cannot produce a deceptively fast sample.
    """

    if not argv:
        raise ValueError("argv must be non-empty")
    allowed = _normalize_expected_statuses(expected_statuses)
    start = time.monotonic()
    proc = subprocess.Popen(
        list(argv),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _terminate_process(proc)
            raise TimeoutError(
                f"child exceeded timeout ({timeout_s}s): {' '.join(argv)}"
            ) from exc
    finally:
        _terminate_process(proc)
    _assert_exit_status(proc.returncode, allowed, argv)
    elapsed_ms = (time.monotonic() - start) * 1000.0
    return elapsed_ms


def _require_linux() -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("peak RSS measurement requires Linux")


# argv[1] = report path; argv[2..] = measured command.
# Child stdout/stderr go to /dev/null so they cannot collide with the report
# channel (review F001). Uses waitpid + getrusage(RUSAGE_CHILDREN) so the
# helper stays clean under -std=c17 without undeclared wait4 (review F003).
_RSS_WRAPPER_SOURCE = """\
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    pid_t pid;
    int status;
    int child_status;
    int null_fd;
    struct rusage usage;
    FILE *report;

    if (argc < 3) {
        return 2;
    }
    pid = fork();
    if (pid < 0) {
        return 2;
    }
    if (pid == 0) {
        null_fd = open("/dev/null", O_RDWR);
        if (null_fd >= 0) {
            (void)dup2(null_fd, STDOUT_FILENO);
            (void)dup2(null_fd, STDERR_FILENO);
            if (null_fd > STDERR_FILENO) {
                close(null_fd);
            }
        }
        execvp(argv[2], argv + 2);
        _exit(127);
    }
    if (waitpid(pid, &status, 0) < 0) {
        return 2;
    }
    if (getrusage(RUSAGE_CHILDREN, &usage) != 0) {
        return 2;
    }
    if (WIFEXITED(status)) {
        child_status = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        child_status = 128 + WTERMSIG(status);
    } else {
        return 2;
    }
    /* Linux ru_maxrss is already kibibytes; a tiny parent avoids Python fork inflation.
     * Report file line 1: peak RSS KiB. Line 2: wrapped command exit status. */
    report = fopen(argv[1], "w");
    if (report == NULL) {
        return 2;
    }
    if (fprintf(report, "%ld\\n%d\\n", usage.ru_maxrss, child_status) < 0) {
        (void)fclose(report);
        return 2;
    }
    if (fclose(report) != 0) {
        return 2;
    }
    return 0;
}
"""

_RSS_WRAPPER_PATH: Path | None = None
_RSS_WRAPPER_WORK: Path | None = None


def _rss_wrapper_path() -> Path:
    """Compile once (into a temp file) a tiny fork/exec RSS reporter."""

    global _RSS_WRAPPER_PATH, _RSS_WRAPPER_WORK
    if _RSS_WRAPPER_PATH is not None and _RSS_WRAPPER_PATH.is_file():
        return _RSS_WRAPPER_PATH
    compiler = _find_compiler()
    work = Path(tempfile.mkdtemp(prefix="sysdiff-rss-wrap."))
    src = work / "rss_wrap.c"
    binary = work / "rss_wrap"
    src.write_text(_RSS_WRAPPER_SOURCE, encoding="utf-8")
    result = subprocess.run(
        [
            compiler,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            "-o",
            str(binary),
            str(src),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not binary.is_file():
        shutil.rmtree(work, ignore_errors=True)
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"failed to compile RSS wrapper: {detail}")
    _RSS_WRAPPER_WORK = work
    _RSS_WRAPPER_PATH = binary
    atexit.register(lambda path=work: shutil.rmtree(path, ignore_errors=True))
    return binary


def _parse_gnu_time_rss_file(text: str) -> int:
    """Parse GNU time -f %M -o output; last numeric line is KiB."""

    if not text.strip():
        raise RuntimeError("GNU time produced empty RSS output")
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            value = int(stripped)
        except ValueError:
            continue
        if value <= 0:
            raise RuntimeError(f"invalid peak RSS sample: {value}")
        return value
    raise RuntimeError(f"GNU time produced no numeric RSS line: {text!r}")


def _peak_rss_via_gnu_time(
    argv: Sequence[str],
    timeout_s: float | None,
    expected_statuses: Sequence[int],
) -> int:
    """Use GNU /usr/bin/time -f %M (KiB). Avoids Python fork ru_maxrss inflation."""

    time_bin = Path("/usr/bin/time")
    if not time_bin.is_file():
        raise RuntimeError("GNU time not found at /usr/bin/time")
    out_fd, out_name = tempfile.mkstemp(prefix="sysdiff-rss.")
    os.close(out_fd)
    out_path = Path(out_name)
    try:
        cmd = [str(time_bin), "-f", "%M", "-o", str(out_path), "--", *list(argv)]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            try:
                proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired as exc:
                _terminate_process(proc)
                raise TimeoutError(
                    f"RSS time(1) exceeded timeout ({timeout_s}s): {' '.join(argv)}"
                ) from exc
        finally:
            _terminate_process(proc)
        # GNU time exits with the wrapped command's status.
        _assert_exit_status(proc.returncode, expected_statuses, argv)
        text = out_path.read_text(encoding="utf-8", errors="replace")
        return _parse_gnu_time_rss_file(text)
    finally:
        out_path.unlink(missing_ok=True)


def _peak_rss_via_tiny_wrapper(
    argv: Sequence[str],
    timeout_s: float | None,
    expected_statuses: Sequence[int],
) -> int:
    """Measure via a tiny C fork/exec parent so ru_maxrss is not Python-sized.

    The wrapper writes its two-line report to a dedicated tempfile (argv[1]) and
    redirects the measured child's stdout/stderr to /dev/null, so child output
    cannot collide with the report channel.
    """

    wrapper = _rss_wrapper_path()
    out_fd, out_name = tempfile.mkstemp(prefix="sysdiff-rss-wrap-out.")
    os.close(out_fd)
    out_path = Path(out_name)
    try:
        cmd = [str(wrapper), str(out_path), *list(argv)]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            try:
                _out, err = proc.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired as exc:
                _terminate_process(proc)
                raise TimeoutError(
                    f"RSS wrapper exceeded timeout ({timeout_s}s): {' '.join(argv)}"
                ) from exc
        finally:
            _terminate_process(proc)
        if proc.returncode not in (0, None):
            detail = (err or "").strip()
            raise RuntimeError(
                f"RSS wrapper failed with status {proc.returncode}: {detail}"
            )
        text = out_path.read_text(encoding="utf-8", errors="replace").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            raise RuntimeError(
                "RSS wrapper produced incomplete output "
                "(need RSS KiB and child status)"
            )
        value = int(lines[0])
        child_status = int(lines[1])
        if value <= 0:
            raise RuntimeError(f"invalid peak RSS sample: {value}")
        _assert_exit_status(child_status, expected_statuses, argv)
        return value
    finally:
        out_path.unlink(missing_ok=True)


def _peak_rss_via_proc_vmhwm(
    argv: Sequence[str],
    timeout_s: float | None,
    expected_statuses: Sequence[int],
) -> int:
    """Poll /proc/<pid>/status VmHWM while the child runs (KiB on Linux)."""

    proc = subprocess.Popen(
        list(argv),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    peak = 0
    status_path = Path(f"/proc/{proc.pid}/status")
    deadline = None if timeout_s is None else (time.monotonic() + float(timeout_s))
    try:
        while True:
            if deadline is not None and time.monotonic() > deadline:
                _terminate_process(proc)
                raise TimeoutError(
                    f"child exceeded timeout ({timeout_s}s): {' '.join(argv)}"
                )
            try:
                text = status_path.read_text(encoding="utf-8", errors="replace")
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                break
            for line in text.splitlines():
                if line.startswith("VmHWM:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        peak = max(peak, int(parts[1]))
                    break
            if proc.poll() is not None:
                try:
                    text = status_path.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        if line.startswith("VmHWM:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                peak = max(peak, int(parts[1]))
                            break
                except (
                    FileNotFoundError,
                    ProcessLookupError,
                    PermissionError,
                    ValueError,
                ):
                    pass
                break
            time.sleep(0.001)
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            _terminate_process(proc)
    finally:
        _terminate_process(proc)
    _assert_exit_status(proc.returncode, expected_statuses, argv)
    if peak <= 0:
        raise RuntimeError("failed to observe peak RSS via /proc VmHWM")
    return peak


def measure_peak_rss_kib(
    argv: Sequence[str],
    *,
    expected_statuses: Sequence[int] = (0,),
    timeout_s: float | None = DEFAULT_CHILD_TIMEOUT_S,
) -> int:
    """Return per-run peak resident set size in KiB for one command on Linux.

    Prefer GNU time(1) or a tiny C wrapper. Do not use Python's
    ``RUSAGE_CHILDREN`` after ``subprocess``: fork-before-exec inherits the
    interpreter's RSS high-water mark and massively inflates the sample.
    Wrapped command exit status must be in ``expected_statuses``.
    """

    _require_linux()
    if not argv:
        raise ValueError("argv must be non-empty")
    allowed = _normalize_expected_statuses(expected_statuses)
    errors: list[str] = []
    for helper in (
        _peak_rss_via_gnu_time,
        _peak_rss_via_tiny_wrapper,
        _peak_rss_via_proc_vmhwm,
    ):
        try:
            return helper(argv, timeout_s, allowed)
        except TimeoutError:
            raise
        except (RuntimeError, ValueError, OSError) as exc:
            errors.append(f"{helper.__name__}: {exc}")
    raise RuntimeError("peak RSS measurement failed: " + "; ".join(errors))


def _find_compiler() -> str:
    for name in ("cc", "gcc", "clang"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("no C compiler (cc/gcc/clang) found on PATH")


def build_sysdiff_in_temp(work_dir: Path | str) -> Path:
    """Compile src/sysdiff.c into work_dir; never writes into the workspace build/."""

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    if not SRC_PATH.is_file():
        raise FileNotFoundError(f"sysdiff source missing: {SRC_PATH}")
    binary = root / "sysdiff"
    compiler = _find_compiler()
    cmd = [compiler, *COMPILE_FLAGS, "-o", str(binary), str(SRC_PATH)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not binary.is_file():
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"failed to compile sysdiff: {detail}")
    return binary


def run_benchmark(
    *,
    binary: Path | str,
    before: Path | str,
    after: Path | str,
    thresholds: Mapping[str, float] | None = None,
    warmups: int = DEFAULT_WARMUPS,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    work_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Run warmups plus fixed samples for startup, fixture compare, and peak RSS."""

    if warmups < 0:
        raise ValueError("warmups must be >= 0")
    if sample_count < 1:
        raise ValueError("sample_count must be >= 1")

    bin_path = Path(binary)
    before_path = Path(before)
    after_path = Path(after)
    if not bin_path.is_file() or not os.access(bin_path, os.X_OK):
        raise FileNotFoundError(f"sysdiff binary is not executable: {bin_path}")
    if not before_path.is_file() or not after_path.is_file():
        raise FileNotFoundError("controlled fixture snapshots are missing")

    limits = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    startup_argv = [str(bin_path), "--help"]
    fixture_argv = [str(bin_path), "compare", str(before_path), str(after_path)]
    # compare exits 0 (identical) or 1 (differences); reject parse/usage failures.
    fixture_statuses = (0, 1)
    startup_statuses = (0,)
    baseline_argv = list(SPAWN_BASELINE_ARGV)

    # Warmups are intentionally untimed and excluded from samples.
    for _ in range(warmups):
        measure_runtime_ms(baseline_argv, expected_statuses=(0,))
        measure_runtime_ms(startup_argv, expected_statuses=startup_statuses)
        measure_runtime_ms(fixture_argv, expected_statuses=fixture_statuses)

    baseline_samples: list[float] = []
    startup_samples: list[float] = []
    fixture_samples: list[float] = []
    rss_samples: list[float] = []
    for _ in range(sample_count):
        baseline_samples.append(
            measure_runtime_ms(baseline_argv, expected_statuses=(0,))
        )
        startup_samples.append(
            measure_runtime_ms(startup_argv, expected_statuses=startup_statuses)
        )
        fixture_samples.append(
            measure_runtime_ms(fixture_argv, expected_statuses=fixture_statuses)
        )
        rss_samples.append(
            float(
                measure_peak_rss_kib(
                    fixture_argv, expected_statuses=fixture_statuses
                )
            )
        )

    measurements = {
        MEASUREMENT_BASELINE: aggregate_samples(baseline_samples),
        MEASUREMENT_STARTUP: aggregate_samples(startup_samples),
        MEASUREMENT_FIXTURE: aggregate_samples(fixture_samples),
        MEASUREMENT_PEAK_RSS: float(max(rss_samples)),
    }
    samples = {
        "baseline_ms": baseline_samples,
        "fixture_ms": fixture_samples,
        "peak_rss_kib": rss_samples,
        "startup_ms": startup_samples,
    }
    # work_dir is accepted for API compatibility but never persisted: absolute
    # mkdtemp paths churn the committed JSON and leak host layout (review B4).
    _ = work_dir
    metadata: dict[str, Any] = {
        "baseline_command": " ".join(baseline_argv),
        "fixture_command": "compare",
        "fixture_entry_count": CONTROLLED_FIXTURE_ENTRY_COUNT,
        "platform": sys.platform,
        "sample_count": sample_count,
        "schema_version": SCHEMA_VERSION,
        "startup_command": "--help",
        "warmups": warmups,
        "work_dir_kind": "tempdir",
    }
    return build_report(
        measurements=measurements,
        thresholds=limits,
        samples=samples,
        metadata=metadata,
    )


def _print_help(stream: TextIO) -> None:
    stream.write(
        "usage: benchmark_sysdiff.py [--help] [--output PATH]\n"
        "\n"
        "Linux-only deterministic performance benchmark for sysdiff.\n"
        "Builds sysdiff in a temporary directory (never in workspace build/),\n"
        "excludes compile/setup from timed samples, and emits stable JSON.\n"
        "\n"
        "Measurements:\n"
        f"  {MEASUREMENT_BASELINE}  median spawn-cost baseline via /bin/true (ms)\n"
        f"  {MEASUREMENT_STARTUP}   median startup time via --help (milliseconds)\n"
        f"  {MEASUREMENT_FIXTURE}   median controlled-fixture compare time (ms)\n"
        f"  {MEASUREMENT_PEAK_RSS}         per-run peak RSS during compare (KiB)\n"
        "                    (GNU /usr/bin/time -f %M; tiny C wrapper fallback)\n"
        f"  Controlled fixture size: {CONTROLLED_FIXTURE_ENTRY_COUNT} key=value entries\n"
        "  Read startup/fixture medians net of baseline_ms_median (spawn floor).\n"
        "\n"
        "Sampling:\n"
        f"  warmups={DEFAULT_WARMUPS}  sample_count={DEFAULT_SAMPLE_COUNT}  "
        "(odd count; median aggregation)\n"
        "\n"
        "Release thresholds (fail when any measurement exceeds its limit):\n"
        f"  {MEASUREMENT_STARTUP} <= {DEFAULT_THRESHOLDS[MEASUREMENT_STARTUP]:.1f}\n"
        f"  {MEASUREMENT_FIXTURE} <= {DEFAULT_THRESHOLDS[MEASUREMENT_FIXTURE]:.1f}\n"
        f"  {MEASUREMENT_PEAK_RSS} <= {DEFAULT_THRESHOLDS[MEASUREMENT_PEAK_RSS]:.1f}\n"
        "\n"
        "Options:\n"
        "  --help            show this help and exit 0\n"
        "  --output PATH     write JSON report to PATH (overwrites if present;\n"
        "                    creates missing parent directories as needed)\n"
        "\n"
        "Exit status is nonzero when a threshold fails or the harness errors.\n"
        "Unexpected child exit statuses fail the harness (not a green gate).\n"
        "Environment variables such as SYSDIFF_BIN are ignored.\n"
    )


def _validate_output_path(raw: str) -> Path:
    if raw is None or raw == "":
        raise ValueError("output path must be a non-empty file path")
    path = Path(raw)
    if path.exists() and path.is_dir():
        raise ValueError(f"output path is a directory: {raw}")
    parent = path.parent if str(path.parent) else Path(".")
    if parent.exists() and not parent.is_dir():
        raise ValueError(f"output parent is not a directory: {parent}")
    return path


def _parse_args(argv: Sequence[str]) -> tuple[str | None, Path | None]:
    """Parse CLI args without trusting unknown options or empty paths."""

    want_help = False
    output: Path | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--help", "-h"):
            want_help = True
            i += 1
            continue
        if arg == "--output":
            if i + 1 >= len(argv):
                raise ValueError("--output requires a PATH argument")
            output = _validate_output_path(argv[i + 1])
            i += 2
            continue
        if arg.startswith("--output="):
            output = _validate_output_path(arg.split("=", 1)[1])
            i += 1
            continue
        raise ValueError(f"unknown option: {arg}")
    if want_help:
        return "help", output
    return None, output


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = list(sys.argv[1:] if argv is None else argv)

    try:
        action, output_path = _parse_args(args)
    except ValueError as exc:
        err.write(f"error: {exc}\n")
        err.write("usage: benchmark_sysdiff.py [--help] [--output PATH]\n")
        return 2

    if action == "help":
        _print_help(out)
        return 0

    if not sys.platform.startswith("linux"):
        err.write("error: benchmark_sysdiff.py requires Linux\n")
        return 2

    # Never honor SYSDIFF_BIN / BENCHMARK_SYSDIFF_BIN or caller binary paths.
    work_root = Path(tempfile.mkdtemp(prefix="sysdiff-benchmark."))
    try:
        build_dir = work_root / "build"
        fixture_dir = work_root / "fixtures"
        binary = build_sysdiff_in_temp(build_dir)
        before, after = prepare_controlled_fixtures(fixture_dir)
        report = run_benchmark(
            binary=binary,
            before=before,
            after=after,
            thresholds=DEFAULT_THRESHOLDS,
            warmups=DEFAULT_WARMUPS,
            sample_count=DEFAULT_SAMPLE_COUNT,
            work_dir=work_root,
        )
    except Exception as exc:
        err.write(f"error: {exc}\n")
        return 2
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    payload = encode_report_json(report)
    if output_path is not None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            err.write(f"error: cannot write output: {exc}\n")
            return 2
    else:
        out.write(payload + "\n")

    return report_exit_status(report)


if __name__ == "__main__":
    sys.exit(main())
