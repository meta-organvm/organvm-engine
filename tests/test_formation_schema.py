"""Tests for the formation.schema.json (INST-FORMATION FORM-001 through FORM-007).

Validates:
  - The schema itself is valid JSON Schema (Draft 2020-12)
  - Valid formation declarations pass validation
  - Required fields are enforced
  - Enum constraints work correctly
  - Pattern constraints work correctly

All operations are read-only or use tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schema-definitions" / "schemas" / "formation.schema.json"
)


@pytest.fixture
def formation_schema() -> dict:
    """Load the formation schema."""
    if not SCHEMA_PATH.is_file():
        pytest.skip(f"formation.schema.json not found at {SCHEMA_PATH}")
    with SCHEMA_PATH.open() as f:
        return json.load(f)


def _minimal_valid_formation() -> dict:
    """Return a minimal valid formation declaration."""
    return {
        "formation_id": "FORM-001",
        "formation_name": "Theoria Generator",
        "formation_type": "GENERATOR",
        "host_organ_primary": "ORGAN-I",
        "metaphysical_role": "Produces foundational theory",
        "question": "What is the system's ontological ground?",
        "signal_inputs": ["ONT_FRAGMENT"],
        "signal_outputs": ["RULE_PROPOSAL", "STATE_MODEL"],
        "maturity_level": "R3",
        "promotion_state": "PUBLIC_PROCESS",
        "exit_modes": ["archive", "migrate"],
    }


def _validate(data: dict, schema: dict) -> list[str]:
    """Return validation error messages."""
    validator = jsonschema.Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(data)]


# ---------------------------------------------------------------------------
# Schema self-validation
# ---------------------------------------------------------------------------

class TestSchemaValidity:
    def test_schema_is_valid_json(self):
        """The schema file must be valid JSON."""
        if not SCHEMA_PATH.is_file():
            pytest.skip("formation.schema.json not found")
        with SCHEMA_PATH.open() as f:
            schema = json.load(f)
        assert isinstance(schema, dict)

    def test_schema_is_valid_json_schema(self, formation_schema):
        """The schema must be a valid Draft 2020-12 JSON Schema."""
        jsonschema.Draft202012Validator.check_schema(formation_schema)

    def test_schema_has_required_metadata(self, formation_schema):
        assert formation_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "title" in formation_schema
        assert "description" in formation_schema
        assert "$id" in formation_schema


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------

class TestValidFormation:
    def test_minimal_valid_passes(self, formation_schema):
        data = _minimal_valid_formation()
        errors = _validate(data, formation_schema)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_full_valid_passes(self, formation_schema):
        data = _minimal_valid_formation()
        data.update({
            "host_organ_secondary": ["ORGAN-II", "META-ORGANVM"],
            "scope_boundary": {
                "includes": ["organvm-engine", "organvm-ontologia"],
                "excludes": ["intake"],
            },
            "feedback_policy": "Accept from downstream organs only",
            "feedfront_policy": "Emit to ORGAN-II and ORGAN-III",
            "clock_source": "event-driven",
            "attenuation_policy": "Logarithmic dampening at boundary",
            "max_active_horizon_days": 90,
            "migration_target_classes": ["TRANSFORMER", "SYNTHESIZER"],
        })
        errors = _validate(data, formation_schema)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_all_formation_types_valid(self, formation_schema):
        types = [
            "GENERATOR", "TRANSFORMER", "ROUTER",
            "RESERVOIR", "INTERFACE", "LABORATORY", "SYNTHESIZER",
        ]
        for ft in types:
            data = _minimal_valid_formation()
            data["formation_type"] = ft
            errors = _validate(data, formation_schema)
            assert errors == [], f"Type {ft} should be valid: {errors}"

    def test_all_exit_modes_valid(self, formation_schema):
        data = _minimal_valid_formation()
        data["exit_modes"] = ["migrate", "archive", "synthesize", "dissolve"]
        errors = _validate(data, formation_schema)
        assert errors == [], f"All exit modes should be valid: {errors}"

    def test_all_maturity_levels_valid(self, formation_schema):
        for level in range(9):
            data = _minimal_valid_formation()
            data["maturity_level"] = f"R{level}"
            errors = _validate(data, formation_schema)
            assert errors == [], f"R{level} should be valid: {errors}"

    def test_all_promotion_states_valid(self, formation_schema):
        states = [
            "INCUBATOR", "LOCAL", "CANDIDATE",
            "PUBLIC_PROCESS", "GRADUATED", "ARCHIVED",
        ]
        for state in states:
            data = _minimal_valid_formation()
            data["promotion_state"] = state
            errors = _validate(data, formation_schema)
            assert errors == [], f"State {state} should be valid: {errors}"


# ---------------------------------------------------------------------------
# Required field enforcement
# ---------------------------------------------------------------------------

class TestRequiredFields:
    REQUIRED = [
        "formation_id",
        "formation_name",
        "formation_type",
        "host_organ_primary",
        "metaphysical_role",
        "question",
        "signal_inputs",
        "signal_outputs",
        "maturity_level",
        "promotion_state",
        "exit_modes",
    ]

    def test_empty_object_fails(self, formation_schema):
        errors = _validate({}, formation_schema)
        assert len(errors) > 0

    @pytest.mark.parametrize("field", REQUIRED)
    def test_missing_required_field(self, field, formation_schema):
        data = _minimal_valid_formation()
        del data[field]
        errors = _validate(data, formation_schema)
        assert len(errors) > 0, f"Missing '{field}' should fail validation"


# ---------------------------------------------------------------------------
# Enum constraints
# ---------------------------------------------------------------------------

class TestEnumConstraints:
    def test_invalid_formation_type(self, formation_schema):
        data = _minimal_valid_formation()
        data["formation_type"] = "INVALID_TYPE"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_invalid_promotion_state(self, formation_schema):
        data = _minimal_valid_formation()
        data["promotion_state"] = "BOGUS"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_invalid_exit_mode(self, formation_schema):
        data = _minimal_valid_formation()
        data["exit_modes"] = ["invalid_mode"]
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_empty_exit_modes_fails(self, formation_schema):
        data = _minimal_valid_formation()
        data["exit_modes"] = []
        errors = _validate(data, formation_schema)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Pattern constraints
# ---------------------------------------------------------------------------

class TestPatternConstraints:
    def test_formation_id_valid_pattern(self, formation_schema):
        data = _minimal_valid_formation()
        data["formation_id"] = "FORM-007"
        errors = _validate(data, formation_schema)
        assert errors == []

    def test_formation_id_invalid_pattern(self, formation_schema):
        data = _minimal_valid_formation()
        data["formation_id"] = "INVALID-001"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_formation_id_no_leading_zeros_required(self, formation_schema):
        data = _minimal_valid_formation()
        data["formation_id"] = "FORM-999"
        errors = _validate(data, formation_schema)
        assert errors == []

    def test_maturity_level_valid_pattern(self, formation_schema):
        data = _minimal_valid_formation()
        data["maturity_level"] = "R0"
        errors = _validate(data, formation_schema)
        assert errors == []

    def test_maturity_level_invalid_pattern(self, formation_schema):
        data = _minimal_valid_formation()
        data["maturity_level"] = "R9"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_maturity_level_no_prefix(self, formation_schema):
        data = _minimal_valid_formation()
        data["maturity_level"] = "3"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Additional properties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_property_rejected(self, formation_schema):
        data = _minimal_valid_formation()
        data["unknown_field"] = "should fail"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_scope_boundary_rejects_extra_keys(self, formation_schema):
        data = _minimal_valid_formation()
        data["scope_boundary"] = {
            "includes": ["a"],
            "excludes": ["b"],
            "extra": "not allowed",
        }
        errors = _validate(data, formation_schema)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# Type constraints
# ---------------------------------------------------------------------------

class TestTypeConstraints:
    def test_signal_inputs_must_be_array(self, formation_schema):
        data = _minimal_valid_formation()
        data["signal_inputs"] = "not an array"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_max_active_horizon_must_be_integer(self, formation_schema):
        data = _minimal_valid_formation()
        data["max_active_horizon_days"] = "ninety"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_max_active_horizon_must_be_positive(self, formation_schema):
        data = _minimal_valid_formation()
        data["max_active_horizon_days"] = 0
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_host_organ_secondary_must_be_array(self, formation_schema):
        data = _minimal_valid_formation()
        data["host_organ_secondary"] = "not an array"
        errors = _validate(data, formation_schema)
        assert len(errors) > 0

    def test_formation_name_must_be_nonempty(self, formation_schema):
        data = _minimal_valid_formation()
        data["formation_name"] = ""
        errors = _validate(data, formation_schema)
        assert len(errors) > 0
