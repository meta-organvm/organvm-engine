"""Tests for the Mandator primitive."""

from organvm_engine.primitives.mandator import Mandator, MandatorStore
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def test_mandator_always_escalates(tmp_path):
    store = MandatorStore(base_path=tmp_path)
    mandator = Mandator(store=store)

    context = InstitutionalContext(
        data={
            "recommended_action": "File response to eviction notice",
            "urgency": "immediate",
            "reversibility": "irreversible",
            "trade_offs": [{"option": "File now", "pros": ["Meets deadline"]}],
            "recommendation_id": "REC-test-123",
        },
    )
    result = mandator.invoke(
        context, Frame(FrameType.OPERATIONAL),
        PrincipalPosition(constraints=["Limited budget"]),
    )

    assert result.escalation_flag is True  # ALWAYS escalates
    assert result.execution_mode == ExecutionMode.HUMAN_ROUTED


def test_mandator_creates_directive(tmp_path):
    store = MandatorStore(base_path=tmp_path)
    mandator = Mandator(store=store)

    context = InstitutionalContext(
        data={
            "recommended_action": "Pay overdue bill",
            "urgency": "short_term",
            "reversibility": "reversible",
        },
    )
    result = mandator.invoke(
        context, Frame(FrameType.OPERATIONAL), PrincipalPosition(),
    )

    directive = result.output
    assert directive["action"] == "Pay overdue bill"
    assert directive["priority"] == "normal"
    assert directive["status"] == "pending"
    assert directive["assigned_to"] == "human"

    # Verify persisted
    directives = store.load_directives()
    assert len(directives) == 1
    assert directives[0].action == "Pay overdue bill"


def test_mandator_urgent_priority(tmp_path):
    store = MandatorStore(base_path=tmp_path)
    mandator = Mandator(store=store)

    context = InstitutionalContext(
        data={
            "recommended_action": "Emergency response",
            "urgency": "immediate",
        },
    )
    result = mandator.invoke(
        context, Frame(FrameType.OPERATIONAL), PrincipalPosition(),
    )

    assert result.output["priority"] == "urgent"
