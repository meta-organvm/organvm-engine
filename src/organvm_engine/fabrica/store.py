"""JSONL append-only persistence for the Cyclic Dispatch Protocol.

Follows the pattern established by ``coordination.lifecycle`` —
append-only log at ``~/.organvm/fabrica/``, one file per object type.
Active state is computed by reading all entries and filtering.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from organvm_engine.fabrica.models import (
    ApproachVector,
    DispatchRecord,
    RelayIntent,
    RelayPacket,
    RelayPhase,
)

# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

_DEFAULT_DIR = Path.home() / ".organvm" / "fabrica"


def fabrica_dir() -> Path:
    """Return the fabrica storage directory.

    Respects ORGANVM_FABRICA_DIR for test isolation.
    """
    env = os.environ.get("ORGANVM_FABRICA_DIR")
    if env:
        return Path(env)
    return _DEFAULT_DIR


def _ensure_dir() -> Path:
    d = fabrica_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Generic JSONL append / read
# ---------------------------------------------------------------------------

def _append(filename: str, data: dict[str, Any]) -> None:
    d = _ensure_dir()
    with (d / filename).open("a") as f:
        f.write(json.dumps(data) + "\n")


def _read_all(filename: str) -> list[dict[str, Any]]:
    path = _ensure_dir() / filename
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped:
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return events


# ---------------------------------------------------------------------------
# RelayPacket persistence
# ---------------------------------------------------------------------------

def save_packet(packet: RelayPacket) -> None:
    _append("packets.jsonl", packet.to_dict())


def load_packets() -> list[RelayPacket]:
    return [RelayPacket.from_dict(d) for d in _read_all("packets.jsonl")]


def load_packet(packet_id: str) -> RelayPacket | None:
    for d in _read_all("packets.jsonl"):
        if d["id"] == packet_id:
            return RelayPacket.from_dict(d)
    return None


# ---------------------------------------------------------------------------
# ApproachVector persistence
# ---------------------------------------------------------------------------

def save_vector(vector: ApproachVector) -> None:
    _append("vectors.jsonl", vector.to_dict())


def load_vectors(packet_id: str | None = None) -> list[ApproachVector]:
    vectors = [ApproachVector.from_dict(d) for d in _read_all("vectors.jsonl")]
    if packet_id:
        vectors = [v for v in vectors if v.packet_id == packet_id]
    return vectors


# ---------------------------------------------------------------------------
# RelayIntent persistence
# ---------------------------------------------------------------------------

def save_intent(intent: RelayIntent) -> None:
    _append("intents.jsonl", intent.to_dict())


def load_intents(packet_id: str | None = None) -> list[RelayIntent]:
    intents = [RelayIntent.from_dict(d) for d in _read_all("intents.jsonl")]
    if packet_id:
        intents = [i for i in intents if i.packet_id == packet_id]
    return intents


def load_active_intents() -> list[RelayIntent]:
    """Return intents not yet COMPLETE."""
    return [
        i for i in load_intents()
        if i.phase != RelayPhase.COMPLETE
    ]


# ---------------------------------------------------------------------------
# DispatchRecord persistence
# ---------------------------------------------------------------------------

def save_dispatch(record: DispatchRecord) -> None:
    _append("dispatches.jsonl", record.to_dict())


def load_dispatches(intent_id: str | None = None) -> list[DispatchRecord]:
    records = [DispatchRecord.from_dict(d) for d in _read_all("dispatches.jsonl")]
    if intent_id:
        records = [r for r in records if r.intent_id == intent_id]
    return records


# ---------------------------------------------------------------------------
# Phase transition persistence (event log)
# ---------------------------------------------------------------------------

def log_transition(
    packet_id: str,
    from_phase: RelayPhase,
    to_phase: RelayPhase,
    reason: str = "",
) -> None:
    """Log a phase transition event."""
    import time

    _append("transitions.jsonl", {
        "type": "phase_transition",
        "packet_id": packet_id,
        "from": from_phase.value,
        "to": to_phase.value,
        "reason": reason,
        "timestamp": time.time(),
    })


def load_transitions(packet_id: str | None = None) -> list[dict[str, Any]]:
    transitions = _read_all("transitions.jsonl")
    if packet_id:
        transitions = [t for t in transitions if t["packet_id"] == packet_id]
    return transitions
