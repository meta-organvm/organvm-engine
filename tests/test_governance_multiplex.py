"""Tests for AX-008: multiplex flow governance (FlowType, TypedEdge, MultiplexGraph)."""

from organvm_engine.governance.dependency_graph import (
    FlowType,
    MultiplexGraph,
    TypedEdge,
    build_multiplex_graph,
)


class TestFlowType:
    def test_enum_values(self):
        assert FlowType.DEPENDENCY.value == "dependency"
        assert FlowType.INFORMATION.value == "information"
        assert FlowType.GOVERNANCE.value == "governance"
        assert FlowType.EVOLUTION.value == "evolution"

    def test_all_four_types_exist(self):
        assert len(FlowType) == 4


class TestTypedEdge:
    def test_create_edge(self):
        edge = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        assert edge.source == "a/b"
        assert edge.target == "c/d"
        assert edge.flow_type == FlowType.DEPENDENCY

    def test_equality(self):
        e1 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        e2 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        assert e1 == e2

    def test_inequality_different_type(self):
        e1 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        e2 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.INFORMATION)
        assert e1 != e2

    def test_inequality_different_source(self):
        e1 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        e2 = TypedEdge(source="x/y", target="c/d", flow_type=FlowType.DEPENDENCY)
        assert e1 != e2

    def test_hashable(self):
        e1 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        e2 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        assert hash(e1) == hash(e2)
        assert len({e1, e2}) == 1

    def test_hash_differs_by_flow_type(self):
        e1 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        e2 = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.GOVERNANCE)
        assert len({e1, e2}) == 2

    def test_equality_with_non_typed_edge(self):
        edge = TypedEdge(source="a/b", target="c/d", flow_type=FlowType.DEPENDENCY)
        assert edge != "not an edge"


class TestMultiplexGraph:
    def test_empty_graph(self):
        graph = MultiplexGraph()
        assert graph.edges == []
        assert graph.layer_counts() == {}
        assert graph.nodes() == set()

    def test_edges_by_type(self):
        graph = MultiplexGraph(edges=[
            TypedEdge("a/b", "c/d", FlowType.DEPENDENCY),
            TypedEdge("a/b", "e/f", FlowType.INFORMATION),
            TypedEdge("c/d", "e/f", FlowType.DEPENDENCY),
        ])
        dep_edges = graph.edges_by_type(FlowType.DEPENDENCY)
        assert len(dep_edges) == 2
        info_edges = graph.edges_by_type(FlowType.INFORMATION)
        assert len(info_edges) == 1
        gov_edges = graph.edges_by_type(FlowType.GOVERNANCE)
        assert len(gov_edges) == 0

    def test_layer_counts(self):
        graph = MultiplexGraph(edges=[
            TypedEdge("a/b", "c/d", FlowType.DEPENDENCY),
            TypedEdge("a/b", "e/f", FlowType.INFORMATION),
            TypedEdge("c/d", "e/f", FlowType.DEPENDENCY),
        ])
        counts = graph.layer_counts()
        assert counts == {"dependency": 2, "information": 1}

    def test_nodes(self):
        graph = MultiplexGraph(edges=[
            TypedEdge("a/b", "c/d", FlowType.DEPENDENCY),
            TypedEdge("c/d", "e/f", FlowType.INFORMATION),
        ])
        assert graph.nodes() == {"a/b", "c/d", "e/f"}

    def test_summary(self):
        graph = MultiplexGraph(edges=[
            TypedEdge("a/b", "c/d", FlowType.DEPENDENCY),
        ])
        summary = graph.summary()
        assert "1 edges" in summary
        assert "dependency" in summary


class TestBuildMultiplexGraph:
    def test_dependency_edges_from_registry(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "theory",
                            "org": "organvm-i-theoria",
                            "dependencies": ["meta-organvm/engine"],
                        },
                    ],
                },
                "META-ORGANVM": {
                    "repositories": [
                        {
                            "name": "engine",
                            "org": "meta-organvm",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        graph = build_multiplex_graph(registry)
        assert len(graph.edges) == 1
        assert graph.edges[0].flow_type == FlowType.DEPENDENCY
        assert graph.edges[0].source == "organvm-i-theoria/theory"
        assert graph.edges[0].target == "meta-organvm/engine"

    def test_empty_registry(self):
        registry = {"organs": {}}
        graph = build_multiplex_graph(registry)
        assert len(graph.edges) == 0

    def test_information_edges_from_seed_graph(self):
        """When a SeedGraph is provided, its edges become INFORMATION edges."""
        registry = {"organs": {}}

        # Mock seed graph with edges attribute
        class MockSeedGraph:
            edges = [
                ("meta-organvm/corpvs", "meta-organvm/engine", "registry"),
                ("meta-organvm/schema", "meta-organvm/engine", "schema"),
            ]

        graph = build_multiplex_graph(registry, seed_graph=MockSeedGraph())
        assert len(graph.edges) == 2
        for edge in graph.edges:
            assert edge.flow_type == FlowType.INFORMATION

    def test_combined_dependency_and_information(self):
        """Both registry deps and seed graph edges produce typed edges."""
        registry = {
            "organs": {
                "META-ORGANVM": {
                    "repositories": [
                        {
                            "name": "engine",
                            "org": "meta-organvm",
                            "dependencies": ["meta-organvm/schema"],
                        },
                        {
                            "name": "schema",
                            "org": "meta-organvm",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }

        class MockSeedGraph:
            edges = [("meta-organvm/corpvs", "meta-organvm/engine", "registry")]

        graph = build_multiplex_graph(registry, seed_graph=MockSeedGraph())
        dep_count = len(graph.edges_by_type(FlowType.DEPENDENCY))
        info_count = len(graph.edges_by_type(FlowType.INFORMATION))
        assert dep_count == 1
        assert info_count == 1

    def test_no_seed_graph(self):
        """When no seed graph is provided, only dependency edges exist."""
        registry = {
            "organs": {
                "META-ORGANVM": {
                    "repositories": [
                        {
                            "name": "engine",
                            "org": "meta-organvm",
                            "dependencies": ["meta-organvm/schema"],
                        },
                        {
                            "name": "schema",
                            "org": "meta-organvm",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        graph = build_multiplex_graph(registry, seed_graph=None)
        assert all(e.flow_type == FlowType.DEPENDENCY for e in graph.edges)
