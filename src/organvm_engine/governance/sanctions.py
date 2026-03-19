"""Or-else sanctions — graduated obligation chains for governance violations.

Implements: SPEC-005, VIOL-001 through VIOL-007
Resolves: engine #29 (Or-else sanctions)

When a governance violation is detected, the sanction engine creates an
ObligationChain — an ordered sequence of remediation steps. The entity
must satisfy the current obligation; if it fails, the chain advances to
the next (more severe) step. When all obligations are exhausted without
resolution, the chain reaches terminal state and the final obligation
(typically demotion or archival) is enforced.

Predefined chains cover common violation patterns:
  - MISSING_CI:   add workflow -> request extension -> demote to LOCAL
  - BACK_EDGE:    remove edge -> redesign architecture -> archive dependent
  - STALE_REPO:   update repo -> declare maintenance -> archive
  - MISSING_SEED: create seed -> register as liminal -> remove from workspace
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ── Predefined obligation chains ────────────────────────────────────

MISSING_CI: list[str] = [
    "add_ci_workflow",
    "request_extension",
    "demote_to_LOCAL",
]

BACK_EDGE: list[str] = [
    "remove_edge",
    "redesign_architecture",
    "archive_dependent",
]

STALE_REPO: list[str] = [
    "update_repo",
    "declare_maintenance",
    "archive",
]

MISSING_SEED: list[str] = [
    "create_seed",
    "register_liminal",
    "remove_from_workspace",
]

# Map rule_id patterns to their default obligation chains
_DEFAULT_CHAINS: dict[str, list[str]] = {
    "MISSING_CI": MISSING_CI,
    "BACK_EDGE": BACK_EDGE,
    "STALE_REPO": STALE_REPO,
    "MISSING_SEED": MISSING_SEED,
}


@dataclass
class ObligationChain:
    """An ordered sequence of remediation obligations for a violation.

    The entity must satisfy obligations[current_index]. If it cannot,
    advance_chain() moves to the next obligation. When current_index
    reaches len(obligations), the chain is terminal.
    """

    obligations: list[str]
    current_index: int
    entity_uid: str
    rule_id: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    violation_details: dict[str, Any] = field(default_factory=dict)

    @property
    def current_obligation(self) -> str | None:
        """The obligation that must currently be satisfied, or None if terminal."""
        if self.current_index < len(self.obligations):
            return self.obligations[self.current_index]
        return None

    @property
    def remaining(self) -> int:
        """Number of obligations remaining (including current)."""
        return max(0, len(self.obligations) - self.current_index)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "obligations": self.obligations,
            "current_index": self.current_index,
            "entity_uid": self.entity_uid,
            "rule_id": self.rule_id,
            "created_at": self.created_at.isoformat(),
            "violation_details": self.violation_details,
            "current_obligation": self.current_obligation,
            "is_terminal": self.current_index >= len(self.obligations),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObligationChain:
        """Deserialize from a dict."""
        created = data.get("created_at", "")
        if isinstance(created, str) and created:
            dt = datetime.fromisoformat(created)
        else:
            dt = datetime.now(timezone.utc)
        return cls(
            obligations=data["obligations"],
            current_index=data["current_index"],
            entity_uid=data["entity_uid"],
            rule_id=data["rule_id"],
            created_at=dt,
            violation_details=data.get("violation_details", {}),
        )


class SanctionEngine:
    """Evaluates violations and manages graduated obligation chains."""

    def __init__(
        self,
        custom_chains: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize with optional custom obligation chains.

        Args:
            custom_chains: Additional rule_id -> obligation list mappings.
                           These are merged with (and override) the defaults.
        """
        self._chains: dict[str, list[str]] = dict(_DEFAULT_CHAINS)
        if custom_chains:
            self._chains.update(custom_chains)

    @property
    def known_rules(self) -> list[str]:
        """List all rule IDs with registered obligation chains."""
        return sorted(self._chains.keys())

    def evaluate_violation(
        self,
        rule_id: str,
        entity_uid: str,
        violation_details: dict[str, Any] | None = None,
    ) -> ObligationChain:
        """Create an obligation chain for a detected violation.

        Args:
            rule_id: The governance rule that was violated (e.g. "MISSING_CI").
            entity_uid: UID of the entity in violation.
            violation_details: Optional dict with context about the violation.

        Returns:
            A new ObligationChain starting at index 0.

        Raises:
            KeyError: If rule_id has no registered obligation chain.
        """
        if rule_id not in self._chains:
            raise KeyError(
                f"No obligation chain registered for rule '{rule_id}'. "
                f"Known rules: {self.known_rules}",
            )
        return ObligationChain(
            obligations=list(self._chains[rule_id]),  # defensive copy
            current_index=0,
            entity_uid=entity_uid,
            rule_id=rule_id,
            violation_details=violation_details or {},
        )

    def advance_chain(self, chain: ObligationChain) -> str | None:
        """Advance to the next obligation when the current one is not met.

        Args:
            chain: The obligation chain to advance.

        Returns:
            The new current obligation, or None if the chain is now terminal.

        Raises:
            ValueError: If the chain is already terminal.
        """
        if self.is_terminal(chain):
            raise ValueError(
                f"Chain for {chain.rule_id} on {chain.entity_uid} is already "
                "terminal — all obligations exhausted.",
            )
        chain.current_index += 1
        return chain.current_obligation

    def is_terminal(self, chain: ObligationChain) -> bool:
        """Return True if all obligations in the chain have been exhausted."""
        return chain.current_index >= len(chain.obligations)
