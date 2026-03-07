"""CLI handler for atoms link + pipeline — cross-system task/prompt matching."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_atoms_link(args: argparse.Namespace) -> int:
    """Link atomized tasks to annotated prompts by content similarity."""
    from organvm_engine.atoms.linker import compute_links
    from organvm_engine.paths import atoms_dir

    tasks_path = Path(
        getattr(args, "tasks", None)
        or (atoms_dir() / "atomized-tasks.jsonl"),
    )
    prompts_path = Path(
        getattr(args, "prompts", None)
        or (atoms_dir() / "annotated-prompts.jsonl"),
    )

    if not tasks_path.exists():
        print(f"Tasks file not found: {tasks_path}", file=sys.stderr)
        print("Run 'organvm plans atomize' first.", file=sys.stderr)
        return 1
    if not prompts_path.exists():
        print(f"Prompts file not found: {prompts_path}", file=sys.stderr)
        print("Run 'organvm prompts narrate' first.", file=sys.stderr)
        return 1

    threshold = getattr(args, "threshold", 0.30)
    by_thread = getattr(args, "by_thread", False)
    as_json = getattr(args, "json", False)
    output = getattr(args, "output", None)

    links = compute_links(
        tasks_path, prompts_path,
        threshold=threshold,
        by_thread=by_thread,
    )

    if as_json:
        text = json.dumps([l.to_dict() for l in links], indent=2, ensure_ascii=False)
    else:
        lines = [
            f"Atom Links — {len(links)} matches (threshold={threshold})",
            f"Mode: {'by-thread' if by_thread else 'per-prompt'}",
            "",
            f"{'Task ID':<14} {'Prompt/Thread ID':<20} {'Jaccard':>8}  Shared",
            f"{'─' * 14} {'─' * 20} {'─' * 8}  {'─' * 30}",
        ]
        for link in links:
            shared = ", ".join(link.shared_tags[:3] + link.shared_refs[:2])
            if not shared:
                shared = "—"
            lines.append(
                f"{link.task_id:<14} {link.prompt_id:<20} {link.jaccard:>8.4f}  {shared}",
            )
        text = "\n".join(lines)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {len(links)} links to {out_path}")
    else:
        print(text)

    return 0


def cmd_atoms_reconcile(args: argparse.Namespace) -> int:
    """Cross-reference tasks against git history to detect completed work."""
    from organvm_engine.atoms.reconciler import apply_verdicts, reconcile_tasks
    from organvm_engine.paths import atoms_dir, workspace_root

    tasks_path = atoms_dir() / "atomized-tasks.jsonl"
    if not tasks_path.exists():
        print(f"Tasks file not found: {tasks_path}", file=sys.stderr)
        print("Run 'organvm atoms pipeline --write' first.", file=sys.stderr)
        return 1

    workspace = Path(getattr(args, "workspace", None) or workspace_root())
    write = getattr(args, "write", False)
    since = getattr(args, "since", None)

    result = reconcile_tasks(tasks_path, workspace, since=since)

    print(f"Reconciliation — {result.total_tasks} tasks")
    print(f"  likely_completed: {result.likely_completed}")
    print(f"  partially_done:   {result.partially_done}")
    print(f"  stale:            {result.stale}")
    print(f"  unknown:          {result.unknown}")

    if write and result.verdicts:
        updated = apply_verdicts(tasks_path, result.verdicts)
        print(f"\n  {updated} tasks updated in {tasks_path}")
    elif not write:
        print("\n  Use --write to update task statuses")

    return 0


def cmd_atoms_pipeline(args: argparse.Namespace) -> int:
    """Run the full atomization pipeline: atomize → narrate → link → index → manifest."""
    from organvm_engine.atoms.pipeline import run_pipeline

    write = getattr(args, "write", False)
    dry_run = not write
    output_dir = getattr(args, "output_dir", None)
    if output_dir:
        output_dir = Path(output_dir)

    skip_reconcile = getattr(args, "skip_reconcile", False)

    result = run_pipeline(
        output_dir=output_dir,
        agent=getattr(args, "agent", None),
        organ=getattr(args, "organ", None),
        skip_narrate=getattr(args, "skip_narrate", False),
        skip_link=getattr(args, "skip_link", False),
        skip_reconcile=skip_reconcile,
        link_threshold=getattr(args, "threshold", 0.30),
        dry_run=dry_run,
    )

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}[1/6] Atomize: {result.plans_parsed} plans → {result.atomize_count} tasks")
    print(f"{prefix}[2/6] Narrate: {result.sessions_processed} sessions → "
          f"{result.narrate_count} prompts ({result.noise_skipped} noise skipped)")
    print(f"{prefix}[3/6] Link: {result.link_count} matches "
          f"(threshold={getattr(args, 'threshold', 0.30)})")
    if not dry_run and not skip_reconcile:
        print(f"{prefix}[4/6] Reconcile: {result.reconcile_completed} completed, "
              f"{result.reconcile_partial} partial")
    else:
        print(f"{prefix}[4/6] Reconcile: skipped ({'dry-run' if dry_run else 'disabled'})")
    if not dry_run:
        idx_count = result.manifest.get("files", {}).get("plan-index.json", {}).get("count", "?")
        print(f"{prefix}[5/6] Index: plan-index.json ({idx_count} plans)")
    else:
        print(f"{prefix}[5/6] Index: skipped (dry-run)")
    print(f"{prefix}[6/6] Manifest: pipeline-manifest.json")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for stage, err in result.errors[:10]:
            print(f"  [{stage}] {err}")

    if dry_run:
        print(f"\n{prefix}Use --write to execute")
    elif not dry_run:
        print("\nRun 'organvm atoms fanout --write' to distribute to organ directories.")

    return 0


def cmd_atoms_fanout(args: argparse.Namespace) -> int:
    """Fan out centralized atom data to per-organ rollup JSON files."""
    from organvm_engine.atoms.rollup import build_rollups, write_rollups
    from organvm_engine.paths import atoms_dir, workspace_root

    a_dir = Path(getattr(args, "atoms_dir", None) or atoms_dir())
    workspace = Path(getattr(args, "workspace", None) or workspace_root())
    write = getattr(args, "write", False)
    dry_run = not write

    if not a_dir.is_dir():
        print(f"Atoms directory not found: {a_dir}", file=sys.stderr)
        print("Run 'organvm atoms pipeline --write' first.", file=sys.stderr)
        return 1

    rollups = build_rollups(a_dir)
    if not rollups:
        print("No organ data found in pipeline outputs.")
        return 0

    paths = write_rollups(rollups, workspace, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Atom Fanout — {len(rollups)} organs\n")
    print(f"{'Organ':<8} {'Tasks':>6} {'Pending':>8} {'Prompts':>8} {'X-Links':>8}")
    print(f"{'─' * 8} {'─' * 6} {'─' * 8} {'─' * 8} {'─' * 8}")
    for key in sorted(rollups):
        r = rollups[key]
        prompt_count = sum(r.prompt_type_dist.values())
        print(
            f"{key:<8} {r.total_tasks:>6} {r.pending_tasks:>8} "
            f"{prompt_count:>8} {len(r.cross_organ_links):>8}",
        )

    print(f"\n{prefix}{len(paths)} rollup files {'would be ' if dry_run else ''}written")
    if dry_run:
        print(f"\n{prefix}Use --write to execute")

    return 0
