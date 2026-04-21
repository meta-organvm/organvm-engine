"""FORM-INST-001 — AEGIS (Defensive Perimeter).

The first crystallized formation.  Composition:

    guardian(threats) → [assessor(legal) || assessor(financial)]
        → counselor(strategic, with archivist precedent) → mandator

Trigger: threats to housing, income, legal standing, benefits.
Escalation: mandator ALWAYS escalates — principal approves all defense
directives.

This module provides:
  - ``build_aegis_graph()`` — construct the composition graph
  - ``AEGIS_SPEC`` — formation metadata
  - ``build_default_engine()`` — convenience to create a fully-wired engine
"""

from __future__ import annotations

from organvm_engine.composition.engine import CompositionEngine
from organvm_engine.composition.graph import (
    CompositionEdge,
    CompositionGraph,
    PrimitiveNode,
)
from organvm_engine.formations.registry import FormationSpec
from organvm_engine.primitives.archivist import Archivist, ArchivistStore
from organvm_engine.primitives.assessor import Assessor
from organvm_engine.primitives.counselor import Counselor
from organvm_engine.primitives.guardian import Guardian, GuardianState
from organvm_engine.primitives.inst_ledger import InstitutionalLedger, LedgerStore
from organvm_engine.primitives.mandator import Mandator, MandatorStore
from organvm_engine.primitives.registry import PrimitiveRegistry
from organvm_engine.primitives.types import Frame, FrameType


def build_aegis_graph() -> CompositionGraph:
    """Construct the AEGIS defensive formation graph.

    guardian(threats) → [assessor(legal) || assessor(financial)]
        → counselor(strategic) → mandator

    The archivist feeds precedent into the counselor via the context
    data pipeline (not as a graph node — it's a side-input resolved
    by the counselor itself).
    """
    guardian_node = PrimitiveNode(
        primitive_name="guardian",
        primitive_id="PRIM-INST-002",
        frame=Frame(FrameType.OPERATIONAL, {"mode": "threat_detection"}),
        node_id="aegis_guardian",
    )
    assessor_legal = PrimitiveNode(
        primitive_name="assessor",
        primitive_id="PRIM-INST-001",
        frame=Frame(FrameType.LEGAL),
        node_id="aegis_assessor_legal",
    )
    assessor_financial = PrimitiveNode(
        primitive_name="assessor",
        primitive_id="PRIM-INST-001",
        frame=Frame(FrameType.FINANCIAL),
        node_id="aegis_assessor_financial",
    )
    counselor_node = PrimitiveNode(
        primitive_name="counselor",
        primitive_id="PRIM-INST-014",
        frame=Frame(FrameType.STRATEGIC, {"synthesis_mode": "integrated_defense"}),
        node_id="aegis_counselor",
    )
    mandator_node = PrimitiveNode(
        primitive_name="mandator",
        primitive_id="PRIM-INST-020",
        frame=Frame(FrameType.OPERATIONAL, {"directive_authority": "human-review"}),
        node_id="aegis_mandator",
    )

    nodes = [
        guardian_node,
        assessor_legal,
        assessor_financial,
        counselor_node,
        mandator_node,
    ]

    edges = [
        # guardian → assessor_legal (chain)
        CompositionEdge("aegis_guardian", "aegis_assessor_legal", "chain"),
        # guardian → assessor_financial (chain — parallel start)
        CompositionEdge("aegis_guardian", "aegis_assessor_financial", "chain"),
        # assessor_legal → counselor (chain)
        CompositionEdge("aegis_assessor_legal", "aegis_counselor", "chain"),
        # assessor_financial → counselor (chain)
        CompositionEdge("aegis_assessor_financial", "aegis_counselor", "chain"),
        # counselor → mandator (chain)
        CompositionEdge("aegis_counselor", "aegis_mandator", "chain"),
    ]

    return CompositionGraph(
        nodes=nodes,
        edges=edges,
        name="aegis",
        formation_id="FORM-INST-001",
    )


AEGIS_SPEC = FormationSpec(
    formation_id="FORM-INST-001",
    name="aegis",
    formation_type="SYNTHESIZER",
    description="Defensive perimeter — detects threats, assesses across "
                "legal and financial frames, synthesizes recommendation, "
                "issues directive for principal approval.",
    trigger_description="Threats to housing, income, legal standing, benefits",
    escalation_policy={
        "guardian": "never (sensing layer)",
        "assessor": "if confidence < 0.6",
        "counselor": "for irreversible actions",
        "mandator": "ALWAYS (principal approves all defense directives)",
    },
    build_graph=build_aegis_graph,
    primitives_used=["guardian", "assessor", "counselor", "mandator", "archivist"],
)


def build_default_engine(
    *,
    guardian_state: GuardianState | None = None,
    archivist_store: ArchivistStore | None = None,
    ledger_store: LedgerStore | None = None,
    mandator_store: MandatorStore | None = None,
) -> CompositionEngine:
    """Create a composition engine with all Phase 0 primitives and AEGIS.

    Convenience function for CLI and tests.
    """
    registry = PrimitiveRegistry()
    registry.register(Assessor())
    registry.register(Guardian(state=guardian_state))
    registry.register(InstitutionalLedger(store=ledger_store))
    registry.register(Counselor())
    registry.register(Archivist(store=archivist_store))
    registry.register(Mandator(store=mandator_store))

    engine = CompositionEngine(registry)
    engine.register_formation("aegis", build_aegis_graph())

    return engine
