"""Build produces/consumes graph from all seed.yaml files."""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.seed.discover import discover_seeds
from organvm_engine.seed.reader import get_consumes, get_produces, read_seed, seed_identity


@dataclass
class SeedGraph:
    """Graph of produces/consumes relationships across all seeds."""

    nodes: list[str] = field(default_factory=list)
    produces: dict[str, list[dict]] = field(default_factory=dict)
    consumes: dict[str, list[dict]] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Seed Graph: {len(self.nodes)} repos, {len(self.edges)} edges",
        ]
        if self.edges:
            lines.append("\nProduces/Consumes edges:")
            for src, tgt, artifact_type in self.edges:
                lines.append(f"  {src} --[{artifact_type}]--> {tgt}")
        if self.errors:
            lines.append(f"\nErrors: {len(self.errors)}")
            for e in self.errors:
                lines.append(f"  {e}")
        return "\n".join(lines)


def build_seed_graph(
    workspace: Path | str | None = None,
    orgs: list[str] | None = None,
) -> SeedGraph:
    """Build a graph from all seed.yaml produces/consumes declarations.

    Args:
        workspace: Root workspace directory.
        orgs: Org directories to scan.

    Returns:
        SeedGraph with nodes, edges, and any parse errors.
    """
    graph = SeedGraph()
    seed_paths = discover_seeds(workspace, orgs)

    # Parse all seeds
    seeds_by_identity: dict[str, dict] = {}
    for path in seed_paths:
        try:
            seed = read_seed(path)
            identity = seed_identity(seed)
            seeds_by_identity[identity] = seed
            graph.nodes.append(identity)
        except Exception as e:
            graph.errors.append(f"{path}: {e}")

    # Index producers by type
    producers_by_type: dict[str, list[str]] = defaultdict(list)
    for identity, seed in seeds_by_identity.items():
        for p in get_produces(seed):
            if isinstance(p, str):
                ptype = "unknown"
            else:
                ptype = p.get("type", "unknown")
            graph.produces.setdefault(identity, []).append(p)
            producers_by_type[ptype].append(identity)

    # Build edges from consumes
    for identity, seed in seeds_by_identity.items():
        for c in get_consumes(seed):
            if isinstance(c, str):
                ctype = "unknown"
                source = ""
            else:
                ctype = c.get("type", "unknown")
                source = c.get("source", "")
            graph.consumes.setdefault(identity, []).append(c)

            # Find matching producers, filtering by source when specified
            for producer in producers_by_type.get(ctype, []):
                if producer == identity:
                    continue
                if source:
                    # Match on org prefix or full identity
                    producer_org = producer.split("/")[0] if "/" in producer else ""
                    if source != producer and source != producer_org:
                        continue
                graph.edges.append((producer, identity, ctype))

    return graph
