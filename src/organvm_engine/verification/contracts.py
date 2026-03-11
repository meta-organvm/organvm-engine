"""Hoare Logic layer — pre/post conditions for dispatch event contracts.

Each cross-organ event type can register a DispatchContract that specifies:
- Required payload fields with expected types
- Custom validators per field
- Whether the trigger should be consumed (linear logic hint)

Contracts are data (dict-registered), not decorators — discoverable by CLI/MCP.
Uncovered event types get a warning, not a failure (incremental adoption).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DispatchContract:
    """Contract for a specific event type."""

    event_pattern: str
    required_payload_fields: dict[str, type] = field(default_factory=dict)
    required_payload_validators: dict[str, Callable[[Any], bool]] = field(
        default_factory=dict,
    )
    post_condition: str = ""
    consumes_trigger: bool = False

    def check_payload(self, payload: dict) -> list[str]:
        """Validate payload against this contract's requirements.

        Returns list of error strings (empty = pass).
        """
        errors: list[str] = []

        for field_name, expected_type in self.required_payload_fields.items():
            if field_name not in payload:
                errors.append(f"Missing required field: {field_name}")
                continue
            value = payload[field_name]
            if not isinstance(value, expected_type):
                errors.append(
                    f"Field '{field_name}' expected {expected_type.__name__}, "
                    f"got {type(value).__name__}",
                )

        for field_name, validator in self.required_payload_validators.items():
            value = payload.get(field_name)
            if value is not None:
                try:
                    if not validator(value):
                        errors.append(f"Validator failed for field '{field_name}'")
                except Exception as exc:
                    errors.append(f"Validator error for '{field_name}': {exc}")

        return errors


@dataclass
class ContractResult:
    """Result of contract verification."""

    event_type: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    contract_found: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "passed": self.passed,
            "errors": self.errors,
            "contract_found": self.contract_found,
        }


def _nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and len(v.strip()) > 0


def _positive_int(v: Any) -> bool:
    return isinstance(v, int) and v > 0


# Event contract registry — the initial set based on seed.yaml produces/consumes.
CONTRACTS: dict[str, DispatchContract] = {
    "theory.published": DispatchContract(
        event_pattern="theory.published",
        required_payload_fields={
            "artifact_id": str,
            "title": str,
            "source_repo": str,
        },
        required_payload_validators={
            "artifact_id": _nonempty_str,
            "title": _nonempty_str,
            "source_repo": _nonempty_str,
        },
        post_condition="Downstream organ acknowledges artifact receipt",
        consumes_trigger=True,
    ),
    "theory.updated": DispatchContract(
        event_pattern="theory.updated",
        required_payload_fields={
            "artifact_id": str,
            "source_repo": str,
            "change_summary": str,
        },
        required_payload_validators={
            "artifact_id": _nonempty_str,
            "source_repo": _nonempty_str,
            "change_summary": _nonempty_str,
        },
        post_condition="Downstream organ applies update",
        consumes_trigger=True,
    ),
    "product.release": DispatchContract(
        event_pattern="product.release",
        required_payload_fields={
            "version": str,
            "repo": str,
            "changelog_url": str,
        },
        required_payload_validators={
            "version": _nonempty_str,
            "repo": _nonempty_str,
            "changelog_url": _nonempty_str,
        },
        post_condition="Distribution channels notified",
        consumes_trigger=True,
    ),
    "product.milestone": DispatchContract(
        event_pattern="product.milestone",
        required_payload_fields={
            "milestone": str,
            "repo": str,
            "description": str,
        },
        required_payload_validators={
            "milestone": _nonempty_str,
            "repo": _nonempty_str,
        },
        post_condition="Community channels updated",
        consumes_trigger=False,
    ),
    "essay.published": DispatchContract(
        event_pattern="essay.published",
        required_payload_fields={
            "title": str,
            "slug": str,
            "word_count": int,
            "category": str,
        },
        required_payload_validators={
            "title": _nonempty_str,
            "slug": _nonempty_str,
            "word_count": _positive_int,
            "category": _nonempty_str,
        },
        post_condition="Essay indexed and distribution triggered",
        consumes_trigger=True,
    ),
    "governance.updated": DispatchContract(
        event_pattern="governance.updated",
        required_payload_fields={
            "rule_id": str,
            "change_type": str,
        },
        required_payload_validators={
            "rule_id": _nonempty_str,
            "change_type": _nonempty_str,
        },
        post_condition="Governance rules reloaded across system",
        consumes_trigger=False,
    ),
    "community.event_created": DispatchContract(
        event_pattern="community.event_created",
        required_payload_fields={
            "event_type": str,
            "title": str,
            "date": str,
        },
        required_payload_validators={
            "event_type": _nonempty_str,
            "title": _nonempty_str,
            "date": _nonempty_str,
        },
        post_condition="Community event scheduled and announced",
        consumes_trigger=False,
    ),
    "distribution.dispatched": DispatchContract(
        event_pattern="distribution.dispatched",
        required_payload_fields={
            "channel_id": str,
            "platform": str,
            "payload_hash": str,
        },
        required_payload_validators={
            "channel_id": _nonempty_str,
            "platform": _nonempty_str,
            "payload_hash": _nonempty_str,
        },
        post_condition="Content delivered to platform",
        consumes_trigger=True,
    ),
    "styx.stake_created": DispatchContract(
        event_pattern="styx.stake_created",
        required_payload_fields={
            "commitment": str,
            "amount": int,
            "stake_id": str,
        },
        required_payload_validators={
            "commitment": _nonempty_str,
            "amount": _positive_int,
            "stake_id": _nonempty_str,
        },
        post_condition="Stake recorded in Behavioral Blockchain (ORGAN-III)",
        consumes_trigger=True,
    ),
    "styx.audit_completed": DispatchContract(
        event_pattern="styx.audit_completed",
        required_payload_fields={
            "stake_id": str,
            "outcome": str,
            "auditor": str,
            "proof_hash": str,
        },
        required_payload_validators={
            "stake_id": _nonempty_str,
            "outcome": lambda v: v in ["PASS", "FAIL"],
            "auditor": _nonempty_str,
            "proof_hash": _nonempty_str,
        },
        post_condition="Resource reward/burn executed (ORGAN-III)",
        consumes_trigger=True,
    ),
}


def verify_contract(event_type: str, payload: dict) -> ContractResult:
    """Verify a dispatch payload against its registered contract.

    Args:
        event_type: The event type string (e.g., "theory.published").
        payload: The payload dict (the `payload` field of the dispatch envelope).

    Returns:
        ContractResult with pass/fail and any errors.
    """
    contract = CONTRACTS.get(event_type)
    if contract is None:
        return ContractResult(
            event_type=event_type,
            passed=True,
            errors=[],
            contract_found=False,
        )

    errors = contract.check_payload(payload)
    return ContractResult(
        event_type=event_type,
        passed=len(errors) == 0,
        errors=errors,
        contract_found=True,
    )
