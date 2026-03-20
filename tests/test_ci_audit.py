"""Tests for ci/audit.py — The Descent Protocol infrastructure audit."""

import json
from pathlib import Path

import pytest

from organvm_engine.ci.audit import (
    CheckStatus,
    InfraAuditReport,
    InfraCheck,
    RepoCompliance,
    TIER_REQUIREMENTS,
    audit_repo,
    check_promotion_infrastructure,
    run_infra_audit,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def full_repo(tmp_path: Path) -> Path:
    """Create a fully-compliant repo structure."""
    repo = tmp_path / "test-repo"
    repo.mkdir()

    # src layout
    (repo / "src").mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'test'")

    # .github structure
    gh = repo / ".github"
    gh.mkdir()
    wf = gh / "workflows"
    wf.mkdir()

    # CI workflow with all steps
    (wf / "ci.yml").write_text(
        "name: CI\non:\n  push:\n    branches: [main]\n"
        "jobs:\n  test:\n    steps:\n"
        "      - run: ruff check src/\n"
        "      - run: pytest tests/ -v\n"
        "      - run: pyright src/\n"
        "      - name: Secret scan\n"
        "        run: |\n"
        "          for pattern in 'sk-[a-zA-Z0-9]{20,}' 'ghp_[a-zA-Z0-9]{36}';\n"
    )

    # CodeQL
    (wf / "codeql.yml").write_text("name: CodeQL\non:\n  push:\n")

    # Release drafter
    (wf / "release-drafter.yml").write_text("name: Release Drafter\non:\n  push:\n")

    # Stale management
    (wf / "stale.yml").write_text("name: Stale\non:\n  schedule:\n")

    # Dependabot
    (gh / "dependabot.yml").write_text("version: 2\nupdates:\n  - package-ecosystem: pip\n")

    # CODEOWNERS
    (gh / "CODEOWNERS").write_text("* @4444j99\n")

    # PR template
    (gh / "pull_request_template.md").write_text("## Summary\n")

    # Issue templates
    it = gh / "ISSUE_TEMPLATE"
    it.mkdir()
    (it / "bug_report.md").write_text("---\nname: Bug\n---\n")
    (it / "feature_request.md").write_text("---\nname: Feature\n---\n")

    # Release drafter config
    (gh / "release-drafter.yml").write_text("name-template: v$RESOLVED_VERSION\n")

    return repo


@pytest.fixture()
def minimal_repo(tmp_path: Path) -> Path:
    """Create a bare-minimum repo (no infrastructure)."""
    repo = tmp_path / "bare-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Bare repo\n")
    (repo / "pyproject.toml").write_text("[project]\nname = 'bare'")
    return repo


@pytest.fixture()
def docs_repo(tmp_path: Path) -> Path:
    """Create a docs-only repo."""
    repo = tmp_path / "docs-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Docs\n")
    gh = repo / ".github"
    gh.mkdir()
    wf = gh / "workflows"
    wf.mkdir()
    (wf / "ci.yml").write_text("name: CI\non:\n  push:\nsteps:\n  - run: markdownlint\n")
    (gh / "dependabot.yml").write_text("version: 2\n")
    return repo


# ---------------------------------------------------------------------------
# Tier requirements
# ---------------------------------------------------------------------------

class TestTierRequirements:
    def test_tiers_are_cumulative(self):
        """Higher tiers should include all lower tier requirements."""
        local = TIER_REQUIREMENTS["LOCAL"]
        candidate = TIER_REQUIREMENTS["CANDIDATE"]
        public = TIER_REQUIREMENTS["PUBLIC_PROCESS"]
        graduated = TIER_REQUIREMENTS["GRADUATED"]

        assert local.issubset(candidate)
        assert candidate.issubset(public)
        assert public.issubset(graduated)

    def test_archived_has_no_requirements(self):
        assert TIER_REQUIREMENTS["ARCHIVED"] == set()

    def test_incubator_has_no_requirements(self):
        assert TIER_REQUIREMENTS["INCUBATOR"] == set()

    def test_graduated_includes_all_filesystem_checks(self):
        graduated = TIER_REQUIREMENTS["GRADUATED"]
        assert "ci_workflow" in graduated
        assert "dependabot" in graduated
        assert "codeowners" in graduated
        assert "codeql" in graduated
        assert "release_automation" in graduated
        assert "stale_management" in graduated
        assert "secret_scan" in graduated


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

class TestAuditRepo:
    def test_full_repo_all_pass(self, full_repo: Path):
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="flagship",
        )
        assert result.repo_name == "test-repo"
        assert result.is_docs_only is False
        # All filesystem-checkable mechanisms should pass
        for check in result.checks:
            if check.status != CheckStatus.API:
                assert check.status in (CheckStatus.PASS, CheckStatus.SKIP), (
                    f"{check.mechanism} should pass: {check.detail}"
                )

    def test_minimal_repo_many_fail(self, minimal_repo: Path):
        result = audit_repo(
            repo_path=minimal_repo,
            repo_name="bare-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="LOCAL",
            tier="standard",
        )
        assert result.failing > 0
        assert result.is_docs_only is False

    def test_docs_repo_skips_code_checks(self, docs_repo: Path):
        result = audit_repo(
            repo_path=docs_repo,
            repo_name="praxis-perpetua",  # in _DOCS_ONLY_INDICATORS
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        assert result.is_docs_only is True
        skipped = [c for c in result.checks if c.status == CheckStatus.SKIP]
        skip_names = {c.mechanism for c in skipped}
        assert "linting" in skip_names
        assert "testing" in skip_names
        assert "type_checking" in skip_names
        assert "codeql" in skip_names

    def test_check_count(self, full_repo: Path):
        """Audit should produce exactly 15 checks."""
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        assert len(result.checks) == 15

    def test_api_checks_present(self, full_repo: Path):
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        api_checks = [c for c in result.checks if c.status == CheckStatus.API]
        api_names = {c.mechanism for c in api_checks}
        assert "branch_protection" in api_names
        assert "required_status_checks" in api_names
        assert "merge_queues" in api_names


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

class TestRepoCompliance:
    def test_tier_compliant_full_repo(self, full_repo: Path):
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        assert result.tier_compliant is True
        assert result.failed_requirements == []

    def test_tier_non_compliant_minimal(self, minimal_repo: Path):
        result = audit_repo(
            repo_path=minimal_repo,
            repo_name="bare-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="CANDIDATE",
            tier="standard",
        )
        assert result.tier_compliant is False
        assert len(result.failed_requirements) > 0

    def test_archived_always_compliant(self, minimal_repo: Path):
        result = audit_repo(
            repo_path=minimal_repo,
            repo_name="bare-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="ARCHIVED",
            tier="archive",
        )
        assert result.tier_compliant is True

    def test_compliance_rate(self, full_repo: Path):
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        assert result.compliance_rate > 0.8

    def test_summary_line(self, full_repo: Path):
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        line = result.summary_line()
        assert "test-repo" in line
        assert "GRADUATED" in line

    def test_to_dict(self, full_repo: Path):
        result = audit_repo(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="standard",
        )
        d = result.to_dict()
        assert d["repo"] == "test-repo"
        assert d["organ"] == "META-ORGANVM"
        assert isinstance(d["checks"], list)
        assert len(d["checks"]) == 15
        # Verify JSON serializable
        json.dumps(d)


# ---------------------------------------------------------------------------
# Full audit report
# ---------------------------------------------------------------------------

class TestRunInfraAudit:
    def test_audit_with_minimal_registry(self, tmp_path: Path):
        """Test audit against a minimal registry with repos on disk."""
        # Create two repos
        repo_a = tmp_path / "meta-organvm" / "repo-a"
        repo_a.mkdir(parents=True)
        (repo_a / "pyproject.toml").write_text("[project]\nname = 'a'")
        gh_a = repo_a / ".github" / "workflows"
        gh_a.mkdir(parents=True)
        (gh_a / "ci.yml").write_text("name: CI\nsteps:\n  - run: pytest\n")
        (repo_a / ".github" / "dependabot.yml").write_text("version: 2\n")

        registry = {
            "organs": {
                "META-ORGANVM": {
                    "repositories": [
                        {
                            "name": "repo-a",
                            "org": "meta-organvm",
                            "promotion_status": "LOCAL",
                            "tier": "standard",
                        },
                    ],
                },
            },
        }

        report = run_infra_audit(registry, workspace=tmp_path)
        assert report.total_repos == 1
        assert len(report.repos) == 1

    def test_organ_filter(self, tmp_path: Path):
        registry = {
            "organs": {
                "META-ORGANVM": {
                    "repositories": [
                        {"name": "r1", "org": "meta-organvm", "promotion_status": "LOCAL", "tier": "standard"},
                    ],
                },
                "ORGAN-I": {
                    "repositories": [
                        {"name": "r2", "org": "organvm-i-theoria", "promotion_status": "LOCAL", "tier": "standard"},
                    ],
                },
            },
        }
        report = run_infra_audit(registry, workspace=tmp_path, organ_filter="META-ORGANVM")
        # Should only include META repos
        assert all(r.organ == "META-ORGANVM" for r in report.repos)

    def test_archived_repos_skipped(self, tmp_path: Path):
        registry = {
            "organs": {
                "META-ORGANVM": {
                    "repositories": [
                        {"name": "old", "org": "meta-organvm", "promotion_status": "ARCHIVED", "tier": "archive"},
                    ],
                },
            },
        }
        report = run_infra_audit(registry, workspace=tmp_path)
        assert report.total_repos == 0

    def test_report_summary(self, tmp_path: Path):
        report = InfraAuditReport(total_repos=10, compliant_repos=7, non_compliant_repos=3)
        summary = report.summary()
        assert "7/10" in summary
        assert "70%" in summary

    def test_report_to_dict(self, tmp_path: Path):
        report = InfraAuditReport(total_repos=5, compliant_repos=3, non_compliant_repos=2)
        d = report.to_dict()
        assert d["total_repos"] == 5
        assert d["compliance_rate"] == 0.6
        json.dumps(d)


# ---------------------------------------------------------------------------
# Promotion gate
# ---------------------------------------------------------------------------

class TestPromotionInfrastructure:
    def test_full_repo_passes_graduated(self, full_repo: Path):
        ok, failures = check_promotion_infrastructure(
            repo_path=full_repo,
            repo_name="test-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            current_status="PUBLIC_PROCESS",
            target_status="GRADUATED",
            tier="standard",
        )
        assert ok is True
        assert failures == []

    def test_minimal_repo_fails_candidate(self, minimal_repo: Path):
        ok, failures = check_promotion_infrastructure(
            repo_path=minimal_repo,
            repo_name="bare-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            current_status="LOCAL",
            target_status="CANDIDATE",
            tier="standard",
        )
        assert ok is False
        assert len(failures) > 0
        assert "ci_workflow" in failures

    def test_minimal_repo_passes_incubator_target(self, minimal_repo: Path):
        """Promoting to INCUBATOR has no infrastructure requirements."""
        ok, failures = check_promotion_infrastructure(
            repo_path=minimal_repo,
            repo_name="bare-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            current_status="INCUBATOR",
            target_status="INCUBATOR",  # INCUBATOR has no requirements
            tier="standard",
        )
        assert ok is True
        assert failures == []

    def test_local_target_requires_ci_and_dependabot(self, minimal_repo: Path):
        """LOCAL tier requires ci_workflow + dependabot."""
        ok, failures = check_promotion_infrastructure(
            repo_path=minimal_repo,
            repo_name="bare-repo",
            organ="META-ORGANVM",
            org="meta-organvm",
            current_status="INCUBATOR",
            target_status="LOCAL",
            tier="standard",
        )
        assert ok is False
        assert "ci_workflow" in failures
        assert "dependabot" in failures


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_nonexistent_repo_path(self, tmp_path: Path):
        result = audit_repo(
            repo_path=tmp_path / "does-not-exist",
            repo_name="ghost",
            organ="ORGAN-I",
            org="ivviiviivvi",
            promotion_status="LOCAL",
            tier="standard",
        )
        # Should fail gracefully
        assert result.failing > 0

    def test_empty_github_dir(self, tmp_path: Path):
        repo = tmp_path / "empty-gh"
        repo.mkdir()
        (repo / ".github").mkdir()
        (repo / "pyproject.toml").write_text("[project]\nname = 'e'")
        result = audit_repo(
            repo_path=repo,
            repo_name="empty-gh",
            organ="ORGAN-I",
            org="ivviiviivvi",
            promotion_status="LOCAL",
            tier="standard",
        )
        assert result.failing > 0

    def test_check_status_enum_values(self):
        assert CheckStatus.PASS.value == "PASS"
        assert CheckStatus.FAIL.value == "FAIL"
        assert CheckStatus.SKIP.value == "SKIP"
        assert CheckStatus.API.value == "API"

    def test_docs_only_detection_by_name(self, tmp_path: Path):
        """Repos in _DOCS_ONLY_INDICATORS are flagged as docs-only."""
        repo = tmp_path / ".github"
        repo.mkdir()
        result = audit_repo(
            repo_path=repo,
            repo_name=".github",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="GRADUATED",
            tier="infrastructure",
        )
        assert result.is_docs_only is True

    def test_docs_only_detection_by_content(self, tmp_path: Path):
        """Repos without pyproject.toml/package.json/src/ are docs-only."""
        repo = tmp_path / "pure-docs"
        repo.mkdir()
        (repo / "README.md").write_text("# Docs only\n")
        result = audit_repo(
            repo_path=repo,
            repo_name="pure-docs",
            organ="META-ORGANVM",
            org="meta-organvm",
            promotion_status="LOCAL",
            tier="standard",
        )
        assert result.is_docs_only is True
