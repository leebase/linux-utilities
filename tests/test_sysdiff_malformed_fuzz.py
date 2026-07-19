"""Bounded deterministic malformed-snapshot fuzz regressions for sysdiff.

Corpus cases are derived from the format-1 grammar implemented by
``src/sysdiff.c`` (``key=value`` records, comment/blank skipping, key syntax,
duplicate rejection, and the line/entry/byte limits). Generation is fully
deterministic: hand-authored fixtures use fixed bytes, and any pseudorandom
mutation uses ``CORPUS_SEED`` with a stable case catalog.

Every ``sysdiff compare`` invocation has a finite timeout. Failures report
case id, seed, paths, command, exit status, timeout/signal/sanitizer flags,
and a regeneration recipe. The executable is compiled into a temporary
directory (never ``build/``) and temporary inputs are cleaned up by pytest.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Sequence

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "sysdiff.c"

# Documented fixed seed for every pseudorandom mutation in this module.
CORPUS_SEED = 0x5FED1FF5

# Parser limits from src/sysdiff.c — keep in sync with production defines.
MAX_LINE_BYTES = 65536
MAX_SNAPSHOT_ENTRIES = 65536

DEFAULT_CASE_TIMEOUT_S = 5.0
LARGE_CASE_TIMEOUT_S = 60.0

VALID_COMPANION = (
    b"# companion\n"
    b"sysdiff.snapshot_version=1\n"
    b"os.id=debian\n"
    b"kernel.release=6.1.0-21-amd64\n"
)

VALID_BASE = (
    b"# valid base snapshot\n"
    b"sysdiff.snapshot_version=1\n"
    b"os.id=debian\n"
    b"os.version_id=12\n"
    b"kernel.release=6.1.0-21-amd64\n"
    b"package.openssh-server.version=1:9.2p1-2+deb12u3\n"
    b"service.ssh.enabled=true\n"
    b"service.ssh.active=\n"
    b"file./etc/ssh/sshd_config.sha256=3b7f6fdeadbeef\n"
    b"same.keep=stable\n"
)

ASAN_RE = re.compile(rb"ERROR:\s*AddressSanitizer", re.IGNORECASE)
UBSAN_RE = re.compile(
    rb"(runtime error:|UndefinedBehaviorSanitizer|SUMMARY:\s*UndefinedBehaviorSanitizer)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FuzzCase:
    """One required-rejection malformed compare case."""

    case_id: str
    payload: bytes
    category: str
    seed: int | None = None
    timeout_s: float = DEFAULT_CASE_TIMEOUT_S
    malformed_side: str = "before"  # "before" or "after"


def _line_prefix_pad(prefix: bytes, total: int, fill: bytes = b"x") -> bytes:
    if len(prefix) > total:
        raise ValueError(f"prefix longer than total ({len(prefix)} > {total})")
    return prefix + (fill * (total - len(prefix)))


def _hand_authored_cases() -> list[FuzzCase]:
    """Fixed-byte cases covering each rejection category from the contract."""

    cases: list[FuzzCase] = []

    # --- Truncation (grammar-derived cuts of otherwise-valid prefixes) ---
    cases.append(
        FuzzCase(
            case_id="trunc_mid_key_no_separator",
            category="truncation",
            payload=b"sysdiff.snapshot_version=1\nos.i",
        )
    )
    cases.append(
        FuzzCase(
            case_id="trunc_after_valid_line_mid_key",
            category="truncation",
            payload=VALID_BASE + b"package.openssh-server.ver",
        )
    )
    cases.append(
        FuzzCase(
            case_id="trunc_cut_before_equals",
            category="truncation",
            payload=b"sysdiff.snapshot_version=1\nkernel.release",
        )
    )
    cases.append(
        FuzzCase(
            case_id="trunc_only_comment_then_orphan_bytes",
            category="truncation",
            payload=b"# header\nnot-a-record",
        )
    )

    # --- Invalid lengths / delimiters ---
    cases.append(
        FuzzCase(
            case_id="delim_missing_equals",
            category="invalid_delimiter",
            payload=b"valid.key=ok\nmissing separator line\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="delim_empty_key",
            category="invalid_delimiter",
            payload=b"=value-only\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="delim_cr_only_line_ending_as_key_byte",
            category="invalid_delimiter",
            # Bare CR is not stripped without LF; it remains key data.
            payload=b"bad\rkey=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="key_no_dot",
            category="invalid_delimiter",
            payload=b"nodot=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="key_leading_slash",
            category="invalid_delimiter",
            payload=b"/starts.with.slash=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="key_trailing_dot",
            category="invalid_delimiter",
            payload=b"ends.with.dot.=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="key_consecutive_dots",
            category="invalid_delimiter",
            payload=b"path..traversal=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="key_space_inside",
            category="invalid_delimiter",
            payload=b"bad key=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="key_tab_inside",
            category="invalid_delimiter",
            payload=b"bad\tkey=value\n",
        )
    )

    # --- Corrupted records ---
    cases.append(
        FuzzCase(
            case_id="corrupt_duplicate_keys",
            category="corrupted_record",
            payload=b"dup.key=first\ndup.key=second\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="corrupt_insert_double_dot_in_valid_key",
            category="corrupted_record",
            payload=b"file./etc/ssh/sshd..config.sha256=abc\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="corrupt_replace_equals_with_colon",
            category="corrupted_record",
            payload=b"os.id:debian\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="corrupt_after_valid_prefix_bad_key",
            category="corrupted_record",
            payload=VALID_BASE + b"package.bad name.version=1\n",
            malformed_side="after",
        )
    )

    # --- Embedded hostile bytes ---
    cases.append(
        FuzzCase(
            case_id="hostile_embedded_nul_in_value",
            category="hostile_bytes",
            payload=b"valid.key=before\0after\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="hostile_embedded_nul_in_key",
            category="hostile_bytes",
            payload=b"va\0lid.key=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="hostile_esc_in_key",
            category="hostile_bytes",
            payload=b"bad\x1b.key=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="hostile_del_in_key",
            category="hostile_bytes",
            payload=b"bad\x7f.key=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="hostile_ff_in_key",
            category="hostile_bytes",
            payload=b"bad\xff.key=value\n",
        )
    )
    cases.append(
        FuzzCase(
            case_id="hostile_nul_after_valid_lines",
            category="hostile_bytes",
            payload=VALID_BASE + b"extra.key=ok\0tail\n",
        )
    )

    # --- Boundary-size cases meaningful for the real parser ---
    at_line = _line_prefix_pad(b"a.key=", MAX_LINE_BYTES, b"x")
    cases.append(
        FuzzCase(
            case_id="boundary_line_over_limit_by_one",
            category="boundary",
            payload=at_line + b"y\n",
            timeout_s=LARGE_CASE_TIMEOUT_S,
        )
    )
    # Content at the LF limit is valid; force rejection via an extra non-newline
    # byte before the terminator (parser allows one extra then rejects).
    cases.append(
        FuzzCase(
            case_id="boundary_line_too_long_without_newline_guard",
            category="boundary",
            # read_line rejects when non-newline length reaches MAX+1 before '\n'.
            payload=_line_prefix_pad(b"z.key=", MAX_LINE_BYTES + 1, b"Z") + b"\n",
            timeout_s=LARGE_CASE_TIMEOUT_S,
        )
    )
    # Entry limit + 1: keep this one case; it matches SYSDIFF_MAX_SNAPSHOT_ENTRIES.
    over_entries = b"".join(f"k.{i}=v\n".encode("ascii") for i in range(MAX_SNAPSHOT_ENTRIES + 1))
    cases.append(
        FuzzCase(
            case_id="boundary_entry_over_limit_by_one",
            category="boundary",
            payload=over_entries,
            timeout_s=LARGE_CASE_TIMEOUT_S,
        )
    )

    return cases


def _seeded_mutation_cases(seed: int = CORPUS_SEED) -> list[FuzzCase]:
    """Small fixed-budget mutation set derived from VALID_BASE."""

    rng = Random(seed)
    cases: list[FuzzCase] = []

    # Truncations at deterministic offsets into VALID_BASE.
    trunc_offsets = sorted(
        {8, 17, 33, 48, len(VALID_BASE) // 3, (2 * len(VALID_BASE)) // 3, len(VALID_BASE) - 5}
    )
    for index, offset in enumerate(trunc_offsets):
        cut = VALID_BASE[:offset]
        # Skip cuts that remain valid (comments-only / complete records only).
        if _looks_like_valid_snapshot(cut):
            continue
        cases.append(
            FuzzCase(
                case_id=f"seeded_trunc_{index:02d}_off{offset}",
                category="truncation",
                payload=cut,
                seed=seed,
            )
        )

    # Byte-flip / insert / delete mutations with a fixed budget.
    mutation_budget = 12
    for index in range(mutation_budget):
        data = bytearray(VALID_BASE)
        kind = index % 4
        if kind == 0:
            # Flip one printable key/value byte toward a hostile control.
            pos = rng.randrange(len(data))
            data[pos] = rng.choice([0x00, 0x1B, 0x7F, 0xFF, ord(" "), ord("\t")])
            label = f"seeded_flip_{index:02d}_pos{pos}"
        elif kind == 1:
            # Delete the first '=' so a record loses its separator.
            eq = data.find(ord("="))
            if eq < 0:
                continue
            del data[eq]
            label = f"seeded_del_eq_{index:02d}_pos{eq}"
        elif kind == 2:
            # Insert consecutive dots into a key region before the first '='.
            eq = data.find(ord("="))
            if eq < 2:
                continue
            insert_at = rng.randrange(1, eq)
            data[insert_at:insert_at] = b".."
            label = f"seeded_insert_dots_{index:02d}_at{insert_at}"
        else:
            # Append a corrupted trailing record with illegal key bytes.
            data.extend(b"evil key\x00=nope\n")
            label = f"seeded_append_hostile_{index:02d}"

        payload = bytes(data)
        if _looks_like_valid_snapshot(payload):
            continue
        cases.append(
            FuzzCase(
                case_id=label,
                category="seeded_mutation",
                payload=payload,
                seed=seed,
                malformed_side="before" if index % 2 == 0 else "after",
            )
        )

    return cases


def _looks_like_valid_snapshot(data: bytes) -> bool:
    """Conservative filter so seeded cases stay in the rejection corpus.

    Mirrors the production grammar closely enough to drop accidental still-valid
    mutations without re-implementing the full C parser.
    """

    if b"\0" in data:
        return False

    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines = lines[:-1]

    seen: set[bytes] = set()
    for raw in lines:
        # Match parse_snapshot: strip one trailing CR only when the line ended in LF.
        line = raw[:-1] if raw.endswith(b"\r") else raw
        stripped = line.lstrip(b" \t")
        if stripped == b"" or stripped.startswith(b"#"):
            continue
        if b"=" not in line:
            return False
        key, _value = line.split(b"=", 1)
        if not _is_valid_key_bytes(key):
            return False
        if key in seen:
            return False
        seen.add(key)
        if len(line) > MAX_LINE_BYTES:
            return False
    return True


def _is_valid_key_bytes(key: bytes) -> bool:
    if not key or key.startswith(b"/") or key.endswith(b"."):
        return False
    allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-/"
    saw_dot = False
    for i, ch in enumerate(key):
        if ch not in allowed:
            return False
        if ch == ord("."):
            saw_dot = True
            if i > 0 and key[i - 1] == ord("."):
                return False
    return saw_dot


def build_corpus(seed: int = CORPUS_SEED) -> list[FuzzCase]:
    """Return the full bounded corpus in stable case_id order."""

    combined = _hand_authored_cases() + _seeded_mutation_cases(seed)
    by_id = {case.case_id: case for case in combined}
    return [by_id[key] for key in sorted(by_id)]


CORPUS: tuple[FuzzCase, ...] = tuple(build_corpus())


def _category_ids(category: str) -> set[str]:
    return {case.case_id for case in CORPUS if case.category == category}


@pytest.fixture(scope="session")
def sysdiff_bin():
    """Compile sysdiff into a temporary directory (never workspace build/)."""

    env_bin = os.environ.get("SYSDIFF_BIN")
    if env_bin:
        binary = Path(env_bin)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            pytest.fail(f"SYSDIFF_BIN is not an executable file: {env_bin}")
        yield binary
        return

    build_dir = Path(tempfile.mkdtemp(prefix="sysdiff-fuzz-build."))
    binary = build_dir / "sysdiff"
    try:
        subprocess.run(
            [
                os.environ.get("CC", "cc"),
                "-std=c17",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                "-o",
                str(binary),
                str(SRC),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        yield binary
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


@pytest.fixture
def corpus_workdir():
    """Per-test temporary directory for snapshot bytes; always cleaned up."""

    workdir = Path(tempfile.mkdtemp(prefix="sysdiff-fuzz-case."))
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _reproduction_block(
    case: FuzzCase,
    *,
    cmd: Sequence[str],
    before: Path,
    after: Path,
    returncode: int | None,
    timed_out: bool,
    signal_status: str | None,
    sanitizer: str | None,
    stdout: bytes,
    stderr: bytes,
) -> str:
    return (
        "malformed-snapshot fuzz regression failure\n"
        f"  case_id: {case.case_id}\n"
        f"  category: {case.category}\n"
        f"  seed: {case.seed if case.seed is not None else 'none (hand-authored)'}\n"
        f"  corpus_seed: {CORPUS_SEED:#x}\n"
        f"  malformed_side: {case.malformed_side}\n"
        f"  timeout_s: {case.timeout_s}\n"
        f"  before: {before}\n"
        f"  after: {after}\n"
        f"  command: {' '.join(cmd)}\n"
        f"  returncode: {returncode}\n"
        f"  timed_out: {timed_out}\n"
        f"  signal: {signal_status}\n"
        f"  sanitizer: {sanitizer}\n"
        f"  stdout_len: {len(stdout)}\n"
        f"  stderr_len: {len(stderr)}\n"
        f"  stderr_preview: {stderr[:500]!r}\n"
        "  regenerate: PYTHONHASHSEED=0 python3 -c "
        "\"from tests.test_sysdiff_malformed_fuzz import build_corpus, CORPUS_SEED; "
        f"c=[x for x in build_corpus(CORPUS_SEED) if x.case_id=='{case.case_id}'][0]; "
        f"open('/tmp/{case.case_id}.snapshot','wb').write(c.payload)\"\n"
    )


def _signal_name(returncode: int | None) -> str | None:
    if returncode is None or returncode >= 0:
        return None
    return f"signal_{-returncode}"


def _sanitizer_hit(stderr: bytes) -> str | None:
    if ASAN_RE.search(stderr):
        return "AddressSanitizer"
    if UBSAN_RE.search(stderr):
        return "UndefinedBehaviorSanitizer"
    return None


def run_compare_case(
    binary: Path, case: FuzzCase, workdir: Path
) -> tuple[list[str], Path, Path, int | None, bytes, bytes, bool]:
    companion = workdir / "companion.snapshot"
    malformed = workdir / f"{case.case_id}.snapshot"
    companion.write_bytes(VALID_COMPANION)
    malformed.write_bytes(case.payload)

    if case.malformed_side == "before":
        before, after = malformed, companion
    else:
        before, after = companion, malformed

    cmd = [str(binary), "compare", str(before), str(after)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=case.timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            cmd,
            before,
            after,
            None,
            exc.stdout or b"",
            exc.stderr or b"",
            True,
        )
    return cmd, before, after, result.returncode, result.stdout, result.stderr, False


def assert_required_rejection(
    binary: Path, case: FuzzCase, workdir: Path
) -> None:
    cmd, before, after, returncode, stdout, stderr, timed_out = run_compare_case(
        binary, case, workdir
    )
    signal_status = _signal_name(returncode)
    sanitizer = _sanitizer_hit(stderr)
    detail = _reproduction_block(
        case,
        cmd=cmd,
        before=before,
        after=after,
        returncode=returncode,
        timed_out=timed_out,
        signal_status=signal_status,
        sanitizer=sanitizer,
        stdout=stdout,
        stderr=stderr,
    )

    if timed_out:
        pytest.fail(f"hang past per-case timeout\n{detail}")
    if signal_status is not None:
        pytest.fail(f"fatal signal / crash\n{detail}")
    if sanitizer is not None:
        pytest.fail(f"sanitizer failure ({sanitizer})\n{detail}")
    if returncode in (0, 1):
        pytest.fail(
            f"malformed input accepted (exit {returncode}); rejection required\n{detail}"
        )
    if returncode != 2:
        pytest.fail(f"expected exit status 2\n{detail}")
    if stdout != b"":
        pytest.fail(f"compare stdout must be empty on rejection\n{detail}")


def test_corpus_is_bounded_deterministic_and_categorized():
    assert 10 <= len(CORPUS) <= 80, f"unexpected corpus size: {len(CORPUS)}"
    assert [case.case_id for case in CORPUS] == sorted(case.case_id for case in CORPUS)
    assert build_corpus(CORPUS_SEED) == build_corpus(CORPUS_SEED)
    assert tuple(c.case_id for c in build_corpus(CORPUS_SEED)) == tuple(
        c.case_id for c in CORPUS
    )

    required_categories = {
        "truncation",
        "invalid_delimiter",
        "corrupted_record",
        "hostile_bytes",
        "boundary",
        "seeded_mutation",
    }
    present = {case.category for case in CORPUS}
    missing = required_categories - present
    assert not missing, f"missing categories: {sorted(missing)}"

    # Stable seed metadata on every seeded case.
    for case in CORPUS:
        if case.category == "seeded_mutation" or case.case_id.startswith("seeded_"):
            assert case.seed == CORPUS_SEED


@pytest.mark.parametrize("case", CORPUS, ids=[case.case_id for case in CORPUS])
def test_malformed_snapshot_rejected_safely(sysdiff_bin, corpus_workdir, case: FuzzCase):
    assert_required_rejection(sysdiff_bin, case, corpus_workdir)


def test_valid_snapshot_pair_is_accepted(sysdiff_bin, corpus_workdir):
    """Positive control: well-formed snapshots must still be accepted.

    Without this, a reject-everything regression would leave the malformed
    corpus green because every case only asserts exit status 2.
    """

    before = corpus_workdir / "valid-before.snapshot"
    after = corpus_workdir / "valid-after.snapshot"
    before.write_bytes(VALID_BASE)
    after.write_bytes(VALID_COMPANION)
    cmd = [str(sysdiff_bin), "compare", str(before), str(after)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=DEFAULT_CASE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            "valid snapshot pair timed out\n"
            f"  cmd: {cmd!r}\n"
            f"  stdout: {(exc.stdout or b'')!r}\n"
            f"  stderr: {(exc.stderr or b'')!r}"
        )
    signal_status = _signal_name(result.returncode)
    sanitizer = _sanitizer_hit(result.stderr)
    if signal_status is not None:
        pytest.fail(
            f"valid pair crashed ({signal_status})\n"
            f"  cmd: {cmd!r}\n"
            f"  stderr: {result.stderr!r}"
        )
    if sanitizer is not None:
        pytest.fail(
            f"valid pair hit {sanitizer}\n"
            f"  cmd: {cmd!r}\n"
            f"  stderr: {result.stderr!r}"
        )
    if result.returncode not in (0, 1):
        pytest.fail(
            f"valid pair rejected (exit {result.returncode}); acceptance required\n"
            f"  cmd: {cmd!r}\n"
            f"  stdout: {result.stdout!r}\n"
            f"  stderr: {result.stderr!r}"
        )
    if result.stdout == b"":
        pytest.fail(
            "valid pair produced empty stdout; expected diff or 'no changes'\n"
            f"  cmd: {cmd!r}\n"
            f"  exit: {result.returncode}\n"
            f"  stderr: {result.stderr!r}"
        )


def test_corpus_covers_contract_attack_surface():
    """Sanity check that representative attack families are present by id."""

    ids = {case.case_id for case in CORPUS}
    assert "trunc_mid_key_no_separator" in ids
    assert "delim_missing_equals" in ids
    assert "delim_empty_key" in ids
    assert "corrupt_duplicate_keys" in ids
    assert "hostile_embedded_nul_in_value" in ids
    assert "boundary_line_over_limit_by_one" in ids
    assert "boundary_entry_over_limit_by_one" in ids
    assert any(case_id.startswith("seeded_") for case_id in ids)
    assert _category_ids("truncation")
    assert _category_ids("boundary")
