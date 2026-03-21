"""Ring 4 — external chain anchoring data structures and hash computation.

Provides the foundational types for anchoring Merkle checkpoint roots
on an external chain (e.g., Base L2, Celestia). This module does NOT
perform actual blockchain interaction — it produces the data structures
and anchor hashes that a future on-chain submission layer would consume.

The anchor hash is a SHA-256 digest over:
- The Merkle root being anchored
- The chain's last event hash (tip)
- The sequence range covered
- A timestamp

This gives an external verifier a single hash that attests to the
entire event batch's integrity at a point in time.
"""

from __future__ import annotations

import hashlib
import json as _json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AnchorRecord:
    """A record prepared for external chain anchoring.

    Encapsulates everything needed to submit a Merkle checkpoint root
    to an external chain.  The ``anchor_hash`` field is the digest
    that would actually be written on-chain.

    Attributes:
        merkle_root: The Merkle root of the event batch.
        chain_tip_hash: The hash of the last event in the anchored range.
        sequence_start: First event sequence number in the batch.
        sequence_end: Last event sequence number in the batch.
        event_count: Number of events in the anchored batch.
        timestamp: ISO-8601 UTC timestamp of anchor creation.
        anchor_hash: SHA-256 digest computed over all anchored fields.
        metadata: Optional metadata (chain target, contract address, etc.).
    """

    merkle_root: str
    chain_tip_hash: str
    sequence_start: int
    sequence_end: int
    event_count: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    anchor_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.anchor_hash:
            self.anchor_hash = compute_anchor_hash(
                merkle_root=self.merkle_root,
                chain_tip_hash=self.chain_tip_hash,
                sequence_start=self.sequence_start,
                sequence_end=self.sequence_end,
                event_count=self.event_count,
                timestamp=self.timestamp,
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnchorRecord:
        """Deserialize from a dict, recomputing anchor_hash for verification."""
        return cls(
            merkle_root=data["merkle_root"],
            chain_tip_hash=data["chain_tip_hash"],
            sequence_start=data["sequence_start"],
            sequence_end=data["sequence_end"],
            event_count=data["event_count"],
            timestamp=data.get(
                "timestamp",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            anchor_hash=data.get("anchor_hash", ""),
            metadata=data.get("metadata", {}),
        )


def compute_anchor_hash(
    merkle_root: str,
    chain_tip_hash: str,
    sequence_start: int,
    sequence_end: int,
    event_count: int,
    timestamp: str,
) -> str:
    """Compute a SHA-256 anchor digest for external chain submission.

    The hash covers all integrity-critical fields in canonical JSON
    form (sorted keys, no whitespace). The result is a ``sha256:``
    prefixed hex string, consistent with the event chain hash format.

    Args:
        merkle_root: Merkle root of the event batch.
        chain_tip_hash: Hash of the last event in the batch.
        sequence_start: First sequence number in the batch.
        sequence_end: Last sequence number in the batch.
        event_count: Number of events in the batch.
        timestamp: ISO-8601 UTC timestamp of anchor creation.

    Returns:
        ``sha256:<64 hex chars>`` anchor digest.
    """
    payload = {
        "chain_tip_hash": chain_tip_hash,
        "event_count": event_count,
        "merkle_root": merkle_root,
        "sequence_end": sequence_end,
        "sequence_start": sequence_start,
        "timestamp": timestamp,
    }
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def verify_anchor(record: AnchorRecord) -> bool:
    """Verify that an AnchorRecord's anchor_hash is consistent.

    Recomputes the hash from the record's fields and compares
    against the stored anchor_hash.

    Returns:
        True if the anchor hash matches the recomputed value.
    """
    expected = compute_anchor_hash(
        merkle_root=record.merkle_root,
        chain_tip_hash=record.chain_tip_hash,
        sequence_start=record.sequence_start,
        sequence_end=record.sequence_end,
        event_count=record.event_count,
        timestamp=record.timestamp,
    )
    return record.anchor_hash == expected
