import importlib.util
import os
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_tools.py"


def make_fake_executable(directory, name):
    executable = directory / name
    executable.write_text(
        "#!/bin/sh\n"
        'case "${1:-}" in\n'
        "  --version|-V|version) printf '%s fake version\\n' \"$0\" ;;\n"
        "  --help|-h|help) printf '%s fake help\\n' \"$0\" ;;\n"
        "  *) printf '%s fake command\\n' \"$0\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def run_check_tools(path):
    env = {
        "PATH": os.fspath(path),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }
    return subprocess.run(
        [sys.executable, os.fspath(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def load_check_tools_module():
    if not SCRIPT.exists():
        pytest.skip("scripts/check_tools.py is not implemented yet")
    spec = importlib.util.spec_from_file_location("check_tools_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default_harness_requirements(module):
    for name in ("DEFAULT_HARNESSES", "DEFAULT_REQUIREMENTS", "REQUIRED_HARNESSES"):
        if hasattr(module, name):
            return getattr(module, name)
    pytest.fail("check_tools module must expose an explicit default harness table")


def result_harness_name(result):
    for attr in ("name", "harness", "harness_name"):
        if hasattr(result, attr):
            return getattr(result, attr)
    requirement = getattr(result, "requirement", None)
    if requirement is not None:
        for attr in ("name", "harness", "harness_name"):
            if hasattr(requirement, attr):
                return getattr(requirement, attr)
    pytest.fail(f"probe result does not expose a harness name: {result!r}")


def test_successful_default_run_reports_required_harnesses(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_executable(bin_dir, "codex")
    make_fake_executable(bin_dir, "claude")

    result = run_check_tools(bin_dir)

    assert result.returncode == 0
    assert "codex_cli" in result.stdout
    assert "claude_code" in result.stdout
    assert "codex" in result.stdout
    assert "claude" in result.stdout
    assert result.stderr == ""


def test_missing_codex_cli_reports_only_stderr_failure(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_executable(bin_dir, "claude")

    result = run_check_tools(bin_dir)

    assert result.returncode != 0
    assert "codex_cli" in result.stderr
    assert "missing" in result.stderr.lower() or "unavailable" in result.stderr.lower()
    assert "all required" not in result.stdout.lower()


def test_missing_claude_code_reports_required_harness(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_executable(bin_dir, "codex")

    result = run_check_tools(bin_dir)

    assert result.returncode != 0
    assert "claude_code" in result.stderr
    assert "missing" in result.stderr.lower() or "unavailable" in result.stderr.lower()
    assert "all required" not in result.stdout.lower()


def test_missing_both_required_harnesses_are_reported_together(tmp_path):
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()

    result = run_check_tools(empty_path)

    assert result.returncode != 0
    assert "codex_cli" in result.stderr
    assert "claude_code" in result.stderr
    assert result.stderr.count("codex_cli") >= 1
    assert result.stderr.count("claude_code") >= 1


def test_failure_diagnostic_frames_routed_worker_infrastructure(tmp_path):
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()

    result = run_check_tools(empty_path)

    assert result.returncode != 0
    diagnostic = result.stderr.lower()
    assert "sysdiff" not in diagnostic
    assert "comparison" not in diagnostic
    assert (
        "routed worker" in diagnostic
        or "worker infrastructure" in diagnostic
        or "routing infrastructure" in diagnostic
    )


def test_cli_streams_keep_success_on_stdout_and_failures_on_stderr(tmp_path):
    success_bin = tmp_path / "success-bin"
    success_bin.mkdir()
    make_fake_executable(success_bin, "codex")
    make_fake_executable(success_bin, "claude")
    success = run_check_tools(success_bin)

    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    failure = run_check_tools(empty_bin)

    assert success.returncode == 0
    assert "codex_cli" in success.stdout
    assert "claude_code" in success.stdout
    assert success.stderr == ""

    assert failure.returncode != 0
    assert failure.stdout == ""
    assert "codex_cli" in failure.stderr
    assert "claude_code" in failure.stderr


def test_module_main_accepts_explicit_environment_without_real_path(tmp_path):
    module = load_check_tools_module()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_executable(bin_dir, "codex")
    make_fake_executable(bin_dir, "claude")

    assert module.main([], env={"PATH": os.fspath(bin_dir)}) == 0


def test_probe_layer_accumulates_structured_missing_harness_results(tmp_path):
    module = load_check_tools_module()
    empty_path = tmp_path / "empty-bin"
    empty_path.mkdir()

    assert hasattr(module, "probe_harnesses")
    results = module.probe_harnesses(
        default_harness_requirements(module),
        env={"PATH": os.fspath(empty_path)},
    )

    missing_names = {
        result_harness_name(result)
        for result in results
        if not getattr(result, "available")
    }
    assert missing_names == {"codex_cli", "claude_code"}


def test_availability_check_is_read_only_and_does_not_launch_workflows(
    monkeypatch, tmp_path
):
    module = load_check_tools_module()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_executable(bin_dir, "codex")
    make_fake_executable(bin_dir, "claude")

    forbidden_commands = []

    def guarded_subprocess_run(command, *args, **kwargs):
        argv = list(map(str, command if isinstance(command, list) else [command]))
        command_text = " ".join(argv)
        dangerous_terms = (
            "launch-workflow",
            "agent_orch.main",
            "apt",
            "apt-get",
            "dnf",
            "yum",
            "pacman",
            "pip",
            "curl",
            "wget",
            "ssh",
            "scp",
        )
        model_session_terms = (
            "exec",
            "run",
            "chat",
            "prompt",
            "session",
            "workflow",
            "playbook",
        )
        executable = Path(argv[0]).name if argv else ""
        if any(term in command_text for term in dangerous_terms) or (
            executable in {"codex", "claude"}
            and any(term in argv[1:] for term in model_session_terms)
        ):
            forbidden_commands.append(command_text)
            raise AssertionError(f"forbidden availability probe: {command_text}")
        return subprocess.CompletedProcess(command, 0, stdout="fake probe\n", stderr="")

    def forbidden_write_open(*args, **kwargs):
        mode = "r"
        if len(args) >= 2:
            mode = args[1]
        elif "mode" in kwargs:
            mode = kwargs["mode"]
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise AssertionError(f"unexpected file write through open(): {args[0]}")
        return original_open(*args, **kwargs)

    original_open = open
    if hasattr(module, "subprocess"):
        monkeypatch.setattr(module.subprocess, "run", guarded_subprocess_run)
    monkeypatch.setattr("builtins.open", forbidden_write_open)

    if hasattr(module, "os"):
        for name in ("chmod", "remove", "unlink", "mkdir", "makedirs"):
            if hasattr(module.os, name):
                monkeypatch.setattr(module.os, name, pytest.fail)
    if hasattr(module, "pathlib"):
        monkeypatch.setattr(module.pathlib.Path, "write_text", pytest.fail)
        monkeypatch.setattr(module.pathlib.Path, "write_bytes", pytest.fail)
    if hasattr(module, "socket"):
        monkeypatch.setattr(module.socket, "create_connection", pytest.fail)
        monkeypatch.setattr(module.socket, "socket", pytest.fail)

    status = module.main([], env={"PATH": os.fspath(bin_dir)})

    assert status == 0
    assert forbidden_commands == []


def test_asan_compile_command_includes_strict_warnings_and_sanitize():
    module = load_check_tools_module()
    command = module.build_asan_compile_command(
        "clang", "src/sysdiff.c", "/tmp/sysdiff-asan"
    )

    assert command[0] == "clang"
    assert command[-3:] == ["-o", "/tmp/sysdiff-asan", "src/sysdiff.c"]
    for flag in ("-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"):
        assert flag in command
    assert "-fsanitize=address" in command
    assert "-fno-omit-frame-pointer" in command


def test_ubsan_compile_command_includes_undefined_sanitize():
    module = load_check_tools_module()
    command = module.build_ubsan_compile_command(
        "clang", "src/sysdiff.c", "/tmp/sysdiff-ubsan"
    )

    assert "-fsanitize=undefined" in command
    for flag in ("-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"):
        assert flag in command


def test_valgrind_compile_and_run_command_construction():
    module = load_check_tools_module()
    compile_command = module.build_valgrind_compile_command(
        "gcc", "src/sysdiff.c", "/tmp/sysdiff-valgrind"
    )
    run_command = module.build_valgrind_run_command(
        "/tmp/sysdiff-valgrind", ["compare", "a", "b"], "/tmp/vg.log"
    )

    assert compile_command[0] == "gcc"
    for flag in (
        "-std=c17",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-g",
        "-fno-omit-frame-pointer",
    ):
        assert flag in compile_command
    assert "-fsanitize=address" not in compile_command

    assert run_command[0] == "valgrind"
    assert "--quiet" in run_command
    assert "--error-exitcode=99" in run_command
    assert "--leak-check=full" in run_command
    assert "--errors-for-leak-kinds=definite,possible" in run_command
    assert "--log-file=/tmp/vg.log" in run_command
    assert run_command[-4:] == ["/tmp/sysdiff-valgrind", "compare", "a", "b"]


def test_memory_gate_platform_preflight_rejects_non_linux():
    module = load_check_tools_module()
    result = module.require_linux_platform(platform="darwin")

    assert result.available is False
    assert "Linux" in result.detail


def test_memory_gate_sanitize_preflight_fails_when_clang_missing(tmp_path):
    module = load_check_tools_module()
    empty = tmp_path / "empty-bin"
    empty.mkdir()

    results = module.preflight_memory_gate(
        "sanitize",
        env={"PATH": os.fspath(empty)},
        platform="linux",
    )
    missing = {result.name for result in results if not result.available}

    assert "clang" in missing

    err = StringIO()
    status = module.main(
        ["--memory-gate", "sanitize"],
        env={"PATH": os.fspath(empty)},
        stdout=StringIO(),
        stderr=err,
    )
    assert status != 0
    assert "clang" in err.getvalue()


def test_memory_gate_valgrind_preflight_fails_when_valgrind_missing(tmp_path):
    module = load_check_tools_module()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_executable(bin_dir, "gcc")

    results = module.preflight_memory_gate(
        "valgrind",
        env={"PATH": os.fspath(bin_dir)},
        platform="linux",
    )
    missing_names = {result.name for result in results if not result.available}

    assert "valgrind" in missing_names

    err = StringIO()
    failure = module.main(
        ["--memory-gate", "valgrind"],
        env={"PATH": os.fspath(bin_dir)},
        stdout=StringIO(),
        stderr=err,
    )
    assert failure != 0
    assert "valgrind" in err.getvalue()


def test_memory_gate_cli_failure_stays_on_stderr(tmp_path):
    module = load_check_tools_module()
    empty = tmp_path / "empty-bin"
    empty.mkdir()

    out = StringIO()
    err = StringIO()
    status = module.main(
        ["--memory-gate", "sanitize"],
        env={"PATH": os.fspath(empty)},
        stdout=out,
        stderr=err,
    )

    assert status != 0
    assert out.getvalue() == ""
    assert "memory-gate sanitize" in err.getvalue()
    assert "clang" in err.getvalue()
    assert "silently skip" in err.getvalue()


def test_memory_gate_sanitize_preflight_passes_on_real_linux_toolchain():
    module = load_check_tools_module()
    if not sys.platform.startswith("linux"):
        pytest.skip("sanitize preflight requires Linux")
    if shutil.which("clang") is None:
        pytest.skip("clang is required for sanitize preflight success path")

    out = StringIO()
    status = module.main(
        ["--memory-gate", "sanitize"],
        stdout=out,
        stderr=StringIO(),
    )
    assert status == 0
    assert "memory-gate sanitize" in out.getvalue()


def test_memory_gate_valgrind_preflight_passes_on_real_linux_toolchain():
    module = load_check_tools_module()
    if not sys.platform.startswith("linux"):
        pytest.skip("valgrind preflight requires Linux")
    if shutil.which("gcc") is None or shutil.which("valgrind") is None:
        pytest.skip("gcc and valgrind are required for valgrind preflight success")

    out = StringIO()
    status = module.main(
        ["--memory-gate", "valgrind"],
        stdout=out,
        stderr=StringIO(),
    )
    assert status == 0
    assert "memory-gate valgrind" in out.getvalue()
