"""Data objects for the Cyclic Dispatch Protocol (SPEC-024).

Four objects compose the protocol's state:

    RelayPacket → ApproachVector → RelayIntent → DispatchRecord

Each entails the next. Objects are append-only — status changes are
recorded as new events, not mutations.
"""

from __future__ import annotations

import enum
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Phase state machine
# ---------------------------------------------------------------------------

class RelayPhase(str, enum.Enum):
    """The five states of a relay cycle."""

    RELEASE = "release"
    CATCH = "catch"
    HANDOFF = "handoff"
    FORTIFY = "fortify"
    COMPLETE = "complete"


class DispatchStatus(str, enum.Enum):
    """Status of a dispatched task."""

    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    DRAFT_RETURNED = "draft_returned"
    FORTIFIED = "fortified"
    MERGED = "merged"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


# ---------------------------------------------------------------------------
# RelayPacket — the seed entering at RELEASE
# ---------------------------------------------------------------------------

def _packet_id(timestamp: float, raw_text: str) -> str:
    """Content-addressed ID: SHA-256[:16] of timestamp + raw_text."""
    content = f"{timestamp}:{raw_text}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class RelayPacket:
    """The seed that enters the system at RELEASE.

    A RelayPacket is NOT a plan. It is pre-expansion, pre-clarification.
    It captures the idealized form before any handling.
    """

    raw_text: str
    source: str  # "cli" | "mcp" | "dashboard" | "voice" | "scheduled"
    timestamp: float = field(default_factory=time.time)
    session_id: str | None = None
    organ_hint: str | None = None
    tags: list[str] = field(default_factory=list)
    phase: RelayPhase = RelayPhase.RELEASE
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _packet_id(self.timestamp, self.raw_text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "relay_packet",
            "id": self.id,
            "raw_text": self.raw_text,
            "source": self.source,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "organ_hint": self.organ_hint,
            "tags": self.tags,
            "phase": self.phase.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelayPacket:
        return cls(
            id=data["id"],
            raw_text=data["raw_text"],
            source=data["source"],
            timestamp=data["timestamp"],
            session_id=data.get("session_id"),
            organ_hint=data.get("organ_hint"),
            tags=data.get("tags", []),
            phase=RelayPhase(data["phase"]),
        )


# ---------------------------------------------------------------------------
# ApproachVector — one interpretation generated during CATCH
# ---------------------------------------------------------------------------

@dataclass
class ApproachVector:
    """One possible interpretation of a RelayPacket.

    Generated during CATCH. The multiverse spray exists to prevent
    premature convergence.
    """

    packet_id: str
    thesis: str
    target_organs: list[str] = field(default_factory=list)
    scope: str = "medium"  # light | medium | heavy (ResourceWeight values)
    agent_types: list[str] = field(default_factory=list)
    selected: bool = False
    rationale: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            content = f"{self.packet_id}:{self.thesis}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "approach_vector",
            "id": self.id,
            "packet_id": self.packet_id,
            "thesis": self.thesis,
            "target_organs": self.target_organs,
            "scope": self.scope,
            "agent_types": self.agent_types,
            "selected": self.selected,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApproachVector:
        return cls(
            id=data["id"],
            packet_id=data["packet_id"],
            thesis=data["thesis"],
            target_organs=data.get("target_organs", []),
            scope=data.get("scope", "medium"),
            agent_types=data.get("agent_types", []),
            selected=data.get("selected", False),
            rationale=data.get("rationale", ""),
        )


# ---------------------------------------------------------------------------
# RelayIntent — a selected vector, ready for planning and dispatch
# ---------------------------------------------------------------------------

@dataclass
class RelayIntent:
    """A selected ApproachVector promoted to an intent.

    Carries the plan path and atomized task IDs once HANDOFF begins.
    """

    vector_id: str
    packet_id: str
    plan_path: str | None = None
    task_ids: list[str] = field(default_factory=list)
    dispatches: list[dict[str, Any]] = field(default_factory=list)
    phase: RelayPhase = RelayPhase.HANDOFF
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            content = f"{self.packet_id}:{self.vector_id}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "relay_intent",
            "id": self.id,
            "vector_id": self.vector_id,
            "packet_id": self.packet_id,
            "plan_path": self.plan_path,
            "task_ids": self.task_ids,
            "dispatches": self.dispatches,
            "phase": self.phase.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelayIntent:
        return cls(
            id=data["id"],
            vector_id=data["vector_id"],
            packet_id=data["packet_id"],
            plan_path=data.get("plan_path"),
            task_ids=data.get("task_ids", []),
            dispatches=data.get("dispatches", []),
            phase=RelayPhase(data["phase"]),
        )


# ---------------------------------------------------------------------------
# DispatchRecord — tracks where a task was sent and what came back
# ---------------------------------------------------------------------------

@dataclass
class DispatchRecord:
    """Tracks a single task dispatched to an agent backend."""

    task_id: str
    intent_id: str
    backend: str  # "copilot" | "jules" | "actions" | "claude" | "launchagent" | "human"
    target: str = ""  # Issue URL, workflow run ID, agent session ID, etc.
    status: DispatchStatus = DispatchStatus.DISPATCHED
    dispatched_at: float = field(default_factory=time.time)
    returned_at: float | None = None
    pr_url: str | None = None
    verdict: str | None = None  # Human verdict from FORTIFY
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            content = f"{self.intent_id}:{self.task_id}:{self.backend}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "dispatch_record",
            "id": self.id,
            "task_id": self.task_id,
            "intent_id": self.intent_id,
            "backend": self.backend,
            "target": self.target,
            "status": self.status.value,
            "dispatched_at": self.dispatched_at,
            "returned_at": self.returned_at,
            "pr_url": self.pr_url,
            "verdict": self.verdict,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DispatchRecord:
        return cls(
            id=data["id"],
            task_id=data["task_id"],
            intent_id=data["intent_id"],
            backend=data["backend"],
            target=data.get("target", ""),
            status=DispatchStatus(data["status"]),
            dispatched_at=data["dispatched_at"],
            returned_at=data.get("returned_at"),
            pr_url=data.get("pr_url"),
            verdict=data.get("verdict"),
        )
