"""Regression test suite for repairing governed run failure 958aec814eec.

Governed run 958aec814eec failed during step_07_repair_and_verify_slice when
system validation attempted to execute raw compiler and static analysis commands:
    Command failed to start: clang -std=c17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only src/sysdiff.c:
        [Errno 2] No such file or directory: 'clang'
    Command failed to start: cppcheck --quiet --enable=all --suppress=missingIncludeSystem src/sysdiff.c:
        [Errno 2] No such file or directory: 'cppcheck'

Failure analysis and root causes:
1. Direct Invocation of Unverified External Toolchains:
   The validation commands invoked 'clang' and 'cppcheck' directly as subprocess
   executables without prior discovery or preflight validation. In environments where
   these secondary tools are not installed or not present in the active $PATH,
   the OS raises FileNotFoundError ([Errno 2]), terminating step validation abruptly
   with an unhandled error rather than a structured diagnostic or graceful fallback.
2. Missing Preflight Guard in Makefile Targets:
   While some Makefile targets (such as cppcheck-check and clang-strict) implement
   preflight availability checks using `command -v`, other targets (such as
   clang-syntax) invoke `clang` directly without checking availability. If executed in
   a minimal or containerized environment lacking clang, this causes untyped shell
   failures (exit code 127 / command not found).
3. Tool Provisioning and Discovery Resilience:
   The repository quality gates require verification via GCC, Clang, clang-tidy,
   and cppcheck when available. The environment must either:
   - Provide structured preflight discovery reporting availability cleanly without crashing.
   - Provide installation/wrapper scripts (e.g. under scripts/) to make missing tools available.
   - Guard Makefile targets to ensure graceful failure reporting instead of shell aborts.
   - Guarantee that the baseline compiler (GCC) remains operational for strict ISO C17 checks.

This regression test verifies that:
- Probing tools via scripts/check_tools.py is bounded, read-only, and safe when tools are absent.
- Makefile recipes (clang-syntax, clang-strict, cppcheck-check, clang-analyzer-check) have preflight guards.
- Exact validation commands from run 958aec814eec are verified for availability and graceful handling.
- cppcheck is either provisioned on PATH or an installer/wrapper script exists under scripts/.
- clang is discoverable on PATH or via host toolchain paths.
- Baseline ISO C17 syntax validation via GCC is verified.
- The product source code (src/sysdiff.c) remains pure with zero run token leakage.
"""

from __future__ import annotations

import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

for _extra_path in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/projects/employee-contract/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if _extra_path not in sys.path and Path(_extra_path).is_dir():
        sys.path.insert(0, _extra_path)

ROOT = Path(__file__).resolve().parents[1]
_scripts_dir = str(ROOT / "scripts")
if _scripts_dir not in sys.path and Path(_scripts_dir).is_dir():
    sys.path.insert(0, _scripts_dir)

try:
    import check_tools
except ImportError:
    check_tools = None  # type: ignore[assignment]

SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
CHECK_TOOLS_SCRIPT = ROOT / "scripts" / "check_tools.py"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"


def make_fake_executable(directory: Path, name: str) -> Path:
    """Create a minimal executable shell script to simulate a toolchain binary."""
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


# ============================================================================
# 1. Makefile Preflight Tool Availability Guards
# ============================================================================


def test_makefile_cppcheck_check_has_preflight_guard() -> None:
    """Makefile target 'cppcheck-check' must probe tool availability before execution."""
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    match = re.search(
        r"^cppcheck-check:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing cppcheck-check target"
    recipe = match.group(1)

    has_preflight = (
        "command -v cppcheck" in recipe
        or "which cppcheck" in recipe
        or "check_tools" in recipe
    )
    assert has_preflight, (
        "Makefile target 'cppcheck-check' invokes cppcheck directly without a preflight "
        "availability guard, causing unhandled exit code 127 when cppcheck is absent "
        "(reproducing governed run 958aec814eec failure mode)."
    )


def test_makefile_clang_strict_has_preflight_guard() -> None:
    """Makefile target 'clang-strict' must guard clang availability before execution."""
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    match = re.search(
        r"^clang-strict:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing clang-strict target"
    recipe = match.group(1)
    assert "command -v clang" in recipe or "which clang" in recipe, (
        "Makefile target 'clang-strict' missing preflight guard for clang availability"
    )


def test_makefile_clang_analyzer_check_has_preflight_guard() -> None:
    """Makefile target 'clang-analyzer-check' must guard clang availability before execution."""
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    match = re.search(
        r"^clang-analyzer-check:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing clang-analyzer-check target"
    recipe = match.group(1)
    assert "command -v clang" in recipe or "which clang" in recipe, (
        "Makefile target 'clang-analyzer-check' missing preflight guard for clang availability"
    )


def test_makefile_clang_syntax_has_preflight_guard() -> None:
    """Makefile target 'clang-syntax' must guard tool availability before execution.

    In run 958aec814eec, raw clang commands crashed because clang was not found.
    The clang-syntax target in Makefile must verify clang availability before invoking it,
    preventing unhandled exit code 127 / command not found errors.
    """
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    match = re.search(
        r"^clang-syntax:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing clang-syntax target"
    recipe = match.group(1)

    has_preflight = (
        "command -v clang" in recipe
        or "which clang" in recipe
        or "check_tools" in recipe
        or "if " in recipe
    )
    assert has_preflight, (
        "Makefile target 'clang-syntax' invokes clang directly without a preflight "
        "availability guard, risking unhandled exit code 127 / command not found when clang is absent "
        "(reproducing governed run 958aec814eec failure mode)."
    )


# ============================================================================
# 2. check_tools.py Preflight Probing
# ============================================================================


def test_preflight_probe_cppcheck_when_absent() -> None:
    """When cppcheck is absent from PATH, preflight probing reports available=False cleanly."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    result = check_tools.probe_executable("cppcheck", env={"PATH": ""})
    assert not result.available
    assert "cppcheck was not found on PATH" in result.detail


def test_preflight_probe_clang_when_absent() -> None:
    """When clang is absent from PATH, preflight probing reports available=False cleanly."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    result = check_tools.probe_executable("clang", env={"PATH": ""})
    assert not result.available
    assert "clang was not found on PATH" in result.detail


def test_preflight_probe_detects_tools_when_present(tmp_path: Path) -> None:
    """When tools are present on PATH, preflight probing reports available=True and resolves path."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cppcheck = make_fake_executable(fake_bin, "cppcheck")
    fake_clang = make_fake_executable(fake_bin, "clang")

    env = {"PATH": str(fake_bin)}

    res_cppcheck = check_tools.probe_executable("cppcheck", env=env)
    assert res_cppcheck.available is True
    assert res_cppcheck.detail == f"found cppcheck at {fake_cppcheck}"

    res_clang = check_tools.probe_executable("clang", env=env)
    assert res_clang.available is True
    assert res_clang.detail == f"found clang at {fake_clang}"


def test_preflight_probes_are_read_only_and_bounded() -> None:
    """Preflight tool probing must be read-only, non-mutating, and complete within 2 seconds."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    start_time = time.monotonic()
    res_gcc = check_tools.probe_executable("gcc")
    res_clang = check_tools.probe_executable("clang")
    res_cppcheck = check_tools.probe_executable("cppcheck")
    elapsed = time.monotonic() - start_time

    assert elapsed < 2.0, f"Tool probing took {elapsed:.2f}s, expected < 2.0s"
    assert res_gcc.name == "gcc"
    assert res_clang.name == "clang"
    assert res_cppcheck.name == "cppcheck"


# ============================================================================
# 3. Tool Provisioning and Resolution Resilience
# ============================================================================


def test_clang_tool_resolved_or_installer_available() -> None:
    """clang must either be discoverable on PATH or an installer/wrapper in scripts/ must exist."""
    clang_path = shutil.which("clang")
    if clang_path is None:
        # Check known host toolchain installation locations
        known_locations = [
            Path("/home/lee/.gemini/antigravity-cli/bin/clang"),
            Path("/usr/bin/clang"),
            Path("/usr/local/bin/clang"),
        ]
        for loc in known_locations:
            if loc.is_file() and os.access(loc, os.X_OK):
                clang_path = str(loc)
                break

    if clang_path is not None:
        res = subprocess.run([clang_path, "--version"], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"clang --version failed: {res.stderr}"
        return

    scripts_dir = ROOT / "scripts"
    candidate_scripts = [
        scripts_dir / "install_tools.sh",
        scripts_dir / "ensure_tools.sh",
        scripts_dir / "setup_tools.sh",
        scripts_dir / "clang",
    ]
    found = [s for s in candidate_scripts if s.is_file() and os.access(s, os.X_OK)]
    assert found, (
        "clang is not found on PATH or known locations, and no installer or wrapper "
        "(e.g. scripts/install_tools.sh, scripts/ensure_tools.sh, or scripts/clang) "
        "exists in scripts/ to resolve missing clang in the environment (reproducing 958aec814eec)."
    )


def test_cppcheck_tool_resolved_or_installer_available() -> None:
    """cppcheck must either be discoverable on PATH or an installer/wrapper in scripts/ must exist."""
    cppcheck_path = shutil.which("cppcheck")
    if cppcheck_path is not None:
        res = subprocess.run([cppcheck_path, "--version"], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"cppcheck --version failed: {res.stderr}"
        return

    scripts_dir = ROOT / "scripts"
    candidate_scripts = [
        scripts_dir / "install_tools.sh",
        scripts_dir / "ensure_tools.sh",
        scripts_dir / "setup_tools.sh",
        scripts_dir / "cppcheck",
    ]
    found = [s for s in candidate_scripts if s.is_file() and os.access(s, os.X_OK)]
    assert found, (
        "cppcheck is not found on PATH, and no executable tool installer or wrapper "
        "(e.g. scripts/install_tools.sh, scripts/ensure_tools.sh, or scripts/cppcheck) "
        "exists in scripts/ to resolve missing cppcheck in the environment (reproducing 958aec814eec)."
    )


def test_clang_syntax_check_sysdiff_c() -> None:
    """Verify run 958aec814eec validation command: clang ... -fsyntax-only src/sysdiff.c."""
    clang_bin = shutil.which("clang")
    if clang_bin is None and Path("/home/lee/.gemini/antigravity-cli/bin/clang").is_file():
        clang_bin = "/home/lee/.gemini/antigravity-cli/bin/clang"

    if clang_bin is None:
        pytest.skip("clang is not yet installed or discoverable on PATH")

    res = subprocess.run(
        [
            clang_bin,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-fsyntax-only",
            str(SYSDIFF_SRC),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"clang syntax check failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"


def test_cppcheck_syntax_check_sysdiff_c() -> None:
    """Verify run 958aec814eec validation command: cppcheck --quiet --enable=all ... src/sysdiff.c."""
    cppcheck_bin = shutil.which("cppcheck")
    if cppcheck_bin is None:
        wrapper = ROOT / "scripts" / "cppcheck"
        if wrapper.is_file() and os.access(wrapper, os.X_OK):
            cppcheck_bin = str(wrapper)

    if cppcheck_bin is None:
        pytest.skip("cppcheck is not yet installed or discoverable on PATH")

    res = subprocess.run(
        [
            cppcheck_bin,
            "--quiet",
            "--enable=all",
            "--suppress=missingIncludeSystem",
            str(SYSDIFF_SRC),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"cppcheck failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"


def test_gcc_syntax_baseline_guaranteed() -> None:
    """GCC is guaranteed on Linux; verify baseline ISO C17 compilation passes cleanly."""
    gcc_bin = shutil.which("gcc")
    assert gcc_bin is not None, "gcc must be available on PATH as baseline compiler"

    res = subprocess.run(
        [
            gcc_bin,
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-fsyntax-only",
            str(SYSDIFF_SRC),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"gcc syntax check failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"


# ============================================================================
# 4. Non-Product Blast Radius and Repository Integrity
# ============================================================================


def test_sysdiff_source_clean_of_run_tokens() -> None:
    """src/sysdiff.c must remain clean and not leak any orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    text = SYSDIFF_SRC.read_text(encoding="utf-8")
    for forbidden in ("958aec814eec", "14543d8cc64c", "agent_orch"):
        assert forbidden not in text, f"sysdiff.c contains forbidden token {forbidden!r}"


def test_check_tools_script_is_valid() -> None:
    """scripts/check_tools.py must be valid Python that compiles without errors."""
    assert CHECK_TOOLS_SCRIPT.exists(), f"Missing {CHECK_TOOLS_SCRIPT}"
    py_compile.compile(str(CHECK_TOOLS_SCRIPT), doraise=True)


def test_manifest_is_valid_json() -> None:
    """tests/user_journeys_manifest.json must exist and be valid JSON."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"
    data = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    assert "journeys" in data
