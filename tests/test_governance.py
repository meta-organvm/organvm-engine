"""Tests for the governance module."""

import json
from pathlib import Path

import pytest

from organvm_engine.governance.state_machine import check_transition, get_valid_transitions
from organvm_engine.governance.dependency_graph import validate_dependencies
from organvm_engine.governance.rules import load_governance_rules
from organvm_engine.registry.loader import load_registry

FIXTURES = Path(__file__).parent / "fixtures"


class TestStateMachine:
    def test_local_to_candidate(self):
        ok, msg = check_transition("LOCAL", "CANDIDATE")
        assert ok

    def test_local_to_graduated_invalid(self):
        ok, msg = check_transition("LOCAL", "GRADUATED")
        assert not ok

    def test_archived_is_terminal(self):
        ok, msg = check_transition("ARCHIVED", "LOCAL")
        assert not ok

    def test_get_valid_transitions(self):
        valid = get_valid_transitions("CANDIDATE")
        assert "PUBLIC_PROCESS" in valid
        assert "LOCAL" in valid
        assert "ARCHIVED" in valid

    def test_unknown_state(self):
        ok, msg = check_transition("BOGUS", "LOCAL")
        assert not ok


class TestDependencyGraph:
    def test_valid_graph_passes(self, registry):
        result = validate_dependencies(registry)
        assert result.passed
        assert result.total_edges > 0

    def test_detects_self_dep(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{
                        "name": "self-ref",
                        "org": "organvm-i-theoria",
                        "dependencies": ["organvm-i-theoria/self-ref"],
                    }]
                }
            }
        }
        result = validate_dependencies(registry)
        assert len(result.self_deps) == 1

    def test_detects_back_edge(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{
                        "name": "theory",
                        "org": "organvm-i-theoria",
                        "dependencies": ["organvm-ii-poiesis/art"],
                    }]
                },
                "ORGAN-II": {
                    "repositories": [{
                        "name": "art",
                        "org": "organvm-ii-poiesis",
                        "dependencies": [],
                    }]
                },
            }
        }
        result = validate_dependencies(registry)
        assert len(result.back_edges) == 1

    def test_detects_cycle(self):
        registry = {
            "organs": {
                "ORGAN-IV": {
                    "repositories": [
                        {
                            "name": "a",
                            "org": "organvm-iv-taxis",
                            "dependencies": ["organvm-iv-taxis/b"],
                        },
                        {
                            "name": "b",
                            "org": "organvm-iv-taxis",
                            "dependencies": ["organvm-iv-taxis/a"],
                        },
                    ]
                }
            }
        }
        result = validate_dependencies(registry)
        assert len(result.cycles) > 0


class TestRules:
    def test_load_test_rules(self):
        rules = load_governance_rules(FIXTURES / "governance-rules-test.json")
        assert rules["version"] == "1.0"
        assert rules["dependency_rules"]["no_circular_dependencies"] is True
