"""Role-based transition authorization using seed.yaml ownership declarations.

Advisory mode (default): returns authorization result without blocking.
Enforcing mode: same result, but callers treat it as a hard gate.

In v1, gate satisfaction is not verified — the authorization module checks
whether the actor has "promote" access and reports which gates are required,
but does not confirm those gates have been met. This is intentional: it
allows incremental adoption (advisory first, enforcing later) without
requiring a full gate-checking pipeline from day one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from organvm_engine.seed.ownership import actor_access, get_review_gates, has_ownership

logger = logging.getLogger(__name__)

# Known promotion target states.
_KNOWN_TARGETS = frozenset({
    "INCUBATOR", "LOCAL", "CANDIDATE", "PUBLIC_PROCESS", "GRADUATED", "ARCHIVED",
})

# Map target states to review gate keys in seed.yaml.
# States not in this map (LOCAL, ARCHIVED, INCUBATOR) have no review gates.
_STATE_TO_GATE = {
    "CANDIDATE": "promote_to_candidate",
    "PUBLIC_PROCESS": "promote_to_public_process",
    "GRADUATED": "promote_to_graduated",
}


@dataclass
class AuthorizationResult:
    """Result of a transition authorization check."""

    authorized: bool
    actor: str
    target_state: str
    reason: str
    gates_required: list[str] = field(default_factory=list)
    advisory: bool = True  # True = advisory mode, False = enforcing


def authorize_transition(
    actor: str,
    target_state: str,
    seed: dict,
    *,
    enforce: bool = False,
) -> AuthorizationResult:
    """Check if an actor is authorized to transition a repo to target_state.

    Args:
        actor: Handle of the person/agent requesting the transition.
        target_state: Desired promotion_status.
        seed: Parsed seed.yaml dict for the repo.
        enforce: If True, result.advisory=False (enforcing mode).

    Returns:
        AuthorizationResult with authorized flag and reason.
    """
    advisory = not enforce

    # Validate target_state is known
    if target_state not in _KNOWN_TARGETS:
        return AuthorizationResult(
            authorized=False,
            actor=actor,
            target_state=target_state,
            reason=f"Unknown target state '{target_state}'",
            advisory=advisory,
        )

    # No ownership section -> solo-operator mode, everyone is authorized
    if not has_ownership(seed):
        return AuthorizationResult(
            authorized=True,
            actor=actor,
            target_state=target_state,
            reason="No ownership declared — solo-operator mode, full access",
            advisory=advisory,
        )

    # Check actor has promote access
    access = actor_access(seed, actor)
    if "promote" not in access:
        msg = f"Actor '{actor}' lacks 'promote' access (has: {sorted(access) or 'none'})"
        logger.info("Authorization denied: %s", msg)
        return AuthorizationResult(
            authorized=False,
            actor=actor,
            target_state=target_state,
            reason=msg,
            advisory=advisory,
        )

    # Look up review gates for this transition
    gates = get_review_gates(seed)
    gate_key = _STATE_TO_GATE.get(target_state, "")
    required = gates.get(gate_key, [])

    return AuthorizationResult(
        authorized=True,
        actor=actor,
        target_state=target_state,
        reason=f"Actor '{actor}' authorized for {target_state}",
        gates_required=required,
        advisory=advisory,
    )
