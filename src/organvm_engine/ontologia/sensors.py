"""Concrete sensor implementations bridging engine data to ontologia sensing.

Four sensors watch real system data and emit RawSignal/NormalizedChange
events that feed ontologia's inference and governance layers:

- RegistrySensor: watches registry-v2.json for state changes
- SoakSensor: watches soak-test snapshots for health signals
- CISensor: watches CI health data for workflow failures
- PromotionSensor: evaluates promotion readiness across repos
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from ontologia.sensing.detection import detect_anomaly
    from ontologia.sensing.interfaces import ChangeType, NormalizedChange, RawSignal

    HAS_ONTOLOGIA = True
except ImportError:
    HAS_ONTOLOGIA = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    """Load JSON file, returning None on failure."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Snapshot persistence for delta detection
# ---------------------------------------------------------------------------

_SNAPSHOT_DIR = Path.home() / ".organvm" / "ontologia" / "sensor_snapshots"


def _load_snapshot(sensor_name: str, snapshot_dir: Path | None = None) -> dict[str, Any]:
    """Load the previous sensor snapshot."""
    d = snapshot_dir or _SNAPSHOT_DIR
    path = d / f"{sensor_name}.json"
    data = _load_json(path)
    return data if isinstance(data, dict) else {}


def _save_snapshot(
    sensor_name: str,
    data: dict[str, Any],
    snapshot_dir: Path | None = None,
) -> None:
    """Persist the current sensor snapshot for next delta."""
    d = snapshot_dir or _SNAPSHOT_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sensor_name}.json").write_text(
        json.dumps(data, indent=2, default=str),
    )


# ---------------------------------------------------------------------------
# Helper: extract flat repo state from registry
# ---------------------------------------------------------------------------

def _extract_repo_states(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract a flat {repo_name: {field: value}} mapping from the registry."""
    states: dict[str, dict[str, Any]] = {}
    for _organ_key, organ_data in registry.get("organs", {}).items():
        for repo in organ_data.get("repositories", []):
            name = repo.get("name", "")
            if not name:
                continue
            states[name] = {
                "promotion_status": repo.get("promotion_status", ""),
                "public": repo.get("public", False),
                "tier": repo.get("tier", ""),
                "ci_workflow": repo.get("ci_workflow", ""),
                "platinum_status": repo.get("platinum_status", False),
                "implementation_status": repo.get("implementation_status", ""),
                "last_validated": repo.get("last_validated", ""),
                "organ": organ_data.get("name", ""),
            }
    return states


# ---------------------------------------------------------------------------
# RegistrySensor
# ---------------------------------------------------------------------------

class RegistrySensor:
    """Watches registry-v2.json for state changes between scans."""

    def __init__(
        self,
        registry_path: Path | None = None,
        snapshot_dir: Path | None = None,
    ) -> None:
        self._registry_path = registry_path
        self._snapshot_dir = snapshot_dir

    @property
    def name(self) -> str:
        return "registry_sensor"

    def is_available(self) -> bool:
        path = self._resolve_registry_path()
        return path is not None and path.is_file()

    def scan(self) -> list:
        """Scan registry for changes since last snapshot.

        Returns list of RawSignal if ontologia is available, else list of dicts.
        """
        path = self._resolve_registry_path()
        if path is None or not path.is_file():
            return []

        registry = _load_json(path)
        if not isinstance(registry, dict):
            return []

        current = _extract_repo_states(registry)
        previous = _load_snapshot(self.name, self._snapshot_dir)
        signals = self._compare(previous, current)
        _save_snapshot(self.name, current, self._snapshot_dir)
        return signals

    def _resolve_registry_path(self) -> Path | None:
        if self._registry_path:
            return self._registry_path
        try:
            from organvm_engine.paths import registry_path
            return registry_path()
        except Exception:
            return None

    def _compare(
        self,
        previous: dict[str, Any],
        current: dict[str, Any],
    ) -> list:
        signals = []
        # Detect new repos
        for name in sorted(set(current) - set(previous)):
            signals.append(self._make_signal(
                "repo_added",
                entity_hint=name,
                details={"repo": name, "state": current[name]},
            ))

        # Detect removed repos
        for name in sorted(set(previous) - set(current)):
            signals.append(self._make_signal(
                "repo_removed",
                entity_hint=name,
                details={"repo": name},
            ))

        # Detect field changes on existing repos
        for name in sorted(set(current) & set(previous)):
            for field_name in sorted(set(current[name]) | set(previous.get(name, {}))):
                old_val = previous.get(name, {}).get(field_name)
                new_val = current[name].get(field_name)
                if old_val != new_val:
                    signals.append(self._make_signal(
                        "field_changed",
                        entity_hint=name,
                        details={
                            "repo": name,
                            "field": field_name,
                            "old": old_val,
                            "new": new_val,
                        },
                    ))
        return signals

    def _make_signal(
        self,
        signal_type: str,
        entity_hint: str = "",
        details: dict[str, Any] | None = None,
    ):
        if HAS_ONTOLOGIA:
            return RawSignal(
                sensor_name=self.name,
                signal_type=signal_type,
                entity_id=entity_hint,
                details=details or {},
                timestamp=_now_iso(),
            )
        return {
            "sensor": self.name,
            "type": signal_type,
            "entity": entity_hint,
            "details": details or {},
            "timestamp": _now_iso(),
        }


# ---------------------------------------------------------------------------
# SoakSensor
# ---------------------------------------------------------------------------

class SoakSensor:
    """Watches soak-test snapshots for health signals."""

    def __init__(
        self,
        soak_dir: Path | None = None,
        snapshot_dir: Path | None = None,
    ) -> None:
        self._soak_dir = soak_dir
        self._snapshot_dir = snapshot_dir

    @property
    def name(self) -> str:
        return "soak_sensor"

    def is_available(self) -> bool:
        d = self._resolve_soak_dir()
        return d is not None and d.is_dir()

    def scan(self) -> list:
        d = self._resolve_soak_dir()
        if d is None or not d.is_dir():
            return []

        latest = self._find_latest_snapshot(d)
        if latest is None:
            return []

        data = _load_json(latest)
        if not isinstance(data, dict):
            return []

        signals = []
        results = data.get("results", data.get("repos", []))
        if isinstance(results, list):
            for entry in results:
                if not isinstance(entry, dict):
                    continue
                repo = entry.get("repo", entry.get("name", ""))
                passed = entry.get("passed", entry.get("status") == "pass")
                if not passed:
                    signals.append(self._make_signal(
                        "validation_failure",
                        entity_hint=repo,
                        details={"repo": repo, "snapshot": latest.name},
                    ))

                # Anomaly detection for numeric metrics
                for metric_key in ("test_count", "code_files", "dependency_count"):
                    val = entry.get(metric_key)
                    if isinstance(val, (int, float)):
                        expected = self._expected_range(metric_key)
                        if HAS_ONTOLOGIA:
                            anomaly = detect_anomaly(
                                repo, float(val), expected, self.name,
                            )
                            if anomaly:
                                signals.append(self._make_signal(
                                    "metric_anomaly",
                                    entity_hint=repo,
                                    details={
                                        "metric": metric_key,
                                        "value": val,
                                        "expected_range": list(expected),
                                    },
                                ))

        return signals

    def _resolve_soak_dir(self) -> Path | None:
        if self._soak_dir:
            return self._soak_dir
        try:
            from organvm_engine.paths import soak_dir
            return soak_dir()
        except Exception:
            return None

    def _find_latest_snapshot(self, d: Path) -> Path | None:
        candidates = sorted(d.glob("daily-*.json"), reverse=True)
        return candidates[0] if candidates else None

    def _expected_range(self, metric_key: str) -> tuple[float, float]:
        ranges: dict[str, tuple[float, float]] = {
            "test_count": (0, 5000),
            "code_files": (0, 500),
            "dependency_count": (0, 50),
        }
        return ranges.get(metric_key, (0, 10000))

    def _make_signal(
        self,
        signal_type: str,
        entity_hint: str = "",
        details: dict[str, Any] | None = None,
    ):
        if HAS_ONTOLOGIA:
            return RawSignal(
                sensor_name=self.name,
                signal_type=signal_type,
                entity_id=entity_hint,
                details=details or {},
                timestamp=_now_iso(),
            )
        return {
            "sensor": self.name,
            "type": signal_type,
            "entity": entity_hint,
            "details": details or {},
            "timestamp": _now_iso(),
        }


# ---------------------------------------------------------------------------
# CISensor
# ---------------------------------------------------------------------------

class CISensor:
    """Watches CI health data for workflow issues."""

    def __init__(
        self,
        registry_path: Path | None = None,
        snapshot_dir: Path | None = None,
    ) -> None:
        self._registry_path = registry_path
        self._snapshot_dir = snapshot_dir

    @property
    def name(self) -> str:
        return "ci_sensor"

    def is_available(self) -> bool:
        path = self._resolve_registry_path()
        return path is not None and path.is_file()

    def scan(self) -> list:
        path = self._resolve_registry_path()
        if path is None or not path.is_file():
            return []

        registry = _load_json(path)
        if not isinstance(registry, dict):
            return []

        signals = []
        for _organ_key, organ_data in registry.get("organs", {}).items():
            for repo in organ_data.get("repositories", []):
                name = repo.get("name", "")
                tier = repo.get("tier", "")
                ci = repo.get("ci_workflow", "")
                status = repo.get("promotion_status", "")

                if status == "ARCHIVED":
                    continue

                # Missing CI on non-infrastructure repos
                if not ci and tier not in ("infrastructure", "archive"):
                    signals.append(self._make_signal(
                        "missing_ci",
                        entity_hint=name,
                        details={
                            "repo": name,
                            "tier": tier,
                            "organ": organ_data.get("name", ""),
                        },
                    ))

                # Stale validation (>30 days since last_validated)
                last_v = repo.get("last_validated", "")
                if last_v and self._is_stale(last_v, days=30):
                    signals.append(self._make_signal(
                        "stale_validation",
                        entity_hint=name,
                        details={
                            "repo": name,
                            "last_validated": last_v,
                        },
                    ))

        return signals

    def _resolve_registry_path(self) -> Path | None:
        if self._registry_path:
            return self._registry_path
        try:
            from organvm_engine.paths import registry_path
            return registry_path()
        except Exception:
            return None

    def _is_stale(self, date_str: str, days: int) -> bool:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - dt
            return delta.days > days
        except (ValueError, TypeError):
            return False

    def _make_signal(
        self,
        signal_type: str,
        entity_hint: str = "",
        details: dict[str, Any] | None = None,
    ):
        if HAS_ONTOLOGIA:
            return RawSignal(
                sensor_name=self.name,
                signal_type=signal_type,
                entity_id=entity_hint,
                details=details or {},
                timestamp=_now_iso(),
            )
        return {
            "sensor": self.name,
            "type": signal_type,
            "entity": entity_hint,
            "details": details or {},
            "timestamp": _now_iso(),
        }


# ---------------------------------------------------------------------------
# PromotionSensor
# ---------------------------------------------------------------------------

class PromotionSensor:
    """Evaluates promotion readiness across all repos."""

    def __init__(
        self,
        registry_path: Path | None = None,
        snapshot_dir: Path | None = None,
    ) -> None:
        self._registry_path = registry_path
        self._snapshot_dir = snapshot_dir

    @property
    def name(self) -> str:
        return "promotion_sensor"

    def is_available(self) -> bool:
        path = self._resolve_registry_path()
        return path is not None and path.is_file()

    def scan(self) -> list:
        path = self._resolve_registry_path()
        if path is None or not path.is_file():
            return []

        registry = _load_json(path)
        if not isinstance(registry, dict):
            return []

        signals = []
        for _organ_key, organ_data in registry.get("organs", {}).items():
            for repo in organ_data.get("repositories", []):
                name = repo.get("name", "")
                status = repo.get("promotion_status", "")
                ci = repo.get("ci_workflow", "")
                platinum = repo.get("platinum_status", False)
                impl = repo.get("implementation_status", "")

                if status == "ARCHIVED":
                    continue

                # Ready-to-promote: CANDIDATE with all criteria met
                if status == "CANDIDATE" and ci and platinum and impl == "ACTIVE":
                    signals.append(self._make_signal(
                        "ready_to_promote",
                        entity_hint=name,
                        details={
                            "repo": name,
                            "current_status": status,
                            "target": "PUBLIC_PROCESS",
                            "organ": organ_data.get("name", ""),
                        },
                    ))

                # Blocked: CANDIDATE missing criteria
                if status == "CANDIDATE" and not (ci and platinum and impl == "ACTIVE"):
                    missing = []
                    if not ci:
                        missing.append("ci_workflow")
                    if not platinum:
                        missing.append("platinum_status")
                    if impl != "ACTIVE":
                        missing.append(f"implementation_status={impl}")
                    signals.append(self._make_signal(
                        "promotion_blocked",
                        entity_hint=name,
                        details={
                            "repo": name,
                            "current_status": status,
                            "missing": missing,
                        },
                    ))

                # Stale CANDIDATE (>90 days with no progress)
                last_v = repo.get("last_validated", "")
                if status == "CANDIDATE" and last_v:
                    try:
                        dt = datetime.fromisoformat(
                            last_v.replace("Z", "+00:00"),
                        )
                        delta = datetime.now(timezone.utc) - dt
                        if delta.days > 90:
                            signals.append(self._make_signal(
                                "stale_candidate",
                                entity_hint=name,
                                details={
                                    "repo": name,
                                    "days_since_validation": delta.days,
                                },
                            ))
                    except (ValueError, TypeError):
                        pass

        return signals

    def _resolve_registry_path(self) -> Path | None:
        if self._registry_path:
            return self._registry_path
        try:
            from organvm_engine.paths import registry_path
            return registry_path()
        except Exception:
            return None

    def _make_signal(
        self,
        signal_type: str,
        entity_hint: str = "",
        details: dict[str, Any] | None = None,
    ):
        if HAS_ONTOLOGIA:
            return RawSignal(
                sensor_name=self.name,
                signal_type=signal_type,
                entity_id=entity_hint,
                details=details or {},
                timestamp=_now_iso(),
            )
        return {
            "sensor": self.name,
            "type": signal_type,
            "entity": entity_hint,
            "details": details or {},
            "timestamp": _now_iso(),
        }


# ---------------------------------------------------------------------------
# Aggregate scan
# ---------------------------------------------------------------------------

ALL_SENSORS = [RegistrySensor, SoakSensor, CISensor, PromotionSensor]


def scan_all(
    registry_path: Path | None = None,
    soak_dir: Path | None = None,
    snapshot_dir: Path | None = None,
    sensor_filter: str | None = None,
) -> dict[str, list]:
    """Run all (or filtered) sensors and return grouped signals.

    Returns:
        {sensor_name: [signals...]}
    """
    results: dict[str, list] = {}
    sensor_map = {
        "registry_sensor": lambda: RegistrySensor(registry_path, snapshot_dir),
        "soak_sensor": lambda: SoakSensor(soak_dir, snapshot_dir),
        "ci_sensor": lambda: CISensor(registry_path, snapshot_dir),
        "promotion_sensor": lambda: PromotionSensor(registry_path, snapshot_dir),
    }

    for sensor_name, factory in sensor_map.items():
        if sensor_filter and sensor_name != sensor_filter:
            continue
        sensor = factory()
        if sensor.is_available():
            results[sensor_name] = sensor.scan()

    return results


def normalize_signals(signals: list) -> list:
    """Convert RawSignals (or dicts) to NormalizedChange objects.

    Best-effort: maps signal_type to ChangeType, preserves entity_id.
    """
    if not HAS_ONTOLOGIA:
        return signals

    changes: list[NormalizedChange] = []
    type_map = {
        "repo_added": ChangeType.STATE,
        "repo_removed": ChangeType.STATE,
        "field_changed": ChangeType.STATE,
        "validation_failure": ChangeType.ANOMALY,
        "metric_anomaly": ChangeType.ANOMALY,
        "missing_ci": ChangeType.STATE,
        "stale_validation": ChangeType.ANOMALY,
        "ready_to_promote": ChangeType.STATE,
        "promotion_blocked": ChangeType.STATE,
        "stale_candidate": ChangeType.ANOMALY,
    }
    for sig in signals:
        if isinstance(sig, RawSignal):
            change_type = type_map.get(sig.signal_type, ChangeType.STATE)
            changes.append(NormalizedChange(
                change_type=change_type,
                entity_id=sig.entity_id or "",
                property_name=sig.signal_type,
                new_value=sig.details,
                confidence=sig.confidence,
                source_sensor=sig.sensor_name,
                timestamp=sig.timestamp,
            ))
    return changes
