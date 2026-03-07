"""CLI commands for prompt narrative analysis.

Usage:
    organvm prompts narrate [--agent claude|gemini|codex] [--project FILTER]
                            [--output FILE] [--summary FILE]
                            [--dry-run] [--gap-hours 24]
    organvm prompts clipboard [--db-path PATH] [--output-dir DIR]
                              [--dry-run] [--json-only] [--md-only]
"""

from __future__ import annotations

import argparse
from pathlib import Path


def cmd_prompts_narrate(args: argparse.Namespace) -> int:
    """Narrate prompts across sessions into threaded narrative arcs."""
    from organvm_engine.prompts.narrator import narrate_prompts, write_jsonl
    from organvm_engine.prompts.summary import generate_narrative_summary

    agent = getattr(args, "agent", None)
    project_filter = getattr(args, "project", None)
    dry_run = getattr(args, "dry_run", False)
    gap_hours = getattr(args, "gap_hours", 24.0)

    from organvm_engine.paths import atoms_dir

    default_dir = atoms_dir()
    output_path = Path(getattr(args, "output", None) or (default_dir / "annotated-prompts.jsonl"))
    summary_path = Path(getattr(args, "summary", None) or (default_dir / "NARRATIVE-SUMMARY.md"))

    result = narrate_prompts(
        agent=agent,
        project_filter=project_filter,
        gap_hours=gap_hours,
    )

    # Print stats
    print(f"Sessions processed: {result.sessions_processed}")
    print(f"Sessions skipped: {result.sessions_skipped}")
    print(f"Prompts extracted: {len(result.prompts)}")
    print(f"Threads: {result.thread_count}")
    print(f"Errors: {len(result.errors)}")
    print()

    print("Type distribution:")
    for ptype, count in sorted(result.type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ptype}: {count}")
    print()

    print("Size distribution:")
    for sclass, count in sorted(result.size_counts.items(), key=lambda x: -x[1]):
        print(f"  {sclass}: {count}")
    print()

    print("Arc patterns:")
    for pattern, count in sorted(result.arc_pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")

    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for loc, err in result.errors[:10]:
            print(f"  {loc}: {err}")

    if dry_run:
        print("\n--dry-run: no files written")
        return 0

    write_jsonl(result.prompts, output_path)
    print(f"\nWrote {len(result.prompts)} prompts to {output_path}")

    summary = generate_narrative_summary(result)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    print(f"Wrote summary to {summary_path}")

    return 0


def cmd_prompts_clipboard(args: argparse.Namespace) -> int:
    """Extract and classify AI prompts from Paste.app clipboard history."""
    from organvm_engine.prompts.clipboard.pipeline import run_pipeline

    db_path_str = getattr(args, "db_path", None)
    db_path = Path(db_path_str) if db_path_str else None
    output_dir_str = getattr(args, "output_dir", None)
    output_dir = Path(output_dir_str) if output_dir_str else None
    dry_run = getattr(args, "dry_run", False)
    json_only = getattr(args, "json_only", False)
    md_only = getattr(args, "md_only", False)

    run_pipeline(
        db_path=db_path,
        output_dir=output_dir,
        dry_run=dry_run,
        json_only=json_only,
        md_only=md_only,
    )

    return 0
