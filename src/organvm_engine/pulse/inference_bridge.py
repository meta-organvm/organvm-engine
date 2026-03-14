"""Inference bridge — wire ontologia inference into the pulse cycle.

Thin bridge that assembles ontologia's entities, names, and edges from
multiple data sources (ontologia store + seed graph), runs the inference
detectors, and returns a compressed summary suitable for AMMOI.

Fail-safe: if ontologia is unavailable or the store isn't bootstrapped,
returns zeroed InferenceSummary.  Never raises.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InferenceSummary:
    """Compressed inference result for AMMOI consumption."""

    tensions: list[dict[str, Any]] = field(default_factory=list)
    tension_count: int = 0
    clusters: list[dict[str, Any]] = field(default_factory=list)
    cluster_count: int = 0
    overcoupled_entities: list[str] = field(default_factory=list)
    orphaned_entities: list[str] = field(default_factory=list)
    naming_conflicts: list[str] = field(default_factory=list)
    inference_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tensions": self.tensions,
            "tension_count": self.tension_count,
            "clusters": self.clusters,
            "cluster_count": self.cluster_count,
            "overcoupled_entities": self.overcoupled_entities,
            "orphaned_entities": self.orphaned_entities,
            "naming_conflicts": self.naming_conflicts,
            "inference_score": self.inference_score,
        }


def _build_edge_index_from_store(store: Any) -> Any:
    """Get the EdgeIndex from the store, falling back to reconstruction.

    If the store has persisted edges (from bootstrap + seed sync),
    use those directly. Otherwise, reconstruct hierarchy edges from
    entity metadata for backwards compatibility.
    """
    # Use persisted edges if available
    edge_index = store.edge_index
    if edge_index.all_hierarchy_edges() or edge_index.all_relation_edges():
        return edge_index

    # Fallback: reconstruct from metadata (pre-Nexus-Vivum stores)
    from ontologia.entity.identity import EntityType
    from ontologia.structure.edges import EdgeIndex, HierarchyEdge

    fallback = EdgeIndex()

    organ_uids: dict[str, str] = {}
    for entity in store.list_entities(entity_type=EntityType.ORGAN):
        rk = entity.metadata.get("registry_key", "")
        if rk:
            organ_uids[rk] = entity.uid

    now = "2020-01-01T00:00:00+00:00"
    for entity in store.list_entities(entity_type=EntityType.REPO):
        organ_key = entity.metadata.get("organ", "") or entity.metadata.get("organ_key", "")
        if organ_key and organ_key in organ_uids:
            fallback.add_hierarchy(HierarchyEdge(
                parent_id=organ_uids[organ_key],
                child_id=entity.uid,
                valid_from=now,
            ))

    return fallback


def _compute_inference_score(
    tension_count: int,
    entity_count: int,
) -> float:
    """Compute inference health score (0.0-1.0, higher = healthier).

    Inverse tension density: fewer tensions per entity = higher score.
    """
    if entity_count == 0:
        return 1.0
    ratio = tension_count / entity_count
    # Score = 1.0 at 0 tensions, drops toward 0 at 1:1 ratio
    return max(0.0, min(1.0, 1.0 - ratio))


def run_inference(workspace: Path | None = None) -> InferenceSummary:
    """Run full inference cycle against ontologia store.

    1. Load ontologia store (entities, names)
    2. Build hierarchy EdgeIndex from entity metadata
    3. Run detect_orphans() → TensionIndicator[]
    4. Run detect_naming_conflicts() → TensionIndicator[]
    5. Run detect_overcoupling() → TensionIndicator[]
    6. Run detect_clusters_from_relations() → Cluster[]
    7. Return InferenceSummary with counts + details

    Fail-safe: returns zeroed InferenceSummary on any error.
    """
    try:
        from ontologia.inference.clusters import detect_clusters_from_relations
        from ontologia.inference.tension import (
            detect_naming_conflicts,
            detect_orphans,
            detect_overcoupling,
        )
        from ontologia.registry.store import open_store

        store = open_store()
        if store.entity_count == 0:
            return InferenceSummary()

        # Build edge index from entity hierarchy
        edge_index = _build_edge_index_from_store(store)

        # Run detectors
        orphan_tensions = detect_orphans(
            dict(store._entities), edge_index,
        )
        naming_tensions = detect_naming_conflicts(store._name_index)
        overcoupling_tensions = detect_overcoupling(edge_index)
        clusters = detect_clusters_from_relations(edge_index)

        # Serialize tensions
        all_tensions: list[dict[str, Any]] = []
        orphaned: list[str] = []
        overcoupled: list[str] = []
        conflict_slugs: list[str] = []

        for t in orphan_tensions:
            all_tensions.append({
                "type": t.tension_type.value,
                "entity_ids": t.entity_ids,
                "severity": t.severity,
                "description": t.description,
            })
            orphaned.extend(t.entity_ids)

        for t in naming_tensions:
            all_tensions.append({
                "type": t.tension_type.value,
                "entity_ids": t.entity_ids,
                "severity": t.severity,
                "description": t.description,
            })
            conflict_slugs.append(t.description)

        for t in overcoupling_tensions:
            all_tensions.append({
                "type": t.tension_type.value,
                "entity_ids": t.entity_ids,
                "severity": t.severity,
                "description": t.description,
            })
            overcoupled.extend(t.entity_ids)

        # Serialize clusters
        cluster_dicts = [
            {
                "entity_ids": c.entity_ids,
                "cohesion": c.cohesion,
                "label": c.label,
                "size": len(c.entity_ids),
            }
            for c in clusters
        ]

        score = _compute_inference_score(
            len(all_tensions), store.entity_count,
        )

        return InferenceSummary(
            tensions=all_tensions,
            tension_count=len(all_tensions),
            clusters=cluster_dicts,
            cluster_count=len(clusters),
            overcoupled_entities=overcoupled,
            orphaned_entities=orphaned,
            naming_conflicts=conflict_slugs,
            inference_score=round(score, 4),
        )

    except ImportError:
        logger.debug("ontologia not available for inference", exc_info=True)
        return InferenceSummary()
    except Exception:
        logger.debug("Inference cycle failed (non-fatal)", exc_info=True)
        return InferenceSummary()


def blast_radius(entity_name_or_uid: str) -> dict[str, Any]:
    """Compute blast radius for a specific entity.

    Returns upward, downward, and lateral propagation paths.
    """
    try:
        from ontologia.inference.propagation import full_blast_radius
        from ontologia.registry.store import open_store

        store = open_store()
        if store.entity_count == 0:
            return {"error": "ontologia store not bootstrapped"}

        # Resolve entity
        resolver = store.resolver()
        result = resolver.resolve(entity_name_or_uid)
        if not result:
            return {"error": f"Entity not found: {entity_name_or_uid}"}

        edge_index = _build_edge_index_from_store(store)

        entity_uid = result.identity.uid
        paths = full_blast_radius(edge_index, entity_uid)

        return {
            "entity_uid": entity_uid,
            "entity_name": entity_name_or_uid,
            "total_affected": len(paths),
            "paths": [
                {
                    "target_id": p.target_id,
                    "direction": p.direction,
                    "distance": p.distance,
                    "path": p.path,
                }
                for p in paths
            ],
            "upward": len([p for p in paths if p.direction == "upward"]),
            "downward": len([p for p in paths if p.direction == "downward"]),
            "lateral": len([p for p in paths if p.direction == "lateral"]),
        }

    except ImportError:
        return {"error": "ontologia not available"}
    except Exception as exc:
        return {"error": str(exc)}
