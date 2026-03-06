"""Tests for workspace path resolution."""

from pathlib import Path

from organvm_engine import paths


class TestPaths:
    def test_workspace_root_uses_blocked_default(self, monkeypatch):
        # autouse fixture sets _DEFAULT_WORKSPACE to /nonexistent/...
        # Clear env var so the blocked default is actually used
        monkeypatch.delenv("ORGANVM_WORKSPACE_DIR", raising=False)
        result = paths.workspace_root()
        assert "nonexistent" in str(result)

    def test_workspace_root_env_override(self, monkeypatch):
        monkeypatch.setenv("ORGANVM_WORKSPACE_DIR", "/tmp/test-workspace")
        assert paths.workspace_root() == Path("/tmp/test-workspace")

    def test_corpus_dir_default(self):
        result = paths.corpus_dir()
        assert str(result).endswith("meta-organvm/organvm-corpvs-testamentvm")

    def test_corpus_dir_env_override(self, monkeypatch):
        monkeypatch.setenv("ORGANVM_CORPUS_DIR", "/tmp/test-corpus")
        assert paths.corpus_dir() == Path("/tmp/test-corpus")

    def test_registry_path(self):
        result = paths.registry_path()
        assert result.name == "registry-v2.json"
        assert "organvm-corpvs-testamentvm" in str(result)

    def test_governance_rules_path(self):
        result = paths.governance_rules_path()
        assert result.name == "governance-rules.json"

    def test_soak_dir(self):
        result = paths.soak_dir()
        assert result.name == "soak-test"
        assert "data" in str(result)
