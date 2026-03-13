"""Tests for ontologia sensor implementations."""

import json
from pathlib import Path

import pytest

from organvm_engine.ontologia.sensors import (
    CISensor,
    PromotionSensor,
    RegistrySensor,
    SoakSensor,
    normalize_signals,
    scan_all,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry_file(tmp_path):
    """Create a minimal registry-v2.json for testing."""
    registry = {
        "version": "2",
        "organs": {
            "ORGAN-I": {
                "name": "Theoria",
                "repositories": [
                    {
                        "name": "engine-alpha",
                        "promotion_status": "CANDIDATE",
                        "public": True,
                        "tier": "standard",
                        "ci_workflow": "ci.yml",
                        "platinum_status": True,
                        "implementation_status": "ACTIVE",
                        "last_validated": "2026-03-10T00:00:00Z",
                    },
                    {
                        "name": "theory-beta",
                        "promotion_status": "CANDIDATE",
                        "public": False,
                        "tier": "standard",
                        "ci_workflow": "",
                        "platinum_status": False,
                        "implementation_status": "STUB",
                        "last_validated": "2025-01-01T00:00:00Z",
                    },
                    {
                        "name": "infra-gamma",
                        "promotion_status": "LOCAL",
                        "public": False,
                        "tier": "infrastructure",
                        "ci_workflow": "",
                        "platinum_status": False,
                        "implementation_status": "STUB",
                        "last_validated": "",
                    },
                    {
                        "name": "archived-repo",
                        "promotion_status": "ARCHIVED",
                        "public": False,
                        "tier": "archive",
                        "ci_workflow": "",
                        "platinum_status": False,
                        "implementation_status": "ARCHIVED",
                        "last_validated": "",
                    },
                ],
            },
        },
    }
    path = tmp_path / "registry-v2.json"
    path.write_text(json.dumps(registry))
    return path


@pytest.fixture
def soak_dir(tmp_path):
    """Create a soak directory with a daily snapshot."""
    d = tmp_path / "soak"
    d.mkdir()
    snapshot = {
        "results": [
            {"repo": "engine-alpha", "passed": True, "test_count": 50},
            {"repo": "theory-beta", "passed": False, "test_count": 0},
            {"repo": "anomaly-repo", "passed": True, "test_count": 99999},
        ],
    }
    (d / "daily-2026-03-13.json").write_text(json.dumps(snapshot))
    return d


@pytest.fixture
def snapshot_dir(tmp_path):
    return tmp_path / "snapshots"


# ---------------------------------------------------------------------------
# RegistrySensor
# ---------------------------------------------------------------------------

class TestRegistrySensor:
    def test_is_available(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        assert sensor.is_available()

    def test_is_not_available(self, tmp_path, snapshot_dir):
        sensor = RegistrySensor(tmp_path / "nonexistent.json", snapshot_dir)
        assert not sensor.is_available()

    def test_name(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        assert sensor.name == "registry_sensor"

    def test_first_scan_detects_all_repos_as_new(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        # First scan with no previous snapshot — all repos are "new"
        added = [s for s in signals if _signal_type(s) == "repo_added"]
        assert len(added) == 4

    def test_second_scan_no_changes(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        sensor.scan()  # first scan saves snapshot
        signals = sensor.scan()  # second scan — no changes
        assert len(signals) == 0

    def test_detects_field_change(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        sensor.scan()  # baseline

        # Modify registry
        reg = json.loads(registry_file.read_text())
        reg["organs"]["ORGAN-I"]["repositories"][0]["promotion_status"] = "PUBLIC_PROCESS"
        registry_file.write_text(json.dumps(reg))

        signals = sensor.scan()
        changed = [s for s in signals if _signal_type(s) == "field_changed"]
        assert len(changed) >= 1
        detail = _signal_details(changed[0])
        assert detail["field"] == "promotion_status"
        assert detail["new"] == "PUBLIC_PROCESS"

    def test_detects_repo_added(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        sensor.scan()

        reg = json.loads(registry_file.read_text())
        reg["organs"]["ORGAN-I"]["repositories"].append({
            "name": "new-repo",
            "promotion_status": "LOCAL",
            "tier": "standard",
        })
        registry_file.write_text(json.dumps(reg))

        signals = sensor.scan()
        added = [s for s in signals if _signal_type(s) == "repo_added"]
        assert len(added) == 1

    def test_detects_repo_removed(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        sensor.scan()

        reg = json.loads(registry_file.read_text())
        reg["organs"]["ORGAN-I"]["repositories"].pop()  # remove last
        registry_file.write_text(json.dumps(reg))

        signals = sensor.scan()
        removed = [s for s in signals if _signal_type(s) == "repo_removed"]
        assert len(removed) == 1


# ---------------------------------------------------------------------------
# SoakSensor
# ---------------------------------------------------------------------------

class TestSoakSensor:
    def test_is_available(self, soak_dir, snapshot_dir):
        sensor = SoakSensor(soak_dir, snapshot_dir)
        assert sensor.is_available()

    def test_is_not_available(self, tmp_path, snapshot_dir):
        sensor = SoakSensor(tmp_path / "nonexistent", snapshot_dir)
        assert not sensor.is_available()

    def test_name(self, soak_dir, snapshot_dir):
        sensor = SoakSensor(soak_dir, snapshot_dir)
        assert sensor.name == "soak_sensor"

    def test_detects_validation_failure(self, soak_dir, snapshot_dir):
        sensor = SoakSensor(soak_dir, snapshot_dir)
        signals = sensor.scan()
        failures = [s for s in signals if _signal_type(s) == "validation_failure"]
        assert len(failures) == 1
        assert _signal_entity(failures[0]) == "theory-beta"

    def test_empty_soak_dir(self, tmp_path, snapshot_dir):
        empty = tmp_path / "empty_soak"
        empty.mkdir()
        sensor = SoakSensor(empty, snapshot_dir)
        assert sensor.scan() == []


# ---------------------------------------------------------------------------
# CISensor
# ---------------------------------------------------------------------------

class TestCISensor:
    def test_is_available(self, registry_file, snapshot_dir):
        sensor = CISensor(registry_file, snapshot_dir)
        assert sensor.is_available()

    def test_name(self, registry_file, snapshot_dir):
        sensor = CISensor(registry_file, snapshot_dir)
        assert sensor.name == "ci_sensor"

    def test_detects_missing_ci(self, registry_file, snapshot_dir):
        sensor = CISensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        missing = [s for s in signals if _signal_type(s) == "missing_ci"]
        # theory-beta has no CI and is standard tier
        assert any(_signal_entity(s) == "theory-beta" for s in missing)

    def test_skips_infrastructure(self, registry_file, snapshot_dir):
        sensor = CISensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        missing = [s for s in signals if _signal_type(s) == "missing_ci"]
        # infra-gamma is infrastructure tier — should not be flagged
        assert not any(_signal_entity(s) == "infra-gamma" for s in missing)

    def test_skips_archived(self, registry_file, snapshot_dir):
        sensor = CISensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        # archived-repo should be completely skipped
        assert not any(_signal_entity(s) == "archived-repo" for s in signals)

    def test_detects_stale_validation(self, registry_file, snapshot_dir):
        sensor = CISensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        stale = [s for s in signals if _signal_type(s) == "stale_validation"]
        # theory-beta has last_validated from 2025-01-01 — very stale
        assert any(_signal_entity(s) == "theory-beta" for s in stale)


# ---------------------------------------------------------------------------
# PromotionSensor
# ---------------------------------------------------------------------------

class TestPromotionSensor:
    def test_is_available(self, registry_file, snapshot_dir):
        sensor = PromotionSensor(registry_file, snapshot_dir)
        assert sensor.is_available()

    def test_name(self, registry_file, snapshot_dir):
        sensor = PromotionSensor(registry_file, snapshot_dir)
        assert sensor.name == "promotion_sensor"

    def test_detects_ready_to_promote(self, registry_file, snapshot_dir):
        sensor = PromotionSensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        ready = [s for s in signals if _signal_type(s) == "ready_to_promote"]
        assert len(ready) == 1
        assert _signal_entity(ready[0]) == "engine-alpha"

    def test_detects_promotion_blocked(self, registry_file, snapshot_dir):
        sensor = PromotionSensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        blocked = [s for s in signals if _signal_type(s) == "promotion_blocked"]
        assert any(_signal_entity(s) == "theory-beta" for s in blocked)

    def test_detects_stale_candidate(self, registry_file, snapshot_dir):
        sensor = PromotionSensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        stale = [s for s in signals if _signal_type(s) == "stale_candidate"]
        # theory-beta: last_validated 2025-01-01, >90 days ago
        assert any(_signal_entity(s) == "theory-beta" for s in stale)


# ---------------------------------------------------------------------------
# scan_all and normalize
# ---------------------------------------------------------------------------

class TestScanAll:
    def test_scan_all_returns_grouped(self, registry_file, soak_dir, snapshot_dir):
        results = scan_all(
            registry_path=registry_file,
            soak_dir=soak_dir,
            snapshot_dir=snapshot_dir,
        )
        assert "registry_sensor" in results
        assert "soak_sensor" in results
        assert "ci_sensor" in results
        assert "promotion_sensor" in results

    def test_scan_all_with_filter(self, registry_file, soak_dir, snapshot_dir):
        results = scan_all(
            registry_path=registry_file,
            soak_dir=soak_dir,
            snapshot_dir=snapshot_dir,
            sensor_filter="ci_sensor",
        )
        assert "ci_sensor" in results
        assert "registry_sensor" not in results

    def test_normalize_signals_returns_list(self, registry_file, snapshot_dir):
        sensor = RegistrySensor(registry_file, snapshot_dir)
        signals = sensor.scan()
        normalized = normalize_signals(signals)
        assert isinstance(normalized, list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal_type(signal) -> str:
    """Extract signal type from RawSignal or dict."""
    if hasattr(signal, "signal_type"):
        return signal.signal_type
    return signal.get("type", "")


def _signal_entity(signal) -> str:
    """Extract entity from RawSignal or dict."""
    if hasattr(signal, "entity_id"):
        return signal.entity_id or ""
    return signal.get("entity", "")


def _signal_details(signal) -> dict:
    """Extract details from RawSignal or dict."""
    if hasattr(signal, "details"):
        return signal.details
    return signal.get("details", {})
