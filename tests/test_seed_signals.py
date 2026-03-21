"""Tests for AX-009: signal I/O (seed/signals.py)."""

from organvm_engine.seed.signals import (
    SIGNAL_CLASSES,
    SignalPort,
    build_signal_graph,
    get_signal_inputs,
    get_signal_outputs,
)


class TestSignalPort:
    def test_valid_class(self):
        port = SignalPort(name="test", signal_class="data")
        assert port.is_valid_class()

    def test_invalid_class(self):
        port = SignalPort(name="test", signal_class="bogus")
        assert not port.is_valid_class()

    def test_all_canonical_classes_valid(self):
        for cls in SIGNAL_CLASSES:
            port = SignalPort(name="test", signal_class=cls)
            assert port.is_valid_class(), f"Expected {cls} to be valid"


class TestGetSignalInputs:
    def test_empty_seed(self):
        assert get_signal_inputs({}) == []

    def test_no_signal_inputs_key(self):
        seed = {"organ": "I", "repo": "test"}
        assert get_signal_inputs(seed) == []

    def test_non_list_signal_inputs(self):
        seed = {"signal_inputs": "not a list"}
        assert get_signal_inputs(seed) == []

    def test_valid_signal_inputs(self):
        seed = {
            "signal_inputs": [
                {"name": "governance-policy", "class": "governance", "description": "Gets policy"},
                {"name": "registry-data", "class": "data"},
            ],
        }
        ports = get_signal_inputs(seed)
        assert len(ports) == 2
        assert ports[0].name == "governance-policy"
        assert ports[0].signal_class == "governance"
        assert ports[0].description == "Gets policy"
        assert ports[1].name == "registry-data"
        assert ports[1].signal_class == "data"
        assert ports[1].description == ""

    def test_skips_entries_without_name(self):
        seed = {
            "signal_inputs": [
                {"class": "data"},  # no name
                {"name": "valid", "class": "data"},
            ],
        }
        ports = get_signal_inputs(seed)
        assert len(ports) == 1
        assert ports[0].name == "valid"

    def test_default_class_is_data(self):
        seed = {"signal_inputs": [{"name": "test-signal"}]}
        ports = get_signal_inputs(seed)
        assert len(ports) == 1
        assert ports[0].signal_class == "data"


class TestGetSignalOutputs:
    def test_empty_seed(self):
        assert get_signal_outputs({}) == []

    def test_valid_signal_outputs(self):
        seed = {
            "signal_outputs": [
                {"name": "registry-update", "class": "data", "description": "Emits updates"},
            ],
        }
        ports = get_signal_outputs(seed)
        assert len(ports) == 1
        assert ports[0].name == "registry-update"
        assert ports[0].signal_class == "data"


class TestBuildSignalGraph:
    def test_empty_seeds(self):
        graph = build_signal_graph({})
        assert graph.nodes == []
        assert graph.edges == []

    def test_no_signals_declared(self):
        seeds = {
            "org/repo-a": {"organ": "I", "repo": "repo-a"},
            "org/repo-b": {"organ": "I", "repo": "repo-b"},
        }
        graph = build_signal_graph(seeds)
        assert len(graph.nodes) == 2
        assert graph.edges == []

    def test_matching_output_to_input(self):
        seeds = {
            "meta-organvm/engine": {
                "signal_outputs": [
                    {"name": "registry-update", "class": "data"},
                ],
            },
            "meta-organvm/dashboard": {
                "signal_inputs": [
                    {"name": "registry-update", "class": "data"},
                ],
            },
        }
        graph = build_signal_graph(seeds)
        assert len(graph.edges) == 1
        edge = graph.edges[0]
        assert edge.source == "meta-organvm/engine"
        assert edge.target == "meta-organvm/dashboard"
        assert edge.signal_name == "registry-update"
        assert edge.signal_class == "data"

    def test_no_match_different_name(self):
        seeds = {
            "org/producer": {
                "signal_outputs": [{"name": "signal-a", "class": "data"}],
            },
            "org/consumer": {
                "signal_inputs": [{"name": "signal-b", "class": "data"}],
            },
        }
        graph = build_signal_graph(seeds)
        assert graph.edges == []
        assert len(graph.unmatched_inputs) == 1
        assert len(graph.unmatched_outputs) == 1

    def test_no_match_different_class(self):
        seeds = {
            "org/producer": {
                "signal_outputs": [{"name": "update", "class": "data"}],
            },
            "org/consumer": {
                "signal_inputs": [{"name": "update", "class": "governance"}],
            },
        }
        graph = build_signal_graph(seeds)
        assert graph.edges == []

    def test_no_self_connections(self):
        seeds = {
            "org/repo": {
                "signal_outputs": [{"name": "internal", "class": "data"}],
                "signal_inputs": [{"name": "internal", "class": "data"}],
            },
        }
        graph = build_signal_graph(seeds)
        assert graph.edges == []

    def test_multiple_consumers(self):
        seeds = {
            "org/producer": {
                "signal_outputs": [{"name": "broadcast", "class": "event"}],
            },
            "org/consumer-a": {
                "signal_inputs": [{"name": "broadcast", "class": "event"}],
            },
            "org/consumer-b": {
                "signal_inputs": [{"name": "broadcast", "class": "event"}],
            },
        }
        graph = build_signal_graph(seeds)
        assert len(graph.edges) == 2
        targets = {e.target for e in graph.edges}
        assert targets == {"org/consumer-a", "org/consumer-b"}

    def test_unmatched_input_tracked(self):
        seeds = {
            "org/consumer": {
                "signal_inputs": [{"name": "orphan-signal", "class": "data"}],
            },
        }
        graph = build_signal_graph(seeds)
        assert len(graph.unmatched_inputs) == 1
        assert graph.unmatched_inputs[0][0] == "org/consumer"
        assert graph.unmatched_inputs[0][1].name == "orphan-signal"

    def test_unmatched_output_tracked(self):
        seeds = {
            "org/producer": {
                "signal_outputs": [{"name": "unused-signal", "class": "data"}],
            },
        }
        graph = build_signal_graph(seeds)
        assert len(graph.unmatched_outputs) == 1
        assert graph.unmatched_outputs[0][0] == "org/producer"

    def test_summary_output(self):
        seeds = {
            "org/a": {
                "signal_outputs": [{"name": "sig", "class": "data"}],
            },
            "org/b": {
                "signal_inputs": [{"name": "sig", "class": "data"}],
            },
        }
        graph = build_signal_graph(seeds)
        summary = graph.summary()
        assert "2 repos" in summary
        assert "1 connection" in summary
        assert "sig" in summary
