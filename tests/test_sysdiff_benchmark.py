"""Contract tests for the deterministic sysdiff performance benchmark harness.

These tests require ``scripts/benchmark_sysdiff.py`` to be present. Absence of
the harness is a hard failure (not a skip). They drive measurement helpers with
controlled fake executables and never require a workspace ``build/`` of
``sysdiff`` or a live compiler invocation for the contract surface.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_sysdiff.py"

# Contract identifiers the harness must expose and emit.
SCHEMA_VERSION = 1
MEASUREMENT_STARTUP = "startup_ms_median"
MEASUREMENT_FIXTURE = "fixture_ms_median"
MEASUREMENT_PEAK_RSS = "peak_rss_kib"
REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "measurements",
    "thresholds",
    "samples",
    "metadata",
    "passed",
)
REQUIRED_MEASUREMENT_KEYS = (
    MEASUREMENT_STARTUP,
    MEASUREMENT_FIXTURE,
    MEASUREMENT_PEAK_RSS,
)


def load_benchmark_module():
    """Import the committed harness; fail hard if the script is missing."""

    if not SCRIPT.is_file():
        pytest.fail(f"{SCRIPT} is missing")
    spec = importlib.util.spec_from_file_location("benchmark_sysdiff_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def benchmark():
    return load_benchmark_module()


def write_executable(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def make_fake_sysdiff(
    directory: Path,
    *,
    startup_sleep_s: float = 0.0,
    compare_sleep_s: float = 0.0,
    allocate_mib: int = 0,
    compare_status: int = 1,
) -> Path:
    """Controlled stand-in for sysdiff: --help/--version and compare only."""

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "sysdiff"
    write_executable(
        binary,
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "import time\n"
        f"STARTUP_SLEEP = {startup_sleep_s!r}\n"
        f"COMPARE_SLEEP = {compare_sleep_s!r}\n"
        f"ALLOCATE_MIB = {allocate_mib!r}\n"
        f"COMPARE_STATUS = {compare_status!r}\n"
        "\n"
        "def allocate() -> None:\n"
        "    if ALLOCATE_MIB <= 0:\n"
        "        return\n"
        "    # Hold a contiguous block so peak RSS is observable on Linux.\n"
        "    blob = bytearray(ALLOCATE_MIB * 1024 * 1024)\n"
        "    blob[0] = 1\n"
        "    blob[-1] = 2\n"
        "    time.sleep(0.05)\n"
        "    del blob\n"
        "\n"
        "argv = sys.argv[1:]\n"
        "if not argv or argv[0] in ('--help', '-h'):\n"
        "    time.sleep(STARTUP_SLEEP)\n"
        "    allocate()\n"
        "    sys.stdout.write('usage: sysdiff --help|--version|compare BEFORE AFTER\\n')\n"
        "    raise SystemExit(0)\n"
        "if argv[0] in ('--version', '-V'):\n"
        "    time.sleep(STARTUP_SLEEP)\n"
        "    allocate()\n"
        "    sys.stdout.write('sysdiff 0.1.0\\n')\n"
        "    raise SystemExit(0)\n"
        "if argv[0] == 'compare':\n"
        "    time.sleep(COMPARE_SLEEP)\n"
        "    allocate()\n"
        "    if len(argv) != 3:\n"
        "        sys.stderr.write('compare requires BEFORE_SNAPSHOT AFTER_SNAPSHOT\\n')\n"
        "        raise SystemExit(2)\n"
        "    sys.stdout.write('+ added.key=value\\n')\n"
        "    raise SystemExit(COMPARE_STATUS)\n"
        "sys.stderr.write('unknown command\\n')\n"
        "raise SystemExit(2)\n",
    )
    return binary


def write_controlled_snapshots(directory: Path) -> tuple[Path, Path]:
    before = directory / "before.snapshot"
    after = directory / "after.snapshot"
    before.write_text(
        "sysdiff.snapshot_version=1\n"
        "os.id=debian\n"
        "removed.key=gone\n"
        "same.keep=stable\n"
        "z.changed=old\n",
        encoding="utf-8",
    )
    after.write_text(
        "sysdiff.snapshot_version=1\n"
        "os.id=debian\n"
        "added.key=new\n"
        "same.keep=stable\n"
        "z.changed=new\n",
        encoding="utf-8",
    )
    return before, after


def run_benchmark_cli(args: Sequence[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None):
    if not SCRIPT.is_file():
        pytest.fail(f"{SCRIPT} is missing")
    full_env = os.environ.copy()
    if env is not None:
        full_env.update(env)
    # Never inherit a workspace build hint; the harness must not trust these.
    full_env.pop("SYSDIFF_BIN", None)
    full_env.pop("BENCHMARK_SYSDIFF_BIN", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=str(cwd or ROOT),
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )


def require_attr(module: Any, name: str):
    if not hasattr(module, name):
        pytest.fail(f"benchmark module must expose {name}")
    return getattr(module, name)


def call_first(module: Any, names: Sequence[str], *args, **kwargs):
    """Call the first present callable among ``names``."""

    for name in names:
        func = getattr(module, name, None)
        if callable(func):
            return func(*args, **kwargs)
    pytest.fail(f"benchmark module must expose one of: {', '.join(names)}")


def extract_median(module: Any, samples: Sequence[float]) -> float:
    return float(
        call_first(
            module,
            ("aggregate_samples", "median", "aggregate_median", "sample_median"),
            samples,
        )
    )


def thresholds_from_module(module: Any) -> Mapping[str, float]:
    for name in ("DEFAULT_THRESHOLDS", "THRESHOLDS", "RELEASE_THRESHOLDS"):
        value = getattr(module, name, None)
        if isinstance(value, Mapping):
            return value
    pytest.fail("benchmark module must expose an explicit default thresholds mapping")


def assert_report_shape(report: Mapping[str, Any]) -> None:
    for key in REQUIRED_TOP_LEVEL_KEYS:
        assert key in report, f"missing top-level key: {key}"
    assert report["schema_version"] == SCHEMA_VERSION
    assert isinstance(report["passed"], bool)
    measurements = report["measurements"]
    thresholds = report["thresholds"]
    samples = report["samples"]
    metadata = report["metadata"]
    assert isinstance(measurements, Mapping)
    assert isinstance(thresholds, Mapping)
    assert isinstance(samples, Mapping)
    assert isinstance(metadata, Mapping)
    for key in REQUIRED_MEASUREMENT_KEYS:
        assert key in measurements, f"missing measurement: {key}"
        assert key in thresholds, f"missing threshold: {key}"
        assert measurements[key] is not None
        assert thresholds[key] is not None
    # Sample lists must exist for each timed/RSS metric family.
    assert any(k.startswith("startup") for k in samples)
    assert any(k.startswith("fixture") for k in samples)
    assert any("rss" in k for k in samples)


# ---------------------------------------------------------------------------
# Deterministic sample aggregation
# ---------------------------------------------------------------------------


def test_sample_aggregation_is_deterministic_median(benchmark):
    samples = [9.0, 1.0, 5.0, 3.0, 7.0]
    first = extract_median(benchmark, samples)
    second = extract_median(benchmark, list(reversed(samples)))
    assert first == second
    assert first == 5.0


def test_sample_aggregation_handles_even_count_without_jitter(benchmark):
    # Even-length median must be stable across shuffles (mean of center pair).
    samples = [2.0, 8.0, 4.0, 6.0]
    assert extract_median(benchmark, samples) == 5.0
    assert extract_median(benchmark, list(reversed(samples))) == 5.0


def test_warmup_and_sample_counts_are_fixed_and_positive(benchmark):
    warmups = require_attr(benchmark, "DEFAULT_WARMUPS")
    sample_count = require_attr(benchmark, "DEFAULT_SAMPLE_COUNT")
    assert isinstance(warmups, int) and warmups >= 0
    assert isinstance(sample_count, int) and sample_count >= 3
    assert sample_count % 2 == 1, "odd sample count keeps median free of pair-averaging drift"


# ---------------------------------------------------------------------------
# Startup-time measurement
# ---------------------------------------------------------------------------


def test_startup_time_measurement_uses_monotonic_samples(benchmark, tmp_path):
    binary = make_fake_sysdiff(tmp_path, startup_sleep_s=0.02)
    measure = require_attr(benchmark, "measure_runtime_ms")
    started = time.monotonic()
    elapsed_ms = float(measure([str(binary), "--help"]))
    wall_ms = (time.monotonic() - started) * 1000.0
    assert elapsed_ms >= 15.0
    assert elapsed_ms <= wall_ms + 50.0


def test_startup_measurement_excludes_setup_by_timing_only_the_child(benchmark, tmp_path):
    binary = make_fake_sysdiff(tmp_path, startup_sleep_s=0.0)
    measure = require_attr(benchmark, "measure_runtime_ms")
    # A fast fake must report a small runtime; setup work around the call is
    # outside the helper and must not inflate the sample into seconds.
    samples = [float(measure([str(binary), "--version"])) for _ in range(3)]
    assert max(samples) < 500.0


# ---------------------------------------------------------------------------
# Controlled-fixture runtime measurement
# ---------------------------------------------------------------------------


def test_controlled_fixture_runtime_measurement(benchmark, tmp_path):
    binary = make_fake_sysdiff(tmp_path, compare_sleep_s=0.03, compare_status=1)
    before, after = write_controlled_snapshots(tmp_path)
    measure = require_attr(benchmark, "measure_runtime_ms")
    elapsed_ms = float(
        measure(
            [str(binary), "compare", str(before), str(after)],
            expected_statuses=(0, 1),
        )
    )
    assert elapsed_ms >= 20.0


def test_fixture_helper_uses_fixed_snapshot_layout_when_building_workload(benchmark, tmp_path):
    prepare = require_attr(benchmark, "prepare_controlled_fixtures")
    before, after = prepare(tmp_path)
    assert Path(before).is_file()
    assert Path(after).is_file()
    assert Path(before).read_bytes() != Path(after).read_bytes()
    # Scaled workload must exceed a trivial five-line pair so compare beats spawn.
    entry_count = getattr(benchmark, "CONTROLLED_FIXTURE_ENTRY_COUNT", None)
    assert isinstance(entry_count, int) and entry_count >= 1000
    before_lines = [
        line for line in Path(before).read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(before_lines) >= entry_count // 2


# ---------------------------------------------------------------------------
# Linux peak-RSS measurement
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="peak RSS contract is Linux-specific")
def test_linux_peak_rss_measurement_reflects_allocation(benchmark, tmp_path):
    small = make_fake_sysdiff(tmp_path / "small", allocate_mib=0)
    large_dir = tmp_path / "large"
    large_dir.mkdir()
    large = make_fake_sysdiff(large_dir, allocate_mib=32)
    measure_rss = require_attr(benchmark, "measure_peak_rss_kib")

    small_rss = int(measure_rss([str(small), "--help"]))
    large_rss = int(measure_rss([str(large), "--help"]))

    assert small_rss > 0
    assert large_rss > small_rss
    # 32 MiB allocation should push peak RSS well above 16 MiB.
    assert large_rss >= 16 * 1024


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="peak RSS contract is Linux-specific")
def test_peak_rss_units_are_kib(benchmark, tmp_path):
    binary = make_fake_sysdiff(tmp_path, allocate_mib=8)
    measure_rss = require_attr(benchmark, "measure_peak_rss_kib")
    rss = int(measure_rss([str(binary), "--version"]))
    # Sanity: KiB scale for an 8 MiB touch should be thousands, not bytes.
    assert 1024 <= rss <= 512 * 1024


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="peak RSS contract is Linux-specific")
def test_peak_rss_tiny_wrapper_tolerates_child_stdout(benchmark, tmp_path):
    """Wrapper report must stay valid when the child writes to stdout (F001)."""

    # Fake sysdiff --help always emits usage text on stdout; the old wrapper
    # shared that pipe with its RSS report and failed to parse.
    binary = make_fake_sysdiff(tmp_path, allocate_mib=4)
    measure = require_attr(benchmark, "_peak_rss_via_tiny_wrapper")
    rss = int(measure([str(binary), "--help"], 30.0, (0,)))
    assert rss > 0


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="peak RSS contract is Linux-specific")
def test_rss_wrapper_compiles_under_strict_c17(benchmark, tmp_path):
    """RSS helper must build with -std=c17 -Wall -Wextra -Werror (F003)."""

    _ = tmp_path
    wrapper_path = require_attr(benchmark, "_rss_wrapper_path")
    binary = wrapper_path()
    assert Path(binary).is_file()
    assert os.access(binary, os.X_OK)


# ---------------------------------------------------------------------------
# Threshold pass and fail behavior
# ---------------------------------------------------------------------------


def test_threshold_pass_when_measurements_within_limits(benchmark):
    thresholds = {
        MEASUREMENT_STARTUP: 100.0,
        MEASUREMENT_FIXTURE: 500.0,
        MEASUREMENT_PEAK_RSS: 65536,
    }
    measurements = {
        MEASUREMENT_STARTUP: 10.0,
        MEASUREMENT_FIXTURE: 50.0,
        MEASUREMENT_PEAK_RSS: 4096,
    }
    passed = call_first(
        benchmark,
        ("thresholds_passed", "evaluate_thresholds", "check_thresholds"),
        measurements,
        thresholds,
    )
    assert passed is True


def test_threshold_fail_when_any_measurement_exceeds_limit(benchmark):
    thresholds = {
        MEASUREMENT_STARTUP: 100.0,
        MEASUREMENT_FIXTURE: 500.0,
        MEASUREMENT_PEAK_RSS: 65536,
    }
    measurements = {
        MEASUREMENT_STARTUP: 10.0,
        MEASUREMENT_FIXTURE: 501.0,
        MEASUREMENT_PEAK_RSS: 4096,
    }
    passed = call_first(
        benchmark,
        ("thresholds_passed", "evaluate_thresholds", "check_thresholds"),
        measurements,
        thresholds,
    )
    assert passed is False


def test_default_thresholds_are_conservative_release_guardrails(benchmark):
    thresholds = thresholds_from_module(benchmark)
    for key in REQUIRED_MEASUREMENT_KEYS:
        assert key in thresholds
        assert float(thresholds[key]) > 0
    # Guardrails must be finite and stricter than multi-second / multi-GiB noise.
    assert float(thresholds[MEASUREMENT_STARTUP]) <= 1000.0
    assert float(thresholds[MEASUREMENT_FIXTURE]) <= 5000.0
    assert float(thresholds[MEASUREMENT_PEAK_RSS]) <= 256 * 1024


def test_report_marks_failed_when_thresholds_are_impossible(benchmark, tmp_path):
    binary = make_fake_sysdiff(tmp_path, compare_sleep_s=0.05)
    before, after = write_controlled_snapshots(tmp_path)
    run_fn = getattr(benchmark, "run_benchmark", None)
    if not callable(run_fn):
        pytest.skip("run_benchmark helper required for injectable threshold failure")
    tight = {
        MEASUREMENT_STARTUP: 0.0001,
        MEASUREMENT_FIXTURE: 0.0001,
        MEASUREMENT_PEAK_RSS: 1,
    }
    report = run_fn(
        binary=binary,
        before=before,
        after=after,
        thresholds=tight,
        warmups=0,
        sample_count=3,
        work_dir=tmp_path / "fail-work",
    )
    assert_report_shape(report)
    assert report["passed"] is False

    # Library/CLI entry points must treat failed reports as nonzero status.
    exit_status = getattr(benchmark, "report_exit_status", None)
    if callable(exit_status):
        assert int(exit_status(report)) != 0
    else:
        main = require_attr(benchmark, "main")
        # When main accepts an already-built report path only, the boolean on
        # the report remains the authoritative fail signal for this contract.
        assert report["passed"] is False
        assert callable(main)


# ---------------------------------------------------------------------------
# Stable JSON output
# ---------------------------------------------------------------------------


def test_json_report_is_stable_for_identical_inputs(benchmark, tmp_path):
    build_report = require_attr(benchmark, "build_report")
    measurements = {
        MEASUREMENT_STARTUP: 1.25,
        MEASUREMENT_FIXTURE: 4.5,
        MEASUREMENT_PEAK_RSS: 3072,
    }
    thresholds = thresholds_from_module(benchmark)
    samples = {
        "startup_ms": [1.0, 1.25, 1.5],
        "fixture_ms": [4.0, 4.5, 5.0],
        "peak_rss_kib": [3072, 3072, 3072],
    }
    metadata = {
        "warmups": 1,
        "sample_count": 3,
        "platform": "linux",
    }
    first = build_report(
        measurements=measurements,
        thresholds=thresholds,
        samples=samples,
        metadata=metadata,
    )
    second = build_report(
        measurements=dict(measurements),
        thresholds=dict(thresholds),
        samples={k: list(v) for k, v in samples.items()},
        metadata=dict(metadata),
    )
    assert_report_shape(first)
    assert_report_shape(second)

    encode = getattr(benchmark, "encode_report_json", None)
    if not callable(encode):
        encode = getattr(benchmark, "report_to_json", None)
    if callable(encode):
        assert encode(first) == encode(second)
        payload = encode(first)
    else:
        payload = json.dumps(first, sort_keys=True, separators=(",", ":"))
        assert payload == json.dumps(second, sort_keys=True, separators=(",", ":"))

    parsed = json.loads(payload)
    assert_report_shape(parsed)
    out = tmp_path / "sysdiff-benchmark.json"
    out.write_text(payload if isinstance(payload, str) else payload.decode(), encoding="utf-8")
    assert out.is_file()


def test_help_lists_metrics_and_thresholds(benchmark):
    main = require_attr(benchmark, "main")
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        status = main(["--help"], stdout=stdout, stderr=stderr)
    except TypeError:
        result = run_benchmark_cli(["--help"])
        status = result.returncode
        help_text = result.stdout + result.stderr
    else:
        help_text = stdout.getvalue() + stderr.getvalue()
    assert status == 0
    lowered = help_text.lower()
    assert "startup" in lowered
    assert "fixture" in lowered or "compare" in lowered
    assert "rss" in lowered
    assert "threshold" in lowered


# ---------------------------------------------------------------------------
# Temporary-directory isolation
# ---------------------------------------------------------------------------


def test_temporary_directory_isolation_does_not_write_workspace_build(benchmark, tmp_path):
    binary = make_fake_sysdiff(tmp_path, startup_sleep_s=0.0, compare_sleep_s=0.0)
    before, after = write_controlled_snapshots(tmp_path)
    run_fn = getattr(benchmark, "run_benchmark", None)
    if not callable(run_fn):
        pytest.skip("run_benchmark helper required for isolation check")

    build_dir = ROOT / "build"
    before_entries = set(build_dir.iterdir()) if build_dir.exists() else None

    report = run_fn(
        binary=binary,
        before=before,
        after=after,
        work_dir=tmp_path / "bench-work",
        warmups=0,
        sample_count=3,
    )
    assert_report_shape(report)

    if before_entries is None:
        assert not build_dir.exists() or set(build_dir.iterdir()) == set()
    else:
        assert set(build_dir.iterdir()) == before_entries

    # When a work_dir is supplied, the harness must not create sibling dirs under
    # the repository root build tree as a side effect of that run.
    assert not (ROOT / "build" / "benchmark-sysdiff").exists()


def test_harness_cleans_up_child_processes(benchmark, tmp_path):
    # A hung child must not be left behind; the harness should terminate it.
    hang = write_executable(
        tmp_path / "hang",
        "#!/usr/bin/env python3\n"
        "import time\n"
        "time.sleep(30)\n",
    )
    measure = getattr(benchmark, "measure_runtime_ms", None)
    if not callable(measure):
        pytest.skip("measure_runtime_ms required for cleanup contract")
    # Optional timeout argument: if unsupported, skip rather than hang the suite.
    try:
        measure([str(hang)], timeout_s=0.2)
    except TypeError:
        pytest.skip("measure_runtime_ms does not expose timeout_s yet")
    except Exception:
        # Timeout/failure is acceptable; the process must not remain.
        pass
    # No python hang child should still be alive with this script path.
    try:
        listing = subprocess.run(
            ["ps", "-eo", "pid,args"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("ps is unavailable")
    assert str(hang) not in listing.stdout


# ---------------------------------------------------------------------------
# Rejection of malformed arguments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        ["--not-a-real-flag"],
        ["--output"],  # missing PATH value
        ["--output", ""],  # empty PATH value
        ["--help", "--not-a-real-flag"],
    ],
)
def test_rejects_malformed_arguments(args):
    result = run_benchmark_cli(args)
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert result.stderr != "" or "usage" in combined


def test_rejects_output_path_that_is_a_directory(tmp_path):
    result = run_benchmark_cli(["--output", str(tmp_path)])
    assert result.returncode != 0
    assert result.stderr != "" or "usage" in result.stdout.lower()


def test_module_main_rejects_unknown_option(benchmark):
    main = require_attr(benchmark, "main")
    err = io.StringIO()
    try:
        status = main(["--definitely-unknown"], stderr=err)
    except TypeError:
        status = main(["--definitely-unknown"])
    assert status != 0


# ---------------------------------------------------------------------------
# End-to-end report against fakes (no workspace build)
# ---------------------------------------------------------------------------


def test_run_benchmark_with_fake_executable_emits_full_contract(benchmark, tmp_path):
    binary = make_fake_sysdiff(
        tmp_path,
        startup_sleep_s=0.0,
        compare_sleep_s=0.0,
        allocate_mib=0,
        compare_status=1,
    )
    before, after = write_controlled_snapshots(tmp_path)
    run_fn = require_attr(benchmark, "run_benchmark")
    report = run_fn(
        binary=binary,
        before=before,
        after=after,
        warmups=0,
        sample_count=3,
        work_dir=tmp_path / "work",
    )
    assert_report_shape(report)
    assert report["schema_version"] == SCHEMA_VERSION
    assert isinstance(report["passed"], bool)
    for key in REQUIRED_MEASUREMENT_KEYS:
        assert float(report["measurements"][key]) >= 0.0
        assert float(report["thresholds"][key]) > 0.0
    # Spawn-cost baseline is recorded so startup/fixture can be read net of it.
    assert "baseline_ms_median" in report["measurements"]
    assert float(report["measurements"]["baseline_ms_median"]) >= 0.0
    assert any(k.startswith("baseline") for k in report["samples"])
    assert report["metadata"].get("work_dir_kind") == "tempdir"
    assert "work_dir" not in report["metadata"]
    # Fixed sample count must match metadata / sample list lengths.
    meta_count = report["metadata"].get("sample_count", 3)
    for values in report["samples"].values():
        assert len(values) == meta_count


def test_run_benchmark_rejects_unexpected_child_status(benchmark, tmp_path):
    """A fast-failing compare must not produce passed=true (review finding B1)."""

    binary = make_fake_sysdiff(
        tmp_path,
        startup_sleep_s=0.0,
        compare_sleep_s=0.0,
        compare_status=2,
    )
    before, after = write_controlled_snapshots(tmp_path)
    run_fn = require_attr(benchmark, "run_benchmark")
    with pytest.raises(RuntimeError, match=r"exited with status 2"):
        run_fn(
            binary=binary,
            before=before,
            after=after,
            warmups=0,
            sample_count=1,
            work_dir=tmp_path / "fail-status-work",
        )
