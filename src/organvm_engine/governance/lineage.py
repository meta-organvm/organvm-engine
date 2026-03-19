"""Lineage wiring on archive/dissolve transitions.

Implements: SPEC-000 AX-000-007, SPEC-003 INV-000-003
Resolves: engine #18 (lineage wiring)

When an entity transitions to ARCHIVED or is dissolved, a lineage record
is created capturing the reason, successor, and dissolution target. An
ENTITY_ARCHIVED event is emitted to the EventSpine.

The lineage record is returned as a dict — it does not write to the
ontologia store directly (that is a separate repo's responsibility).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def create_archival_lineage(
    entity_uid: str,
    reason: str,
    successor_uid: str | None = None,
    dissolution_target: str | None = None,
) -> dict[str, Any]:
    """Create a lineage record for an archived or dissolved entity.

    Args:
        entity_uid: The UID of the entity being archived/dissolved.
        reason: Human-readable explanation for the archival/dissolution.
        successor_uid: Optional UID of the entity that succeeds this one.
            Used when one entity replaces another (merge, rename, etc.).
        dissolution_target: Optional identifier of the target that absorbs
            the dissolved entity's responsibilities (e.g., a materia-collider
            entry, a merged repo name).

    Returns:
        A LineageRecord-compatible dict with all provenance fields.
    """
    now = datetime.now(timezone.utc).isoformat()
    lineage_id = f"lin_{uuid.uuid4().hex[:12]}"

    record: dict[str, Any] = {
        "lineage_id": lineage_id,
        "entity_uid": entity_uid,
        "action": _classify_action(reason, dissolution_target),
        "reason": reason,
        "timestamp": now,
    }

    if successor_uid is not None:
        record["successor_uid"] = successor_uid

    if dissolution_target is not None:
        record["dissolution_target"] = dissolution_target

    return record


def wire_lineage_on_transition(
    entity_uid: str,
    from_state: str,
    to_state: str,
    reason: str | None = None,
    *,
    successor_uid: str | None = None,
    dissolution_target: str | None = None,
    actor: str = "cli",
    spine_path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Create a lineage record when a transition warrants one.

    A lineage record is created when:
      - to_state is "ARCHIVED"
      - reason contains "dissolve" or "dissolved" (case-insensitive)

    If neither condition is met, returns None (no lineage needed).

    Args:
        entity_uid: The entity UID undergoing the transition.
        from_state: The state being left.
        to_state: The state being entered.
        reason: Optional explanation for the transition.
        successor_uid: Optional successor entity UID.
        dissolution_target: Optional dissolution target identifier.
        actor: Who/what triggered the transition.
        spine_path: Optional path for the EventSpine JSONL file.

    Returns:
        LineageRecord dict if lineage was created, None otherwise.
    """
    reason_text = reason or ""

    needs_lineage = (
        to_state == "ARCHIVED"
        or "dissolve" in reason_text.lower()
    )

    if not needs_lineage:
        return None

    # Determine the effective reason
    effective_reason = reason_text if reason_text else f"Transitioned from {from_state} to {to_state}"

    record = create_archival_lineage(
        entity_uid=entity_uid,
        reason=effective_reason,
        successor_uid=successor_uid,
        dissolution_target=dissolution_target,
    )

    # Add transition metadata
    record["from_state"] = from_state
    record["to_state"] = to_state
    record["actor"] = actor

    # Emit ENTITY_ARCHIVED event
    _emit_archived_event(
        entity_uid=entity_uid,
        from_state=from_state,
        to_state=to_state,
        reason=effective_reason,
        lineage_id=record["lineage_id"],
        actor=actor,
        spine_path=spine_path,
    )

    return record


def _classify_action(reason: str, dissolution_target: str | None) -> str:
    """Classify the lineage action from the reason and dissolution target.

    Returns one of: archive, dissolve, merge, deprecate.
    """
    reason_lower = reason.lower()

    if dissolution_target is not None or "dissolve" in reason_lower:
        return "dissolve"
    if "merge" in reason_lower:
        return "merge"
    if "deprecat" in reason_lower:
        return "deprecate"
    return "archive"


def _emit_archived_event(
    entity_uid: str,
    from_state: str,
    to_state: str,
    reason: str,
    lineage_id: str,
    actor: str = "cli",
    spine_path: Path | str | None = None,
) -> None:
    """Emit an ENTITY_ARCHIVED event to the EventSpine. Fail-safe: never raises."""
    try:
        from organvm_engine.events.spine import EventSpine, EventType

        kwargs: dict[str, Any] = {}
        if spine_path is not None:
            kwargs["path"] = spine_path

        spine = EventSpine(**kwargs)
        spine.emit(
            event_type=EventType.ENTITY_ARCHIVED,
            entity_uid=entity_uid,
            payload={
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
                "lineage_id": lineage_id,
            },
            source_spec="SPEC-000",
            actor=actor,
        )
    except Exception:
        logger.debug("EventSpine emission failed during lineage wiring (non-fatal)", exc_info=True)
