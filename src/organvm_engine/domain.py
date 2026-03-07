"""Shared domain fingerprinting for atomic units.

Provides content-based identity that links tasks and prompts by the files
they touch and the technologies they reference, regardless of directory origin.
"""

from __future__ import annotations

import hashlib


def domain_fingerprint(tags: list[str], file_refs: list[str]) -> str:
    """SHA256[:16] of normalized tags + file_refs.

    Produces a stable 16-char hex digest that identifies the "domain" of
    an atomic unit based on its content DNA rather than its file path.
    """
    normalized = sorted(set(t.lower() for t in tags)) + sorted(set(file_refs))
    raw = "|".join(normalized)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def domain_set(tags: list[str], file_refs: list[str]) -> set[str]:
    """Build prefixed set for Jaccard comparison.

    Returns items like {tag:python, ref:src/foo.py, ...} so that tags
    and file refs occupy the same similarity space without collisions.
    """
    items: set[str] = set()
    for t in tags:
        items.add(f"tag:{t.lower()}")
    for f in file_refs:
        items.add(f"ref:{f}")
    return items
