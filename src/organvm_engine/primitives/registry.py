"""Flat registry for institutional primitives (SPEC-025 §7).

All 32 primitives (13 production + 19 institutional) inhabit a single
shared pool — no hierarchy.  This registry provides lookup by ID, by
name, and enumeration.
"""

from __future__ import annotations

from organvm_engine.primitives.base import InstitutionalPrimitive


class PrimitiveRegistry:
    """Register and retrieve primitive instances."""

    def __init__(self) -> None:
        self._by_id: dict[str, InstitutionalPrimitive] = {}
        self._by_name: dict[str, InstitutionalPrimitive] = {}

    def register(self, primitive: InstitutionalPrimitive) -> None:
        """Add a primitive to the pool."""
        self._by_id[primitive.PRIMITIVE_ID] = primitive
        self._by_name[primitive.PRIMITIVE_NAME] = primitive

    def get_by_id(self, primitive_id: str) -> InstitutionalPrimitive | None:
        return self._by_id.get(primitive_id)

    def get_by_name(self, name: str) -> InstitutionalPrimitive | None:
        return self._by_name.get(name)

    def list_all(self) -> list[InstitutionalPrimitive]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, key: str) -> bool:
        return key in self._by_id or key in self._by_name
