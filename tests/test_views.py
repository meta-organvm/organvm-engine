"""Tests for view projection functions."""

from organvm_engine.metrics.organism import compute_organism
from organvm_engine.metrics.views import (
    project_blockers,
    project_gate_stats,
    project_mcp_health,
    project_organism_cli,
    project_progress_api,
    project_system_metrics,
)


class TestProjectProgressApi:
    def test_structure(self, registry):
        org = compute_organism(registry)
        d = project_progress_api(org)
        assert d["total"] == 6
        assert "sys_pct" in d
        assert "profiles" in d
        assert len(d["projects"]) == 6

    def test_projects_have_gates(self, registry):
        org = compute_organism(registry)
        d = project_progress_api(org)
        for p in d["projects"]:
            assert "gates" in p
            assert "repo" in p


class TestProjectMcpHealth:
    def test_structure(self, registry):
        org = compute_organism(registry)
        d = project_mcp_health(org)
        assert d["total_repos"] == 6
        assert "active_repos" in d
        assert "archived_repos" in d
        assert "ci_coverage" in d
        assert "test_coverage" in d
        assert "docs_coverage" in d

    def test_by_organ(self, registry):
        org = compute_organism(registry)
        d = project_mcp_health(org)
        assert "ORGAN-I" in d["by_organ"]
        assert d["by_organ"]["ORGAN-I"]["total"] == 2

    def test_promo_distribution(self, registry):
        org = compute_organism(registry)
        d = project_mcp_health(org)
        dist = d["promotion_distribution"]
        assert sum(dist.values()) == 6

    def test_coverage_ratios(self, registry):
        org = compute_organism(registry)
        d = project_mcp_health(org)
        # All coverage values should be between 0 and 1
        assert 0 <= d["ci_coverage"] <= 1
        assert 0 <= d["test_coverage"] <= 1
        assert 0 <= d["docs_coverage"] <= 1


class TestProjectSystemMetrics:
    def test_structure(self, registry):
        org = compute_organism(registry)
        d = project_system_metrics(org)
        assert d["total_repos"] == 6
        assert "per_organ" in d
        assert "implementation_status" in d

    def test_per_organ(self, registry):
        org = compute_organism(registry)
        d = project_system_metrics(org)
        assert d["per_organ"]["ORGAN-I"]["repos"] == 2


class TestProjectGateStats:
    def test_structure(self, registry):
        org = compute_organism(registry)
        d = project_gate_stats(org)
        assert "gates" in d
        assert len(d["gates"]) == 10

    def test_gate_has_failing_repos(self, registry):
        org = compute_organism(registry)
        d = project_gate_stats(org)
        for g in d["gates"]:
            assert "name" in g
            assert "failing_repos" in g
            assert g["applicable"] >= g["passed"]


class TestProjectBlockers:
    def test_structure(self, registry):
        org = compute_organism(registry)
        d = project_blockers(org)
        assert "ready" in d
        assert "blocked" in d

    def test_blocked_has_details(self, registry):
        org = compute_organism(registry)
        d = project_blockers(org)
        for b in d["blocked"]:
            assert "repo" in b
            assert "blockers" in b


class TestProjectOrganismCli:
    def test_system_level(self, registry):
        org = compute_organism(registry)
        d = project_organism_cli(org)
        assert d["total_repos"] == 6
        assert "organs" in d

    def test_organ_level(self, registry):
        org = compute_organism(registry)
        d = project_organism_cli(org, organ="ORGAN-I")
        assert d["organ_id"] == "ORGAN-I"
        assert d["count"] == 2

    def test_repo_level(self, registry):
        org = compute_organism(registry)
        d = project_organism_cli(org, repo="recursive-engine")
        assert d["repo"] == "recursive-engine"

    def test_missing_organ(self, registry):
        org = compute_organism(registry)
        d = project_organism_cli(org, organ="ORGAN-99")
        assert "error" in d

    def test_missing_repo(self, registry):
        org = compute_organism(registry)
        d = project_organism_cli(org, repo="nonexistent")
        assert "error" in d
