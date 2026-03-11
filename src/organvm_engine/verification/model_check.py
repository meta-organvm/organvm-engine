"""Bounded Model Checking — system-wide verification orchestrator.

Runs all three verification layers (contracts, temporal, idempotency)
against the live system state and produces a unified report.

Read-only: verify_system() never mutates state, only reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from organvm_engine.verification.contracts import CONTRACTS
from organvm_engine.verification.idempotency import DispatchLedger
from organvm_engine.verification.temporal import verify_prerequisite_chain


@dataclass
class VerificationReport:
    """Unified verification report across all formal logic layers."""

    vacuous_truths: list[str] = field(default_factory=list)
    temporal_violations: list[str] = field(default_factory=list)
    idempotency_risks: list[str] = field(default_factory=list)
    contract_coverage: float = 0.0
    uncovered_events: list[str] = field(default_factory=list)
    contracts_checked: int = 0
    contracts_passed: int = 0
    temporal_checks: int = 0
    temporal_passed: int = 0
    ledger_total: int = 0
    ledger_pending: int = 0
    ledger_duplicates: int = 0

    @property
    def passed(self) -> bool:
        return (
            len(self.vacuous_truths) == 0
            and len(self.temporal_violations) == 0
            and len(self.idempotency_risks) == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "vacuous_truths": self.vacuous_truths,
            "temporal_violations": self.temporal_violations,
            "idempotency_risks": self.idempotency_risks,
            "contract_coverage": round(self.contract_coverage, 2),
            "uncovered_events": self.uncovered_events,
            "contracts_checked": self.contracts_checked,
            "contracts_passed": self.contracts_passed,
            "temporal_checks": self.temporal_checks,
            "temporal_passed": self.temporal_passed,
            "ledger_total": self.ledger_total,
            "ledger_pending": self.ledger_pending,
            "ledger_duplicates": self.ledger_duplicates,
        }


def _collect_event_types(seed_graph: dict[str, dict]) -> set[str]:
    """Collect all event types from seed graph (produces, consumes, subscriptions)."""
    from organvm_engine.seed.reader import get_consumes, get_produces, get_subscriptions

    events: set[str] = set()
    for _identity, seed in seed_graph.items():
        for prod in get_produces(seed):
            if isinstance(prod, str):
                events.add(prod)
            elif isinstance(prod, dict):
                t = prod.get("type", "")
                if t:
                    events.add(t)

        for cons in get_consumes(seed):
            if isinstance(cons, str):
                events.add(cons)
            elif isinstance(cons, dict):
                t = cons.get("type", "")
                if t:
                    events.add(t)

        for sub in get_subscriptions(seed):
            evt = sub.get("event", "")
            if evt:
                events.add(evt)

    return events


def verify_system(
    registry: dict,
    seed_graph: dict[str, dict],
    ledger: DispatchLedger | None = None,
) -> VerificationReport:
    """Run full model check against system state.

    Args:
        registry: Loaded registry dict.
        seed_graph: Dict of identity -> seed data.
        ledger: Optional dispatch ledger (creates default if None).

    Returns:
        VerificationReport with all findings.
    """
    report = VerificationReport()

    # --- Layer 1: Contract coverage ---
    all_events = _collect_event_types(seed_graph)
    covered = set(CONTRACTS.keys())
    uncovered = all_events - covered

    report.uncovered_events = sorted(uncovered)
    if all_events:
        report.contract_coverage = len(covered & all_events) / len(all_events) * 100
    else:
        report.contract_coverage = 100.0

    # Check each registered contract for vacuous truths:
    # A contract with no required fields is vacuous (passes any dict)
    for event_type, contract in CONTRACTS.items():
        report.contracts_checked += 1
        if not contract.required_payload_fields:
            report.vacuous_truths.append(
                f"Contract '{event_type}' has no required payload fields — vacuous",
            )
        else:
            # Verify the contract itself is self-consistent
            # (validators reference fields that exist in required_payload_fields)
            for vfield in contract.required_payload_validators:
                if vfield not in contract.required_payload_fields:
                    report.vacuous_truths.append(
                        f"Contract '{event_type}': validator for '{vfield}' "
                        f"but field not in required_payload_fields",
                    )
            report.contracts_passed += 1

    # --- Layer 2: Temporal ordering ---
    for event_type in all_events:
        prereq = verify_prerequisite_chain(event_type, seed_graph)
        report.temporal_checks += 1
        if prereq.passed:
            report.temporal_passed += 1
        else:
            report.temporal_violations.extend(prereq.violations)

    # --- Layer 3: Idempotency (ledger state) ---
    if ledger is not None:
        ledger_status = ledger.status()
        report.ledger_total = ledger_status.total
        report.ledger_pending = ledger_status.pending

        # Check for duplicate dispatches (same event+source+target)
        seen_signatures: dict[str, list[str]] = {}
        for entry in ledger_status.entries:
            sig = f"{entry.event}|{entry.source}|{entry.target}"
            seen_signatures.setdefault(sig, []).append(entry.dispatch_id)

        for sig, ids in seen_signatures.items():
            if len(ids) > 1:
                report.ledger_duplicates += 1
                report.idempotency_risks.append(
                    f"Duplicate dispatches for {sig}: {len(ids)} entries",
                )

        # Flag stale pending entries (older than 24h)
        import time

        now = time.time()
        for entry in ledger_status.entries:
            if entry.status == "pending" and (now - entry.timestamp) > 86400:
                report.idempotency_risks.append(
                    f"Stale pending dispatch: {entry.dispatch_id} "
                    f"({entry.event}) — pending > 24h",
                )

    return report
