"""State snapshot bridge — creates and compares entity snapshots for drift detection.

Bridges ontologia's StateSnapshot with real registry + soak data:
- Creates a snapshot per entity with properties from the registry
- Compares with previous snapshots to detect drift
- Stores snapshots in ~/.organvm/ontologia/snapshots/ (30-day window)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from ontologia.state.snapshot import (
        StateSnapshot,
        compare_snapshots,
        create_snapshot,
        has_drift,
    )

    HAS_ONTOLOGIA = True
except ImportError:
    HAS_ONTOLOGIA = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_DEFAULT_SNAPSHOTS_DIR = Path.home() / ".organvm" / "ontologia" / "snapshots"


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------

def create_entity_snapshot(
    entity_id: str,
    repo_data: dict[str, Any],
    metric_values: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Create a snapshot for a single entity from registry data.

    Returns a dict (snapshot_to_dict) regardless of whether ontologia is installed.
    """
    properties = {
        "name": repo_data.get("name", ""),
        "promotion_status": repo_data.get("promotion_status", ""),
        "tier": repo_data.get("tier", ""),
        "public": repo_data.get("public", False),
        "ci_workflow": repo_data.get("ci_workflow", ""),
        "platinum_status": repo_data.get("platinum_status", False),
        "implementation_status": repo_data.get("implementation_status", ""),
        "last_validated": repo_data.get("last_validated", ""),
    }

    metrics = metric_values or {}

    if HAS_ONTOLOGIA:
        snap = create_snapshot(
            entity_id=entity_id,
            properties=properties,
            metric_values=metrics,
        )
        return snap.to_dict()

    # Fallback without ontologia
    return {
        "snapshot_id": f"snap_fallback_{entity_id[:16]}",
        "entity_id": entity_id,
        "timestamp": _now_iso(),
        "properties": properties,
        "metric_values": metrics,
    }


def create_system_snapshot(
    registry_path: Path | None = None,
    snapshots_dir: Path | None = None,
) -> dict[str, Any]:
    """Create snapshots for all entities and save to disk.

    Returns:
        {"date": str, "entity_count": int, "snapshot_path": str}
    """
    reg_path = registry_path
    if reg_path is None:
        try:
            from organvm_engine.paths import registry_path as _rp
            reg_path = _rp()
        except Exception:
            return {"error": "Cannot resolve registry path"}

    try:
        registry = json.loads(reg_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"error": f"Cannot read registry: {reg_path}"}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshots: dict[str, Any] = {
        "date": today,
        "created_at": _now_iso(),
        "entities": {},
    }

    for _organ_key, organ_data in registry.get("organs", {}).items():
        for repo in organ_data.get("repositories", []):
            name = repo.get("name", "")
            if not name:
                continue
            entity_id = name  # Use name as entity key; resolves to UID when store available
            snapshots["entities"][entity_id] = create_entity_snapshot(entity_id, repo)

    # Save to disk
    out_dir = snapshots_dir or _DEFAULT_SNAPSHOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"snapshot-{today}.json"
    out_path.write_text(json.dumps(snapshots, indent=2, default=str))

    # Prune old snapshots (keep 30 days)
    _prune_old_snapshots(out_dir, keep_days=30)

    return {
        "date": today,
        "entity_count": len(snapshots["entities"]),
        "snapshot_path": str(out_path),
    }


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def detect_drift(
    snapshots_dir: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Compare today's snapshot against the most recent previous one.

    Returns:
        {
            "has_drift": bool,
            "changed_entities": [...],
            "from_date": str,
            "to_date": str,
        }
    """
    out_dir = snapshots_dir or _DEFAULT_SNAPSHOTS_DIR
    if not out_dir.is_dir():
        return {"error": "No snapshots directory found", "has_drift": False}

    # Find the two most recent snapshots
    snapshots = sorted(out_dir.glob("snapshot-*.json"), reverse=True)
    if len(snapshots) < 2:
        # Create today's snapshot first if only one exists
        if len(snapshots) == 0:
            create_system_snapshot(registry_path, snapshots_dir)
            return {"has_drift": False, "changed_entities": [], "note": "First snapshot created"}
        return {"has_drift": False, "changed_entities": [], "note": "Only one snapshot exists"}

    current_data = _load_snapshot_file(snapshots[0])
    previous_data = _load_snapshot_file(snapshots[1])

    if not current_data or not previous_data:
        return {"error": "Cannot load snapshots", "has_drift": False}

    changes = _compare_system_snapshots(previous_data, current_data)

    return {
        "has_drift": len(changes) > 0,
        "changed_entities": changes,
        "from_date": previous_data.get("date", ""),
        "to_date": current_data.get("date", ""),
        "total_changes": len(changes),
    }


def compare_entity_snapshots(
    entity_id: str,
    snapshots_dir: Path | None = None,
) -> dict[str, Any]:
    """Compare a specific entity across the two most recent snapshots.

    Returns detailed diff for the entity.
    """
    out_dir = snapshots_dir or _DEFAULT_SNAPSHOTS_DIR
    snapshots = sorted(out_dir.glob("snapshot-*.json"), reverse=True)
    if len(snapshots) < 2:
        return {"error": "Need at least 2 snapshots for comparison"}

    current_data = _load_snapshot_file(snapshots[0])
    previous_data = _load_snapshot_file(snapshots[1])

    if not current_data or not previous_data:
        return {"error": "Cannot load snapshots"}

    prev_entity = previous_data.get("entities", {}).get(entity_id)
    curr_entity = current_data.get("entities", {}).get(entity_id)

    if prev_entity is None and curr_entity is None:
        return {"error": f"Entity {entity_id} not found in either snapshot"}

    if prev_entity is None:
        return {"change": "added", "entity_id": entity_id, "new_state": curr_entity}

    if curr_entity is None:
        return {"change": "removed", "entity_id": entity_id, "old_state": prev_entity}

    if HAS_ONTOLOGIA:
        snap_a = StateSnapshot.from_dict(prev_entity)
        snap_b = StateSnapshot.from_dict(curr_entity)
        drift = has_drift(snap_a, snap_b)
        diff = compare_snapshots(snap_a, snap_b) if drift else {}
        return {
            "entity_id": entity_id,
            "has_drift": drift,
            "diff": diff,
            "from_date": previous_data.get("date", ""),
            "to_date": current_data.get("date", ""),
        }

    # Fallback comparison
    changed_props = {}
    all_keys = set(prev_entity.get("properties", {})) | set(curr_entity.get("properties", {}))
    for key in sorted(all_keys):
        old_v = prev_entity.get("properties", {}).get(key)
        new_v = curr_entity.get("properties", {}).get(key)
        if old_v != new_v:
            changed_props[key] = {"old": old_v, "new": new_v}

    return {
        "entity_id": entity_id,
        "has_drift": bool(changed_props),
        "changed_properties": changed_props,
        "from_date": previous_data.get("date", ""),
        "to_date": current_data.get("date", ""),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_snapshot_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _compare_system_snapshots(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare two system snapshots, returning per-entity change summaries."""
    changes: list[dict[str, Any]] = []
    prev_entities = previous.get("entities", {})
    curr_entities = current.get("entities", {})

    # New entities
    for eid in sorted(set(curr_entities) - set(prev_entities)):
        changes.append({"entity_id": eid, "change": "added"})

    # Removed entities
    for eid in sorted(set(prev_entities) - set(curr_entities)):
        changes.append({"entity_id": eid, "change": "removed"})

    # Changed entities
    for eid in sorted(set(prev_entities) & set(curr_entities)):
        prev_props = prev_entities[eid].get("properties", {})
        curr_props = curr_entities[eid].get("properties", {})
        changed_fields: list[str] = []
        for key in set(prev_props) | set(curr_props):
            if prev_props.get(key) != curr_props.get(key):
                changed_fields.append(key)
        if changed_fields:
            changes.append({
                "entity_id": eid,
                "change": "modified",
                "fields": changed_fields,
            })

    return changes


def _prune_old_snapshots(snapshots_dir: Path, keep_days: int = 30) -> int:
    """Remove snapshots older than keep_days. Returns count removed."""
    removed = 0
    for f in snapshots_dir.glob("snapshot-*.json"):
        try:
            date_str = f.stem.replace("snapshot-", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc,
            )
            age = (datetime.now(timezone.utc) - file_date).days
            if age > keep_days:
                f.unlink()
                removed += 1
        except (ValueError, OSError):
            continue
    return removed
