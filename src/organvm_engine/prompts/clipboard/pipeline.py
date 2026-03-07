"""Orchestrate the full clipboard prompt extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.prompts.clipboard.classifier import (
    build_prompt_record,
    classify_as_prompt,
)
from organvm_engine.prompts.clipboard.export import export_json, export_markdown
from organvm_engine.prompts.clipboard.extractor import load_items
from organvm_engine.prompts.clipboard.schema import (
    ClipboardExportStats,
    ClipboardPrompt,
    ClipboardSession,
)
from organvm_engine.prompts.clipboard.session import compute_sessions, deduplicate


@dataclass
class PipelineResult:
    """Result of running the clipboard extraction pipeline."""

    prompts: list[ClipboardPrompt]
    stats: ClipboardExportStats
    session_summaries: list[ClipboardSession]
    rejection_reasons: dict[str, int] = field(default_factory=dict)


def run_pipeline(
    db_path: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
    json_only: bool = False,
    md_only: bool = False,
) -> PipelineResult:
    """Run the full clipboard prompt extraction pipeline.

    Steps: load -> classify -> dedup -> session-cluster -> export

    Args:
        db_path: Path to Paste.app database (None = default location).
        output_dir: Directory for output files (None = current directory).
        dry_run: If True, skip file writing.
        json_only: Only write JSON output.
        md_only: Only write Markdown output.

    Returns:
        PipelineResult with prompts, stats, and session data.
    """
    print("Loading clipboard items from Paste.app...")
    items = load_items(db_path)
    print(f"  {len(items)} text items loaded")

    if not items:
        print("No items found.")
        return PipelineResult(
            prompts=[],
            stats=ClipboardExportStats(
                total_items=0, prompts_found=0, dupes_removed=0,
                unique_prompts=0, date_range="", rejection_reasons={},
                total_sessions=0, multi_prompt_sessions=0,
                multi_app_sessions=0, avg_session_size=0,
                max_session_size=0,
            ),
            session_summaries=[],
        )

    date_range = f"{items[0].date} to {items[-1].date}"

    print("Classifying prompts...")
    raw_prompts: list[ClipboardPrompt] = []
    rejection_reasons: dict[str, int] = {}
    for item in items:
        is_prompt, signals = classify_as_prompt(item)
        if is_prompt:
            record = build_prompt_record(item, signals)
            raw_prompts.append(record)
        else:
            reason = signals[0] if signals else "unknown"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

    print(f"  {len(raw_prompts)} prompts identified")
    print("  Rejection breakdown:")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
        print(f"    {count:5d}  {reason}")

    print("Deduplicating...")
    prompts, dupe_count = deduplicate(raw_prompts)
    print(f"  {dupe_count} duplicates removed, {len(prompts)} unique prompts")

    print("Computing sessions (gap threshold: 30 min)...")
    _sessions, session_summaries = compute_sessions(prompts)
    multi_prompt_sessions = sum(1 for s in session_summaries if s.size > 1)
    multi_app_sessions = sum(1 for s in session_summaries if s.multi_app)
    max_session = max((s.size for s in session_summaries), default=0)
    print(
        f"  {len(session_summaries)} sessions ({multi_prompt_sessions} multi-prompt, "
        f"{multi_app_sessions} multi-app, max size {max_session})",
    )

    size_dist: dict[int, int] = {}
    for s in session_summaries:
        size_dist[s.size] = size_dist.get(s.size, 0) + 1

    stats = ClipboardExportStats(
        total_items=len(items),
        prompts_found=len(raw_prompts),
        dupes_removed=dupe_count,
        unique_prompts=len(prompts),
        date_range=date_range,
        rejection_reasons=rejection_reasons,
        total_sessions=len(session_summaries),
        multi_prompt_sessions=multi_prompt_sessions,
        multi_app_sessions=multi_app_sessions,
        avg_session_size=(
            round(len(prompts) / len(session_summaries), 1) if session_summaries else 0
        ),
        max_session_size=max_session,
        session_size_distribution=size_dist,
    )

    if not dry_run:
        out = output_dir or Path.cwd()
        print("Exporting...")
        if not md_only:
            json_path = out / "ai-prompts-clipboard-export.json"
            export_json(prompts, stats, session_summaries, json_path)
            print(f"  JSON: {json_path}")
        if not json_only:
            md_path = out / "ai-prompts-clipboard-export.md"
            export_markdown(prompts, stats, session_summaries, md_path)
            print(f"  Markdown: {md_path}")
    else:
        print("\n--dry-run: no files written")

    print("Done.")

    return PipelineResult(
        prompts=prompts,
        stats=stats,
        session_summaries=session_summaries,
        rejection_reasons=rejection_reasons,
    )
