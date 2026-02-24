"""Impact Analysis / Blast Radius Calculator.

Determines which repositories might be affected by changes to a given repo.
Combines explicit registry dependencies with implicit seed.yaml data flow edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from organvm_engine.registry.query import all_repos
from organvm_engine.seed.graph import build_seed_graph


@dataclass
class ImpactReport:
    source_repo: str
    affected_repos: list[str] = field(default_factory=list)
    impact_graph: dict[str, list[str]] = field(default_factory=dict)
    
    def summary(self) -> str:
        lines = [f"Impact Analysis for: {self.source_repo}"]
        if not self.affected_repos:
            lines.append("  No downstream dependencies found.")
            return "\n".join(lines)

        lines.append(f"  {len(self.affected_repos)} repositories affected:")
        for repo in sorted(self.affected_repos):
            lines.append(f"    - {repo}")

        lines.append("\n  Propagation Path:")
        # Simple BFS print
        queue = [(self.source_repo, 0)]
        visited = {self.source_repo}
        while queue:
            current, depth = queue.pop(0)
            if depth > 0:
                lines.append(f"    {'  ' * depth}↳ {current}")

            for child in self.affected_repos:
                if child in self.impact_graph.get(current, []) and child not in visited:
                    visited.add(child)
                    queue.append((child, depth + 1))

        return "\n".join(lines)


def calculate_impact(
    repo_name: str,
    registry: dict,
    workspace_path: str | None = None
) -> ImpactReport:
    """Calculate the downstream impact of a change to repo_name."""
    
    # 1. Build Adjacency List (A -> B means A affects B)
    # This is the reverse of "dependencies" (A depends on B means B affects A)
    adjacency: dict[str, set[str]] = {}
    
    # Add Registry Dependencies (Explicit)
    # If R depends on D, then D affects R.
    # Registry has "dependencies": ["org/dep"]
    for organ_key, repo in all_repos(registry):
        name = repo.get("name")
        deps = repo.get("dependencies", []) or []
        for dep in deps:
            # dep might be "org/repo" or just "repo"
            dep_name = dep.split("/")[-1]
            if dep_name not in adjacency:
                adjacency[dep_name] = set()
            adjacency[dep_name].add(name)
            
    # Add Seed Edges (Implicit Data Flow)
    # If Producer P produces Type T, and Consumer C consumes Type T from P:
    # Then P affects C.
    seed_graph = build_seed_graph(workspace_path)
    for producer, consumer, artifact_type in seed_graph.edges:
        # identities are "org/repo"
        p_name = producer.split("/")[-1]
        c_name = consumer.split("/")[-1]
        
        if p_name not in adjacency:
            adjacency[p_name] = set()
        adjacency[p_name].add(c_name)
        
    # 2. Traverse Graph (BFS)
    affected = set()
    impact_graph = {}
    
    queue = [repo_name]
    visited = {repo_name}
    
    while queue:
        current = queue.pop(0)
        downstream = adjacency.get(current, set())
        
        impact_graph[current] = list(downstream)
        
        for neighbor in downstream:
            if neighbor not in visited:
                visited.add(neighbor)
                affected.add(neighbor)
                queue.append(neighbor)
                
    return ImpactReport(
        source_repo=repo_name,
        affected_repos=list(affected),
        impact_graph=impact_graph
    )
