"""Tests for governance authorization."""

from organvm_engine.governance.authorization import authorize_transition

SEED_WITH_GATES = {
    "schema_version": "1.1",
    "organ": "Meta",
    "repo": "test-repo",
    "org": "meta-organvm",
    "ownership": {
        "lead": "alice",
        "collaborators": [
            {"handle": "bob", "role": "contributor", "access": ["commit", "pr"]},
            {"handle": "carol", "role": "lead", "access": ["commit", "pr", "promote"]},
        ],
    },
    "review": {
        "promote_to_candidate": {"requires": ["ci_pass", "lead_approval"]},
        "promote_to_public_process": {"requires": ["ci_pass", "lead_approval", "code_review"]},
        "promote_to_graduated": {"requires": ["ci_pass", "organ_lead_approval", "stranger_test"]},
    },
}

SEED_NO_OWNERSHIP = {
    "schema_version": "1.0",
    "organ": "Meta",
    "repo": "old-repo",
    "org": "meta-organvm",
}


class TestAuthorizeTransition:
    def test_lead_can_promote_to_candidate(self):
        result = authorize_transition("alice", "CANDIDATE", SEED_WITH_GATES)
        assert result.authorized is True

    def test_contributor_cannot_promote(self):
        result = authorize_transition("bob", "CANDIDATE", SEED_WITH_GATES)
        assert result.authorized is False
        assert "promote" in result.reason.lower()

    def test_collaborator_with_promote_access_can(self):
        result = authorize_transition("carol", "CANDIDATE", SEED_WITH_GATES)
        assert result.authorized is True

    def test_unknown_actor_cannot_promote(self):
        result = authorize_transition("stranger", "CANDIDATE", SEED_WITH_GATES)
        assert result.authorized is False

    def test_no_ownership_allows_anyone(self):
        result = authorize_transition("anyone", "CANDIDATE", SEED_NO_OWNERSHIP)
        assert result.authorized is True
        assert "no ownership" in result.reason.lower()

    def test_result_includes_required_gates(self):
        result = authorize_transition("alice", "GRADUATED", SEED_WITH_GATES)
        assert result.authorized is True
        assert "organ_lead_approval" in result.gates_required

    def test_archived_transition_by_lead(self):
        result = authorize_transition("alice", "ARCHIVED", SEED_WITH_GATES)
        assert result.authorized is True
        assert result.gates_required == []

    def test_advisory_mode_flag(self):
        result = authorize_transition("bob", "CANDIDATE", SEED_WITH_GATES, enforce=False)
        assert result.authorized is False
        assert result.advisory is True

    def test_enforce_mode_flag(self):
        result = authorize_transition("bob", "CANDIDATE", SEED_WITH_GATES, enforce=True)
        assert result.authorized is False
        assert result.advisory is False

    def test_unknown_target_state_rejected(self):
        result = authorize_transition("alice", "BOGUS", SEED_WITH_GATES)
        assert result.authorized is False
        assert "unknown" in result.reason.lower()

    def test_local_transition_no_gates(self):
        result = authorize_transition("alice", "LOCAL", SEED_WITH_GATES)
        assert result.authorized is True
        assert result.gates_required == []

    def test_public_process_gates(self):
        result = authorize_transition("carol", "PUBLIC_PROCESS", SEED_WITH_GATES)
        assert result.authorized is True
        assert "code_review" in result.gates_required
