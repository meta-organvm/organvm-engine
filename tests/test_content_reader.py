"""Tests for content pipeline reader."""

from __future__ import annotations

from pathlib import Path

from organvm_engine.paths import PathConfig


def test_content_dir_resolves_relative_to_corpus(tmp_path: Path):
    """content_dir should be corpus parent / praxis-perpetua / content-pipeline / posts."""
    corpus = tmp_path / "organvm-corpvs-testamentvm"
    corpus.mkdir()
    cfg = PathConfig(corpus_root=corpus)
    expected = tmp_path / "praxis-perpetua" / "content-pipeline" / "posts"
    assert cfg.content_dir() == expected
