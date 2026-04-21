"""Execution mode determination for institutional primitives.

Standalone function usable outside a primitive instance — e.g. by the
composition engine to pre-check mode before wiring.

Rules from SPEC-025 Section 3:
  - conf >= 0.8 AND stakes <= routine  →  AI_PERFORMED
  - 0.5 <= conf < 0.8 OR significant  →  AI_PREPARED_HUMAN_REVIEWED
  - conf < 0.5 OR critical            →  HUMAN_ROUTED
  - deterministic operation            →  PROTOCOL_STRUCTURED
"""

from __future__ import annotations

from organvm_engine.primitives.types import ExecutionMode, StakesLevel


def mode_for_invocation(
    confidence: float,
    stakes: StakesLevel,
    *,
    is_deterministic: bool = False,
) -> ExecutionMode:
    """Determine execution mode for a single invocation."""
    if is_deterministic:
        return ExecutionMode.PROTOCOL_STRUCTURED
    if stakes == StakesLevel.CRITICAL or confidence < 0.5:
        return ExecutionMode.HUMAN_ROUTED
    if stakes == StakesLevel.SIGNIFICANT or confidence < 0.8:
        return ExecutionMode.AI_PREPARED_HUMAN_REVIEWED
    return ExecutionMode.AI_PERFORMED
