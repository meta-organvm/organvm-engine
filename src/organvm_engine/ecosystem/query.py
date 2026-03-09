"""Query across all ecosystem profiles.

Functions for building coverage matrices, finding gaps,
aggregating next-actions, and summarizing status.
"""

from __future__ import annotations

from organvm_engine.ecosystem.reader import get_pillars
from organvm_engine.ecosystem.taxonomy import DEFAULT_PILLARS


def coverage_matrix(ecosystems: list[dict]) -> dict[str, dict]:
    """Product x Pillar matrix showing arm counts and statuses.

    Returns:
        {repo: {pillar: {total: N, live: N, planned: N, ...}}}
    """
    matrix: dict[str, dict] = {}
    for eco in ecosystems:
        repo = eco.get("repo", "unknown")
        pillars = get_pillars(eco)
        repo_coverage: dict[str, dict] = {}
        for pillar_name, arms in pillars.items():
            status_counts: dict[str, int] = {}
            for arm in arms:
                s = arm.get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            repo_coverage[pillar_name] = {
                "total": len(arms),
                **status_counts,
            }
        matrix[repo] = repo_coverage
    return matrix


def pillar_view(ecosystems: list[dict], pillar: str) -> dict[str, list[dict]]:
    """All products' arms for one pillar.

    For cross-product comparison, e.g., 'show me all revenue
    arms across all products'.

    Returns:
        {repo: [arm, arm, ...]}
    """
    view: dict[str, list[dict]] = {}
    for eco in ecosystems:
        repo = eco.get("repo", "unknown")
        pillars = get_pillars(eco)
        arms = pillars.get(pillar, [])
        if arms:
            view[repo] = arms
    return view


def gaps(ecosystem: dict) -> list[str]:
    """What's missing? Compares against DEFAULT_PILLARS suggestions.

    Returns human-readable gap descriptions, not errors.
    These are suggestions — products can intentionally skip pillars.
    """
    gap_list: list[str] = []
    pillars = get_pillars(ecosystem)

    for pillar_name, pillar_info in DEFAULT_PILLARS.items():
        if pillar_name not in pillars:
            gap_list.append(
                f"Missing pillar '{pillar_name}': {pillar_info['description']}",
            )
        else:
            arms = pillars[pillar_name]
            if not arms:
                gap_list.append(f"Pillar '{pillar_name}' has no arms defined")
            else:
                all_not_started = all(
                    a.get("status") == "not_started" for a in arms
                )
                if all_not_started:
                    gap_list.append(
                        f"Pillar '{pillar_name}' has {len(arms)} arms but all are not_started",
                    )

    return gap_list


def next_actions(ecosystems: list[dict]) -> list[dict]:
    """Aggregate all next_action fields across all products.

    Returns prioritized action list for the human.
    """
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "deferred": 4}
    actions: list[dict] = []

    for eco in ecosystems:
        repo = eco.get("repo", "unknown")
        pillars = get_pillars(eco)
        for pillar_name, arms in pillars.items():
            for arm in arms:
                na = arm.get("next_action")
                if na:
                    actions.append({
                        "repo": repo,
                        "pillar": pillar_name,
                        "platform": arm.get("platform", "unknown"),
                        "status": arm.get("status", "unknown"),
                        "priority": arm.get("priority", "medium"),
                        "next_action": na,
                        "target_date": arm.get("target_date"),
                    })

    actions.sort(key=lambda a: priority_order.get(a["priority"], 99))
    return actions


def status_summary(ecosystems: list[dict]) -> dict:
    """System-wide: how many arms are live, planned, not_started, etc."""
    counts: dict[str, int] = {}
    total_arms = 0
    total_products = len(ecosystems)
    total_pillars = 0

    pillar_names: set[str] = set()

    for eco in ecosystems:
        pillars = get_pillars(eco)
        for pillar_name, arms in pillars.items():
            pillar_names.add(pillar_name)
            total_pillars += 1
            for arm in arms:
                total_arms += 1
                s = arm.get("status", "unknown")
                counts[s] = counts.get(s, 0) + 1

    return {
        "total_products": total_products,
        "total_pillars": total_pillars,
        "unique_pillar_names": sorted(pillar_names),
        "total_arms": total_arms,
        "by_status": counts,
    }
