"""Phase 4: Remediation — convert rectification deltas to actionable items.

Produces three output formats:
  1. YAML summary for machine consumption
  2. Markdown plan file for human review
  3. Structured issue list for project board creation
"""

from __future__ import annotations

import yaml

from organvm_engine.governance.exit_interview.schemas import (
    RectificationReport,
    RemediationItem,
    RemediationPriority,
)

# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_remediation(reports: list[RectificationReport]) -> list[RemediationItem]:
    """Collect all remediation items across gate reports, deduplicated by action."""
    seen: set[str] = set()
    items: list[RemediationItem] = []
    for report in reports:
        for item in report.remediation:
            key = f"{item.source_path}:{item.action}"
            if key not in seen:
                seen.add(key)
                items.append(item)
    # Sort by priority
    priority_order = {
        RemediationPriority.CRITICAL: 0,
        RemediationPriority.HIGH: 1,
        RemediationPriority.MEDIUM: 2,
        RemediationPriority.LOW: 3,
    }
    items.sort(key=lambda i: (priority_order.get(i.priority, 9), i.gate, i.source_path))
    return items


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------


def compute_summary(reports: list[RectificationReport]) -> dict:
    """Compute aggregate statistics across all rectification reports."""
    total_gates = len(reports)
    total_modules = sum(r.v1_modules_claimed for r in reports)
    total_orphans = sum(r.orphaned for r in reports)

    # Count verdicts across all modules
    verdict_counts: dict[str, int] = {}
    for report in reports:
        for verdicts in report.module_verdicts.values():
            for v in verdicts:
                verdict_counts[v.verdict.value] = verdict_counts.get(v.verdict.value, 0) + 1

    # Alignment scores per gate
    gate_scores = {r.gate_name: round(r.alignment_score, 3) for r in reports}

    # Overall alignment
    all_scores = [r.alignment_score for r in reports if r.alignment_score > 0]
    overall = round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0

    return {
        "total_gates": total_gates,
        "total_v1_modules": total_modules,
        "total_orphans": total_orphans,
        "verdict_counts": verdict_counts,
        "gate_alignment_scores": gate_scores,
        "overall_alignment": overall,
    }


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------


def render_yaml(reports: list[RectificationReport]) -> str:
    """Render all rectification reports as YAML."""
    items = aggregate_remediation(reports)
    summary = compute_summary(reports)
    output = {
        "exit_interview_remediation": {
            "summary": summary,
            "remediation_items": [i.to_dict() for i in items],
            "gate_reports": [r.to_dict() for r in reports],
        },
    }
    return yaml.dump(output, default_flow_style=False, sort_keys=False, width=120)


# ---------------------------------------------------------------------------
# Markdown plan output
# ---------------------------------------------------------------------------


def render_plan(reports: list[RectificationReport]) -> str:
    """Render remediation as a markdown plan file."""
    items = aggregate_remediation(reports)
    summary = compute_summary(reports)

    lines = [
        "# Exit Interview Remediation Plan",
        "",
        "## Summary",
        "",
        f"- **Gates analyzed:** {summary['total_gates']}",
        f"- **V1 modules claimed:** {summary['total_v1_modules']}",
        f"- **Orphaned modules:** {summary['total_orphans']}",
        f"- **Overall alignment:** {summary['overall_alignment']:.1%}",
        "",
        "### Verdict Distribution",
        "",
    ]

    for verdict_name, count in sorted(summary["verdict_counts"].items()):
        lines.append(f"- **{verdict_name}:** {count}")

    lines.extend(["", "### Per-Gate Alignment", ""])
    lines.append("| Gate | Alignment |")
    lines.append("|------|-----------|")
    for gate, score in sorted(summary["gate_alignment_scores"].items(), key=lambda x: x[1]):
        lines.append(f"| {gate} | {score:.1%} |")

    # Remediation items grouped by priority
    lines.extend(["", "## Remediation Items", ""])
    for priority in RemediationPriority:
        priority_items = [i for i in items if i.priority == priority]
        if not priority_items:
            continue
        lines.append(f"### {priority.value}")
        lines.append("")
        for item in priority_items:
            lines.append(f"- **[{item.gate}]** {item.action}")
            lines.append(f"  - Source: `{item.source_path}`")
            lines.append(f"  - Type: {item.item_type.value}")
        lines.append("")

    # Orphan report
    all_orphans = [o for r in reports for o in r.orphan_report]
    if all_orphans:
        lines.extend(["## Orphaned V1 Artifacts", ""])
        lines.append("These governance modules are not claimed by any gate contract.")
        lines.append("They may need manual review to determine if their essence is")
        lines.append("preserved elsewhere or genuinely dissolved.")
        lines.append("")
        for orphan in all_orphans:
            rec = f" — {orphan.recommendation}" if orphan.recommendation else ""
            lines.append(f"- `{orphan.v1_path}` ({orphan.artifact_type}){rec}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Issue list output
# ---------------------------------------------------------------------------


def render_issues(reports: list[RectificationReport]) -> list[dict]:
    """Render remediation items as structured issue objects.

    Each issue has: title, body, labels, gate reference.
    Suitable for creating GitHub issues on the a-organvm project board.
    """
    items = aggregate_remediation(reports)
    issues = []
    for item in items:
        title = f"[{item.gate}] {item.action[:80]}"
        body_lines = [
            f"**Gate:** {item.gate}",
            f"**Source:** `{item.source_path}`",
            f"**Priority:** {item.priority.value}",
            f"**Type:** {item.item_type.value}",
            "",
            "**Action:**",
            item.action,
            "",
            "---",
            "*Generated by `organvm exit-interview plan`*",
        ]
        labels = [
            f"priority:{item.priority.value.lower()}",
            f"type:{item.item_type.value}",
            "exit-interview",
        ]
        issues.append({
            "title": title,
            "body": "\n".join(body_lines),
            "labels": labels,
            "gate": item.gate,
        })
    return issues
