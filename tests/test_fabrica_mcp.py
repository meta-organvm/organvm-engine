"""Tests for fabrica MCP tool functions (SPEC-024 Phase 6).

Each tool returns a JSON-serializable dict. Tests use isolated
tmp_path storage via ORGANVM_FABRICA_DIR to avoid filesystem
dependencies.
"""

from __future__ import annotations

import json

import pytest

from organvm_engine.fabrica.mcp_tools import (
    fabrica_dispatch,
    fabrica_health,
    fabrica_log,
    fabrica_status,
)
from organvm_engine.fabrica.models import (
    ApproachVector,
    DispatchRecord,
    DispatchStatus,
    RelayIntent,
    RelayPacket,
    RelayPhase,
)
from organvm_engine.fabrica.store import (
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
def seeded_cycle(tmp_path):
    """Seed a full relay cycle (RELEASE → CATCH → HANDOFF → FORTIFY) for queries."""
    packet = RelayPacket(
        raw_text="Implement MCP projection for fabrica",
        source="cli",
        tags=["meta", "mcp"],
        organ_hint="META",
        timestamp=1700000000.0,
    )
    save_packet(packet)
    log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto")

    vector = ApproachVector(
        packet_id=packet.id,
        thesis="Expose fabrica state via MCP tools",
        target_organs=["META"],
        scope="medium",
    )
    vector.selected = True
    save_vector(vector)

    intent = RelayIntent(vector_id=vector.id, packet_id=packet.id)
    save_intent(intent)
    log_transition(packet.id, RelayPhase.CATCH, RelayPhase.HANDOFF, reason="vector selected")

    dispatch = DispatchRecord(
        task_id="task001",
        intent_id=intent.id,
        backend="claude",
        target="https://github.com/meta-organvm/organvm-engine/issues/80",
        dispatched_at=1700000100.0,
    )
    save_dispatch(dispatch)
    log_transition(
        packet.id, RelayPhase.HANDOFF, RelayPhase.FORTIFY,
        reason="dispatched to claude",
    )

    return {
        "packet": packet,
        "vector": vector,
        "intent": intent,
        "dispatch": dispatch,
    }


# ---------------------------------------------------------------------------
# fabrica_status
# ---------------------------------------------------------------------------


class TestFabricaStatus:
    def test_empty_returns_zero(self):
        result = fabrica_status()
        assert result["total"] == 0
        assert result["cycles"] == []

    def test_json_serializable(self):
        result = fabrica_status()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_lists_seeded_cycle(self, seeded_cycle):
        result = fabrica_status()
        assert result["total"] == 1
        cycle = result["cycles"][0]
        assert cycle["packet_id"] == seeded_cycle["packet"].id
        assert cycle["current_phase"] == "fortify"
        assert cycle["source"] == "cli"
        assert cycle["vector_count"] == 1
        assert cycle["dispatch_count"] == 1
        assert cycle["transition_count"] == 3

    def test_filter_by_packet_id(self, seeded_cycle):
        pid = seeded_cycle["packet"].id
        result = fabrica_status(packet_id=pid)
        assert result["total"] == 1
        assert result["cycles"][0]["packet_id"] == pid

    def test_filter_by_packet_id_prefix(self, seeded_cycle):
        pid = seeded_cycle["packet"].id
        prefix = pid[:6]
        result = fabrica_status(packet_id=prefix)
        assert result["total"] == 1

    def test_filter_by_packet_id_no_match(self):
        result = fabrica_status(packet_id="nonexistent")
        assert result["total"] == 0

    def test_filter_by_phase(self, seeded_cycle):
        result = fabrica_status(phase="fortify")
        assert result["total"] == 1

        result_catch = fabrica_status(phase="catch")
        assert result_catch["total"] == 0

    def test_dispatches_included(self, seeded_cycle):
        result = fabrica_status()
        cycle = result["cycles"][0]
        assert len(cycle["dispatches"]) == 1
        assert cycle["dispatches"][0]["backend"] == "claude"
        assert cycle["dispatches"][0]["task_id"] == "task001"

    def test_limit_applied(self):
        """Seed multiple packets and verify limit is respected."""
        for i in range(5):
            p = RelayPacket(raw_text=f"Packet {i}", source="cli", timestamp=1700000000.0 + i)
            save_packet(p)

        result = fabrica_status(limit=3)
        assert result["total"] == 3

    def test_multiple_packets(self):
        p1 = RelayPacket(raw_text="First", source="cli", timestamp=1700000000.0)
        p2 = RelayPacket(raw_text="Second", source="mcp", timestamp=1700000001.0)
        save_packet(p1)
        save_packet(p2)

        result = fabrica_status()
        assert result["total"] == 2
        ids = {c["packet_id"] for c in result["cycles"]}
        assert p1.id in ids
        assert p2.id in ids


# ---------------------------------------------------------------------------
# fabrica_dispatch
# ---------------------------------------------------------------------------


class TestFabricaDispatch:
    def test_missing_text_returns_error(self):
        result = fabrica_dispatch(text="")
        assert "error" in result
        assert "text" in result["error"]

    def test_json_serializable(self):
        result = fabrica_dispatch(text="Test dispatch")
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_release_only(self):
        """Without backend/repo, only RELEASE → CATCH occurs."""
        result = fabrica_dispatch(
            text="Build the thing",
            source="mcp",
            organ_hint="META",
            tags=["test"],
        )
        assert "packet_id" in result
        assert result["source"] == "mcp"
        assert result["organ_hint"] == "META"
        assert result["tags"] == ["test"]
        assert result["phase"] == "catch"
        assert "dispatch" not in result

    def test_full_dispatch_with_backend(self):
        """With backend + repo, dispatches through to FORTIFY."""
        result = fabrica_dispatch(
            text="Implement feature X",
            backend="human",
            repo="meta-organvm/organvm-engine",
            title="Feature X implementation",
            body="Full specification here",
            dry_run=True,
        )
        assert "packet_id" in result
        assert result["phase"] == "fortify"
        assert "dispatch" in result
        assert result["dispatch"]["backend"] == "human"
        assert result["dry_run"] is True
        assert "intent_id" in result

    def test_invalid_backend_returns_error(self):
        result = fabrica_dispatch(
            text="Test dispatch",
            backend="nonexistent_backend",
            repo="org/repo",
        )
        assert "dispatch_error" in result
        assert "nonexistent_backend" in result["dispatch_error"]

    def test_creates_packet_in_store(self):
        result = fabrica_dispatch(text="Stored packet")
        packet_id = result["packet_id"]

        # Verify it persisted
        status = fabrica_status(packet_id=packet_id)
        assert status["total"] == 1

    def test_creates_transitions(self):
        result = fabrica_dispatch(text="With transitions")
        log = fabrica_log(packet_id=result["packet_id"])
        assert log["total"] >= 1
        assert log["transitions"][0]["from_phase"] == "release"
        assert log["transitions"][0]["to_phase"] == "catch"

    def test_full_dispatch_creates_multiple_transitions(self):
        result = fabrica_dispatch(
            text="Full cycle",
            backend="human",
            repo="org/repo",
            dry_run=True,
        )
        log = fabrica_log(packet_id=result["packet_id"])
        # RELEASE → CATCH, CATCH → HANDOFF, HANDOFF → FORTIFY
        assert log["total"] == 3
        phases = [(t["from_phase"], t["to_phase"]) for t in log["transitions"]]
        assert ("release", "catch") in phases
        assert ("catch", "handoff") in phases
        assert ("handoff", "fortify") in phases

    def test_default_source_is_mcp(self):
        result = fabrica_dispatch(text="Default source")
        assert result["source"] == "mcp"

    def test_default_dry_run_is_true(self):
        result = fabrica_dispatch(
            text="Dry run check",
            backend="human",
            repo="org/repo",
        )
        assert result["dry_run"] is True


# ---------------------------------------------------------------------------
# fabrica_log
# ---------------------------------------------------------------------------


class TestFabricaLog:
    def test_empty_returns_zero(self):
        result = fabrica_log()
        assert result["total"] == 0
        assert result["transitions"] == []

    def test_json_serializable(self):
        result = fabrica_log()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_shows_transitions(self, seeded_cycle):
        result = fabrica_log(packet_id=seeded_cycle["packet"].id)
        assert result["total"] == 3
        phases = [t["to_phase"] for t in result["transitions"]]
        assert phases == ["catch", "handoff", "fortify"]

    def test_filter_by_packet_id(self, seeded_cycle):
        # Seed another packet with transitions
        p2 = RelayPacket(raw_text="Other", source="cli", timestamp=1700000002.0)
        save_packet(p2)
        log_transition(p2.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto")

        # Filter should only return seeded_cycle transitions
        result = fabrica_log(packet_id=seeded_cycle["packet"].id)
        all_pids = {t["packet_id"] for t in result["transitions"]}
        assert all_pids == {seeded_cycle["packet"].id}

    def test_no_filter_returns_all(self, seeded_cycle):
        p2 = RelayPacket(raw_text="Other", source="cli", timestamp=1700000002.0)
        save_packet(p2)
        log_transition(p2.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto")

        result = fabrica_log()
        assert result["total"] == 4  # 3 from seeded_cycle + 1 from p2

    def test_limit_applied(self, seeded_cycle):
        result = fabrica_log(packet_id=seeded_cycle["packet"].id, limit=2)
        assert result["total"] == 2

    def test_transition_structure(self, seeded_cycle):
        result = fabrica_log(packet_id=seeded_cycle["packet"].id)
        t = result["transitions"][0]
        assert "packet_id" in t
        assert "from_phase" in t
        assert "to_phase" in t
        assert "reason" in t
        assert "timestamp" in t


# ---------------------------------------------------------------------------
# fabrica_health
# ---------------------------------------------------------------------------


class TestFabricaHealth:
    def test_empty_returns_zeroes(self):
        result = fabrica_health()
        assert result["total_packets"] == 0
        assert result["total_intents"] == 0
        assert result["total_dispatches"] == 0
        assert result["total_transitions"] == 0
        assert result["by_phase"] == {}
        assert result["by_dispatch_status"] == {}
        assert result["by_backend"] == {}
        assert result["summary"]["active"] == 0
        assert result["summary"]["completed"] == 0
        assert result["summary"]["failed"] == 0
        assert result["summary"]["pending_review"] == 0

    def test_json_serializable(self):
        result = fabrica_health()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_counts_seeded_data(self, seeded_cycle):
        result = fabrica_health()
        assert result["total_packets"] == 1
        assert result["total_intents"] == 1
        assert result["total_dispatches"] == 1
        assert result["total_transitions"] == 3

    def test_phase_counts(self, seeded_cycle):
        result = fabrica_health()
        assert result["by_phase"]["fortify"] == 1

    def test_dispatch_status_counts(self, seeded_cycle):
        result = fabrica_health()
        assert result["by_dispatch_status"]["dispatched"] == 1

    def test_backend_counts(self, seeded_cycle):
        result = fabrica_health()
        assert result["by_backend"]["claude"] == 1

    def test_summary_active(self, seeded_cycle):
        result = fabrica_health()
        assert result["summary"]["active"] == 1  # dispatched is active
        assert result["summary"]["completed"] == 0
        assert result["summary"]["failed"] == 0

    def test_summary_completed(self, seeded_cycle):
        """Add a FORTIFIED dispatch and check summary."""
        intent = seeded_cycle["intent"]
        completed = DispatchRecord(
            task_id="task002",
            intent_id=intent.id,
            backend="human",
            target="https://example.com/pr/1",
            status=DispatchStatus.FORTIFIED,
        )
        save_dispatch(completed)

        result = fabrica_health()
        assert result["summary"]["completed"] == 1

    def test_summary_failed(self, seeded_cycle):
        """Add a REJECTED dispatch and check summary."""
        intent = seeded_cycle["intent"]
        rejected = DispatchRecord(
            task_id="task003",
            intent_id=intent.id,
            backend="copilot",
            target="https://example.com/pr/2",
            status=DispatchStatus.REJECTED,
        )
        save_dispatch(rejected)

        result = fabrica_health()
        assert result["summary"]["failed"] == 1

    def test_summary_pending_review(self, seeded_cycle):
        """Add a DRAFT_RETURNED dispatch and check summary."""
        intent = seeded_cycle["intent"]
        draft = DispatchRecord(
            task_id="task004",
            intent_id=intent.id,
            backend="jules",
            target="https://example.com/pr/3",
            status=DispatchStatus.DRAFT_RETURNED,
        )
        save_dispatch(draft)

        result = fabrica_health()
        assert result["summary"]["pending_review"] == 1

    def test_multiple_backends(self, seeded_cycle):
        """Verify backend breakdown with multiple backends."""
        intent = seeded_cycle["intent"]
        for i, backend in enumerate(["human", "copilot", "copilot"]):
            d = DispatchRecord(
                task_id=f"multi{i}",
                intent_id=intent.id,
                backend=backend,
                target=f"target-{i}",
            )
            save_dispatch(d)

        result = fabrica_health()
        assert result["by_backend"]["claude"] == 1
        assert result["by_backend"]["human"] == 1
        assert result["by_backend"]["copilot"] == 2

    def test_multiple_phases(self):
        """Verify phase breakdown with packets at different phases."""
        # Packet in RELEASE (no transitions)
        p1 = RelayPacket(raw_text="At release", source="cli", timestamp=1700000000.0)
        save_packet(p1)

        # Packet in CATCH
        p2 = RelayPacket(raw_text="At catch", source="cli", timestamp=1700000001.0)
        save_packet(p2)
        log_transition(p2.id, RelayPhase.RELEASE, RelayPhase.CATCH)

        # Packet in COMPLETE
        p3 = RelayPacket(raw_text="Done", source="cli", timestamp=1700000002.0)
        save_packet(p3)
        log_transition(p3.id, RelayPhase.RELEASE, RelayPhase.CATCH)
        log_transition(p3.id, RelayPhase.CATCH, RelayPhase.HANDOFF)
        log_transition(p3.id, RelayPhase.HANDOFF, RelayPhase.FORTIFY)
        log_transition(p3.id, RelayPhase.FORTIFY, RelayPhase.COMPLETE)

        result = fabrica_health()
        assert result["total_packets"] == 3
        assert result["by_phase"]["release"] == 1
        assert result["by_phase"]["catch"] == 1
        assert result["by_phase"]["complete"] == 1
