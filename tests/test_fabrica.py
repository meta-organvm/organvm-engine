"""Tests for the Cyclic Dispatch Protocol (SPEC-024) — fabrica module."""

from __future__ import annotations

import pytest

from organvm_engine.fabrica.models import (
    ApproachVector,
    DispatchRecord,
    DispatchStatus,
    RelayIntent,
    RelayPacket,
    RelayPhase,
)
from organvm_engine.fabrica.state import (
    PHASE_TRANSITIONS,
    advance,
    is_backward,
    valid_transition,
)
from organvm_engine.fabrica.store import (
    load_active_intents,
    load_dispatches,
    load_intents,
    load_packet,
    load_packets,
    load_transitions,
    load_vectors,
    log_transition,
    save_dispatch,
    save_intent,
    save_packet,
    save_vector,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_fabrica(tmp_path, monkeypatch):
    """Redirect all fabrica I/O to a temp directory."""
    monkeypatch.setenv("ORGANVM_FABRICA_DIR", str(tmp_path / "fabrica"))


@pytest.fixture()
def packet() -> RelayPacket:
    return RelayPacket(
        raw_text="Build the cyclic dispatch protocol",
        source="cli",
        tags=["meta", "dispatch"],
    )


@pytest.fixture()
def vector(packet: RelayPacket) -> ApproachVector:
    return ApproachVector(
        packet_id=packet.id,
        thesis="Engine module composing existing dispatch + coordination + atoms",
        target_organs=["META"],
        scope="heavy",
        agent_types=["claude"],
    )


@pytest.fixture()
def intent(packet: RelayPacket, vector: ApproachVector) -> RelayIntent:
    return RelayIntent(vector_id=vector.id, packet_id=packet.id)


@pytest.fixture()
def dispatch(intent: RelayIntent) -> DispatchRecord:
    return DispatchRecord(
        task_id="abc123",
        intent_id=intent.id,
        backend="copilot",
        target="https://github.com/meta-organvm/organvm-engine/issues/42",
    )


# ---------------------------------------------------------------------------
# Data model tests
# ---------------------------------------------------------------------------

class TestRelayPacket:
    def test_content_addressed_id(self):
        p = RelayPacket(raw_text="test", source="cli", timestamp=1000.0)
        assert len(p.id) == 16
        # Same content + timestamp = same ID
        p2 = RelayPacket(raw_text="test", source="cli", timestamp=1000.0)
        assert p.id == p2.id

    def test_different_content_different_id(self):
        p1 = RelayPacket(raw_text="alpha", source="cli", timestamp=1000.0)
        p2 = RelayPacket(raw_text="beta", source="cli", timestamp=1000.0)
        assert p1.id != p2.id

    def test_default_phase_is_release(self, packet):
        assert packet.phase == RelayPhase.RELEASE

    def test_round_trip(self, packet):
        d = packet.to_dict()
        restored = RelayPacket.from_dict(d)
        assert restored.id == packet.id
        assert restored.raw_text == packet.raw_text
        assert restored.source == packet.source
        assert restored.tags == packet.tags
        assert restored.phase == packet.phase


class TestApproachVector:
    def test_id_derived_from_packet_and_thesis(self, vector):
        assert len(vector.id) == 16

    def test_round_trip(self, vector):
        d = vector.to_dict()
        restored = ApproachVector.from_dict(d)
        assert restored.id == vector.id
        assert restored.packet_id == vector.packet_id
        assert restored.thesis == vector.thesis
        assert restored.scope == "heavy"


class TestRelayIntent:
    def test_default_phase_is_handoff(self, intent):
        assert intent.phase == RelayPhase.HANDOFF

    def test_round_trip(self, intent):
        d = intent.to_dict()
        restored = RelayIntent.from_dict(d)
        assert restored.id == intent.id
        assert restored.vector_id == intent.vector_id


class TestDispatchRecord:
    def test_default_status_is_dispatched(self, dispatch):
        assert dispatch.status == DispatchStatus.DISPATCHED

    def test_round_trip(self, dispatch):
        d = dispatch.to_dict()
        restored = DispatchRecord.from_dict(d)
        assert restored.id == dispatch.id
        assert restored.backend == "copilot"
        assert restored.target == dispatch.target


# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_forward_transitions(self):
        assert valid_transition(RelayPhase.RELEASE, RelayPhase.CATCH)
        assert valid_transition(RelayPhase.CATCH, RelayPhase.HANDOFF)
        assert valid_transition(RelayPhase.HANDOFF, RelayPhase.FORTIFY)
        assert valid_transition(RelayPhase.FORTIFY, RelayPhase.COMPLETE)

    def test_backward_transitions_from_fortify(self):
        assert valid_transition(RelayPhase.FORTIFY, RelayPhase.CATCH)
        assert valid_transition(RelayPhase.FORTIFY, RelayPhase.HANDOFF)

    def test_cycle_complete_to_release(self):
        assert valid_transition(RelayPhase.COMPLETE, RelayPhase.RELEASE)

    def test_no_phase_skipping(self):
        assert not valid_transition(RelayPhase.RELEASE, RelayPhase.HANDOFF)
        assert not valid_transition(RelayPhase.CATCH, RelayPhase.FORTIFY)
        assert not valid_transition(RelayPhase.RELEASE, RelayPhase.FORTIFY)

    def test_no_backward_from_non_fortify(self):
        assert not valid_transition(RelayPhase.HANDOFF, RelayPhase.RELEASE)
        assert not valid_transition(RelayPhase.CATCH, RelayPhase.RELEASE)
        assert not valid_transition(RelayPhase.HANDOFF, RelayPhase.CATCH)

    def test_advance_unambiguous(self):
        assert advance(RelayPhase.RELEASE) == RelayPhase.CATCH
        assert advance(RelayPhase.CATCH) == RelayPhase.HANDOFF
        assert advance(RelayPhase.HANDOFF) == RelayPhase.FORTIFY

    def test_advance_ambiguous_returns_none(self):
        assert advance(RelayPhase.FORTIFY) is None

    def test_advance_complete_returns_release(self):
        assert advance(RelayPhase.COMPLETE) == RelayPhase.RELEASE

    def test_is_backward(self):
        assert is_backward(RelayPhase.FORTIFY, RelayPhase.CATCH)
        assert is_backward(RelayPhase.FORTIFY, RelayPhase.HANDOFF)
        assert not is_backward(RelayPhase.RELEASE, RelayPhase.CATCH)
        assert not is_backward(RelayPhase.CATCH, RelayPhase.HANDOFF)

    def test_all_phases_have_transitions(self):
        for phase in RelayPhase:
            assert phase in PHASE_TRANSITIONS


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_packet_round_trip(self, packet):
        save_packet(packet)
        loaded = load_packets()
        assert len(loaded) == 1
        assert loaded[0].id == packet.id
        assert loaded[0].raw_text == packet.raw_text

    def test_packet_lookup_by_id(self, packet):
        save_packet(packet)
        found = load_packet(packet.id)
        assert found is not None
        assert found.id == packet.id

    def test_packet_lookup_missing(self):
        assert load_packet("nonexistent") is None

    def test_vector_round_trip(self, vector):
        save_vector(vector)
        loaded = load_vectors(packet_id=vector.packet_id)
        assert len(loaded) == 1
        assert loaded[0].thesis == vector.thesis

    def test_vector_filter_by_packet(self, packet, vector):
        save_vector(vector)
        other = ApproachVector(
            packet_id="other_packet", thesis="Different approach",
        )
        save_vector(other)
        filtered = load_vectors(packet_id=packet.id)
        assert len(filtered) == 1
        assert filtered[0].packet_id == packet.id

    def test_intent_round_trip(self, intent):
        save_intent(intent)
        loaded = load_intents(packet_id=intent.packet_id)
        assert len(loaded) == 1
        assert loaded[0].vector_id == intent.vector_id

    def test_active_intents_excludes_complete(self, intent):
        save_intent(intent)
        assert len(load_active_intents()) == 1

        # Save a completed intent
        completed = RelayIntent(
            vector_id="v2", packet_id="p2", phase=RelayPhase.COMPLETE,
        )
        save_intent(completed)
        active = load_active_intents()
        assert len(active) == 1
        assert active[0].id == intent.id

    def test_dispatch_round_trip(self, dispatch):
        save_dispatch(dispatch)
        loaded = load_dispatches(intent_id=dispatch.intent_id)
        assert len(loaded) == 1
        assert loaded[0].backend == "copilot"

    def test_transition_log(self, packet):
        save_packet(packet)
        log_transition(
            packet.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto",
        )
        transitions = load_transitions(packet_id=packet.id)
        assert len(transitions) == 1
        assert transitions[0]["from"] == "release"
        assert transitions[0]["to"] == "catch"
        assert transitions[0]["reason"] == "auto"

    def test_empty_store_returns_empty_lists(self):
        assert load_packets() == []
        assert load_vectors() == []
        assert load_intents() == []
        assert load_dispatches() == []
        assert load_transitions() == []

    def test_multiple_appends_accumulate(self, packet):
        save_packet(packet)
        p2 = RelayPacket(raw_text="Second prompt", source="mcp")
        save_packet(p2)
        loaded = load_packets()
        assert len(loaded) == 2


# ---------------------------------------------------------------------------
# Integration: full cycle trace
# ---------------------------------------------------------------------------

class TestFullCycle:
    def test_release_to_complete(self, packet, vector, intent, dispatch):
        """Trace a RelayPacket through all four phases to COMPLETE."""
        # RELEASE
        save_packet(packet)
        log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH)

        # CATCH — generate and select vector
        save_vector(vector)
        vector.selected = True
        save_intent(intent)
        log_transition(packet.id, RelayPhase.CATCH, RelayPhase.HANDOFF)

        # HANDOFF — dispatch task
        save_dispatch(dispatch)
        log_transition(packet.id, RelayPhase.HANDOFF, RelayPhase.FORTIFY)

        # FORTIFY — approve and complete
        log_transition(
            packet.id, RelayPhase.FORTIFY, RelayPhase.COMPLETE,
            reason="all artifacts approved",
        )

        # Verify full trace
        transitions = load_transitions(packet_id=packet.id)
        phases_visited = [t["to"] for t in transitions]
        assert phases_visited == ["catch", "handoff", "fortify", "complete"]

    def test_fortify_recycle_to_catch(self, packet):
        """Verify FORTIFY can cycle back to CATCH."""
        save_packet(packet)
        log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH)
        log_transition(packet.id, RelayPhase.CATCH, RelayPhase.HANDOFF)
        log_transition(packet.id, RelayPhase.HANDOFF, RelayPhase.FORTIFY)
        log_transition(
            packet.id, RelayPhase.FORTIFY, RelayPhase.CATCH,
            reason="review revealed new questions",
        )

        transitions = load_transitions(packet_id=packet.id)
        assert transitions[-1]["to"] == "catch"
        assert is_backward(RelayPhase.FORTIFY, RelayPhase.CATCH)
