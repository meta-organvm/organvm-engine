"""Load and query governance-rules.json.

Implements: SPEC-003, INV-000-002
Resolves: AX-000-002 DRIFT (engine #15)

Governance must validate itself before applying. The validate_rules_schema()
function checks structural integrity (required top-level keys) and optionally
validates against a JSON Schema. On successful load, a GOVERNANCE_AUDIT event
is emitted to the EventSpine.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from organvm_engine.paths import governance_rules_path as _default_rules_path

logger = logging.getLogger(__name__)

# Required top-level keys for structural validation
_REQUIRED_KEYS: tuple[str, ...] = (
    "version",
    "dependency_rules",
    "promotion_rules",
    "state_machine",
    "audit_thresholds",
)


def validate_rules_schema(
    rules_path: Path | str,
    schema_path: Path | str | None = None,
) -> tuple[bool, list[str]]:
    """Validate governance-rules.json structure and optionally against JSON Schema.

    If schema_path is provided, validates the rules file against that JSON Schema
    using the jsonschema library. If schema_path is None, performs structural
    validation: checks that all required top-level keys are present and that
    each has the expected type.

    Args:
        rules_path: Path to the governance-rules.json file.
        schema_path: Optional path to a JSON Schema file for full validation.

    Returns:
        (valid, errors) tuple. valid is True when no errors found.
    """
    path = Path(rules_path)
    errors: list[str] = []

    # Load the rules file
    if not path.is_file():
        return False, [f"Rules file not found: {path}"]

    try:
        with path.open() as f:
            rules = json.load(f)
    except json.JSONDecodeError as exc:
        return False, [f"Invalid JSON in rules file: {exc}"]

    if not isinstance(rules, dict):
        return False, ["Rules file root must be a JSON object"]

    # Schema-based validation (when schema_path provided)
    if schema_path is not None:
        return _validate_against_schema(rules, Path(schema_path), errors)

    # Structural validation (no schema provided)
    return _validate_structure(rules, errors)


def _validate_against_schema(
    rules: dict[str, Any],
    schema_path: Path,
    errors: list[str],
) -> tuple[bool, list[str]]:
    """Validate rules dict against a JSON Schema file."""
    if not schema_path.is_file():
        return False, [f"Schema file not found: {schema_path}"]

    try:
        import jsonschema
    except ImportError:
        return False, ["jsonschema library not installed — cannot validate against schema"]

    try:
        with schema_path.open() as f:
            schema = json.load(f)
    except json.JSONDecodeError as exc:
        return False, [f"Invalid JSON in schema file: {exc}"]

    validator = jsonschema.Draft202012Validator(schema)
    for err in validator.iter_errors(rules):
        errors.append(err.message)

    return len(errors) == 0, errors


def _validate_structure(
    rules: dict[str, Any],
    errors: list[str],
) -> tuple[bool, list[str]]:
    """Structural validation: required keys and basic type checks."""
    # Check required top-level keys
    for key in _REQUIRED_KEYS:
        if key not in rules:
            errors.append(f"Missing required key: '{key}'")

    # Type checks for keys that are present
    _check_type(rules, "version", str, errors)
    _check_type(rules, "dependency_rules", dict, errors)
    _check_type(rules, "promotion_rules", dict, errors)
    _check_type(rules, "state_machine", dict, errors)
    _check_type(rules, "audit_thresholds", dict, errors)

    # State machine sub-structure
    sm = rules.get("state_machine")
    if isinstance(sm, dict):
        if "transitions" not in sm:
            errors.append("state_machine missing 'transitions' key")
        elif not isinstance(sm["transitions"], dict):
            errors.append("state_machine.transitions must be a dict")

    return len(errors) == 0, errors


def _check_type(
    data: dict[str, Any],
    key: str,
    expected: type,
    errors: list[str],
) -> None:
    """Append an error if data[key] exists but has wrong type."""
    if key in data and not isinstance(data[key], expected):
        errors.append(
            f"'{key}' must be {expected.__name__}, got {type(data[key]).__name__}",
        )


def _emit_governance_load_event(
    rules_path: Path,
    valid: bool,
    error_count: int,
    spine_path: Path | str | None = None,
) -> None:
    """Emit a GOVERNANCE_AUDIT event on rules load. Fail-safe: never raises."""
    try:
        from organvm_engine.events.spine import EventSpine, EventType

        kwargs: dict[str, Any] = {}
        if spine_path is not None:
            kwargs["path"] = spine_path

        spine = EventSpine(**kwargs)
        spine.emit(
            event_type=EventType.GOVERNANCE_AUDIT,
            entity_uid="governance-rules",
            payload={
                "action": "load",
                "rules_path": str(rules_path),
                "valid": valid,
                "error_count": error_count,
            },
            source_spec="SPEC-003",
            actor="governance",
        )
    except Exception:
        logger.debug("EventSpine emission failed during rules load (non-fatal)", exc_info=True)


def load_governance_rules(
    path: Path | str | None = None,
    *,
    spine_path: Path | str | None = None,
) -> dict:
    """Load governance-rules.json with self-validation on load.

    Validates the rules file structurally before returning. Emits a
    GOVERNANCE_AUDIT event to the EventSpine on every load attempt.

    Args:
        path: Path to rules file. Defaults to corpus repo location.
        spine_path: Optional path for the EventSpine JSONL file.

    Returns:
        Parsed governance rules dict.

    Raises:
        FileNotFoundError: If the rules file does not exist.
        json.JSONDecodeError: If the rules file is not valid JSON.
        ValueError: If the rules file fails structural validation.
    """
    rules_path = Path(path) if path else _default_rules_path()

    # Self-validate before loading
    valid, errors = validate_rules_schema(rules_path)

    # Emit event regardless of outcome
    _emit_governance_load_event(rules_path, valid, len(errors), spine_path)

    if not valid:
        msg = f"Governance rules failed self-validation: {'; '.join(errors)}"
        logger.warning(msg)
        # If the file doesn't exist or isn't valid JSON, let the original
        # error propagate naturally from the open/load below
        if errors and errors[0].startswith("Rules file not found"):
            raise FileNotFoundError(errors[0])

    with rules_path.open() as f:
        return json.load(f)


def get_dependency_rules(rules: dict) -> dict:
    """Extract dependency rules section."""
    return rules.get("dependency_rules", {})


def get_promotion_rules(rules: dict) -> dict:
    """Extract promotion rules section."""
    return rules.get("promotion_rules", {})


def get_audit_thresholds(rules: dict) -> dict:
    """Extract audit threshold section."""
    return rules.get("audit_thresholds", {})


def get_organ_requirements(rules: dict, organ_key: str) -> dict:
    """Get requirements for a specific organ."""
    return rules.get("organ_requirements", {}).get(organ_key, {})


def get_dictums(rules: dict) -> dict:
    """Extract the dictums section from governance rules."""
    return rules.get("dictums", {})
