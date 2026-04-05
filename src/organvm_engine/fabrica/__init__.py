"""Cyclic Dispatch Protocol — RELEASE → CATCH → HANDOFF → FORTIFY.

The outer loop of the ORGANVM agent lifecycle (SPEC-024). Composes
dispatch, coordination, atoms, and irf into a four-phase cycle that
delays the degradation of ideal abstractions by inserting careful
expansion, exhaustive planning, agent-dispatched execution, and human
fortification between intention and realization.

Sister formation to praxis-perpetua: praxis is the knowledge of process;
fabrica is the machinery that enacts it.
"""

from organvm_engine.fabrica.models import (  # noqa: F401
    ApproachVector,
    DispatchRecord,
    DispatchStatus,
    RelayIntent,
    RelayPacket,
    RelayPhase,
)
from organvm_engine.fabrica.state import (  # noqa: F401
    PHASE_TRANSITIONS,
    valid_transition,
)

__all__ = [
    "ApproachVector",
    "DispatchRecord",
    "DispatchStatus",
    "RelayIntent",
    "RelayPacket",
    "RelayPhase",
    "PHASE_TRANSITIONS",
    "valid_transition",
]
