"""Tests for plans/graph.py — Jaccard overlap, edges, clustering."""

from __future__ import annotations

import pytest

from organvm_engine.plans.graph import (
    PlanEdge,
    PlanOverlap,
    _domain_set,
    compute_edges,
    compute_overlaps,
    jaccard_similarity,
)
from organvm_engine.plans.index import PlanEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    slug="plan-a", agent="claude", organ="III", repo="repo-a",
    tags=None, file_refs=None, version=1, status="active",
) -> PlanEntry:
    """Create a minimal PlanEntry for testing."""
    tags = tags or []
    file_refs = file_refs or []
    return PlanEntry(
        qualified_id=f"{agent}:{organ}:{repo}:{slug}",
        path=f"/fake/{slug}.md",
        agent=agent,
        organ=organ,
        repo=repo,
        slug=slug,
        date="2026-03-01",
        version=version,
        status=status,
        title=f"Plan {slug}",
        size_bytes=1000,
        has_verification=False,
        archetype="checkbox",
        task_count=5,
        completed_count=2,
        tags=tags,
        file_refs=file_refs,
        domain_fingerprint="abc123",
    )


# ---------------------------------------------------------------------------
# jaccard_similarity
# ---------------------------------------------------------------------------

class TestJaccard:
    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        j = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(j - 0.5) < 0.01  # 2/4

    def test_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 0.0

    def test_one_empty(self):
        assert jaccard_similarity({"a"}, set()) == 0.0


# ---------------------------------------------------------------------------
# _domain_set
# ---------------------------------------------------------------------------

class TestDomainSet:
    def test_tags_and_refs(self):
        e = _entry(tags=["python", "pytest"], file_refs=["src/foo.py"])
        ds = _domain_set(e)
        assert "tag:python" in ds
        assert "tag:pytest" in ds
        assert "ref:src/foo.py" in ds

    def test_empty_entry(self):
        e = _entry(tags=[], file_refs=[])
        ds = _domain_set(e)
        assert len(ds) == 0


# ---------------------------------------------------------------------------
# compute_overlaps
# ---------------------------------------------------------------------------

class TestComputeOverlaps:
    def test_no_entries(self):
        assert compute_overlaps([]) == []

    def test_single_entry(self):
        assert compute_overlaps([_entry()]) == []

    def test_identical_domains(self):
        tags = ["python", "fastapi", "pytest"]
        refs = ["src/main.py", "tests/test_main.py"]
        e1 = _entry(slug="a", agent="claude", tags=tags, file_refs=refs)
        e2 = _entry(slug="b", agent="gemini", tags=tags, file_refs=refs)

        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        assert len(overlaps) >= 1
        assert overlaps[0].severity == "conflict"  # Jaccard=1.0, different agents
        assert len(overlaps[0].plans) == 2

    def test_disjoint_domains(self):
        e1 = _entry(slug="a", tags=["python"], file_refs=["src/a.py"])
        e2 = _entry(slug="b", tags=["rust"], file_refs=["src/b.rs"])

        overlaps = compute_overlaps([e1, e2], threshold=0.3)
        assert len(overlaps) == 0

    def test_partial_overlap_warning(self):
        e1 = _entry(slug="a", agent="claude",
                     tags=["python", "fastapi", "pydantic"],
                     file_refs=["src/app.py"])
        e2 = _entry(slug="b", agent="gemini",
                     tags=["python", "fastapi", "sqlalchemy"],
                     file_refs=["src/db.py"])

        overlaps = compute_overlaps([e1, e2], threshold=0.2)
        assert len(overlaps) >= 1

    def test_threshold_filtering(self):
        e1 = _entry(slug="a", tags=["python", "a", "b", "c"], file_refs=[])
        e2 = _entry(slug="b", tags=["python", "d", "e", "f"], file_refs=[])

        low = compute_overlaps([e1, e2], threshold=0.05)
        high = compute_overlaps([e1, e2], threshold=0.8)
        assert len(low) >= len(high)

    def test_severity_ordering(self):
        tags = ["python", "pytest"]
        e1 = _entry(slug="a", agent="claude", tags=tags, file_refs=["x.py"])
        e2 = _entry(slug="b", agent="gemini", tags=tags, file_refs=["x.py"])
        e3 = _entry(slug="c", agent="claude", tags=["python"], file_refs=["y.py"])

        overlaps = compute_overlaps([e1, e2, e3], threshold=0.1)
        if len(overlaps) >= 2:
            # Conflicts should come before info
            severities = [o.severity for o in overlaps]
            sev_order = {"conflict": 0, "warning": 1, "info": 2}
            assert all(
                sev_order.get(severities[i], 3) <= sev_order.get(severities[i + 1], 3)
                for i in range(len(severities) - 1)
            )


# ---------------------------------------------------------------------------
# compute_edges
# ---------------------------------------------------------------------------

class TestComputeEdges:
    def test_supersedes_edge(self):
        e1 = _entry(slug="my-plan", version=1)
        e2 = _entry(slug="my-plan", version=2)
        edges = compute_edges([e1, e2])
        supersedes = [e for e in edges if e.edge_type == "supersedes"]
        assert len(supersedes) == 1
        assert supersedes[0].source == e2.qualified_id

    def test_same_domain_edge(self):
        e1 = _entry(slug="a", agent="claude", organ="III", repo="repo-x")
        e2 = _entry(slug="b", agent="gemini", organ="III", repo="repo-x")
        edges = compute_edges([e1, e2])
        same = [e for e in edges if e.edge_type == "same-domain"]
        assert len(same) == 1

    def test_no_same_domain_for_same_agent(self):
        e1 = _entry(slug="a", agent="claude", organ="III", repo="repo-x")
        e2 = _entry(slug="b", agent="claude", organ="III", repo="repo-x")
        edges = compute_edges([e1, e2])
        same = [e for e in edges if e.edge_type == "same-domain"]
        assert len(same) == 0

    def test_cross_organ_edge(self):
        e = _entry(slug="a", organ="III",
                   file_refs=["organvm-i-theoria/my-lib/src/foo.py"])
        edges = compute_edges([e])
        cross = [e for e in edges if e.edge_type == "cross-organ"]
        assert len(cross) == 1

    def test_parent_child_edge(self):
        parent = _entry(slug="big-plan", agent="claude")
        child = _entry(slug="big-plan-agent-a1b2c3", agent="claude")
        edges = compute_edges([parent, child])
        pc = [e for e in edges if e.edge_type == "parent-child"]
        assert len(pc) == 1
        assert pc[0].source == parent.qualified_id
        assert pc[0].target == child.qualified_id

    def test_empty_entries(self):
        assert compute_edges([]) == []
