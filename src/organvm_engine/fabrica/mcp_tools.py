"""MCP tool functions for the Cyclic Dispatch Protocol (SPEC-024 Phase 6).

Exposes fabrica state and operations as pure functions returning
JSON-serializable dicts. These functions are consumed by the MCP
server in organvm-mcp-server — they do NOT depend on the MCP SDK.

Four tools:
    fabrica_status   — list active relay cycles with dispatch records
    fabrica_dispatch — create a new dispatch (wraps release + handoff)
    fabrica_log      — show transition history for a relay
    fabrica_health   — return health report (active/completed/failed counts)
"""

from __future__ import annotations

from typing import Any


def fabrica_status(
    packet_id: str | None = None,
    phase: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List active relay cycles with dispatch records and current phase.

    Parameters
    ----------
    packet_id:
        Filter to a single packet by ID or prefix.
    phase:
        Filter by current phase (release, catch, handoff, fortify, complete).
    limit:
        Maximum number of cycles to return (default 50).
    """
    from organvm_engine.fabrica.store import (
        load_active_intents,
        load_dispatches,
        load_packets,
        load_transitions,
        load_vectors,
    )

    packets = load_packets()

    if packet_id:
        packets = [p for p in packets if p.id == packet_id or p.id.startswith(packet_id)]

    cycles: list[dict[str, Any]] = []
    for p in packets:
        transitions = load_transitions(packet_id=p.id)
        current_phase = transitions[-1]["to"] if transitions else p.phase.value
        vectors = load_vectors(packet_id=p.id)

        # Collect dispatches via intents
        dispatch_records: list[dict[str, Any]] = []
        for intent in load_active_intents():
            if intent.packet_id == p.id:
                for d in load_dispatches(intent_id=intent.id):
                    dispatch_records.append(d.to_dict())

        # Also check all intents (not just active) for completed cycles
        if not dispatch_records:
            from organvm_engine.fabrica.store import load_intents
            for intent in load_intents(packet_id=p.id):
                for d in load_dispatches(intent_id=intent.id):
                    dispatch_records.append(d.to_dict())

        cycle = {
            "packet_id": p.id,
            "raw_text": p.raw_text,
            "source": p.source,
            "organ_hint": p.organ_hint,
            "tags": p.tags,
            "current_phase": current_phase,
            "timestamp": p.timestamp,
            "vector_count": len(vectors),
            "dispatch_count": len(dispatch_records),
            "transition_count": len(transitions),
            "dispatches": dispatch_records,
        }
        cycles.append(cycle)

    # Apply phase filter after computing current_phase
    if phase:
        phase_lower = phase.lower()
        cycles = [c for c in cycles if c["current_phase"] == phase_lower]

    # Apply limit
    cycles = cycles[:limit]

    return {
        "total": len(cycles),
        "cycles": cycles,
    }


def fabrica_dispatch(
    text: str,
    source: str = "mcp",
    organ_hint: str | None = None,
    tags: list[str] | None = None,
    backend: str | None = None,
    repo: str | None = None,
    title: str | None = None,
    body: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Create a new dispatch — wraps RELEASE through HANDOFF.

    At minimum, creates a RelayPacket (RELEASE phase) and transitions
    to CATCH. If ``backend`` and ``repo`` are provided, also creates
    a minimal intent and dispatches to the backend (HANDOFF phase).

    Parameters
    ----------
    text:
        Raw intention text for the relay packet.
    source:
        Source channel (mcp, cli, dashboard, voice, scheduled).
    organ_hint:
        Optional organ target hint.
    tags:
        Semantic tags for the packet.
    backend:
        Agent backend to dispatch to (copilot, jules, actions, claude,
        launchagent, human). If omitted, only RELEASE is performed.
    repo:
        Target repository (owner/repo). Required if backend is set.
    title:
        Task title. Defaults to first 72 chars of text.
    body:
        Task body/specification. Defaults to full text.
    dry_run:
        If True (default), simulates dispatch without side effects.
        Backend dry-run prevents actual issue/workflow creation.
    """
    from organvm_engine.fabrica.models import RelayPacket, RelayPhase
    from organvm_engine.fabrica.state import valid_transition
    from organvm_engine.fabrica.store import log_transition, save_packet

    if not text:
        return {"error": "text is required"}

    packet = RelayPacket(
        raw_text=text,
        source=source,
        organ_hint=organ_hint,
        tags=tags or [],
    )
    save_packet(packet)

    # Transition RELEASE → CATCH
    if valid_transition(RelayPhase.RELEASE, RelayPhase.CATCH):
        log_transition(packet.id, RelayPhase.RELEASE, RelayPhase.CATCH, reason="auto")

    result: dict[str, Any] = {
        "packet_id": packet.id,
        "raw_text": packet.raw_text,
        "source": packet.source,
        "organ_hint": packet.organ_hint,
        "tags": packet.tags,
        "phase": "catch",
    }

    # If backend + repo are provided, proceed through HANDOFF
    if backend and repo:
        from organvm_engine.fabrica.backends import VALID_BACKENDS

        if backend not in VALID_BACKENDS:
            result["dispatch_error"] = (
                f"Unknown backend {backend!r}. "
                f"Valid: {', '.join(sorted(VALID_BACKENDS))}"
            )
            return result

        import hashlib
        import time

        from organvm_engine.fabrica.backends import get_backend
        from organvm_engine.fabrica.models import RelayIntent
        from organvm_engine.fabrica.store import save_dispatch, save_intent

        # Create intent
        intent = RelayIntent(vector_id="auto", packet_id=packet.id)
        save_intent(intent)

        # Generate task_id
        task_id = hashlib.sha256(
            f"{packet.id}:{title or text[:72]}:{time.time()}".encode(),
        ).hexdigest()[:16]

        # Dispatch to backend
        backend_impl = get_backend(backend)
        record = backend_impl.dispatch(
            task_id=task_id,
            intent_id=intent.id,
            repo=repo,
            title=title or text[:72],
            body=body or text,
            labels=None,
            branch=None,
            dry_run=dry_run,
        )
        save_dispatch(record)

        # Transition CATCH → HANDOFF → FORTIFY
        if valid_transition(RelayPhase.CATCH, RelayPhase.HANDOFF):
            log_transition(
                packet.id, RelayPhase.CATCH, RelayPhase.HANDOFF,
                reason="vector auto-selected",
            )
        if valid_transition(RelayPhase.HANDOFF, RelayPhase.FORTIFY):
            log_transition(
                packet.id, RelayPhase.HANDOFF, RelayPhase.FORTIFY,
                reason=f"dispatched to {backend}",
            )

        result["phase"] = "fortify"
        result["intent_id"] = intent.id
        result["dispatch"] = record.to_dict()
        result["dry_run"] = dry_run

    return result


def fabrica_log(
    packet_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Show transition history for a relay cycle.

    Parameters
    ----------
    packet_id:
        Filter transitions to a specific packet. If omitted,
        returns all transitions.
    limit:
        Maximum number of transitions to return (default 100).
    """
    from organvm_engine.fabrica.store import load_transitions

    transitions = load_transitions(packet_id=packet_id)
    transitions = transitions[:limit]

    entries: list[dict[str, Any]] = []
    for t in transitions:
        entries.append({
            "packet_id": t["packet_id"],
            "from_phase": t["from"],
            "to_phase": t["to"],
            "reason": t.get("reason", ""),
            "timestamp": t["timestamp"],
        })

    return {
        "total": len(entries),
        "transitions": entries,
    }


def fabrica_health() -> dict[str, Any]:
    """Return the health report — active/completed/failed counts.

    Aggregates across all relay cycles to produce:
    - Counts by current phase
    - Counts by dispatch status
    - Total packets, intents, and dispatches
    """
    from organvm_engine.fabrica.models import DispatchStatus
    from organvm_engine.fabrica.store import (
        load_dispatches,
        load_intents,
        load_packets,
        load_transitions,
    )

    packets = load_packets()
    all_intents = load_intents()
    all_dispatches = load_dispatches()
    all_transitions = load_transitions()

    # Compute current phase for each packet
    phase_counts: dict[str, int] = {}
    for p in packets:
        transitions = [t for t in all_transitions if t["packet_id"] == p.id]
        current_phase = transitions[-1]["to"] if transitions else p.phase.value
        phase_counts[current_phase] = phase_counts.get(current_phase, 0) + 1

    # Dispatch status counts
    status_counts: dict[str, int] = {}
    for d in all_dispatches:
        status_counts[d.status.value] = status_counts.get(d.status.value, 0) + 1

    # Backend counts
    backend_counts: dict[str, int] = {}
    for d in all_dispatches:
        backend_counts[d.backend] = backend_counts.get(d.backend, 0) + 1

    # Derive summary categorization
    active_statuses = {DispatchStatus.DISPATCHED, DispatchStatus.IN_PROGRESS}
    completed_statuses = {DispatchStatus.FORTIFIED, DispatchStatus.MERGED}
    failed_statuses = {DispatchStatus.REJECTED, DispatchStatus.TIMED_OUT}

    active = sum(1 for d in all_dispatches if d.status in active_statuses)
    completed = sum(1 for d in all_dispatches if d.status in completed_statuses)
    failed = sum(1 for d in all_dispatches if d.status in failed_statuses)
    pending_review = sum(
        1 for d in all_dispatches if d.status == DispatchStatus.DRAFT_RETURNED
    )

    return {
        "total_packets": len(packets),
        "total_intents": len(all_intents),
        "total_dispatches": len(all_dispatches),
        "total_transitions": len(all_transitions),
        "by_phase": phase_counts,
        "by_dispatch_status": status_counts,
        "by_backend": backend_counts,
        "summary": {
            "active": active,
            "completed": completed,
            "failed": failed,
            "pending_review": pending_review,
        },
    }
