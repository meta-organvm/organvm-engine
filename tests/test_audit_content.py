"""Tests for audit content layer."""

from organvm_engine.audit.content import audit_content
from organvm_engine.audit.types import Severity


def _registry_with_repo(name, ci_workflow="", platinum=False, tier="standard"):
    return {
        "organs": {
            "ORGAN-I": {
                "name": "I",
                "repositories": [
                    {
                        "name": name,
                        "org": "org-i",
                        "implementation_status": "ACTIVE",
                        "ci_workflow": ci_workflow,
                        "platinum_status": platinum,
                        "tier": tier,
                    },
                ],
            },
        },
    }


class TestContentAudit:
    def test_readme_present(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Hello")

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo")
        report = audit_content(registry, tmp_path)

        warns = [f for f in report.findings if f.repo == "my-repo" and f.severity == Severity.WARNING]
        assert not any("readme" in f.message.lower() for f in warns)

    def test_readme_missing(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo")
        report = audit_content(registry, tmp_path)

        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("readme" in f.message.lower() for f in warns)

    def test_ci_drift_registry_says_yes_disk_says_no(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Hi")

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo", ci_workflow="ci.yml")
        report = audit_content(registry, tmp_path)

        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("registry claims ci" in f.message.lower() for f in warns)

    def test_ci_drift_disk_says_yes_registry_says_no(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Hi")
        ci_dir = repo_dir / ".github" / "workflows"
        ci_dir.mkdir(parents=True)
        (ci_dir / "build.yml").write_text("name: build")

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo", ci_workflow="")
        report = audit_content(registry, tmp_path)

        infos = [f for f in report.findings if f.severity == Severity.INFO]
        assert any("ci workflows on disk" in f.message.lower() for f in infos)

    def test_platinum_no_changelog(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Hi")

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo", platinum=True)
        report = audit_content(registry, tmp_path)

        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("changelog" in f.message.lower() for f in warns)

    def test_platinum_with_changelog(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Hi")
        (repo_dir / "CHANGELOG.md").write_text("# Changelog")

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo", platinum=True)
        report = audit_content(registry, tmp_path)

        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert not any("changelog" in f.message.lower() for f in warns)

    def test_flagship_no_docs(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "my-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "README.md").write_text("# Hi")

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = _registry_with_repo("my-repo", tier="flagship")
        report = audit_content(registry, tmp_path)

        infos = [f for f in report.findings if f.severity == Severity.INFO]
        assert any("docs/" in f.message.lower() for f in infos)

    def test_archived_repos_skipped(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "organ-i" / "archived-repo"
        repo_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        registry = {
            "organs": {
                "ORGAN-I": {
                    "name": "I",
                    "repositories": [{
                        "name": "archived-repo",
                        "org": "org",
                        "implementation_status": "ARCHIVED",
                    }],
                },
            },
        }
        report = audit_content(registry, tmp_path)
        assert not any(f.repo == "archived-repo" for f in report.findings)
