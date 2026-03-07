"""Plan graph — compute edges between plans for overlap and dependency detection.

Pure computation over PlanEntry data; no I/O beyond what the index already captured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from organvm_engine.plans.index import PlanEntry


@dataclass
class PlanOverlap:
    """A cluster of overlapping plans detected via domain fingerprint similarity."""

    domain: str
    plans: list[str]  # qualified_ids
    agents: list[str]
    organs: list[str]
    severity: str  # info | warning | conflict
    jaccard: float = 0.0


@dataclass
class PlanEdge:
    """A directed edge between two plans."""

    source: str  # qualified_id
    target: str  # qualified_id
    edge_type: str  # supersedes | overlaps | same-domain | cross-organ | parent-child
    weight: float = 1.0


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _domain_set(entry: "PlanEntry") -> set[str]:
    """Build the domain set for overlap comparison: normalized tags + file_refs."""
    from organvm_engine.domain import domain_set
    return domain_set(entry.tags, entry.file_refs)


def compute_overlaps(
    entries: list["PlanEntry"],
    threshold: float = 0.3,
) -> list[PlanOverlap]:
    """Detect overlapping plan clusters via pairwise Jaccard similarity.

    Args:
        entries: Active PlanEntry objects to compare.
        threshold: Minimum Jaccard to consider an overlap.

    Returns:
        List of PlanOverlap clusters, sorted by severity descending.
    """
    if len(entries) < 2:
        return []

    # Precompute domain sets
    domains = [(e, _domain_set(e)) for e in entries]

    # Pairwise comparison — cluster overlapping pairs
    pairs: list[tuple[PlanEntry, PlanEntry, float]] = []
    for i in range(len(domains)):
        e_a, set_a = domains[i]
        if not set_a:
            continue
        for j in range(i + 1, len(domains)):
            e_b, set_b = domains[j]
            if not set_b:
                continue
            j_sim = jaccard_similarity(set_a, set_b)
            if j_sim >= threshold:
                pairs.append((e_a, e_b, j_sim))

    # Group into overlap clusters using union-find
    clusters = _cluster_pairs(pairs)

    overlaps: list[PlanOverlap] = []
    for cluster_entries, max_jaccard in clusters:
        plan_ids = sorted(set(e.qualified_id for e in cluster_entries))
        agents = sorted(set(e.agent for e in cluster_entries))
        organs = sorted(set(e.organ or "?" for e in cluster_entries))

        # Determine severity
        if max_jaccard > 0.6 and len(agents) > 1:
            severity = "conflict"
        elif max_jaccard > 0.4 or len(agents) > 1:
            severity = "warning"
        else:
            severity = "info"

        # Build domain description from common tags
        all_tags: set[str] = set()
        for e in cluster_entries:
            all_tags.update(e.tags)
        domain_desc = ", ".join(sorted(all_tags)[:5]) if all_tags else "shared file refs"

        overlaps.append(PlanOverlap(
            domain=domain_desc,
            plans=plan_ids,
            agents=agents,
            organs=organs,
            severity=severity,
            jaccard=round(max_jaccard, 3),
        ))

    # Sort: conflict first, then warning, then info
    severity_order = {"conflict": 0, "warning": 1, "info": 2}
    overlaps.sort(key=lambda o: (severity_order.get(o.severity, 3), -o.jaccard))
    return overlaps


def _cluster_pairs(
    pairs: list[tuple["PlanEntry", "PlanEntry", float]],
) -> list[tuple[list["PlanEntry"], float]]:
    """Union-find clustering of overlapping pairs."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    entry_map: dict[str, "PlanEntry"] = {}
    max_j: dict[str, float] = {}

    for e_a, e_b, j_sim in pairs:
        entry_map[e_a.qualified_id] = e_a
        entry_map[e_b.qualified_id] = e_b
        union(e_a.qualified_id, e_b.qualified_id)
        # Track max jaccard per cluster root
        root = find(e_a.qualified_id)
        max_j[root] = max(max_j.get(root, 0), j_sim)

    # Group by root
    groups: dict[str, list["PlanEntry"]] = {}
    for qid, entry in entry_map.items():
        root = find(qid)
        groups.setdefault(root, []).append(entry)
        # Re-track max_j after path compression
        if root not in max_j:
            max_j[root] = 0

    # Recompute max jaccard per final root
    final_max: dict[str, float] = {}
    for e_a, _e_b, j_sim in pairs:
        root = find(e_a.qualified_id)
        final_max[root] = max(final_max.get(root, 0), j_sim)

    return [(members, final_max.get(root, 0)) for root, members in groups.items()]


def compute_edges(entries: list["PlanEntry"]) -> list[PlanEdge]:
    """Compute all edge types between plans.

    Edge types:
    - supersedes: Same slug, higher version
    - same-domain: Same (organ, repo), different agents
    - cross-organ: Plan's file_refs contain paths from another organ's directory
    - parent-child: Agent subplan pattern (-agent-aXXX suffix)
    """
    import re

    from organvm_engine.organ_config import organ_dir_map

    edges: list[PlanEdge] = []
    dir_map = organ_dir_map()  # key → dir
    dir_to_key = {v: k for k, v in dir_map.items()}

    # Index by slug for supersedes detection
    by_slug: dict[str, list["PlanEntry"]] = {}
    for e in entries:
        base_slug = re.sub(r"-v\d+$", "", e.slug)
        by_slug.setdefault(base_slug, []).append(e)

    # Supersedes edges
    for _slug, group in by_slug.items():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda x: x.version)
        for i in range(1, len(sorted_group)):
            edges.append(PlanEdge(
                source=sorted_group[i].qualified_id,
                target=sorted_group[i - 1].qualified_id,
                edge_type="supersedes",
            ))

    # Same-domain edges (same organ+repo, different agents)
    by_domain: dict[tuple[str | None, str | None], list["PlanEntry"]] = {}
    for e in entries:
        by_domain.setdefault((e.organ, e.repo), []).append(e)

    for (organ, repo), group in by_domain.items():
        if organ is None and repo is None:
            continue
        agents = set(e.agent for e in group)
        if len(agents) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if group[i].agent != group[j].agent:
                        edges.append(PlanEdge(
                            source=group[i].qualified_id,
                            target=group[j].qualified_id,
                            edge_type="same-domain",
                        ))

    # Cross-organ edges
    for e in entries:
        if not e.file_refs:
            continue
        for ref in e.file_refs:
            for organ_dir, organ_key in dir_to_key.items():
                if ref.startswith(organ_dir + "/") and organ_key != e.organ:
                    edges.append(PlanEdge(
                        source=e.qualified_id,
                        target=f"organ:{organ_key}",
                        edge_type="cross-organ",
                    ))
                    break  # One edge per ref

    # Parent-child edges
    subplan_re = re.compile(r"-agent-a[0-9a-f]+$", re.IGNORECASE)
    for e in entries:
        if subplan_re.search(e.slug):
            parent_slug = subplan_re.sub("", e.slug)
            # Find parent
            for candidate in entries:
                if candidate.slug == parent_slug and candidate.agent == e.agent:
                    edges.append(PlanEdge(
                        source=candidate.qualified_id,
                        target=e.qualified_id,
                        edge_type="parent-child",
                    ))
                    break

    return edges
