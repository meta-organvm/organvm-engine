"""Signal I/O graph from seed.yaml declarations.

Implements: AX-009 (Modular Alchemical Synthesis) — signal inputs/outputs.

Each seed.yaml may declare:
    signal_inputs:
      - name: governance-policy
        class: governance
        description: "Receives governance rules updates"
    signal_outputs:
      - name: registry-update
        class: data
        description: "Emits registry change notifications"

This module reads those declarations and builds a signal graph connecting
repos through their declared signal I/O.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Canonical signal classes from AX-009.
# This is the initial minimal set; the full 14-class taxonomy from SPEC-000
# can be added as the system matures.
SIGNAL_CLASSES: tuple[str, ...] = (
    "data",
    "governance",
    "lifecycle",
    "content",
    "event",
    "metric",
    "error",
)


@dataclass
class SignalPort:
    """A single signal input or output declared in a seed.yaml."""

    name: str
    signal_class: str
    description: str = ""

    def is_valid_class(self) -> bool:
        """Check if the signal class is one of the canonical classes."""
        return self.signal_class in SIGNAL_CLASSES


@dataclass
class SignalEdge:
    """A connection between a signal output and a matching signal input."""

    source: str  # org/repo identity of the output
    target: str  # org/repo identity of the input
    signal_name: str  # matching signal name
    signal_class: str  # signal class


@dataclass
class SignalGraph:
    """Graph of signal connections across all seeds."""

    nodes: list[str] = field(default_factory=list)
    inputs: dict[str, list[SignalPort]] = field(default_factory=dict)
    outputs: dict[str, list[SignalPort]] = field(default_factory=dict)
    edges: list[SignalEdge] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unmatched_inputs: list[tuple[str, SignalPort]] = field(default_factory=list)
    unmatched_outputs: list[tuple[str, SignalPort]] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary of the signal graph."""
        lines = [
            f"Signal Graph: {len(self.nodes)} repos, {len(self.edges)} connection(s)",
        ]
        if self.edges:
            lines.append("\nSignal connections:")
            for e in self.edges:
                lines.append(f"  {e.source} --[{e.signal_name} ({e.signal_class})]-> {e.target}")
        if self.unmatched_inputs:
            lines.append(f"\nUnmatched inputs: {len(self.unmatched_inputs)}")
            for identity, port in self.unmatched_inputs:
                lines.append(f"  {identity}: {port.name} ({port.signal_class})")
        if self.unmatched_outputs:
            lines.append(f"\nUnmatched outputs: {len(self.unmatched_outputs)}")
            for identity, port in self.unmatched_outputs:
                lines.append(f"  {identity}: {port.name} ({port.signal_class})")
        if self.errors:
            lines.append(f"\nErrors: {len(self.errors)}")
            for e in self.errors:
                lines.append(f"  {e}")
        return "\n".join(lines)


def get_signal_inputs(seed: dict) -> list[SignalPort]:
    """Extract signal_inputs from a seed dict.

    Args:
        seed: Parsed seed.yaml dict.

    Returns:
        List of SignalPort objects for inputs.
    """
    raw = seed.get("signal_inputs")
    if not isinstance(raw, list):
        return []
    ports: list[SignalPort] = []
    for entry in raw:
        if isinstance(entry, dict) and "name" in entry:
            ports.append(SignalPort(
                name=entry["name"],
                signal_class=entry.get("class", "data"),
                description=entry.get("description", ""),
            ))
    return ports


def get_signal_outputs(seed: dict) -> list[SignalPort]:
    """Extract signal_outputs from a seed dict.

    Args:
        seed: Parsed seed.yaml dict.

    Returns:
        List of SignalPort objects for outputs.
    """
    raw = seed.get("signal_outputs")
    if not isinstance(raw, list):
        return []
    ports: list[SignalPort] = []
    for entry in raw:
        if isinstance(entry, dict) and "name" in entry:
            ports.append(SignalPort(
                name=entry["name"],
                signal_class=entry.get("class", "data"),
                description=entry.get("description", ""),
            ))
    return ports


def build_signal_graph(
    seeds_by_identity: dict[str, dict],
) -> SignalGraph:
    """Build a signal graph from pre-parsed seeds.

    Matches signal outputs to signal inputs by name and class.
    An output connects to an input when both the signal name and
    signal class match.

    Args:
        seeds_by_identity: Dict mapping "org/repo" identity to parsed seed dict.

    Returns:
        SignalGraph with nodes, edges, and unmatched ports.
    """
    graph = SignalGraph()

    # Parse all signal ports
    for identity, seed in seeds_by_identity.items():
        graph.nodes.append(identity)
        inputs = get_signal_inputs(seed)
        outputs = get_signal_outputs(seed)
        if inputs:
            graph.inputs[identity] = inputs
        if outputs:
            graph.outputs[identity] = outputs

    # Index outputs by (name, class) for matching
    output_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for identity, ports in graph.outputs.items():
        for port in ports:
            output_index[(port.name, port.signal_class)].append(identity)

    # Match inputs to outputs
    matched_inputs: set[tuple[str, str]] = set()  # (identity, port.name)
    matched_outputs: set[tuple[str, str]] = set()  # (identity, port.name)

    for identity, ports in graph.inputs.items():
        for port in ports:
            key = (port.name, port.signal_class)
            producers = output_index.get(key, [])
            for producer in producers:
                if producer == identity:
                    continue  # skip self-connections
                graph.edges.append(SignalEdge(
                    source=producer,
                    target=identity,
                    signal_name=port.name,
                    signal_class=port.signal_class,
                ))
                matched_inputs.add((identity, port.name))
                matched_outputs.add((producer, port.name))

    # Identify unmatched ports
    for identity, ports in graph.inputs.items():
        for port in ports:
            if (identity, port.name) not in matched_inputs:
                graph.unmatched_inputs.append((identity, port))

    for identity, ports in graph.outputs.items():
        for port in ports:
            if (identity, port.name) not in matched_outputs:
                graph.unmatched_outputs.append((identity, port))

    return graph


def build_signal_graph_from_workspace(
    workspace: Path | str | None = None,
    orgs: list[str] | None = None,
) -> SignalGraph:
    """Build a signal graph by discovering seeds from the workspace.

    Convenience wrapper that discovers seed.yaml files and builds
    the signal graph from them.

    Args:
        workspace: Root workspace directory.
        orgs: Org directories to scan.

    Returns:
        SignalGraph with nodes, edges, and any errors.
    """
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed, seed_identity

    graph_seeds: dict[str, dict] = {}
    errors: list[str] = []

    seed_paths = discover_seeds(workspace, orgs)
    for path in seed_paths:
        try:
            seed = read_seed(path)
            identity = seed_identity(seed)
            graph_seeds[identity] = seed
        except Exception as e:
            errors.append(f"{path}: {e}")

    result = build_signal_graph(graph_seeds)
    result.errors.extend(errors)
    return result
