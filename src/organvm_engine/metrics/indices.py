"""Composite graph indices — multiplex graph health metrics.

Implements: INST-GRAPH-INDICES, IDX-001 through IDX-005
Resolves: engine #37

Five indices derived from the constitutional corpus:
  CCI — Constitutional Coverage Index (reachability from governance root)
  DDI — Dependency Discipline Index (DAG acyclicity + organ-rank ordering)
  FVI — Feedback Vitality Index (produces/consumes loops = learning capacity)
  CRI — Coupling Risk Index (average degree vs threshold)
  ECI — Evolutionary Coherence Index (governed evolution of archived repos)

Each index returns a float in [0.0, 1.0] plus diagnostic details.
compute_all_indices() consolidates all five.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from organvm_engine.governance.dependency_graph import validate_dependencies
from organvm_engine.registry.query import all_repos

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class IndexReport:
    """Consolidated report of all five graph indices."""

    cci: float = 0.0
    ddi: float = 0.0
    fvi: float = 0.0
    cri: float = 0.0
    eci: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cci": round(self.cci, 4),
            "ddi": round(self.ddi, 4),
            "fvi": round(self.fvi, 4),
            "cri": round(self.cri, 4),
            "eci": round(self.eci, 4),
            "details": self.details,
        }

    def summary(self) -> str:
        lines = [
            "Graph Indices",
            "=" * 40,
            f"  CCI (Constitutional Coverage): {self.cci:.2%}",
            f"  DDI (Dependency Discipline):   {self.ddi:.2%}",
            f"  FVI (Feedback Vitality):        {self.fvi:.4f}",
            f"  CRI (Coupling Risk):            {self.cri:.4f}",
            f"  ECI (Evolutionary Coherence):   {self.eci:.2%}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# IDX-001: Constitutional Coverage Index
# ---------------------------------------------------------------------------

def compute_cci(registry: dict) -> tuple[float, dict[str, Any]]:
    """Fraction of active repos reachable from governance roots.

    BFS from all organ keys (as governance roots) to repos via organ
    membership + dependency edges. CCI = reachable / active.

    Args:
        registry: Loaded registry dict.

    Returns:
        (cci_value, details) — cci_value in [0.0, 1.0].
    """
    # Build adjacency from organs → repos and repos → deps
    adj: dict[str, set[str]] = {}
    active_repos: set[str] = set()
    organs = registry.get("organs", {})

    # Seed roots: all organ keys
    roots: set[str] = set(organs.keys())
    for root in roots:
        adj.setdefault(root, set())

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue

        repo_key = f"{repo.get('org', '')}/{repo.get('name', '')}"
        active_repos.add(repo_key)

        # Organ → repo membership edge
        adj.setdefault(organ_key, set()).add(repo_key)
        adj.setdefault(repo_key, set())

        # Dependency edges
        for dep in repo.get("dependencies", []):
            adj[repo_key].add(dep)
            adj.setdefault(dep, set()).add(repo_key)

    if not active_repos:
        return 1.0, {"active": 0, "reachable": 0, "orphaned": []}

    # BFS from all roots
    visited: set[str] = set()
    queue: deque[str] = deque(roots)
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in adj.get(node, set()):
            if neighbor not in visited:
                queue.append(neighbor)

    reachable = active_repos & visited
    orphaned = sorted(active_repos - visited)
    cci = len(reachable) / len(active_repos) if active_repos else 1.0

    return cci, {
        "active": len(active_repos),
        "reachable": len(reachable),
        "orphaned": orphaned,
    }


# ---------------------------------------------------------------------------
# IDX-002: Dependency Discipline Index
# ---------------------------------------------------------------------------

def compute_ddi(
    registry: dict,
    dependency_edges: list[tuple[str, str]] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Dependency discipline: 1.0 if DAG is acyclic and all edges follow organ-rank.

    Penalized per violation: each cycle or back-edge deducts from 1.0.

    Args:
        registry: Loaded registry dict.
        dependency_edges: Pre-computed edge list, or None to extract from registry.

    Returns:
        (ddi_value, details) — ddi_value in [0.0, 1.0].
    """
    dep_result = validate_dependencies(registry)
    total_edges = max(dep_result.total_edges, 1)  # avoid division by zero

    violation_count = len(dep_result.cycles) + len(dep_result.back_edges)
    penalty = violation_count / total_edges
    ddi = max(0.0, 1.0 - penalty)

    return ddi, {
        "total_edges": dep_result.total_edges,
        "cycles": len(dep_result.cycles),
        "back_edges": len(dep_result.back_edges),
        "violation_count": violation_count,
    }


# ---------------------------------------------------------------------------
# IDX-003: Feedback Vitality Index
# ---------------------------------------------------------------------------

def compute_fvi(
    seed_graph: Any | None = None,
) -> tuple[float, dict[str, Any]]:
    """Count feedback cycles (produces/consumes loops) / active repo count.

    Measures learning capacity: systems with feedback loops between producers
    and consumers can adapt. FVI = unique_feedback_loops / active_repo_count.

    Args:
        seed_graph: A SeedGraph object with nodes and edges.
            If None, returns 0.0 (no seed data available).

    Returns:
        (fvi_value, details).
    """
    if seed_graph is None:
        return 0.0, {"feedback_loops": 0, "active_repos": 0, "loops": []}

    nodes = seed_graph.nodes or []
    edges = seed_graph.edges or []
    active_count = max(len(nodes), 1)

    # Build adjacency from edges (producer → consumer)
    adj: dict[str, set[str]] = defaultdict(set)
    for src, tgt, _artifact_type in edges:
        adj[src].add(tgt)

    # Find feedback loops: A→B and B→A (bidirectional edges = feedback)
    loops: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for src, targets in adj.items():
        for tgt in targets:
            if src in adj.get(tgt, set()):
                pair = (min(src, tgt), max(src, tgt))
                if pair not in seen:
                    seen.add(pair)
                    loops.append(pair)

    fvi = len(loops) / active_count

    return fvi, {
        "feedback_loops": len(loops),
        "active_repos": len(nodes),
        "loops": [{"a": a, "b": b} for a, b in loops],
    }


# ---------------------------------------------------------------------------
# IDX-004: Coupling Risk Index
# ---------------------------------------------------------------------------

def compute_cri(
    dependency_edges: list[tuple[str, str]],
    threshold: int = 6,
) -> tuple[float, dict[str, Any]]:
    """Average (in_degree + out_degree) / threshold. High = over-coupled.

    Args:
        dependency_edges: List of (from_repo, to_repo) tuples.
        threshold: Maximum acceptable total degree per node.

    Returns:
        (cri_value, details) — cri_value where > 1.0 means over-coupled.
    """
    if not dependency_edges:
        return 0.0, {
            "avg_degree": 0.0,
            "threshold": threshold,
            "over_coupled": [],
        }

    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    all_nodes: set[str] = set()

    for src, tgt in dependency_edges:
        out_degree[src] += 1
        in_degree[tgt] += 1
        all_nodes.add(src)
        all_nodes.add(tgt)

    if not all_nodes:
        return 0.0, {"avg_degree": 0.0, "threshold": threshold, "over_coupled": []}

    total_degrees: list[tuple[str, int]] = []
    for node in all_nodes:
        total = in_degree.get(node, 0) + out_degree.get(node, 0)
        total_degrees.append((node, total))

    avg_degree = sum(d for _, d in total_degrees) / len(total_degrees)
    cri = avg_degree / threshold

    over_coupled = sorted(
        [(node, deg) for node, deg in total_degrees if deg > threshold],
        key=lambda x: -x[1],
    )

    return cri, {
        "avg_degree": round(avg_degree, 4),
        "threshold": threshold,
        "node_count": len(all_nodes),
        "over_coupled": [{"node": n, "degree": d} for n, d in over_coupled],
    }


# ---------------------------------------------------------------------------
# IDX-005: Evolutionary Coherence Index
# ---------------------------------------------------------------------------

def compute_eci(registry: dict) -> tuple[float, dict[str, Any]]:
    """Fraction of archived/dissolved repos with structured lineage notes.

    Measures governed evolution: repos that are archived should have a 'note'
    field explaining why (not just freetext) or a non-empty lineage reference.
    ECI = archived_with_lineage / total_archived.

    Args:
        registry: Loaded registry dict.

    Returns:
        (eci_value, details) — eci_value in [0.0, 1.0].
    """
    archived_repos: list[str] = []
    with_lineage: list[str] = []

    for organ_key, repo in all_repos(registry):
        promo_status = repo.get("promotion_status", "")
        impl_status = repo.get("implementation_status", "")

        if promo_status != "ARCHIVED" and impl_status != "ARCHIVED":
            continue

        name = repo.get("name", "?")
        label = f"{organ_key}/{name}"
        archived_repos.append(label)

        # Check for structured lineage: note field with meaningful content
        note = repo.get("note", "")
        lineage = repo.get("lineage", "")
        successor = repo.get("successor", "")

        has_lineage = bool(note and len(note) > 10) or bool(lineage) or bool(successor)
        if has_lineage:
            with_lineage.append(label)

    if not archived_repos:
        # No archived repos — perfect coherence (nothing to govern)
        return 1.0, {
            "total_archived": 0,
            "with_lineage": 0,
            "missing_lineage": [],
        }

    eci = len(with_lineage) / len(archived_repos)
    missing = sorted(set(archived_repos) - set(with_lineage))

    return eci, {
        "total_archived": len(archived_repos),
        "with_lineage": len(with_lineage),
        "missing_lineage": missing,
    }


# ---------------------------------------------------------------------------
# Consolidated computation
# ---------------------------------------------------------------------------

def compute_all_indices(
    registry: dict,
    dependency_edges: list[tuple[str, str]] | None = None,
    seed_graph: Any | None = None,
    coupling_threshold: int = 6,
) -> IndexReport:
    """Compute all five graph indices from registry + seed graph.

    Args:
        registry: Loaded registry dict.
        dependency_edges: Pre-computed dependency edge list. If None,
            extracted from registry.
        seed_graph: A SeedGraph with nodes and edges. If None, FVI = 0.
        coupling_threshold: Max acceptable total degree for CRI.

    Returns:
        IndexReport with all five values + diagnostic details.
    """
    # Extract dependency edges from registry if not provided
    if dependency_edges is None:
        dependency_edges = []
        for _organ_key, repo in all_repos(registry):
            repo_key = f"{repo.get('org', '')}/{repo.get('name', '')}"
            for dep in repo.get("dependencies", []):
                dependency_edges.append((repo_key, dep))

    report = IndexReport()

    cci_val, cci_details = compute_cci(registry)
    report.cci = cci_val
    report.details["cci"] = cci_details

    ddi_val, ddi_details = compute_ddi(registry, dependency_edges)
    report.ddi = ddi_val
    report.details["ddi"] = ddi_details

    fvi_val, fvi_details = compute_fvi(seed_graph)
    report.fvi = fvi_val
    report.details["fvi"] = fvi_details

    cri_val, cri_details = compute_cri(dependency_edges, coupling_threshold)
    report.cri = cri_val
    report.details["cri"] = cri_details

    eci_val, eci_details = compute_eci(registry)
    report.eci = eci_val
    report.details["eci"] = eci_details

    return report
