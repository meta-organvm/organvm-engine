"""Tests for the contextmd module (context file generation and sync)."""

from pathlib import Path

import pytest

from organvm_engine.contextmd import AUTO_START, AUTO_END
from organvm_engine.contextmd.sync import _inject_section, sync_repo
from organvm_engine.contextmd.generator import (
    generate_repo_section,
    generate_organ_section,
    generate_workspace_section,
    _read_omega_counts,
)
from organvm_engine.registry.loader import load_registry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def registry():
    return load_registry(FIXTURES / "registry-minimal.json")


class TestInjectSection:
    def test_creates_new_file(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        action = _inject_section(target, "## Generated\nContent here")
        assert action == "created"
        assert target.read_text() == "## Generated\nContent here\n"

    def test_replaces_existing_markers(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text(
            "# My Project\n\n"
            f"{AUTO_START}\n## Old Section\n{AUTO_END}\n\n"
            "## Manual Section\n"
        )
        new_section = f"{AUTO_START}\n## New Section\n{AUTO_END}"
        action = _inject_section(target, new_section)
        assert action == "updated"
        content = target.read_text()
        assert "## New Section" in content
        assert "## Old Section" not in content
        assert "## Manual Section" in content

    def test_appends_when_no_markers(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        target.write_text("# My Project\n\nSome content.")
        new_section = f"{AUTO_START}\n## Generated\n{AUTO_END}"
        action = _inject_section(target, new_section)
        assert action == "updated"
        content = target.read_text()
        assert content.startswith("# My Project")
        assert AUTO_START in content

    def test_unchanged_when_same_content(self, tmp_path):
        section = f"{AUTO_START}\n## Same\n{AUTO_END}"
        target = tmp_path / "CLAUDE.md"
        target.write_text(f"# Title\n\n{section}\n")
        action = _inject_section(target, section)
        assert action == "unchanged"

    def test_dry_run_does_not_write(self, tmp_path):
        target = tmp_path / "CLAUDE.md"
        action = _inject_section(target, "## Content", dry_run=True)
        assert action == "created"
        assert not target.exists()


class TestGenerateRepoSection:
    def test_generates_valid_section(self, registry):
        section = generate_repo_section("recursive-engine", "organvm-i-theoria", registry)
        assert AUTO_START in section
        assert AUTO_END in section
        assert "ORGAN-I" in section
        assert "flagship" in section
        assert "recursive-engine" in section

    def test_returns_error_for_missing_repo(self, registry):
        section = generate_repo_section("nonexistent", "org", registry)
        assert "ERROR" in section

    def test_includes_siblings(self, registry):
        section = generate_repo_section("recursive-engine", "organvm-i-theoria", registry)
        assert "ontological-framework" in section

    def test_includes_seed_edges(self, registry):
        seed = {
            "produces": [{"target": "repo-b", "artifact": "data"}],
            "consumes": [{"source": "meta-organvm/schema-definitions", "artifact": "schemas"}],
        }
        section = generate_repo_section("recursive-engine", "organvm-i-theoria", registry, seed)
        assert "Produces" in section
        assert "Consumes" in section


class TestGenerateOrganSection:
    def test_generates_valid_organ_section(self, registry):
        section = generate_organ_section("ORGAN-I", registry)
        assert AUTO_START in section
        assert "Theory" in section
        assert "recursive-engine" in section

    def test_returns_error_for_missing_organ(self, registry):
        section = generate_organ_section("ORGAN-IX", registry)
        assert "ERROR" in section


class TestGenerateWorkspaceSection:
    def test_generates_valid_workspace_section(self, registry):
        section = generate_workspace_section(registry, seeds=[{}, {}, {}])
        assert AUTO_START in section
        assert "repos" in section
        assert "organs" in section

    def test_seed_coverage_reflects_count(self, registry):
        section = generate_workspace_section(registry, seeds=[{}, {}])
        assert "2/6" in section  # 2 seeds, 6 repos in fixture


class TestReadOmegaCounts:
    def test_reads_from_evidence_map(self, tmp_path, monkeypatch):
        evidence = tmp_path / "docs" / "evaluation" / "omega-evidence-map.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text(
            "## Summary\n\n"
            "| Status | Count | Criteria |\n"
            "|--------|-------|----------|\n"
            "| MET | 3 | #1, #2, #3 |\n"
            "| IN PROGRESS | 5 | #4-#8 |\n"
            "| NOT STARTED | 9 | #9-#17 |\n"
        )
        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path,
        )
        met, total = _read_omega_counts()
        assert met == 3
        assert total == 17

    def test_fallback_on_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.paths.corpus_dir",
            lambda: tmp_path,
        )
        met, total = _read_omega_counts()
        assert met == 0
        assert total == 17


class TestSyncRepo:
    def test_sync_creates_file(self, tmp_path, registry):
        repo_path = tmp_path / "recursive-engine"
        repo_path.mkdir()
        result = sync_repo(repo_path, "recursive-engine", "organvm-i-theoria", registry)
        assert result["action"] == "created"
        content = (repo_path / "CLAUDE.md").read_text()
        assert AUTO_START in content
        assert "recursive-engine" in content

    def test_sync_updates_existing(self, tmp_path, registry):
        repo_path = tmp_path / "recursive-engine"
        repo_path.mkdir()
        claude_md = repo_path / "CLAUDE.md"
        claude_md.write_text(
            f"# My Repo\n\n{AUTO_START}\n## Old\n{AUTO_END}\n\n## Keep This\n"
        )
        result = sync_repo(repo_path, "recursive-engine", "organvm-i-theoria", registry)
        assert result["action"] == "updated"
        content = claude_md.read_text()
        assert "## Keep This" in content
        assert "## Old" not in content
