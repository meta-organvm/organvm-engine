"""Resolve SOP-skill cascade: T4 (repo) > T3 (organ) > T2 (system)."""

from __future__ import annotations

from organvm_engine.sop.discover import SOPEntry

_SCOPE_PRIORITY = {"repo": 0, "organ": 1, "system": 2, "unknown": 3}

_PROMOTION_TO_PHASE = {
    "LOCAL": "foundation",
    "CANDIDATE": "hardening",
    "PUBLIC_PROCESS": "graduation",
    "GRADUATED": "sustaining",
    "ARCHIVED": "sustaining",
}


def promotion_to_phase(status: str) -> str:
    """Map a promotion status to a lifecycle phase.

    Returns the corresponding phase, or 'any' for unrecognized statuses.
    """
    return _PROMOTION_TO_PHASE.get(status, "any")


def resolve_sop(name: str, discovered: list[SOPEntry]) -> list[SOPEntry]:
    """Return SOPs matching name, ordered most-specific first (T4→T3→T2).

    If any entry declares ``overrides: <name>``, the overridden entry is removed.
    """
    matches = [e for e in discovered if e.sop_name == name]
    return _apply_overrides(matches)


def resolve_all(
    discovered: list[SOPEntry],
    repo: str | None = None,
    organ: str | None = None,
    phase: str | None = None,
) -> list[SOPEntry]:
    """Return all active SOPs for a given repo/organ context, with overrides applied.

    Scope filtering:
    - system SOPs always included
    - organ SOPs included if ``organ`` matches ``entry.org``
    - repo SOPs included if ``repo`` matches ``entry.repo``

    Phase filtering (when ``phase`` is set):
    - Only entries with ``entry.phase == phase`` or ``entry.phase == "any"`` are included
    """
    filtered: list[SOPEntry] = []
    for e in discovered:
        if (
            e.scope == "system"
            or (e.scope == "organ" and organ and e.org == organ)
            or (e.scope == "repo" and repo and e.repo == repo)
            or (e.scope == "unknown" and (
                (repo and e.repo == repo) or (organ and e.org == organ)
            ))
        ):
            filtered.append(e)

    if phase:
        filtered = [e for e in filtered if e.phase in (phase, "any")]

    return _apply_overrides(filtered)


def _apply_overrides(entries: list[SOPEntry]) -> list[SOPEntry]:
    """Remove entries that are overridden by more-specific entries.

    An entry with ``overrides=X`` removes entries named X that do NOT
    themselves declare an override — i.e., the overrider survives.
    """
    overriders: set[int] = set()
    overridden_names: set[str] = set()
    for e in entries:
        if e.overrides:
            overriders.add(id(e))
            overridden_names.add(e.overrides)

    result = [
        e for e in entries
        if id(e) in overriders or e.sop_name not in overridden_names
    ]
    return sorted(result, key=lambda e: _SCOPE_PRIORITY.get(e.scope, 99))
