"""Tests for fabrica dashboard projection (SPEC-024 Phase 7).

Validates project_fabrica_dashboard() returns the correct shape
for dashboard rendering: relay cycles with age, dispatch records,
health summary, and heartbeat info.

Uses isolated tmp_path storage via ORGANVM_FABRICA_DIR.
"""

from __future__ import annotations

import json

import pytest

from organvm_engine.fabrica.models import (
    ApproachVector,
    DispatchRecord,
    DispatchStatus,
    RelayIntent,
    RelayPacket,
    RelayPhase,
)
from organvm_engine.fabrica.store import (
    fabrica_dir,
    log_transition,
    save_dispatch,
    save_intent,
    save_packet,
    save_vector,
)
from organvm_engine.metrics.views import (
    _format_age,
    _load_latest_heartbeat,
    project_fabrica_dashboard,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_fabrica(tmp_path, monkeypatch):
    """Redirect all fabrica I/O to a temp directory."""
    monkeypatch.setenv("ORGANVM_FABRICA_DIR", str(tmp_path / "fabrica"))


@pytest.fixture()
def seeded_cycle():
    """Seed a complete relay cycle with known timestamps."""
    packet = RelayPacket(
        raw_text="Implement dashboard projection for fabrica",
        source="cli",
        tags=["meta", "dashboard"],
        organ_hint="META",
        timestamp=1700000000.0,
    )
    save_packet(packet)
    log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto")

    vector = ApproachVector(
        packet_id=packet.id,
        thesis="Project fabrica state into dashboard views",
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


@pytest.fixture()
def heartbeat_report_file():
    """Write a synthetic heartbeat report for testing."""
    logs_dir = fabrica_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "type": "heartbeat_report",
        "timestamp": 1700001000.0,
        "active_intents": 1,
        "total_dispatches": 2,
        "polled": 2,
        "changed": 1,
        "completed": 0,
        "failed": 0,
        "errors": 0,
        "poll_results": [],
        "transitions": [],
        "duration_seconds": 0.45,
    }
    report_path = logs_dir / "heartbeat-latest.json"
    report_path.write_text(json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------------------
# _format_age
# ---------------------------------------------------------------------------


class TestFormatAge:
    def test_seconds(self):
        assert _format_age(30) == "30s"

    def test_minutes(self):
        assert _format_age(120) == "2m"

    def test_hours(self):
        assert _format_age(3600) == "1h"

    def test_hours_and_minutes(self):
        assert _format_age(5400) == "1h 30m"

    def test_days(self):
        assert _format_age(86400) == "1d"

    def test_days_and_hours(self):
        assert _format_age(90000) == "1d 1h"

    def test_zero(self):
        assert _format_age(0) == "0s"

    def test_negative(self):
        assert _format_age(-10) == "0s"

    def test_sub_second(self):
        assert _format_age(0.5) == "0s"


# ---------------------------------------------------------------------------
# _load_latest_heartbeat
# ---------------------------------------------------------------------------


class TestLoadLatestHeartbeat:
    def test_returns_none_when_no_report(self):
        assert _load_latest_heartbeat() is None

    def test_loads_valid_report(self, heartbeat_report_file):
        result = _load_latest_heartbeat()
        assert result is not None
        assert result["type"] == "heartbeat_report"
        assert result["timestamp"] == 1700001000.0
        assert result["polled"] == 2

    def test_returns_none_for_corrupt_json(self):
        logs_dir = fabrica_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "heartbeat-latest.json").write_text("not valid json")
        assert _load_latest_heartbeat() is None


# ---------------------------------------------------------------------------
# project_fabrica_dashboard — empty state
# ---------------------------------------------------------------------------


class TestFabricaDashboardEmpty:
    def test_empty_structure(self):
        result = project_fabrica_dashboard()
        assert result["total_cycles"] == 0
        assert result["cycles"] == []
        assert result["health"]["total_packets"] == 0
        assert result["health"]["active"] == 0
        assert result["health"]["completed"] == 0
        assert result["health"]["failed"] == 0
        assert result["health"]["pending_review"] == 0
        assert result["heartbeat"]["available"] is False
        assert "generated" in result

    def test_json_serializable(self):
        result = project_fabrica_dashboard()
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_heartbeat_unavailable_shape(self):
        result = project_fabrica_dashboard()
        hb = result["heartbeat"]
        assert hb["available"] is False
        assert hb["timestamp"] is None
        assert hb["timestamp_iso"] is None
        assert hb["age"] is None
        assert hb["polled"] == 0
        assert hb["errors"] == 0


# ---------------------------------------------------------------------------
# project_fabrica_dashboard — with data
# ---------------------------------------------------------------------------


class TestFabricaDashboardWithData:
    def test_cycle_structure(self, seeded_cycle):
        # Use a fixed "now" to get deterministic ages
        now = 1700000200.0
        result = project_fabrica_dashboard(now=now)

        assert result["total_cycles"] == 1
        cycle = result["cycles"][0]
        assert cycle["packet_id"] == seeded_cycle["packet"].id
        assert cycle["current_phase"] == "fortify"
        assert cycle["source"] == "cli"
        assert cycle["organ_hint"] == "META"
        assert cycle["tags"] == ["meta", "dashboard"]
        assert cycle["dispatch_count"] == 1
        assert cycle["vector_count"] == 1
        assert cycle["transition_count"] == 3

    def test_cycle_age_computed(self, seeded_cycle):
        now = 1700000200.0  # 200 seconds after packet creation
        result = project_fabrica_dashboard(now=now)
        cycle = result["cycles"][0]
        assert cycle["age"] == "3m"  # 200s = 3m (int(200/60)=3)
        assert cycle["age_seconds"] == 200.0

    def test_dispatch_records_shaped(self, seeded_cycle):
        now = 1700000200.0
        result = project_fabrica_dashboard(now=now)
        cycle = result["cycles"][0]
        assert len(cycle["dispatches"]) == 1

        d = cycle["dispatches"][0]
        assert d["backend"] == "claude"
        assert d["status"] == "dispatched"
        assert d["target"] == "https://github.com/meta-organvm/organvm-engine/issues/80"
        assert d["dispatched_at"] == 1700000100.0
        assert d["time_since_dispatch"] == "1m"  # 100 seconds = 1m

    def test_health_summary(self, seeded_cycle):
        result = project_fabrica_dashboard()
        health = result["health"]
        assert health["total_packets"] == 1
        assert health["total_dispatches"] == 1
        assert health["total_transitions"] == 3
        assert health["active"] == 1  # dispatched = active
        assert health["completed"] == 0
        assert health["failed"] == 0
        assert health["pending_review"] == 0

    def test_health_by_phase(self, seeded_cycle):
        result = project_fabrica_dashboard()
        assert result["health"]["by_phase"]["fortify"] == 1

    def test_health_by_backend(self, seeded_cycle):
        result = project_fabrica_dashboard()
        assert result["health"]["by_backend"]["claude"] == 1

    def test_heartbeat_with_report(self, seeded_cycle, heartbeat_report_file):
        now = 1700001100.0  # 100s after heartbeat
        result = project_fabrica_dashboard(now=now)
        hb = result["heartbeat"]
        assert hb["available"] is True
        assert hb["timestamp"] == 1700001000.0
        assert hb["timestamp_iso"] is not None
        assert hb["age"] == "1m"  # 100 seconds
        assert hb["polled"] == 2
        assert hb["changed"] == 1
        assert hb["errors"] == 0
        assert hb["duration_seconds"] == 0.45


# ---------------------------------------------------------------------------
# project_fabrica_dashboard — multiple cycles and statuses
# ---------------------------------------------------------------------------


class TestFabricaDashboardMultiple:
    def test_multiple_cycles(self):
        """Multiple packets appear as separate cycles."""
        p1 = RelayPacket(raw_text="First task", source="cli", timestamp=1700000000.0)
        p2 = RelayPacket(raw_text="Second task", source="mcp", timestamp=1700000010.0)
        save_packet(p1)
        save_packet(p2)

        result = project_fabrica_dashboard()
        assert result["total_cycles"] == 2
        ids = {c["packet_id"] for c in result["cycles"]}
        assert p1.id in ids
        assert p2.id in ids

    def test_health_counts_multiple_statuses(self, seeded_cycle):
        """Verify health summary with mixed dispatch statuses."""
        intent = seeded_cycle["intent"]

        completed = DispatchRecord(
            task_id="task_done",
            intent_id=intent.id,
            backend="human",
            status=DispatchStatus.FORTIFIED,
        )
        save_dispatch(completed)

        failed = DispatchRecord(
            task_id="task_fail",
            intent_id=intent.id,
            backend="copilot",
            status=DispatchStatus.REJECTED,
        )
        save_dispatch(failed)

        review = DispatchRecord(
            task_id="task_review",
            intent_id=intent.id,
            backend="jules",
            status=DispatchStatus.DRAFT_RETURNED,
        )
        save_dispatch(review)

        result = project_fabrica_dashboard()
        health = result["health"]
        assert health["active"] == 1  # original dispatched
        assert health["completed"] == 1
        assert health["failed"] == 1
        assert health["pending_review"] == 1
        assert health["total_dispatches"] == 4

    def test_cycle_with_no_dispatches(self):
        """A packet with no intents/dispatches still appears."""
        p = RelayPacket(raw_text="No dispatches yet", source="cli", timestamp=1700000000.0)
        save_packet(p)

        result = project_fabrica_dashboard()
        assert result["total_cycles"] == 1
        cycle = result["cycles"][0]
        assert cycle["dispatch_count"] == 0
        assert cycle["dispatches"] == []

    def test_raw_text_preserved(self):
        """The raw intention text is included for display."""
        text = "Build the entire system from scratch including everything"
        p = RelayPacket(raw_text=text, source="dashboard", timestamp=1700000000.0)
        save_packet(p)

        result = project_fabrica_dashboard()
        assert result["cycles"][0]["raw_text"] == text


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


class TestFabricaDashboardSerialization:
    def test_full_data_serializable(self, seeded_cycle, heartbeat_report_file):
        result = project_fabrica_dashboard(now=1700001100.0)
        serialized = json.dumps(result)
        roundtripped = json.loads(serialized)
        assert roundtripped["total_cycles"] == 1
        assert roundtripped["heartbeat"]["available"] is True

    def test_generated_is_iso(self):
        result = project_fabrica_dashboard()
        # generated should be a valid ISO 8601 timestamp
        assert "T" in result["generated"]
        assert result["generated"].endswith("+00:00")
