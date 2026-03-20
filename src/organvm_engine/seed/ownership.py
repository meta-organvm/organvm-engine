"""Parse ownership and review gate declarations from seed.yaml v1.1.

When no ownership section is present (v1.0 seeds), all functions return
permissive defaults — preserving solo-operator behavior.
"""

from __future__ import annotations

# Full access set granted to lead or when no ownership is declared
_FULL_ACCESS = frozenset({"read", "edit", "commit", "pr", "promote", "audit", "release"})


def has_ownership(seed: dict) -> bool:
    """Check if the seed declares an ownership section."""
    return isinstance(seed.get("ownership"), dict) and bool(seed["ownership"])


def get_lead(seed: dict) -> str | None:
    """Return the lead handle, or None if no ownership declared."""
    ownership = seed.get("ownership")
    if not isinstance(ownership, dict):
        return None
    return ownership.get("lead") or None


def get_collaborators(seed: dict) -> list[dict]:
    """Return the list of collaborator declarations."""
    ownership = seed.get("ownership")
    if not isinstance(ownership, dict):
        return []
    collabs = ownership.get("collaborators")
    if not isinstance(collabs, list):
        return []
    return [c for c in collabs if isinstance(c, dict) and "handle" in c]


def get_ai_agents(seed: dict) -> list[dict]:
    """Return the list of AI agent access declarations."""
    ownership = seed.get("ownership")
    if not isinstance(ownership, dict):
        return []
    agents = ownership.get("ai_agents")
    if not isinstance(agents, list):
        return []
    return [a for a in agents if isinstance(a, dict) and "type" in a]


def get_review_gates(seed: dict) -> dict[str, list[str]]:
    """Return review gate requirements keyed by transition name.

    Example return: {"promote_to_candidate": ["ci_pass", "lead_approval"]}

    Note: In v1, gates are advisory-only — the authorization module reports
    required gates but does not verify whether they have been satisfied.
    Gate satisfaction checking is a future concern.
    """
    review = seed.get("review")
    if not isinstance(review, dict):
        return {}
    gates: dict[str, list[str]] = {}
    for gate_name, gate_def in review.items():
        if isinstance(gate_def, dict) and isinstance(gate_def.get("requires"), list):
            gates[gate_name] = gate_def["requires"]
    return gates


def actor_access(seed: dict, actor_handle: str) -> set[str]:
    """Determine the access set for a given actor handle.

    Rules:
    1. If no ownership section exists -> full access (solo-operator compat)
    2. If actor is the lead -> full access
    3. If actor is a declared collaborator -> their declared access set
    4. Otherwise -> empty set (no access)
    """
    if not has_ownership(seed):
        return set(_FULL_ACCESS)

    lead = get_lead(seed)
    if lead and actor_handle == lead:
        return set(_FULL_ACCESS)

    for collab in get_collaborators(seed):
        if collab.get("handle") == actor_handle:
            return set(collab.get("access", []))

    return set()
