"""Tests for audit coordinator."""

from organvm_engine.audit.coordinator import run_audit


def _mini_registry():
    return {
        "organs": {
            "ORGAN-I": {
                "name": "I",
                "repositories": [
                    {"name": "repo-a", "org": "org-i", "implementation_status": "ACTIVE"},
                ],
            },
        },
    }


class TestCoordinator:
    def test_runs_single_layer(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        (ws / "organ-i").mkdir()

        report = run_audit(_mini_registry(), ws, layers=["filesystem"])
        assert "filesystem" in report.layers
        assert "reconcile" not in report.layers

    def test_runs_all_layers(self, tmp_path, monkeypatch):
        # Patch everything needed for all layers
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        monkeypatch.setattr(
            "organvm_engine.audit.reconcile.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        monkeypatch.setattr(
            "organvm_engine.audit.reconcile.discover_seeds",
            lambda workspace: [],
        )
        monkeypatch.setattr(
            "organvm_engine.audit.seeds.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        monkeypatch.setattr(
            "organvm_engine.audit.seeds.discover_seeds",
            lambda workspace: [],
        )
        monkeypatch.setattr(
            "organvm_engine.audit.content.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        from organvm_engine.seed.graph import SeedGraph
        monkeypatch.setattr(
            "organvm_engine.audit.edges.build_seed_graph",
            lambda workspace: SeedGraph(),
        )
        monkeypatch.setattr(
            "organvm_engine.audit.edges.validate_edge_resolution",
            lambda g: [],
        )
        monkeypatch.setattr(
            "organvm_engine.audit.absorption._DEPOSIT_SPECS",
            [],
        )

        ws = tmp_path
        (ws / "organ-i").mkdir()

        report = run_audit(_mini_registry(), ws)
        assert len(report.layers) == 6

    def test_scope_organ(self, tmp_path, monkeypatch):
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
                    "repositories": [{"name": "r1", "org": "o"}],
                },
                "ORGAN-II": {
                    "name": "II",
                    "repositories": [{"name": "r2", "org": "o"}],
                },
            },
        }

        report = run_audit(registry, ws, scope_organ="ORGAN-I", layers=["filesystem"])
        for f in report.all_findings:
            assert f.organ != "ORGAN-II"

    def test_scope_repo_filters(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        ws = tmp_path
        (ws / "organ-i").mkdir()

        registry = {
            "organs": {
                "ORGAN-I": {
                    "name": "I",
                    "repositories": [
                        {"name": "target", "org": "o", "implementation_status": "ACTIVE"},
                        {"name": "other", "org": "o", "implementation_status": "ACTIVE"},
                    ],
                },
            },
        }

        report = run_audit(registry, ws, scope_repo="target", layers=["filesystem"])
        for f in report.all_findings:
            # Should be target or system-level (empty repo)
            assert f.repo in ("target", "")

    def test_invalid_layer_ignored(self, tmp_path):
        report = run_audit(_mini_registry(), tmp_path, layers=["nonexistent"])
        assert len(report.layers) == 0

    def test_report_to_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.filesystem.registry_key_to_dir",
            lambda: {"ORGAN-I": "organ-i"},
        )
        (tmp_path / "organ-i").mkdir()

        report = run_audit(_mini_registry(), tmp_path, layers=["filesystem"])
        d = report.to_dict()
        assert "summary" in d
        assert "layers" in d
        assert isinstance(d["summary"]["total_findings"], int)
