"""CLI commands for plan analysis: atomize, index, audit, overlaps.

Usage:
    organvm plans atomize [--plans-dir DIR] [--output FILE] [--summary FILE] [--dry-run]
    organvm plans index [--json] [--write] [--agent X] [--organ X]
    organvm plans audit [--organ X] [--stale-days 30]
    organvm plans overlaps [--severity conflict]
"""

from __future__ import annotations

import argparse
from pathlib import Path


def cmd_plans_index(args: argparse.Namespace) -> int:
    """Build and display the plan index."""
    from organvm_engine.plans.index import (
        build_plan_index,
        index_to_json,
        render_index_table,
    )

    agent = getattr(args, "agent", None)
    organ = getattr(args, "organ", None)
    as_json = getattr(args, "json", False)
    write = getattr(args, "write", False)

    index = build_plan_index(agent=agent, organ=organ)

    output = index_to_json(index) if as_json else render_index_table(index)

    print(output)

    if write:
        from organvm_engine.paths import corpus_dir

        out_dir = corpus_dir() / "data" / "plans"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "plan-index.json"
        out_path.write_text(index_to_json(index), encoding="utf-8")
        print(f"\nWrote plan index to {out_path}")

    return 0


def cmd_plans_audit(args: argparse.Namespace) -> int:
    """Flag stale plans, duplicates, and orphans."""
    from organvm_engine.plans.index import build_plan_index

    organ = getattr(args, "organ", None)
    stale_days = getattr(args, "stale_days", 30) or 30

    index = build_plan_index(organ=organ, stale_days=stale_days)

    active = [e for e in index.entries if e.status == "active"]
    print(f"Total plans: {index.total_plans}")
    print(f"Active plans: {len(active)}")
    print(f"Total tasks: {index.total_tasks}")
    print()

    # Duplicate slugs (same slug across different agents)
    import re

    slug_agents: dict[str, set[str]] = {}
    for e in index.entries:
        base = re.sub(r"-v\d+$", "", e.slug)
        slug_agents.setdefault(base, set()).add(e.agent)
    dupes = {s: agents for s, agents in slug_agents.items() if len(agents) > 1}
    if dupes:
        print(f"Duplicate slugs across agents ({len(dupes)}):")
        for slug, agents in sorted(dupes.items()):
            print(f"  {slug}: {', '.join(sorted(agents))}")
        print()

    # Stale candidates
    if index.stale_candidates:
        print(f"Stale plans (>{stale_days} days, 0% complete): {len(index.stale_candidates)}")
        for qid in index.stale_candidates:
            print(f"  {qid}")
        print()
    else:
        print(f"No stale plans (>{stale_days} days threshold)\n")

    # Overlaps summary
    if index.overlaps:
        conflicts = [o for o in index.overlaps if o.get("severity") == "conflict"]
        warnings = [o for o in index.overlaps if o.get("severity") == "warning"]
        n_c, n_w = len(conflicts), len(warnings)
        print(f"Overlaps: {len(index.overlaps)} ({n_c} conflicts, {n_w} warnings)")
    else:
        print("No overlaps detected")

    return 0


def cmd_plans_overlaps(args: argparse.Namespace) -> int:
    """Show overlapping plan clusters."""
    from organvm_engine.plans.index import build_plan_index

    severity_filter = getattr(args, "severity", None)
    organ = getattr(args, "organ", None)

    index = build_plan_index(organ=organ)

    overlaps = index.overlaps
    if severity_filter:
        overlaps = [o for o in overlaps if o.get("severity") == severity_filter]

    if not overlaps:
        print("No overlaps found" + (f" at severity={severity_filter}" if severity_filter else ""))
        return 0

    print(f"Plan overlaps: {len(overlaps)}\n")
    for o in overlaps:
        sev = o.get("severity", "?")
        domain = o.get("domain", "?")
        plans = o.get("plans", [])
        agents = o.get("agents", [])
        jaccard = o.get("jaccard", 0)
        print(f"[{sev.upper()}] {domain} (Jaccard={jaccard:.2f})")
        print(f"  Agents: {', '.join(agents)}")
        for qid in plans:
            print(f"  - {qid}")
        print()

    return 0


def cmd_plans_sweep(args: argparse.Namespace) -> int:
    """List archival candidates (read-only)."""
    import json as json_mod

    from organvm_engine.plans.hygiene import compute_sprawl, sweep_candidates
    from organvm_engine.plans.index import build_plan_index

    agent = getattr(args, "agent", None)
    organ = getattr(args, "organ", None)
    stale_days = getattr(args, "stale_days", 14) or 14
    as_json = getattr(args, "json", False)

    index = build_plan_index(agent=agent, organ=organ, stale_days=stale_days)
    candidates = sweep_candidates(index.entries, stale_days=stale_days)
    sprawl = compute_sprawl(index.entries)

    if as_json:
        data = {
            "sweep_count": len(candidates),
            "sprawl_level": sprawl.sprawl_level,
            "total_active": sprawl.total_active,
            "oldest_untouched_days": sprawl.oldest_untouched_days,
            "candidates": [
                {
                    "qualified_id": c.entry.qualified_id,
                    "reason": c.reason,
                    "confidence": c.confidence,
                    "archive_target": c.archive_target,
                }
                for c in candidates
            ],
        }
        print(json_mod.dumps(data, indent=2))
        return 0

    if not candidates:
        print(f"No archival candidates (stale_days={stale_days})")
        print(f"Sprawl: {sprawl.sprawl_level} ({sprawl.total_active} active)")
        return 0

    # Table output
    auto = [c for c in candidates if c.confidence == "auto"]
    review = [c for c in candidates if c.confidence == "review"]

    if auto:
        print(f"Auto-archivable ({len(auto)}):")
        for c in auto:
            print(f"  [{c.reason}] {c.entry.qualified_id}")
    if review:
        print(f"\nNeeds review ({len(review)}):")
        for c in review:
            print(f"  [{c.reason}] {c.entry.qualified_id}")

    print(f"\nSprawl: {sprawl.sprawl_level} ({sprawl.total_active} active, "
          f"{len(candidates)} candidates)")
    return 0


def cmd_plans_tidy(args: argparse.Namespace) -> int:
    """Execute archival moves. Dry-run by default."""
    from organvm_engine.plans.hygiene import archive_plans, sweep_candidates
    from organvm_engine.plans.index import build_plan_index

    agent = getattr(args, "agent", None)
    organ = getattr(args, "organ", None)
    stale_days = getattr(args, "stale_days", 14) or 14
    include_review = getattr(args, "include_review", False)
    write = getattr(args, "write", False)
    dry_run = not write

    index = build_plan_index(agent=agent, organ=organ, stale_days=stale_days)
    candidates = sweep_candidates(index.entries, stale_days=stale_days)

    if not include_review:
        candidates = [c for c in candidates if c.confidence == "auto"]

    if not candidates:
        print("No plans to archive"
              + (" (use --include-review for stale plans)" if not include_review else ""))
        return 0

    result = archive_plans(candidates, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Archived: {result.moved}")
    if result.skipped:
        print(f"{prefix}Skipped: {result.skipped}")
    if result.errors:
        print(f"{prefix}Errors: {len(result.errors)}")

    for detail in result.details[:20]:
        print(f"  {detail}")
    if len(result.details) > 20:
        print(f"  ... and {len(result.details) - 20} more")

    if dry_run:
        print(f"\n{prefix}Use --write to execute")

    return 0


def cmd_plans_atomize(args: argparse.Namespace) -> int:
    """Atomize plan files into atomic tasks with rich metadata."""
    from organvm_engine.plans.atomizer import atomize_all, atomize_plans, write_jsonl
    from organvm_engine.plans.summary import generate_summary

    discover_all = getattr(args, "all", False)
    agent = getattr(args, "agent", None)
    organ = getattr(args, "organ", None)

    if discover_all:
        # Use unified multi-agent discovery
        from organvm_engine.paths import atoms_dir

        result = atomize_all(agent=agent, organ=organ)
        output_path = Path(
            getattr(args, "output", None)
            or (atoms_dir() / "atomized-tasks.jsonl"),
        )
        summary_path = Path(
            getattr(args, "summary", None)
            or (atoms_dir() / "ATOMIZED-SUMMARY.md"),
        )
    else:
        plans_dir = Path(
            getattr(args, "plans_dir", None) or Path.home() / ".claude" / "plans",
        ).resolve()
        output_path = Path(getattr(args, "output", None) or (plans_dir / "atomized-tasks.jsonl"))
        summary_path = Path(
            getattr(args, "summary", None) or (plans_dir / "ATOMIZED-SUMMARY.md"),
        )

        if not plans_dir.is_dir():
            print(f"Error: {plans_dir} is not a directory")
            return 1

        result = atomize_plans(plans_dir)

    dry_run = getattr(args, "dry_run", False)

    # Print stats
    print(f"Plans parsed: {result.plans_parsed}")
    print(f"Tasks extracted: {len(result.tasks)}")
    print(f"Parse errors: {len(result.errors)}")
    print()
    print("Archetypes:")
    for arch, count in sorted(result.archetype_counts.items(), key=lambda x: -x[1]):
        print(f"  {arch}: {count}")
    print()
    print("Statuses:")
    for status, count in sorted(result.status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {count}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for f, e in result.errors[:10]:
            print(f"  {f}: {e}")

    if dry_run:
        print("\n--dry-run: no files written")
        return 0

    write_jsonl(result.tasks, output_path)
    print(f"\nWrote {len(result.tasks)} tasks to {output_path}")

    summary = generate_summary(result.tasks, result.plans_parsed)
    summary_path.write_text(summary, encoding="utf-8")
    print(f"Wrote summary to {summary_path}")

    return 0
