"""Tests for InstitutionalPrimitive ABC and execution mode."""

import pytest

from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.execution import mode_for_invocation
from organvm_engine.primitives.registry import PrimitiveRegistry
from organvm_engine.primitives.types import (
    ExecutionMode,
    Frame,
    FrameType,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
    StakesLevel,
)


class _DummyPrimitive(InstitutionalPrimitive):
    PRIMITIVE_ID = "PRIM-TEST-001"
    PRIMITIVE_NAME = "dummy"
    CLUSTER = "test"

    def invoke(self, context, frame, principal_position):
        return PrimitiveOutput(output="ok", confidence=0.9)


def test_abc_enforcement():
    """Cannot instantiate without implementing invoke."""
    with pytest.raises(TypeError):
        InstitutionalPrimitive()  # type: ignore[abstract]


def test_concrete_subclass():
    p = _DummyPrimitive()
    assert p.PRIMITIVE_ID == "PRIM-TEST-001"
    result = p.invoke(
        InstitutionalContext(),
        Frame(FrameType.OPERATIONAL),
        PrincipalPosition(),
    )
    assert result.output == "ok"


def test_execution_mode_ai_performed():
    assert mode_for_invocation(0.9, StakesLevel.ROUTINE) == ExecutionMode.AI_PERFORMED


def test_execution_mode_human_reviewed():
    assert mode_for_invocation(0.7, StakesLevel.ROUTINE) == ExecutionMode.AI_PREPARED_HUMAN_REVIEWED
    assert mode_for_invocation(0.9, StakesLevel.SIGNIFICANT) == ExecutionMode.AI_PREPARED_HUMAN_REVIEWED


def test_execution_mode_human_routed():
    assert mode_for_invocation(0.3, StakesLevel.ROUTINE) == ExecutionMode.HUMAN_ROUTED
    assert mode_for_invocation(0.9, StakesLevel.CRITICAL) == ExecutionMode.HUMAN_ROUTED


def test_execution_mode_protocol():
    assert mode_for_invocation(0.5, StakesLevel.ROUTINE, is_deterministic=True) == ExecutionMode.PROTOCOL_STRUCTURED


def test_make_audit_entry():
    p = _DummyPrimitive()
    ae = p._make_audit_entry(
        operation="test",
        rationale="testing",
        inputs_summary="in",
        output_summary="out",
        execution_mode=ExecutionMode.AI_PERFORMED,
        confidence=0.9,
    )
    assert ae.primitive_id == "PRIM-TEST-001"
    assert ae.operation == "test"


def test_registry():
    reg = PrimitiveRegistry()
    p = _DummyPrimitive()
    reg.register(p)
    assert reg.get_by_id("PRIM-TEST-001") is p
    assert reg.get_by_name("dummy") is p
    assert len(reg) == 1
    assert "dummy" in reg
    assert "PRIM-TEST-001" in reg
    assert reg.get_by_name("nonexistent") is None
