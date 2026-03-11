"""Infrastructure wiring audit — 6-layer bottom-up verification.

Validates that the ORGANVM system's declarations (registry, seeds, edges)
match what actually exists on the filesystem. Separate from governance
audit (policy compliance); this checks infrastructure wiring.
"""

AUDIT_LAYERS = ("filesystem", "reconcile", "seeds", "edges", "content", "absorption")
