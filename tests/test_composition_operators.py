"""Tests for composition operators."""

from organvm_engine.composition.operators import (
    chain_execute,
    parallel_execute,
)
from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.types import (
    Frame,
    FrameType,
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
)


class _EchoPrimitive(InstitutionalPrimitive):
    PRIMITIVE_ID = "PRIM-TEST-ECHO"
    PRIMITIVE_NAME = "echo"
    CLUSTER = "test"

    def invoke(self, context, frame, principal_position):
        return PrimitiveOutput(
            output={"echo": context.situation, "frame": frame.frame_type.value},
            confidence=0.8,
        )


class _EscalatingPrimitive(InstitutionalPrimitive):
    PRIMITIVE_ID = "PRIM-TEST-ESC"
    PRIMITIVE_NAME = "escalator"
    CLUSTER = "test"

    def invoke(self, context, frame, principal_position):
        return PrimitiveOutput(
            output={"escalated": True},
            confidence=0.3,
            escalation_flag=True,
        )


def test_chain_sequential():
    prims = [_EchoPrimitive(), _EchoPrimitive()]
    frames = [Frame(FrameType.LEGAL), Frame(FrameType.FINANCIAL)]
    context = InstitutionalContext(situation="test chain")
    position = PrincipalPosition()

    result = chain_execute(prims, context, frames, position)

    assert result.output is not None
    assert result.escalation_flag is False
    assert result.confidence == 0.8  # min of both


def test_chain_halts_on_escalation():
    prims = [_EscalatingPrimitive(), _EchoPrimitive()]
    frames = [Frame(FrameType.LEGAL), Frame(FrameType.FINANCIAL)]
    context = InstitutionalContext(situation="test")
    position = PrincipalPosition()

    result = chain_execute(prims, context, frames, position)

    assert result.escalation_flag is True
    assert result.metadata.get("chain_halted_at") == 0
    assert len(result.metadata.get("remaining_primitives", [])) == 1


def test_parallel_merge():
    prims = [_EchoPrimitive(), _EchoPrimitive()]
    frames = [Frame(FrameType.LEGAL), Frame(FrameType.FINANCIAL)]
    context = InstitutionalContext(situation="test parallel")
    position = PrincipalPosition()

    result = parallel_execute(prims, context, frames, position)

    assert isinstance(result.output, dict)
    assert "echo_legal" in result.output
    assert "echo_financial" in result.output
    assert result.confidence == 0.8


def test_parallel_escalation_propagates():
    prims = [_EchoPrimitive(), _EscalatingPrimitive()]
    frames = [Frame(FrameType.LEGAL), Frame(FrameType.FINANCIAL)]
    context = InstitutionalContext(situation="test")
    position = PrincipalPosition()

    result = parallel_execute(prims, context, frames, position)

    assert result.escalation_flag is True
    assert result.confidence == 0.3  # min
