"""Tests for exit interview Phase 2: V2 Counter-Testimony."""

from pathlib import Path

from organvm_engine.governance.exit_interview.counter_testimony import (
    generate_all_counter_testimonies,
    generate_counter_testimony,
)
from organvm_engine.governance.exit_interview.discovery import load_gate_contracts
from organvm_engine.governance.exit_interview.schemas import CounterTestimony

FIXTURES = Path(__file__).parent / "fixtures" / "gate-contracts"


class TestGenerateCounterTestimony:
    def test_generates_from_gate_contract(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        assert isinstance(ct, CounterTestimony)
        assert ct.v2_mechanism == "nervous"
        assert ct.v2_verb == "govern"

    def test_counter_has_existence_expectations(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        assert ct.existence["required"] is True
        assert ct.existence["expected_lines"] == 10500

    def test_counter_has_expected_signals(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        assert "TRACE" in ct.expected_consumes
        assert "RULE" in ct.expected_produces

    def test_counter_captures_defects(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        assert len(ct.defects_flagged) == 2

    def test_counter_has_law_from_gate_conditions(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        assert "G1" in ct.law
        assert "imports from engine governance" in ct.law

    def test_counter_has_teleology_from_axioms(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        # ISOTOPES_RESOLVED maps to A5, SIGNAL_DECLARED to A2
        assert "A5" in ct.teleology or "A2" in ct.teleology

    def test_counter_serializes_to_dict(self):
        contracts = load_gate_contracts(FIXTURES)
        nervous = next(c for c in contracts if c.name == "nervous--govern")
        source = nervous.sources[0]
        module = source.modules[0]

        ct = generate_counter_testimony(nervous, source, module)
        d = ct.to_dict()
        assert "identity" in d
        assert "expectation" in d
        assert "signals" in d
        assert "defects_flagged" in d


class TestGenerateAllCounterTestimonies:
    def test_generates_for_all_modules(self):
        contracts = load_gate_contracts(FIXTURES)
        counter = generate_all_counter_testimonies(contracts)
        assert len(counter) > 0
        for _key, ct in counter.items():
            assert isinstance(ct, CounterTestimony)

    def test_keys_match_supply_map_format(self):
        """Keys should be 'repo/module' format."""
        contracts = load_gate_contracts(FIXTURES)
        counter = generate_all_counter_testimonies(contracts)
        for key in counter:
            assert "/" in key
            # Should contain at least repo/module
            parts = key.split("/")
            assert len(parts) >= 3  # org/repo/module
