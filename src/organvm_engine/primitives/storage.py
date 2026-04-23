"""Shared storage path contract for stateful institutional primitives."""

from __future__ import annotations

from pathlib import Path

_INSTITUTIONAL_ROOT = Path(".organvm") / "institutional"
_STATEFUL_PRIMITIVE_DIRS: dict[str, str] = {
    "guardian": "guardian",
    "ledger": "ledger",
    "archivist": "archivist",
    "mandator": "mandator",
}


def institutional_store_root(*, home_dir: Path | str | None = None) -> Path:
    """Return the shared root for persistent institutional state."""
    home = Path(home_dir).expanduser() if home_dir is not None else Path.home()
    return home / _INSTITUTIONAL_ROOT


def primitive_store_dir(
    primitive_name: str,
    *,
    home_dir: Path | str | None = None,
) -> Path:
    """Return the storage directory for a stateful primitive.

    Assessor and counselor are intentionally excluded because they are
    stateless primitives.
    """
    segment = _STATEFUL_PRIMITIVE_DIRS.get(primitive_name)
    if segment is None:
        raise ValueError(f"Primitive '{primitive_name}' is stateless or unknown")
    return institutional_store_root(home_dir=home_dir) / segment


def stateful_primitive_names() -> tuple[str, ...]:
    """Return the primitive names that persist institutional state."""
    return tuple(_STATEFUL_PRIMITIVE_DIRS)
