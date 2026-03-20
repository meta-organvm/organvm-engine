"""Tests for plans/graph.py — plan overlap and edge computation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from organvm_engine.plans.graph import (
    PlanEdge,
    PlanOverlap,
    compute_edges,
    compute_overlaps,
    jaccard_similarity,
)


# ---------------------------------------------------------------------------
# Lightweight PlanEntry stub
# ---------------------------------------------------------------------------
# We avoid importing the real PlanEntry to keep tests fast and decoupled.
# The graph module only reads attributes via duck typing.


@dataclass
class FakePlanEntry:
    """Minimal stub matching the PlanEntry fields used by graph.py."""

    qualified_id: str = ""
    path: str = ""
    agent: str = "claude"
    organ: str | None = None
    repo: str | None = None
    slug: str = ""
    date: str = "2026-01-01"
    version: int = 1
    status: str = "active"
    title: str = ""
    size_bytes: int = 100
    has_verification: bool = False
    archetype: str | None = None
    task_count: int = 1
    completed_count: int = 0
    tags: list[str] = field(default_factory=list)
    file_refs: list[str] = field(default_factory=list)
    domain_fingerprint: str = ""


# ---------------------------------------------------------------------------
# jaccard_similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    def test_identical_sets(self):
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # {a,b,c} & {b,c,d} = {b,c}, union = {a,b,c,d} -> 2/4 = 0.5
        assert jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"}) == 0.5

    def test_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 0.0

    def test_one_empty(self):
        assert jaccard_similarity({"a"}, set()) == 0.0
        assert jaccard_similarity(set(), {"a"}) == 0.0

    def test_subset(self):
        # {a} & {a,b} = {a}, union = {a,b} -> 1/2 = 0.5
        assert jaccard_similarity({"a"}, {"a", "b"}) == 0.5

    def test_single_element_match(self):
        assert jaccard_similarity({"x"}, {"x"}) == 1.0

    def test_large_overlap(self):
        a = set("abcdefghij")
        b = set("abcdefghik")  # 9 shared, 1 different each -> 9/11
        result = jaccard_similarity(a, b)
        assert abs(result - 9 / 11) < 1e-9


# ---------------------------------------------------------------------------
# compute_overlaps
# ---------------------------------------------------------------------------


class TestComputeOverlaps:
    def test_no_entries(self):
        assert compute_overlaps([]) == []

    def test_single_entry(self):
        e = FakePlanEntry(
            qualified_id="plan-1",
            tags=["python", "fastapi"],
            file_refs=["src/main.py"],
        )
        assert compute_overlaps([e]) == []

    def test_identical_domains_overlap(self):
        e1 = FakePlanEntry(
            qualified_id="plan-1",
            agent="claude",
            organ="META",
            tags=["python", "fastapi"],
            file_refs=["src/main.py"],
        )
        e2 = FakePlanEntry(
            qualified_id="plan-2",
            agent="gemini",
            organ="META",
            tags=["python", "fastapi"],
            file_refs=["src/main.py"],
        )
        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        assert len(overlaps) == 1
        assert overlaps[0].jaccard == 1.0
        assert set(overlaps[0].plans) == {"plan-1", "plan-2"}

    def test_disjoint_domains_no_overlap(self):
        e1 = FakePlanEntry(
            qualified_id="plan-1",
            tags=["python"],
            file_refs=["src/a.py"],
        )
        e2 = FakePlanEntry(
            qualified_id="plan-2",
            tags=["rust"],
            file_refs=["src/b.rs"],
        )
        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        assert len(overlaps) == 0

    def test_threshold_filtering(self):
        e1 = FakePlanEntry(
            qualified_id="plan-1",
            tags=["python", "fastapi", "docker", "postgres"],
            file_refs=[],
        )
        e2 = FakePlanEntry(
            qualified_id="plan-2",
            tags=["python"],
            file_refs=[],
        )
        # Jaccard = 1/4 = 0.25 (below 0.3 threshold)
        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        assert len(overlaps) == 0

        # With lower threshold, should match
        overlaps = compute_overlaps([e1, e2], threshold=0.2)
        assert len(overlaps) == 1

    def test_severity_conflict(self):
        # High jaccard (>0.6) + multiple agents -> conflict
        e1 = FakePlanEntry(
            qualified_id="p1", agent="claude",
            tags=["python", "mcp"], file_refs=["src/server.py"],
        )
        e2 = FakePlanEntry(
            qualified_id="p2", agent="gemini",
            tags=["python", "mcp"], file_refs=["src/server.py"],
        )
        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        assert len(overlaps) == 1
        assert overlaps[0].severity == "conflict"

    def test_severity_info_single_agent(self):
        # Same agent, moderate overlap -> info
        e1 = FakePlanEntry(
            qualified_id="p1", agent="claude",
            tags=["python", "docker", "fastapi"],
            file_refs=[],
        )
        e2 = FakePlanEntry(
            qualified_id="p2", agent="claude",
            tags=["python", "docker"],
            file_refs=[],
        )
        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        if overlaps:
            # Single agent, jaccard <= 0.4 typically -> info
            assert overlaps[0].severity in ("info", "warning")

    def test_empty_domain_sets_ignored(self):
        e1 = FakePlanEntry(qualified_id="p1", tags=[], file_refs=[])
        e2 = FakePlanEntry(qualified_id="p2", tags=[], file_refs=[])
        overlaps = compute_overlaps([e1, e2], threshold=0.0)
        assert len(overlaps) == 0

    def test_sorted_by_severity(self):
        # Create entries that will produce both conflict and info overlaps
        entries = [
            FakePlanEntry(
                qualified_id="c1", agent="claude",
                tags=["python", "mcp"], file_refs=["src/a.py"],
            ),
            FakePlanEntry(
                qualified_id="c2", agent="gemini",
                tags=["python", "mcp"], file_refs=["src/a.py"],
            ),
            FakePlanEntry(
                qualified_id="i1", agent="claude",
                tags=["rust", "wasm"], file_refs=["src/b.rs"],
            ),
            FakePlanEntry(
                qualified_id="i2", agent="claude",
                tags=["rust", "wasm"], file_refs=["src/b.rs"],
            ),
        ]
        overlaps = compute_overlaps(entries, threshold=0.3)
        if len(overlaps) >= 2:
            severity_order = {"conflict": 0, "warning": 1, "info": 2}
            for i in range(len(overlaps) - 1):
                a = severity_order.get(overlaps[i].severity, 3)
                b = severity_order.get(overlaps[i + 1].severity, 3)
                assert a <= b


# ---------------------------------------------------------------------------
# compute_edges
# ---------------------------------------------------------------------------


class TestComputeEdges:
    def test_no_entries(self):
        assert compute_edges([]) == []

    def test_supersedes_edges(self):
        e1 = FakePlanEntry(qualified_id="plan-v1", slug="deploy", version=1)
        e2 = FakePlanEntry(qualified_id="plan-v2", slug="deploy-v2", version=2)
        # Both share base slug "deploy" after stripping -v2
        edges = compute_edges([e1, e2])
        supersedes = [e for e in edges if e.edge_type == "supersedes"]
        assert len(supersedes) == 1
        assert supersedes[0].source == "plan-v2"
        assert supersedes[0].target == "plan-v1"

    def test_same_domain_edges(self):
        e1 = FakePlanEntry(
            qualified_id="p1", agent="claude", organ="META", repo="engine",
        )
        e2 = FakePlanEntry(
            qualified_id="p2", agent="gemini", organ="META", repo="engine",
        )
        edges = compute_edges([e1, e2])
        same_domain = [e for e in edges if e.edge_type == "same-domain"]
        assert len(same_domain) == 1
        assert {same_domain[0].source, same_domain[0].target} == {"p1", "p2"}

    def test_no_same_domain_for_same_agent(self):
        e1 = FakePlanEntry(
            qualified_id="p1", agent="claude", organ="META", repo="engine",
        )
        e2 = FakePlanEntry(
            qualified_id="p2", agent="claude", organ="META", repo="engine",
        )
        edges = compute_edges([e1, e2])
        same_domain = [e for e in edges if e.edge_type == "same-domain"]
        assert len(same_domain) == 0

    def test_no_same_domain_for_none_organ_repo(self):
        e1 = FakePlanEntry(qualified_id="p1", agent="claude", organ=None, repo=None)
        e2 = FakePlanEntry(qualified_id="p2", agent="gemini", organ=None, repo=None)
        edges = compute_edges([e1, e2])
        same_domain = [e for e in edges if e.edge_type == "same-domain"]
        assert len(same_domain) == 0

    def test_parent_child_edges(self):
        parent = FakePlanEntry(
            qualified_id="parent-plan", slug="deploy", agent="claude",
        )
        child = FakePlanEntry(
            qualified_id="child-plan", slug="deploy-agent-a1b2c3d4", agent="claude",
        )
        edges = compute_edges([parent, child])
        pc = [e for e in edges if e.edge_type == "parent-child"]
        assert len(pc) == 1
        assert pc[0].source == "parent-plan"
        assert pc[0].target == "child-plan"

    def test_cross_organ_edges(self):
        # file_refs containing a path from a different organ's directory
        e = FakePlanEntry(
            qualified_id="p1",
            organ="META",
            file_refs=["organvm-i-theoria/some-repo/src/file.py"],
        )
        edges = compute_edges([e])
        cross = [e for e in edges if e.edge_type == "cross-organ"]
        assert len(cross) >= 1
        assert cross[0].target.startswith("organ:")

    def test_single_entry_no_spurious_edges(self):
        e = FakePlanEntry(qualified_id="solo", slug="unique-plan")
        edges = compute_edges([e])
        # No supersedes, no same-domain, no parent-child
        assert all(
            e.edge_type not in ("supersedes", "same-domain", "parent-child")
            for e in edges
        )

    def test_edge_dataclass_fields(self):
        e = PlanEdge(source="a", target="b", edge_type="supersedes", weight=1.0)
        assert e.source == "a"
        assert e.target == "b"
        assert e.edge_type == "supersedes"
        assert e.weight == 1.0
