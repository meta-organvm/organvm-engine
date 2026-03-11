"""Tests for audit types."""

from organvm_engine.audit.types import (
    Finding,
    InfrastructureAuditReport,
    LayerReport,
    Severity,
)


class TestFinding:
    def test_to_dict(self):
        f = Finding(
            severity=Severity.CRITICAL,
            layer="filesystem",
            organ="ORGAN-I",
            repo="test-repo",
            message="Repo not found",
            suggestion="Clone it",
        )
        d = f.to_dict()
        assert d["severity"] == "critical"
        assert d["layer"] == "filesystem"
        assert d["organ"] == "ORGAN-I"
        assert d["repo"] == "test-repo"
        assert d["message"] == "Repo not found"
        assert d["suggestion"] == "Clone it"

    def test_default_suggestion(self):
        f = Finding(
            severity=Severity.INFO,
            layer="edges",
            organ="",
            repo="",
            message="OK",
        )
        assert f.suggestion == ""


class TestLayerReport:
    def test_empty(self):
        lr = LayerReport(layer="test")
        assert lr.critical_count == 0
        assert lr.warning_count == 0
        assert lr.info_count == 0

    def test_counts(self):
        lr = LayerReport(layer="test", findings=[
            Finding(Severity.CRITICAL, "test", "A", "r1", "bad"),
            Finding(Severity.WARNING, "test", "A", "r2", "warn"),
            Finding(Severity.INFO, "test", "B", "r3", "info"),
            Finding(Severity.CRITICAL, "test", "B", "r4", "bad2"),
        ])
        assert lr.critical_count == 2
        assert lr.warning_count == 1
        assert lr.info_count == 1

    def test_by_severity(self):
        lr = LayerReport(layer="test", findings=[
            Finding(Severity.CRITICAL, "test", "A", "r1", "bad"),
            Finding(Severity.INFO, "test", "A", "r2", "ok"),
        ])
        assert len(lr.by_severity(Severity.CRITICAL)) == 1
        assert len(lr.by_severity(Severity.INFO)) == 1
        assert len(lr.by_severity(Severity.WARNING)) == 0

    def test_by_organ(self):
        lr = LayerReport(layer="test", findings=[
            Finding(Severity.INFO, "test", "ORGAN-I", "r1", "a"),
            Finding(Severity.INFO, "test", "ORGAN-II", "r2", "b"),
            Finding(Severity.INFO, "test", "ORGAN-I", "r3", "c"),
        ])
        assert len(lr.by_organ("ORGAN-I")) == 2

    def test_to_dict(self):
        lr = LayerReport(layer="fs", findings=[
            Finding(Severity.WARNING, "fs", "A", "r", "w"),
        ])
        d = lr.to_dict()
        assert d["layer"] == "fs"
        assert d["critical"] == 0
        assert d["warnings"] == 1
        assert len(d["findings"]) == 1


class TestInfrastructureAuditReport:
    def test_empty(self):
        r = InfrastructureAuditReport()
        assert r.all_findings == []
        assert r.critical_count == 0

    def test_rollup(self):
        r = InfrastructureAuditReport()
        r.layers["fs"] = LayerReport(layer="fs", findings=[
            Finding(Severity.CRITICAL, "fs", "A", "r1", "bad"),
        ])
        r.layers["edges"] = LayerReport(layer="edges", findings=[
            Finding(Severity.WARNING, "edges", "B", "r2", "warn"),
        ])
        assert r.critical_count == 1
        assert r.warning_count == 1
        assert len(r.all_findings) == 2

    def test_findings_for_organ(self):
        r = InfrastructureAuditReport()
        r.layers["fs"] = LayerReport(layer="fs", findings=[
            Finding(Severity.INFO, "fs", "ORGAN-I", "r1", "a"),
            Finding(Severity.INFO, "fs", "ORGAN-II", "r2", "b"),
        ])
        assert len(r.findings_for_organ("ORGAN-I")) == 1

    def test_findings_for_repo(self):
        r = InfrastructureAuditReport()
        r.layers["fs"] = LayerReport(layer="fs", findings=[
            Finding(Severity.INFO, "fs", "A", "target", "a"),
            Finding(Severity.INFO, "fs", "A", "other", "b"),
        ])
        assert len(r.findings_for_repo("target")) == 1

    def test_to_dict(self):
        r = InfrastructureAuditReport(scope_organ="ORGAN-I")
        r.layers["fs"] = LayerReport(layer="fs")
        d = r.to_dict()
        assert d["scope_organ"] == "ORGAN-I"
        assert "summary" in d
        assert "layers" in d

    def test_organs_with_findings(self):
        r = InfrastructureAuditReport()
        r.layers["fs"] = LayerReport(layer="fs", findings=[
            Finding(Severity.INFO, "fs", "ORGAN-I", "r1", "a"),
            Finding(Severity.INFO, "fs", "ORGAN-III", "r2", "b"),
            Finding(Severity.INFO, "fs", "ORGAN-I", "r3", "c"),
        ])
        organs = r.organs_with_findings()
        assert organs == ["ORGAN-I", "ORGAN-III"]
