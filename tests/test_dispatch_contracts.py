"""Tests for contract-aware dispatch — payload validation and verified routing."""

import pytest

from organvm_engine.dispatch.payload import (
    create_payload,
    validate_payload,
    validate_payload_with_contract,
)
from organvm_engine.dispatch.router import DispatchReceipt, route_event, route_event_verified


class TestValidatePayloadWithContract:
    def test_valid_theory_published(self):
        payload = create_payload(
            event="theory.published",
            source_organ="ORGAN-I",
            target_organ="ORGAN-II",
            payload_data={
                "artifact_id": "art-001",
                "title": "Formal Logic in Organ Pipes",
                "source_repo": "styx",
            },
        )
        ok, errors, found = validate_payload_with_contract(payload)
        assert ok
        assert found
        assert errors == []

    def test_theory_published_missing_field(self):
        payload = create_payload(
            event="theory.published",
            source_organ="ORGAN-I",
            target_organ="ORGAN-II",
            payload_data={"artifact_id": "art-001"},
        )
        ok, errors, found = validate_payload_with_contract(payload)
        assert not ok
        assert found
        assert any("Missing required field" in e for e in errors)

    def test_theory_published_empty_string(self):
        payload = create_payload(
            event="theory.published",
            source_organ="ORGAN-I",
            target_organ="ORGAN-II",
            payload_data={
                "artifact_id": "",
                "title": "ok",
                "source_repo": "styx",
            },
        )
        ok, errors, found = validate_payload_with_contract(payload)
        assert not ok
        assert any("Validator failed" in e for e in errors)

    def test_unknown_event_passes_structure(self):
        payload = create_payload(
            event="custom.event",
            source_organ="ORGAN-I",
            target_organ="ORGAN-II",
            payload_data={"whatever": True},
        )
        ok, errors, found = validate_payload_with_contract(payload)
        assert ok
        assert not found  # no contract registered

    def test_structural_failure_before_contract_check(self):
        """If structural validation fails, contract check is skipped."""
        ok, errors, found = validate_payload_with_contract({"bad": "payload"})
        assert not ok
        assert not found

    def test_essay_published_wrong_type(self):
        payload = create_payload(
            event="essay.published",
            source_organ="ORGAN-V",
            target_organ="ORGAN-VII",
            payload_data={
                "title": "My Essay",
                "slug": "my-essay",
                "word_count": "not-an-int",  # should be int
                "category": "discourse",
            },
        )
        ok, errors, found = validate_payload_with_contract(payload)
        assert not ok
        assert found
        assert any("expected int" in e for e in errors)

    def test_product_release_valid(self):
        payload = create_payload(
            event="product.release",
            source_organ="ORGAN-III",
            target_organ="ORGAN-VII",
            payload_data={
                "version": "1.0.0",
                "repo": "my-product",
                "changelog_url": "https://example.com/changelog",
            },
        )
        ok, errors, found = validate_payload_with_contract(payload)
        assert ok
        assert found


class TestRouteEventVerified:
    def test_basic_routing_works(self):
        seeds = {
            "org/consumer": {
                "org": "org",
                "repo": "consumer",
                "subscriptions": [
                    {"event": "theory.published", "source": "ORGAN-I", "action": "ingest"},
                ],
            },
        }
        receipt = route_event_verified(
            "theory.published",
            "ORGAN-I",
            seeds,
            payload_data={"artifact_id": "x", "title": "y", "source_repo": "z"},
        )
        assert receipt.match_count == 1
        assert receipt.contract_verified
        assert receipt.contract_found

    def test_routing_with_bad_payload(self):
        seeds = {
            "org/consumer": {
                "org": "org",
                "repo": "consumer",
                "subscriptions": [
                    {"event": "theory.published", "source": "ORGAN-I", "action": "ingest"},
                ],
            },
        }
        receipt = route_event_verified(
            "theory.published",
            "ORGAN-I",
            seeds,
            payload_data={"artifact_id": "x"},  # missing fields
        )
        assert receipt.match_count == 1  # routing still works
        assert not receipt.contract_verified
        assert len(receipt.contract_errors) > 0

    def test_routing_without_payload(self):
        seeds = {
            "org/consumer": {
                "org": "org",
                "repo": "consumer",
                "subscriptions": [
                    {"event": "theory.published", "source": "ORGAN-I", "action": "ingest"},
                ],
            },
        }
        receipt = route_event_verified("theory.published", "ORGAN-I", seeds)
        assert receipt.match_count == 1
        assert not receipt.contract_verified  # no payload to verify

    def test_receipt_to_dict(self):
        receipt = DispatchReceipt(
            event_type="test.event",
            source_organ="ORGAN-I",
            matches=[{"repo": "org/repo", "action": "run"}],
        )
        d = receipt.to_dict()
        assert d["match_count"] == 1
        assert d["event_type"] == "test.event"

    def test_no_matches(self):
        receipt = route_event_verified("unknown.event", "ORGAN-I", {})
        assert receipt.match_count == 0

    def test_backward_compat_route_event(self):
        """Original route_event still returns bare list."""
        seeds = {
            "org/consumer": {
                "org": "org",
                "repo": "consumer",
                "subscriptions": [
                    {"event": "theory.published", "source": "ORGAN-I", "action": "ingest"},
                ],
            },
        }
        result = route_event("theory.published", "ORGAN-I", seeds)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["repo"] == "org/consumer"
