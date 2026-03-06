"""Tests for governance/audit.py — full governance audit."""

from pathlib import Path

from organvm_engine.governance.audit import AuditResult, run_audit

FIXTURES = Path(__file__).parent / "fixtures"


class TestAuditResult:
    def test_passed_no_criticals(self):
        result = AuditResult(critical=[], warnings=["minor issue"])
        assert result.passed is True

    def test_failed_with_critical(self):
        result = AuditResult(critical=["major issue"])
        assert result.passed is False

    def test_summary_includes_findings(self):
        result = AuditResult(
            critical=["crit1"],
            warnings=["warn1"],
            info=["info1"],
        )
        summary = result.summary()
        assert "CRITICAL" in summary
        assert "WARNINGS" in summary
        assert "INFO" in summary
        assert "FAIL" in summary

    def test_summary_pass(self):
        result = AuditResult()
        summary = result.summary()
        assert "PASS" in summary


class TestRunAudit:
    def _load_test_rules(self):
        import json

        with (FIXTURES / "governance-rules-test.json").open() as f:
            return json.load(f)

    def test_run_audit_clean_registry(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "clean-repo",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "documentation_status": "COMPLETE",
                            "ci_workflow": True,
                            "platinum_status": True,
                            "last_validated": "2026-03-01T00:00:00",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        rules = self._load_test_rules()
        result = run_audit(registry, rules)
        assert len(result.critical) == 0

    def test_run_audit_detects_missing_readme(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "no-readme",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "documentation_status": "EMPTY",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        rules = self._load_test_rules()
        result = run_audit(registry, rules)
        assert any("missing README" in c for c in result.critical)

    def test_run_audit_detects_stale_repo(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "stale-repo",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "last_validated": "2020-01-01T00:00:00",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        rules = self._load_test_rules()
        result = run_audit(registry, rules)
        assert any("stale" in w for w in result.warnings)

    def test_run_audit_detects_missing_ci(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "no-ci",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        rules = self._load_test_rules()
        result = run_audit(registry, rules)
        assert any("no CI workflow" in w for w in result.warnings)

    def test_run_audit_propagates_dependency_result(self):
        registry = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [
                        {
                            "name": "repo-a",
                            "org": "organvm-i-theoria",
                            "implementation_status": "ACTIVE",
                            "dependencies": [],
                        },
                    ],
                },
            },
        }
        rules = self._load_test_rules()
        result = run_audit(registry, rules)
        assert result.dependency_result is not None
