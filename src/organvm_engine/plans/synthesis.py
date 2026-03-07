"""Plan synthesis — aggregate repo-level plans into per-organ strategic views."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from organvm_engine.plans.index import PlanEntry


@dataclass
class OrganPlanSummary:
    """Aggregated plan metrics for a single organ."""

    organ_key: str
    total_plans: int = 0
    active_plans: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    completion_pct: float = 0.0
    agents_active: list[str] = field(default_factory=list)
    top_tags: list[str] = field(default_factory=list)
    cross_organ_refs: list[str] = field(default_factory=list)
    stale_count: int = 0


def synthesize_organ(
    organ_key: str,
    entries: list["PlanEntry"],
    stale_days: int = 30,
) -> OrganPlanSummary:
    """Synthesize plan metrics for a single organ from its PlanEntry list."""
    from collections import Counter
    from datetime import datetime, timezone

    summary = OrganPlanSummary(organ_key=organ_key)
    summary.total_plans = len(entries)
    summary.active_plans = sum(1 for e in entries if e.status == "active")
    summary.total_tasks = sum(e.task_count for e in entries)
    summary.completed_tasks = sum(e.completed_count for e in entries)

    if summary.total_tasks > 0:
        summary.completion_pct = round(
            summary.completed_tasks / summary.total_tasks * 100, 1,
        )

    summary.agents_active = sorted(set(e.agent for e in entries))

    # Top tags across all plans in this organ
    tag_counter: Counter[str] = Counter()
    for e in entries:
        tag_counter.update(e.tags)
    summary.top_tags = [t for t, _ in tag_counter.most_common(10)]

    # Cross-organ references: organs mentioned in file_refs
    from organvm_engine.organ_config import organ_dir_map

    dir_map = organ_dir_map()
    dir_to_key = {v: k for k, v in dir_map.items()}
    xrefs: set[str] = set()
    for e in entries:
        for ref in e.file_refs:
            for organ_dir, key in dir_to_key.items():
                if ref.startswith(organ_dir + "/") and key != organ_key:
                    xrefs.add(key)
    summary.cross_organ_refs = sorted(xrefs)

    # Stale count
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for e in entries:
        if e.status != "active" or e.completed_count > 0 or e.task_count == 0:
            continue
        try:
            age = (
                datetime.strptime(today, "%Y-%m-%d")
                - datetime.strptime(e.date, "%Y-%m-%d")
            ).days
            if age > stale_days:
                summary.stale_count += 1
        except ValueError:
            continue

    return summary


def synthesize_all(
    entries: list["PlanEntry"],
    stale_days: int = 30,
) -> dict[str, OrganPlanSummary]:
    """Synthesize plan summaries for all organs represented in entries."""
    by_organ: dict[str, list["PlanEntry"]] = {}
    for e in entries:
        key = e.organ or "unknown"
        by_organ.setdefault(key, []).append(e)

    return {
        key: synthesize_organ(key, organ_entries, stale_days)
        for key, organ_entries in sorted(by_organ.items())
    }
