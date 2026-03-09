"""Generate Markdown summary report from atomized tasks."""

from __future__ import annotations

import datetime
from collections import Counter


def generate_summary(tasks: list[dict], plans_parsed: int) -> str:
    """Generate ATOMIZED-SUMMARY.md content from a list of task dicts."""
    lines = [
        "# Plan Atomization Summary",
        f"**Generated**: {datetime.date.today().isoformat()}",
        f"**Plans parsed**: {plans_parsed} | **Tasks extracted**: {len(tasks)}",
        "",
    ]

    # By Project
    project_stats: dict[str, dict] = {}
    for t in tasks:
        slug = t["project"]["slug"]
        if slug not in project_stats:
            project_stats[slug] = {
                "plans": set(), "tasks": 0, "completed": 0,
                "pending": 0, "in_progress": 0,
            }
        project_stats[slug]["plans"].add(t["source"]["file"])
        project_stats[slug]["tasks"] += 1
        project_stats[slug][t["status"]] = project_stats[slug].get(t["status"], 0) + 1

    lines.append("## By Project")
    lines.append("")
    lines.append("| Project | Plans | Tasks | Completed | Pending | In Progress |")
    lines.append("|---------|-------|-------|-----------|---------|-------------|")
    for slug in sorted(project_stats):
        s = project_stats[slug]
        lines.append(
            f"| {slug} | {len(s['plans'])} | {s['tasks']} | "
            f"{s.get('completed', 0)} | {s.get('pending', 0)} | "
            f"{s.get('in_progress', 0)} |",
        )
    lines.append("")

    # By Task Type
    type_counts = Counter(t["task_type"] for t in tasks)
    total = len(tasks) or 1
    lines.append("## By Task Type")
    lines.append("")
    lines.append("| Type | Count | % |")
    lines.append("|------|-------|---|")
    for ttype, count in type_counts.most_common():
        lines.append(f"| {ttype} | {count} | {count * 100 // total}% |")
    lines.append("")

    # By Status
    status_counts = Counter(t["status"] for t in tasks)
    lines.append("## By Status")
    lines.append("")
    lines.append("| Status | Count | % |")
    lines.append("|--------|-------|---|")
    for status, count in status_counts.most_common():
        lines.append(f"| {status} | {count} | {count * 100 // total}% |")
    lines.append("")

    # Largest Plans
    plan_task_counts: dict[str, dict] = {}
    for t in tasks:
        key = t["source"]["file"]
        if key not in plan_task_counts:
            plan_task_counts[key] = {
                "project": t["project"]["slug"],
                "total": 0,
                "completed": 0,
                "title": t["source"]["plan_title"],
            }
        plan_task_counts[key]["total"] += 1
        if t["status"] == "completed":
            plan_task_counts[key]["completed"] += 1

    lines.append("## Largest Plans (by task count)")
    lines.append("")
    lines.append("| Plan | Project | Tasks | Completed % |")
    lines.append("|------|---------|-------|-------------|")
    top_plans = sorted(
        plan_task_counts.items(), key=lambda x: x[1]["total"], reverse=True,
    )[:20]
    for _plan_file, info in top_plans:
        pct = (
            f"{info['completed'] * 100 // info['total']}%"
            if info["total"] > 0
            else "0%"
        )
        title_short = info["title"][:50]
        lines.append(
            f"| {title_short} | {info['project']} | {info['total']} | {pct} |",
        )
    lines.append("")

    # By Agent
    agent_counts = Counter(t.get("agent", "claude") for t in tasks)
    if len(agent_counts) > 1 or "claude" not in agent_counts:
        lines.append("## By Agent")
        lines.append("")
        lines.append("| Agent | Count | % |")
        lines.append("|-------|-------|---|")
        for agent, count in agent_counts.most_common():
            lines.append(f"| {agent} | {count} | {count * 100 // total}% |")
        lines.append("")

    # By Organ
    organ_counts = Counter(
        t.get("project", {}).get("organ") or "unknown" for t in tasks
    )
    if any(o != "unknown" for o in organ_counts):
        lines.append("## By Organ")
        lines.append("")
        lines.append("| Organ | Count | % |")
        lines.append("|-------|-------|---|")
        for o, count in organ_counts.most_common():
            lines.append(f"| {o} | {count} | {count * 100 // total}% |")
        lines.append("")

    # Non-Actionable Documents
    non_actionable = [t for t in tasks if not t["actionable"]]
    if non_actionable:
        seen_plans: set[str] = set()
        lines.append("## Non-Actionable Documents")
        lines.append("")
        lines.append("| Plan | Project | Classification |")
        lines.append("|------|---------|----------------|")
        for t in non_actionable:
            key = t["source"]["file"]
            if key not in seen_plans:
                seen_plans.add(key)
                lines.append(
                    f"| {t['source']['plan_title'][:50]} | "
                    f"{t['project']['slug']} | {t['task_type']} |",
                )
        lines.append("")

    return "\n".join(lines)
