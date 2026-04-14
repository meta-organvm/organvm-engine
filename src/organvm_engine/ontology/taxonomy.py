"""Stratified entity taxonomy — BFO-aligned categories for ontologia EntityTypes.

Implements: SPEC-001, ONT-001 through ONT-028
Resolves: engine #26 (stratified EntityType)

Maps every EntityType value from ontologia's identity module into a two-level
ontological classification derived from BFO (Basic Formal Ontology):

  - CONTINUANT: entities that persist through time (organs, repos, modules)
  - OCCURRENT: entities that unfold in time (sessions, events)
  - ABSTRACT: entities that are neither spatial nor temporal (governance objects,
    capabilities, types)

Within each top-level category, subcategories distinguish independent
continuants (exist on their own) from dependent ones (inhere in something
else), processes from events, and so on.

This module does NOT import from ontologia — it operates on string values
matching EntityType.value, so the engine can classify entities without
requiring ontologia as a runtime dependency.
"""

from __future__ import annotations

from enum import Enum


class EntityCategory(str, Enum):
    """Top-level BFO-aligned ontological category."""

    CONTINUANT = "CONTINUANT"
    OCCURRENT = "OCCURRENT"
    ABSTRACT = "ABSTRACT"


class EntitySubCategory(str, Enum):
    """Second-level ontological subcategory."""

    # Continuant subcategories
    INDEPENDENT_CONTINUANT = "INDEPENDENT_CONTINUANT"
    SPECIFICALLY_DEPENDENT_CONTINUANT = "SPECIFICALLY_DEPENDENT_CONTINUANT"
    GENERICALLY_DEPENDENT_CONTINUANT = "GENERICALLY_DEPENDENT_CONTINUANT"

    # Occurrent subcategories
    PROCESS = "PROCESS"
    EVENT = "EVENT"
    TEMPORAL_REGION = "TEMPORAL_REGION"

    # Abstract subcategories
    GOVERNANCE_OBJECT = "GOVERNANCE_OBJECT"
    CAPABILITY = "CAPABILITY"
    TYPE = "TYPE"


# ── Category map ────────────────────────────────────────────────────
# Keys are EntityType.value strings from ontologia.entity.identity.
# Values are (EntityCategory, EntitySubCategory) tuples.

CATEGORY_MAP: dict[str, tuple[EntityCategory, EntitySubCategory]] = {
    # Independent continuants — SPEC-000 primitive: Entity
    # ONT-004, ONT-005, ONT-006: exist on their own, persist through time
    "organ": (EntityCategory.CONTINUANT, EntitySubCategory.INDEPENDENT_CONTINUANT),
    "repo": (EntityCategory.CONTINUANT, EntitySubCategory.INDEPENDENT_CONTINUANT),
    "module": (EntityCategory.CONTINUANT, EntitySubCategory.INDEPENDENT_CONTINUANT),

    # Specifically dependent continuants — SPEC-000 primitive: Value
    # ONT-008, ONT-009: data/qualities inhering in a bearer entity
    "variable": (
        EntityCategory.CONTINUANT,
        EntitySubCategory.SPECIFICALLY_DEPENDENT_CONTINUANT,
    ),
    "metric": (
        EntityCategory.CONTINUANT,
        EntitySubCategory.SPECIFICALLY_DEPENDENT_CONTINUANT,
    ),

    # Generically dependent continuants — SPEC-000 primitive: Entity
    # ONT-011: information content entities that can migrate between bearers
    "document": (
        EntityCategory.CONTINUANT,
        EntitySubCategory.GENERICALLY_DEPENDENT_CONTINUANT,
    ),

    # Occurrent: processes — SPEC-000 primitive: Event
    # ONT-015: bounded agent work episodes unfolding over a temporal interval
    "session": (EntityCategory.OCCURRENT, EntitySubCategory.PROCESS),
}

# Subcategories that are dependent (specifically or generically)
_DEPENDENT_SUBCATEGORIES: frozenset[EntitySubCategory] = frozenset({
    EntitySubCategory.SPECIFICALLY_DEPENDENT_CONTINUANT,
    EntitySubCategory.GENERICALLY_DEPENDENT_CONTINUANT,
})


def classify(entity_type: str) -> tuple[EntityCategory, EntitySubCategory]:
    """Classify an entity type into its ontological category path.

    Args:
        entity_type: The EntityType.value string (e.g. "organ", "session").

    Returns:
        Tuple of (EntityCategory, EntitySubCategory).

    Raises:
        KeyError: If entity_type is not in CATEGORY_MAP.
    """
    try:
        return CATEGORY_MAP[entity_type]
    except KeyError:
        raise KeyError(
            f"Unknown entity type '{entity_type}'. "
            f"Known types: {sorted(CATEGORY_MAP.keys())}",
        ) from None


def is_independent(entity_type: str) -> bool:
    """Return True if the entity type is an independent continuant.

    Independent continuants exist on their own — they are not qualities,
    dispositions, or roles that inhere in something else.
    """
    cat, sub = classify(entity_type)
    return (
        cat == EntityCategory.CONTINUANT
        and sub == EntitySubCategory.INDEPENDENT_CONTINUANT
    )


def is_dependent(entity_type: str) -> bool:
    """Return True if the entity type is a dependent continuant.

    Dependent continuants inhere in or depend on a bearer entity.
    This includes both specifically dependent (variables, metrics) and
    generically dependent (documents) continuants.
    """
    cat, sub = classify(entity_type)
    return cat == EntityCategory.CONTINUANT and sub in _DEPENDENT_SUBCATEGORIES


def is_occurrent(entity_type: str) -> bool:
    """Return True if the entity type is an occurrent (process or event)."""
    cat, _sub = classify(entity_type)
    return cat == EntityCategory.OCCURRENT
