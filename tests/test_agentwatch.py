"""Test-first contract for the Linux-only ``agentwatch`` first slice.

The production source intentionally need not exist when this module is authored.
Once it does, the fixtures build normal and ``AGENTWATCH_TEST_SEAM`` binaries in
pytest-owned directories below /tmp.  The seam changes platform inputs only.

The seam contract used here is deliberately text based and auditable.  Setting
``AGENTWATCH_TEST_SCRIPT`` names a file containing one directive per line;
``AGENTWATCH_TEST_TRACE`` names the file to which the seam appends calls as
``NAME key=value ...``.  Directives are consumed in order for the named boundary:
``FAIL NAME ERRNO``, ``CLOCK MS``, ``PROC PID RESULT PPID START [SIZE]``,
``SCAN COUNT``, ``WAIT PID STATUS``, and ``INTERRUPT SIGNAL``.  The production
parser, state machine, limits, precedence, and target selection remain in use.
Every injected failure test checks its trace positive control.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "agentwatch.c"
STRICT_FLAGS = ("-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror")
PLATFORM_FLAGS = ("-D_GNU_SOURCE",)
SEAM_FLAG = "-DAGENTWATCH_TEST_SEAM"
RUN_TIMEOUT = 12.0

HELP = (
    b"usage: agentwatch [--timeout SECONDS] [--grace SECONDS] -- COMMAND [ARG...]\n"
)
VERSION = b"agentwatch 0.1.0\n"
TAXONOMY = {
    "INVALID_ARGUMENTS", "SUBREAPER_SETUP_FAILURE", "SIGNAL_SETUP_FAILURE",
    "COMMAND_START_FAILURE", "TIMEOUT", "INTERRUPTED", "PROCFS_DISAPPEARED",
    "PROCFS_UNTRUSTED", "TRACKING_LIMIT", "PID_IDENTITY_CHANGED",
    "SIGNAL_DELIVERY_FAILURE", "REAP_FAILURE", "CLEANUP_INCOMPLETE",
    "INTERNAL_FAILURE",
}


def _outside_tmp(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp")).resolve()
    assert ROOT.resolve() not in path.parents
    return path


def _compile(output: Path, *, seam: bool) -> None:
    if not SRC.is_file():
        pytest.fail(f"required source is absent: {SRC}")
    cc = shutil.which(os.environ.get("CC", "cc"))
    if cc is None:
        pytest.fail("C compiler not found")
    argv = [cc, *STRICT_FLAGS, *PLATFORM_FLAGS]
    if seam:
        argv.append(SEAM_FLAG)
    argv.extend([str(SRC), "-o", str(output)])
    result = subprocess.run(argv, capture_output=True, check=False, timeout=60)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


@pytest.fixture(scope="session")
def agentwatch_bin() -> Path:
    directory = _outside_tmp("agentwatch-build.")
    binary = directory / "agentwatch"
    try:
        _compile(binary, seam=False)
        yield binary
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture(scope="session")
def agentwatch_seam_bin() -> Path:
    directory = _outside_tmp("agentwatch-seam-build.")
    binary = directory / "agentwatch-seam"
    try:
        _compile(binary, seam=True)
        yield binary
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def sealed_env(**updates: str) -> dict[str, str]:
    env = {"PATH": "/nonexistent", "LC_ALL": "C", "LANG": "C"}
    env.update(updates)
    return env


def run(binary: Path, *args: str, timeout: float = RUN_TIMEOUT,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(binary), *args], capture_output=True, check=False, timeout=timeout,
        env=env or sealed_env(),
    )


def assert_silent(result: subprocess.CompletedProcess[bytes], status: int) -> None:
    assert result.returncode == status
    assert result.stdout == b""
    assert result.stderr == b""


@pytest.mark.parametrize(
    "argv",
    [(), ("--",), ("true",), ("--timeout", "1", "/bin/true"),
     ("--timeout", "1", "--timeout", "2", "--", "/bin/true"),
     ("--grace", "1", "--grace", "2", "--", "/bin/true"),
     ("--unknown", "--", "/bin/true"), ("--help", "x"),
     ("--version", "x")],
)
def test_invalid_grammar_is_status_2(agentwatch_bin: Path, argv: tuple[str, ...]) -> None:
    result = run(agentwatch_bin, *argv)
    assert result.returncode == 2
    assert b"INVALID_ARGUMENTS" in result.stderr
    assert result.stdout == b""


@pytest.mark.parametrize(
    "value",
    ["", "0", "0.000", ".001", "86400.001", "-1", "+1", " 1", "1 ",
     "1e0", "1s", "nan", "NaN", "inf", "0.0009", "1.0001"],
)
@pytest.mark.parametrize("option", ["--timeout", "--grace"])
def test_strict_seconds_reject_invalid_classes(
    agentwatch_bin: Path, option: str, value: str
) -> None:
    result = run(agentwatch_bin, option, value, "--", "/bin/true")
    assert result.returncode == 2
    assert b"INVALID_ARGUMENTS" in result.stderr


@pytest.mark.parametrize("value", ["0.001", "0.010", "1", "1.5", "86400", "86400.000"])
def test_seconds_accept_boundaries(agentwatch_bin: Path, value: str) -> None:
    assert_silent(run(agentwatch_bin, "--grace", value, "--", "/bin/true"), 0)


def test_help_version_and_no_shell_insertion(agentwatch_bin: Path, tmp_path: Path) -> None:
    help_result = run(agentwatch_bin, "--help")
    version_result = run(agentwatch_bin, "--version")
    assert (help_result.returncode, help_result.stdout, help_result.stderr) == (0, HELP, b"")
    assert (version_result.returncode, version_result.stdout, version_result.stderr) == (0, VERSION, b"")
    marker = tmp_path / "shell-ran"
    result = run(agentwatch_bin, "--", f"touch {marker}")
    assert result.returncode == 127
    assert not marker.exists()


@pytest.mark.parametrize("status", [0, 2, 123, 124, 125, 127])
def test_preserves_real_command_exit_status(agentwatch_bin: Path, status: int) -> None:
    result = run(agentwatch_bin, "--", sys.executable, "-c", f"raise SystemExit({status})")
    assert_silent(result, status)


def test_exec_failure_is_distinct_from_child_exit_127(agentwatch_bin: Path) -> None:
    missing = run(agentwatch_bin, "--", "/definitely/missing/agentwatch-command")
    exited = run(agentwatch_bin, "--", sys.executable, "-c", "raise SystemExit(127)")
    assert missing.returncode == 127 and b"COMMAND_START_FAILURE" in missing.stderr
    assert_silent(exited, 127)


@pytest.mark.parametrize("signum", [signal.SIGABRT, signal.SIGUSR1, signal.SIGUSR2])
def test_direct_signal_status(agentwatch_bin: Path, signum: signal.Signals) -> None:
    code = f"import os,signal; os.kill(os.getpid(), {int(signum)})"
    assert_silent(run(agentwatch_bin, "--", sys.executable, "-c", code), 128 + int(signum))


def test_waits_for_descendant_after_original_exits(agentwatch_bin: Path, tmp_path: Path) -> None:
    marker = tmp_path / "descendant-done"
    code = (
        "import os,time; p=os.fork(); "
        f"(time.sleep(.15),open({str(marker)!r},'w').close(),os._exit(0)) if p==0 else os._exit(0)"
    )
    result = run(agentwatch_bin, "--", sys.executable, "-c", code)
    assert_silent(result, 0)
    assert marker.exists()


def test_waits_for_double_fork_descendant_outside_group(
    agentwatch_bin: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "detached-done"
    code = (
        "import os,time; p=os.fork(); "
        "\nif p: os._exit(0)\n"
        "os.setsid(); q=os.fork();\n"
        "if q: os._exit(0)\n"
        f"time.sleep(.15); open({str(marker)!r},'w').close(); os._exit(0)"
    )
    assert_silent(run(agentwatch_bin, "--", sys.executable, "-c", code), 0)
    assert marker.exists()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP])
def test_interrupt_is_forwarded_and_has_precedence(
    agentwatch_bin: Path, tmp_path: Path, signum: signal.Signals
) -> None:
    ready = tmp_path / f"ready-{int(signum)}"
    child = f"import pathlib,time; pathlib.Path({str(ready)!r}).touch(); time.sleep(60)"
    proc = subprocess.Popen(
        [str(agentwatch_bin), "--grace", "0.050", "--", sys.executable, "-c", child],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=sealed_env(),
    )
    try:
        deadline = time.monotonic() + 3
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert ready.exists(), "child never reported readiness"
        proc.send_signal(signum)
        stdout, stderr = proc.communicate(timeout=RUN_TIMEOUT)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
    assert proc.returncode == 128 + int(signum)
    assert stdout == b""
    assert b"INTERRUPTED" in stderr


def test_timeout_is_bounded_and_returns_124(agentwatch_bin: Path) -> None:
    start = time.monotonic()
    result = run(
        agentwatch_bin, "--timeout", "0.050", "--grace", "0.050", "--",
        sys.executable, "-c", "import time; time.sleep(60)", timeout=4,
    )
    elapsed = time.monotonic() - start
    assert result.returncode == 124
    assert b"TIMEOUT" in result.stderr
    assert elapsed < 3.0


def test_term_precedes_kill_and_owned_group_is_the_only_group_target(
    agentwatch_seam_bin: Path, tmp_path: Path
) -> None:
    _, trace = run_seam(
        agentwatch_seam_bin, tmp_path,
        ["CLOCK 0", "CLOCK 1", "WAIT 0 RUNNING", "CLOCK 2",
         "WAIT 0 RUNNING", "CLOCK 2002"],
        "--timeout", "0.001", "--grace", "0.001", "--", "/bin/true")
    group_sends = [line for line in trace.splitlines() if line.startswith("KILL_GROUP ")]
    assert any("signal=15" in line for line in group_sends)
    assert any("signal=9" in line for line in group_sends)
    assert next(i for i, line in enumerate(group_sends) if "signal=15" in line) < next(
        i for i, line in enumerate(group_sends) if "signal=9" in line
    )
    pgids = {re.search(r"pgid=(-\d+)", line).group(1) for line in group_sends}
    assert len(pgids) == 1 and "-1" not in pgids


def write_script(tmp_path: Path, directives: list[str]) -> tuple[Path, Path]:
    script = tmp_path / "scenario.txt"
    trace = tmp_path / "trace.txt"
    script.write_text("\n".join(directives) + "\n", encoding="ascii")
    return script, trace


def run_seam(binary: Path, tmp_path: Path, directives: list[str], *args: str):
    script, trace = write_script(tmp_path, directives)
    result = run(binary, *args, env=sealed_env(
        AGENTWATCH_TEST_SCRIPT=str(script), AGENTWATCH_TEST_TRACE=str(trace)))
    text = trace.read_text(encoding="ascii") if trace.exists() else ""
    return result, text


@pytest.mark.parametrize(
    "directive,call,diagnostic,status",
    [
        ("FAIL SIGACTION 12", "SIGACTION", "SIGNAL_SETUP_FAILURE", 125),
        ("FAIL PRCTL 1", "PRCTL", "SUBREAPER_SETUP_FAILURE", 125),
        ("FAIL PIPE 24", "PIPE", "COMMAND_START_FAILURE", 127),
        ("FAIL FORK 11", "FORK", "COMMAND_START_FAILURE", 127),
        ("FAIL SETPGID 1", "SETPGID", "COMMAND_START_FAILURE", 127),
        ("FAIL CLOCK 5", "CLOCK", "INTERNAL_FAILURE", 125),
        ("FAIL PPOLL 5", "PPOLL", "INTERNAL_FAILURE", 125),
        ("FAIL KILL 1", "KILL", "SIGNAL_DELIVERY_FAILURE", 125),
        ("FAIL WAITPID 10", "WAITPID", "REAP_FAILURE", 125),
        ("FAIL ALLOC 12", "ALLOC", "INTERNAL_FAILURE", 125),
        ("FAIL STDERR 5", "STDERR", "INTERNAL_FAILURE", 125),
    ],
)
def test_fault_matrix_has_positive_control(
    agentwatch_seam_bin: Path, tmp_path: Path, directive: str, call: str,
    diagnostic: str, status: int,
) -> None:
    result, trace = run_seam(
        agentwatch_seam_bin, tmp_path, [directive], "--timeout", "0.001", "--",
        "/bin/true",
    )
    assert call in trace
    assert result.returncode == status
    if call != "STDERR":
        assert diagnostic.encode() in result.stderr


@pytest.mark.parametrize(
    "result", ["ENOENT", "MIDREAD_ENOENT", "EACCES", "MALFORMED", "OVERSIZE", "INCONSISTENT"]
)
def test_hostile_procfs_is_never_individually_signaled(
    agentwatch_seam_bin: Path, tmp_path: Path, result: str
) -> None:
    directives = ["CLOCK 0", "SCAN 1", f"PROC 4242 {result} 4000 99 4097", "CLOCK 50"]
    completed, trace = run_seam(
        agentwatch_seam_bin, tmp_path, directives, "--timeout", "0.001",
        "--grace", "0.001", "--", "/bin/true",
    )
    assert "PROC pid=4242" in trace
    assert not re.search(r"KILL pid=4242(?:\s|$)", trace)
    assert completed.returncode in (0, 124, 125)


@pytest.mark.parametrize("size,trusted", [(4096, True), (4097, False)])
def test_proc_stat_record_size_boundary(
    agentwatch_seam_bin: Path, tmp_path: Path, size: int, trusted: bool
) -> None:
    result, trace = run_seam(
        agentwatch_seam_bin, tmp_path,
        ["SCAN 1", f"PROC 4242 OK 4000 99 {size}", "CLOCK 0", "CLOCK 50"],
        "--timeout", "0.001", "--grace", "0.001", "--", "/bin/true",
    )
    assert "PROC pid=4242" in trace
    assert (b"PROCFS_UNTRUSTED" not in result.stderr) is trusted


@pytest.mark.parametrize("comm", ["simple", "has spaces", "right)paren) inside"])
def test_proc_stat_parser_uses_final_right_parenthesis(
    agentwatch_seam_bin: Path, tmp_path: Path, comm: str
) -> None:
    # RAWSTAT passes these exact bytes through the production stat parser.
    record = f"4242 ({comm}) S 4000 " + "0 " * 17 + "99"
    result, trace = run_seam(
        agentwatch_seam_bin, tmp_path, [f"RAWSTAT 4242 {record}"],
        "--", "/bin/true")
    assert "RAWSTAT pid=4242" in trace
    assert b"PROCFS_UNTRUSTED" not in result.stderr


@pytest.mark.parametrize("count,limited", [(65536, False), (65537, True)])
def test_proc_directory_entry_limit(
    agentwatch_seam_bin: Path, tmp_path: Path, count: int, limited: bool
) -> None:
    result, trace = run_seam(agentwatch_seam_bin, tmp_path, [f"SCAN {count}"],
                             "--", "/bin/true")
    scans = [line for line in trace.splitlines() if line.startswith("SCAN_ENTRY ")]
    assert len(scans) <= 65536
    assert (b"TRACKING_LIMIT" in result.stderr) is limited


@pytest.mark.parametrize("count,limited", [(4096, False), (4097, True)])
def test_identity_retention_limit(
    agentwatch_seam_bin: Path, tmp_path: Path, count: int, limited: bool
) -> None:
    result, trace = run_seam(agentwatch_seam_bin, tmp_path,
                             [f"SCAN_IDENTITIES {count}"], "--", "/bin/true")
    retained = [x for x in trace.splitlines() if x.startswith("RETAIN ")]
    assert len(retained) <= 4096
    assert (b"TRACKING_LIMIT" in result.stderr) is limited


def test_scan_throttle_is_49_closed_50_open(
    agentwatch_seam_bin: Path, tmp_path: Path
) -> None:
    _, trace = run_seam(agentwatch_seam_bin, tmp_path,
                        ["CLOCK 0", "CLOCK 49", "CLOCK 50", "SCAN 0"],
                        "--timeout", "0.100", "--", "/bin/true")
    starts = [line for line in trace.splitlines() if line.startswith("SCAN_START")]
    assert len(starts) == 2
    assert "ms=0" in starts[0] and "ms=50" in starts[1]


@pytest.mark.parametrize(
    "revalidation,may_signal",
    [("OK 4000 99", True), ("OK 4000 100", False), ("ENOENT 0 0", False),
     ("MALFORMED 0 0", False), ("EACCES 0 0", False)],
)
def test_pid_identity_revalidated_immediately_before_signal(
    agentwatch_seam_bin: Path, tmp_path: Path, revalidation: str, may_signal: bool
) -> None:
    directives = ["SCAN 1", "PROC 4242 OK 4000 99", f"PROC 4242 {revalidation}",
                  "CLOCK 0", "CLOCK 1", "CLOCK 2"]
    _, trace = run_seam(agentwatch_seam_bin, tmp_path, directives,
                        "--timeout", "0.001", "--grace", "0.001", "--",
                        "/bin/true")
    individual = bool(re.search(r"KILL pid=4242(?:\s|$)", trace))
    assert individual is may_signal
    if may_signal:
        assert trace.index("PROC_REVALIDATE pid=4242") < trace.index("KILL pid=4242")


def test_incomplete_ancestry_and_duplicate_targets_are_suppressed(
    agentwatch_seam_bin: Path, tmp_path: Path
) -> None:
    _, trace = run_seam(
        agentwatch_seam_bin, tmp_path,
        ["SCAN 3", "PROC 4100 OK 9999 1", "PROC 4200 OK 4100 2",
         "PROC 4200 OK 4100 2", "CLOCK 0", "CLOCK 1", "CLOCK 2"],
        "--timeout", "0.001", "--grace", "0.001", "--", "/bin/true")
    assert "KILL pid=4100" not in trace
    assert "KILL pid=4200" not in trace
    assert len(re.findall(r"KILL_GROUP pgid=-\d+ signal=", trace)) <= 2
    assert "pgid=-1" not in trace


def test_cleanup_ceiling_and_precedence_matrix(agentwatch_seam_bin: Path, tmp_path: Path) -> None:
    result, trace = run_seam(
        agentwatch_seam_bin, tmp_path,
        ["CLOCK 0", "CLOCK 1", "FAIL PPOLL 5", "INTERRUPT 15",
         "WAIT 0 RUNNING", "CLOCK 2002"],
        "--timeout", "0.001", "--grace", "0.001", "--", "/bin/true")
    assert "PPOLL" in trace and "WAITPID" in trace
    assert result.returncode == 128 + signal.SIGTERM
    assert b"INTERRUPTED" in result.stderr


def test_untrusted_diagnostic_bytes_are_escaped(agentwatch_bin: Path) -> None:
    hostile = "bad\n\t\x1b\\\"\udcff"
    result = run(agentwatch_bin, "--", hostile)
    assert result.returncode == 127
    assert b"\\x0A" in result.stderr and b"\\x09" in result.stderr
    assert b"\\x1B" in result.stderr and b"\\\\" in result.stderr
    assert b"\x1b" not in result.stderr and b"\n\t" not in result.stderr


def test_source_audit_keeps_first_slice_narrow() -> None:
    if not SRC.is_file():
        pytest.fail(f"required source is absent: {SRC}")
    text = SRC.read_text(encoding="utf-8")
    assert "PR_SET_CHILD_SUBREAPER" in text
    assert "CLOCK_MONOTONIC" in text
    assert "execvp" in text and not re.search(r"\bsystem\s*\(", text)
    assert not re.search(r"\bkill\s*\(\s*-1\s*,", text)
    for forbidden in ("socket(", "daemon(", "setuid(", "setgid(", "unshare(",
                      "clone(", "sqlite", "curl", "telemetry"):
        assert forbidden not in text.lower()


def test_closed_taxonomy_is_fully_represented() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    assert TAXONOMY <= set(re.findall(r'"([A-Z][A-Z0-9_]+)"', source))
