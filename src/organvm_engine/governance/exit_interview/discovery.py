"""Phase 0: Discovery — parse gate contracts, build demand/supply maps.

Reads all gate contract YAML files from a-organvm (or any directory),
extracts source references, and builds two complementary indexes:

  Demand map (gate → V1 modules): what does each gate contract claim?
  Supply map (V1 module → gates): which gates claim each V1 artifact?

Also identifies orphaned V1 governance artifacts — modules not referenced
by any gate contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from organvm_engine.governance.exit_interview.schemas import (
    DemandEntry,
    GateCheck,
    GateContract,
    GateSource,
    OrphanEntry,
    SupplyEntry,
)

# ---------------------------------------------------------------------------
# Gate contract parsing
# ---------------------------------------------------------------------------


def _is_gate_contract(data: dict) -> bool:
    """Filter: true if YAML has identity + gate keys (excludes structural files)."""
    return isinstance(data.get("identity"), dict) and isinstance(data.get("gate"), list)


def parse_gate_contract(path: Path) -> GateContract | None:
    """Parse a single gate contract YAML file.

    Returns None if the file is not a gate contract (e.g. signal-graph.yaml).
    """
    with path.open() as f:
        data = yaml.safe_load(f)

    if not data or not _is_gate_contract(data):
        return None

    identity = data["identity"]

    sources = []
    for src in data.get("sources", []):
        sources.append(
            GateSource(
                repo=src.get("repo", ""),
                modules=src.get("modules", []),
                lines=src.get("lines", 0),
                note=src.get("note", ""),
                isotope=src.get("isotope", False),
                resolution=src.get("resolution", ""),
            ),
        )

    gates = []
    for g in data.get("gate", []):
        gates.append(
            GateCheck(
                id=g.get("id", ""),
                check=g.get("check", ""),
                condition=g.get("condition", ""),
                status=g.get("status", "PENDING"),
                note=g.get("note", ""),
            ),
        )

    return GateContract(
        name=identity.get("name", path.stem),
        mechanism=identity.get("mechanism", ""),
        verb=identity.get("verb", ""),
        signal_inputs=identity.get("signal_inputs", []),
        signal_outputs=identity.get("signal_outputs", []),
        sources=sources,
        gates=gates,
        dna=data.get("dna", []),
        defects=data.get("defect", []),
        state=data.get("state", "CALLING"),
        file_path=str(path),
    )


def load_gate_contracts(gate_dir: Path) -> list[GateContract]:
    """Load all gate contracts from a directory.

    Filters out non-gate YAML files (cocoon-map.yaml, signal-graph.yaml, etc.)
    by checking for identity + gate keys.
    """
    contracts = []
    for yaml_path in sorted(gate_dir.glob("*.yaml")):
        contract = parse_gate_contract(yaml_path)
        if contract is not None:
            contracts.append(contract)
    return contracts


# ---------------------------------------------------------------------------
# Demand map (gate-indexed)
# ---------------------------------------------------------------------------


@dataclass
class DemandMap:
    """Gate-indexed: for each gate contract, which V1 modules does it claim?"""

    entries: dict[str, list[DemandEntry]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            gate: [e.to_dict() for e in entries]
            for gate, entries in self.entries.items()
        }


def build_demand_map(contracts: list[GateContract]) -> DemandMap:
    """Build the demand map from parsed gate contracts.

    For each gate contract, enumerate all V1 modules it references via sources.
    Each source module list entry becomes a DemandEntry with the gate's context.
    """
    dm = DemandMap()
    for contract in contracts:
        entries = []
        gate_ids = [g.id for g in contract.gates]
        for source in contract.sources:
            for _module in source.modules:
                entries.append(
                    DemandEntry(
                        gate_name=contract.name,
                        gate_ids=gate_ids,
                        mechanism=contract.mechanism,
                        verb=contract.verb,
                        expected_signals=contract.signal_inputs + contract.signal_outputs,
                        expected_lines=source.lines,
                        isotope=source.isotope,
                        resolution=source.resolution,
                    ),
                )
        dm.entries[contract.name] = entries
    return dm


# ---------------------------------------------------------------------------
# Supply map (V1-module-indexed)
# ---------------------------------------------------------------------------


@dataclass
class SupplyMap:
    """V1-indexed: for each V1 module, which gates claim it?"""

    entries: dict[str, SupplyEntry] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {path: entry.to_dict() for path, entry in self.entries.items()}


def _module_key(repo: str, module: str) -> str:
    """Canonical key for a V1 module: 'repo/module' with trailing slash stripped."""
    module = module.rstrip("/")
    return f"{repo}/{module}"


def build_supply_map(contracts: list[GateContract]) -> SupplyMap:
    """Build the supply map — invert the demand map to V1-module-indexed view.

    Each V1 module path accumulates all gate contracts that claim it.
    """
    sm = SupplyMap()
    for contract in contracts:
        gate_ids = [g.id for g in contract.gates]
        for source in contract.sources:
            for module in source.modules:
                key = _module_key(source.repo, module)
                if key not in sm.entries:
                    sm.entries[key] = SupplyEntry(
                        v1_path=module.rstrip("/"),
                        repo=source.repo,
                    )
                sm.entries[key].demands.append(
                    DemandEntry(
                        gate_name=contract.name,
                        gate_ids=gate_ids,
                        mechanism=contract.mechanism,
                        verb=contract.verb,
                        expected_signals=contract.signal_inputs + contract.signal_outputs,
                        expected_lines=source.lines,
                        isotope=source.isotope,
                        resolution=source.resolution,
                    ),
                )
    return sm


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def _list_governance_modules(workspace_root: Path) -> list[tuple[str, str]]:
    """List V1 governance-related modules from the engine.

    Returns (repo, module_path) tuples for all Python modules in the
    governance package.
    """
    engine_gov = workspace_root / "meta-organvm" / "organvm-engine" / "src" / "organvm_engine" / "governance"
    modules = []
    if engine_gov.is_dir():
        for item in sorted(engine_gov.iterdir()):
            if item.name.startswith(("_", ".")):
                continue
            if item.is_dir() or item.suffix == ".py":
                modules.append(("meta-organvm/organvm-engine", f"governance/{item.name}"))
    return modules


def find_orphans(
    supply_map: SupplyMap,
    workspace_root: Path,
) -> list[OrphanEntry]:
    """Find V1 governance modules not referenced by any gate contract.

    Compares the supply map against the actual governance directory contents.
    Modules in the supply map have at least one gate claiming them; those
    absent are orphans.
    """
    claimed_prefixes = set()
    for key in supply_map.entries:
        # Key format: "meta-organvm/organvm-engine/governance/..."
        # We extract the module part after the repo prefix
        parts = key.split("/", 2)
        if len(parts) >= 3:
            claimed_prefixes.add(parts[2].rstrip("/"))

    orphans = []
    for repo, module_path in _list_governance_modules(workspace_root):
        module_name = module_path.rstrip("/")
        # Check if this module is claimed by any gate (prefix match)
        claimed = any(
            module_name.startswith(prefix) or prefix.startswith(module_name)
            for prefix in claimed_prefixes
        )
        if not claimed:
            orphans.append(
                OrphanEntry(
                    v1_path=module_path,
                    repo=repo,
                    artifact_type="module",
                ),
            )
    return orphans


# ---------------------------------------------------------------------------
# Full discovery
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryResult:
    """Complete discovery result."""

    contracts: list[GateContract]
    demand_map: DemandMap
    supply_map: SupplyMap
    orphans: list[OrphanEntry]

    def summary(self) -> str:
        lines = [
            f"Gate contracts: {len(self.contracts)}",
            f"V1 modules claimed: {len(self.supply_map.entries)}",
            f"Orphaned modules: {len(self.orphans)}",
        ]
        if self.orphans:
            lines.append("  Orphans:")
            for o in self.orphans:
                lines.append(f"    - {o.v1_path}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "contracts": [c.to_dict() for c in self.contracts],
            "demand_map": self.demand_map.to_dict(),
            "supply_map": self.supply_map.to_dict(),
            "orphans": [o.to_dict() for o in self.orphans],
        }


def discover(
    gate_dir: Path,
    workspace_root: Path | None = None,
) -> DiscoveryResult:
    """Run full discovery: parse gates, build maps, find orphans.

    Args:
        gate_dir: Directory containing gate contract YAML files.
        workspace_root: Workspace root for orphan detection.
            If None, orphan detection is skipped.
    """
    contracts = load_gate_contracts(gate_dir)
    demand_map = build_demand_map(contracts)
    supply_map = build_supply_map(contracts)

    orphans = []
    if workspace_root is not None:
        orphans = find_orphans(supply_map, workspace_root)

    return DiscoveryResult(
        contracts=contracts,
        demand_map=demand_map,
        supply_map=supply_map,
        orphans=orphans,
    )
