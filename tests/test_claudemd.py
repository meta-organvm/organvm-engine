"""Tests for CLAUDE.md generator and sync."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from organvm_engine.claudemd.generator import (
    generate_repo_section,
    generate_organ_section,
    generate_workspace_section,
)
from organvm_engine.claudemd.sync import sync_all, sync_repo


@pytest.fixture
def mock_registry():
    return {
        "organs": {
            "ORGAN-I": {
                "name": "Theory",
                "organization": "organvm-i-theoria",
                "repositories": [
                    {"name": "repo-a", "tier": "flagship", "promotion_status": "GRADUATED"},
                    {"name": "repo-b", "tier": "standard", "promotion_status": "LOCAL"}
                ]
            }
        }
    }


class TestGenerator:
    def test_generate_repo_section(self, mock_registry):
        seed = {"repo": "repo-a", "produces": [{"target": "repo-b", "artifact": "docs"}]}
        section = generate_repo_section("repo-a", "organvm-i-theoria", mock_registry, seed)
        assert "## System Context" in section
        assert "**Organ:** ORGAN-I" in section
        assert "Produces" in section
        assert "repo-b" in section

    def test_generate_organ_section(self, mock_registry):
        section = generate_organ_section("ORGAN-I", mock_registry, [])
        assert "## Organ Map" in section
        assert "2 repos" in section
        assert "1 flagship" in section

    def test_generate_workspace_section(self, mock_registry):
        section = generate_workspace_section(mock_registry, [])
        assert "## System Overview" in section
        assert "2 repos" in section
        assert "ORGAN-I" in section


class TestSync:
    @patch("organvm_engine.claudemd.sync._inject_section")
    def test_sync_repo(self, mock_inject, mock_registry):
        mock_inject.return_value = "updated"
        res = sync_repo(Path("/tmp"), "repo-a", "org", mock_registry)
        assert res["action"] == "updated"
        assert "CLAUDE.md" in res["path"]
