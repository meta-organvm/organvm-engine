"""Time-series analysis from soak-test snapshots."""

import json
from pathlib import Path

DEFAULT_SOAK_DIR = (
    Path.home() / "Workspace" / "meta-organvm" / "organvm-corpvs-testamentvm" / "data" / "soak-test"
)


def load_snapshots(soak_dir: Path | str | None = None) -> list[dict]:
    """Load all daily soak test snapshots, sorted by date.

    Args:
        soak_dir: Directory containing daily-*.json files.

    Returns:
        List of snapshot dicts sorted by date.
    """
    d = Path(soak_dir) if soak_dir else DEFAULT_SOAK_DIR
    if not d.is_dir():
        return []

    snapshots = []
    for path in sorted(d.glob("daily-*.json")):
        with open(path) as f:
            snapshots.append(json.load(f))

    return snapshots


def ci_trend(snapshots: list[dict]) -> list[dict]:
    """Extract CI pass rate trend from snapshots.

    Returns:
        List of {date, passing, failing, total, rate} dicts.
    """
    trend = []
    for snap in snapshots:
        ci = snap.get("ci", {})
        total = ci.get("total_checked", 0)
        passing = ci.get("passing", 0)
        failing = ci.get("failing", 0)
        rate = passing / total if total > 0 else 0.0
        trend.append({
            "date": snap.get("date", "?"),
            "passing": passing,
            "failing": failing,
            "total": total,
            "rate": round(rate, 3),
        })
    return trend


def engagement_trend(snapshots: list[dict]) -> list[dict]:
    """Extract engagement trend from snapshots.

    Returns:
        List of {date, stars, forks} dicts.
    """
    trend = []
    for snap in snapshots:
        eng = snap.get("engagement", {})
        trend.append({
            "date": snap.get("date", "?"),
            "stars": eng.get("total_stars", 0),
            "forks": eng.get("total_forks", 0),
        })
    return trend
