"""Tests for composite graph indices (INST-GRAPH-INDICES)."""

from dataclasses import dataclass, field

import pytest

from organvm_engine.metrics.indices import (
    IndexReport,
    compute_all_indices,
    compute_cci,
    compute_cri,
    compute_ddi,
    compute_eci,
    compute_fvi,
)

# ---------------------------------------------------------------------------
# Mock SeedGraph for FVI tests
# ---------------------------------------------------------------------------

@dataclass
class MockSeedGraph:
    """Minimal stand-in for seed.graph.SeedGraph."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def healthy_registry():
    """Registry with valid DAG, no cycles, no back-edges."""
    return {
        "organs": {
            "ORGAN-I": {
                "repositories": [
                    {
                        "name": "theory-core",
                        "org": "organvm-i-theoria",
                        "implementation_status": "ACTIVE",
                        "promotion_status": "PUBLIC_PROCESS",
                        "dependencies": [],
                    },
                ],
            },
            "ORGAN-II": {
                "repositories": [
                    {
                        "name": "art-engine",
                        "org": "organvm-ii-poiesis",
                        "implementation_status": "ACTIVE",
                        "promotion_status": "CANDIDATE",
                        "dependencies": ["organvm-i-theoria/theory-core"],
                    },
                ],
            },
            "META-ORGANVM": {
                "repositories": [
                    {
                        "name": "organvm-engine",
                        "org": "meta-organvm",
                        "implementation_status": "ACTIVE",
                        "promotion_status": "PUBLIC_PROCESS",
                        "dependencies": [],
                    },
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# IDX-001: CCI — Constitutional Coverage
# ---------------------------------------------------------------------------

class TestCCI:
    def test_all_reachable(self, healthy_registry):
        cci, details = compute_cci(healthy_registry)
        assert cci == 1.0
        assert details["orphaned"] == []
        assert details["active"] == 3

    def test_empty_registry(self):
        cci, details = compute_cci({"organs": {}})
        assert cci == 1.0
        assert details["active"] == 0

    def test_archived_excluded(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "old",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ARCHIVED",
                            "dependencies": [],
                        },
                        {
                            "name": "active",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        cci, details = compute_cci(registry)
        assert cci == 1.0
        assert details["active"] == 1

    def test_connected_via_dependency(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "a",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "dependencies": ["organvm-i-theoria/b"],
                        },
                        {
                            "name": "b",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        cci, details = compute_cci(registry)
        assert cci == 1.0


# ---------------------------------------------------------------------------
# IDX-002: DDI — Dependency Discipline
# ---------------------------------------------------------------------------

class TestDDI:
    def test_clean_dag(self, healthy_registry):
        ddi, details = compute_ddi(healthy_registry)
        assert ddi == 1.0
        assert details["cycles"] == 0
        assert details["back_edges"] == 0

    def test_cycle_penalizes(self):
        registry = {
            "organs": {
                "ORGAN-IV": {
                    "repositories": [
                        {
                            "name": "a",
                            "org": "organvm-iv-taxis",
                            "dependencies": ["organvm-iv-taxis/b"],
                        },
                        {
                            "name": "b",
                            "org": "organvm-iv-taxis",
                            "dependencies": ["organvm-iv-taxis/a"],
                        },
                    ],
                },
            },
        }
        ddi, details = compute_ddi(registry)
        assert ddi < 1.0
        assert details["cycles"] > 0

    def test_back_edge_penalizes(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "x",
                            "org": "organvm-i-theoria",
                            "dependencies": ["organvm-ii-poiesis/y"],
                        },
                    ],
                },
                "ORGAN-II": {
                    "repositories": [
                        {
                            "name": "y",
                            "org": "organvm-ii-poiesis",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        ddi, details = compute_ddi(registry)
        assert ddi < 1.0
        assert details["back_edges"] > 0

    def test_no_edges_is_perfect(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "solo",
                            "org": "organvm-i-theoria",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        ddi, details = compute_ddi(registry)
        assert ddi == 1.0


# ---------------------------------------------------------------------------
# IDX-003: FVI — Feedback Vitality
# ---------------------------------------------------------------------------

class TestFVI:
    def test_no_seed_graph(self):
        fvi, details = compute_fvi(None)
        assert fvi == 0.0

    def test_no_edges(self):
        graph = MockSeedGraph(nodes=["a", "b"], edges=[])
        fvi, details = compute_fvi(graph)
        assert fvi == 0.0
        assert details["feedback_loops"] == 0

    def test_one_way_no_loops(self):
        graph = MockSeedGraph(
            nodes=["a", "b"],
            edges=[("a", "b", "data")],
        )
        fvi, details = compute_fvi(graph)
        assert fvi == 0.0

    def test_feedback_loop_detected(self):
        graph = MockSeedGraph(
            nodes=["a", "b", "c"],
            edges=[
                ("a", "b", "data"),
                ("b", "a", "feedback"),
            ],
        )
        fvi, details = compute_fvi(graph)
        assert fvi > 0
        assert details["feedback_loops"] == 1
        assert len(details["loops"]) == 1

    def test_multiple_loops(self):
        graph = MockSeedGraph(
            nodes=["a", "b", "c", "d"],
            edges=[
                ("a", "b", "data"),
                ("b", "a", "feedback"),
                ("c", "d", "data"),
                ("d", "c", "feedback"),
            ],
        )
        fvi, details = compute_fvi(graph)
        assert details["feedback_loops"] == 2

    def test_fvi_is_ratio(self):
        graph = MockSeedGraph(
            nodes=["a", "b"],
            edges=[
                ("a", "b", "data"),
                ("b", "a", "data"),
            ],
        )
        fvi, details = compute_fvi(graph)
        # 1 loop / 2 nodes = 0.5
        assert fvi == 0.5


# ---------------------------------------------------------------------------
# IDX-004: CRI — Coupling Risk
# ---------------------------------------------------------------------------

class TestCRI:
    def test_no_edges(self):
        cri, details = compute_cri([])
        assert cri == 0.0

    def test_low_coupling(self):
        edges = [("a", "b")]
        cri, details = compute_cri(edges, threshold=6)
        # avg degree = (1+1)/2 = 1.0, CRI = 1.0/6 ≈ 0.1667
        assert 0 < cri < 1.0
        assert details["over_coupled"] == []

    def test_over_coupled(self):
        # Node 'hub' with degree 8 (above threshold 6)
        edges = [
            ("hub", "a"),
            ("hub", "b"),
            ("hub", "c"),
            ("hub", "d"),
            ("hub", "e"),
            ("hub", "f"),
            ("hub", "g"),
            ("hub", "h"),
        ]
        cri, details = compute_cri(edges, threshold=6)
        assert len(details["over_coupled"]) > 0
        hub_entry = next(e for e in details["over_coupled"] if e["node"] == "hub")
        assert hub_entry["degree"] == 8

    def test_custom_threshold(self):
        edges = [("a", "b"), ("b", "c")]
        cri_low, _ = compute_cri(edges, threshold=2)
        cri_high, _ = compute_cri(edges, threshold=10)
        assert cri_low > cri_high


# ---------------------------------------------------------------------------
# IDX-005: ECI — Evolutionary Coherence
# ---------------------------------------------------------------------------

class TestECI:
    def test_no_archived_repos(self, healthy_registry):
        eci, details = compute_eci(healthy_registry)
        assert eci == 1.0
        assert details["total_archived"] == 0

    def test_archived_with_lineage(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "old-project",
                            "org": "organvm-i-theoria",
                            "promotion_status": "ARCHIVED",
                            "note": "Merged into recursive-engine as part of consolidation.",
                        },
                    ],
                },
            },
        }
        eci, details = compute_eci(registry)
        assert eci == 1.0
        assert details["with_lineage"] == 1

    def test_archived_without_lineage(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "abandoned",
                            "org": "organvm-i-theoria",
                            "promotion_status": "ARCHIVED",
                            # no note, no lineage, no successor
                        },
                    ],
                },
            },
        }
        eci, details = compute_eci(registry)
        assert eci == 0.0
        assert "ORGAN-I/abandoned" in details["missing_lineage"]

    def test_short_note_insufficient(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "terse",
                            "org": "organvm-i-theoria",
                            "promotion_status": "ARCHIVED",
                            "note": "old",  # less than 10 chars
                        },
                    ],
                },
            },
        }
        eci, details = compute_eci(registry)
        assert eci == 0.0

    def test_successor_counts_as_lineage(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "evolved",
                            "org": "organvm-i-theoria",
                            "promotion_status": "ARCHIVED",
                            "successor": "new-project",
                        },
                    ],
                },
            },
        }
        eci, details = compute_eci(registry)
        assert eci == 1.0

    def test_mixed_archived(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "good",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ARCHIVED",
                            "note": "Superseded by better-project. All functionality migrated.",
                        },
                        {
                            "name": "bad",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ARCHIVED",
                        },
                    ],
                },
            },
        }
        eci, details = compute_eci(registry)
        assert eci == 0.5


# ---------------------------------------------------------------------------
# Consolidated report
# ---------------------------------------------------------------------------

class TestComputeAllIndices:
    def test_returns_all_five(self, healthy_registry):
        report = compute_all_indices(healthy_registry)
        assert isinstance(report, IndexReport)
        assert "cci" in report.details
        assert "ddi" in report.details
        assert "fvi" in report.details
        assert "cri" in report.details
        assert "eci" in report.details

    def test_healthy_registry_high_scores(self, healthy_registry):
        report = compute_all_indices(healthy_registry)
        assert report.cci == 1.0
        assert report.ddi == 1.0
        assert report.fvi == 0.0  # no seed graph provided

    def test_with_seed_graph(self, healthy_registry):
        graph = MockSeedGraph(
            nodes=["a", "b"],
            edges=[("a", "b", "data"), ("b", "a", "data")],
        )
        report = compute_all_indices(healthy_registry, seed_graph=graph)
        assert report.fvi > 0

    def test_to_dict(self, healthy_registry):
        report = compute_all_indices(healthy_registry)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert all(k in d for k in ("cci", "ddi", "fvi", "cri", "eci", "details"))

    def test_summary_output(self, healthy_registry):
        report = compute_all_indices(healthy_registry)
        text = report.summary()
        assert "Graph Indices" in text
        assert "CCI" in text
        assert "DDI" in text

    def test_custom_coupling_threshold(self, healthy_registry):
        report = compute_all_indices(healthy_registry, coupling_threshold=2)
        # With threshold=2, even moderate coupling registers higher CRI
        assert "cri" in report.details
