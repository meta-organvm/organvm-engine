"""Default governance policies — built-in rules for the advisory system.

Each policy uses ontologia's EvolutionPolicy with declarative conditions
and actions.  These are the system's baseline rules; operators can add
custom policies via a policies.yaml in the future.
"""

from __future__ import annotations

from typing import Any


def _build_policies() -> list[Any]:
    """Build the default policy set.

    Returns EvolutionPolicy instances if ontologia is available,
    otherwise returns an empty list.
    """
    try:
        from ontologia.governance.policies import (
            EvolutionPolicy,
            PolicyAction,
            PolicyCondition,
        )
    except ImportError:
        return []

    return [
        EvolutionPolicy(
            policy_id="auto-promote-candidate",
            name="Auto-promote CANDIDATE repos",
            description=(
                "Recommend promotion to PUBLIC_PROCESS for repos that have "
                "CI, platinum status, and active implementation."
            ),
            conditions=[
                PolicyCondition("promotion_status", "eq", "CANDIDATE"),
                PolicyCondition("ci_workflow", "eq", True),
                PolicyCondition("platinum_status", "eq", True),
                PolicyCondition("implementation_status", "eq", "ACTIVE"),
            ],
            action=PolicyAction.PROMOTE,
            scope_entity_type="repo",
            priority=10,
        ),
        EvolutionPolicy(
            policy_id="flag-orphan",
            name="Flag orphaned entities",
            description=(
                "Alert on entities that have no structural connections "
                "despite being active."
            ),
            conditions=[
                PolicyCondition("is_orphan", "eq", True),
                PolicyCondition("lifecycle", "eq", "ACTIVE"),
            ],
            action=PolicyAction.FLAG,
            priority=5,
        ),
        EvolutionPolicy(
            policy_id="flag-overcoupled",
            name="Flag overcoupled entities",
            description=(
                "Alert on entities with 5+ incoming relations — "
                "potential change bottlenecks."
            ),
            conditions=[
                PolicyCondition("incoming_relations", "gte", 5),
            ],
            action=PolicyAction.NOTIFY,
            priority=5,
        ),
        EvolutionPolicy(
            policy_id="flag-stale",
            name="Flag stale repos",
            description=(
                "Alert on repos not validated in the last 30 days "
                "that are not archived."
            ),
            conditions=[
                PolicyCondition("is_stale", "eq", True),
                PolicyCondition("promotion_status", "ne", "ARCHIVED"),
            ],
            action=PolicyAction.FLAG,
            scope_entity_type="repo",
            priority=3,
        ),
        EvolutionPolicy(
            policy_id="suggest-merge-small-clusters",
            name="Suggest merging small tightly-coupled clusters",
            description=(
                "When two entities are tightly coupled (cohesion >= 0.8), "
                "suggest merging them."
            ),
            conditions=[
                PolicyCondition("cluster_size", "lte", 2),
                PolicyCondition("cohesion", "gte", 0.8),
            ],
            action=PolicyAction.MERGE,
            priority=2,
        ),
        EvolutionPolicy(
            policy_id="deprecate-archived-with-dependents",
            name="Flag archived repos with active consumers",
            description=(
                "Archived repos that still have active dependents should "
                "be flagged for attention."
            ),
            conditions=[
                PolicyCondition("promotion_status", "eq", "ARCHIVED"),
                PolicyCondition("has_active_dependents", "eq", True),
            ],
            action=PolicyAction.FLAG,
            scope_entity_type="repo",
            priority=7,
        ),
    ]


DEFAULT_POLICIES = _build_policies()
