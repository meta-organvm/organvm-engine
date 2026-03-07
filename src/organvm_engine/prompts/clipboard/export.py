"""Export clipboard prompt data to JSON and Markdown formats."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from organvm_engine.prompts.clipboard.schema import (
    ClipboardExportStats,
    ClipboardPrompt,
    ClipboardSession,
)


def export_json(
    prompts: list[ClipboardPrompt],
    stats: ClipboardExportStats,
    session_summaries: list[ClipboardSession],
    output_path: Path,
) -> None:
    """Write the full export as a JSON file."""
    out = {
        "generated": datetime.now().isoformat(),
        "stats": stats.to_dict(),
        "total": len(prompts),
        "sessions": [
            {
                "session_id": s.session_id,
                "start": s.start,
                "end": s.end,
                "duration_minutes": s.duration_minutes,
                "size": s.size,
                "apps": s.apps,
                "categories": s.categories,
                "dominant_category": s.dominant_category,
                "multi_app": s.multi_app,
                "prompt_ids": s.prompt_ids,
            }
            for s in session_summaries
        ],
        "prompts": [p.to_dict() for p in prompts],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def export_markdown(
    prompts: list[ClipboardPrompt],
    stats: ClipboardExportStats,
    session_summaries: list[ClipboardSession],
    output_path: Path,
) -> None:
    """Write the export as a Markdown report."""
    cat_counts: dict[str, int] = {}
    app_counts: dict[str, int] = {}
    conf_counts: dict[str, int] = {}
    by_category: dict[str, list[ClipboardPrompt]] = {}

    for p in prompts:
        cat = p.category
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        app_counts[p.source_app] = app_counts.get(p.source_app, 0) + 1
        conf_counts[p.confidence] = conf_counts.get(p.confidence, 0) + 1
        by_category.setdefault(cat, []).append(p)

    lines = [
        "# AI Prompts -- Clipboard History Export",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Source: Paste.app ({stats.date_range})",
        f"Total items scanned: {stats.total_items}",
        f"Prompts identified: {stats.prompts_found}",
        f"Duplicates removed: {stats.dupes_removed}",
        f"Final unique prompts: {len(prompts)}",
        "",
        "## Summary by Category",
        "| Category | Count | % |",
        "|----------|------:|--:|",
    ]
    for cat in sorted(cat_counts, key=lambda c: cat_counts[c], reverse=True):
        pct = cat_counts[cat] / len(prompts) * 100
        lines.append(f"| {cat} | {cat_counts[cat]} | {pct:.0f}% |")

    lines += [
        "",
        "## Summary by Source App",
        "| App | Count |",
        "|-----|------:|",
    ]
    for app in sorted(app_counts, key=lambda a: app_counts[a], reverse=True):
        lines.append(f"| {app} | {app_counts[app]} |")

    lines += [
        "",
        "## Confidence Distribution",
        "| Level | Count |",
        "|-------|------:|",
    ]
    for level in ["high", "medium", "low"]:
        lines.append(f"| {level} | {conf_counts.get(level, 0)} |")

    # Session statistics
    total_sessions = len(session_summaries)
    multi_prompt = [s for s in session_summaries if s.size > 1]
    multi_app = [s for s in session_summaries if s.multi_app]
    avg_size = sum(s.size for s in session_summaries) / total_sessions if total_sessions else 0
    max_size = max((s.size for s in session_summaries), default=0)
    durations = [s.duration_minutes for s in session_summaries if s.size > 1]
    avg_duration = sum(durations) / len(durations) if durations else 0

    lines += [
        "",
        "## Session Statistics",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Total sessions | {total_sessions} |",
    ]
    if total_sessions:
        lines.append(
            f"| Multi-prompt sessions | {len(multi_prompt)}"
            f" ({len(multi_prompt) * 100 // total_sessions}%) |",
        )
        lines.append(
            f"| Multi-app sessions | {len(multi_app)}"
            f" ({len(multi_app) * 100 // total_sessions}%) |",
        )
    else:
        lines.append("| Multi-prompt sessions | 0 |")
        lines.append("| Multi-app sessions | 0 |")
    lines += [
        f"| Avg session size | {avg_size:.1f} |",
        f"| Max session size | {max_size} |",
        f"| Avg session duration (multi-prompt) | {avg_duration:.0f} min |",
    ]

    # Sessions timeline (multi-prompt only)
    lines += ["", "---", "", "## Sessions Timeline", ""]
    prompt_by_id: dict[int, ClipboardPrompt] = {p.id: p for p in prompts}

    for s in session_summaries:
        if s.size < 2:
            continue

        start_dt = datetime.fromisoformat(s.start)
        end_dt = datetime.fromisoformat(s.end)
        header_date = start_dt.strftime("%Y-%m-%d")
        start_time = start_dt.strftime("%H:%M")
        end_time = end_dt.strftime("%H:%M")

        apps_str = ", ".join(
            f"{app} ({cnt})"
            for app, cnt in sorted(s.apps.items(), key=lambda x: -x[1])
        )
        cats_str = ", ".join(
            f"{cat} ({cnt})"
            for cat, cnt in sorted(s.categories.items(), key=lambda x: -x[1])
        )

        lines.append(
            f"### Session {s.session_id} -- {header_date} "
            f"{start_time}-{end_time} "
            f"({s.duration_minutes:.0f} min, {s.size} prompts)",
        )
        lines.append(f"Apps: {apps_str}  ")
        lines.append(f"Categories: {cats_str}")
        lines.append("")

        for pid in s.prompt_ids:
            p = prompt_by_id.get(pid)
            if not p:
                continue
            time_short = p.time[:5]
            preview = p.text.split("\n")[0][:120]
            pos = p.position_in_session
            lines.append(f"  {pos}. [{time_short}] [{p.source_app}] {preview}")
        lines.append("")

    # Prompts by category
    lines += ["---", "", "## Prompts by Category"]

    for cat in sorted(by_category, key=lambda c: cat_counts.get(c, 0), reverse=True):
        items = by_category[cat]
        lines.append(f"\n### {cat} ({len(items)} prompts)\n")
        for p in sorted(items, key=lambda x: x.timestamp):
            ts_short = f"{p.date} {p.time[:5]}"
            conf_badge = {"high": "[H]", "medium": "[M]", "low": "[L]"}[p.confidence]
            lines.append(f"#### {ts_short} -- [{p.source_app}] {conf_badge}")

            meta_parts = [f"{p.word_count}w"]
            if (p.session_size or 1) > 1:
                meta_parts.append(
                    f"session {p.session_id} ({p.position_in_session}/{p.session_size})",
                )
            if p.tech_mentions:
                meta_parts.append(f"tech: {', '.join(p.tech_mentions[:5])}")
            if p.file_refs:
                meta_parts.append(f"files: {len(p.file_refs)}")
            lines.append(f"*{' | '.join(meta_parts)}*\n")

            display_text = p.text
            if len(display_text) > 3000:
                display_text = display_text[:3000] + "\n[...truncated...]"
            quoted = "\n".join(f"> {line}" for line in display_text.split("\n"))
            lines.append(quoted)
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
