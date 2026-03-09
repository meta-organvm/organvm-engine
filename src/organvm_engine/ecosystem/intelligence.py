"""Snapshot and intelligence artifact I/O for pillar workspaces.

Manages date-stamped snapshots (append-only) and living intelligence
files within each repo's ecosystem/ directory.

Directory layout:
    ecosystem/
        snapshots/<pillar>/YYYY-MM-DD--<name>.yaml
        intelligence/<pillar>/<artifact>.yaml
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

SNAPSHOTS_DIR = "ecosystem/snapshots"
INTELLIGENCE_DIR = "ecosystem/intelligence"


def write_snapshot(
    repo_path: Path | str,
    pillar: str,
    data: dict,
    snapshot_name: str = "landscape",
    snapshot_date: date | None = None,
) -> Path:
    """Write a date-stamped snapshot (append-only — never overwrites).

    Returns the path written.
    """
    d = snapshot_date or date.today()
    snap_dir = Path(repo_path) / SNAPSHOTS_DIR / pillar
    snap_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{d.isoformat()}--{snapshot_name}.yaml"
    snap_path = snap_dir / filename
    with snap_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return snap_path


def list_snapshots(
    repo_path: Path | str,
    pillar: str,
) -> list[tuple[str, Path]]:
    """List snapshots for a pillar, sorted by date (newest first).

    Returns list of (date_string, path) tuples.
    """
    snap_dir = Path(repo_path) / SNAPSHOTS_DIR / pillar
    if not snap_dir.is_dir():
        return []

    results: list[tuple[str, Path]] = []
    for p in snap_dir.iterdir():
        if p.is_file() and p.suffix in (".yaml", ".yml"):
            # Extract date from filename: YYYY-MM-DD--name.yaml
            date_part = p.stem.split("--")[0] if "--" in p.stem else p.stem
            results.append((date_part, p))

    return sorted(results, key=lambda x: x[0], reverse=True)


def read_snapshot(
    repo_path: Path | str,
    pillar: str,
    snapshot_date: str,
) -> dict | None:
    """Read a specific snapshot by date prefix.

    Returns None if not found.
    """
    snap_dir = Path(repo_path) / SNAPSHOTS_DIR / pillar
    if not snap_dir.is_dir():
        return None

    for p in snap_dir.iterdir():
        if p.is_file() and p.name.startswith(snapshot_date):
            with p.open() as f:
                return yaml.safe_load(f)
    return None


def latest_snapshot(
    repo_path: Path | str,
    pillar: str,
) -> dict | None:
    """Read the most recent snapshot for a pillar."""
    snaps = list_snapshots(repo_path, pillar)
    if not snaps:
        return None
    _, path = snaps[0]
    with path.open() as f:
        return yaml.safe_load(f)


def read_intelligence(
    repo_path: Path | str,
    pillar: str,
    artifact_name: str,
) -> dict | None:
    """Read a living intelligence artifact.

    Returns None if not found.
    """
    intel_dir = Path(repo_path) / INTELLIGENCE_DIR / pillar
    for suffix in (".yaml", ".yml"):
        path = intel_dir / f"{artifact_name}{suffix}"
        if path.is_file():
            with path.open() as f:
                return yaml.safe_load(f)
    return None


def write_intelligence(
    repo_path: Path | str,
    pillar: str,
    artifact_name: str,
    data: dict,
) -> Path:
    """Write a living intelligence artifact.

    Returns the path written.
    """
    intel_dir = Path(repo_path) / INTELLIGENCE_DIR / pillar
    intel_dir.mkdir(parents=True, exist_ok=True)
    path = intel_dir / f"{artifact_name}.yaml"
    with path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return path


def staleness_report(repo_path: Path | str) -> list[dict]:
    """Check all pillar DNA artifacts against staleness thresholds.

    Reads pillar-dna/*.yaml to find artifact definitions and their
    staleness_days, then checks snapshots/intelligence for freshness.

    Returns a list of stale artifact dicts with pillar, name, days_stale.
    """
    from organvm_engine.ecosystem.pillar_dna import list_pillar_dnas, read_pillar_dna

    repo = Path(repo_path)
    stale: list[dict] = []
    today = date.today()

    for pillar in list_pillar_dnas(repo):
        dna = read_pillar_dna(repo, pillar)
        if not dna:
            continue

        artifacts = dna.get("artifacts", [])
        if not isinstance(artifacts, list):
            continue

        for art in artifacts:
            if not isinstance(art, dict):
                continue
            name = art.get("name", "")
            staleness_days = art.get("staleness_days")
            if not staleness_days or not isinstance(staleness_days, int):
                continue

            # Check snapshots for this artifact
            snaps = list_snapshots(repo, pillar)
            most_recent_date: date | None = None

            for date_str, _ in snaps:
                try:
                    snap_date = date.fromisoformat(date_str)
                    if most_recent_date is None or snap_date > most_recent_date:
                        most_recent_date = snap_date
                except ValueError:
                    continue

            if most_recent_date is None:
                stale.append({
                    "pillar": pillar,
                    "artifact": name,
                    "staleness_days": staleness_days,
                    "days_stale": None,
                    "status": "missing",
                })
            else:
                age = (today - most_recent_date).days
                if age > staleness_days:
                    stale.append({
                        "pillar": pillar,
                        "artifact": name,
                        "staleness_days": staleness_days,
                        "days_stale": age,
                        "status": "stale",
                    })

    return stale
