"""Tests for governance/impact.py — blast radius calculation."""

from unittest.mock import patch

from organvm_engine.governance.impact import ImpactReport, calculate_impact


def _empty_seed_graph():
    """Return a mock seed graph with no edges."""
    class MockGraph:
        edges = []
    return MockGraph()


class TestImpactReport:
    def test_summary_no_affected(self):
        report = ImpactReport(source_repo="my-repo")
        summary = report.summary()
        assert "my-repo" in summary
        assert "No downstream dependencies" in summary

    def test_summary_with_affected(self):
        report = ImpactReport(
            source_repo="core-lib",
            affected_repos=["consumer-a", "consumer-b"],
            impact_graph={"core-lib": ["consumer-a", "consumer-b"]},
        )
        summary = report.summary()
        assert "core-lib" in summary
        assert "2 repositories affected" in summary
        assert "consumer-a" in summary
        assert "consumer-b" in summary

    def test_summary_propagation_path(self):
        report = ImpactReport(
            source_repo="root",
            affected_repos=["mid", "leaf"],
            impact_graph={"root": ["mid"], "mid": ["leaf"]},
        )
        summary = report.summary()
        assert "Propagation Path" in summary
        assert "mid" in summary
        assert "leaf" in summary


class TestCalculateImpact:
    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_no_deps(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "isolated-repo", "dependencies": []},
                    ],
                },
            },
        }
        report = calculate_impact("isolated-repo", registry)
        assert report.source_repo == "isolated-repo"
        assert report.affected_repos == []

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_direct_dependency(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "core-lib", "dependencies": []},
                        {"name": "consumer", "dependencies": ["org/core-lib"]},
                    ],
                },
            },
        }
        report = calculate_impact("core-lib", registry)
        assert "consumer" in report.affected_repos

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_transitive_dependency(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "a", "dependencies": []},
                        {"name": "b", "dependencies": ["org/a"]},
                        {"name": "c", "dependencies": ["org/b"]},
                    ],
                },
            },
        }
        report = calculate_impact("a", registry)
        assert "b" in report.affected_repos
        assert "c" in report.affected_repos

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_seed_graph_edges(self, mock_graph):
        class MockGraph:
            edges = [("org/producer", "org/consumer", "data")]
        mock_graph.return_value = MockGraph()

        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "producer", "dependencies": []},
                        {"name": "consumer", "dependencies": []},
                    ],
                },
            },
        }
        report = calculate_impact("producer", registry)
        assert "consumer" in report.affected_repos

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_no_self_in_affected(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "a", "dependencies": []},
                        {"name": "b", "dependencies": ["org/a"]},
                    ],
                },
            },
        }
        report = calculate_impact("a", registry)
        assert "a" not in report.affected_repos

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_circular_deps_no_infinite_loop(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "a", "dependencies": ["org/b"]},
                        {"name": "b", "dependencies": ["org/a"]},
                    ],
                },
            },
        }
        report = calculate_impact("a", registry)
        assert "b" in report.affected_repos

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_impact_graph_populated(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "root", "dependencies": []},
                        {"name": "child", "dependencies": ["org/root"]},
                    ],
                },
            },
        }
        report = calculate_impact("root", registry)
        assert "child" in report.impact_graph.get("root", [])

    @patch("organvm_engine.governance.impact.build_seed_graph")
    def test_none_dependencies_handled(self, mock_graph):
        mock_graph.return_value = _empty_seed_graph()
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {"name": "repo", "dependencies": None},
                    ],
                },
            },
        }
        report = calculate_impact("repo", registry)
        assert report.affected_repos == []
