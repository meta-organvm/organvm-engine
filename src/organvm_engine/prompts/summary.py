"""Generate Markdown narrative summary from annotated prompts."""

from __future__ import annotations

import datetime
from collections import Counter

from organvm_engine.prompts.schema import NarrateResult


def generate_narrative_summary(result: NarrateResult) -> str:
    """Generate NARRATIVE-SUMMARY.md content."""
    prompts = result.prompts
    total = len(prompts) or 1
    lines = [
        "# Prompt Narrative Analysis",
        f"**Generated**: {datetime.date.today().isoformat()}",
        f"**Sessions**: {result.sessions_processed} | "
        f"**Prompts**: {len(prompts)} | "
        f"**Threads**: {result.thread_count}",
        "",
    ]

    # Prompt Type Distribution
    lines.append("## Prompt Type Distribution")
    lines.append("")
    lines.append("| Type | Count | % |")
    lines.append("|------|-------|---|")
    for ptype, count in sorted(result.type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {ptype} | {count} | {count * 100 // total}% |")
    lines.append("")

    # Size Distribution
    lines.append("## Size Distribution")
    lines.append("")
    lines.append("| Class | Count | % |")
    lines.append("|-------|-------|---|")
    for sclass, count in sorted(result.size_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {sclass} | {count} | {count * 100 // total}% |")
    lines.append("")

    # Top Narrative Threads
    thread_stats: dict[str, dict] = {}
    for p in prompts:
        tid = p["threading"]["thread_id"]
        label = p["threading"]["thread_label"]
        if tid not in thread_stats:
            thread_stats[tid] = {
                "label": label,
                "sessions": set(),
                "prompts": 0,
                "dates": [],
                "types": Counter(),
            }
        thread_stats[tid]["sessions"].add(p["source"]["session_id"])
        thread_stats[tid]["prompts"] += 1
        ts = p["source"].get("timestamp")
        if ts:
            thread_stats[tid]["dates"].append(ts[:10])
        thread_stats[tid]["types"][p["classification"]["prompt_type"]] += 1

    top_threads = sorted(
        thread_stats.items(), key=lambda x: x[1]["prompts"], reverse=True,
    )[:25]

    if top_threads:
        lines.append("## Top Narrative Threads (by prompt count)")
        lines.append("")
        lines.append("| Thread | Sessions | Prompts | Date Range | Dominant Type |")
        lines.append("|--------|----------|---------|------------|---------------|")
        for _tid, info in top_threads:
            dates = sorted(set(info["dates"]))
            date_range = f"{dates[0]}..{dates[-1]}" if len(dates) > 1 else (dates[0] if dates else "?")
            dominant = info["types"].most_common(1)[0][0] if info["types"] else "?"
            label = info["label"][:50]
            lines.append(
                f"| {label} | {len(info['sessions'])} | "
                f"{info['prompts']} | {date_range} | {dominant} |",
            )
        lines.append("")

    # Temporal Activity
    month_stats: dict[str, dict] = {}
    for p in prompts:
        ts = p["source"].get("timestamp")
        if not ts or len(ts) < 7:
            continue
        month = ts[:7]
        if month not in month_stats:
            month_stats[month] = {
                "sessions": set(),
                "prompts": 0,
                "new_threads": set(),
                "projects": Counter(),
            }
        month_stats[month]["sessions"].add(p["source"]["session_id"])
        month_stats[month]["prompts"] += 1
        month_stats[month]["new_threads"].add(p["threading"]["thread_id"])
        month_stats[month]["projects"][p["source"]["project_slug"]] += 1

    if month_stats:
        lines.append("## Temporal Activity")
        lines.append("")
        lines.append("| Month | Sessions | Prompts | Threads | Top Project |")
        lines.append("|-------|----------|---------|---------|-------------|")
        for month in sorted(month_stats):
            info = month_stats[month]
            top_proj = info["projects"].most_common(1)[0][0] if info["projects"] else "?"
            top_proj = top_proj[:30]
            lines.append(
                f"| {month} | {len(info['sessions'])} | "
                f"{info['prompts']} | {len(info['new_threads'])} | {top_proj} |",
            )
        lines.append("")

    # Top Imperative Verbs
    verb_counter: Counter[str] = Counter()
    for p in prompts:
        v = p["signals"].get("imperative_verb", "")
        if v:
            verb_counter[v] += 1

    if verb_counter:
        lines.append("## Top Imperative Verbs")
        lines.append("")
        lines.append("| Verb | Count | % |")
        lines.append("|------|-------|---|")
        for verb, count in verb_counter.most_common(20):
            lines.append(f"| {verb} | {count} | {count * 100 // total}% |")
        lines.append("")

    # Narrative Arc Patterns
    if result.arc_pattern_counts:
        lines.append("## Narrative Arc Patterns")
        lines.append("")
        lines.append("| Pattern | Count | Description |")
        lines.append("|---------|-------|-------------|")
        descriptions = {
            "plan-then-execute": "Opens with plan invocation, bulk commands follow",
            "iterative-correction": "Commands interspersed with corrections (>20%)",
            "exploration-first": "Opens with questions or exploration",
            "single-shot": "Thread with 1-2 prompts only",
            "steady-build": "Continuous command flow without major corrections",
        }
        for pattern, count in sorted(
            result.arc_pattern_counts.items(), key=lambda x: -x[1],
        ):
            desc = descriptions.get(pattern, "")
            lines.append(f"| {pattern} | {count} | {desc} |")
        lines.append("")

    # Recurring Themes (tags)
    tag_counter: Counter[str] = Counter()
    for p in prompts:
        for tag in p["signals"].get("tags", []):
            tag_counter[tag] += 1

    if tag_counter:
        lines.append("## Recurring Themes (tags)")
        lines.append("")
        lines.append("| Tag | Count |")
        lines.append("|-----|-------|")
        for tag, count in tag_counter.most_common(30):
            lines.append(f"| {tag} | {count} |")
        lines.append("")

    return "\n".join(lines)
