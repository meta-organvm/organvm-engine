"""Tests for seed ownership parsing (v1.1)."""

from pathlib import Path

import yaml

from organvm_engine.seed.ownership import (
    actor_access,
    get_ai_agents,
    get_collaborators,
    get_lead,
    get_review_gates,
    has_ownership,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_seed():
    with (FIXTURES / "seed-v1.1-minimal.yaml").open() as f:
        return yaml.safe_load(f)


class TestOwnershipParsing:
    def test_has_ownership_true(self):
        seed = _load_seed()
        assert has_ownership(seed) is True

    def test_has_ownership_false_v1(self):
        seed = {"schema_version": "1.0", "organ": "Meta", "repo": "x", "org": "y"}
        assert has_ownership(seed) is False

    def test_has_ownership_false_empty_dict(self):
        seed = {"ownership": {}}
        assert has_ownership(seed) is False

    def test_get_lead(self):
        seed = _load_seed()
        assert get_lead(seed) == "alice"

    def test_get_lead_missing(self):
        seed = {"schema_version": "1.0", "organ": "Meta", "repo": "x", "org": "y"}
        assert get_lead(seed) is None

    def test_get_lead_empty_string(self):
        seed = {"ownership": {"lead": ""}}
        assert get_lead(seed) is None

    def test_get_collaborators(self):
        seed = _load_seed()
        collabs = get_collaborators(seed)
        assert len(collabs) == 2
        assert collabs[0]["handle"] == "bob"
        assert collabs[0]["role"] == "contributor"
        assert "commit" in collabs[0]["access"]

    def test_get_collaborators_empty(self):
        seed = {"schema_version": "1.0", "organ": "Meta", "repo": "x", "org": "y"}
        assert get_collaborators(seed) == []

    def test_get_collaborators_filters_invalid(self):
        seed = {"ownership": {"collaborators": [{"handle": "ok"}, "bad", {"no_handle": True}]}}
        assert len(get_collaborators(seed)) == 1

    def test_get_ai_agents(self):
        seed = _load_seed()
        agents = get_ai_agents(seed)
        assert len(agents) == 2
        assert agents[0]["type"] == "claude"
        assert "read" in agents[0]["access"]

    def test_get_ai_agents_empty(self):
        seed = {}
        assert get_ai_agents(seed) == []


class TestReviewGates:
    def test_get_review_gates(self):
        seed = _load_seed()
        gates = get_review_gates(seed)
        assert "promote_to_candidate" in gates
        assert "ci_pass" in gates["promote_to_candidate"]
        assert "lead_approval" in gates["promote_to_candidate"]

    def test_get_review_gates_missing(self):
        seed = {}
        gates = get_review_gates(seed)
        assert gates == {}

    def test_gate_for_graduated(self):
        seed = _load_seed()
        gates = get_review_gates(seed)
        grad = gates["promote_to_graduated"]
        assert "organ_lead_approval" in grad
        assert "stranger_test" in grad

    def test_malformed_gate_ignored(self):
        seed = {"review": {"bad_gate": "not a dict", "ok_gate": {"requires": ["ci_pass"]}}}
        gates = get_review_gates(seed)
        assert "bad_gate" not in gates
        assert "ok_gate" in gates


class TestActorAccess:
    def test_lead_has_all_access(self):
        seed = _load_seed()
        access = actor_access(seed, "alice")
        assert "promote" in access
        assert "commit" in access
        assert "release" in access

    def test_collaborator_has_declared_access(self):
        seed = _load_seed()
        access = actor_access(seed, "bob")
        assert "commit" in access
        assert "pr" in access
        assert "promote" not in access

    def test_unknown_actor_has_no_access(self):
        seed = _load_seed()
        access = actor_access(seed, "unknown-person")
        assert access == set()

    def test_no_ownership_returns_full_access(self):
        seed = {"schema_version": "1.0", "organ": "Meta", "repo": "x", "org": "y"}
        access = actor_access(seed, "anyone")
        assert "promote" in access

    def test_empty_actor_handle(self):
        seed = _load_seed()
        access = actor_access(seed, "")
        assert access == set()

    def test_case_sensitive_handles(self):
        seed = _load_seed()
        assert actor_access(seed, "Alice") == set()  # lead is "alice"
        assert "promote" in actor_access(seed, "alice")

    def test_collaborator_missing_access_key(self):
        seed = {"ownership": {"lead": "alice", "collaborators": [{"handle": "dave", "role": "contributor"}]}}
        access = actor_access(seed, "dave")
        assert access == set()  # no access key means empty set

    def test_ownership_non_dict_ignored(self):
        seed = {"ownership": "invalid"}
        assert has_ownership(seed) is False
        assert get_lead(seed) is None
        assert get_collaborators(seed) == []
        assert get_ai_agents(seed) == []
