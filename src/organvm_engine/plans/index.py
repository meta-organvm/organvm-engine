"""Plan index — machine-readable snapshot of all plans across the workspace.

Builds a PlanIndex from discovered plan files, computing metadata, domain
fingerprints, and stale candidates. Output is a JSON-serializable structure
analogous to system-organism.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.plans.graph import compute_overlaps


@dataclass
class PlanEntry:
    """Indexed metadata for a single plan file."""

    qualified_id: str
    path: str
    agent: str
    organ: str | None
    repo: str | None
    slug: str
    date: str
    version: int
    status: str  # active | superseded | archived
    title: str
    size_bytes: int
    has_verification: bool
    archetype: str | None
    task_count: int
    completed_count: int
    tags: list[str]
    file_refs: list[str]
    domain_fingerprint: str


@dataclass
class PlanIndex:
    """Complete plan index for the workspace."""

    generated: str
    total_plans: int
    total_tasks: int
    entries: list[PlanEntry]
    organ_summary: dict[str, dict]
    overlaps: list[dict]
    stale_candidates: list[str]


def _domain_fingerprint(tags: list[str], file_refs: list[str]) -> str:
    """Compute a stable hash of normalized tags + file_refs for overlap detection."""
    from organvm_engine.domain import domain_fingerprint
    return domain_fingerprint(tags, file_refs)


def _build_entry_from_plan(pf, workspace: Path) -> PlanEntry:
    """Build a PlanEntry from a PlanFile, atomizing for task stats."""
    from organvm_engine.plans.atomizer import (
        PlanParser,
        classify_archetype,
        extract_file_refs,
        extract_tags,
    )

    archetype = None
    task_count = 0
    completed_count = 0
    tags: list[str] = []
    file_ref_paths: list[str] = []

    try:
        text = pf.path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if lines:
            archetype = classify_archetype(lines)
            tags = extract_tags(text)
            file_ref_paths = [r.path for r in extract_file_refs(text)]

            # Parse tasks for count/completion
            try:
                base = pf.path.parent
                parser = PlanParser(
                    lines, pf.path, base,
                    agent=pf.agent, organ=pf.organ, repo=pf.repo,
                )
                tasks = parser.parse()
                task_count = len(tasks)
                completed_count = sum(1 for t in tasks if t.status == "completed")
            except Exception:
                task_count = 0
    except OSError:
        pass

    return PlanEntry(
        qualified_id=pf.qualified_id,
        path=str(pf.path),
        agent=pf.agent,
        organ=pf.organ,
        repo=pf.repo,
        slug=pf.slug,
        date=pf.date,
        version=pf.version,
        status=pf.status,
        title=pf.title,
        size_bytes=pf.size_bytes,
        has_verification=pf.has_verification,
        archetype=archetype,
        task_count=task_count,
        completed_count=completed_count,
        tags=tags,
        file_refs=file_ref_paths,
        domain_fingerprint=_domain_fingerprint(tags, file_ref_paths),
    )


def build_plan_index(
    workspace: Path | None = None,
    agent: str | None = None,
    organ: str | None = None,
    stale_days: int = 30,
) -> PlanIndex:
    """Build a complete plan index from discovered plan files.

    Args:
        workspace: Workspace root (default ~/Workspace).
        agent: Filter to specific agent.
        organ: Filter to specific organ key.
        stale_days: Plans older than this with 0% completion are flagged stale.
    """
    from organvm_engine.plans.synthesis import synthesize_all
    from organvm_engine.session.plans import discover_plans

    ws = workspace or Path.home() / "Workspace"
    plan_files = discover_plans(workspace=ws, agent=agent, organ=organ)

    entries = [_build_entry_from_plan(pf, ws) for pf in plan_files]

    # Compute overlaps on active plans only
    active = [e for e in entries if e.status == "active"]
    overlaps = compute_overlaps(active)

    # Flag stale candidates: active, 0 tasks completed, older than stale_days
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stale: list[str] = []
    for e in active:
        if e.completed_count > 0 or e.task_count == 0:
            continue
        try:
            age = (
                datetime.strptime(today, "%Y-%m-%d")
                - datetime.strptime(e.date, "%Y-%m-%d")
            ).days
            if age > stale_days:
                stale.append(e.qualified_id)
        except ValueError:
            continue

    total_tasks = sum(e.task_count for e in entries)
    organ_summary = synthesize_all(entries)

    return PlanIndex(
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        total_plans=len(entries),
        total_tasks=total_tasks,
        entries=entries,
        organ_summary={k: asdict(v) for k, v in organ_summary.items()},
        overlaps=[asdict(o) for o in overlaps],
        stale_candidates=stale,
    )


def index_to_json(index: PlanIndex) -> str:
    """Serialize a PlanIndex to JSON string."""
    data = {
        "generated": index.generated,
        "total_plans": index.total_plans,
        "total_tasks": index.total_tasks,
        "entries": [asdict(e) for e in index.entries],
        "organ_summary": index.organ_summary,
        "overlaps": index.overlaps,
        "stale_candidates": index.stale_candidates,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def render_index_table(index: PlanIndex) -> str:
    """Render a human-readable summary of the plan index."""
    lines = [
        f"Plan Index — {index.total_plans} plans, {index.total_tasks} tasks",
        "",
    ]

    # By status
    status_counts: dict[str, int] = {}
    for e in index.entries:
        status_counts[e.status] = status_counts.get(e.status, 0) + 1
    lines.append("Status distribution:")
    for s, c in sorted(status_counts.items()):
        lines.append(f"  {s}: {c}")

    # By agent
    agent_counts: dict[str, int] = {}
    for e in index.entries:
        agent_counts[e.agent] = agent_counts.get(e.agent, 0) + 1
    lines.append("\nBy agent:")
    for a, c in sorted(agent_counts.items()):
        lines.append(f"  {a}: {c}")

    # Organ summary
    if index.organ_summary:
        lines.append("\nBy organ:")
        for key in sorted(index.organ_summary):
            s = index.organ_summary[key]
            pct = s.get("completion_pct", 0)
            lines.append(
                f"  {key}: {s.get('active_plans', 0)} active, "
                f"{s.get('total_tasks', 0)} tasks, {pct:.0f}% complete",
            )

    # Overlaps
    if index.overlaps:
        lines.append(f"\nOverlaps: {len(index.overlaps)}")
        for o in index.overlaps[:5]:
            plans = o.get("plans", [])
            sev = o.get('severity', '?')
            dom = o.get('domain', '?')
            lines.append(f"  [{sev}] {dom} ({len(plans)} plans)")

    # Stale
    if index.stale_candidates:
        lines.append(f"\nStale candidates ({len(index.stale_candidates)}):")
        for qid in index.stale_candidates[:10]:
            lines.append(f"  {qid}")

    return "\n".join(lines)
