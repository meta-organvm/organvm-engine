"""Tests for the CompositionEngine."""

import pytest

from organvm_engine.composition.engine import CompositionEngine, CompositionError
from organvm_engine.composition.graph import (
    CompositionEdge,
    CompositionGraph,
    PrimitiveNode,
)
from organvm_engine.primitives.base import InstitutionalPrimitive
from organvm_engine.primitives.registry import PrimitiveRegistry
from organvm_engine.primitives.types import (
    InstitutionalContext,
    PrimitiveOutput,
    PrincipalPosition,
)


class _TestPrimitive(InstitutionalPrimitive):
    PRIMITIVE_ID = "PRIM-TEST-001"
    PRIMITIVE_NAME = "tester"
    CLUSTER = "test"

    def invoke(self, context, frame, principal_position):
        return PrimitiveOutput(
            output={"processed": True, "frame": frame.frame_type.value},
            confidence=0.85,
        )


def test_execute_single_node():
    reg = PrimitiveRegistry()
    reg.register(_TestPrimitive())

    engine = CompositionEngine(reg)
    graph = CompositionGraph(
        nodes=[PrimitiveNode("tester", "PRIM-TEST-001", node_id="t")],
        edges=[],
        name="test",
    )

    context = InstitutionalContext(situation="test")
    result = engine.execute_graph(graph, context, PrincipalPosition())

    assert result.output["processed"] is True
    assert result.confidence == 0.85


def test_execute_prohibited_composition():
    reg = PrimitiveRegistry()
    reg.register(_TestPrimitive())

    engine = CompositionEngine(reg)
    graph = CompositionGraph(
        nodes=[
            PrimitiveNode("assessor", "PRIM-INST-001", node_id="a"),
            PrimitiveNode("mandator", "PRIM-INST-020", node_id="m"),
        ],
        edges=[CompositionEdge("a", "m", "chain")],
    )

    with pytest.raises(CompositionError, match="Prohibited"):
        engine.execute_graph(
            graph, InstitutionalContext(), PrincipalPosition(),
        )


def test_formation_registration():
    reg = PrimitiveRegistry()
    reg.register(_TestPrimitive())
    engine = CompositionEngine(reg)

    graph = CompositionGraph(name="test_formation")
    engine.register_formation("test", graph)

    assert "test" in engine.list_formations()
    assert engine.get_formation_graph("test") is graph


def test_unknown_formation():
    reg = PrimitiveRegistry()
    engine = CompositionEngine(reg)

    with pytest.raises(CompositionError, match="Unknown"):
        engine.execute_formation(
            "nonexistent", InstitutionalContext(), PrincipalPosition(),
        )
