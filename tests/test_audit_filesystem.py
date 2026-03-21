"""Tests for audit filesystem layer."""

from organvm_engine.audit.filesystem import audit_filesystem
from organvm_engine.audit.types import Severity


def _mini_registry(organ_key, repos):
    """Build a minimal registry with one organ."""
    return {
        "organs": {
            organ_key: {
                "name": "Test",
                "repositories": [
                    {"name": r, "org": "test-org", "implementation_status": "ACTIVE"}
                    for r in repos
                ],
            },
        },
    }


class TestFilesystemAudit:
    def test_repo_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        repo_dir = ws / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / ".git").mkdir()
        (repo_dir / "seed.yaml").write_text("repo: my-repo")

        registry = _mini_registry("ORGAN-I", ["my-repo"])
        report = audit_filesystem(registry, ws)

        # No critical or warning findings for this repo
        repo_findings = [f for f in report.findings if f.repo == "my-repo"]
        assert all(f.severity == Severity.INFO for f in repo_findings)

    def test_missing_repo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        (ws / "organ-i").mkdir()

        registry = _mini_registry("ORGAN-I", ["missing-repo"])
        report = audit_filesystem(registry, ws)

        crits = [f for f in report.findings if f.severity == Severity.CRITICAL]
        assert any("not on disk" in f.message for f in crits)

    def test_missing_organ_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        # Don't create organ-i directory

        registry = _mini_registry("ORGAN-I", ["some-repo"])
        report = audit_filesystem(registry, ws)

        crits = [f for f in report.findings if f.severity == Severity.CRITICAL]
        assert any("does not exist" in f.message for f in crits)

    def test_no_git_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        repo_dir = ws / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        # No .git directory

        registry = _mini_registry("ORGAN-I", ["my-repo"])
        report = audit_filesystem(registry, ws)

        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("no .git" in f.message.lower() for f in warns)

    def test_no_seed_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        repo_dir = ws / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / ".git").mkdir()
        # No seed.yaml

        registry = _mini_registry("ORGAN-I", ["my-repo"])
        report = audit_filesystem(registry, ws)

        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("seed.yaml" in f.message.lower() for f in warns)

    def test_orphan_detection(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        (ws / "organ-i" / "registered-repo").mkdir(parents=True)
        (ws / "organ-i" / "orphan-dir").mkdir(parents=True)

        registry = _mini_registry("ORGAN-I", ["registered-repo"])
        report = audit_filesystem(registry, ws)

        infos = [f for f in report.findings if f.severity == Severity.INFO]
        assert any("orphan-dir" in f.message for f in infos)

    def test_hidden_dirs_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        (ws / "organ-i" / ".hidden").mkdir(parents=True)
        (ws / "organ-i" / "node_modules").mkdir(parents=True)

        registry = _mini_registry("ORGAN-I", [])
        report = audit_filesystem(registry, ws)

        # No orphan findings for hidden dirs
        orphan_names = [f.repo for f in report.findings if "not in registry" in f.message]
        assert ".hidden" not in orphan_names
        assert "node_modules" not in orphan_names

    def test_scope_organ_filter(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i", "ORGAN-II": "organ-ii"},
        )
        ws = tmp_path
        (ws / "organ-i").mkdir()
        (ws / "organ-ii").mkdir()

        registry = {
            "organs": {
                "ORGAN-I": {
                    "name": "I",
                    "repositories": [{"name": "r1", "org": "o1", "implementation_status": "ACTIVE"}],
                },
                "ORGAN-II": {
                    "name": "II",
                    "repositories": [{"name": "r2", "org": "o2", "implementation_status": "ACTIVE"}],
                },
            },
        }
        report = audit_filesystem(registry, ws, scope_organ="ORGAN-I")

        # Should only have findings about ORGAN-I
        for f in report.findings:
            assert f.organ != "ORGAN-II"
