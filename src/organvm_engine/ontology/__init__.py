"""Ontology module — stratified entity taxonomy per SPEC-001, unified relations per SPEC-002.

Provides a compatibility layer over ontologia's EntityType enum, adding
BFO-aligned ontological categories (Continuant/Occurrent/Abstract) and
subcategories without modifying the ontologia repo directly.

Also provides the unified relation layer (SPEC-002, PRIM-003) that abstracts
over ontologia lineage, seed graph, and dependency graph stores.
"""

from organvm_engine.ontology.relations import (
    Relation,
    RelationType,
    UnifiedRelationStore,
)
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
    "Relation",
    "RelationType",
    "UnifiedRelationStore",
    "classify",
    "is_dependent",
    "is_independent",
    "is_occurrent",
]
