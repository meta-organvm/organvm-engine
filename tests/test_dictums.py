"""Tests for governance/dictums.py — constitutional dictum validation."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from organvm_engine.governance.dictums import (
    DictumReport,
    DictumViolation,
    check_all_dictums,
    get_axioms,
    get_dictums,
    get_organ_dictum,
    get_repo_rules,
    list_all_dictums,
    validate_dag_invariant,
    validate_epistemic_membranes,
    validate_organ_iii_factory,
    validate_seed_mandate,
    validate_ttl_eviction,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def rules():
    with (FIXTURES / "governance-rules-test.json").open() as f:
        return json.load(f)


@pytest.fixture
def registry():
    with (FIXTURES / "registry-minimal.json").open() as f:
        return json.load(f)


# ── Loading tests ────────────────────────────────────────────────


class TestDictumLoading:
    def test_get_dictums(self, rules):
        d = get_dictums(rules)
        assert "axioms" in d
        assert "organ_dictums" in d
        assert "repo_rules" in d

    def test_get_dictums_missing(self):
        assert get_dictums({}) == {}

    def test_get_axioms(self, rules):
        axioms = get_axioms(rules)
        assert len(axioms) == 3
        ids = [a["id"] for a in axioms]
        assert "AX-1" in ids
        assert "AX-2" in ids
        assert "AX-3" in ids

    def test_get_axioms_missing(self):
        assert get_axioms({}) == []

    def test_get_organ_dictum(self, rules):
        od3 = get_organ_dictum(rules, "ORGAN-III")
        assert len(od3) == 1
        assert od3[0]["id"] == "OD-III"

    def test_get_organ_dictum_missing(self, rules):
        assert get_organ_dictum(rules, "ORGAN-X") == []

    def test_get_repo_rules(self, rules):
        rr = get_repo_rules(rules)
        assert len(rr) == 3
        ids = [r["id"] for r in rr]
        assert "RR-1" in ids
        assert "RR-2" in ids
        assert "RR-3" in ids

    def test_get_repo_rules_missing(self):
        assert get_repo_rules({}) == []


class TestListAllDictums:
    def test_list_all(self, rules):
        all_d = list_all_dictums(rules)
        # 3 axioms + 2 organ dictums (OD-III, OD-IV) + 3 repo rules = 8
        assert len(all_d) == 8

    def test_list_has_level_tags(self, rules):
        all_d = list_all_dictums(rules)
        levels = {d["level"] for d in all_d}
        assert levels == {"axiom", "organ", "repo"}

    def test_organ_dictums_have_organ_key(self, rules):
        all_d = list_all_dictums(rules)
        organ_dicts = [d for d in all_d if d["level"] == "organ"]
        for od in organ_dicts:
            assert "organ" in od

    def test_list_empty_rules(self):
        assert list_all_dictums({}) == []


# ── Axiom validators ─────────────────────────────────────────────


class TestAxiomValidators:
    def test_dag_invariant_pass(self, registry):
        """Clean registry has no back-edges or cycles."""
        violations = validate_dag_invariant(registry)
        assert violations == []

    def test_dag_invariant_back_edge(self, registry):
        """Inject a back-edge: ORGAN-I repo depends on ORGAN-III."""
        registry["organs"]["ORGAN-I"]["repositories"][0]["dependencies"] = [
            "organvm-iii-ergon/product-app",
        ]
        violations = validate_dag_invariant(registry)
        assert len(violations) >= 1
        assert violations[0].dictum_id == "AX-1"
        assert violations[0].severity == "critical"
        assert "Back-edge" in violations[0].message

    def test_epistemic_membranes_no_workspace(self, registry):
        """Without workspace, validator returns no violations."""
        violations = validate_epistemic_membranes(registry)
        assert violations == []

    def test_epistemic_membranes_missing_seed(self, registry, tmp_path):
        """Cross-organ dep without seed.yaml raises violation."""
        # metasystem-master depends on organvm-i-theoria/recursive-engine
        # which is cross-organ. If no seed.yaml, should flag it.
        org_dir = tmp_path / "organvm-ii-poiesis" / "metasystem-master"
        org_dir.mkdir(parents=True)
        # No seed.yaml created

        violations = validate_epistemic_membranes(registry, workspace=tmp_path)
        ax2 = [v for v in violations if v.dictum_id == "AX-2"]
        assert len(ax2) >= 1

    def test_epistemic_membranes_with_seed(self, registry, tmp_path):
        """Cross-organ dep with seed.yaml present = no violation."""
        org_dir = tmp_path / "organvm-ii-poiesis" / "metasystem-master"
        org_dir.mkdir(parents=True)
        (org_dir / "seed.yaml").write_text("organ: ORGAN-II\n")

        violations = validate_epistemic_membranes(registry, workspace=tmp_path)
        ax2 = [v for v in violations if v.dictum_id == "AX-2"]
        assert ax2 == []

    def test_ttl_fresh(self, registry, rules):
        """Fresh repos have no TTL violations."""
        # Set all last_validated to today
        for _organ, organ_data in registry["organs"].items():
            for repo in organ_data["repositories"]:
                repo["last_validated"] = datetime.now(timezone.utc).isoformat()
        violations = validate_ttl_eviction(registry, rules)
        assert violations == []

    def test_ttl_stale(self, registry, rules):
        """A stale repo triggers AX-3."""
        registry["organs"]["ORGAN-I"]["repositories"][0]["last_validated"] = "2025-01-01"
        violations = validate_ttl_eviction(registry, rules)
        stale = [v for v in violations if "Stale" in v.message]
        assert len(stale) >= 1
        assert stale[0].dictum_id == "AX-3"

    def test_ttl_incubator_expired(self, registry, rules):
        """Expired INCUBATOR repo triggers AX-3."""
        repo = registry["organs"]["ORGAN-I"]["repositories"][0]
        repo["promotion_status"] = "INCUBATOR"
        repo["last_validated"] = "2025-01-01"
        violations = validate_ttl_eviction(registry, rules)
        incubator = [v for v in violations if "INCUBATOR" in v.message]
        assert len(incubator) >= 1


# ── Organ dictum validators ──────────────────────────────────────


class TestOrganDictumValidators:
    def test_od_iii_pass(self, registry):
        """ORGAN-III repo with revenue_model passes."""
        violations = validate_organ_iii_factory(registry)
        # product-app has revenue_model but no ci_workflow
        ci_violations = [v for v in violations if "CI" in v.message]
        rev_violations = [v for v in violations if "revenue" in v.message]
        assert rev_violations == []
        assert len(ci_violations) >= 1  # Missing CI

    def test_od_iii_missing_revenue(self, registry):
        """ORGAN-III repo without revenue_model fails."""
        del registry["organs"]["ORGAN-III"]["repositories"][0]["revenue_model"]
        violations = validate_organ_iii_factory(registry)
        rev = [v for v in violations if "revenue" in v.message]
        assert len(rev) == 1
        assert rev[0].dictum_id == "OD-III"

    def test_od_iii_archived_skip(self, registry):
        """Archived ORGAN-III repos are skipped."""
        registry["organs"]["ORGAN-III"]["repositories"][0]["implementation_status"] = "ARCHIVED"
        violations = validate_organ_iii_factory(registry)
        assert violations == []


# ── Repo rule validators ─────────────────────────────────────────


class TestRepoRuleValidators:
    def test_seed_mandate_no_workspace(self, registry):
        violations = validate_seed_mandate(registry)
        assert violations == []

    def test_seed_mandate_missing(self, registry, tmp_path):
        """Repos without seed.yaml trigger RR-1."""
        # Create dirs but no seed.yaml
        for _organ, organ_data in registry["organs"].items():
            for repo in organ_data["repositories"]:
                d = tmp_path / repo["org"] / repo["name"]
                d.mkdir(parents=True, exist_ok=True)

        violations = validate_seed_mandate(registry, workspace=tmp_path)
        assert len(violations) > 0
        assert all(v.dictum_id == "RR-1" for v in violations)

    def test_seed_mandate_present(self, registry, tmp_path):
        """Repos with seed.yaml pass RR-1."""
        for _organ, organ_data in registry["organs"].items():
            for repo in organ_data["repositories"]:
                d = tmp_path / repo["org"] / repo["name"]
                d.mkdir(parents=True, exist_ok=True)
                (d / "seed.yaml").write_text("organ: test\n")

        violations = validate_seed_mandate(registry, workspace=tmp_path)
        assert violations == []


# ── DictumReport ─────────────────────────────────────────────────


class TestDictumReport:
    def test_empty_report(self):
        report = DictumReport(checked=5, passed=5)
        assert report.all_passed
        assert "PASS" in report.summary()

    def test_report_with_violations(self):
        v = DictumViolation(
            dictum_id="AX-1",
            dictum_name="DAG Invariant",
            severity="critical",
            message="Back-edge detected",
            organ="ORGAN-I",
            repo="test-repo",
        )
        report = DictumReport(violations=[v], checked=1, passed=0)
        assert not report.all_passed
        assert "FAIL" in report.summary()

    def test_report_to_dict(self):
        report = DictumReport(checked=3, passed=2)
        report.violations.append(DictumViolation(
            dictum_id="AX-3",
            dictum_name="TTL",
            severity="warning",
            message="stale",
        ))
        d = report.to_dict()
        assert d["checked"] == 3
        assert d["passed"] == 2
        assert len(d["violations"]) == 1
        assert d["all_passed"] is False

    def test_violation_to_dict(self):
        v = DictumViolation(
            dictum_id="RR-1",
            dictum_name="Seed Contract",
            severity="warning",
            message="No seed.yaml",
            organ="ORGAN-I",
            repo="test",
        )
        d = v.to_dict()
        assert d["dictum_id"] == "RR-1"
        assert d["organ"] == "ORGAN-I"
        assert d["repo"] == "test"

    def test_violation_to_dict_no_organ(self):
        v = DictumViolation(
            dictum_id="AX-1",
            dictum_name="DAG",
            severity="critical",
            message="cycle",
        )
        d = v.to_dict()
        assert "organ" not in d
        assert "repo" not in d


# ── check_all_dictums ────────────────────────────────────────────


class TestCheckAllDictums:
    def test_full_run(self, registry, rules):
        """Full run with no workspace returns a valid report."""
        report = check_all_dictums(registry, rules)
        assert report.checked > 0
        # Without workspace, seed/membrane validators return nothing
        assert isinstance(report.violations, list)

    def test_skips_manual(self, rules, registry):
        """Manual-enforcement dictums are not checked."""
        report = check_all_dictums(registry, rules)
        # OD-IV (manual) and RR-2 (manual) should not be checked
        checked_ids = set()
        for v in report.violations:
            checked_ids.add(v.dictum_id)
        assert "OD-IV" not in checked_ids
        assert "RR-2" not in checked_ids

    def test_no_dictums_section(self, registry):
        """Rules without dictums section returns empty report."""
        report = check_all_dictums(registry, {"version": "1.0"})
        assert report.checked == 0
        assert report.all_passed

    def test_correct_counts(self, registry, rules):
        """Checked + passed counts are consistent."""
        report = check_all_dictums(registry, rules)
        # validators with 0 violations count as passed
        validators_with_violations = len({v.dictum_id for v in report.violations})
        assert report.passed + validators_with_violations <= report.checked


# ── Audit integration ────────────────────────────────────────────


class TestAuditIntegration:
    def test_audit_with_dictums(self, registry, rules):
        """Audit includes dictum violations when rules have dictums."""
        from organvm_engine.governance.audit import run_audit

        result = run_audit(registry, rules, check_dictums=True)
        assert result.dictum_report is not None
        # Should have at least the dictums info line
        dictum_info = [i for i in result.info if "Dictums:" in i]
        assert len(dictum_info) == 1

    def test_audit_without_dictums(self, registry):
        """Audit works fine without dictums section."""
        from organvm_engine.governance.audit import run_audit

        rules_no_dictums = {
            "version": "1.0",
            "dependency_rules": {
                "max_transitive_depth": 4,
                "no_circular_dependencies": True,
                "no_back_edges": True,
            },
            "audit_thresholds": {"critical": {}, "warning": {}},
            "organ_requirements": {},
        }
        result = run_audit(registry, rules_no_dictums, check_dictums=True)
        assert result.dictum_report is None

    def test_audit_backwards_compatible(self, registry):
        """Audit with check_dictums=False behaves as before."""
        from organvm_engine.governance.audit import run_audit

        rules_no_dictums = {
            "version": "1.0",
            "dependency_rules": {
                "max_transitive_depth": 4,
                "no_circular_dependencies": True,
                "no_back_edges": True,
            },
            "audit_thresholds": {"critical": {}, "warning": {}},
            "organ_requirements": {},
        }
        result = run_audit(registry, rules_no_dictums, check_dictums=False)
        assert result.dictum_report is None
