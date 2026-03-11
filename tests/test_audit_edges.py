"""Tests for audit edges layer and validate_edge_resolution."""

from organvm_engine.audit.edges import audit_edges
from organvm_engine.audit.types import Severity
from organvm_engine.seed.graph import SeedGraph, validate_edge_resolution


class TestValidateEdgeResolution:
    def test_empty_graph(self):
        graph = SeedGraph()
        assert validate_edge_resolution(graph) == []

    def test_resolved_edge(self):
        graph = SeedGraph(
            nodes=["org/producer", "org/consumer"],
            produces={"org/producer": [{"type": "api"}]},
            consumes={"org/consumer": [{"type": "api"}]},
            edges=[("org/producer", "org/consumer", "api")],
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 0

    def test_unresolved_edge(self):
        graph = SeedGraph(
            nodes=["org/consumer"],
            produces={},
            consumes={"org/consumer": [{"type": "data-feed"}]},
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 1
        assert unresolved[0]["consumer"] == "org/consumer"
        assert unresolved[0]["type"] == "data-feed"

    def test_unresolved_with_source(self):
        graph = SeedGraph(
            nodes=["org/consumer", "other/producer"],
            produces={"other/producer": [{"type": "api"}]},
            consumes={"org/consumer": [{"type": "api", "source": "wrong-org"}]},
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 1
        assert unresolved[0].get("source") == "wrong-org"

    def test_resolved_with_source(self):
        graph = SeedGraph(
            nodes=["org/consumer", "org/producer"],
            produces={"org/producer": [{"type": "api"}]},
            consumes={"org/consumer": [{"type": "api", "source": "org"}]},
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 0

    def test_self_reference_not_matched(self):
        graph = SeedGraph(
            nodes=["org/repo"],
            produces={"org/repo": [{"type": "data"}]},
            consumes={"org/repo": [{"type": "data"}]},
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 1

    def test_string_consumes(self):
        graph = SeedGraph(
            nodes=["org/consumer"],
            produces={},
            consumes={"org/consumer": ["raw-string-type"]},
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 1
        assert unresolved[0]["type"] == "raw-string-type"

    def test_multiple_unresolved(self):
        graph = SeedGraph(
            nodes=["org/a", "org/b"],
            produces={},
            consumes={
                "org/a": [{"type": "x"}],
                "org/b": [{"type": "y"}, {"type": "z"}],
            },
        )
        unresolved = validate_edge_resolution(graph)
        assert len(unresolved) == 3


class TestAuditEdges:
    def test_with_mocked_graph(self, tmp_path, monkeypatch):
        graph = SeedGraph(
            nodes=["org/a", "org/b"],
            produces={"org/a": [{"type": "api"}]},
            consumes={"org/b": [{"type": "missing-type"}]},
            edges=[],
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.build_seed_graph",
            lambda workspace: graph,
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.validate_edge_resolution",
            lambda g: [{"consumer": "org/b", "type": "missing-type"}],
        )

        report = audit_edges(tmp_path)
        crits = [f for f in report.findings if f.severity == Severity.CRITICAL]
        assert any("unresolved" in f.message.lower() for f in crits)

    def test_orphan_producer(self, tmp_path, monkeypatch):
        graph = SeedGraph(
            nodes=["org/a"],
            produces={"org/a": [{"type": "rare-artifact"}]},
            consumes={},
            edges=[],
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.build_seed_graph",
            lambda workspace: graph,
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.validate_edge_resolution",
            lambda g: [],
        )

        report = audit_edges(tmp_path)
        infos = [f for f in report.findings if f.severity == Severity.INFO]
        assert any("orphan producer" in f.message.lower() for f in infos)

    def test_graph_errors_reported(self, tmp_path, monkeypatch):
        graph = SeedGraph(
            nodes=[],
            errors=["bad-path: parse error"],
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.build_seed_graph",
            lambda workspace: graph,
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.validate_edge_resolution",
            lambda g: [],
        )

        report = audit_edges(tmp_path)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("parse error" in f.message for f in warns)
