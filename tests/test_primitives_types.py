"""Tests for institutional primitive types."""

from organvm_engine.primitives.types import (
    AuditEntry,
    ExecutionMode,
    Frame,
    FrameType,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)


def test_stakes_level_values():
    assert StakesLevel.ROUTINE.value == "routine"
    assert StakesLevel.SIGNIFICANT.value == "significant"
    assert StakesLevel.CRITICAL.value == "critical"


def test_execution_mode_values():
    assert ExecutionMode.AI_PERFORMED.value == "ai_performed"
    assert ExecutionMode.HUMAN_ROUTED.value == "human_routed"
    assert ExecutionMode.PROTOCOL_STRUCTURED.value == "protocol_structured"


def test_frame_frozen():
    f = Frame(FrameType.LEGAL)
    assert f.frame_type == FrameType.LEGAL
    # frozen dataclass
    try:
        f.frame_type = FrameType.FINANCIAL  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass


def test_context_auto_id():
    c1 = InstitutionalContext(situation="test")
    c2 = InstitutionalContext(situation="test")
    assert c1.context_id != c2.context_id
    assert c1.timestamp != ""


def test_principal_position_defaults():
    p = PrincipalPosition()
    assert p.interests == []
    assert p.objectives == []
    assert p.constraints == []


def test_primitive_output_defaults():
    out = PrimitiveOutput()
    assert out.output is None
    assert out.confidence == 0.0
    assert out.escalation_flag is False
    assert out.audit_trail == []


def test_audit_entry_auto_id():
    a1 = AuditEntry(operation="test")
    a2 = AuditEntry(operation="test")
    assert a1.entry_id != a2.entry_id
