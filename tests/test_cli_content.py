"""CLI smoke tests for organvm content commands."""

from __future__ import annotations

from pathlib import Path

import yaml

import organvm_engine.paths as paths_mod
from organvm_engine.cli import build_parser


def _setup_content_dir(tmp_path: Path) -> Path:
    """Create a content dir with one post.

    Path structure must match content_dir() resolution:
    workspace / meta-organvm / organvm-corpvs-testamentvm -> corpus_dir
    workspace / meta-organvm / praxis-perpetua / content-pipeline / posts -> content_dir
    """
    meta_org = tmp_path / "meta-organvm"
    corpus = meta_org / "organvm-corpvs-testamentvm"
    corpus.mkdir(parents=True)
    content_dir = meta_org / "praxis-perpetua" / "content-pipeline" / "posts"
    content_dir.mkdir(parents=True)
    post_dir = content_dir / "2026-03-19-test-post"
    post_dir.mkdir()
    meta = {
        "title": "Test Post",
        "date": "2026-03-19",
        "slug": "test-post",
        "hook": "The test hook",
        "source_session": "",
        "context": "",
        "status": "draft",
        "distribution": {"linkedin": {"posted": False}},
        "engagement": {},
        "tags": ["test"],
        "redacted_items": [],
    }
    (post_dir / "meta.yaml").write_text(yaml.dump(meta))
    return tmp_path


def test_content_list_returns_zero(tmp_path: Path, monkeypatch):
    _setup_content_dir(tmp_path)
    monkeypatch.setattr(paths_mod, "_DEFAULT_WORKSPACE", tmp_path)
    parser = build_parser()
    args = parser.parse_args(["content", "list"])
    from organvm_engine.cli.content import cmd_content_list
    result = cmd_content_list(args)
    assert result == 0


def test_content_status_returns_zero(tmp_path: Path, monkeypatch):
    _setup_content_dir(tmp_path)
    monkeypatch.setattr(paths_mod, "_DEFAULT_WORKSPACE", tmp_path)
    parser = build_parser()
    args = parser.parse_args(["content", "status"])
    from organvm_engine.cli.content import cmd_content_status
    result = cmd_content_status(args)
    assert result == 0


def test_content_new_dry_run(tmp_path: Path, monkeypatch):
    _setup_content_dir(tmp_path)
    monkeypatch.setattr(paths_mod, "_DEFAULT_WORKSPACE", tmp_path)
    parser = build_parser()
    args = parser.parse_args(["content", "new", "my-new-post", "--dry-run"])
    from organvm_engine.cli.content import cmd_content_new
    result = cmd_content_new(args)
    assert result == 0


def test_build_parser_has_content_command():
    parser = build_parser()
    args = parser.parse_args(["content", "list"])
    assert args.command == "content"
    assert args.subcommand == "list"


def test_build_parser_content_new_args():
    parser = build_parser()
    args = parser.parse_args(
        ["content", "new", "my-slug", "--title", "My Title", "--hook", "The hook"],
    )
    assert args.slug == "my-slug"
    assert args.title == "My Title"
    assert args.hook == "The hook"
