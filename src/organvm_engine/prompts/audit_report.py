"""Render audit results to Markdown."""

from __future__ import annotations

import datetime


def generate_audit_report(results: dict) -> str:
    """Produce AUDIT-REPORT.md content from audit results dict."""
    lines: list[str] = []
    noise = results.get("noise", {})
    completion = results.get("completion", {})
    effectiveness = results.get("effectiveness", {})
    sessions = results.get("sessions", {})
    links = results.get("links", {})
    recommendations = results.get("recommendations", [])

    # ── Executive Summary ───────────────────────────────────
    funnel = completion.get("funnel_summary", {})
    lines.append("# Prompt & Pipeline Data Audit")
    lines.append(f"**Generated**: {datetime.date.today().isoformat()}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Prompts analyzed**: {noise.get('total', 0)}")
    lines.append(f"- **Signal prompts**: {noise.get('signal_count', 0)} "
                 f"({100 - noise.get('noise_pct', 0):.0f}%)")
    lines.append(f"- **Noise prompts**: {noise.get('noise_count', 0)} "
                 f"({noise.get('noise_pct', 0)}%)")
    lines.append(f"- **Tasks**: {funnel.get('total_tasks', 0)} "
                 f"(completion: {funnel.get('completion_rate', 0)}%)")
    lines.append(f"- **Links**: {links.get('total_links', 0)} "
                 f"(empty-FP contamination: {links.get('empty_fp_pct', 0)}%)")
    lines.append(f"- **Sessions**: {sessions.get('total_sessions', 0)}")
    lines.append(f"- **Recommendations**: {len(recommendations)} "
                 f"({sum(1 for r in recommendations if r.get('priority') == 'P0')} P0)")
    lines.append("")

    # Health grade
    p0_count = sum(1 for r in recommendations if r.get("priority") == "P0")
    if p0_count == 0:
        grade = "A"
    elif p0_count <= 2:
        grade = "B"
    elif p0_count <= 4:
        grade = "C"
    else:
        grade = "D"
    lines.append(f"**Overall Health Grade: {grade}**")
    lines.append("")

    # ── Data Quality ────────────────────────────────────────
    lines.append("## Data Quality")
    lines.append("")
    lines.append("| Noise Type | Count |")
    lines.append("|------------|-------|")
    for ntype, count in sorted(
        noise.get("noise_by_type", {}).items(), key=lambda x: -x[1],
    ):
        lines.append(f"| {ntype} | {count} |")
    lines.append("")

    # ── Completion Funnel ───────────────────────────────────
    lines.append("## Completion Funnel")
    lines.append("")
    lines.append("| Stage | Count |")
    lines.append("|-------|-------|")
    lines.append(f"| Plans parsed | {funnel.get('plans_parsed', 0)} |")
    lines.append(f"| Tasks extracted | {funnel.get('total_tasks', 0)} |")
    lines.append(f"| Tasks with links | {funnel.get('tasks_with_links', 0)} |")
    lines.append(f"| Tasks with HQ links (J>=0.30) | {funnel.get('tasks_with_hq_links', 0)} |")
    lines.append(f"| Completed tasks | {funnel.get('completed_tasks', 0)} |")
    lines.append("")
    lines.append(f"**Completion rate**: {funnel.get('completion_rate', 0)}%")
    lines.append(f"**Linkage rate (J>=0.30)**: {funnel.get('linkage_rate', 0)}%")
    lines.append("")

    # By organ
    by_organ = completion.get("by_organ", {})
    if by_organ:
        lines.append("### By Organ")
        lines.append("")
        lines.append("| Organ | Tasks | Completed | HQ Linked | Plans |")
        lines.append("|-------|-------|-----------|-----------|-------|")
        for organ, info in sorted(by_organ.items()):
            lines.append(
                f"| {organ} | {info['total']} | {info['completed']} | "
                f"{info['hq_linked']} | {info['plans']} |",
            )
        lines.append("")

    # Ghost plans
    ghosts = completion.get("ghost_plans", [])
    if ghosts:
        lines.append(f"### Ghost Plans ({completion.get('ghost_plan_count', 0)} total)")
        lines.append("")
        lines.append("Plans with tasks but 0 completion and 0 high-quality links:")
        lines.append("")
        lines.append("| Plan | Tasks |")
        lines.append("|------|-------|")
        for g in ghosts[:20]:
            plan_name = g["plan"].rsplit("/", 1)[-1] if "/" in g["plan"] else g["plan"]
            lines.append(f"| {plan_name} | {g['tasks']} |")
        lines.append("")

    # ── Prompt Effectiveness ────────────────────────────────
    lines.append("## Prompt Effectiveness")
    lines.append("")

    by_type = effectiveness.get("by_type", {})
    if by_type:
        lines.append("### By Prompt Type")
        lines.append("")
        lines.append("| Type | Prompts | Linked Tasks | Completed |")
        lines.append("|------|---------|-------------|-----------|")
        for ptype, info in sorted(by_type.items(), key=lambda x: -x[1]["prompts"]):
            lines.append(
                f"| {ptype} | {info['prompts']} | "
                f"{info['linked_tasks']} | {info['completed_tasks']} |",
            )
        lines.append("")

    by_size = effectiveness.get("by_size", {})
    if by_size:
        lines.append("### By Size Class")
        lines.append("")
        lines.append("| Size | Prompts | Linked Tasks | Completed |")
        lines.append("|------|---------|-------------|-----------|")
        for sclass, info in sorted(by_size.items()):
            lines.append(
                f"| {sclass} | {info['prompts']} | "
                f"{info['linked_tasks']} | {info['completed_tasks']} |",
            )
        lines.append("")

    spec = effectiveness.get("specificity_analysis", {})
    if spec:
        lines.append("### Specificity Analysis")
        lines.append("")
        lines.append("| Specificity | Linked Tasks | Completed |")
        lines.append("|-------------|-------------|-----------|")
        for level in ("high", "low"):
            info = spec.get(level, {})
            lines.append(f"| {level} | {info.get('total', 0)} | {info.get('completed', 0)} |")
        lines.append("")

    corr = effectiveness.get("correction_analysis", {})
    if corr:
        hi_corr = corr.get('threads_with_high_correction', 0)
        total_t = corr.get('total_threads', 0)
        lines.append(
            f"**Correction rate**: {corr.get('correction_rate', 0)}%"
            f" of threads ({hi_corr}/{total_t})",
        )
        lines.append("")

    # ── Session Patterns ────────────────────────────────────
    lines.append("## Session Patterns")
    lines.append("")

    length_dist = sessions.get("length_dist", {})
    if length_dist:
        lines.append("### Session Length")
        lines.append("")
        lines.append("| Prompts per Session | Count |")
        lines.append("|---------------------|-------|")
        for bucket, count in length_dist.items():
            lines.append(f"| {bucket} | {count} |")
        lines.append("")

    dur_dist = sessions.get("duration_dist", {})
    if dur_dist:
        lines.append("### Session Duration")
        lines.append("")
        lines.append("| Duration | Count |")
        lines.append("|----------|-------|")
        for bucket, count in dur_dist.items():
            lines.append(f"| {bucket} | {count} |")
        lines.append("")

    lines.append(f"**Productive sessions** (ending with git_ops): "
                 f"{sessions.get('productive_sessions', 0)} "
                 f"({sessions.get('productive_pct', 0)}%)")
    lines.append("")

    ctx = sessions.get("context_switches", {})
    lines.append(f"**Avg projects/day**: {ctx.get('avg_projects_per_day', 0)} | "
                 f"**Max**: {ctx.get('max_projects_in_day', 0)}")
    lines.append("")

    churn = sessions.get("churn", {})
    lines.append(f"**Session churn**: {churn.get('churn_ratio', 0)}% single-prompt "
                 f"({churn.get('single_prompt_sessions', 0)}/{sessions.get('total_sessions', 0)})")
    lines.append("")

    hourly = sessions.get("hourly", {})
    if hourly:
        lines.append("### Hourly Distribution")
        lines.append("")
        lines.append("| Hour | Prompts |")
        lines.append("|------|---------|")
        for hour in range(24):
            count = hourly.get(str(hour), hourly.get(hour, 0))
            if count:
                lines.append(f"| {hour:02d}:00 | {count} |")
        lines.append("")

    # ── Linking Quality ─────────────────────────────────────
    lines.append("## Linking Quality")
    lines.append("")
    lines.append(f"**Total links**: {links.get('total_links', 0)}")
    lines.append(f"**Empty-fingerprint contamination**: {links.get('empty_fp_count', 0)} "
                 f"({links.get('empty_fp_pct', 0)}%)")
    lines.append(f"**Generic-tag-only links**: {links.get('generic_tag_links', 0)} "
                 f"({links.get('generic_tag_pct', 0)}%)")
    lines.append(f"**High fan-out tasks (>100 links)**: {links.get('high_fanout_count', 0)}")
    lines.append("")

    threshold = links.get("threshold_analysis", {})
    if threshold:
        lines.append("### Threshold Analysis")
        lines.append("")
        lines.append("| Jaccard >= | Links | Tasks w/ Links | % of Total |")
        lines.append("|-----------|-------|----------------|------------|")
        for t, info in sorted(threshold.items()):
            lines.append(
                f"| {t} | {info['links']} | "
                f"{info['tasks_with_links']} | {info['pct_of_total']}% |",
            )
        lines.append("")

    # ── Recommendations ─────────────────────────────────────
    lines.append("## Recommendations")
    lines.append("")
    if recommendations:
        lines.append("| Priority | Category | Finding | Recommendation |")
        lines.append("|----------|----------|---------|----------------|")
        for rec in recommendations:
            lines.append(
                f"| {rec['priority']} | {rec['category']} | "
                f"{rec['finding']} | {rec['recommendation']} |",
            )
    else:
        lines.append("No recommendations — pipeline is healthy.")
    lines.append("")

    return "\n".join(lines)
