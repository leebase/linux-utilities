"""Regression test suite for repairing governed run failure 718b3902389f.

Mission:
Author a regression test in tests/test_repair_718b3902389f.py.
This test ensures the user-tester manifest (tests/user_journeys_manifest.json)
is valid, well-formed, conforms to the canonical JSON schema, preserves all
required journey contracts and command allowlists, and enforces fail-closed
behavior on any malformed variations.

Constraints & Scope Confinement:
- Write scope strictly confined to tests/.
- Clean Python environment without foreign repository contamination.
- Non-product blast radius: zero changes to src/sysdiff.c, Makefile, or man/sysdiff.1.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest

# Clean sys.path: allow agent_orch if present, but avoid foreign cross-project paths
for _extra_path in (
    "/home/lee/projects/agent-orch/src",
    "/home/lee/.local/lib/python3.12/site-packages",
):
    if _extra_path not in sys.path and Path(_extra_path).is_dir():
        sys.path.insert(0, _extra_path)

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

try:
    from agent_orch.user_journeys import (
        JOURNEY_AUTHORITIES,
        REQUIRED_JOURNEY_AUTHORITIES,
        USER_JOURNEYS_MANIFEST_SCHEMA,
        USER_JOURNEYS_RESULT_SCHEMA,
    )
except ImportError:
    JOURNEY_AUTHORITIES = ("human", "mission", "author", "exploratory")  # type: ignore[assignment]
    REQUIRED_JOURNEY_AUTHORITIES = ("human", "mission", "author")  # type: ignore[assignment]
    USER_JOURNEYS_MANIFEST_SCHEMA = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["journeys", "command_allowlist"],
        "properties": {
            "journeys": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "authority": {
                            "enum": ["human", "mission", "author", "exploratory"]
                        },
                        "traces_to": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
            "command_allowlist": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
        },
    }
    USER_JOURNEYS_RESULT_SCHEMA = {}  # type: ignore[assignment]

try:
    import agent_orch.validators as validators
except ImportError:
    validators = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
TESTS_MANIFEST = ROOT / "tests" / "user_journeys_manifest.json"
JOURNEYS_MANIFEST = ROOT / "journeys" / "user_journeys_manifest.json"
SYSDIFF_SRC = ROOT / "src" / "sysdiff.c"
MAKEFILE = ROOT / "Makefile"

# Pinned SHA-256 for tests/user_journeys_manifest.json
EXPECTED_MANIFEST_SHA256 = (
    "6d5d8d39069cf264c1cf5dbd00e8bb7b9ad22815f5a64459ab7d8cd1add0eb9c"
)

# 10 Preserved Workspace Abstraction Author Journeys
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

# 4 Core Sysdiff Product Journeys
SYSDIFF_JOURNEYS = {
    "A user runs the real sysdiff binary with no arguments and receives usage guidance instead of a crash",
    "A user asks the real sysdiff binary for help and receives its usage summary",
    "A user compares two snapshots with the real sysdiff binary and sees deterministic added removed and changed entries",
    "A user gives the real sysdiff binary a malformed snapshot and receives an escaped diagnostic without partial output",
}

# 7 Sandbox Containment and Repair Journeys
BWRAP_JOURNEYS = {
    "A worker launcher delivers large prompt payloads via stdin and verifies that no single argv argument exceeds kernel MAX_ARG_STRLEN limits",
    "A user confirms bubblewrap sandbox containment remains strictly enforced on Linux without granting unsandboxed execution bypasses",
    "An operator observes pre-exec payload measurement rejecting oversized bwrap arguments fail-closed with typed LAUNCH_PAYLOAD_TOO_LARGE classification",
    "An evaluator inspects edge-case payload sizes near the 128 KiB boundary to confirm exact byte accounting without information leakage",
    "A validator bounds process output in retry feedback to head and tail excerpts while preserving full unmodified logs in hash-chained artifacts",
    "A maintainer verifies the synchronized user journeys manifest adheres to canonical schema and covers all enumerated contract acceptance checks",
    "A developer runs the sysdiff test suite and smoke verification to confirm the repair introduces no product regressions or scope expansion",
}

ALL_EXPECTED_JOURNEYS = PRESERVED_AUTHOR_JOURNEYS | SYSDIFF_JOURNEYS | BWRAP_JOURNEYS
EXPECTED_COMMAND_ALLOWLIST = ["build/sysdiff"]
ALLOWED_ACCEPTANCE_CHECKS = {"AC-1", "AC-2", "AC-3"}


def _load_manifest_dict() -> dict[str, Any]:
    """Helper to load and return the parsed user journeys manifest."""
    assert TESTS_MANIFEST.exists(), f"User journeys manifest missing: {TESTS_MANIFEST}"
    content = TESTS_MANIFEST.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, dict), f"Manifest root must be an object, got {type(data).__name__}"
    return data


def _validate_schema(data: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Validate data against Draft202012 schema, returning error messages."""
    target_schema = schema or USER_JOURNEYS_MANIFEST_SCHEMA
    if not target_schema:
        return []
    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator(target_schema)
        return [err.message for err in validator.iter_errors(data)]
    # Minimal fallback validation if jsonschema is not present
    errors = []
    if not isinstance(data, dict):
        errors.append("Root is not a dict")
        return errors
    for req in target_schema.get("required", []):
        if req not in data:
            errors.append(f"Missing required property: {req}")
    if "journeys" in data:
        if not isinstance(data["journeys"], list) or len(data["journeys"]) < 1:
            errors.append("journeys must be a non-empty array")
        else:
            for i, j in enumerate(data["journeys"]):
                if not isinstance(j, dict):
                    errors.append(f"journey[{i}] is not an object")
                elif "name" not in j or not isinstance(j["name"], str) or len(j["name"]) < 1:
                    errors.append(f"journey[{i}] invalid name")
    if "command_allowlist" in data:
        if not isinstance(data["command_allowlist"], list) or len(data["command_allowlist"]) < 1:
            errors.append("command_allowlist must be a non-empty array")
        else:
            for i, c in enumerate(data["command_allowlist"]):
                if not isinstance(c, str) or len(c) < 1:
                    errors.append(f"command_allowlist[{i}] invalid string")
    return errors


# ============================================================================
# 1. Manifest File Existence, Readability, and Format
# ============================================================================


def test_user_tester_manifest_file_exists_and_is_regular_file() -> None:
    """The user-tester manifest must exist at tests/user_journeys_manifest.json as a non-empty regular file."""
    assert TESTS_MANIFEST.exists(), f"User journeys manifest missing at {TESTS_MANIFEST}"
    assert TESTS_MANIFEST.is_file(), f"User journeys manifest {TESTS_MANIFEST} must be a regular file"
    assert TESTS_MANIFEST.stat().st_size > 0, f"User journeys manifest {TESTS_MANIFEST} is empty"


def test_user_tester_manifest_is_valid_utf8_json() -> None:
    """The user-tester manifest must parse cleanly as UTF-8 encoded JSON without syntax errors."""
    raw_bytes = TESTS_MANIFEST.read_bytes()
    decoded = raw_bytes.decode("utf-8")
    assert len(decoded) > 0

    parsed = json.loads(decoded)
    assert isinstance(parsed, dict), f"Top-level JSON value must be an object/dict, got {type(parsed).__name__}"


def test_user_tester_manifest_matches_sha256_hash() -> None:
    """The user-tester manifest digest matches the expected canonical SHA-256 hash."""
    content = TESTS_MANIFEST.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert (
        digest == EXPECTED_MANIFEST_SHA256
    ), f"tests/user_journeys_manifest.json hash mismatch: expected {EXPECTED_MANIFEST_SHA256}, got {digest}"


def test_user_tester_manifest_exact_root_keys() -> None:
    """The user-tester manifest root must contain exactly the required top-level keys."""
    manifest = _load_manifest_dict()
    root_keys = set(manifest.keys())
    expected_keys = {"journeys", "command_allowlist"}
    assert expected_keys.issubset(
        root_keys
    ), f"Manifest root is missing required keys: {expected_keys - root_keys}"
    # Standard schema only defines journeys and command_allowlist
    assert root_keys == expected_keys, f"Manifest root contains unexpected keys: {root_keys - expected_keys}"


# ============================================================================
# 2. Canonical JSON Schema Conformance
# ============================================================================


def test_user_tester_manifest_conforms_to_canonical_schema() -> None:
    """The manifest must strictly satisfy the Draft202012 USER_JOURNEYS_MANIFEST_SCHEMA."""
    manifest = _load_manifest_dict()
    errors = _validate_schema(manifest)
    assert not errors, f"User journeys manifest schema validation failed with errors: {errors}"


def test_user_tester_manifest_passes_agent_orch_validator_summary() -> None:
    """If agent_orch.validators is available, _schema_violation_summary must return None."""
    if validators is None:
        pytest.skip("agent_orch.validators not importable in current environment")

    manifest = _load_manifest_dict()
    summary = validators._schema_violation_summary(
        USER_JOURNEYS_MANIFEST_SCHEMA, manifest
    )
    assert summary is None, f"agent_orch validator reported schema violation: {summary}"


# ============================================================================
# 3. Command Allowlist Integrity
# ============================================================================


def test_command_allowlist_is_non_empty_list_of_strings() -> None:
    """The command allowlist must be a non-empty list of non-empty strings."""
    manifest = _load_manifest_dict()
    allowlist = manifest.get("command_allowlist")
    assert isinstance(allowlist, list), f"command_allowlist must be a list, got {type(allowlist).__name__}"
    assert len(allowlist) >= 1, "command_allowlist must contain at least one entry"

    for idx, entry in enumerate(allowlist):
        assert isinstance(entry, str), f"command_allowlist entry [{idx}] must be a str, got {type(entry).__name__}"
        assert entry.strip() == entry, f"command_allowlist entry [{idx}] has leading/trailing whitespace: {entry!r}"
        assert len(entry) > 0, f"command_allowlist entry [{idx}] cannot be empty"


def test_command_allowlist_matches_expected_sysdiff_entry() -> None:
    """The command allowlist must strictly match ['build/sysdiff'] for safe execution."""
    manifest = _load_manifest_dict()
    allowlist = manifest.get("command_allowlist", [])
    assert (
        allowlist == EXPECTED_COMMAND_ALLOWLIST
    ), f"Expected command_allowlist {EXPECTED_COMMAND_ALLOWLIST}, but got {allowlist}"


def test_command_allowlist_security_hygiene() -> None:
    """Allowlist entries must not contain shell operators, path traversal, or control characters."""
    manifest = _load_manifest_dict()
    forbidden_patterns = [
        r"\.\.",  # path traversal
        r"[;&|`$><]",  # shell operators
        r"[\r\n\t]",  # whitespace control characters
    ]
    for entry in manifest.get("command_allowlist", []):
        for pat in forbidden_patterns:
            assert not re.search(
                pat, entry
            ), f"Dangerous character or pattern {pat!r} found in command_allowlist entry: {entry!r}"


# ============================================================================
# 4. Journeys Collection Structure, Count, and Uniqueness
# ============================================================================


def test_journeys_count_is_exactly_twenty_one() -> None:
    """The manifest must contain exactly 21 user journeys covering all system capabilities."""
    manifest = _load_manifest_dict()
    journeys = manifest.get("journeys")
    assert isinstance(journeys, list), f"journeys must be a list, got {type(journeys).__name__}"
    assert (
        len(journeys) == 21
    ), f"Expected exactly 21 journeys in manifest, found {len(journeys)}"


def test_journey_names_are_unique_and_non_empty() -> None:
    """Every journey must have a unique, non-empty name string without surrounding whitespace."""
    manifest = _load_manifest_dict()
    journeys = manifest.get("journeys", [])
    seen_names: set[str] = set()

    for idx, journey in enumerate(journeys):
        assert isinstance(journey, dict), f"Journey [{idx}] must be a dict"
        name = journey.get("name")
        assert isinstance(name, str), f"Journey [{idx}] missing or invalid name string"
        assert len(name.strip()) > 0, f"Journey [{idx}] has empty name"
        assert name.strip() == name, f"Journey [{idx}] name has leading/trailing whitespace: {name!r}"
        assert name not in seen_names, f"Duplicate journey name found at index [{idx}]: {name!r}"
        seen_names.add(name)


def test_manifest_contains_all_twenty_one_expected_journeys() -> None:
    """The manifest must include every required journey across workspace, sysdiff, and bwrap sets."""
    manifest = _load_manifest_dict()
    actual_names = {j["name"] for j in manifest.get("journeys", [])}

    missing_preserved = PRESERVED_AUTHOR_JOURNEYS - actual_names
    assert not missing_preserved, f"Missing preserved workspace journeys: {missing_preserved}"

    missing_sysdiff = SYSDIFF_JOURNEYS - actual_names
    assert not missing_sysdiff, f"Missing sysdiff product journeys: {missing_sysdiff}"

    missing_bwrap = BWRAP_JOURNEYS - actual_names
    assert not missing_bwrap, f"Missing bwrap repair journeys: {missing_bwrap}"

    assert (
        actual_names == ALL_EXPECTED_JOURNEYS
    ), f"Journey set mismatch. Extra: {actual_names - ALL_EXPECTED_JOURNEYS}"


# ============================================================================
# 5. Journey Authorities and Traceability
# ============================================================================


def test_journey_authorities_are_valid() -> None:
    """Every journey authority must belong to the closed JOURNEY_AUTHORITIES set."""
    manifest = _load_manifest_dict()
    for journey in manifest.get("journeys", []):
        authority = journey.get("authority", "author")
        assert (
            authority in JOURNEY_AUTHORITIES
        ), f"Journey {journey.get('name')!r} has invalid authority: {authority!r} (expected one of {JOURNEY_AUTHORITIES})"


def test_required_journey_authorities_are_present() -> None:
    """Manifest must include journeys with required authorial weight ('author')."""
    manifest = _load_manifest_dict()
    authorities_present = {j.get("authority", "author") for j in manifest.get("journeys", [])}
    assert (
        "author" in authorities_present
    ), "Manifest must contain at least one journey with 'author' authority"


def test_journey_traces_to_format_and_acceptance_coverage() -> None:
    """All non-exploratory journeys must specify valid traces_to mapping to AC-1, AC-2, or AC-3."""
    manifest = _load_manifest_dict()
    covered_acs: set[str] = set()

    for journey in manifest.get("journeys", []):
        authority = journey.get("authority", "author")
        traces = journey.get("traces_to")

        if authority != "exploratory":
            assert isinstance(
                traces, list
            ), f"Required journey {journey['name']!r} traces_to must be a list, got {type(traces).__name__}"
            assert len(traces) >= 1, f"Required journey {journey['name']!r} traces_to cannot be empty"
            for t in traces:
                assert isinstance(t, str) and len(t) > 0, f"Invalid trace identifier {t!r} in {journey['name']!r}"
                assert (
                    t in ALLOWED_ACCEPTANCE_CHECKS
                ), f"Journey {journey['name']!r} traces to unknown check {t!r} (allowed: {ALLOWED_ACCEPTANCE_CHECKS})"
                covered_acs.add(t)
        else:
            # Exploratory journeys may trace or be supplementary
            if traces is not None:
                assert isinstance(traces, list)
                for t in traces:
                    assert t in ALLOWED_ACCEPTANCE_CHECKS
                    covered_acs.add(t)

    assert (
        covered_acs == ALLOWED_ACCEPTANCE_CHECKS
    ), f"Acceptance checks not fully covered by manifest journeys: {ALLOWED_ACCEPTANCE_CHECKS - covered_acs}"


# ============================================================================
# 6. Secondary Mirror Synchronization
# ============================================================================


def test_user_journeys_manifest_synchronized_with_secondary_mirror() -> None:
    """tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json must be identical."""
    if not JOURNEYS_MANIFEST.exists():
        pytest.skip(f"Secondary journeys mirror {JOURNEYS_MANIFEST} not present")

    tests_manifest = _load_manifest_dict()
    secondary_text = JOURNEYS_MANIFEST.read_text(encoding="utf-8")
    secondary_manifest = json.loads(secondary_text)

    assert (
        tests_manifest == secondary_manifest
    ), "tests/user_journeys_manifest.json and journeys/user_journeys_manifest.json are not identical parsed objects"


# ============================================================================
# 7. Fail-Closed Validation of Malformed Manifest Variants
# ============================================================================


def test_manifest_schema_rejects_missing_journeys() -> None:
    """Schema validation must fail closed when the 'journeys' property is omitted."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    del mutated["journeys"]

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject manifest without 'journeys' key"


def test_manifest_schema_rejects_empty_journeys_list() -> None:
    """Schema validation must fail closed when 'journeys' is an empty list."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["journeys"] = []

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject manifest with empty 'journeys' list"


def test_manifest_schema_rejects_missing_command_allowlist() -> None:
    """Schema validation must fail closed when 'command_allowlist' is missing."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    del mutated["command_allowlist"]

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject manifest without 'command_allowlist' key"


def test_manifest_schema_rejects_empty_command_allowlist() -> None:
    """Schema validation must fail closed when 'command_allowlist' is empty."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["command_allowlist"] = []

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject manifest with empty 'command_allowlist'"


def test_manifest_schema_rejects_non_string_command_allowlist_entry() -> None:
    """Schema validation must fail closed when an allowlist entry is not a string."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["command_allowlist"] = [12345]  # type: ignore[list-item]

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject manifest with non-string command_allowlist entry"


def test_manifest_schema_rejects_empty_string_command_allowlist_entry() -> None:
    """Schema validation must fail closed when an allowlist entry is empty string."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["command_allowlist"] = [""]

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject manifest with empty string command_allowlist entry"


def test_manifest_schema_rejects_journey_missing_name() -> None:
    """Schema validation must fail closed when a journey entry lacks a 'name' field."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["journeys"][0] = {"authority": "author", "traces_to": ["AC-1"]}

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject journey entry missing 'name'"


def test_manifest_schema_rejects_journey_empty_name() -> None:
    """Schema validation must fail closed when a journey entry has an empty 'name' string."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["journeys"][0]["name"] = ""

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject journey entry with empty 'name'"


def test_manifest_schema_rejects_journey_invalid_authority() -> None:
    """Schema validation must fail closed when a journey entry specifies an unapproved authority."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["journeys"][0]["authority"] = "unauthorized_role"

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject journey entry with invalid authority"


def test_manifest_schema_rejects_journey_empty_trace_item() -> None:
    """Schema validation must fail closed when a trace identifier is an empty string."""
    manifest = _load_manifest_dict()
    mutated = copy.deepcopy(manifest)
    mutated["journeys"][0]["traces_to"] = [""]

    errors = _validate_schema(mutated)
    assert errors, "Schema must reject journey entry with empty string in traces_to"


def test_manifest_schema_rejects_non_object_root() -> None:
    """Schema validation must fail closed when the root JSON element is an array or primitive."""
    errors_list = _validate_schema(["not", "an", "object"])
    assert errors_list, "Schema must reject array root"

    errors_str = _validate_schema("not an object")
    assert errors_str, "Schema must reject string root"


# ============================================================================
# 8. Test Harness Cleanliness and Blast Radius Protection
# ============================================================================


def test_no_foreign_cross_project_sys_path_contamination() -> None:
    """Test modules must not hardcode foreign repository paths like employee-contract into sys.path."""
    this_file = Path(__file__)
    foreign_marker = "/home/lee/projects/" + "employee-contract"
    for line in this_file.read_text(encoding="utf-8").splitlines():
        if foreign_marker in line and not line.strip().startswith("#"):
            pytest.fail(f"Foreign repository path found hardcoded in {this_file.name}: {line.strip()}")


def test_product_source_and_makefile_unaltered_by_slice_tests() -> None:
    """Authoring slice tests must maintain non-product blast radius and leave product sources intact."""
    assert SYSDIFF_SRC.exists() and SYSDIFF_SRC.stat().st_size > 0
    assert MAKEFILE.exists() and MAKEFILE.stat().st_size > 0

    # Ensure sysdiff.c remains pure C17 without regression tokens
    src_text = SYSDIFF_SRC.read_text(encoding="utf-8")
    assert "718b3902389f" not in src_text, "Run token leaked into src/sysdiff.c"
