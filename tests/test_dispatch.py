"""Tests for the dispatch module."""

import pytest

from organvm_engine.dispatch.payload import create_payload, validate_payload
from organvm_engine.dispatch.router import route_event
from organvm_engine.dispatch.cascade import plan_cascade
from organvm_engine.registry.loader import load_registry
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


class TestPayload:
    def test_create_payload(self):
        p = create_payload(
            event="theory.published",
            source_organ="ORGAN-I",
            target_organ="ORGAN-II",
            payload_data={"message": "New theory"},
        )
        assert p["event"] == "theory.published"
        assert p["source"]["organ"] == "ORGAN-I"
        assert "dispatch_id" in p["metadata"]

    def test_validate_valid(self):
        p = create_payload(
            event="theory.published",
            source_organ="ORGAN-I",
            target_organ="ORGAN-II",
            payload_data={},
        )
        ok, errors = validate_payload(p)
        assert ok
        assert errors == []

    def test_validate_missing_event(self):
        ok, errors = validate_payload({
            "source": {"organ": "ORGAN-I"},
            "target": {"organ": "ORGAN-II"},
            "payload": {},
        })
        assert not ok
        assert any("event" in e for e in errors)

    def test_validate_bad_event_format(self):
        ok, errors = validate_payload({
            "event": "nodotshere",
            "source": {"organ": "ORGAN-I"},
            "target": {"organ": "ORGAN-II"},
            "payload": {},
        })
        assert not ok


class TestRouter:
    def test_route_finds_subscribers(self):
        seeds = {
            "organvm-ii-poiesis/art-repo": {
                "subscriptions": [
                    {"event": "theory.published", "source": "ORGAN-I", "action": "Create art"},
                ]
            },
            "organvm-iii-ergon/product": {
                "subscriptions": [
                    {"event": "other.event", "source": "ORGAN-II", "action": "Build product"},
                ]
            },
        }
        matches = route_event("theory.published", "ORGAN-I", seeds)
        assert len(matches) == 1
        assert matches[0]["repo"] == "organvm-ii-poiesis/art-repo"

    def test_route_no_match(self):
        seeds = {
            "organvm-ii-poiesis/art-repo": {
                "subscriptions": [
                    {"event": "other.event", "source": "ORGAN-IV", "action": "Do nothing"},
                ]
            },
        }
        matches = route_event("theory.published", "ORGAN-I", seeds)
        assert len(matches) == 0


class TestCascade:
    def test_cascade_from_dependency(self):
        registry = load_registry(FIXTURES / "registry-minimal.json")
        # recursive-engine is depended on by ontological-framework and metasystem-master
        order = plan_cascade(registry, "organvm-i-theoria/recursive-engine")
        assert len(order) >= 1
