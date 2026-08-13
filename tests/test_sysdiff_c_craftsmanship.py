"""Focused regressions for the sysdiff C craftsmanship repair slice.

These tests exercise observable parser, diagnostic, cleanup, and portability
contracts.  They keep all binaries, preload shims, snapshots, and fake tools in
pytest's temporary directory; no workspace build artifact is required.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"
MALFORMED_FUZZ = ROOT / "tests" / "test_sysdiff_malformed_fuzz.py"
MAX_LINE_BYTES = 65536
STRICT_FLAGS = ("-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror")


@pytest.fixture(scope="module")
def sysdiff_bin(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the source under the repository's strict C17 warning floor."""

    compiler = os.environ.get("CC", "cc")
    if shutil.which(compiler) is None:
        pytest.fail(f"strict C compiler is unavailable: {compiler}")

    build_dir = tmp_path_factory.mktemp("sysdiff-c-craftsmanship-build")
    binary = build_dir / "sysdiff"
    result = subprocess.run(
        [compiler, *STRICT_FLAGS, "-O2", "-o", str(binary), str(SRC)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert binary.is_file()
    return binary


def run_sysdiff(binary: Path, *args: object, env: dict[str, str] | None = None):
    child_env = os.environ.copy()
    if env is not None:
        child_env.update(env)
    return subprocess.run(
        [str(binary), *(str(arg) for arg in args)],
        capture_output=True,
        check=False,
        env=child_env,
        timeout=10,
    )


def assert_terminal_safe_diagnostics(stderr: bytes) -> None:
    """Allow diagnostic line endings, but never raw hostile control bytes."""

    unsafe = [byte for byte in stderr if byte < 0x20 and byte != 0x0A]
    assert not unsafe, f"raw control bytes in stderr: {unsafe!r}"


def test_strict_c17_source_build_is_available_without_workspace_binary(sysdiff_bin):
    """The source must pass the declared warning floor in a temporary tree."""

    assert sysdiff_bin.parent != ROOT / "build"
    assert sysdiff_bin.is_file()


def test_crlf_boundary_preserves_content_limit_and_rejects_one_extra_byte(
    sysdiff_bin, tmp_path
):
    """CRLF's terminator bytes must not reduce the 65,536-byte content limit."""

    prefix = b"boundary.key="
    value_at_limit = b"x" * (MAX_LINE_BYTES - len(prefix))
    lf = tmp_path / "limit-lf.snapshot"
    crlf = tmp_path / "limit-crlf.snapshot"
    over = tmp_path / "limit-over.snapshot"
    lf.write_bytes(prefix + value_at_limit + b"\n")
    crlf.write_bytes(prefix + value_at_limit + b"\r\n")
    over.write_bytes(prefix + value_at_limit + b"y\n")

    equivalent = run_sysdiff(sysdiff_bin, "compare", lf, crlf)
    assert equivalent.returncode == 0
    assert equivalent.stdout == b"no changes\n"
    assert equivalent.stderr == b""

    rejected = run_sysdiff(sysdiff_bin, "compare", over, lf)
    assert rejected.returncode == 2
    assert rejected.stdout == b""
    assert b"line length limit" in rejected.stderr
    assert str(over).encode() in rejected.stderr


def test_malformed_after_snapshot_is_atomic_and_escapes_hostile_path(
    sysdiff_bin, tmp_path
):
    """A late hostile byte cannot leak a partial diff or forge diagnostics."""

    before = tmp_path / "before.snapshot"
    after = tmp_path / "after-\x1b\n.snapshot"
    before.write_bytes(b"changed.key=old\nkeep.key=value\n")
    after.write_bytes(b"changed.key=new\nbad.key=prefix\x00suffix\n")

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"after-\\x1B\\x0A.snapshot" in result.stderr
    assert b"embedded NUL byte" in result.stderr
    assert b"changed.key" not in result.stdout
    assert_terminal_safe_diagnostics(result.stderr)


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux directory read semantics")
def test_directory_read_failure_is_status_two_with_empty_stdout(sysdiff_bin, tmp_path):
    """A readable directory operand must fail closed after parser setup."""

    before = tmp_path / "before.snapshot"
    after_dir = tmp_path / "directory.snapshot"
    before.write_bytes(b"changed.key=old\n")
    after_dir.mkdir()

    result = run_sysdiff(sysdiff_bin, "compare", before, after_dir)

    assert result.returncode == 2
    assert result.stdout == b""
    assert str(after_dir).encode() in result.stderr
    assert b"read error" in result.stderr


@pytest.mark.skipif(platform.system() != "Linux", reason="LD_PRELOAD is Linux-only here")
def test_second_snapshot_close_failure_is_reported_without_partial_diff(
    sysdiff_bin, tmp_path
):
    """The after-snapshot close error must free the before snapshot and fail."""

    compiler = os.environ.get("CC", "cc")
    if shutil.which(compiler) is None:
        pytest.fail(f"C compiler is unavailable for fclose shim: {compiler}")

    shim_source = tmp_path / "fail-second-fclose.c"
    shim = tmp_path / "fail-second-fclose.so"
    shim_source.write_text(
        textwrap.dedent(
            r"""
            #define _GNU_SOURCE
            #include <dlfcn.h>
            #include <errno.h>
            #include <stdio.h>

            typedef int (*real_fclose_fn)(FILE *);
            static real_fclose_fn real_fclose;
            static unsigned long calls;

            int fclose(FILE *stream) {
                if (real_fclose == NULL) {
                    real_fclose = (real_fclose_fn)dlsym(RTLD_NEXT, "fclose");
                }
                calls++;
                if (calls == 2) {
                    errno = EIO;
                    return EOF;
                }
                return real_fclose(stream);
            }
            """
        ),
        encoding="ascii",
    )
    build = subprocess.run(
        [
            compiler,
            "-shared",
            "-fPIC",
            "-std=c17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-o",
            str(shim),
            str(shim_source),
            "-ldl",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert build.returncode == 0, build.stderr

    before = tmp_path / "before.snapshot"
    after = tmp_path / "after.snapshot"
    before.write_bytes(b"changed.key=old\n")
    after.write_bytes(b"changed.key=new\n")

    result = run_sysdiff(
        sysdiff_bin,
        "compare",
        before,
        after,
        env={"LD_PRELOAD": str(shim)},
    )

    assert result.returncode == 2
    assert result.stdout == b""
    assert str(after).encode() in result.stderr
    assert b"close failed" in result.stderr
    assert b"Input/output error" in result.stderr


def test_late_duplicate_after_reallocation_fails_atomically(sysdiff_bin, tmp_path):
    """Cleanup must reclaim transferred entries after several array growths."""

    before = tmp_path / "before.snapshot"
    after = tmp_path / "after-with-duplicate.snapshot"
    records = [f"entry.{index:03d}=value\n" for index in range(257)]
    after.write_text("".join(records) + "entry.128=duplicate\n", encoding="ascii")
    before.write_text("changed.key=old\n", encoding="ascii")

    result = run_sysdiff(sysdiff_bin, "compare", before, after)

    assert result.returncode == 2
    assert result.stdout == b""
    assert str(after).encode() in result.stderr
    assert b"duplicate key: entry.128" in result.stderr
    assert_terminal_safe_diagnostics(result.stderr)


def test_source_guards_dynamic_size_arithmetic_before_allocation():
    """C storage growth must check additions and multiplications first."""

    source = SRC.read_text(encoding="ascii")

    assert "static bool checked_size_add" in source
    assert "static bool checked_size_mul" in source
    assert "!checked_size_add(len, 1, &allocation_size)" in source
    assert "!checked_size_mul(new_cap, sizeof(line[0])," in source
    assert "!checked_size_mul(new_cap, sizeof(snapshot->items[0])," in source
    assert "realloc(line, new_cap * sizeof(line[0]))" not in source
    assert "realloc(snapshot->items, new_cap * sizeof(snapshot->items[0]))" not in source


def _load_malformed_fuzz_module():
    spec = importlib.util.spec_from_file_location(
        "sysdiff_malformed_fuzz_for_craftsmanship", MALFORMED_FUZZ
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_malformed_fuzz_runner_honors_valgrind_environment(tmp_path, monkeypatch):
    """The direct hostile corpus route must not bypass requested Valgrind."""

    fuzz = _load_malformed_fuzz_module()
    fake_valgrind = tmp_path / "valgrind"
    invocation = tmp_path / "valgrind-argv"
    fake_valgrind.write_text(
        textwrap.dedent(
            """
            #!/usr/bin/env python3
            import os
            from pathlib import Path
            import sys

            Path(os.environ["FAKE_VALGRIND_INVOCATION"]).write_text(
                "\\n".join(sys.argv[1:]), encoding="ascii"
            )
            raise SystemExit(2)
            """
        ).lstrip(),
        encoding="ascii",
    )
    fake_valgrind.chmod(0o755)
    monkeypatch.setenv("SYSDIFF_UNDER_VALGRIND", "1")
    monkeypatch.setenv("FAKE_VALGRIND_INVOCATION", str(invocation))
    monkeypatch.setenv(
        "PATH",
        f"{fake_valgrind.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    )

    case = fuzz.FuzzCase(
        case_id="craftsmanship_valgrind_route",
        category="hostile_bytes",
        payload=b"bad key=value\n",
        timeout_s=2.0,
    )
    binary = tmp_path / "sysdiff-placeholder"
    binary.write_text("#!/bin/sh\nexit 2\n", encoding="ascii")
    binary.chmod(0o755)
    case_workdir = tmp_path / "case-work"
    case_workdir.mkdir()

    (
        command,
        _before,
        _after,
        returncode,
        stdout,
        _stderr,
        timed_out,
    ) = fuzz.run_compare_case(binary, case, case_workdir)

    assert not timed_out
    assert returncode == 2
    assert stdout == b""
    assert invocation.is_file(), f"Valgrind was not invoked: {command!r}"
    argv = invocation.read_text(encoding="ascii").splitlines()
    assert "--error-exitcode=99" in argv
    assert str(binary) in argv
    assert "compare" in argv


def test_makefile_retains_strict_and_memory_quality_routes():
    """The quality target must retain strict, sanitizer, and Valgrind floors."""

    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "STRICT_WARNINGS := -std=c17 -Wall -Wextra -Wpedantic -Werror" in makefile
    for target in (
        "$(MAKE) gcc-strict",
        "$(MAKE) clang-strict",
        "$(MAKE) format-check",
        "$(MAKE) clang-tidy-check",
        "$(MAKE) cppcheck-check",
        "$(MAKE) clang-analyzer-check",
        "$(MAKE) test-sanitize",
        "$(MAKE) test-valgrind",
    ):
        assert target in makefile
    assert "SYSDIFF_UNDER_VALGRIND=1" in makefile
    assert "--error-exitcode=99" in makefile


def test_makefile_valgrind_route_instruments_shell_and_pytest_corpus():
    """The dedicated memory route must cover both direct test callers."""

    makefile = MAKEFILE.read_text(encoding="utf-8")
    shell = (ROOT / "tests" / "test_sysdiff.sh").read_text(encoding="utf-8")
    recipe = makefile.split("test-valgrind:", 1)[1].split("\n\n", 1)[0]

    assert recipe.count("SYSDIFF_UNDER_VALGRIND=1") == 2
    assert "./tests/test_sysdiff.sh" in recipe
    assert "$(PYTEST_NO_CACHE) tests/ -q" in recipe
    assert "valgrind --quiet --error-exitcode=99" in shell
    assert "--leak-check=full" in shell
