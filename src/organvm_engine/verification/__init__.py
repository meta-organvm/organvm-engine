"""Formal verification module — proving the organ dispatch pipeline.

Three vulnerability classes addressed:
1. Vacuous truths — dispatch triggers on boolean status, not payload substance
2. Race conditions — fire-and-forget routing with no receipt/handshake
3. Linear logic failures — no idempotency, duplicate events can cascade

Four formal logic layers:
- contracts.py — Hoare Logic (pre/post conditions per event type)
- temporal.py — Temporal Logic (DAG ordering enforcement)
- idempotency.py — Linear Logic (consumption semantics, dispatch ledger)
- model_check.py — Bounded Model Checking (system-wide verification)
"""

from organvm_engine.verification.contracts import (
    CONTRACTS,
    ContractResult,
    DispatchContract,
    verify_contract,
)
from organvm_engine.verification.idempotency import DispatchLedger
from organvm_engine.verification.model_check import VerificationReport, verify_system
from organvm_engine.verification.temporal import (
    verify_prerequisite_chain,
    verify_temporal_order,
)

__all__ = [
    "CONTRACTS",
    "ContractResult",
    "DispatchContract",
    "DispatchLedger",
    "VerificationReport",
    "verify_contract",
    "verify_prerequisite_chain",
    "verify_system",
    "verify_temporal_order",
]
