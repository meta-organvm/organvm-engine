"""Tests for composition prohibition rules."""

from organvm_engine.composition.graph import (
    CompositionEdge,
    CompositionGraph,
    PrimitiveNode,
)
from organvm_engine.composition.prohibitions import validate_composition
from organvm_engine.primitives.types import Frame, FrameType


def test_mandator_without_counselor():
    graph = CompositionGraph(
        nodes=[
            PrimitiveNode("assessor", "PRIM-INST-001", node_id="a"),
            PrimitiveNode("mandator", "PRIM-INST-020", node_id="m"),
        ],
        edges=[
            CompositionEdge("a", "m", "chain"),
        ],
    )
    violations = validate_composition(graph)
    assert any("COMP-013-2" in v for v in violations)


def test_mandator_with_counselor_valid():
    graph = CompositionGraph(
        nodes=[
            PrimitiveNode("assessor", "PRIM-INST-001", node_id="a"),
            PrimitiveNode("counselor", "PRIM-INST-014", node_id="c"),
            PrimitiveNode("mandator", "PRIM-INST-020", node_id="m"),
        ],
        edges=[
            CompositionEdge("a", "c", "chain"),
            CompositionEdge("c", "m", "chain"),
        ],
    )
    violations = validate_composition(graph)
    assert not any("COMP-013-2" in v for v in violations)


def test_assessor_self_assessment():
    same_frame = Frame(FrameType.LEGAL)
    graph = CompositionGraph(
        nodes=[
            PrimitiveNode("assessor", "PRIM-INST-001", frame=same_frame, node_id="a1"),
            PrimitiveNode("assessor", "PRIM-INST-001", frame=same_frame, node_id="a2"),
        ],
        edges=[
            CompositionEdge("a1", "a2", "feedback"),
        ],
    )
    violations = validate_composition(graph)
    assert any("COMP-013-1" in v for v in violations)


def test_valid_aegis_composition():
    """The AEGIS graph should pass all prohibitions."""
    from organvm_engine.formations.aegis import build_aegis_graph
    graph = build_aegis_graph()
    violations = validate_composition(graph)
    assert violations == [], f"AEGIS should be valid but got: {violations}"
