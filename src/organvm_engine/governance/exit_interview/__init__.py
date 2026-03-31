"""Exit interview protocol — presidential handoff between system versions.

Formalizes A9 (Alchemical Inheritance): V1 governance artifacts testify about
themselves in V2's vocabulary, V2 gate contracts state expectations in the same
format, and a rectification engine diffs the two voices against reality.

Five phases:
  0. Discovery   — parse gate contracts, build demand/supply maps
  1. Testimony   — V1 artifacts self-describe in V2-native format
  2. Counter     — V2 gate contracts state expectations in same format
  3. Rectify     — three-voice symmetrical diff (V1 / V2 / actuality)
  4. Remediate   — convert deltas to actionable items
"""

from organvm_engine.governance.exit_interview.schemas import (
    AxiomClaim,
    CounterTestimony,
    DemandEntry,
    DimensionVerdict,
    GateContract,
    GateSource,
    OrphanEntry,
    RectificationReport,
    RemediationItem,
    SupplyEntry,
    Testimony,
    Verdict,
)

__all__ = [
    "AxiomClaim",
    "CounterTestimony",
    "DemandEntry",
    "DimensionVerdict",
    "GateContract",
    "GateSource",
    "OrphanEntry",
    "RectificationReport",
    "RemediationItem",
    "SupplyEntry",
    "Testimony",
    "Verdict",
]
