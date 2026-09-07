"""Regression test suite for repairing governed run failure ba39f236f2b4.

Governed run ba39f236f2b4 failed during validation because essential toolchain utilities—
specifically clang, cppcheck, and clang-tidy—were missing from the execution environment.

Repair Contract Reference: docs/repair-ba39f236f2b4-contract.md
- AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement.
  Contract document adheres to required headings with >= 120 non-whitespace characters each.
  Closed hazard taxonomy (TOOL_AVAILABILITY, EXECUTION_TIMEOUT, ORACLE_TAMPERING, BLAST_RADIUS).
  Sealed evidence directory /home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4.
- AC-2: Tool Availability and Validation Environment Repair (clang, cppcheck, clang-tidy).
  Validation environment and implementation ensure clang, cppcheck, and clang-tidy are reliably
  available for automated validation commands.
- AC-3: User Journey Manifest Synchronization, Traceability, and Non-Product Blast Radius.
  Both tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json exist as
  identical parsed objects adhering to canonical schema and containing all 21 journeys.
  Every required journey maps to AC-1, AC-2, or AC-3 with zero orphaned acceptance checks.
  Command allowlist remains strictly ["build/sysdiff"].
  Zero regressions or modifications to src/sysdiff.c, Makefile binary packaging, or man/sysdiff.1.
"""

from __future__ import annotations

import json
import os
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
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
        USER_JOURNEYS_RESULT_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {}  # type: ignore[assignment]
    USER_JOURNEYS_RESULT_SCHEMA = {}  # type: ignore[assignment]

try:
    import check_tools
except ImportError:
    check_tools = None  # type: ignore[assignment]

CONTRACT = ROOT / "docs" / "repair-ba39f236f2b4-contract.md"
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MAN_PAGE = ROOT / "man" / "sysdiff.1"


def make_fake_executable(directory: Path, name: str) -> Path:
    """Create a minimal executable shell script to simulate a toolchain binary."""
    executable = directory / name
    executable.write_text(
        "#!/bin/sh\n"
        'case "${1:-}" in\n'
        '  --version|-V|-v|version) printf "%s version 1.0.0\\n" "$0" ;;\n'
        '  --help|-h|help) printf "Usage: %s [options]\\n" "$0" ;;\n'
        '  *) printf "%s executed\\n" "$0" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def resolve_tool_executable(tool_name: str) -> str | None:
    """Resolve executable path for a toolchain binary via PATH, host locations, or scripts/ wrapper."""
    resolved = shutil.which(tool_name)
    if resolved is not None:
        return resolved

    known_paths = [
        Path(f"/home/lee/.gemini/antigravity-cli/bin/{tool_name}"),
        Path(f"/usr/bin/{tool_name}"),
        Path(f"/usr/local/bin/{tool_name}"),
    ]
    for p in known_paths:
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    wrapper = ROOT / "scripts" / tool_name
    if wrapper.is_file() and os.access(wrapper, os.X_OK):
        return str(wrapper)

    return None

PRESERVED_AUTHOR_JOURNEYS = {
    "A user reads the repository-owned journey contract and confirms the manifest is a usable named oracle",
    "A user supplies malformed journey data and receives a specific fail-closed validation result",
    "A user runs the governed check from an unrelated current directory without changing path meaning",
    "A user observes that only the exact allowlisted smoke argv prefix is re-executed directly",
    "A user confirms that required journey authority is retained when the workspace is repaired",
    "A user follows every acceptance-check trace and sees exploratory coverage remain supplementary",
    "A user retries after producer-side narrowing and sees the pinned journey oracle reject tampering",
    "A user reviews a result that reports every journey with concrete steps commands and actionable evidence",
    "A user runs the existing deterministic smoke chain without confusing it with direct journey evidence",
    "A user confirms the workspace abstraction remains additive and does not create product release or network behavior",
}

SYSDIFF_JOURNEYS = {
    "A user runs the real sysdiff binary with no arguments and receives usage guidance instead of a crash",
    "A user asks the real sysdiff binary for help and receives its usage summary",
    "A user compares two snapshots with the real sysdiff binary and sees deterministic added removed and changed entries",
    "A user gives the real sysdiff binary a malformed snapshot and receives an escaped diagnostic without partial output",
}

BWRAP_JOURNEYS = {
    "A worker launcher delivers large prompt payloads via stdin and verifies that no single argv argument exceeds kernel MAX_ARG_STRLEN limits",
    "A user confirms bubblewrap sandbox containment remains strictly enforced on Linux without granting unsandboxed execution bypasses",
    "An operator observes pre-exec payload measurement rejecting oversized bwrap arguments fail-closed with typed LAUNCH_PAYLOAD_TOO_LARGE classification",
    "An evaluator inspects edge-case payload sizes near the 128 KiB boundary to confirm exact byte accounting without information leakage",
    "A validator bounds process output in retry feedback to head and tail excerpts while preserving full unmodified logs in hash-chained artifacts",
    "A maintainer verifies the synchronized user journeys manifest adheres to canonical schema and covers all enumerated contract acceptance checks",
    "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
}


# ============================================================================
# AC-1: Contract Establishment, Document Integrity, and Write Scope Confinement
# ============================================================================


def test_repair_contract_structure_and_headings() -> None:
    """AC-1: docs/repair-ba39f236f2b4-contract.md has required headings with >= 120 chars each."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    required_headings = ["Overview", "Problem", "Constraints", "Acceptance Checks"]
    for heading in required_headings:
        pattern = rf"^#+\s+{re.escape(heading)}\b"
        match = re.search(pattern, content, re.MULTILINE)
        assert match is not None, f"Contract missing required heading: {heading}"

        start_pos = match.end()
        next_heading_match = re.search(r"^#+\s+", content[start_pos:], re.MULTILINE)
        if next_heading_match:
            section_text = content[start_pos : start_pos + next_heading_match.start()]
        else:
            section_text = content[start_pos:]

        non_whitespace_count = len(re.sub(r"\s", "", section_text))
        assert non_whitespace_count >= 120, (
            f"Section {heading!r} in {CONTRACT} has only {non_whitespace_count} non-whitespace characters, "
            f"minimum required is 120"
        )

    assert "ba39f236f2b4" in content
    assert "clang" in content
    assert "cppcheck" in content
    assert "clang-tidy" in content
    assert "/home/lee/projects/linux-utilities-agent-orch-runs/ba39f236f2b4" in content
    assert "TOOL_AVAILABILITY" in content
    assert "AC-1" in content
    assert "AC-2" in content
    assert "AC-3" in content


def test_hazard_taxonomy_compliance() -> None:
    """AC-1: Identified hazards must belong strictly to the closed repository taxonomy."""
    assert CONTRACT.exists(), f"Missing repair contract: {CONTRACT}"
    content = CONTRACT.read_text(encoding="utf-8")

    assert "Closed Hazard Taxonomy" in content
    taxonomy_match = re.search(
        r"Closed Hazard Taxonomy.*?(TOOL_AVAILABILITY|EXECUTION_TIMEOUT|ORACLE_TAMPERING|BLAST_RADIUS)",
        content,
        re.DOTALL,
    )
    assert taxonomy_match is not None, "Contract does not reference closed hazard taxonomy"
    assert "TOOL_AVAILABILITY" in content


# ============================================================================
# AC-2: Tool Availability and Validation Environment Repair
# ============================================================================


def test_tool_availability_specification_in_contract() -> None:
    """AC-2: Contract explicitly defines requirements for clang, cppcheck, and clang-tidy."""
    assert CONTRACT.exists()
    content = CONTRACT.read_text(encoding="utf-8")

    # The problem description and acceptance check must explicitly address all 3 tools
    assert "clang" in content
    assert "cppcheck" in content
    assert "clang-tidy" in content

    # Acceptance check AC-2 must be enumerated and cover validation environment repair
    assert re.search(r"-\s+\*\*AC-2\*\*", content) is not None


def test_tool_availability() -> None:
    """AC-2: Targeted check that clang, cppcheck, and clang-tidy can each be invoked.

    In governed run ba39f236f2b4, validation commands failed because clang, cppcheck,
    and clang-tidy were missing or unlocatable. This test verifies that each of the three
    required tools can be resolved and successfully invoked with a 0 exit status.
    """
    required_tools = ["clang", "cppcheck", "clang-tidy"]
    missing_tools: list[str] = []
    invocation_errors: dict[str, str] = {}

    for tool in required_tools:
        executable = resolve_tool_executable(tool)
        if executable is None:
            missing_tools.append(tool)
            continue

        res = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
        if res.returncode != 0:
            invocation_errors[tool] = f"exit {res.returncode}: {res.stderr.strip()}"

    assert not missing_tools, (
        f"Toolchain availability check failed: missing required tools {missing_tools}. "
        f"Validation environment must provide executable implementations or wrappers for all three: {required_tools}."
    )
    assert not invocation_errors, (
        f"Toolchain invocation failed for tools: {invocation_errors}"
    )


def test_clang_tool_availability_and_invocation() -> None:
    """AC-2: clang must be discoverable and invokable with --version, --help, and syntax check."""
    clang = resolve_tool_executable("clang")
    assert clang is not None, "clang is not discoverable on PATH or scripts/clang"

    res_version = subprocess.run([clang, "--version"], capture_output=True, text=True, check=False)
    assert res_version.returncode == 0, f"clang --version failed:\n{res_version.stderr}"

    res_help = subprocess.run([clang, "--help"], capture_output=True, text=True, check=False)
    assert res_help.returncode == 0, f"clang --help failed:\n{res_help.stderr}"

    res_syntax = subprocess.run(
        [
            clang,
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
    assert res_syntax.returncode == 0, f"clang syntax check failed:\nstdout: {res_syntax.stdout}\nstderr: {res_syntax.stderr}"


def test_cppcheck_tool_availability_and_invocation() -> None:
    """AC-2: cppcheck must be discoverable and invokable with --version, --help, and analysis."""
    cppcheck = resolve_tool_executable("cppcheck")
    assert cppcheck is not None, "cppcheck is not discoverable on PATH or scripts/cppcheck"

    res_version = subprocess.run([cppcheck, "--version"], capture_output=True, text=True, check=False)
    assert res_version.returncode == 0, f"cppcheck --version failed:\n{res_version.stderr}"

    res_help = subprocess.run([cppcheck, "--help"], capture_output=True, text=True, check=False)
    assert res_help.returncode == 0, f"cppcheck --help failed:\n{res_help.stderr}"

    res_check = subprocess.run(
        [
            cppcheck,
            "--quiet",
            "--enable=all",
            "--suppress=missingIncludeSystem",
            str(SYSDIFF_SRC),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_check.returncode == 0, f"cppcheck check failed:\nstdout: {res_check.stdout}\nstderr: {res_check.stderr}"


def test_clang_tidy_tool_availability_and_invocation() -> None:
    """AC-2: clang-tidy must be discoverable and invokable with --version, --help, and analysis."""
    clang_tidy = resolve_tool_executable("clang-tidy")
    assert clang_tidy is not None, (
        "clang-tidy is not discoverable on PATH, known locations, or as a wrapper in scripts/clang-tidy. "
        "Validation environment repair must provide a working clang-tidy executable (reproducing ba39f236f2b4)."
    )

    res_version = subprocess.run([clang_tidy, "--version"], capture_output=True, text=True, check=False)
    assert res_version.returncode == 0, f"clang-tidy --version failed:\nstdout: {res_version.stdout}\nstderr: {res_version.stderr}"

    res_help = subprocess.run([clang_tidy, "--help"], capture_output=True, text=True, check=False)
    assert res_help.returncode == 0, f"clang-tidy --help failed:\nstdout: {res_help.stdout}\nstderr: {res_help.stderr}"


def test_ensure_tools_script_provisions_all_tools() -> None:
    """AC-2: scripts/ensure_tools.sh must verify and provision clang, cppcheck, and clang-tidy."""
    ensure_script = ROOT / "scripts" / "ensure_tools.sh"
    assert ensure_script.exists(), f"Missing {ensure_script}"
    content = ensure_script.read_text(encoding="utf-8")

    assert "clang" in content, "scripts/ensure_tools.sh does not reference clang"
    assert "cppcheck" in content, "scripts/ensure_tools.sh does not reference cppcheck"
    assert "clang-tidy" in content, (
        "scripts/ensure_tools.sh does not verify or provision clang-tidy. "
        "In governed run ba39f236f2b4, clang-tidy was missing from the validation environment. "
        "ensure_tools.sh must ensure all three tools (clang, cppcheck, clang-tidy)."
    )

    res = subprocess.run([str(ensure_script)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"scripts/ensure_tools.sh execution failed: {res.stderr}"


def test_makefile_clang_tidy_check_resilience() -> None:
    """AC-2: Makefile target 'clang-tidy-check' must provide preflight tool resolution or guard.

    In governed run ba39f236f2b4, clang-tidy-check failed immediately because clang-tidy
    was absent from host $PATH and the Makefile target lacked wrapper resolution or a preflight guard.
    Analogous to cppcheck-check and clang-strict, the recipe must locate scripts/clang-tidy
    or verify availability before execution to prevent untyped exit 127 faults.
    """
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    match = re.search(
        r"^clang-tidy-check:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing clang-tidy-check target"
    recipe = match.group(1)

    has_resolution = (
        "scripts/clang-tidy" in recipe
        or "command -v clang-tidy" in recipe
        or "which clang-tidy" in recipe
        or "check_tools" in recipe
    )
    assert has_resolution, (
        "Makefile target 'clang-tidy-check' invokes bare clang-tidy without preflight discovery "
        "or wrapper resolution (scripts/clang-tidy), causing untyped exit code 127 when clang-tidy "
        "is absent from $PATH (reproducing governed run ba39f236f2b4 failure mode)."
    )


def test_makefile_cppcheck_check_has_preflight_guard() -> None:
    """AC-2: Makefile target 'cppcheck-check' must probe tool availability before execution."""
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
        or "scripts/cppcheck" in recipe
    )
    assert has_preflight, (
        "Makefile target 'cppcheck-check' missing preflight guard for cppcheck availability"
    )


def test_makefile_clang_strict_and_syntax_have_preflight_guards() -> None:
    """AC-2: Makefile targets 'clang-strict' and 'clang-syntax' must guard clang availability."""
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    for target in ("clang-strict", "clang-syntax"):
        match = re.search(
            rf"^{re.escape(target)}:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        )
        assert match is not None, f"Makefile missing {target} target"
        recipe = match.group(1)
        has_guard = (
            "command -v clang" in recipe
            or "which clang" in recipe
            or "scripts/clang" in recipe
        )
        assert has_guard, f"Makefile target {target!r} missing clang availability guard"


def test_makefile_clang_analyzer_check_has_preflight_guard() -> None:
    """AC-2: Makefile target 'clang-analyzer-check' must guard clang availability."""
    assert MAKEFILE.exists(), f"Missing {MAKEFILE}"
    content = MAKEFILE.read_text(encoding="utf-8")

    match = re.search(
        r"^clang-analyzer-check:(.*?)(?=\n[a-zA-Z0-9_.-]+:|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, "Makefile missing clang-analyzer-check target"
    recipe = match.group(1)
    has_guard = (
        "command -v clang" in recipe
        or "which clang" in recipe
        or "scripts/clang" in recipe
    )
    assert has_guard, "Makefile target 'clang-analyzer-check' missing clang availability guard"


def test_preflight_probe_all_tools_when_absent() -> None:
    """AC-2: When tools are absent from PATH, preflight probing reports available=False cleanly."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    empty_env = {"PATH": ""}
    for tool in ("clang", "cppcheck", "clang-tidy"):
        result = check_tools.probe_executable(tool, env=empty_env)
        assert not result.available, f"Expected {tool} to be absent with empty PATH"
        assert f"{tool} was not found on PATH" in result.detail


def test_preflight_probe_all_tools_when_present(tmp_path: Path) -> None:
    """AC-2: When tools are present on PATH, preflight probing reports available=True."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for tool in ("clang", "cppcheck", "clang-tidy"):
        fake_exe = make_fake_executable(fake_bin, tool)
        result = check_tools.probe_executable(tool, env={"PATH": str(fake_bin)})
        assert result.available is True, f"Failed to detect {tool} on PATH"
        assert result.detail == f"found {tool} at {fake_exe}"


def test_preflight_probes_are_read_only_and_bounded() -> None:
    """AC-2: Preflight tool probing must be read-only, non-mutating, and complete within 2.0s."""
    if check_tools is None:
        pytest.skip("scripts/check_tools.py is not importable")

    start_time = time.monotonic()
    res_gcc = check_tools.probe_executable("gcc")
    res_clang = check_tools.probe_executable("clang")
    res_cppcheck = check_tools.probe_executable("cppcheck")
    res_clang_tidy = check_tools.probe_executable("clang-tidy")
    elapsed = time.monotonic() - start_time

    assert elapsed < 2.0, f"Tool probing took {elapsed:.2f}s, expected < 2.0s"
    assert res_gcc.name == "gcc"
    assert res_clang.name == "clang"
    assert res_cppcheck.name == "cppcheck"
    assert res_clang_tidy.name == "clang-tidy"


def test_gcc_syntax_baseline_guaranteed() -> None:
    """AC-2: GCC is guaranteed on Linux; baseline ISO C17 compilation passes cleanly."""
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
# AC-3: Manifest Synchronization, Traceability, and Non-Product Blast Radius
# ============================================================================


def test_user_journeys_manifests_are_synchronized() -> None:
    """AC-3: Both tests and journeys manifests exist and are identical parsed objects."""
    assert TESTS_MANIFEST.exists(), f"Missing canonical oracle {TESTS_MANIFEST}"
    assert JOURNEYS_MANIFEST.exists(), f"Missing secondary manifest {JOURNEYS_MANIFEST}"

    tests_manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys_manifest = json.loads(JOURNEYS_MANIFEST.read_text(encoding="utf-8"))

    assert tests_manifest == journeys_manifest, (
        "Repository journey manifests are not identical parsed objects."
    )


def test_user_journeys_manifest_schema_and_command_allowlist() -> None:
    """AC-3: Manifest adheres to canonical schema and preserves immutable command allowlist."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))

    if jsonschema is not None and USER_JOURNEYS_MANIFEST_SCHEMA:
        validator = jsonschema.Draft202012Validator(USER_JOURNEYS_MANIFEST_SCHEMA)
        errors = list(validator.iter_errors(manifest))
        assert not errors, f"Schema validation errors in {TESTS_MANIFEST}: {errors}"

    allowlist = manifest.get("command_allowlist", [])
    assert allowlist == ["build/sysdiff"], (
        f"command_allowlist must remain strictly ['build/sysdiff'], got: {allowlist}"
    )


def test_user_journeys_manifest_contains_all_21_journeys() -> None:
    """AC-3: Manifest preserves all 21 author, sysdiff, and bwrap journeys without omission."""
    assert TESTS_MANIFEST.exists(), f"Missing {TESTS_MANIFEST}"
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = manifest.get("journeys", [])
    assert len(journeys) == 21, f"Expected exactly 21 journeys, found {len(journeys)}"

    names = {j["name"] for j in journeys}
    missing_author = PRESERVED_AUTHOR_JOURNEYS - names
    assert not missing_author, f"Manifest omitted preserved author journeys: {missing_author}"

    missing_sysdiff = SYSDIFF_JOURNEYS - names
    assert not missing_sysdiff, f"Manifest omitted sysdiff product journeys: {missing_sysdiff}"

    missing_bwrap = BWRAP_JOURNEYS - names
    assert not missing_bwrap, f"Manifest omitted bwrap repair journeys: {missing_bwrap}"


def test_journey_traceability_and_acceptance_coverage() -> None:
    """AC-3: All required journeys map to valid acceptance checks and AC-1..3 are covered."""
    manifest = json.loads(TESTS_MANIFEST.read_text(encoding="utf-8"))
    journeys = manifest.get("journeys", [])
    allowed_traces = {"AC-1", "AC-2", "AC-3"}

    covered_traces: set[str] = set()
    for j in journeys:
        authority = j.get("authority", "author")
        assert authority in JOURNEY_AUTHORITIES, f"Invalid authority {authority!r} in journey {j['name']!r}"
        traces = j.get("traces_to", [])
        if authority != "exploratory":
            assert traces, f"Required journey {j['name']!r} lacks traces_to"
            assert set(traces) <= allowed_traces, f"Journey {j['name']!r} has invalid traces: {traces}"
            covered_traces.update(traces)

    assert covered_traces == allowed_traces, (
        f"Acceptance checks not fully covered by required journeys: {allowed_traces - covered_traces}"
    )


def test_sysdiff_c_source_and_non_product_blast_radius() -> None:
    """AC-3: sysdiff C source remains unaltered ISO C17 without leaking orchestrator tokens."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0
    assert MAN_PAGE.exists() and MAN_PAGE.stat().st_size > 0

    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")
    for forbidden in ("bwrap", "agent_orch", "PATH_ESCAPE", "ba39f236f2b4"):
        assert forbidden not in src_text, f"sysdiff source contaminated with {forbidden}"
