"""Tests for audit absorption layer."""

import time

from organvm_engine.audit.absorption import (
    _format_bytes,
    _scan_deposit,
    audit_absorption,
)
from organvm_engine.audit.types import Severity


class TestFormatBytes:
    def test_bytes(self):
        assert _format_bytes(500) == "500B"

    def test_kilobytes(self):
        assert "KB" in _format_bytes(2048)

    def test_megabytes(self):
        assert "MB" in _format_bytes(5 * 1024 * 1024)

    def test_gigabytes(self):
        assert "GB" in _format_bytes(3 * 1024 * 1024 * 1024)


class TestScanDeposit:
    def test_nonexistent(self, tmp_path):
        result = _scan_deposit(tmp_path / "nonexistent")
        assert result["exists"] is False
        assert result["file_count"] == 0

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        result = _scan_deposit(d)
        assert result["exists"] is True
        assert result["file_count"] == 0

    def test_with_files(self, tmp_path):
        d = tmp_path / "deposit"
        d.mkdir()
        (d / "a.txt").write_text("hello")
        (d / "b.txt").write_text("world!!")

        sub = d / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("nested")

        result = _scan_deposit(d)
        assert result["exists"] is True
        assert result["file_count"] == 3
        assert result["total_bytes"] > 0
        assert result["newest_mtime"] > 0


class TestAuditAbsorption:
    def test_no_deposits(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.absorption._DEPOSIT_SPECS",
            [{
                "name": "test-deposit",
                "relative_to": "workspace",
                "path": "nonexistent",
                "description": "Test deposit",
            }],
        )
        report = audit_absorption(tmp_path)
        # Should have summary finding
        assert len(report.findings) > 0

    def test_existing_deposit(self, tmp_path, monkeypatch):
        dep_dir = tmp_path / "my-deposit"
        dep_dir.mkdir()
        (dep_dir / "file.txt").write_text("x" * 1000)

        monkeypatch.setattr(
            "organvm_engine.audit.absorption._DEPOSIT_SPECS",
            [{
                "name": "test-deposit",
                "relative_to": "workspace",
                "path": "my-deposit",
                "description": "Test deposit",
            }],
        )
        report = audit_absorption(tmp_path)
        msgs = [f.message for f in report.findings]
        assert any("test-deposit" in m for m in msgs)

    def test_large_deposit_warning(self, tmp_path, monkeypatch):
        dep_dir = tmp_path / "big-deposit"
        dep_dir.mkdir()
        # Create a file > 100MB in reported size (we'll mock _scan_deposit)
        (dep_dir / "huge.bin").write_bytes(b"\0" * (101 * 1024 * 1024))

        monkeypatch.setattr(
            "organvm_engine.audit.absorption._DEPOSIT_SPECS",
            [{
                "name": "big",
                "relative_to": "workspace",
                "path": "big-deposit",
                "description": "Large deposit",
            }],
        )
        report = audit_absorption(tmp_path)
        warns = [f for f in report.findings if f.severity == Severity.WARNING]
        assert any("big" in f.message for f in warns)

    def test_specstory_detection(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.absorption._DEPOSIT_SPECS",
            [],
        )
        # Create .specstory dirs
        (tmp_path / "organ-i" / "repo-a" / ".specstory").mkdir(parents=True)
        (tmp_path / "organ-i" / "repo-b" / ".specstory").mkdir(parents=True)

        report = audit_absorption(tmp_path)
        msgs = [f.message for f in report.findings]
        assert any(".specstory" in m.lower() or "specstory" in m.lower() for m in msgs)

    def test_verbose_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "organvm_engine.audit.absorption._DEPOSIT_SPECS",
            [{
                "name": "absent",
                "relative_to": "workspace",
                "path": "no-such-dir",
                "description": "Missing deposit",
            }],
        )
        # Non-verbose: no finding for missing deposit
        report_quiet = audit_absorption(tmp_path, verbose=False)
        absent_findings = [
            f for f in report_quiet.findings
            if "absent" in f.message and "not found" in f.message
        ]
        assert len(absent_findings) == 0

        # Verbose: finding for missing deposit
        report_verbose = audit_absorption(tmp_path, verbose=True)
        absent_findings = [
            f for f in report_verbose.findings
            if "absent" in f.message and "not found" in f.message
        ]
        assert len(absent_findings) == 1
