"""Tests for exit interview Phase 0: Discovery."""

from pathlib import Path

import pytest

from organvm_engine.governance.exit_interview.discovery import (
    DiscoveryResult,
    build_demand_map,
    build_supply_map,
    discover,
    load_gate_contracts,
    parse_gate_contract,
)
from organvm_engine.governance.exit_interview.schemas import GateContract

FIXTURES = Path(__file__).parent / "fixtures" / "gate-contracts"


class TestParseGateContract:
    def test_parses_valid_contract(self):
        contract = parse_gate_contract(FIXTURES / "nervous--govern.yaml")
        assert contract is not None
        assert contract.name == "nervous--govern"
        assert contract.mechanism == "nervous"
        assert contract.verb == "govern"

    def test_extracts_sources(self):
        contract = parse_gate_contract(FIXTURES / "nervous--govern.yaml")
        assert len(contract.sources) == 2
        assert contract.sources[0].repo == "meta-organvm/organvm-engine"
        assert "governance/" in contract.sources[0].modules

    def test_extracts_gates(self):
        contract = parse_gate_contract(FIXTURES / "nervous--govern.yaml")
        assert len(contract.gates) == 3
        assert contract.gates[0].id == "G1"
        assert contract.gates[0].check == "ISOTOPES_RESOLVED"

    def test_extracts_dna(self):
        contract = parse_gate_contract(FIXTURES / "nervous--govern.yaml")
        assert len(contract.dna) == 3

    def test_extracts_defects(self):
        contract = parse_gate_contract(FIXTURES / "nervous--govern.yaml")
        assert len(contract.defects) == 2

    def test_filters_non_gate_files(self):
        """signal-graph.yaml has no identity+gate keys, should return None."""
        contract = parse_gate_contract(FIXTURES / "signal-graph.yaml")
        assert contract is None


class TestLoadGateContracts:
    def test_loads_only_gate_contracts(self):
        contracts = load_gate_contracts(FIXTURES)
        names = [c.name for c in contracts]
        assert "nervous--govern" in names
        assert "skeletal--define" in names
        # signal-graph.yaml should be excluded
        assert not any("signal" in n for n in names)

    def test_returns_sorted(self):
        contracts = load_gate_contracts(FIXTURES)
        names = [c.name for c in contracts]
        assert names == sorted(names)


class TestDemandMap:
    def test_builds_demand_entries(self):
        contracts = load_gate_contracts(FIXTURES)
        dm = build_demand_map(contracts)
        assert "nervous--govern" in dm.entries
        assert len(dm.entries["nervous--govern"]) > 0

    def test_demand_entries_have_gate_ids(self):
        contracts = load_gate_contracts(FIXTURES)
        dm = build_demand_map(contracts)
        entry = dm.entries["nervous--govern"][0]
        assert "G1" in entry.gate_ids
        assert entry.mechanism == "nervous"


class TestSupplyMap:
    def test_builds_supply_entries(self):
        contracts = load_gate_contracts(FIXTURES)
        sm = build_supply_map(contracts)
        # governance/ is claimed by nervous--govern
        key = "meta-organvm/organvm-engine/governance"
        assert key in sm.entries

    def test_supply_entry_tracks_demands(self):
        contracts = load_gate_contracts(FIXTURES)
        sm = build_supply_map(contracts)
        key = "meta-organvm/organvm-engine/governance"
        entry = sm.entries[key]
        assert any(d.gate_name == "nervous--govern" for d in entry.demands)

    def test_module_claimed_by_multiple_gates(self):
        """registry/ is claimed by skeletal--define; governance/ by nervous--govern."""
        contracts = load_gate_contracts(FIXTURES)
        sm = build_supply_map(contracts)
        reg_key = "meta-organvm/organvm-engine/registry"
        gov_key = "meta-organvm/organvm-engine/governance"
        assert reg_key in sm.entries
        assert gov_key in sm.entries
        assert sm.entries[reg_key].gate_names != sm.entries[gov_key].gate_names


class TestDiscover:
    def test_full_discovery(self):
        result = discover(FIXTURES, workspace_root=None)
        assert isinstance(result, DiscoveryResult)
        assert len(result.contracts) == 2
        assert len(result.supply_map.entries) > 0
        # No orphan detection without workspace_root
        assert result.orphans == []

    def test_summary_output(self):
        result = discover(FIXTURES)
        summary = result.summary()
        assert "Gate contracts:" in summary
        assert "V1 modules claimed:" in summary

    def test_to_dict_serializable(self):
        result = discover(FIXTURES)
        d = result.to_dict()
        assert "contracts" in d
        assert "demand_map" in d
        assert "supply_map" in d
