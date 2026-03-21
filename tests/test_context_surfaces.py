"""Tests for conversation corpus surface discovery and CLI output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from organvm_engine.cli.context import cmd_context_surfaces
from organvm_engine.contextmd.surfaces import collect_conversation_corpus_surfaces
from organvm_engine.paths import PathConfig


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _bootstrap_surface_workspace(tmp_path: Path) -> Path:
    schemas_dir = tmp_path / "meta-organvm" / "schema-definitions" / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    schema_payloads = {
        "conversation-corpus-surface-manifest.schema.json": {
            "type": "object",
            "required": ["contract_name", "registry"],
            "properties": {
                "contract_name": {
                    "const": "conversation-corpus-engine-surface-manifest-v1",
                },
                "registry": {"type": "object"},
            },
        },
        "conversation-corpus-mcp-context.schema.json": {
            "type": "object",
            "required": ["contract_name", "summary", "providers"],
            "properties": {
                "contract_name": {
                    "const": "conversation-corpus-engine-mcp-context-v1",
                },
                "summary": {"type": "object"},
                "providers": {"type": "array"},
            },
        },
        "conversation-corpus-surface-bundle.schema.json": {
            "type": "object",
            "required": ["contract_name", "summary", "manifest", "context"],
            "properties": {
                "contract_name": {
                    "const": "conversation-corpus-engine-surface-bundle-v1",
                },
                "summary": {"type": "object"},
                "manifest": {"type": "object"},
                "context": {"type": "object"},
            },
        },
    }
    for name, payload in schema_payloads.items():
        _write_json(schemas_dir / name, payload)

    repo_root = tmp_path / "organvm-i-theoria" / "conversation-corpus-engine"
    surface_dir = repo_root / "reports" / "surfaces"

    _write_json(
        surface_dir / "surface-manifest.json",
        {
            "contract_name": "conversation-corpus-engine-surface-manifest-v1",
            "registry": {
                "default_corpus_id": "claude-main",
                "corpus_count": 1,
                "active_corpus_count": 1,
            },
        },
    )
    _write_json(
        surface_dir / "mcp-context.json",
        {
            "contract_name": "conversation-corpus-engine-mcp-context-v1",
            "summary": {
                "registered_corpus_count": 1,
                "active_corpus_count": 1,
                "provider_count": 1,
                "healthy_provider_count": 1,
                "open_review_count": 0,
            },
            "registry": {"default_corpus_id": "claude-main"},
            "providers": [{"provider": "claude"}],
        },
    )
    _write_json(
        surface_dir / "surface-bundle.json",
        {
            "contract_name": "conversation-corpus-engine-surface-bundle-v1",
            "summary": {"valid": True, "error_count": 0},
            "manifest": {"path": str(surface_dir / "surface-manifest.json")},
            "context": {"path": str(surface_dir / "mcp-context.json")},
        },
    )
    return repo_root


class TestConversationCorpusSurfaces:
    def test_collect_surfaces_discovers_valid_bundle(self, tmp_path):
        repo_root = _bootstrap_surface_workspace(tmp_path)

        report = collect_conversation_corpus_surfaces(config=PathConfig(workspace_dir=tmp_path))

        assert report["surface_count"] == 1
        assert report["valid_count"] == 1
        assert report["invalid_count"] == 0
        surface = report["surfaces"][0]
        assert surface["repo"] == "conversation-corpus-engine"
        assert surface["organization"] == "organvm-i-theoria"
        assert surface["state"] == "valid"
        assert surface["repo_root"] == str(repo_root.resolve())
        assert surface["summary"]["default_corpus_id"] == "claude-main"
        assert surface["summary"]["provider_count"] == 1
        assert surface["summary"]["provider_names"] == ["claude"]
        assert surface["validation"]["bundle"]["valid"] is True

    def test_collect_surfaces_filters_by_repo(self, tmp_path):
        _bootstrap_surface_workspace(tmp_path)

        report = collect_conversation_corpus_surfaces(
            config=PathConfig(workspace_dir=tmp_path),
            repo="organvm-i-theoria/conversation-corpus-engine",
        )

        assert report["surface_count"] == 1
        assert report["surfaces"][0]["repo"] == "conversation-corpus-engine"

    def test_collect_surfaces_marks_invalid_payload(self, tmp_path):
        repo_root = _bootstrap_surface_workspace(tmp_path)
        _write_json(
            repo_root / "reports" / "surfaces" / "mcp-context.json",
            {
                "contract_name": "invalid-contract",
                "summary": {"provider_count": 1},
                "providers": [],
            },
        )

        report = collect_conversation_corpus_surfaces(config=PathConfig(workspace_dir=tmp_path))

        assert report["surface_count"] == 1
        assert report["invalid_count"] == 1
        validation = report["surfaces"][0]["validation"]["context"]
        assert validation["valid"] is False
        assert any("conversation-corpus-engine-mcp-context-v1" in error for error in validation["errors"])


class TestContextSurfaceCli:
    def test_cmd_context_surfaces_json(self, tmp_path, capsys):
        _bootstrap_surface_workspace(tmp_path)
        args = argparse.Namespace(workspace=str(tmp_path), repo=None, json=True)

        rc = cmd_context_surfaces(args)

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["surface_count"] == 1
        assert payload["surfaces"][0]["summary"]["provider_count"] == 1

    def test_cmd_context_surfaces_text(self, tmp_path, capsys):
        _bootstrap_surface_workspace(tmp_path)
        args = argparse.Namespace(workspace=str(tmp_path), repo=None, json=False)

        rc = cmd_context_surfaces(args)

        assert rc == 0
        output = capsys.readouterr().out
        assert "Conversation Corpus Surfaces" in output
        assert "conversation-corpus-engine [valid]" in output
