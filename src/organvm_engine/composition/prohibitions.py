"""Prohibited composition rules (COMP-013).

These compositions are structurally invalid regardless of context.
The validator checks a CompositionGraph before execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from organvm_engine.composition.graph import CompositionGraph


@dataclass
class ProhibitionRule:
    rule_id: str
    description: str
    check: Callable[[CompositionGraph], str | None]
    # check returns an error message if violated, None if ok


def _check_mandator_without_counselor(graph: CompositionGraph) -> str | None:
    """COMP-013-2: Mandator requires counselor upstream."""
    mandator_ids = [
        n.node_id for n in graph.nodes if n.primitive_name == "mandator"
    ]
    if not mandator_ids:
        return None
    counselor_ids = {
        n.node_id for n in graph.nodes if n.primitive_name == "counselor"
    }
    if not counselor_ids:
        return "Mandator without counselor: directives require judgment"

    # Check that every mandator has at least one counselor as ancestor
    for m_id in mandator_ids:
        if not _has_ancestor(graph, m_id, counselor_ids):
            return (
                f"Mandator node {m_id} has no counselor in its ancestry chain"
            )
    return None


def _check_allocator_without_ledger(graph: CompositionGraph) -> str | None:
    """COMP-013-4: Allocator requires ledger upstream."""
    allocator_ids = [
        n.node_id for n in graph.nodes if n.primitive_name == "allocator"
    ]
    if not allocator_ids:
        return None
    ledger_ids = {
        n.node_id for n in graph.nodes if n.primitive_name == "ledger"
    }
    if not ledger_ids:
        return "Allocator without ledger: cannot allocate without position state"
    for a_id in allocator_ids:
        if not _has_ancestor(graph, a_id, ledger_ids):
            return f"Allocator node {a_id} has no ledger in its ancestry chain"
    return None


def _check_enforcer_without_guardian(graph: CompositionGraph) -> str | None:
    """COMP-013-3: Enforcer requires guardian upstream."""
    enforcer_ids = [
        n.node_id for n in graph.nodes if n.primitive_name == "enforcer"
    ]
    if not enforcer_ids:
        return None
    guardian_ids = {
        n.node_id for n in graph.nodes if n.primitive_name == "guardian"
    }
    if not guardian_ids:
        return "Enforcer without guardian: aggression, not defense"
    for e_id in enforcer_ids:
        if not _has_ancestor(graph, e_id, guardian_ids):
            return f"Enforcer node {e_id} has no guardian in its ancestry chain"
    return None


def _check_assessor_self_assessment(graph: CompositionGraph) -> str | None:
    """COMP-013-1: Assessor cannot assess itself (same frame in feedback)."""
    for edge in graph.edges:
        if edge.operator != "feedback":
            continue
        src = graph.node_by_id(edge.source_node_id)
        tgt = graph.node_by_id(edge.target_node_id)
        if (
            src and tgt
            and src.primitive_name == "assessor"
            and tgt.primitive_name == "assessor"
            and src.frame == tgt.frame
        ):
            return (
                f"Assessor self-assessment: nodes {src.node_id} and "
                f"{tgt.node_id} share the same frame in a feedback loop"
            )
    return None


def _check_representative_without_insulator(
    graph: CompositionGraph,
) -> str | None:
    """COMP-013-5: Representative without insulator in adversarial context."""
    rep_nodes = [
        n for n in graph.nodes if n.primitive_name == "representative"
    ]
    if not rep_nodes:
        return None
    insulator_ids = {
        n.node_id for n in graph.nodes if n.primitive_name == "insulator"
    }
    for rep in rep_nodes:
        is_adversarial = rep.config.get("adversarial", False)
        if is_adversarial and not _has_ancestor(graph, rep.node_id, insulator_ids):
            return (
                f"Representative {rep.node_id} in adversarial context "
                f"without insulator: information leakage risk"
            )
    return None


# ---------------------------------------------------------------------------
# Ancestry helper
# ---------------------------------------------------------------------------


def _has_ancestor(
    graph: CompositionGraph,
    node_id: str,
    target_ids: set[str],
) -> bool:
    """BFS to check if any node in target_ids is an ancestor of node_id."""
    visited: set[str] = set()
    queue = graph.predecessors(node_id)
    while queue:
        current = queue.pop(0)
        if current in target_ids:
            return True
        if current in visited:
            continue
        visited.add(current)
        queue.extend(graph.predecessors(current))
    return False


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------


PROHIBITED_COMPOSITIONS: list[ProhibitionRule] = [
    ProhibitionRule(
        rule_id="COMP-013-1",
        description="Assessor self-assessment (same frame feedback)",
        check=_check_assessor_self_assessment,
    ),
    ProhibitionRule(
        rule_id="COMP-013-2",
        description="Mandator without counselor",
        check=_check_mandator_without_counselor,
    ),
    ProhibitionRule(
        rule_id="COMP-013-3",
        description="Enforcer without guardian",
        check=_check_enforcer_without_guardian,
    ),
    ProhibitionRule(
        rule_id="COMP-013-4",
        description="Allocator without ledger",
        check=_check_allocator_without_ledger,
    ),
    ProhibitionRule(
        rule_id="COMP-013-5",
        description="Representative without insulator (adversarial)",
        check=_check_representative_without_insulator,
    ),
]


def validate_composition(graph: CompositionGraph) -> list[str]:
    """Check graph against all prohibited compositions.

    Returns list of violation messages.  Empty = valid.
    """
    violations: list[str] = []
    for rule in PROHIBITED_COMPOSITIONS:
        result = rule.check(graph)
        if result:
            violations.append(f"[{rule.rule_id}] {result}")
    return violations
