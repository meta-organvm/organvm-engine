"""Tests for AX-003: individual primacy governance check."""

from pathlib import Path

from organvm_engine.governance.individual_primacy import (
    PrimacyFinding,
    PrimacyReport,
    check_individual_primacy,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestPrimacyReport:
    def test_empty_report_passes(self):
        report = PrimacyReport()
        assert report.passed

    def test_report_with_critical_fails(self):
        report = PrimacyReport(findings=[
            PrimacyFinding(severity="critical", message="test"),
        ])
        assert not report.passed

    def test_report_with_only_warnings_passes(self):
        report = PrimacyReport(findings=[
            PrimacyFinding(severity="warning", message="test"),
        ])
        assert report.passed

    def test_human_gated_property(self):
        report = PrimacyReport(provisions_present=["human_approval_required"])
        assert report.human_gated

    def test_not_human_gated_when_missing(self):
        report = PrimacyReport(provisions_present=[])
        assert not report.human_gated

    def test_summary_contains_result(self):
        report = PrimacyReport()
        summary = report.summary()
        assert "PASS" in summary
        assert "AX-003" in summary

    def test_summary_fail(self):
        report = PrimacyReport(findings=[
            PrimacyFinding(severity="critical", message="no HITL"),
        ])
        summary = report.summary()
        assert "FAIL" in summary


class TestCheckIndividualPrimacy:
    def test_rules_with_no_provisions_fails(self):
        """Rules with zero HITL provisions should produce a critical finding."""
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        report = check_individual_primacy(rules)
        assert not report.passed
        critical = [f for f in report.findings if f.severity == "critical"]
        assert len(critical) >= 1
        assert "human-in-the-loop" in critical[0].message.lower() or \
               "individual primacy" in critical[0].message.lower()

    def test_rules_with_top_level_provision(self):
        """Rules with a top-level HITL provision should be recognized."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        report = check_individual_primacy(rules)
        assert report.passed
        assert "human_approval_required" in report.provisions_present
        assert "individual_primacy" in report.provisions_present
        assert "human_review_required" in report.provisions_present
        assert report.provisions_missing == []

    def test_provision_in_sub_section(self):
        """Provisions inside promotion_rules are detected."""
        rules = {
            "version": "1.0",
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        report = check_individual_primacy(rules)
        assert "human_approval_required" in report.provisions_present

    def test_promotion_gating_warnings(self):
        """Transitions to critical states without conditions produce warnings."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {},
            "state_machine": {
                "transitions": {
                    "CANDIDATE": ["PUBLIC_PROCESS", "LOCAL"],
                    "PUBLIC_PROCESS": ["GRADUATED", "CANDIDATE"],
                },
            },
            "audit_thresholds": {},
        }
        report = check_individual_primacy(rules)
        # Should have warnings about missing human approval on transitions
        warnings = [f for f in report.findings if f.severity == "warning"]
        transition_warnings = [
            w for w in warnings if "human approval" in w.message.lower()
        ]
        assert len(transition_warnings) >= 1

    def test_promotion_gating_with_explicit_approval(self):
        """When promotion_rules has human_approval_required, no transition warnings."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {
                "transitions": {
                    "CANDIDATE": ["PUBLIC_PROCESS"],
                },
            },
            "audit_thresholds": {},
        }
        report = check_individual_primacy(rules)
        # Explicit approval means no transition-level warnings
        transition_warnings = [
            f for f in report.findings
            if f.severity == "warning" and "transition" in f.message.lower()
        ]
        assert len(transition_warnings) == 0

    def test_ai_agent_unrestricted_scope_fails(self):
        """AI agent with unrestricted scope should produce a critical finding."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        seeds = {
            "org/repo": {
                "ownership": {
                    "lead": "human",
                    "ai_agents": [
                        {"type": "claude", "scope": "full"},
                    ],
                },
            },
        }
        report = check_individual_primacy(rules, seeds=seeds)
        assert not report.passed
        critical = [f for f in report.findings if f.severity == "critical"]
        assert any("unrestricted" in f.message.lower() for f in critical)

    def test_ai_agent_bounded_scope_passes(self):
        """AI agent with bounded scope should not produce critical findings."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        seeds = {
            "org/repo": {
                "ownership": {
                    "lead": "human",
                    "ai_agents": [
                        {"type": "claude", "scope": "read,edit,commit"},
                    ],
                },
            },
        }
        report = check_individual_primacy(rules, seeds=seeds)
        assert report.passed

    def test_ai_agent_no_scope_warns(self):
        """AI agent with no scope should produce a warning."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        seeds = {
            "org/repo": {
                "ownership": {
                    "lead": "human",
                    "ai_agents": [
                        {"type": "gemini"},
                    ],
                },
            },
        }
        report = check_individual_primacy(rules, seeds=seeds)
        warnings = [f for f in report.findings if f.severity == "warning"]
        assert any("no declared scope" in w.message.lower() for w in warnings)

    def test_no_seeds_skips_agent_check(self):
        """When no seeds are provided, AI agent check is skipped."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        report = check_individual_primacy(rules, seeds=None)
        assert report.passed
        # No agent-related findings
        assert not any("agent" in f.message.lower() for f in report.findings)

    def test_seeds_without_ownership_no_error(self):
        """Seeds without ownership section should not cause errors."""
        rules = {
            "version": "1.0",
            "human_approval_required": True,
            "individual_primacy": True,
            "human_review_required": True,
            "dependency_rules": {},
            "promotion_rules": {"human_approval_required": True},
            "state_machine": {"transitions": {}},
            "audit_thresholds": {},
        }
        seeds = {
            "org/repo": {"organ": "I", "repo": "test"},
        }
        report = check_individual_primacy(rules, seeds=seeds)
        assert report.passed
