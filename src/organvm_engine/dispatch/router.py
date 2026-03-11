"""Route events to target organs based on seed.yaml subscriptions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from organvm_engine.seed.reader import get_subscriptions


@dataclass
class DispatchReceipt:
    """Receipt from routing an event — includes matches and verification."""

    event_type: str
    source_organ: str
    matches: list[dict] = field(default_factory=list)
    contract_verified: bool = False
    contract_found: bool = False
    contract_errors: list[str] = field(default_factory=list)

    @property
    def match_count(self) -> int:
        return len(self.matches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "source_organ": self.source_organ,
            "match_count": self.match_count,
            "matches": self.matches,
            "contract_verified": self.contract_verified,
            "contract_found": self.contract_found,
            "contract_errors": self.contract_errors,
        }


def route_event(
    event_type: str,
    source_organ: str,
    all_seeds: dict[str, dict],
) -> list[dict]:
    """Find all repos subscribed to a given event type.

    Args:
        event_type: Event type to route (e.g., "theory.published").
        source_organ: Organ where the event originated.
        all_seeds: Dict of identity -> seed data for all repos.

    Returns:
        List of {repo, action} dicts for matching subscriptions.
    """
    matches = []
    for identity, seed in all_seeds.items():
        for sub in get_subscriptions(seed):
            if sub.get("event") == event_type and sub.get("source") == source_organ:
                matches.append(
                    {
                        "repo": identity,
                        "action": sub.get("action", ""),
                        "event": event_type,
                    },
                )
    return matches


def route_event_verified(
    event_type: str,
    source_organ: str,
    all_seeds: dict[str, dict],
    payload_data: dict | None = None,
) -> DispatchReceipt:
    """Route an event with contract verification and receipt.

    Like route_event but returns a DispatchReceipt that includes
    contract verification status alongside the matches.

    Args:
        event_type: Event type to route.
        source_organ: Source organ identifier.
        all_seeds: Dict of identity -> seed data.
        payload_data: Optional payload dict to verify against contract.

    Returns:
        DispatchReceipt with matches and verification status.
    """
    matches = route_event(event_type, source_organ, all_seeds)

    receipt = DispatchReceipt(
        event_type=event_type,
        source_organ=source_organ,
        matches=matches,
    )

    if payload_data is not None:
        from organvm_engine.verification.contracts import verify_contract

        result = verify_contract(event_type, payload_data)
        receipt.contract_verified = result.passed
        receipt.contract_found = result.contract_found
        receipt.contract_errors = result.errors

    return receipt
