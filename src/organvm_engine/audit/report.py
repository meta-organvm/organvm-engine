"""Text (markdown) and JSON formatters for audit reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from organvm_engine.audit.types import InfrastructureAuditReport, Severity


def format_text(report: InfrastructureAuditReport) -> str:
    """Format audit report as human-readable text."""
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    scope = "SYSTEM"
    if report.scope_organ:
        scope = report.scope_organ
    if report.scope_repo:
        scope = f"{report.scope_organ or '?'}/{report.scope_repo}"

    lines.append("Infrastructure Wiring Audit")
    lines.append("=" * 40)
    lines.append(f"Scope: {scope} | {now}")
    lines.append("")

    # Overview
    lines.append("OVERVIEW")
    lines.append(f"  Findings: {len(report.all_findings)} total")
    lines.append(
        f"  Critical: {report.critical_count} | "
        f"Warnings: {report.warning_count} | "
        f"Info: {report.info_count}",
    )
    lines.append("")

    # Critical findings
    criticals = [f for f in report.all_findings if f.severity == Severity.CRITICAL]
    if criticals:
        lines.append(f"CRITICAL ({len(criticals)})")
        for f in criticals:
            prefix = f"[{f.layer}]"
            loc = f"{f.organ}/{f.repo}" if f.repo else f.organ
            lines.append(f"  {prefix} {loc}: {f.message}")
        lines.append("")

    # Warnings
    warnings = [f for f in report.all_findings if f.severity == Severity.WARNING]
    if warnings:
        lines.append(f"WARNINGS ({len(warnings)})")
        for f in warnings:
            prefix = f"[{f.layer}]"
            loc = f"{f.organ}/{f.repo}" if f.repo else f.organ
            lines.append(f"  {prefix} {loc}: {f.message}")
        lines.append("")

    # Per-organ breakdown
    organs = report.organs_with_findings()
    if organs and not report.scope_repo:
        lines.append("PER-ORGAN BREAKDOWN")
        for organ in organs:
            if organ in ("SYSTEM", ""):
                continue
            findings = report.findings_for_organ(organ)
            crit = sum(1 for f in findings if f.severity == Severity.CRITICAL)
            warn = sum(1 for f in findings if f.severity == Severity.WARNING)
            info = sum(1 for f in findings if f.severity == Severity.INFO)
            lines.append(f"  {organ}: {crit}C/{warn}W/{info}I")
        lines.append("")

    # Suggestions
    suggestions = [f for f in report.all_findings if f.suggestion]
    if suggestions:
        lines.append("SUGGESTIONS")
        seen: set[str] = set()
        for i, f in enumerate(suggestions, 1):
            if f.suggestion not in seen:
                seen.add(f.suggestion)
                lines.append(f"  {i}. {f.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_json(report: InfrastructureAuditReport) -> str:
    """Format audit report as JSON."""
    return json.dumps(report.to_dict(), indent=2, default=str)
