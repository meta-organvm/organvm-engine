"""Linear Logic layer — consumption semantics and dispatch ledger.

Tracks dispatch_id values to prevent double-execution. The dispatch
payload already generates a dispatch_id (UUID) — this module tracks
which IDs have been consumed.

Storage: JSONL at ~/.organvm/dispatch-ledger.jsonl (same pattern as
coordination/claims.py which uses ~/.organvm/claims.jsonl).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_LEDGER_DIR = Path.home() / ".organvm"
_LEDGER_FILE = _LEDGER_DIR / "dispatch-ledger.jsonl"


def _ledger_file() -> Path:
    """Return path to the dispatch ledger file."""
    env = os.environ.get("ORGANVM_DISPATCH_LEDGER")
    if env:
        return Path(env)
    return _LEDGER_FILE


@dataclass
class LedgerEntry:
    """A single dispatch event record."""

    dispatch_id: str
    event: str
    source: str
    target: str
    timestamp: float
    status: str = "pending"  # pending | consumed | rejected
    consumed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "event": self.event,
            "source": self.source,
            "target": self.target,
            "timestamp": self.timestamp,
            "status": self.status,
            "consumed_at": self.consumed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LedgerEntry:
        return cls(
            dispatch_id=d.get("dispatch_id", ""),
            event=d.get("event", ""),
            source=d.get("source", ""),
            target=d.get("target", ""),
            timestamp=d.get("timestamp", 0.0),
            status=d.get("status", "pending"),
            consumed_at=d.get("consumed_at", 0.0),
        )


@dataclass
class LedgerStatus:
    """Summary of the dispatch ledger state."""

    total: int = 0
    pending: int = 0
    consumed: int = 0
    rejected: int = 0
    duplicates_prevented: int = 0
    entries: list[LedgerEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "pending": self.pending,
            "consumed": self.consumed,
            "rejected": self.rejected,
            "duplicates_prevented": self.duplicates_prevented,
        }


class DispatchLedger:
    """Append-only ledger of dispatched events. Prevents double-fire.

    Thread-safe for single-process use (append-only JSONL).
    """

    def __init__(self, ledger_path: Path | None = None):
        self._path = ledger_path or _ledger_file()
        self._entries: dict[str, LedgerEntry] | None = None

    def _ensure_loaded(self) -> dict[str, LedgerEntry]:
        if self._entries is not None:
            return self._entries
        self._entries = {}
        if self._path.is_file():
            for line in self._path.read_text().splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                    entry = LedgerEntry.from_dict(data)
                    # Later entries override earlier ones (for status updates)
                    self._entries[entry.dispatch_id] = entry
                except (json.JSONDecodeError, KeyError):
                    continue
        return self._entries

    def _append(self, entry: LedgerEntry) -> None:
        """Append an entry to the JSONL ledger file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def record(
        self,
        dispatch_id: str,
        event: str,
        source: str,
        target: str,
    ) -> bool:
        """Record a dispatch. Returns False if already recorded (duplicate).

        Args:
            dispatch_id: Unique dispatch identifier (UUID from payload).
            event: Event type string.
            source: Source organ identifier.
            target: Target organ identifier.

        Returns:
            True if recorded successfully, False if duplicate.
        """
        entries = self._ensure_loaded()

        if dispatch_id in entries:
            return False

        entry = LedgerEntry(
            dispatch_id=dispatch_id,
            event=event,
            source=source,
            target=target,
            timestamp=time.time(),
            status="pending",
        )
        entries[dispatch_id] = entry
        self._append(entry)
        return True

    def consume(self, dispatch_id: str) -> bool:
        """Mark a dispatch as consumed. Returns False if not found or already consumed."""
        entries = self._ensure_loaded()

        entry = entries.get(dispatch_id)
        if entry is None:
            return False
        if entry.status == "consumed":
            return False

        entry.status = "consumed"
        entry.consumed_at = time.time()
        # Append updated status
        self._append(entry)
        return True

    def reject(self, dispatch_id: str) -> bool:
        """Mark a dispatch as rejected. Returns False if not found."""
        entries = self._ensure_loaded()

        entry = entries.get(dispatch_id)
        if entry is None:
            return False

        entry.status = "rejected"
        self._append(entry)
        return True

    def is_consumed(self, dispatch_id: str) -> bool:
        """Check if a dispatch ID has been consumed."""
        entries = self._ensure_loaded()
        entry = entries.get(dispatch_id)
        return entry is not None and entry.status == "consumed"

    def is_known(self, dispatch_id: str) -> bool:
        """Check if a dispatch ID exists in the ledger."""
        entries = self._ensure_loaded()
        return dispatch_id in entries

    def get_status(self, dispatch_id: str) -> str:
        """Get the status of a dispatch ID.

        Returns: "pending", "consumed", "rejected", or "unknown".
        """
        entries = self._ensure_loaded()
        entry = entries.get(dispatch_id)
        if entry is None:
            return "unknown"
        return entry.status

    def status(self) -> LedgerStatus:
        """Get summary of ledger state."""
        entries = self._ensure_loaded()

        result = LedgerStatus(total=len(entries))
        for entry in entries.values():
            if entry.status == "pending":
                result.pending += 1
            elif entry.status == "consumed":
                result.consumed += 1
            elif entry.status == "rejected":
                result.rejected += 1
            result.entries.append(entry)

        return result

    def find_duplicates(self, event: str, source: str, target: str) -> list[LedgerEntry]:
        """Find entries matching event+source+target (potential duplicates)."""
        entries = self._ensure_loaded()
        return [
            e for e in entries.values()
            if e.event == event and e.source == source and e.target == target
        ]

    def recent(self, hours: float = 24) -> list[LedgerEntry]:
        """Get entries from the last N hours."""
        entries = self._ensure_loaded()
        cutoff = time.time() - (hours * 3600)
        return [e for e in entries.values() if e.timestamp >= cutoff]
