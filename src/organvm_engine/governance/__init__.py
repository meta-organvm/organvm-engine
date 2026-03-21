"""Governance module — rules enforcement, state machine, dependency graph, audit, temporal versioning."""

from organvm_engine.governance.audit import AuditResult, run_audit
from organvm_engine.governance.authorization import AuthorizationResult, authorize_transition
from organvm_engine.governance.dependency_graph import (
    DependencyResult,
    FlowType,
    MultiplexGraph,
    TypedEdge,
    build_multiplex_graph,
    validate_dependencies,
)
from organvm_engine.governance.individual_primacy import (
    PrimacyReport,
    check_individual_primacy,
)
from organvm_engine.governance.rules import load_governance_rules
from organvm_engine.governance.state_machine import check_transition, get_valid_transitions
from organvm_engine.governance.temporal import (
    GraphDiff,
    TemporalEdge,
    TemporalGraph,
    extract_edges_from_registry,
    record_registry_snapshot,
)

__all__ = [
    "load_governance_rules",
    "check_transition",
    "get_valid_transitions",
    "validate_dependencies",
    "DependencyResult",
    "FlowType",
    "TypedEdge",
    "MultiplexGraph",
    "build_multiplex_graph",
    "run_audit",
    "AuditResult",
    "authorize_transition",
    "AuthorizationResult",
    "check_individual_primacy",
    "PrimacyReport",
    "GraphDiff",
    "TemporalEdge",
    "TemporalGraph",
    "extract_edges_from_registry",
    "record_registry_snapshot",
]
