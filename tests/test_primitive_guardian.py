"""Tests for the Guardian primitive."""

from datetime import datetime, timedelta, timezone

from organvm_engine.primitives.guardian import Guardian, GuardianState, WatchItem
from organvm_engine.primitives.types import (
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def test_guardian_deadline_approaching(tmp_path):
    state = GuardianState(base_path=tmp_path)
    deadline = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    state.add_watch(WatchItem(
        category="deadline",
        description="Lease renewal",
        threshold=deadline,
        direction="approaching",
        alert_window_days=7,
    ))

    guardian = Guardian(state=state)
    context = InstitutionalContext(situation="Check cycle")
    result = guardian.invoke(context, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    alerts = result.output
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "deadline_approaching"


def test_guardian_deadline_expired(tmp_path):
    state = GuardianState(base_path=tmp_path)
    deadline = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    state.add_watch(WatchItem(
        category="deadline",
        description="Filing deadline",
        threshold=deadline,
        direction="expired",
        alert_window_days=7,
    ))

    guardian = Guardian(state=state)
    context = InstitutionalContext(situation="Check cycle")
    result = guardian.invoke(context, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    alerts = result.output
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["alert_type"] == "expired"


def test_guardian_threshold_crossed(tmp_path):
    state = GuardianState(base_path=tmp_path)
    state.add_watch(WatchItem(
        category="threshold",
        description="Bank balance low",
        watched_value="balance",
        threshold="500",
        direction="below",
    ))

    guardian = Guardian(state=state)
    context = InstitutionalContext(
        situation="Check cycle",
        data={"current_state": {"balance": 350}},
    )
    result = guardian.invoke(context, Frame(FrameType.FINANCIAL), PrincipalPosition())

    alerts = result.output
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "threshold_crossed"


def test_guardian_no_alerts(tmp_path):
    state = GuardianState(base_path=tmp_path)
    deadline = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    state.add_watch(WatchItem(
        category="deadline",
        description="Far away deadline",
        threshold=deadline,
        direction="approaching",
        alert_window_days=7,
    ))

    guardian = Guardian(state=state)
    context = InstitutionalContext(situation="Check cycle")
    result = guardian.invoke(context, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    assert result.output == []
    assert result.escalation_flag is False


def test_guardian_never_escalates(tmp_path):
    """Guardian is a sensing layer — it never escalates."""
    state = GuardianState(base_path=tmp_path)
    deadline = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    state.add_watch(WatchItem(
        category="deadline",
        description="Critical past due",
        threshold=deadline,
        direction="expired",
    ))

    guardian = Guardian(state=state)
    context = InstitutionalContext(situation="Check cycle")
    result = guardian.invoke(context, Frame(FrameType.OPERATIONAL), PrincipalPosition())

    assert len(result.output) == 1
    assert result.escalation_flag is False  # guardian NEVER escalates


def test_guardian_remove_watch(tmp_path):
    state = GuardianState(base_path=tmp_path)
    item = WatchItem(item_id="test-1", description="Test watch")
    state.add_watch(item)
    assert len(state.get_watchlist()) == 1

    state.remove_watch("test-1")
    assert len(state.get_watchlist()) == 0
