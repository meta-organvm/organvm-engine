"""Tests for governance/sanctions.py — graduated obligation chains (SPEC-005)."""

from datetime import datetime, timezone

import pytest

from organvm_engine.governance.sanctions import (
    BACK_EDGE,
    MISSING_CI,
    MISSING_SEED,
    STALE_REPO,
    ObligationChain,
    SanctionEngine,
)

# ── ObligationChain dataclass ───────────────────────────────────────


class TestObligationChain:
    def test_current_obligation_at_start(self):
        chain = ObligationChain(
            obligations=["a", "b", "c"],
            current_index=0,
            entity_uid="ent_repo_TEST",
            rule_id="MISSING_CI",
        )
        assert chain.current_obligation == "a"

    def test_current_obligation_mid_chain(self):
        chain = ObligationChain(
            obligations=["a", "b", "c"],
            current_index=1,
            entity_uid="ent_repo_TEST",
            rule_id="MISSING_CI",
        )
        assert chain.current_obligation == "b"

    def test_current_obligation_none_when_terminal(self):
        chain = ObligationChain(
            obligations=["a", "b"],
            current_index=2,
            entity_uid="ent_repo_TEST",
            rule_id="MISSING_CI",
        )
        assert chain.current_obligation is None

    def test_remaining_at_start(self):
        chain = ObligationChain(
            obligations=["a", "b", "c"],
            current_index=0,
            entity_uid="ent_repo_TEST",
            rule_id="TEST",
        )
        assert chain.remaining == 3

    def test_remaining_at_end(self):
        chain = ObligationChain(
            obligations=["a", "b"],
            current_index=2,
            entity_uid="ent_repo_TEST",
            rule_id="TEST",
        )
        assert chain.remaining == 0

    def test_remaining_mid_chain(self):
        chain = ObligationChain(
            obligations=["a", "b", "c"],
            current_index=1,
            entity_uid="ent_repo_TEST",
            rule_id="TEST",
        )
        assert chain.remaining == 2

    def test_to_dict_structure(self):
        ts = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        chain = ObligationChain(
            obligations=["x", "y"],
            current_index=0,
            entity_uid="ent_repo_ABC",
            rule_id="STALE_REPO",
            created_at=ts,
            violation_details={"days_stale": 120},
        )
        d = chain.to_dict()
        assert d["obligations"] == ["x", "y"]
        assert d["current_index"] == 0
        assert d["entity_uid"] == "ent_repo_ABC"
        assert d["rule_id"] == "STALE_REPO"
        assert d["current_obligation"] == "x"
        assert d["is_terminal"] is False
        assert d["violation_details"] == {"days_stale": 120}
        assert "2026-03-19" in d["created_at"]

    def test_to_dict_terminal(self):
        chain = ObligationChain(
            obligations=["a"],
            current_index=1,
            entity_uid="ent_repo_X",
            rule_id="TEST",
        )
        d = chain.to_dict()
        assert d["is_terminal"] is True
        assert d["current_obligation"] is None

    def test_from_dict_roundtrip(self):
        ts = datetime(2026, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
        original = ObligationChain(
            obligations=["a", "b", "c"],
            current_index=1,
            entity_uid="ent_repo_RT",
            rule_id="BACK_EDGE",
            created_at=ts,
            violation_details={"edge": "I->II"},
        )
        restored = ObligationChain.from_dict(original.to_dict())
        assert restored.obligations == original.obligations
        assert restored.current_index == original.current_index
        assert restored.entity_uid == original.entity_uid
        assert restored.rule_id == original.rule_id
        assert restored.violation_details == original.violation_details
        assert restored.created_at.year == 2026

    def test_from_dict_missing_optional_fields(self):
        data = {
            "obligations": ["a"],
            "current_index": 0,
            "entity_uid": "ent_repo_MIN",
            "rule_id": "TEST",
        }
        chain = ObligationChain.from_dict(data)
        assert chain.violation_details == {}
        assert isinstance(chain.created_at, datetime)

    def test_default_created_at(self):
        chain = ObligationChain(
            obligations=["a"],
            current_index=0,
            entity_uid="ent_repo_NOW",
            rule_id="TEST",
        )
        assert isinstance(chain.created_at, datetime)
        assert chain.created_at.tzinfo is not None


# ── Predefined chains ───────────────────────────────────────────────


class TestPredefinedChains:
    def test_missing_ci_chain(self):
        assert MISSING_CI == ["add_ci_workflow", "request_extension", "demote_to_LOCAL"]

    def test_back_edge_chain(self):
        assert BACK_EDGE == ["remove_edge", "redesign_architecture", "archive_dependent"]

    def test_stale_repo_chain(self):
        assert STALE_REPO == ["update_repo", "declare_maintenance", "archive"]

    def test_missing_seed_chain(self):
        assert MISSING_SEED == ["create_seed", "register_liminal", "remove_from_workspace"]

    def test_all_chains_non_empty(self):
        for chain in [MISSING_CI, BACK_EDGE, STALE_REPO, MISSING_SEED]:
            assert len(chain) >= 2, "Each chain must have at least 2 obligations"

    def test_all_chains_end_with_severe_action(self):
        """Terminal obligations should be enforcement actions, not requests."""
        terminal = {
            MISSING_CI[-1],
            BACK_EDGE[-1],
            STALE_REPO[-1],
            MISSING_SEED[-1],
        }
        # Terminal obligations should contain demotion/archival/removal keywords
        severe_keywords = {"demote", "archive", "remove"}
        for t in terminal:
            assert any(
                kw in t for kw in severe_keywords
            ), f"Terminal obligation '{t}' lacks severity keyword"


# ── SanctionEngine ──────────────────────────────────────────────────


class TestSanctionEngine:
    def test_default_known_rules(self):
        engine = SanctionEngine()
        rules = engine.known_rules
        assert "MISSING_CI" in rules
        assert "BACK_EDGE" in rules
        assert "STALE_REPO" in rules
        assert "MISSING_SEED" in rules

    def test_custom_chains_added(self):
        engine = SanctionEngine(custom_chains={"CUSTOM_RULE": ["step1", "step2"]})
        assert "CUSTOM_RULE" in engine.known_rules

    def test_custom_chains_override_default(self):
        engine = SanctionEngine(
            custom_chains={"MISSING_CI": ["only_step"]},
        )
        chain = engine.evaluate_violation("MISSING_CI", "ent_repo_X")
        assert chain.obligations == ["only_step"]

    def test_evaluate_violation_creates_chain(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation(
            rule_id="MISSING_CI",
            entity_uid="ent_repo_TESTUID",
            violation_details={"repo": "my-repo"},
        )
        assert isinstance(chain, ObligationChain)
        assert chain.current_index == 0
        assert chain.entity_uid == "ent_repo_TESTUID"
        assert chain.rule_id == "MISSING_CI"
        assert chain.obligations == MISSING_CI
        assert chain.violation_details == {"repo": "my-repo"}

    def test_evaluate_violation_defensive_copy(self):
        """Modifying the returned chain's obligations must not affect defaults."""
        engine = SanctionEngine()
        chain = engine.evaluate_violation("MISSING_CI", "ent_repo_X")
        chain.obligations.append("extra")
        # Create a second chain — it should not have the appended item
        chain2 = engine.evaluate_violation("MISSING_CI", "ent_repo_Y")
        assert "extra" not in chain2.obligations

    def test_evaluate_violation_unknown_rule(self):
        engine = SanctionEngine()
        with pytest.raises(KeyError, match="No obligation chain registered"):
            engine.evaluate_violation("NONEXISTENT", "ent_repo_X")

    def test_evaluate_violation_no_details(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation("STALE_REPO", "ent_repo_X")
        assert chain.violation_details == {}

    def test_advance_chain_moves_forward(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation("MISSING_CI", "ent_repo_X")
        assert chain.current_obligation == "add_ci_workflow"

        next_ob = engine.advance_chain(chain)
        assert next_ob == "request_extension"
        assert chain.current_index == 1

        next_ob = engine.advance_chain(chain)
        assert next_ob == "demote_to_LOCAL"
        assert chain.current_index == 2

    def test_advance_to_terminal(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation("MISSING_CI", "ent_repo_X")
        # Advance through all obligations
        engine.advance_chain(chain)  # -> request_extension
        engine.advance_chain(chain)  # -> demote_to_LOCAL
        result = engine.advance_chain(chain)  # -> terminal
        assert result is None
        assert engine.is_terminal(chain)

    def test_advance_past_terminal_raises(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation("MISSING_CI", "ent_repo_X")
        for _ in range(3):
            engine.advance_chain(chain)
        with pytest.raises(ValueError, match="already terminal"):
            engine.advance_chain(chain)

    def test_is_terminal_false_at_start(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation("BACK_EDGE", "ent_repo_X")
        assert engine.is_terminal(chain) is False

    def test_is_terminal_true_when_exhausted(self):
        engine = SanctionEngine()
        chain = engine.evaluate_violation("BACK_EDGE", "ent_repo_X")
        for _ in range(len(BACK_EDGE)):
            engine.advance_chain(chain)
        assert engine.is_terminal(chain) is True


# ── Full lifecycle scenarios ────────────────────────────────────────


class TestSanctionLifecycle:
    def test_stale_repo_full_lifecycle(self):
        """Walk a STALE_REPO chain from detection to terminal."""
        engine = SanctionEngine()
        chain = engine.evaluate_violation(
            "STALE_REPO",
            "ent_repo_STALE1",
            {"days_stale": 180, "last_validated": "2025-09-01"},
        )
        steps_seen = []
        while not engine.is_terminal(chain):
            steps_seen.append(chain.current_obligation)
            engine.advance_chain(chain)

        assert steps_seen == ["update_repo", "declare_maintenance", "archive"]
        assert chain.remaining == 0

    def test_missing_seed_resolution_at_first_step(self):
        """If the entity creates a seed, the chain stops at step 0."""
        engine = SanctionEngine()
        chain = engine.evaluate_violation("MISSING_SEED", "ent_repo_NOSEED")
        # Entity creates the seed — chain is resolved, no need to advance
        assert chain.current_obligation == "create_seed"
        assert not engine.is_terminal(chain)
        # We choose not to advance — the chain stays at step 0
        assert chain.remaining == 3

    def test_back_edge_escalation(self):
        """BACK_EDGE chain escalates from removal to archival."""
        engine = SanctionEngine()
        chain = engine.evaluate_violation(
            "BACK_EDGE",
            "ent_repo_CYCLE",
            {"edge": "ORGAN-I -> ORGAN-II (back)"},
        )
        assert chain.current_obligation == "remove_edge"
        engine.advance_chain(chain)
        assert chain.current_obligation == "redesign_architecture"
        engine.advance_chain(chain)
        assert chain.current_obligation == "archive_dependent"
