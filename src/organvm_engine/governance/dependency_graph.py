"""Dependency graph validation — cycle detection, back-edge checking, DAG analysis.

Implements: AX-008 (Multiplex Flow Governance) — typed edge support.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from organvm_engine.registry.query import all_repos

# Organ ordering for back-edge detection
# Flow: I -> II -> III. IV-VII + Meta can reference anything.
ORGAN_LEVELS = {
    "organvm-i-theoria": 1,
    "organvm-ii-poiesis": 2,
    "organvm-iii-ergon": 3,
    "organvm-iv-taxis": 4,
    "organvm-v-logos": 5,
    "organvm-vi-koinonia": 6,
    "organvm-vii-kerygma": 7,
    "meta-organvm": 8,
}
RESTRICTED_LEVELS = {1, 2, 3}


class FlowType(Enum):
    """Types of inter-repo flow in the multiplex graph.

    AX-008 requires distinguishing at least four flow types:
    - DEPENDENCY: build/runtime dependency (the only type previously tracked)
    - INFORMATION: data/artifact flow (produces/consumes from seed.yaml)
    - GOVERNANCE: policy propagation (governance rules, dictums, audit)
    - EVOLUTION: promotion state transitions and lifecycle events
    """

    DEPENDENCY = "dependency"
    INFORMATION = "information"
    GOVERNANCE = "governance"
    EVOLUTION = "evolution"


@dataclass
class TypedEdge:
    """An edge in the multiplex graph with a flow type annotation."""

    source: str
    target: str
    flow_type: FlowType

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypedEdge):
            return NotImplemented
        return (
            self.source == other.source
            and self.target == other.target
            and self.flow_type == other.flow_type
        )

    def __hash__(self) -> int:
        return hash((self.source, self.target, self.flow_type))


@dataclass
class MultiplexGraph:
    """Multiplex graph containing typed edges across all flow layers.

    Each flow type forms an independent graph layer with its own edge set.
    The legacy dependency-only graph is the DEPENDENCY layer.
    """

    edges: list[TypedEdge] = field(default_factory=list)

    def edges_by_type(self, flow_type: FlowType) -> list[TypedEdge]:
        """Return edges filtered to a single flow type."""
        return [e for e in self.edges if e.flow_type == flow_type]

    def layer_counts(self) -> dict[str, int]:
        """Return edge count per flow type."""
        counts: dict[str, int] = {}
        for ft in FlowType:
            n = sum(1 for e in self.edges if e.flow_type == ft)
            if n > 0:
                counts[ft.value] = n
        return counts

    def nodes(self) -> set[str]:
        """Return all unique node identifiers across all layers."""
        result: set[str] = set()
        for e in self.edges:
            result.add(e.source)
            result.add(e.target)
        return result

    def summary(self) -> str:
        """Human-readable summary of the multiplex graph."""
        counts = self.layer_counts()
        total = len(self.edges)
        lines = [f"Multiplex graph: {total} edges across {len(counts)} layer(s)"]
        for layer, count in sorted(counts.items()):
            lines.append(f"  {layer}: {count} edge(s)")
        return "\n".join(lines)


def build_multiplex_graph(
    registry: dict,
    seed_graph: object | None = None,
) -> MultiplexGraph:
    """Build a multiplex graph from registry dependency edges and optional seed graph.

    The registry provides DEPENDENCY edges (from repo dependencies fields).
    If a SeedGraph is provided, its produces/consumes edges become INFORMATION edges.

    Args:
        registry: Loaded registry dict.
        seed_graph: Optional SeedGraph instance (from seed.graph.build_seed_graph).

    Returns:
        MultiplexGraph with typed edges.
    """
    graph = MultiplexGraph()

    # Layer 1: DEPENDENCY edges from registry
    for _organ_key, repo in all_repos(registry):
        key = f"{repo['org']}/{repo['name']}"
        for dep in repo.get("dependencies", []):
            graph.edges.append(TypedEdge(source=key, target=dep, flow_type=FlowType.DEPENDENCY))

    # Layer 2: INFORMATION edges from seed graph (produces/consumes)
    if seed_graph is not None:
        seed_edges = getattr(seed_graph, "edges", [])
        for edge in seed_edges:
            if len(edge) >= 2:
                graph.edges.append(
                    TypedEdge(source=edge[0], target=edge[1], flow_type=FlowType.INFORMATION),
                )

    return graph


@dataclass
class DependencyResult:
    """Result of dependency graph validation."""

    total_edges: int = 0
    missing_targets: list[tuple[str, str]] = field(default_factory=list)
    self_deps: list[str] = field(default_factory=list)
    back_edges: list[tuple[str, str, str, str]] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    cross_organ: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (
            len(self.missing_targets) == 0
            and len(self.self_deps) == 0
            and len(self.back_edges) == 0
            and len(self.cycles) == 0
        )

    @property
    def violations(self) -> list[str]:
        v = []
        for f, t in self.missing_targets:
            v.append(f"Missing target: {f} -> {t}")
        for s in self.self_deps:
            v.append(f"Self-dep: {s}")
        for f, t, fo, to in self.back_edges:
            v.append(f"Back-edge: {f} -> {t} ({fo} -> {to})")
        for c in self.cycles:
            v.append(f"Cycle: {' -> '.join(c)}")
        return v


def validate_dependencies(registry: dict) -> DependencyResult:
    """Validate the dependency graph from a registry.

    Checks:
    1. All dependency targets exist
    2. No self-dependencies
    3. No back-edges in I->II->III chain
    4. No circular dependencies

    Args:
        registry: Loaded registry dict.

    Returns:
        DependencyResult with all findings.
    """
    result = DependencyResult()

    # Build repo map and edge list
    repo_map: dict[str, dict] = {}
    edges: list[tuple[str, str]] = []

    for _organ_key, repo in all_repos(registry):
        key = f"{repo['org']}/{repo['name']}"
        repo_map[key] = repo
        for dep in repo.get("dependencies", []):
            edges.append((key, dep))
            result.total_edges += 1

    # Check 1: Targets exist
    for from_key, to_key in edges:
        if to_key not in repo_map:
            result.missing_targets.append((from_key, to_key))

    # Check 2: Self-deps
    for from_key, to_key in edges:
        if from_key == to_key:
            result.self_deps.append(from_key)

    # Check 3: Back-edges
    for from_key, to_key in edges:
        from_org = from_key.split("/")[0]
        to_org = to_key.split("/")[0]
        from_level = ORGAN_LEVELS.get(from_org)
        to_level = ORGAN_LEVELS.get(to_org)

        if from_level is None or to_level is None:
            continue

        if (
            from_level in RESTRICTED_LEVELS
            and to_level in RESTRICTED_LEVELS
            and from_level < to_level
        ):
            result.back_edges.append((from_key, to_key, from_org, to_org))

    # Check 4: Cycle detection (DFS with coloring)
    adj: dict[str, list[str]] = defaultdict(list)
    for from_key, to_key in edges:
        adj[from_key].append(to_key)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = defaultdict(lambda: WHITE)

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in adj[node]:
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                result.cycles.append(path[cycle_start:] + [neighbor])
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for node in repo_map:
        if color[node] == WHITE:
            dfs(node, [])

    # Cross-organ summary
    cross: dict[str, int] = defaultdict(int)
    for from_key, to_key in edges:
        from_org = from_key.split("/")[0]
        to_org = to_key.split("/")[0]
        if from_org != to_org:
            cross[f"{from_org} -> {to_org}"] += 1
    result.cross_organ = dict(cross)

    # Emit violation events if any found
    if not result.passed:
        try:
            from organvm_engine.pulse.emitter import emit_engine_event
            from organvm_engine.pulse.types import DEPENDENCY_VIOLATION

            emit_engine_event(
                event_type=DEPENDENCY_VIOLATION,
                source="governance",
                payload={
                    "back_edges": len(result.back_edges),
                    "cycles": len(result.cycles),
                    "missing_targets": len(result.missing_targets),
                    "violations": result.violations[:10],
                },
            )
        except Exception:
            pass

    return result
