"""Temporal versioning for the dependency graph.

Tracks when edges were added and removed so you can reconstruct the graph
state at any historical point in time, and diff two snapshots to see how
edges evolved.

Implements GitHub issue #8: Add temporal versioning to dependency graph.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TemporalEdge:
    """A dependency edge annotated with lifecycle timestamps.

    Attributes:
        source: Fully-qualified repo key (``org/name``).
        target: Fully-qualified repo key (``org/name``).
        created_at: ISO-8601 timestamp when the edge was first recorded.
        removed_at: ISO-8601 timestamp when the edge was removed, or ``None``
            if it is still active.
        source_status: Promotion status of the source repo when the edge was
            recorded (e.g. ``"LOCAL"``, ``"CANDIDATE"``).  Optional context.
        target_status: Promotion status of the target repo when the edge was
            recorded.  Optional context.
    """

    source: str
    target: str
    created_at: str
    removed_at: str | None = None
    source_status: str | None = None
    target_status: str | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_active_at(self, timestamp: str) -> bool:
        """Return True if this edge was active at *timestamp* (inclusive)."""
        if self.created_at > timestamp:
            return False
        return not (self.removed_at is not None and self.removed_at <= timestamp)

    @property
    def is_active(self) -> bool:
        """Return True if the edge has not been removed."""
        return self.removed_at is None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Drop None fields for cleaner serialization
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class GraphDiff:
    """Edges added and removed between two points in time.

    Attributes:
        t1: Start of the comparison window (ISO-8601).
        t2: End of the comparison window (ISO-8601).
        added: Edges whose ``created_at`` falls in (t1, t2].
        removed: Edges whose ``removed_at`` falls in (t1, t2].
    """

    t1: str
    t2: str
    added: list[TemporalEdge] = field(default_factory=list)
    removed: list[TemporalEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "t1": self.t1,
            "t2": self.t2,
            "added": [e.to_dict() for e in self.added],
            "removed": [e.to_dict() for e in self.removed],
        }


@dataclass
class TemporalGraph:
    """Append-only temporal dependency graph.

    All mutations go through :meth:`record_snapshot` which compares the
    live edge set against the currently-active temporal edges and emits
    the appropriate add/remove events.  The underlying list of
    :class:`TemporalEdge` instances is the single source of truth.
    """

    edges: list[TemporalEdge] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Snapshot ingestion
    # ------------------------------------------------------------------

    def record_snapshot(
        self,
        live_edges: list[tuple[str, str]],
        timestamp: str | None = None,
        status_map: dict[str, str] | None = None,
    ) -> tuple[list[TemporalEdge], list[TemporalEdge]]:
        """Reconcile *live_edges* against the current graph state.

        Args:
            live_edges: The complete set of ``(source, target)`` edges that
                exist right now in the registry.
            timestamp: ISO-8601 timestamp for this snapshot.  Defaults to
                ``datetime.now(UTC).isoformat()``.
            status_map: Optional mapping of ``org/name`` -> promotion status,
                used to annotate new edges.

        Returns:
            A ``(added, removed)`` tuple of :class:`TemporalEdge` lists.
        """
        if timestamp is None:
            timestamp = _now_iso()

        status_map = status_map or {}

        live_set = set(live_edges)
        active: dict[tuple[str, str], TemporalEdge] = {}
        for e in self.edges:
            if e.is_active:
                active[(e.source, e.target)] = e

        added: list[TemporalEdge] = []
        removed: list[TemporalEdge] = []

        # New edges: present in live but not currently active
        for src, tgt in live_set:
            if (src, tgt) not in active:
                edge = TemporalEdge(
                    source=src,
                    target=tgt,
                    created_at=timestamp,
                    source_status=status_map.get(src),
                    target_status=status_map.get(tgt),
                )
                self.edges.append(edge)
                added.append(edge)

        # Removed edges: currently active but missing from live
        for key, edge in active.items():
            if key not in live_set:
                # Replace the frozen dataclass with an updated copy
                updated = TemporalEdge(
                    source=edge.source,
                    target=edge.target,
                    created_at=edge.created_at,
                    removed_at=timestamp,
                    source_status=edge.source_status,
                    target_status=edge.target_status,
                )
                idx = self.edges.index(edge)
                self.edges[idx] = updated
                removed.append(updated)

        return added, removed

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def graph_at(self, timestamp: str) -> list[TemporalEdge]:
        """Return all edges that were active at *timestamp*."""
        return [e for e in self.edges if e.is_active_at(timestamp)]

    def graph_diff(self, t1: str, t2: str) -> GraphDiff:
        """Return edges added and removed in the half-open interval (t1, t2].

        An edge counts as *added* if ``t1 < created_at <= t2``.
        An edge counts as *removed* if ``t1 < removed_at <= t2``.
        """
        added: list[TemporalEdge] = []
        removed: list[TemporalEdge] = []

        for e in self.edges:
            if t1 < e.created_at <= t2:
                added.append(e)
            if e.removed_at is not None and t1 < e.removed_at <= t2:
                removed.append(e)

        return GraphDiff(t1=t1, t2=t2, added=added, removed=removed)

    def active_edges(self) -> list[TemporalEdge]:
        """Return all currently-active (non-removed) edges."""
        return [e for e in self.edges if e.is_active]

    def edge_history(self, source: str, target: str) -> list[TemporalEdge]:
        """Return all temporal records for a specific source->target pair."""
        return [
            e for e in self.edges
            if e.source == source and e.target == target
        ]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Write the temporal graph to a JSON file."""
        data = {
            "version": "1.0",
            "generated_at": _now_iso(),
            "edges": [e.to_dict() for e in self.edges],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> TemporalGraph:
        """Load a temporal graph from a JSON file."""
        data = json.loads(path.read_text())
        edges = [
            TemporalEdge(
                source=e["source"],
                target=e["target"],
                created_at=e["created_at"],
                removed_at=e.get("removed_at"),
                source_status=e.get("source_status"),
                target_status=e.get("target_status"),
            )
            for e in data.get("edges", [])
        ]
        return cls(edges=edges)

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "edge_count": len(self.edges),
            "active_count": len(self.active_edges()),
            "edges": [e.to_dict() for e in self.edges],
        }


# ------------------------------------------------------------------
# Registry helpers
# ------------------------------------------------------------------

def extract_edges_from_registry(registry: dict) -> tuple[
    list[tuple[str, str]], dict[str, str],
]:
    """Pull live edges and promotion-status map from a registry dict.

    Returns:
        ``(edges, status_map)`` where *edges* is a list of
        ``(source, target)`` tuples and *status_map* maps
        ``org/name`` to promotion status.
    """
    from organvm_engine.registry.query import all_repos

    edges: list[tuple[str, str]] = []
    status_map: dict[str, str] = {}

    for _organ_key, repo in all_repos(registry):
        key = f"{repo['org']}/{repo['name']}"
        status_map[key] = repo.get("promotion_status", "LOCAL")
        for dep in repo.get("dependencies", []):
            edges.append((key, dep))

    return edges, status_map


def record_registry_snapshot(
    graph: TemporalGraph,
    registry: dict,
    timestamp: str | None = None,
) -> tuple[list[TemporalEdge], list[TemporalEdge]]:
    """Convenience: extract edges from *registry* and record them.

    Returns:
        ``(added, removed)`` edge lists.
    """
    live_edges, status_map = extract_edges_from_registry(registry)
    return graph.record_snapshot(live_edges, timestamp=timestamp, status_map=status_map)


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
