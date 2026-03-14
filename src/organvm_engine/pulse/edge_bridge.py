"""Bridge seed.yaml edges into ontologia relation edges.

Reads the seed graph (produces/consumes/subscribes/depends), resolves
node identities to ontologia entity UIDs, and persists RelationEdge
records into the ontologia store. Idempotent — skips edges that
already exist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Seed edge type → ontologia relation type
_SEED_TO_RELATION: dict[str, str] = {
    "produces": "produces_for",
    "consumes": "consumes_from",
    "subscribes": "subscribes_to",
    "dependency": "depends_on",
}


@dataclass
class EdgeSyncResult:
    """Summary of a seed→ontologia edge sync run."""

    created: int = 0
    skipped: int = 0
    unresolved: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "skipped": self.skipped,
            "unresolved": self.unresolved,
            "total_seed_edges": self.created + self.skipped + self.unresolved,
            "details": self.details,
        }


def _resolve_seed_node(
    node_name: str,
    name_to_uid: dict[str, str],
) -> str | None:
    """Resolve a seed graph node name to an ontologia entity UID.

    Seed nodes use "org/repo-name" format. We try exact match first,
    then fall back to matching just the repo name portion.
    """
    # Exact match on org/name
    if node_name in name_to_uid:
        return name_to_uid[node_name]

    # Try just the repo name (after /)
    if "/" in node_name:
        repo_part = node_name.split("/", 1)[1]
        if repo_part in name_to_uid:
            return name_to_uid[repo_part]

    return None


def _build_name_to_uid_map(store: Any) -> dict[str, str]:
    """Build a mapping from various name forms to entity UIDs.

    Maps: display_name, org/name metadata, just name metadata.
    """
    from ontologia.entity.identity import EntityType

    mapping: dict[str, str] = {}
    for entity in store.list_entities(entity_type=EntityType.REPO):
        uid = entity.uid
        org = entity.metadata.get("org", "")
        name = entity.metadata.get("name", "")

        if org and name:
            mapping[f"{org}/{name}"] = uid
        if name:
            mapping[name] = uid

        # Also map by current display name
        current = store.current_name(uid)
        if current:
            mapping[current.display_name] = uid

    return mapping


def sync_seed_edges(workspace: Path | None = None) -> EdgeSyncResult:
    """Bridge seed.yaml edges into ontologia relation edges.

    1. Build seed graph from workspace
    2. Load ontologia store
    3. Resolve seed node names to entity UIDs
    4. For each seed edge, create a RelationEdge if not already present
    5. Return summary of created/skipped/unresolved edges

    Fail-safe: returns empty result on any import/runtime error.
    """
    result = EdgeSyncResult()

    try:
        from ontologia.registry.store import open_store

        from organvm_engine.seed.graph import build_seed_graph

        store = open_store()
        if store.entity_count == 0:
            return result

        ws = workspace or Path.home() / "Workspace"
        graph = build_seed_graph(ws)

        if not graph.edges:
            return result

        name_to_uid = _build_name_to_uid_map(store)

        # Build set of existing active relation edges for dedup
        existing: set[tuple[str, str, str]] = set()
        for edge in store.edge_index.all_relation_edges():
            if edge.is_active():
                existing.add((edge.source_id, edge.target_id, edge.relation_type))

        for src_name, tgt_name, edge_type in graph.edges:
            src_uid = _resolve_seed_node(src_name, name_to_uid)
            tgt_uid = _resolve_seed_node(tgt_name, name_to_uid)

            if not src_uid or not tgt_uid:
                result.unresolved += 1
                result.details.append({
                    "action": "unresolved",
                    "source": src_name,
                    "target": tgt_name,
                    "edge_type": edge_type,
                    "source_resolved": src_uid is not None,
                    "target_resolved": tgt_uid is not None,
                })
                continue

            relation_type = _SEED_TO_RELATION.get(edge_type, edge_type)

            if (src_uid, tgt_uid, relation_type) in existing:
                result.skipped += 1
                result.details.append({
                    "action": "skipped",
                    "source": src_name,
                    "target": tgt_name,
                    "relation_type": relation_type,
                })
                continue

            store.add_relation_edge(
                source_id=src_uid,
                target_id=tgt_uid,
                relation_type=relation_type,
                metadata={
                    "source_name": src_name,
                    "target_name": tgt_name,
                    "seed_edge_type": edge_type,
                },
            )
            existing.add((src_uid, tgt_uid, relation_type))
            result.created += 1
            result.details.append({
                "action": "created",
                "source": src_name,
                "target": tgt_name,
                "relation_type": relation_type,
            })

    except ImportError:
        logger.debug("ontologia or seed module not available", exc_info=True)
    except Exception:
        logger.debug("Edge sync failed (non-fatal)", exc_info=True)

    return result
