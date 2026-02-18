"""Dispatch payload creation and validation."""

import uuid
from datetime import datetime, timezone


def create_payload(
    event: str,
    source_organ: str,
    target_organ: str,
    payload_data: dict,
    priority: str = "normal",
    source_org: str | None = None,
    source_repo: str | None = None,
    target_org: str | None = None,
    target_repo: str | None = None,
) -> dict:
    """Create a dispatch payload.

    Args:
        event: Event type (e.g., "theory.published").
        source_organ: Source organ identifier.
        target_organ: Target organ identifier.
        payload_data: Event-specific data.
        priority: Event priority.
        source_org: Source GitHub org.
        source_repo: Source repo name.
        target_org: Target GitHub org.
        target_repo: Target repo name.

    Returns:
        Fully formed dispatch payload dict.
    """
    source = {"organ": source_organ}
    if source_org:
        source["org"] = source_org
    if source_repo:
        source["repo"] = source_repo

    target = {"organ": target_organ}
    if target_org:
        target["org"] = target_org
    if target_repo:
        target["repo"] = target_repo

    return {
        "event": event,
        "source": source,
        "target": target,
        "payload": payload_data,
        "metadata": {
            "dispatch_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "priority": priority,
            "ttl_seconds": 86400,
        },
    }


def validate_payload(payload: dict) -> tuple[bool, list[str]]:
    """Validate a dispatch payload structure.

    Args:
        payload: Payload dict to validate.

    Returns:
        (valid, errors) tuple.
    """
    errors = []

    for field in ("event", "source", "target", "payload"):
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    event = payload.get("event", "")
    if event and "." not in event:
        errors.append(f"Event '{event}' must contain a dot separator (e.g., 'theory.published')")

    for endpoint_name in ("source", "target"):
        endpoint = payload.get(endpoint_name, {})
        if isinstance(endpoint, dict) and "organ" not in endpoint:
            errors.append(f"{endpoint_name}: missing 'organ' field")

    meta = payload.get("metadata", {})
    if meta:
        priority = meta.get("priority")
        if priority and priority not in ("low", "normal", "high", "critical"):
            errors.append(f"Invalid priority: {priority}")

    return len(errors) == 0, errors
