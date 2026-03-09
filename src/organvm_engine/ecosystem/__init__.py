"""Product ecosystem discovery — per-product business ecosystem profiles.

Each product has an ecosystem.yaml alongside its seed.yaml, declaring
the full business ecosystem as a set of pillars (delivery, revenue,
marketing, community, content, listings, etc.) with per-arm status.
"""

ECOSYSTEM_FILENAME = "ecosystem.yaml"

# Header fields that are NOT pillars
HEADER_FIELDS = frozenset({"schema_version", "repo", "organ", "display_name"})
