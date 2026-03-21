"""Tests for the ledger anchor module (Ring 4 external anchoring) — issue #55."""

from __future__ import annotations

import json

from organvm_engine.ledger.anchor import (
    AnchorRecord,
    compute_anchor_hash,
    verify_anchor,
)

# ── compute_anchor_hash ───────────────────────────────────────────


class TestComputeAnchorHash:
    """Tests for the anchor hash computation."""

    def test_produces_sha256_prefixed_string(self):
        h = compute_anchor_hash(
            merkle_root="sha256:" + "a" * 64,
            chain_tip_hash="sha256:" + "b" * 64,
            sequence_start=0,
            sequence_end=99,
            event_count=100,
            timestamp="2026-03-21T12:00:00Z",
        )
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64

    def test_deterministic_for_same_inputs(self):
        kwargs = {
            "merkle_root": "sha256:" + "c" * 64,
            "chain_tip_hash": "sha256:" + "d" * 64,
            "sequence_start": 10,
            "sequence_end": 50,
            "event_count": 41,
            "timestamp": "2026-03-21T12:00:00Z",
        }
        h1 = compute_anchor_hash(**kwargs)
        h2 = compute_anchor_hash(**kwargs)
        assert h1 == h2

    def test_different_inputs_produce_different_hashes(self):
        base = {
            "merkle_root": "sha256:" + "e" * 64,
            "chain_tip_hash": "sha256:" + "f" * 64,
            "sequence_start": 0,
            "sequence_end": 99,
            "event_count": 100,
            "timestamp": "2026-03-21T12:00:00Z",
        }
        h1 = compute_anchor_hash(**base)
        h2 = compute_anchor_hash(**{**base, "event_count": 101})
        assert h1 != h2

    def test_timestamp_affects_hash(self):
        base = {
            "merkle_root": "sha256:" + "0" * 64,
            "chain_tip_hash": "sha256:" + "1" * 64,
            "sequence_start": 0,
            "sequence_end": 10,
            "event_count": 11,
        }
        h1 = compute_anchor_hash(**base, timestamp="2026-03-21T12:00:00Z")
        h2 = compute_anchor_hash(**base, timestamp="2026-03-21T13:00:00Z")
        assert h1 != h2


# ── AnchorRecord ──────────────────────────────────────────────────


class TestAnchorRecord:
    """Tests for the AnchorRecord dataclass."""

    def _make_record(self, **kwargs) -> AnchorRecord:
        defaults = {
            "merkle_root": "sha256:" + "a" * 64,
            "chain_tip_hash": "sha256:" + "b" * 64,
            "sequence_start": 0,
            "sequence_end": 99,
            "event_count": 100,
            "timestamp": "2026-03-21T12:00:00Z",
        }
        defaults.update(kwargs)
        return AnchorRecord(**defaults)

    def test_auto_computes_anchor_hash(self):
        record = self._make_record()
        assert record.anchor_hash.startswith("sha256:")
        assert len(record.anchor_hash) == len("sha256:") + 64

    def test_anchor_hash_matches_compute_function(self):
        record = self._make_record()
        expected = compute_anchor_hash(
            merkle_root=record.merkle_root,
            chain_tip_hash=record.chain_tip_hash,
            sequence_start=record.sequence_start,
            sequence_end=record.sequence_end,
            event_count=record.event_count,
            timestamp=record.timestamp,
        )
        assert record.anchor_hash == expected

    def test_preserves_explicit_anchor_hash(self):
        """If anchor_hash is provided, it is kept as-is."""
        explicit = "sha256:" + "f" * 64
        record = self._make_record(anchor_hash=explicit)
        assert record.anchor_hash == explicit

    def test_to_dict_round_trip(self):
        record = self._make_record()
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["merkle_root"] == record.merkle_root
        assert d["anchor_hash"] == record.anchor_hash
        assert d["event_count"] == 100

    def test_from_dict_round_trip(self):
        original = self._make_record()
        d = original.to_dict()
        restored = AnchorRecord.from_dict(d)
        assert restored.merkle_root == original.merkle_root
        assert restored.chain_tip_hash == original.chain_tip_hash
        assert restored.sequence_start == original.sequence_start
        assert restored.sequence_end == original.sequence_end
        assert restored.event_count == original.event_count
        assert restored.timestamp == original.timestamp

    def test_json_serializable(self):
        record = self._make_record(metadata={"chain": "base-sepolia"})
        d = record.to_dict()
        s = json.dumps(d)
        parsed = json.loads(s)
        assert parsed["metadata"]["chain"] == "base-sepolia"
        assert parsed["anchor_hash"].startswith("sha256:")

    def test_metadata_defaults_to_empty(self):
        record = self._make_record()
        assert record.metadata == {}

    def test_metadata_preserved(self):
        record = self._make_record(metadata={"contract": "0xDEAD", "network": "base"})
        assert record.metadata["contract"] == "0xDEAD"
        assert record.metadata["network"] == "base"


# ── verify_anchor ─────────────────────────────────────────────────


class TestVerifyAnchor:
    """Tests for anchor verification."""

    def test_valid_record_passes(self):
        record = AnchorRecord(
            merkle_root="sha256:" + "a" * 64,
            chain_tip_hash="sha256:" + "b" * 64,
            sequence_start=0,
            sequence_end=99,
            event_count=100,
            timestamp="2026-03-21T12:00:00Z",
        )
        assert verify_anchor(record) is True

    def test_tampered_record_fails(self):
        record = AnchorRecord(
            merkle_root="sha256:" + "a" * 64,
            chain_tip_hash="sha256:" + "b" * 64,
            sequence_start=0,
            sequence_end=99,
            event_count=100,
            timestamp="2026-03-21T12:00:00Z",
        )
        # Tamper with a field after construction
        record.event_count = 999
        assert verify_anchor(record) is False

    def test_explicit_wrong_hash_fails(self):
        record = AnchorRecord(
            merkle_root="sha256:" + "a" * 64,
            chain_tip_hash="sha256:" + "b" * 64,
            sequence_start=0,
            sequence_end=99,
            event_count=100,
            timestamp="2026-03-21T12:00:00Z",
            anchor_hash="sha256:" + "0" * 64,  # wrong hash
        )
        assert verify_anchor(record) is False


# ── Integration with ledger __init__ ──────────────────────────────


class TestLedgerExports:
    """Verify anchor types are exported from the ledger package."""

    def test_anchor_record_importable(self):
        from organvm_engine.ledger import AnchorRecord
        assert AnchorRecord is not None

    def test_compute_anchor_hash_importable(self):
        from organvm_engine.ledger import compute_anchor_hash
        assert callable(compute_anchor_hash)

    def test_verify_anchor_importable(self):
        from organvm_engine.ledger import verify_anchor
        assert callable(verify_anchor)
