"""Tests for atoms link summary generation."""

from __future__ import annotations

from organvm_engine.atoms.linker import AtomLink
from organvm_engine.atoms.summary import generate_link_summary


def test_empty_links():
    """Summary handles empty link list gracefully."""
    md = generate_link_summary([], threshold=0.15)
    assert "No links found" in md
    assert "**Links**: 0" in md


def test_basic_summary():
    """Summary includes Jaccard distribution and top tags."""
    links = [
        AtomLink("t1", "p1", 0.55, shared_tags=["python", "cli"], shared_refs=["src/main.py"]),
        AtomLink("t2", "p2", 0.32, shared_tags=["python"], shared_refs=[]),
        AtomLink("t3", "p3", 0.18, shared_tags=["docs"], shared_refs=["README.md"]),
    ]
    md = generate_link_summary(links, threshold=0.15)

    assert "**Links**: 3" in md
    assert "## Jaccard Distribution" in md
    assert "## Top Shared Tags" in md
    assert "python" in md
    assert "## Most-Linked Tasks" in md


def test_jaccard_buckets():
    """Summary correctly buckets Jaccard values."""
    links = [
        AtomLink("t1", "p1", 0.60, shared_tags=[], shared_refs=[]),
        AtomLink("t2", "p2", 0.45, shared_tags=[], shared_refs=[]),
        AtomLink("t3", "p3", 0.25, shared_tags=[], shared_refs=[]),
        AtomLink("t4", "p4", 0.16, shared_tags=[], shared_refs=[]),
    ]
    md = generate_link_summary(links, threshold=0.15)

    assert "0.50+" in md
    assert "0.30–0.49" in md
    assert "0.20–0.29" in md
    assert "0.15–0.19" in md


def test_shared_refs_section():
    """Summary includes shared file references when present."""
    links = [
        AtomLink("t1", "p1", 0.30, shared_tags=[], shared_refs=["src/a.py", "src/b.py"]),
    ]
    md = generate_link_summary(links, threshold=0.15)

    assert "## Top Shared File References" in md
    assert "`src/a.py`" in md


def test_no_tags_no_refs():
    """Summary handles links with no shared tags or refs."""
    links = [
        AtomLink("t1", "p1", 0.20, shared_tags=[], shared_refs=[]),
    ]
    md = generate_link_summary(links, threshold=0.15)

    # Should still have the Jaccard distribution and most-linked
    assert "## Jaccard Distribution" in md
    assert "## Most-Linked Tasks" in md
    # Should NOT have tags or refs sections
    assert "## Top Shared Tags" not in md
    assert "## Top Shared File References" not in md


def test_threshold_displayed():
    """Summary displays the threshold used."""
    md = generate_link_summary([], threshold=0.25)
    assert "**Threshold**: 0.25" in md
