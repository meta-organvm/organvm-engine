"""Tests for temporal versioning of the dependency graph (issue #8)."""

from __future__ import annotations

from pathlib import Path

from organvm_engine.governance.temporal import (
    GraphDiff,
    TemporalEdge,
    TemporalGraph,
    extract_edges_from_registry,
    record_registry_snapshot,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------
# TemporalEdge
# ---------------------------------------------------------------

class TestTemporalEdge:
    def test_active_edge_is_active(self):
        e = TemporalEdge(source="a/x", target="b/y", created_at="2026-01-01T00:00:00")
        assert e.is_active is True

    def test_removed_edge_is_not_active(self):
        e = TemporalEdge(
            source="a/x", target="b/y",
            created_at="2026-01-01T00:00:00",
            removed_at="2026-02-01T00:00:00",
        )
        assert e.is_active is False

    def test_is_active_at_before_creation(self):
        e = TemporalEdge(source="a/x", target="b/y", created_at="2026-03-01T00:00:00")
        assert e.is_active_at("2026-02-01T00:00:00") is False

    def test_is_active_at_on_creation(self):
        e = TemporalEdge(source="a/x", target="b/y", created_at="2026-03-01T00:00:00")
        assert e.is_active_at("2026-03-01T00:00:00") is True

    def test_is_active_at_after_creation_before_removal(self):
        e = TemporalEdge(
            source="a/x", target="b/y",
            created_at="2026-01-01T00:00:00",
            removed_at="2026-06-01T00:00:00",
        )
        assert e.is_active_at("2026-03-15T00:00:00") is True

    def test_is_active_at_on_removal(self):
        """At the exact removal timestamp the edge is no longer active."""
        e = TemporalEdge(
            source="a/x", target="b/y",
            created_at="2026-01-01T00:00:00",
            removed_at="2026-06-01T00:00:00",
        )
        assert e.is_active_at("2026-06-01T00:00:00") is False

    def test_is_active_at_after_removal(self):
        e = TemporalEdge(
            source="a/x", target="b/y",
            created_at="2026-01-01T00:00:00",
            removed_at="2026-06-01T00:00:00",
        )
        assert e.is_active_at("2026-12-01T00:00:00") is False

    def test_to_dict_omits_none(self):
        e = TemporalEdge(source="a/x", target="b/y", created_at="2026-01-01T00:00:00")
        d = e.to_dict()
        assert "removed_at" not in d
        assert "source_status" not in d
        assert d["source"] == "a/x"
        assert d["created_at"] == "2026-01-01T00:00:00"

    def test_to_dict_includes_present_values(self):
        e = TemporalEdge(
            source="a/x", target="b/y",
            created_at="2026-01-01T00:00:00",
            removed_at="2026-02-01T00:00:00",
            source_status="LOCAL",
        )
        d = e.to_dict()
        assert d["removed_at"] == "2026-02-01T00:00:00"
        assert d["source_status"] == "LOCAL"


# ---------------------------------------------------------------
# TemporalGraph — record_snapshot
# ---------------------------------------------------------------

class TestRecordSnapshot:
    def test_first_snapshot_adds_all_edges(self):
        g = TemporalGraph()
        edges = [("a/x", "b/y"), ("c/z", "d/w")]
        added, removed = g.record_snapshot(edges, timestamp="2026-01-01T00:00:00")

        assert len(added) == 2
        assert len(removed) == 0
        assert len(g.edges) == 2
        assert all(e.is_active for e in g.edges)

    def test_second_snapshot_detects_removal(self):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y"), ("c/z", "d/w")],
            timestamp="2026-01-01T00:00:00",
        )
        # Second snapshot has only one of the two edges
        added, removed = g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-02-01T00:00:00",
        )

        assert len(added) == 0
        assert len(removed) == 1
        assert removed[0].source == "c/z"
        assert removed[0].removed_at == "2026-02-01T00:00:00"

    def test_second_snapshot_detects_addition(self):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-01-01T00:00:00",
        )
        added, removed = g.record_snapshot(
            [("a/x", "b/y"), ("new/src", "new/tgt")],
            timestamp="2026-02-01T00:00:00",
        )

        assert len(added) == 1
        assert len(removed) == 0
        assert added[0].source == "new/src"
        assert added[0].created_at == "2026-02-01T00:00:00"

    def test_snapshot_with_status_map(self):
        g = TemporalGraph()
        status = {"a/x": "GRADUATED", "b/y": "LOCAL"}
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-01-01T00:00:00",
            status_map=status,
        )

        assert g.edges[0].source_status == "GRADUATED"
        assert g.edges[0].target_status == "LOCAL"

    def test_idempotent_snapshot(self):
        """Recording the same edges twice produces no adds or removes."""
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-01-01T00:00:00")
        added, removed = g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-02-01T00:00:00",
        )

        assert len(added) == 0
        assert len(removed) == 0
        assert len(g.edges) == 1

    def test_re_add_after_removal_creates_new_record(self):
        """If an edge is removed then re-added, a new temporal record is created."""
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-01-01T00:00:00")
        g.record_snapshot([], timestamp="2026-02-01T00:00:00")  # remove
        added, _ = g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-03-01T00:00:00",
        )  # re-add

        assert len(added) == 1
        assert len(g.edges) == 2  # two records: one removed, one active
        history = g.edge_history("a/x", "b/y")
        assert len(history) == 2
        assert history[0].removed_at == "2026-02-01T00:00:00"
        assert history[1].is_active

    def test_empty_snapshot(self):
        g = TemporalGraph()
        added, removed = g.record_snapshot([], timestamp="2026-01-01T00:00:00")
        assert len(added) == 0
        assert len(removed) == 0
        assert len(g.edges) == 0


# ---------------------------------------------------------------
# TemporalGraph — graph_at
# ---------------------------------------------------------------

class TestGraphAt:
    def test_graph_at_returns_active_edges(self):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y"), ("c/z", "d/w")],
            timestamp="2026-01-01T00:00:00",
        )
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-03-01T00:00:00",
        )

        # At t=Jan: both edges active
        at_jan = g.graph_at("2026-01-15T00:00:00")
        assert len(at_jan) == 2

        # At t=Mar: only one edge active
        at_mar = g.graph_at("2026-03-15T00:00:00")
        assert len(at_mar) == 1
        assert at_mar[0].source == "a/x"

    def test_graph_at_before_any_data(self):
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-06-01T00:00:00")
        assert g.graph_at("2026-01-01T00:00:00") == []


# ---------------------------------------------------------------
# TemporalGraph — graph_diff
# ---------------------------------------------------------------

class TestGraphDiff:
    def test_diff_shows_additions(self):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-01-01T00:00:00",
        )
        g.record_snapshot(
            [("a/x", "b/y"), ("new/s", "new/t")],
            timestamp="2026-02-01T00:00:00",
        )

        diff = g.graph_diff("2026-01-01T00:00:00", "2026-02-15T00:00:00")
        assert len(diff.added) == 1
        assert diff.added[0].source == "new/s"
        assert len(diff.removed) == 0

    def test_diff_shows_removals(self):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y"), ("c/z", "d/w")],
            timestamp="2026-01-01T00:00:00",
        )
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-02-01T00:00:00",
        )

        diff = g.graph_diff("2026-01-01T00:00:00", "2026-02-15T00:00:00")
        assert len(diff.removed) == 1
        assert diff.removed[0].source == "c/z"

    def test_diff_both_additions_and_removals(self):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-01-01T00:00:00",
        )
        g.record_snapshot(
            [("new/s", "new/t")],
            timestamp="2026-02-01T00:00:00",
        )

        diff = g.graph_diff("2026-01-01T00:00:00", "2026-02-15T00:00:00")
        assert len(diff.added) == 1
        assert len(diff.removed) == 1

    def test_diff_empty_interval(self):
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-01-01T00:00:00")

        diff = g.graph_diff("2026-02-01T00:00:00", "2026-03-01T00:00:00")
        assert len(diff.added) == 0
        assert len(diff.removed) == 0

    def test_diff_to_dict(self):
        diff = GraphDiff(
            t1="2026-01-01T00:00:00",
            t2="2026-02-01T00:00:00",
            added=[TemporalEdge(source="a/x", target="b/y", created_at="2026-01-15T00:00:00")],
            removed=[],
        )
        d = diff.to_dict()
        assert d["t1"] == "2026-01-01T00:00:00"
        assert len(d["added"]) == 1
        assert len(d["removed"]) == 0


# ---------------------------------------------------------------
# TemporalGraph — edge_history
# ---------------------------------------------------------------

class TestEdgeHistory:
    def test_history_for_specific_edge(self):
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y"), ("c/z", "d/w")], timestamp="2026-01-01T00:00:00")

        history = g.edge_history("a/x", "b/y")
        assert len(history) == 1
        assert history[0].source == "a/x"

    def test_history_empty_for_unknown_edge(self):
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-01-01T00:00:00")
        assert g.edge_history("no/edge", "at/all") == []


# ---------------------------------------------------------------
# Persistence — save / load
# ---------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        g = TemporalGraph()
        g.record_snapshot(
            [("a/x", "b/y")],
            timestamp="2026-01-01T00:00:00",
            status_map={"a/x": "GRADUATED", "b/y": "LOCAL"},
        )
        g.record_snapshot(
            [("a/x", "b/y"), ("c/z", "d/w")],
            timestamp="2026-02-01T00:00:00",
        )

        path = tmp_path / "temporal-graph.json"
        g.save(path)
        assert path.exists()

        loaded = TemporalGraph.load(path)
        assert len(loaded.edges) == 2
        assert loaded.edges[0].source == "a/x"
        assert loaded.edges[0].source_status == "GRADUATED"
        assert loaded.edges[1].created_at == "2026-02-01T00:00:00"

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        g = TemporalGraph()
        path = tmp_path / "nested" / "dir" / "graph.json"
        g.save(path)
        assert path.exists()

    def test_load_empty_graph(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text('{"version": "1.0", "edges": []}')
        g = TemporalGraph.load(path)
        assert len(g.edges) == 0

    def test_roundtrip_preserves_removed_edges(self, tmp_path: Path):
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-01-01T00:00:00")
        g.record_snapshot([], timestamp="2026-02-01T00:00:00")

        path = tmp_path / "graph.json"
        g.save(path)
        loaded = TemporalGraph.load(path)

        assert len(loaded.edges) == 1
        assert loaded.edges[0].removed_at == "2026-02-01T00:00:00"


# ---------------------------------------------------------------
# extract_edges_from_registry
# ---------------------------------------------------------------

class TestExtractEdgesFromRegistry:
    def test_extracts_edges_and_status(self, registry):
        edges, status_map = extract_edges_from_registry(registry)

        # The minimal registry has these deps:
        # ontological-framework -> organvm-i-theoria/recursive-engine
        # metasystem-master -> organvm-i-theoria/recursive-engine
        assert len(edges) >= 2

        edge_set = set(edges)
        assert (
            "organvm-i-theoria/ontological-framework",
            "organvm-i-theoria/recursive-engine",
        ) in edge_set

        assert status_map["organvm-i-theoria/recursive-engine"] == "PUBLIC_PROCESS"

    def test_empty_registry(self):
        edges, status_map = extract_edges_from_registry({"organs": {}})
        assert edges == []
        assert status_map == {}


# ---------------------------------------------------------------
# record_registry_snapshot (convenience wrapper)
# ---------------------------------------------------------------

class TestRecordRegistrySnapshot:
    def test_records_from_registry(self, registry):
        g = TemporalGraph()
        added, removed = record_registry_snapshot(
            g, registry, timestamp="2026-03-01T00:00:00",
        )

        assert len(added) >= 2
        assert len(removed) == 0
        assert all(e.created_at == "2026-03-01T00:00:00" for e in added)

        # Status annotations should be populated
        has_status = any(e.source_status is not None for e in added)
        assert has_status


# ---------------------------------------------------------------
# TemporalGraph — to_dict
# ---------------------------------------------------------------

class TestToDict:
    def test_to_dict_structure(self):
        g = TemporalGraph()
        g.record_snapshot([("a/x", "b/y")], timestamp="2026-01-01T00:00:00")

        d = g.to_dict()
        assert d["version"] == "1.0"
        assert d["edge_count"] == 1
        assert d["active_count"] == 1
        assert len(d["edges"]) == 1
