"""Temporal Logic layer — ordering enforcement for cross-organ dispatch.

Ensures events respect the DAG ordering (I→II→III). Uses ORGAN_LEVELS
from governance/dependency_graph.py to enforce that source organs can
only fire events to organs at their level or higher.

Also verifies prerequisite chains: for a given event, traces back through
consumes edges to verify all prerequisite events have valid sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from organvm_engine.governance.dependency_graph import ORGAN_LEVELS, RESTRICTED_LEVELS
from organvm_engine.organ_config import ORGANS


def _dir_to_key(organ_dir: str) -> str | None:
    """Convert organ directory name to organ key (e.g., 'organvm-i-theoria' -> 'ORGAN-I')."""
    for key, info in ORGANS.items():
        if info.get("dir") == organ_dir:
            return info.get("registry_key", key)
    return None


def _key_to_dir(organ_key: str) -> str | None:
    """Convert organ key to directory name (e.g., 'ORGAN-I' -> 'organvm-i-theoria')."""
    for _key, info in ORGANS.items():
        if info.get("registry_key") == organ_key:
            return info.get("dir")
    return None


@dataclass
class TemporalResult:
    """Result of temporal order verification."""

    source_organ: str
    target_organ: str
    valid: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_organ": self.source_organ,
            "target_organ": self.target_organ,
            "valid": self.valid,
            "reason": self.reason,
        }


def verify_temporal_order(
    event_type: str,
    source_organ: str,
    target_organ: str,
) -> TemporalResult:
    """Verify that source organ can fire an event to target organ.

    Rules:
    - Within restricted levels (I, II, III): flow must be I→II→III (lower→higher level)
    - Organs IV-VIII can send to any organ
    - Any organ can send events to organs IV-VIII

    Args:
        event_type: Event type (for context in error messages).
        source_organ: Source organ directory name or registry key.
        target_organ: Target organ directory name or registry key.

    Returns:
        TemporalResult with validity and reasoning.
    """
    source_level = ORGAN_LEVELS.get(source_organ)
    target_level = ORGAN_LEVELS.get(target_organ)

    if source_level is None or target_level is None:
        return TemporalResult(
            source_organ=source_organ,
            target_organ=target_organ,
            valid=True,
            reason="Unrecognized organ(s) — skipping temporal check",
        )

    # If either is outside the restricted chain, allow freely
    if source_level not in RESTRICTED_LEVELS or target_level not in RESTRICTED_LEVELS:
        return TemporalResult(
            source_organ=source_organ,
            target_organ=target_organ,
            valid=True,
            reason=f"Non-restricted flow ({source_organ} L{source_level} → "
            f"{target_organ} L{target_level})",
        )

    # Within restricted chain: source must be at same or lower level than target
    if source_level <= target_level:
        return TemporalResult(
            source_organ=source_organ,
            target_organ=target_organ,
            valid=True,
            reason=f"Valid forward flow (L{source_level} → L{target_level})",
        )

    return TemporalResult(
        source_organ=source_organ,
        target_organ=target_organ,
        valid=False,
        reason=(
            f"Back-edge in restricted chain: {source_organ} (L{source_level}) "
            f"→ {target_organ} (L{target_level}) for event '{event_type}'"
        ),
    )


@dataclass
class PrerequisiteResult:
    """Result of prerequisite chain verification."""

    event_type: str
    chain: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "chain": self.chain,
            "violations": self.violations,
            "passed": self.passed,
        }


def verify_prerequisite_chain(
    event_type: str,
    seed_graph: dict[str, dict],
) -> PrerequisiteResult:
    """Trace consumes edges back from an event to verify prerequisite ordering.

    For each repo that subscribes to this event_type, check that the
    producing repo's organ level is compatible with the consuming repo's organ.

    Args:
        event_type: Event type to verify.
        seed_graph: Dict of identity -> seed data.

    Returns:
        PrerequisiteResult with chain and any violations.
    """
    from organvm_engine.seed.reader import get_consumes, get_produces, get_subscriptions

    result = PrerequisiteResult(event_type=event_type)

    # Find producers and consumers
    producers: list[tuple[str, str]] = []  # (identity, organ)
    consumers: list[tuple[str, str]] = []  # (identity, organ)

    for identity, seed in seed_graph.items():
        organ = seed.get("organ", "")

        for prod in get_produces(seed):
            prod_type = prod if isinstance(prod, str) else prod.get("type", "")
            if prod_type == event_type:
                producers.append((identity, organ))

        for cons in get_consumes(seed):
            cons_type = cons if isinstance(cons, str) else cons.get("type", "")
            if cons_type == event_type:
                consumers.append((identity, organ))

        for sub in get_subscriptions(seed):
            if sub.get("event") == event_type:
                consumers.append((identity, organ))

    for prod_id, prod_organ in producers:
        result.chain.append(f"produces: {prod_id} ({prod_organ})")

    for cons_id, cons_organ in consumers:
        result.chain.append(f"consumes: {cons_id} ({cons_organ})")

        # Check temporal ordering against each producer
        for _prod_id, prod_organ in producers:
            prod_dir = _key_to_dir(prod_organ) or prod_organ
            cons_dir = _key_to_dir(cons_organ) or cons_organ
            temporal = verify_temporal_order(event_type, prod_dir, cons_dir)
            if not temporal.valid:
                result.violations.append(temporal.reason)
                result.passed = False

    return result
