"""Tests for the Testament Protocol chain operations."""

from __future__ import annotations

import json
from pathlib import Path

from organvm_engine.ledger.chain import (
    GENESIS_PREV_HASH,
    ChainVerificationResult,
    compute_event_hash,
    verify_chain,
    verify_chain_link,
    verify_hash,
)


class TestHashComputation:

    def test_compute_hash_deterministic(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "testament.genesis",
            "source_organ": "META-ORGANVM",
            "source_repo": "organvm-engine",
            "entity_uid": "",
            "actor": "human:4jp",
            "payload": {},
            "source_spec": "",
            "causal_predecessor": "",
            "prev_hash": GENESIS_PREV_HASH,
        }
        h1 = compute_event_hash(event)
        h2 = compute_event_hash(event)
        assert h1 == h2
        assert h1.startswith("sha256:")
        assert len(h1) == 71  # "sha256:" + 64 hex chars

    def test_compute_hash_excludes_hash_field(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
        }
        h1 = compute_event_hash(event)
        event_with_hash = {**event, "hash": "sha256:bogus"}
        h2 = compute_event_hash(event_with_hash)
        assert h1 == h2

    def test_any_field_change_changes_hash(self):
        base = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
        }
        h_base = compute_event_hash(base)
        for key in base:
            modified = {**base, key: "MODIFIED"}
            assert compute_event_hash(modified) != h_base, (
                f"Changing {key} should change hash"
            )

    def test_verify_hash_valid(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
        }
        event["hash"] = compute_event_hash(event)
        assert verify_hash(event) is True

    def test_verify_hash_tampered(self):
        event = {
            "event_id": "test-001",
            "sequence": 0,
            "timestamp": "2026-03-19T00:00:00+00:00",
            "event_type": "test",
            "prev_hash": GENESIS_PREV_HASH,
            "hash": "sha256:" + "0" * 64,
        }
        assert verify_hash(event) is False

    def test_verify_hash_empty_returns_false(self):
        assert verify_hash({"hash": ""}) is False
        assert verify_hash({}) is False

    def test_genesis_prev_hash_is_all_zeros(self):
        assert GENESIS_PREV_HASH == "sha256:" + "0" * 64

    def test_verify_chain_link(self):
        prev = {"hash": "sha256:abc123"}
        curr = {"prev_hash": "sha256:abc123"}
        assert verify_chain_link(prev, curr) is True

    def test_verify_chain_link_broken(self):
        prev = {"hash": "sha256:abc123"}
        curr = {"prev_hash": "sha256:different"}
        assert verify_chain_link(prev, curr) is False


class TestChainVerification:

    def test_verify_empty_chain(self, tmp_path):
        result = verify_chain(tmp_path / "empty.jsonl")
        assert result.valid is True
        assert result.event_count == 0

    def test_verify_nonexistent_file(self, tmp_path):
        result = verify_chain(tmp_path / "nope.jsonl")
        assert result.valid is True
        assert result.event_count == 0

    def test_verify_valid_chain(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(10):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")
        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is True
        assert result.event_count == 10
        assert result.errors == []

    def test_detect_tampered_hash(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        lines = (tmp_path / "events.jsonl").read_text().splitlines()
        event = json.loads(lines[2])
        event["payload"]["tampered"] = True
        lines[2] = json.dumps(event, separators=(",", ":"))
        (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n")

        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is False
        assert len(result.errors) >= 1
        assert any("hash mismatch" in e.lower() for e in result.errors)

    def test_detect_broken_chain_link(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        lines = (tmp_path / "events.jsonl").read_text().splitlines()
        event = json.loads(lines[3])
        event["prev_hash"] = "sha256:" + "f" * 64
        event["hash"] = compute_event_hash(event)
        lines[3] = json.dumps(event, separators=(",", ":"))
        (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n")

        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is False
        assert any("chain link" in e.lower() for e in result.errors)

    def test_result_tracks_last_sequence_and_hash(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        records = [spine.emit(event_type="test", entity_uid="e", actor="t") for _ in range(3)]
        result = verify_chain(tmp_path / "events.jsonl")
        assert result.last_sequence == 2
        assert result.last_hash == records[-1].hash

    def test_detect_sequence_gap(self, tmp_path):
        """Detect when a sequence number is skipped (event deleted)."""
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        # Delete event at sequence 2 (third line)
        lines = (tmp_path / "events.jsonl").read_text().splitlines()
        del lines[2]
        (tmp_path / "events.jsonl").write_text("\n".join(lines) + "\n")

        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is False
        # Should detect both sequence gap and chain link break
        assert len(result.errors) >= 1

    def test_verify_chain_string_path(self, tmp_path):
        """verify_chain accepts string paths."""
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        spine.emit(event_type="test", entity_uid="e", actor="t")
        result = verify_chain(str(tmp_path / "events.jsonl"))
        assert result.valid is True

    def test_verify_chain_with_blank_lines(self, tmp_path):
        """Chain verification handles blank lines in JSONL."""
        from organvm_engine.events.spine import EventSpine

        spine = EventSpine(tmp_path / "events.jsonl")
        spine.emit(event_type="test", entity_uid="e", actor="t")

        # Insert blank lines
        content = (tmp_path / "events.jsonl").read_text()
        content = "\n\n" + content + "\n\n"
        (tmp_path / "events.jsonl").write_text(content)

        result = verify_chain(tmp_path / "events.jsonl")
        assert result.valid is True
        assert result.event_count == 1


class TestChainReload:
    """Test that chain properties survive across EventSpine instances."""

    def test_new_spine_continues_chain(self, tmp_path):
        from organvm_engine.events.spine import EventSpine

        path = tmp_path / "events.jsonl"
        spine1 = EventSpine(path)
        r1 = spine1.emit(event_type="first", entity_uid="e", actor="t")

        # New instance reads from same file
        spine2 = EventSpine(path)
        r2 = spine2.emit(event_type="second", entity_uid="e", actor="t")

        assert r2.prev_hash == r1.hash
        assert r2.sequence == 1

        result = verify_chain(path)
        assert result.valid is True

    def test_many_reloads(self, tmp_path):
        """10 separate spine instances, each emitting one event."""
        from organvm_engine.events.spine import EventSpine

        path = tmp_path / "events.jsonl"
        for i in range(10):
            spine = EventSpine(path)
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        result = verify_chain(path)
        assert result.valid is True
        assert result.event_count == 10
        assert result.last_sequence == 9


class TestRepairChain:
    """Tests for repair_chain() — fixes corrupted chains."""

    def test_repair_valid_chain_is_noop(self, tmp_path):
        from organvm_engine.events.spine import EventSpine
        from organvm_engine.ledger.chain import repair_chain

        path = tmp_path / "events.jsonl"
        spine = EventSpine(path)
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        result = repair_chain(path)
        assert result["events_read"] == 5
        assert result["events_repaired"] == 0  # Nothing to fix

        post = verify_chain(path)
        assert post.valid is True

    def test_repair_fixes_broken_hashes(self, tmp_path):
        from organvm_engine.events.spine import EventSpine
        from organvm_engine.ledger.chain import repair_chain

        path = tmp_path / "events.jsonl"
        spine = EventSpine(path)
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        # Corrupt event 2
        lines = path.read_text().splitlines()
        event = json.loads(lines[2])
        event["payload"]["tampered"] = True
        lines[2] = json.dumps(event, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n")

        # Verify it's broken
        pre = verify_chain(path)
        assert pre.valid is False

        # Repair
        result = repair_chain(path)
        assert result["events_read"] == 5
        assert result["events_repaired"] > 0

        # Verify it's fixed
        post = verify_chain(path)
        assert post.valid is True

    def test_repair_fixes_sequence_gaps(self, tmp_path):
        from organvm_engine.events.spine import EventSpine
        from organvm_engine.ledger.chain import repair_chain

        path = tmp_path / "events.jsonl"
        spine = EventSpine(path)
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        # Mess up sequence numbers
        lines = path.read_text().splitlines()
        event = json.loads(lines[3])
        event["sequence"] = 99
        lines[3] = json.dumps(event, separators=(",", ":"))
        path.write_text("\n".join(lines) + "\n")

        result = repair_chain(path)
        assert result["events_repaired"] > 0

        post = verify_chain(path)
        assert post.valid is True
        assert post.last_sequence == 4  # Sequences are 0-4

    def test_repair_creates_backup(self, tmp_path):
        from organvm_engine.events.spine import EventSpine
        from organvm_engine.ledger.chain import repair_chain

        path = tmp_path / "events.jsonl"
        spine = EventSpine(path)
        spine.emit(event_type="test", entity_uid="e", actor="t")

        # Corrupt
        lines = path.read_text().splitlines()
        event = json.loads(lines[0])
        event["hash"] = "sha256:bogus"
        path.write_text(json.dumps(event, separators=(",", ":")) + "\n")

        result = repair_chain(path)
        backup = Path(result["backup"])
        assert backup.exists()
        assert backup.stat().st_size > 0

    def test_repair_nonexistent_file(self, tmp_path):
        from organvm_engine.ledger.chain import repair_chain

        result = repair_chain(tmp_path / "nope.jsonl")
        assert result["events_read"] == 0
        assert "File not found" in result["errors"]

    def test_repair_empty_file(self, tmp_path):
        from organvm_engine.ledger.chain import repair_chain

        path = tmp_path / "events.jsonl"
        path.touch()
        result = repair_chain(path)
        assert result["events_read"] == 0


class TestConcurrentLocking:
    """Test that file locking prevents chain corruption under concurrency."""

    def test_threaded_writes_produce_valid_chain(self, tmp_path):
        """Two threads writing 50 events each should produce a valid 100-event chain."""
        import threading

        from organvm_engine.events.spine import EventSpine

        path = tmp_path / "chain.jsonl"
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(50):
                    spine = EventSpine(path)
                    spine.emit(
                        event_type="test",
                        entity_uid=f"t{thread_id}_e{i}",
                        actor=f"thread-{thread_id}",
                    )
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=writer, args=(1,))
        t2 = threading.Thread(target=writer, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == [], f"Thread errors: {errors}"

        result = verify_chain(path)
        assert result.event_count == 100
        assert result.valid is True
        assert result.last_sequence == 99
