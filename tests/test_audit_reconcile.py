"""Tests for audit reconcile layer."""

from organvm_engine.audit.reconcile import audit_reconcile
from organvm_engine.audit.types import Severity


def _make_workspace_with_seeds(tmp_path, monkeypatch, seeds):
    """Create a workspace with seed.yaml files and patch organ config.

    Args:
        seeds: list of (organ_dir, repo_name, seed_content) tuples.
    """
    ws = tmp_path
    dir_mapping = {}
    for organ_dir, repo_name, content in seeds:
        repo_dir = ws / organ_dir / repo_name
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "seed.yaml").write_text(content)
        # Build dir mapping: guess registry key
        dir_mapping[organ_dir] = organ_dir

    # Patch discover to use our tmp workspace
    monkeypatch.setattr(
        "organvm_engine.audit.reconcile.registry_key_to_dir",
        lambda: {v: k for k, v in dir_mapping.items()},
    )
    monkeypatch.setattr(
        "organvm_engine.audit.reconcile.discover_seeds",
        lambda workspace: [
            ws / organ_dir / repo_name / "seed.yaml"
            for organ_dir, repo_name, _ in seeds
        ],
    )
    return ws


class TestReconcile:
    def test_aligned(self, tmp_path, monkeypatch):
        ws = _make_workspace_with_seeds(tmp_path, monkeypatch, [
            ("organ-i", "repo-a", "repo: repo-a\norgan: organ-i\ntier: standard"),
        ])

        registry = {
            "organs": {
                "organ-i": {
                    "name": "I",
                    "repositories": [
                        {"name": "repo-a", "org": "org-a", "tier": "standard"},
                    ],
                }
            }
        }
        report = audit_reconcile(registry, ws)
        # No count mismatch, no missing entries
        crits = [f for f in report.findings if f.severity == Severity.CRITICAL]
        assert len(crits) == 0

    def test_count_mismatch(self, tmp_path, monkeypatch):
        ws = _make_workspace_with_seeds(tmp_path, monkeypatch, [
            ("organ-i", "repo-a", "repo: repo-a\norgan: organ-i\ntier: standard"),
            ("organ-i", "repo-b", "repo: repo-b\norgan: organ-i\ntier: standard"),
        ])

        registry = {
            "organs": {
                "organ-i": {
                    "name": "I",
                    "repositories": [
                        {"name": "repo-a", "org": "org-a"},
                    ],
                }
            }
        }
        report = audit_reconcile(registry, ws)
        msgs = [f.message for f in report.findings]
        assert any("delta" in m for m in msgs)

    def test_in_seed_not_registry(self, tmp_path, monkeypatch):
        ws = _make_workspace_with_seeds(tmp_path, monkeypatch, [
            ("organ-i", "orphan-seed", "repo: orphan-seed\norgan: organ-i\ntier: standard"),
        ])

        registry = {"organs": {"organ-i": {"name": "I", "repositories": []}}}
        report = audit_reconcile(registry, ws)
        crits = [f for f in report.findings if f.severity == Severity.CRITICAL]
        assert any("orphan-seed" in f.repo for f in crits)

    def test_in_registry_not_seed(self, tmp_path, monkeypatch):
        ws = _make_workspace_with_seeds(tmp_path, monkeypatch, [])

        registry = {
            "organs": {
                "organ-i": {
                    "name": "I",
                    "repositories": [{"name": "ghost-repo", "org": "org"}],
                }
            }
        }
        report = audit_reconcile(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("ghost-repo" in f.repo for f in warns)

    def test_tier_drift(self, tmp_path, monkeypatch):
        ws = _make_workspace_with_seeds(tmp_path, monkeypatch, [
            ("organ-i", "repo-a", "repo: repo-a\norgan: organ-i\ntier: flagship"),
        ])

        registry = {
            "organs": {
                "organ-i": {
                    "name": "I",
                    "repositories": [
                        {"name": "repo-a", "org": "org-a", "tier": "standard"},
                    ],
                }
            }
        }
        report = audit_reconcile(registry, ws)
        infos = [f for f in report.findings if f.severity == Severity.INFO]
        assert any("tier drift" in f.message.lower() for f in infos)

    def test_unparseable_seed(self, tmp_path, monkeypatch):
        ws = tmp_path
        repo_dir = ws / "organ-i" / "bad-repo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "seed.yaml").write_text("- this\n- is\n- a list")

        monkeypatch.setattr(
            "organvm_engine.audit.reconcile.registry_key_to_dir",
            lambda: {"organ-i": "organ-i"},
        )
        monkeypatch.setattr(
            "organvm_engine.audit.reconcile.discover_seeds",
            lambda workspace: [repo_dir / "seed.yaml"],
        )

        registry = {"organs": {"organ-i": {"name": "I", "repositories": []}}}
        report = audit_reconcile(registry, ws)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("cannot parse" in f.message.lower() for f in warns)
