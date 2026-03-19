"""Tests for governance self-validation (SPEC-003, INV-000-002).

Implements: AX-000-002 DRIFT (engine #15)

Covers:
  - validate_rules_schema() structural validation
  - validate_rules_schema() with JSON Schema validation
  - load_governance_rules() self-validation on load
  - GOVERNANCE_AUDIT event emission on load

All file operations use tmp_path — never writes to production paths.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organvm_engine.events.spine import EventSpine, EventType
from organvm_engine.governance.rules import (
    _REQUIRED_KEYS,
    load_governance_rules,
    validate_rules_schema,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helper: write governance-rules.json to tmp_path
# ---------------------------------------------------------------------------

def _write_valid_rules(tmp_path: Path) -> Path:
    """Write a minimal valid governance-rules.json and return its path."""
    rules = {
        "version": "1.0",
        "dependency_rules": {
            "max_transitive_depth": 4,
            "no_circular_dependencies": True,
            "no_back_edges": True,
        },
        "promotion_rules": {},
        "state_machine": {
            "states": ["LOCAL", "CANDIDATE", "ARCHIVED"],
            "transitions": {
                "LOCAL": ["CANDIDATE", "ARCHIVED"],
                "CANDIDATE": ["ARCHIVED"],
                "ARCHIVED": [],
            },
        },
        "audit_thresholds": {
            "critical": {"missing_readme": True},
            "warning": {"stale_repo_days": 90},
        },
    }
    path = tmp_path / "governance-rules.json"
    path.write_text(json.dumps(rules))
    return path


def _write_rules_dict(tmp_path: Path, rules: dict) -> Path:
    """Write an arbitrary rules dict and return its path."""
    path = tmp_path / "governance-rules.json"
    path.write_text(json.dumps(rules))
    return path


# ---------------------------------------------------------------------------
# validate_rules_schema — structural validation (no schema_path)
# ---------------------------------------------------------------------------

class TestValidateRulesStructural:
    def test_valid_rules_pass(self, tmp_path):
        path = _write_valid_rules(tmp_path)
        valid, errors = validate_rules_schema(path)
        assert valid
        assert errors == []

    def test_fixture_rules_pass(self):
        valid, errors = validate_rules_schema(FIXTURES / "governance-rules-test.json")
        assert valid
        assert errors == []

    def test_missing_file_fails(self, tmp_path):
        valid, errors = validate_rules_schema(tmp_path / "nonexistent.json")
        assert not valid
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_invalid_json_fails(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json!!")
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("Invalid JSON" in e for e in errors)

    def test_non_object_root_fails(self, tmp_path):
        path = tmp_path / "array.json"
        path.write_text(json.dumps([1, 2, 3]))
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("JSON object" in e for e in errors)

    def test_missing_version_fails(self, tmp_path):
        rules = {
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("version" in e for e in errors)

    def test_missing_dependency_rules_fails(self, tmp_path):
        rules = {
            "version": "1.0",
            "promotion_rules": {},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("dependency_rules" in e for e in errors)

    def test_missing_state_machine_fails(self, tmp_path):
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {},
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("state_machine" in e for e in errors)

    def test_missing_multiple_keys_reports_all(self, tmp_path):
        rules = {"version": "1.0"}
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        # Should report all missing keys, not just the first
        assert len(errors) >= 3

    def test_wrong_type_version_fails(self, tmp_path):
        rules = {
            "version": 42,
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("str" in e and "version" in e for e in errors)

    def test_wrong_type_state_machine_fails(self, tmp_path):
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": "not a dict",
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("state_machine" in e for e in errors)

    def test_state_machine_missing_transitions_fails(self, tmp_path):
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"states": ["LOCAL"]},
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("transitions" in e for e in errors)

    def test_state_machine_transitions_wrong_type_fails(self, tmp_path):
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"transitions": "not a dict"},
            "audit_thresholds": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert not valid
        assert any("transitions must be a dict" in e for e in errors)

    def test_extra_keys_do_not_cause_failure(self, tmp_path):
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
            "extra_key": "allowed",
            "dictums": {},
        }
        path = _write_rules_dict(tmp_path, rules)
        valid, errors = validate_rules_schema(path)
        assert valid

    def test_required_keys_constant_has_five_entries(self):
        assert len(_REQUIRED_KEYS) == 5
        assert "version" in _REQUIRED_KEYS
        assert "state_machine" in _REQUIRED_KEYS


# ---------------------------------------------------------------------------
# validate_rules_schema — JSON Schema validation
# ---------------------------------------------------------------------------

class TestValidateRulesWithSchema:
    def test_valid_rules_with_schema(self, tmp_path):
        rules_path = _write_valid_rules(tmp_path)
        schema_path = (
            Path(__file__).resolve().parent.parent.parent
            / "schema-definitions" / "schemas" / "governance-rules.schema.json"
        )
        if not schema_path.is_file():
            pytest.skip("governance-rules.schema.json not found")
        valid, errors = validate_rules_schema(rules_path, schema_path=schema_path)
        assert valid, f"Errors: {errors}"

    def test_invalid_rules_with_schema(self, tmp_path):
        rules = {"not_valid": True}
        rules_path = _write_rules_dict(tmp_path, rules)
        schema_path = (
            Path(__file__).resolve().parent.parent.parent
            / "schema-definitions" / "schemas" / "governance-rules.schema.json"
        )
        if not schema_path.is_file():
            pytest.skip("governance-rules.schema.json not found")
        valid, errors = validate_rules_schema(rules_path, schema_path=schema_path)
        assert not valid
        assert len(errors) > 0

    def test_missing_schema_file_fails(self, tmp_path):
        rules_path = _write_valid_rules(tmp_path)
        valid, errors = validate_rules_schema(
            rules_path,
            schema_path=tmp_path / "nonexistent-schema.json",
        )
        assert not valid
        assert any("Schema file not found" in e for e in errors)

    def test_malformed_schema_file_fails(self, tmp_path):
        rules_path = _write_valid_rules(tmp_path)
        bad_schema = tmp_path / "bad-schema.json"
        bad_schema.write_text("not json")
        valid, errors = validate_rules_schema(rules_path, schema_path=bad_schema)
        assert not valid
        assert any("Invalid JSON in schema" in e for e in errors)


# ---------------------------------------------------------------------------
# load_governance_rules — self-validation on load
# ---------------------------------------------------------------------------

class TestLoadGovernanceRulesSelfValidation:
    def test_loads_valid_rules(self, tmp_path):
        path = _write_valid_rules(tmp_path)
        rules = load_governance_rules(path)
        assert rules["version"] == "1.0"
        assert "dependency_rules" in rules

    def test_loads_fixture_rules(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        assert "state_machine" in rules
        assert "audit_thresholds" in rules

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_governance_rules(tmp_path / "no-such-file.json")

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{nope")
        with pytest.raises(json.JSONDecodeError):
            load_governance_rules(path)

    def test_structurally_invalid_still_loads(self, tmp_path):
        """Rules with missing keys still load — validation logs a warning."""
        rules = {"version": "1.0", "extra": True}
        path = _write_rules_dict(tmp_path, rules)
        result = load_governance_rules(path)
        assert result["version"] == "1.0"


# ---------------------------------------------------------------------------
# Event emission on load
# ---------------------------------------------------------------------------

class TestGovernanceAuditEvent:
    def test_emits_governance_audit_on_load(self, tmp_path):
        rules_path = _write_valid_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        load_governance_rules(rules_path, spine_path=spine_path)

        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.GOVERNANCE_AUDIT)
        assert len(events) == 1
        evt = events[0]
        assert evt.entity_uid == "governance-rules"
        assert evt.payload["action"] == "load"
        assert evt.payload["valid"] is True
        assert evt.payload["error_count"] == 0
        assert evt.source_spec == "SPEC-003"

    def test_emits_event_even_on_validation_failure(self, tmp_path):
        rules = {"version": "1.0"}  # Missing required keys
        rules_path = _write_rules_dict(tmp_path, rules)
        spine_path = tmp_path / "events.jsonl"
        load_governance_rules(rules_path, spine_path=spine_path)

        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.GOVERNANCE_AUDIT)
        assert len(events) == 1
        evt = events[0]
        assert evt.payload["valid"] is False
        assert evt.payload["error_count"] > 0

    def test_no_spine_path_does_not_crash(self, tmp_path):
        rules_path = _write_valid_rules(tmp_path)
        # No spine_path — event goes to default location, but that's blocked
        # by conftest.py production path guard. Should not raise.
        rules = load_governance_rules(rules_path)
        assert rules["version"] == "1.0"

    def test_event_records_rules_path(self, tmp_path):
        rules_path = _write_valid_rules(tmp_path)
        spine_path = tmp_path / "events.jsonl"
        load_governance_rules(rules_path, spine_path=spine_path)

        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.GOVERNANCE_AUDIT)
        assert str(rules_path) in events[0].payload["rules_path"]
