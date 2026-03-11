"""Tests for audit seeds layer."""

from organvm_engine.audit.seeds import audit_seeds
from organvm_engine.audit.types import Severity


def _setup_seeds(tmp_path, monkeypatch, seeds, flagships=None):
    """Create seed files and patch discovery."""
    ws = tmp_path
    paths = []
    for organ_dir, repo_name, content in seeds:
        repo_dir = ws / organ_dir / repo_name
        repo_dir.mkdir(parents=True, exist_ok=True)
        seed_file = repo_dir / "seed.yaml"
        seed_file.write_text(content)
        paths.append(seed_file)

    monkeypatch.setattr(
        "organvm_engine.audit.seeds.registry_key_to_dir",
        lambda: {"ORGAN-I": "organ-i"},
    )
    monkeypatch.setattr(
        "organvm_engine.audit.seeds.discover_seeds",
        lambda workspace: paths,
    )

    # Build registry with flagships
    repos = []
    for _, repo_name, _ in seeds:
        tier = "flagship" if flagships and repo_name in flagships else "standard"
        repos.append({"name": repo_name, "org": "org", "tier": tier})

    registry = {"organs": {"ORGAN-I": {"name": "I", "repositories": repos}}}
    return ws, registry


class TestSeedsAudit:
    def test_complete_seed(self, tmp_path, monkeypatch):
        ws, registry = _setup_seeds(tmp_path, monkeypatch, [
            ("organ-i", "good-repo", (
                "repo: good-repo\norgan: ORGAN-I\ntier: standard\n"
                "description: A good repo"
            )),
        ])
        report = audit_seeds(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert len(warns) == 0

    def test_missing_required_field(self, tmp_path, monkeypatch):
        ws, registry = _setup_seeds(tmp_path, monkeypatch, [
            ("organ-i", "no-tier", "repo: no-tier\norgan: ORGAN-I"),
        ])
        report = audit_seeds(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("tier" in f.message for f in warns)

    def test_identity_mismatch(self, tmp_path, monkeypatch):
        ws, registry = _setup_seeds(tmp_path, monkeypatch, [
            ("organ-i", "actual-dir", (
                "repo: different-name\norgan: ORGAN-I\ntier: standard"
            )),
        ])
        report = audit_seeds(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("directory" in f.message.lower() for f in warns)

    def test_flagship_no_edges(self, tmp_path, monkeypatch):
        ws, registry = _setup_seeds(
            tmp_path, monkeypatch,
            [("organ-i", "flagship-repo", (
                "repo: flagship-repo\norgan: ORGAN-I\ntier: flagship"
            ))],
            flagships={"flagship-repo"},
        )
        report = audit_seeds(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("produces/consumes" in f.message for f in warns)

    def test_flagship_with_edges(self, tmp_path, monkeypatch):
        ws, registry = _setup_seeds(
            tmp_path, monkeypatch,
            [("organ-i", "flagship-repo", (
                "repo: flagship-repo\norgan: ORGAN-I\ntier: flagship\n"
                "produces:\n  - type: api\nconsumes:\n  - type: data"
            ))],
            flagships={"flagship-repo"},
        )
        report = audit_seeds(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        # No warning about missing edges
        assert not any("produces/consumes" in f.message for f in warns)

    def test_malformed_seed(self, tmp_path, monkeypatch):
        ws, registry = _setup_seeds(tmp_path, monkeypatch, [
            ("organ-i", "broken", "- this\n- is\n- a list\n- not a mapping"),
        ])
        report = audit_seeds(registry, ws)
        crits = [f for f in report.findings if f.severity == Severity.CRITICAL]
        assert any("cannot parse" in f.message.lower() for f in crits)
