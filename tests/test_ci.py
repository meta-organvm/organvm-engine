"""Tests for the CI triage module."""

import json
from pathlib import Path

import pytest

from organvm_engine.ci.triage import triage, CITriageReport


@pytest.fixture
def soak_dir_with_failures(tmp_path):
    """Soak dir with CI failure details."""
    d = tmp_path / "soak-test"
    d.mkdir()
    snapshot = {
        "date": "2026-02-23",
        "validation": {"registry_pass": True, "dependency_pass": True},
        "ci": {
            "total_checked": 77,
            "passing": 52,
            "failing": 25,
            "failing_repos": [
                {"name": "repo-a", "organ": "ORGAN-I"},
                {"name": "repo-b", "organ": "ORGAN-I"},
                {"name": ".github", "organ": "ORGAN-VII"},
                {"name": "social-automation", "organ": "ORGAN-VII"},
                {"name": "product-app", "organ": "ORGAN-III"},
            ],
        },
    }
    (d / "daily-2026-02-23.json").write_text(json.dumps(snapshot))
    return d


@pytest.fixture
def soak_dir_string_format(tmp_path):
    """Soak dir with string-format failing repos."""
    d = tmp_path / "soak-test"
    d.mkdir()
    snapshot = {
        "date": "2026-02-23",
        "ci": {
            "total_checked": 10,
            "passing": 7,
            "failing": 3,
            "failing_repos": [
                "ORGAN-I/repo-a",
                "ORGAN-III/product-app",
                "ORGAN-VII/.github",
            ],
        },
    }
    (d / "daily-2026-02-23.json").write_text(json.dumps(snapshot))
    return d


class TestCITriage:
    def test_basic_counts(self, soak_dir_with_failures):
        report = triage(soak_dir=soak_dir_with_failures)
        assert report.total_checked == 77
        assert report.passing == 52
        assert report.failing == 25

    def test_categorizes_by_organ(self, soak_dir_with_failures):
        report = triage(soak_dir=soak_dir_with_failures)
        assert "ORGAN-I" in report.by_organ
        assert len(report.by_organ["ORGAN-I"]) == 2
        assert "ORGAN-VII" in report.by_organ
        assert "ORGAN-III" in report.by_organ

    def test_phantom_detection(self, soak_dir_with_failures):
        report = triage(soak_dir=soak_dir_with_failures)
        assert ".github" in report.phantom_candidates
        assert "social-automation" in report.phantom_candidates

    def test_pass_rate(self, soak_dir_with_failures):
        report = triage(soak_dir=soak_dir_with_failures)
        assert abs(report.pass_rate - 52 / 77) < 0.01

    def test_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        report = triage(soak_dir=empty)
        assert report.total_checked == 0
        assert report.failing == 0

    def test_nonexistent_dir(self, tmp_path):
        report = triage(soak_dir=tmp_path / "nope")
        assert report.total_checked == 0

    def test_string_format_repos(self, soak_dir_string_format):
        report = triage(soak_dir=soak_dir_string_format)
        assert "ORGAN-I" in report.by_organ
        assert "ORGAN-III" in report.by_organ

    def test_summary_output(self, soak_dir_with_failures):
        report = triage(soak_dir=soak_dir_with_failures)
        summary = report.summary()
        assert "CI Triage Report" in summary
        assert "ORGAN-I" in summary
        assert "PHANTOM?" in summary

    def test_to_dict(self, soak_dir_with_failures):
        report = triage(soak_dir=soak_dir_with_failures)
        d = report.to_dict()
        assert d["failing"] == 25
        assert "by_organ" in d
        assert "phantom_candidates" in d

    def test_no_failing_repos_key(self, tmp_path):
        """Snapshot without failing_repos list still works."""
        d = tmp_path / "soak-test"
        d.mkdir()
        snapshot = {
            "date": "2026-02-23",
            "ci": {"total_checked": 77, "passing": 77, "failing": 0},
        }
        (d / "daily-2026-02-23.json").write_text(json.dumps(snapshot))
        report = triage(soak_dir=d)
        assert report.failing == 0
        assert report.by_organ == {}
