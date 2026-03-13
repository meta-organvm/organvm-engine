"""Inference bridge — connects ontologia's tension/propagation/cluster detectors to real data.

Loads entity store + edge index from the ontologia registry and runs
the inference detectors against actual system state. Surfaces results
as structured dicts for CLI/MCP/dashboard consumption.
"""

from __future__ import annotations

from typing import Any

try:
    from ontologia.inference.clusters import detect_clusters_from_relations
    from ontologia.inference.propagation import full_blast_radius
    from ontologia.inference.tension import (
        detect_naming_conflicts,
        detect_orphans,
        detect_overcoupling,
    )
    from ontologia.registry.store import open_store
    from ontologia.structure.edges import EdgeIndex

    HAS_ONTOLOGIA = True
except ImportError:
    HAS_ONTOLOGIA = False


def _check() -> dict[str, Any] | None:
    if not HAS_ONTOLOGIA:
        return {"error": "organvm-ontologia is not installed"}
    return None


# ---------------------------------------------------------------------------
# Tension detection
# ---------------------------------------------------------------------------

def detect_tensions(
    store_dir: str | None = None,
    overcoupling_threshold: int = 5,
) -> dict[str, Any]:
    """Run all tension detectors and return a combined report.

    Returns:
        {
            "orphans": [...],
            "naming_conflicts": [...],
            "overcoupled": [...],
            "total_tensions": int,
            "summary": str,
        }
    """
    err = _check()
    if err:
        return err

    from pathlib import Path

    store_path = Path(store_dir) if store_dir else None
    store = open_store(store_path)

    entities = {e.uid: e for e in store.list_entities()}
    name_index = store._name_index  # Bridge needs internal access for tension detection
    edge_index = _build_edge_index(store)

    orphans = detect_orphans(entities, edge_index)
    naming = detect_naming_conflicts(name_index)
    overcoupled = detect_overcoupling(edge_index, threshold=overcoupling_threshold)

    all_tensions = orphans + naming + overcoupled

    return {
        "orphans": [_tension_to_dict(t, store) for t in orphans],
        "naming_conflicts": [_tension_to_dict(t, store) for t in naming],
        "overcoupled": [_tension_to_dict(t, store) for t in overcoupled],
        "total_tensions": len(all_tensions),
        "summary": (
            f"{len(orphans)} orphans, "
            f"{len(naming)} naming conflicts, "
            f"{len(overcoupled)} overcoupled"
        ),
    }


# ---------------------------------------------------------------------------
# Propagation / blast radius
# ---------------------------------------------------------------------------

def compute_blast_radius(
    entity_query: str,
    max_depth: int = 3,
    store_dir: str | None = None,
) -> dict[str, Any]:
    """Compute the full blast radius for a given entity.

    Returns:
        {
            "source": str,
            "upward": [...],
            "downward": [...],
            "lateral": [...],
            "total_affected": int,
        }
    """
    err = _check()
    if err:
        return err

    from pathlib import Path

    store_path = Path(store_dir) if store_dir else None
    store = open_store(store_path)
    resolver = store.resolver()
    resolved = resolver.resolve(entity_query)

    if resolved is None:
        return {"error": f"Entity not found: {entity_query}"}

    edge_index = _build_edge_index(store)
    uid = resolved.identity.uid
    paths = full_blast_radius(edge_index, uid, max_depth=max_depth)

    upward = [_path_to_dict(p, store) for p in paths if p.direction == "upward"]
    downward = [_path_to_dict(p, store) for p in paths if p.direction == "downward"]
    lateral = [_path_to_dict(p, store) for p in paths if p.direction == "lateral"]

    source_name = store.current_name(uid)
    return {
        "source": {
            "uid": uid,
            "name": source_name.display_name if source_name else uid,
        },
        "upward": upward,
        "downward": downward,
        "lateral": lateral,
        "total_affected": len(paths),
    }


# ---------------------------------------------------------------------------
# Cluster analysis
# ---------------------------------------------------------------------------

def detect_entity_clusters(
    relation_type: str | None = None,
    min_size: int = 2,
    store_dir: str | None = None,
) -> dict[str, Any]:
    """Detect entity clusters based on shared relations.

    Returns:
        {
            "clusters": [...],
            "total_clusters": int,
        }
    """
    err = _check()
    if err:
        return err

    from pathlib import Path

    store_path = Path(store_dir) if store_dir else None
    store = open_store(store_path)
    edge_index = _build_edge_index(store)

    clusters = detect_clusters_from_relations(
        edge_index,
        relation_type=relation_type,
        min_cluster_size=min_size,
    )

    return {
        "clusters": [_cluster_to_dict(c, store) for c in clusters],
        "total_clusters": len(clusters),
    }


# ---------------------------------------------------------------------------
# Combined health inference
# ---------------------------------------------------------------------------

def infer_health(
    store_dir: str | None = None,
    entity_query: str | None = None,
) -> dict[str, Any]:
    """Combined inference: tensions + clusters for the whole system or one entity.

    Returns a composite health view suitable for CLI/MCP/dashboard.
    """
    err = _check()
    if err:
        return err

    from pathlib import Path

    store_path = Path(store_dir) if store_dir else None
    store = open_store(store_path)

    result: dict[str, Any] = {
        "entity_count": store.entity_count,
    }

    # Tensions
    tensions = detect_tensions(store_dir=store_dir)
    result["tensions"] = tensions

    # Clusters
    clusters = detect_entity_clusters(store_dir=store_dir)
    result["clusters"] = clusters

    # Per-entity detail if requested
    if entity_query:
        resolver = store.resolver()
        resolved = resolver.resolve(entity_query)
        if resolved:
            uid = resolved.identity.uid
            name = store.current_name(uid)
            result["entity"] = {
                "uid": uid,
                "name": name.display_name if name else uid,
                "type": resolved.identity.entity_type.value,
                "status": resolved.identity.lifecycle_status.value,
            }
            blast = compute_blast_radius(uid, store_dir=store_dir)
            result["blast_radius"] = blast
        else:
            result["entity"] = {"error": f"Not found: {entity_query}"}

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_edge_index(store) -> EdgeIndex:
    """Build an EdgeIndex from the store's hierarchy and relation data.

    The store tracks hierarchy via entity metadata (organ_key for organs,
    parent organ for repos). We construct edges from this structural data.
    """
    index = EdgeIndex()

    entities = store.list_entities()
    organs: dict[str, str] = {}  # organ display_name -> uid
    for e in entities:
        if e.entity_type.value == "organ":
            name = store.current_name(e.uid)
            if name:
                organs[name.display_name] = e.uid

    # Build hierarchy: organ -> repo
    for e in entities:
        if e.entity_type.value == "repo":
            # Find parent organ from metadata
            organ_key = e.metadata.get("organ_key", "")
            parent_uid = None
            for oname, ouid in organs.items():
                if organ_key and organ_key.lower() in oname.lower():
                    parent_uid = ouid
                    break
            if parent_uid:
                from ontologia.structure.edges import HierarchyEdge
                index.add_hierarchy(HierarchyEdge(
                    parent_id=parent_uid,
                    child_id=e.uid,
                    valid_from=e.created_at,
                ))

    return index


def _tension_to_dict(t, store=None) -> dict[str, Any]:
    """Convert a TensionIndicator to a serializable dict with resolved names."""
    result = {
        "type": t.tension_type.value,
        "severity": t.severity,
        "description": t.description,
        "entity_ids": t.entity_ids,
    }
    if store:
        names = []
        for uid in t.entity_ids:
            name = store.current_name(uid)
            names.append(name.display_name if name else uid)
        result["entity_names"] = names
    return result


def _path_to_dict(p, store=None) -> dict[str, Any]:
    """Convert a PropagationPath to a serializable dict."""
    result = {
        "target_id": p.target_id,
        "direction": p.direction,
        "distance": p.distance,
        "path": p.path,
    }
    if store:
        name = store.current_name(p.target_id)
        result["target_name"] = name.display_name if name else p.target_id
    return result


def _cluster_to_dict(c, store=None) -> dict[str, Any]:
    """Convert a Cluster to a serializable dict."""
    result = {
        "entity_ids": c.entity_ids,
        "cohesion": c.cohesion,
        "size": len(c.entity_ids),
    }
    if store:
        names = []
        for uid in c.entity_ids:
            name = store.current_name(uid)
            names.append(name.display_name if name else uid)
        result["entity_names"] = names
    return result
