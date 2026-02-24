"""Tests for the metrics module."""

import json
from pathlib import Path

import pytest

from organvm_engine.metrics.calculator import compute_metrics
from organvm_engine.metrics.propagator import (
    compute_vitals,
    compute_landing,
    copy_json_targets,
    transform_for_portfolio,
)
from organvm_engine.registry.loader import load_registry

FIXTURES = Path(__file__).parent / "fixtures"


def _make_canonical(registry):
    """Build a canonical system-metrics.json dict from a registry fixture."""
    computed = compute_metrics(registry)
    return {
        "schema_version": "1.0",
        "generated": "2026-02-24T12:00:00+00:00",
        "computed": computed,
        "manual": {
            "code_files": 100,
            "test_files": 20,
            "repos_with_tests": 5,
            "total_words_numeric": 404000,
            "total_words_short": "404K+",
        },
    }


class TestCalculator:
    def test_compute_totals(self, registry):
        m = compute_metrics(registry)
        assert m["total_repos"] == 6
        assert m["active_repos"] == 6
        assert m["total_organs"] == 4

    def test_per_organ_counts(self, registry):
        m = compute_metrics(registry)
        assert m["per_organ"]["ORGAN-I"]["repos"] == 2
        assert m["per_organ"]["ORGAN-II"]["repos"] == 1

    def test_ci_count(self, registry):
        m = compute_metrics(registry)
        # Only recursive-engine has ci_workflow in fixture
        assert m["ci_workflows"] == 1

    def test_dependency_count(self, registry):
        m = compute_metrics(registry)
        # recursive-engine has 0 deps, ontological has 1, metasystem has 1, product has 0
        assert m["dependency_edges"] == 2


class TestComputeVitals:
    def test_vitals_structure(self, registry):
        canonical = _make_canonical(registry)
        vitals = compute_vitals(canonical)
        assert "repos" in vitals
        assert "substance" in vitals
        assert "logos" in vitals
        assert "timestamp" in vitals

    def test_vitals_repos(self, registry):
        canonical = _make_canonical(registry)
        vitals = compute_vitals(canonical)
        assert vitals["repos"]["total"] == 6
        assert vitals["repos"]["active"] == 6
        assert vitals["repos"]["orgs"] == 4

    def test_vitals_substance_from_manual(self, registry):
        canonical = _make_canonical(registry)
        vitals = compute_vitals(canonical)
        assert vitals["substance"]["code_files"] == 100
        assert vitals["substance"]["test_files"] == 20

    def test_vitals_ci_coverage(self, registry):
        canonical = _make_canonical(registry)
        vitals = compute_vitals(canonical)
        # 1 CI workflow / 6 repos = 17%
        assert vitals["substance"]["ci_passing"] == 1
        assert vitals["substance"]["ci_coverage_pct"] == 17

    def test_vitals_logos(self, registry):
        canonical = _make_canonical(registry)
        vitals = compute_vitals(canonical)
        assert vitals["logos"]["words"] == 404000

    def test_vitals_zero_repos(self):
        canonical = {
            "computed": {
                "total_repos": 0,
                "active_repos": 0,
                "ci_workflows": 0,
                "total_organs": 0,
            },
            "manual": {},
        }
        vitals = compute_vitals(canonical)
        assert vitals["substance"]["ci_coverage_pct"] == 0


class TestComputeLanding:
    def test_landing_structure(self, registry):
        canonical = _make_canonical(registry)
        landing = compute_landing(canonical, registry, Path("/tmp/landing.json"))
        assert "title" in landing
        assert "tagline" in landing
        assert "metrics" in landing
        assert "organs" in landing
        assert "sprint_history" in landing
        assert "generated" in landing

    def test_landing_metrics(self, registry):
        canonical = _make_canonical(registry)
        landing = compute_landing(canonical, registry, Path("/tmp/landing.json"))
        assert landing["metrics"]["total_repos"] == 6
        assert landing["metrics"]["active_repos"] == 6
        assert landing["metrics"]["ci_workflows"] == 1

    def test_landing_organs_list(self, registry):
        canonical = _make_canonical(registry)
        landing = compute_landing(canonical, registry, Path("/tmp/landing.json"))
        organ_keys = [o["key"] for o in landing["organs"]]
        assert "ORGAN-I" in organ_keys
        assert "META-ORGANVM" in organ_keys

    def test_landing_organ_repo_count(self, registry):
        canonical = _make_canonical(registry)
        landing = compute_landing(canonical, registry, Path("/tmp/landing.json"))
        organ_i = next(o for o in landing["organs"] if o["key"] == "ORGAN-I")
        assert organ_i["repo_count"] == 2
        assert organ_i["name"] == "Theory"
        assert organ_i["greek"] == "Theoria"

    def test_landing_sprint_history_empty_when_no_existing(self, registry):
        canonical = _make_canonical(registry)
        landing = compute_landing(canonical, registry, Path("/tmp/nonexistent/landing.json"))
        assert landing["sprint_history"] == []

    def test_landing_sprint_history_preserved(self, registry, tmp_path):
        canonical = _make_canonical(registry)
        # Create a fake existing system-metrics.json with sprint_history
        existing = {
            "sprint_history": [{"name": "TEST", "date": "2026-01-01"}],
        }
        sm_path = tmp_path / "system-metrics.json"
        sm_path.write_text(json.dumps(existing))
        landing_path = tmp_path / "landing.json"
        landing = compute_landing(canonical, registry, landing_path)
        assert len(landing["sprint_history"]) == 1
        assert landing["sprint_history"][0]["name"] == "TEST"


class TestCopyJsonTargets:
    def test_vitals_transform(self, registry, tmp_path):
        canonical = _make_canonical(registry)
        dest = tmp_path / "vitals.json"
        manifest = {
            "json_copies": [{"dest": str(dest), "transform": "vitals"}],
        }
        count = copy_json_targets(manifest, canonical, dry_run=False)
        assert count == 1
        assert dest.exists()
        data = json.loads(dest.read_text())
        assert data["repos"]["total"] == 6

    def test_landing_transform(self, registry, tmp_path):
        canonical = _make_canonical(registry)
        dest = tmp_path / "landing.json"
        manifest = {
            "json_copies": [{"dest": str(dest), "transform": "landing"}],
        }
        count = copy_json_targets(manifest, canonical, dry_run=False, registry=registry)
        assert count == 1
        assert dest.exists()
        data = json.loads(dest.read_text())
        assert data["metrics"]["total_repos"] == 6
        assert len(data["organs"]) == 4  # 4 organs in fixture

    def test_landing_skipped_without_registry(self, registry, tmp_path):
        canonical = _make_canonical(registry)
        dest = tmp_path / "landing.json"
        manifest = {
            "json_copies": [{"dest": str(dest), "transform": "landing"}],
        }
        count = copy_json_targets(manifest, canonical, dry_run=False, registry=None)
        assert count == 0  # skipped because no registry
        assert not dest.exists()

    def test_portfolio_transform(self, registry, tmp_path):
        canonical = _make_canonical(registry)
        dest = tmp_path / "system-metrics.json"
        manifest = {
            "json_copies": [{"dest": str(dest), "transform": "portfolio"}],
        }
        count = copy_json_targets(manifest, canonical, dry_run=False)
        assert count == 1
        data = json.loads(dest.read_text())
        assert data["registry"]["total_repos"] == 6
