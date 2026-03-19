"""Ontology module — stratified entity taxonomy per SPEC-001.

Provides a compatibility layer over ontologia's EntityType enum, adding
BFO-aligned ontological categories (Continuant/Occurrent/Abstract) and
subcategories without modifying the ontologia repo directly.
"""

from organvm_engine.ontology.taxonomy import (
    CATEGORY_MAP,
    EntityCategory,
    EntitySubCategory,
    classify,
    is_dependent,
    is_independent,
    is_occurrent,
)

__all__ = [
    "CATEGORY_MAP",
    "EntityCategory",
    "EntitySubCategory",
    "classify",
    "is_dependent",
    "is_independent",
    "is_occurrent",
]
