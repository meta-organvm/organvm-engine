"""Tests for soak-test time-series analysis."""

import json

from organvm_engine.metrics.timeseries import ci_trend, engagement_trend, load_snapshots


class TestLoadSnapshots:
    def test_empty_dir(self, tmp_path):
        assert load_snapshots(tmp_path) == []

    def test_nonexistent_dir(self, tmp_path):
        assert load_snapshots(tmp_path / "does-not-exist") == []

    def test_with_files(self, tmp_path):
        for name, data in [
            ("daily-2026-03-01.json", {"date": "2026-03-01", "ci": {}}),
            ("daily-2026-03-02.json", {"date": "2026-03-02", "ci": {}}),
        ]:
            (tmp_path / name).write_text(json.dumps(data))
        result = load_snapshots(tmp_path)
        assert len(result) == 2
        assert result[0]["date"] == "2026-03-01"
        assert result[1]["date"] == "2026-03-02"

    def test_ignores_non_daily_files(self, tmp_path):
        (tmp_path / "daily-2026-03-01.json").write_text(json.dumps({"date": "2026-03-01"}))
        (tmp_path / "summary.json").write_text(json.dumps({"type": "summary"}))
        (tmp_path / "notes.txt").write_text("hello")
        result = load_snapshots(tmp_path)
        assert len(result) == 1


class TestCiTrend:
    def test_empty(self):
        assert ci_trend([]) == []

    def test_extraction(self):
        snaps = [
            {"date": "2026-03-01", "ci": {"total_checked": 100, "passing": 80, "failing": 20}},
        ]
        result = ci_trend(snaps)
        assert len(result) == 1
        assert result[0]["rate"] == 0.8
        assert result[0]["passing"] == 80
        assert result[0]["failing"] == 20

    def test_zero_total(self):
        snaps = [{"date": "2026-03-01", "ci": {"total_checked": 0, "passing": 0, "failing": 0}}]
        result = ci_trend(snaps)
        assert result[0]["rate"] == 0.0


class TestEngagementTrend:
    def test_empty(self):
        assert engagement_trend([]) == []

    def test_extraction(self):
        snaps = [
            {"date": "2026-03-01", "engagement": {"total_stars": 42, "total_forks": 7}},
        ]
        result = engagement_trend(snaps)
        assert len(result) == 1
        assert result[0]["stars"] == 42
        assert result[0]["forks"] == 7
