"""Generate Markdown summary report from cross-system atom links."""

from __future__ import annotations

import datetime
from collections import Counter

from organvm_engine.atoms.linker import AtomLink


def generate_link_summary(links: list[AtomLink], threshold: float) -> str:
    """Generate LINK-SUMMARY.md content from atom link results."""
    total = len(links)
    lines = [
        "# Atom Link Summary",
        f"**Generated**: {datetime.date.today().isoformat()}",
        f"**Links**: {total} | **Threshold**: {threshold}",
        "",
    ]

    if not links:
        lines.append("No links found at this threshold.")
        return "\n".join(lines)

    # Jaccard distribution
    buckets: dict[str, int] = {
        "0.50+": 0, "0.30–0.49": 0, "0.20–0.29": 0, "0.15–0.19": 0, "<0.15": 0,
    }
    for link in links:
        if link.jaccard >= 0.50:
            buckets["0.50+"] += 1
        elif link.jaccard >= 0.30:
            buckets["0.30–0.49"] += 1
        elif link.jaccard >= 0.20:
            buckets["0.20–0.29"] += 1
        elif link.jaccard >= 0.15:
            buckets["0.15–0.19"] += 1
        else:
            buckets["<0.15"] += 1

    lines.append("## Jaccard Distribution")
    lines.append("")
    lines.append("| Range | Count | % |")
    lines.append("|-------|-------|---|")
    for label, count in buckets.items():
        pct = count * 100 // total if total else 0
        lines.append(f"| {label} | {count} | {pct}% |")
    lines.append("")

    # Top shared tags
    tag_counter: Counter[str] = Counter()
    for link in links:
        for tag in link.shared_tags:
            tag_counter[tag] += 1

    if tag_counter:
        lines.append("## Top Shared Tags")
        lines.append("")
        lines.append("| Tag | Occurrences |")
        lines.append("|-----|-------------|")
        for tag, count in tag_counter.most_common(20):
            lines.append(f"| {tag} | {count} |")
        lines.append("")

    # Top shared refs
    ref_counter: Counter[str] = Counter()
    for link in links:
        for ref in link.shared_refs:
            ref_counter[ref] += 1

    if ref_counter:
        lines.append("## Top Shared File References")
        lines.append("")
        lines.append("| File | Occurrences |")
        lines.append("|------|-------------|")
        for ref, count in ref_counter.most_common(20):
            lines.append(f"| `{ref}` | {count} |")
        lines.append("")

    # Top linked tasks
    task_counter: Counter[str] = Counter()
    for link in links:
        task_counter[link.task_id] += 1

    lines.append("## Most-Linked Tasks")
    lines.append("")
    lines.append("| Task ID | Links |")
    lines.append("|---------|-------|")
    for tid, count in task_counter.most_common(15):
        lines.append(f"| {tid} | {count} |")
    lines.append("")

    return "\n".join(lines)
