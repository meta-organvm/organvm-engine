"""Phase 2: V2 Counter-Testimony — incoming expectations from gate contracts.

For each gate contract, reformulate its dna/defect/gate/sources fields into
the same 7-dimension testimony format that V1 uses. This creates a symmetric
pair: V1 says what it IS, V2 says what it EXPECTS, rectification diffs them.

The raw material already exists in gate contracts:
  - identity.signal_inputs/outputs → signals
  - sources[].modules + lines → existence expectations
  - dna[] → identity, structure, law
  - defect[] → flagged contradictions
  - gate[].condition → law, process
  - gate[].check tracing to axiom → teleology
"""

from __future__ import annotations

import re
from pathlib import Path

from organvm_engine.governance.exit_interview.schemas import (
    CounterTestimony,
    GateContract,
    GateSource,
)

# Map gate check names to axioms
_CHECK_TO_AXIOM: dict[str, str] = {
    "ISOTOPES_RESOLVED": "A5",  # minimality — no duplicates
    "CANONICAL_REGISTRY": "A5",
    "CANONICAL_ORGAN_MAP": "A5",
    "SIGNAL_DECLARED": "A2",  # composition — explicit signal contracts
    "TESTS_PASS": "A3",  # persistence — system must maintain itself
    "NO_PROHIBITED_COUPLING": "A6",  # organizational closure
    "TRACEABILITY": "A6",
    "GRANULARITY": "A5",  # minimality
    "STANDALONE_SCRIPTS_DISSOLVED": "A5",
    "INDEX_CANONICALIZED": "A5",
}


def _axiom_from_check(check_name: str) -> str:
    """Map a gate check name to its most likely axiom."""
    return _CHECK_TO_AXIOM.get(check_name, "")


def _extract_law_from_gates(contract: GateContract) -> str:
    """Extract law dimension from gate conditions."""
    conditions = []
    for gate in contract.gates:
        conditions.append(f"[{gate.id}] {gate.condition}")
    return "; ".join(conditions) if conditions else "No gate conditions specified"


def _extract_process_from_gates(contract: GateContract) -> str:
    """Extract process expectations from gate checks."""
    checks = [f"{g.check} ({g.status})" for g in contract.gates]
    return f"Required checks: {', '.join(checks)}" if checks else "No process checks"


def _extract_identity_from_dna(contract: GateContract) -> str:
    """Extract identity expectation from dna field."""
    if contract.dna:
        # Take first dna entry as primary identity
        first = contract.dna[0]
        # Strip leading " - " if present
        if isinstance(first, str):
            return first.lstrip("- ").split("—")[0].strip()
    return f"{contract.mechanism}--{contract.verb}"


def _extract_structure_from_dna(contract: GateContract) -> str:
    """Extract expected structure from dna entries."""
    if not contract.dna:
        return "No structural expectations declared"
    parts = []
    for entry in contract.dna:
        if isinstance(entry, str):
            # Extract the module name before the em-dash
            module = entry.lstrip("- ").split("—")[0].strip()
            parts.append(module)
    return f"Expected modules: {', '.join(parts)}" if parts else "No structure specified"


def _extract_teleology_from_gates(contract: GateContract) -> str:
    """Extract purpose/axiom alignment from gate checks."""
    axioms = set()
    for gate in contract.gates:
        axiom = _axiom_from_check(gate.check)
        if axiom:
            axioms.add(axiom)
        # Also check condition text for axiom references (e.g. "upward trace to A6")
        for match in re.findall(r"A\d", gate.condition):
            axioms.add(match)
    if axioms:
        return f"Serves {', '.join(sorted(axioms))}"
    return "No axiom traceability declared in gate checks"


def _extract_relation_from_sources(source: GateSource, contract: GateContract) -> str:
    """Extract relation expectations for a specific source."""
    parts = []
    if source.isotope:
        parts.append(f"ISOTOPE — resolution: {source.resolution}")
    # Check defects for relation info
    for defect in contract.defects:
        if isinstance(defect, str) and any(
            mod in defect for mod in source.modules
        ):
            parts.append(f"defect: {defect}")
    if not parts:
        parts.append(f"Expected as source for {contract.name}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Counter-testimony generation
# ---------------------------------------------------------------------------


def generate_counter_testimony(
    contract: GateContract,
    source: GateSource,
    module: str,
) -> CounterTestimony:
    """Generate V2 counter-testimony for a specific V1 module within a gate contract.

    Args:
        contract: The parsed gate contract.
        source: The specific source entry referencing this V1 repo.
        module: The specific module path within the source.
    """
    gate_ids = [g.id for g in contract.gates]

    return CounterTestimony(
        v1_path=f"{source.repo}/{module.rstrip('/')}",
        v2_mechanism=contract.mechanism,
        v2_verb=contract.verb,
        gate_source=Path(contract.file_path).name if contract.file_path else f"{contract.name}.yaml",
        existence={
            "required": True,
            "expected_lines": source.lines,
            "note": f"Part of {source.repo} source pool ({source.lines} lines total)",
        },
        identity=_extract_identity_from_dna(contract),
        structure=_extract_structure_from_dna(contract),
        law=_extract_law_from_gates(contract),
        process=_extract_process_from_gates(contract),
        relation=_extract_relation_from_sources(source, contract),
        teleology=_extract_teleology_from_gates(contract),
        expected_consumes=contract.signal_inputs,
        expected_produces=contract.signal_outputs,
        defects_flagged=[d for d in contract.defects if isinstance(d, str)],
        gates_served=[f"{contract.name}/{gid}" for gid in gate_ids],
    )


def generate_all_counter_testimonies(
    contracts: list[GateContract],
) -> dict[str, CounterTestimony]:
    """Generate counter-testimony for all V1 modules across all gate contracts.

    Returns dict keyed by 'repo/module' path, same as supply map keys.
    """
    counter = {}
    for contract in contracts:
        for source in contract.sources:
            for module in source.modules:
                key = f"{source.repo}/{module.rstrip('/')}"
                # If a module is claimed by multiple gates, use the first one
                # (a more sophisticated approach would merge expectations)
                if key not in counter:
                    counter[key] = generate_counter_testimony(contract, source, module)
    return counter
