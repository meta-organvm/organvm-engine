"""Compute system-wide metrics from registry."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.registry.query import all_repos


def compute_metrics(registry: dict) -> dict:
    """Derive all computable metrics from registry-v2.json.

    Args:
        registry: Loaded registry dict.

    Returns:
        Dict with computed metrics (total_repos, per_organ, status distribution, etc.).
    """
    organs = registry.get("organs", {})
    repos = []
    per_organ = {}

    for organ_key, organ_data in organs.items():
        organ_repos = organ_data.get("repositories", [])
        repos.extend(organ_repos)
        per_organ[organ_key] = {
            "name": organ_data.get("name", organ_key),
            "repos": len(organ_repos),
        }

    status_dist: dict[str, int] = defaultdict(int)
    ci_count = 0
    dep_count = 0

    for repo in repos:
        status_dist[repo.get("implementation_status", "UNKNOWN")] += 1
        if repo.get("ci_workflow"):
            ci_count += 1
        dep_count += len(repo.get("dependencies", []))

    operational = sum(
        1 for o in organs.values()
        if o.get("launch_status") == "OPERATIONAL"
    )

    return {
        "total_repos": len(repos),
        "active_repos": status_dist.get("ACTIVE", 0),
        "archived_repos": status_dist.get("ARCHIVED", 0),
        "total_organs": len(organs),
        "operational_organs": operational,
        "ci_workflows": ci_count,
        "dependency_edges": dep_count,
        "per_organ": per_organ,
        "implementation_status": dict(sorted(status_dist.items())),
    }


def write_metrics(
    computed: dict,
    output_path: Path | str,
    manual: dict | None = None,
) -> None:
    """Write system-metrics.json with computed and manual sections.

    Args:
        computed: Computed metrics dict.
        output_path: Output file path.
        manual: Manual section to preserve. Loaded from existing file if None.
    """
    out = Path(output_path)

    if manual is None:
        # Preserve existing manual section
        if out.exists():
            with open(out) as f:
                existing = json.load(f)
            manual = existing.get("manual", {})
        else:
            manual = {
                "_note": "Edit these by hand. calculate-metrics.py preserves this section.",
            }

    metrics = {
        "schema_version": "1.0",
        "generated": datetime.now(timezone.utc).isoformat(),
        "computed": computed,
        "manual": manual,
    }

    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")
