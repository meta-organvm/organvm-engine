"""Tests for ontologia governance policies bridge."""

import json
from pathlib import Path

import pytest

from organvm_engine.ontologia.policies import (
    CORE_POLICIES,
    _build_entity_state,
    _eval_condition,
    append_revision,
    bootstrap_policies,
    evaluate_all_policies,
    load_policies,
    load_revisions,
    policies_path,
    revisions_path,
    save_policies,
)


@pytest.fixture
def store_dir(tmp_path):
    return tmp_path / "ontologia"


@pytest.fixture
def registry_file(tmp_path):
    registry = {
        "version": "2",
        "organs": {
            "ORGAN-I": {
                "name": "Theoria",
                "repositories": [
                    {
                        "name": "ready-repo",
                        "promotion_status": "CANDIDATE",
                        "ci_workflow": "ci.yml",
                        "platinum_status": True,
                        "implementation_status": "ACTIVE",
                        "tier": "standard",
                        "last_validated": "2026-03-10T00:00:00Z",
                    },
                    {
                        "name": "blocked-repo",
                        "promotion_status": "CANDIDATE",
                        "ci_workflow": "",
                        "platinum_status": False,
                        "implementation_status": "STUB",
                        "tier": "standard",
                        "last_validated": "2025-01-01T00:00:00Z",
                    },
                    {
                        "name": "no-ci-repo",
                        "promotion_status": "LOCAL",
                        "ci_workflow": "",
                        "platinum_status": False,
                        "implementation_status": "ACTIVE",
                        "tier": "standard",
                        "last_validated": "",
                    },
                    {
                        "name": "archived-repo",
                        "promotion_status": "ARCHIVED",
                        "ci_workflow": "",
                        "platinum_status": False,
                        "implementation_status": "ARCHIVED",
                        "tier": "archive",
                        "last_validated": "",
                    },
                ],
            },
        },
    }
    path = tmp_path / "registry-v2.json"
    path.write_text(json.dumps(registry))
    return path


# ---------------------------------------------------------------------------
# Core policy definitions
# ---------------------------------------------------------------------------

class TestCorePolicies:
    def test_six_policies_defined(self):
        assert len(CORE_POLICIES) == 6

    def test_all_have_required_fields(self):
        for p in CORE_POLICIES:
            assert "policy_id" in p
            assert "name" in p
            assert "conditions" in p
            assert "action" in p

    def test_unique_ids(self):
        ids = [p["policy_id"] for p in CORE_POLICIES]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Policy I/O
# ---------------------------------------------------------------------------

class TestPolicyIO:
    def test_bootstrap_creates_file(self, store_dir):
        bootstrap_policies(store_dir)
        assert policies_path(store_dir).is_file()

    def test_load_policies_after_bootstrap(self, store_dir):
        bootstrap_policies(store_dir)
        policies = load_policies(store_dir)
        assert len(policies) == 6

    def test_save_and_load_roundtrip(self, store_dir):
        custom = [{"policy_id": "test-1", "name": "Test", "conditions": [], "action": "flag"}]
        save_policies(custom, store_dir)
        loaded = load_policies(store_dir)
        assert len(loaded) == 1
        assert loaded[0]["policy_id"] == "test-1"

    def test_load_auto_bootstraps(self, store_dir):
        # No file exists yet — load should bootstrap
        policies = load_policies(store_dir)
        assert len(policies) == 6


# ---------------------------------------------------------------------------
# Revision I/O
# ---------------------------------------------------------------------------

class TestRevisionIO:
    def test_append_and_load(self, store_dir):
        rev = {"revision_id": "rev_001", "title": "Test", "status": "detected"}
        append_revision(rev, store_dir)
        revisions = load_revisions(store_dir)
        assert len(revisions) == 1
        assert revisions[0]["revision_id"] == "rev_001"

    def test_multiple_revisions(self, store_dir):
        for i in range(5):
            append_revision(
                {"revision_id": f"rev_{i}", "title": f"Rev {i}", "status": "detected"},
                store_dir,
            )
        revisions = load_revisions(store_dir)
        assert len(revisions) == 5

    def test_filter_by_status(self, store_dir):
        append_revision({"revision_id": "rev_1", "status": "detected"}, store_dir)
        append_revision({"revision_id": "rev_2", "status": "applied"}, store_dir)
        detected = load_revisions(store_dir, status="detected")
        assert len(detected) == 1
        assert detected[0]["revision_id"] == "rev_1"

    def test_empty_revisions(self, store_dir):
        assert load_revisions(store_dir) == []


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

class TestEvalCondition:
    def test_eq(self):
        assert _eval_condition({"field": "x", "operator": "eq", "value": 5}, {"x": 5})
        assert not _eval_condition({"field": "x", "operator": "eq", "value": 5}, {"x": 3})

    def test_ne(self):
        assert _eval_condition({"field": "x", "operator": "ne", "value": 5}, {"x": 3})
        assert not _eval_condition({"field": "x", "operator": "ne", "value": 5}, {"x": 5})

    def test_gt(self):
        assert _eval_condition({"field": "x", "operator": "gt", "value": 5}, {"x": 10})
        assert not _eval_condition({"field": "x", "operator": "gt", "value": 5}, {"x": 3})

    def test_lt(self):
        assert _eval_condition({"field": "x", "operator": "lt", "value": 5}, {"x": 3})

    def test_in(self):
        assert _eval_condition(
            {"field": "x", "operator": "in", "value": ["a", "b"]}, {"x": "a"},
        )
        assert not _eval_condition(
            {"field": "x", "operator": "in", "value": ["a", "b"]}, {"x": "c"},
        )

    def test_not_in(self):
        assert _eval_condition(
            {"field": "x", "operator": "not_in", "value": ["a", "b"]}, {"x": "c"},
        )

    def test_missing_field(self):
        assert _eval_condition({"field": "x", "operator": "eq", "value": None}, {"y": 5})


# ---------------------------------------------------------------------------
# Entity state building
# ---------------------------------------------------------------------------

class TestBuildEntityState:
    def test_basic_fields(self):
        repo = {
            "name": "test",
            "promotion_status": "CANDIDATE",
            "ci_workflow": "ci.yml",
            "platinum_status": True,
            "implementation_status": "ACTIVE",
            "tier": "standard",
            "last_validated": "2026-03-10T00:00:00Z",
        }
        state = _build_entity_state(repo)
        assert state["promotion_status"] == "CANDIDATE"
        assert state["ci_workflow"] == "ci.yml"
        assert state["platinum_status"] is True
        assert state["name_matches_repo"] is True

    def test_days_since_validation_computed(self):
        repo = {"last_validated": "2025-01-01T00:00:00Z"}
        state = _build_entity_state(repo)
        assert state["days_since_validation"] > 400

    def test_missing_validation_date(self):
        repo = {"last_validated": ""}
        state = _build_entity_state(repo)
        assert state["days_since_validation"] == 999


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------

class TestEvaluateAllPolicies:
    def test_evaluates_all_repos(self, registry_file, store_dir):
        bootstrap_policies(store_dir)
        result = evaluate_all_policies(
            registry_path=registry_file,
            store_dir=store_dir,
        )
        assert result["evaluated"] == 4

    def test_detects_promotion_ready(self, registry_file, store_dir):
        bootstrap_policies(store_dir)
        result = evaluate_all_policies(
            registry_path=registry_file,
            store_dir=store_dir,
        )
        promote = [
            t for t in result["triggered"]
            if t["policy_id"] == "pol-promote-ready"
        ]
        assert len(promote) == 1
        assert promote[0]["entity"] == "ready-repo"

    def test_detects_missing_ci(self, registry_file, store_dir):
        bootstrap_policies(store_dir)
        result = evaluate_all_policies(
            registry_path=registry_file,
            store_dir=store_dir,
        )
        missing_ci = [
            t for t in result["triggered"]
            if t["policy_id"] == "pol-missing-ci"
        ]
        # blocked-repo and no-ci-repo both lack CI and are standard tier
        entity_names = {t["entity"] for t in missing_ci}
        assert "blocked-repo" in entity_names
        assert "no-ci-repo" in entity_names

    def test_detects_stale_candidate(self, registry_file, store_dir):
        bootstrap_policies(store_dir)
        result = evaluate_all_policies(
            registry_path=registry_file,
            store_dir=store_dir,
        )
        stale = [
            t for t in result["triggered"]
            if t["policy_id"] == "pol-stale-candidate"
        ]
        assert any(t["entity"] == "blocked-repo" for t in stale)

    def test_write_revisions(self, registry_file, store_dir):
        bootstrap_policies(store_dir)
        result = evaluate_all_policies(
            registry_path=registry_file,
            store_dir=store_dir,
            write_revisions=True,
        )
        assert result["revisions_created"] > 0
        revisions = load_revisions(store_dir)
        assert len(revisions) == result["revisions_created"]
