"""Promotion state machine: LOCAL -> CANDIDATE -> PUBLIC_PROCESS -> GRADUATED -> ARCHIVED."""

# Canonical transitions from governance-rules.json
TRANSITIONS = {
    "LOCAL": ["CANDIDATE", "ARCHIVED"],
    "CANDIDATE": ["PUBLIC_PROCESS", "LOCAL", "ARCHIVED"],
    "PUBLIC_PROCESS": ["GRADUATED", "CANDIDATE", "ARCHIVED"],
    "GRADUATED": ["ARCHIVED"],
    "ARCHIVED": [],
}


def get_valid_transitions(current_state: str) -> list[str]:
    """Get valid target states for a given current state.

    Args:
        current_state: Current promotion_status.

    Returns:
        List of valid target states.
    """
    return TRANSITIONS.get(current_state, [])


def check_transition(current_state: str, target_state: str) -> tuple[bool, str]:
    """Check if a state transition is valid.

    Args:
        current_state: Current promotion_status.
        target_state: Desired promotion_status.

    Returns:
        (valid, message) tuple.
    """
    valid = TRANSITIONS.get(current_state)
    if valid is None:
        return False, f"Unknown state '{current_state}'"

    if target_state in valid:
        return True, f"{current_state} -> {target_state}"

    return False, (
        f"Cannot transition {current_state} -> {target_state}. "
        f"Valid targets: {', '.join(valid) if valid else 'none (terminal state)'}"
    )
