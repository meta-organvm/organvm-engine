"""IRF query — filter and look up IRFItem objects.

All filter parameters are optional. Multiple filters combine with AND logic.
String matching is case-insensitive.
"""

from __future__ import annotations

from organvm_engine.irf.parser import IRFItem


def query_irf(
    items: list[IRFItem],
    *,
    item_id: str | None = None,
    priority: str | None = None,
    domain: str | None = None,
    status: str | None = None,
    owner: str | None = None,
) -> list[IRFItem]:
    """Filter a list of IRFItem objects by one or more criteria.

    All criteria are optional; any combination is valid.
    Matching is case-insensitive for all string fields.

    Args:
        items:    The list of IRFItem objects to search.
        item_id:  Exact match on IRFItem.id (e.g. "IRF-SYS-001").
        priority: Exact match on IRFItem.priority (e.g. "P0", "P1").
        domain:   Exact match on IRFItem.domain (e.g. "SYS", "OBJ").
        status:   Exact match on IRFItem.status ("open", "completed", "blocked", "archived").
        owner:    Case-insensitive substring match on IRFItem.owner.

    Returns:
        A filtered list of IRFItem objects satisfying all provided criteria.
    """
    result = items

    if item_id is not None:
        needle = item_id.upper()
        result = [i for i in result if i.id.upper() == needle]

    if priority is not None:
        needle = priority.upper()
        result = [i for i in result if i.priority.upper() == needle]

    if domain is not None:
        needle = domain.upper()
        result = [i for i in result if i.domain.upper() == needle]

    if status is not None:
        needle = status.lower()
        result = [i for i in result if i.status.lower() == needle]

    if owner is not None:
        needle = owner.lower()
        result = [i for i in result if needle in i.owner.lower()]

    return result
