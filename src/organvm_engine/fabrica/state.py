"""Phase transition logic for the Cyclic Dispatch Protocol (SPEC-024).

The state machine enforces hard phase gates. No phase may be skipped.
The only backward transitions originate from FORTIFY.
"""

from __future__ import annotations

from organvm_engine.fabrica.models import RelayPhase

# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------

PHASE_TRANSITIONS: dict[RelayPhase, set[RelayPhase]] = {
    RelayPhase.RELEASE: {RelayPhase.CATCH},
    RelayPhase.CATCH: {RelayPhase.HANDOFF},
    RelayPhase.HANDOFF: {RelayPhase.FORTIFY},
    RelayPhase.FORTIFY: {
        RelayPhase.COMPLETE,  # all artifacts approved
        RelayPhase.CATCH,     # review revealed new questions
        RelayPhase.HANDOFF,   # approach correct, execution incomplete
    },
    RelayPhase.COMPLETE: {RelayPhase.RELEASE},  # new cycle
}


def valid_transition(current: RelayPhase, target: RelayPhase) -> bool:
    """Return True if *target* is a valid successor of *current*."""
    return target in PHASE_TRANSITIONS.get(current, set())


def advance(current: RelayPhase) -> RelayPhase | None:
    """Return the single forward phase, or None if ambiguous/terminal.

    Only works for phases with exactly one successor (RELEASE, CATCH,
    HANDOFF). FORTIFY and COMPLETE have multiple/conditional successors
    and require explicit target selection via ``valid_transition``.
    """
    successors = PHASE_TRANSITIONS.get(current, set())
    if len(successors) == 1:
        return next(iter(successors))
    return None


def is_terminal(phase: RelayPhase) -> bool:
    """Return True if the phase has no successors (never true in a cycle)."""
    return not PHASE_TRANSITIONS.get(phase, set())


def is_backward(current: RelayPhase, target: RelayPhase) -> bool:
    """Return True if the transition is a backward move (re-cycle)."""
    order = list(RelayPhase)
    return order.index(target) < order.index(current)
