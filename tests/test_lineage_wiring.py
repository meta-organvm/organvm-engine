"""Tests for lineage wiring on archive/dissolve transitions.

Implements: SPEC-000 AX-000-007, SPEC-003 INV-000-003
Resolves: engine #18 (lineage wiring)

Covers:
  - create_archival_lineage() record creation
  - wire_lineage_on_transition() conditional lineage
  - Action classification (archive, dissolve, merge, deprecate)
  - ENTITY_ARCHIVED event emission

All file operations use tmp_path — never writes to production paths.
"""

from __future__ import annotations

from organvm_engine.events.spine import EventSpine, EventType
from organvm_engine.governance.lineage import (
    create_archival_lineage,
    wire_lineage_on_transition,
)

# ---------------------------------------------------------------------------
# create_archival_lineage
# ---------------------------------------------------------------------------

class TestCreateArchivalLineage:
    def test_minimal_record(self):
        record = create_archival_lineage("ent_repo_abc", "No longer needed")
        assert record["entity_uid"] == "ent_repo_abc"
        assert record["reason"] == "No longer needed"
        assert record["action"] == "archive"
        assert record["lineage_id"].startswith("lin_")
        assert "timestamp" in record

    def test_with_successor(self):
        record = create_archival_lineage(
            "ent_repo_old",
            "Replaced by new repo",
            successor_uid="ent_repo_new",
        )
        assert record["successor_uid"] == "ent_repo_new"
        assert record["entity_uid"] == "ent_repo_old"

    def test_with_dissolution_target(self):
        record = create_archival_lineage(
            "ent_repo_xyz",
            "Dissolved into collider",
            dissolution_target="materia-collider",
        )
        assert record["dissolution_target"] == "materia-collider"
        assert record["action"] == "dissolve"

    def test_with_both_successor_and_dissolution(self):
        record = create_archival_lineage(
            "ent_repo_a",
            "Dissolved and replaced",
            successor_uid="ent_repo_b",
            dissolution_target="collider-entry-42",
        )
        assert record["successor_uid"] == "ent_repo_b"
        assert record["dissolution_target"] == "collider-entry-42"

    def test_unique_lineage_ids(self):
        r1 = create_archival_lineage("ent_1", "Reason 1")
        r2 = create_archival_lineage("ent_2", "Reason 2")
        assert r1["lineage_id"] != r2["lineage_id"]

    def test_lineage_id_format(self):
        record = create_archival_lineage("ent_repo_x", "test")
        lid = record["lineage_id"]
        assert lid.startswith("lin_")
        assert len(lid) == 16  # "lin_" + 12 hex chars

    def test_timestamp_is_iso_format(self):
        record = create_archival_lineage("ent_1", "test")
        ts = record["timestamp"]
        # ISO 8601 with timezone
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_no_successor_key_when_none(self):
        record = create_archival_lineage("ent_1", "simple archive")
        assert "successor_uid" not in record

    def test_no_dissolution_key_when_none(self):
        record = create_archival_lineage("ent_1", "simple archive")
        assert "dissolution_target" not in record


# ---------------------------------------------------------------------------
# Action classification
# ---------------------------------------------------------------------------

class TestActionClassification:
    def test_default_is_archive(self):
        record = create_archival_lineage("e", "No longer maintained")
        assert record["action"] == "archive"

    def test_dissolve_from_reason(self):
        record = create_archival_lineage("e", "Dissolved into materia-collider")
        assert record["action"] == "dissolve"

    def test_dissolve_from_target(self):
        record = create_archival_lineage(
            "e", "Moved elsewhere", dissolution_target="collider",
        )
        assert record["action"] == "dissolve"

    def test_merge_from_reason(self):
        record = create_archival_lineage("e", "Merged with sibling repo")
        assert record["action"] == "merge"

    def test_deprecate_from_reason(self):
        record = create_archival_lineage("e", "Deprecated in favor of v2")
        assert record["action"] == "deprecate"

    def test_dissolved_case_insensitive(self):
        record = create_archival_lineage("e", "DISSOLVED into collider")
        assert record["action"] == "dissolve"

    def test_merge_case_insensitive(self):
        record = create_archival_lineage("e", "MERGE with other")
        assert record["action"] == "merge"


# ---------------------------------------------------------------------------
# wire_lineage_on_transition
# ---------------------------------------------------------------------------

class TestWireLineageOnTransition:
    def test_archived_transition_creates_lineage(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_repo_old",
            "GRADUATED",
            "ARCHIVED",
            reason="Project complete",
            spine_path=spine_path,
        )
        assert record is not None
        assert record["entity_uid"] == "ent_repo_old"
        assert record["from_state"] == "GRADUATED"
        assert record["to_state"] == "ARCHIVED"
        assert record["reason"] == "Project complete"

    def test_dissolved_reason_creates_lineage(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_repo_dead",
            "LOCAL",
            "LOCAL",
            reason="Dissolved into materia-collider",
            spine_path=spine_path,
        )
        assert record is not None
        assert record["action"] == "dissolve"

    def test_non_archive_no_dissolve_returns_none(self):
        record = wire_lineage_on_transition(
            "ent_repo_x",
            "LOCAL",
            "CANDIDATE",
            reason="Promoted",
        )
        assert record is None

    def test_no_reason_still_works_for_archived(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_repo_y",
            "PUBLIC_PROCESS",
            "ARCHIVED",
            spine_path=spine_path,
        )
        assert record is not None
        assert "Transitioned from" in record["reason"]

    def test_actor_recorded(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_repo_z",
            "GRADUATED",
            "ARCHIVED",
            reason="Done",
            actor="agent:forge-3",
            spine_path=spine_path,
        )
        assert record is not None
        assert record["actor"] == "agent:forge-3"

    def test_successor_uid_passed_through(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_repo_old",
            "GRADUATED",
            "ARCHIVED",
            reason="Replaced",
            successor_uid="ent_repo_new",
            spine_path=spine_path,
        )
        assert record is not None
        assert record["successor_uid"] == "ent_repo_new"

    def test_dissolution_target_passed_through(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_repo_old",
            "LOCAL",
            "ARCHIVED",
            reason="Dissolved",
            dissolution_target="materia-collider",
            spine_path=spine_path,
        )
        assert record is not None
        assert record["dissolution_target"] == "materia-collider"
        assert record["action"] == "dissolve"

    def test_default_actor_is_cli(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        record = wire_lineage_on_transition(
            "ent_1",
            "CANDIDATE",
            "ARCHIVED",
            spine_path=spine_path,
        )
        assert record is not None
        assert record["actor"] == "cli"


# ---------------------------------------------------------------------------
# ENTITY_ARCHIVED event emission
# ---------------------------------------------------------------------------

class TestEntityArchivedEvent:
    def test_emits_entity_archived_event(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        wire_lineage_on_transition(
            "ent_repo_archived",
            "GRADUATED",
            "ARCHIVED",
            reason="End of life",
            actor="human",
            spine_path=spine_path,
        )
        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.ENTITY_ARCHIVED)
        assert len(events) == 1
        evt = events[0]
        assert evt.entity_uid == "ent_repo_archived"
        assert evt.payload["from_state"] == "GRADUATED"
        assert evt.payload["to_state"] == "ARCHIVED"
        assert evt.payload["reason"] == "End of life"
        assert evt.payload["lineage_id"].startswith("lin_")
        assert evt.source_spec == "SPEC-000"
        assert evt.actor == "human"

    def test_no_event_when_no_lineage_needed(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        wire_lineage_on_transition(
            "ent_repo_normal",
            "LOCAL",
            "CANDIDATE",
            reason="Normal promotion",
            spine_path=spine_path,
        )
        # Spine file should not exist
        assert not spine_path.exists()

    def test_event_on_dissolve_reason(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        wire_lineage_on_transition(
            "ent_repo_dissolved",
            "LOCAL",
            "LOCAL",
            reason="Dissolved into collider",
            spine_path=spine_path,
        )
        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.ENTITY_ARCHIVED)
        assert len(events) == 1
        assert events[0].payload["reason"] == "Dissolved into collider"

    def test_multiple_archives_accumulate_events(self, tmp_path):
        spine_path = tmp_path / "events.jsonl"
        wire_lineage_on_transition(
            "ent_1", "GRADUATED", "ARCHIVED",
            reason="Done 1", spine_path=spine_path,
        )
        wire_lineage_on_transition(
            "ent_2", "CANDIDATE", "ARCHIVED",
            reason="Done 2", spine_path=spine_path,
        )
        spine = EventSpine(path=spine_path)
        events = spine.query(event_type=EventType.ENTITY_ARCHIVED)
        assert len(events) == 2
        uids = {e.entity_uid for e in events}
        assert uids == {"ent_1", "ent_2"}
