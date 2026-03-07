"""Orchestrator — narrate_prompts() ties extraction, classification, and threading."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from organvm_engine.plans.atomizer import extract_tags
from organvm_engine.prompts.classifier import (
    classify_prompt_type,
    classify_session_position,
    classify_size,
    extract_file_mentions,
    extract_imperative_verb,
    extract_opening_phrase,
    extract_tool_mentions,
)
from organvm_engine.prompts.extractor import extract_prompts
from organvm_engine.prompts.schema import (
    AnnotatedPrompt,
    NarrateResult,
    PromptClassification,
    PromptContent,
    PromptSignals,
    PromptSource,
    PromptThreading,
)
from organvm_engine.prompts.threading import (
    assign_arc_positions,
    assign_threads,
    classify_arc_pattern,
    cluster_into_episodes,
    derive_project_slug,
)
from organvm_engine.session.agents import AgentSession, discover_all_sessions


def narrate_prompts(
    agent: str | None = None,
    project_filter: str | None = None,
    gap_hours: float = 24.0,
) -> NarrateResult:
    """Main entry point: discover sessions, extract & classify prompts, thread into arcs."""
    sessions = discover_all_sessions(agent=agent, project_filter=project_filter)

    all_annotated: list[AnnotatedPrompt] = []
    errors: list[tuple[str, str]] = []
    sessions_processed = 0
    sessions_skipped = 0

    for session in sessions:
        raw_prompts = extract_prompts(session)
        if raw_prompts is None:
            sessions_skipped += 1
            continue

        sessions_processed += 1
        prompt_count = len(raw_prompts)
        slug = derive_project_slug(session.project_dir)

        for rp in raw_prompts:
            try:
                ap = _build_annotated(rp.text, rp.timestamp, rp.index, prompt_count, session, slug)
                all_annotated.append(ap)
            except Exception as e:
                errors.append((f"{session.session_id}:{rp.index}", str(e)))

    # Threading
    episodes = cluster_into_episodes(all_annotated, gap_hours=gap_hours)
    thread_map = assign_threads(episodes)
    assign_arc_positions(episodes)

    # Arc pattern classification
    arc_pattern_counts: Counter[str] = Counter()
    for episode in episodes:
        pattern = classify_arc_pattern(episode)
        arc_pattern_counts[pattern] += 1

    # Aggregate counts
    type_counts: Counter[str] = Counter()
    size_counts: Counter[str] = Counter()
    for ap in all_annotated:
        type_counts[ap.classification.prompt_type] += 1
        size_counts[ap.classification.size_class] += 1

    return NarrateResult(
        prompts=[ap.to_dict() for ap in all_annotated],
        sessions_processed=sessions_processed,
        sessions_skipped=sessions_skipped,
        thread_count=len(thread_map),
        errors=errors,
        type_counts=dict(type_counts),
        size_counts=dict(size_counts),
        arc_pattern_counts=dict(arc_pattern_counts),
    )


def _build_annotated(
    text: str,
    timestamp: str | None,
    index: int,
    prompt_count: int,
    session: AgentSession,
    slug: str,
) -> AnnotatedPrompt:
    """Build a fully annotated prompt from raw data."""
    ap = AnnotatedPrompt()

    ap.source = PromptSource(
        session_id=session.session_id,
        agent=session.agent,
        project_dir=session.project_dir,
        project_slug=slug,
        timestamp=timestamp,
        prompt_index=index,
        prompt_count=prompt_count,
    )

    words = text.split()
    ap.content = PromptContent(
        text=text[:500],
        char_count=len(text),
        word_count=len(words),
        line_count=text.count("\n") + 1,
    )

    prompt_type = classify_prompt_type(text, index)
    size_class = classify_size(len(text))
    position = classify_session_position(index, prompt_count)

    ap.classification = PromptClassification(
        prompt_type=prompt_type,
        size_class=size_class,
        session_position=position,
        is_continuation=prompt_type == "continuation",
        is_interrupted=False,
    )

    ap.signals = PromptSignals(
        opening_phrase=extract_opening_phrase(text),
        imperative_verb=extract_imperative_verb(text),
        mentions_files=extract_file_mentions(text),
        mentions_tools=extract_tool_mentions(text),
        tags=extract_tags(text),
    )

    ap.threading = PromptThreading()

    from organvm_engine.domain import domain_fingerprint
    ap.domain_fingerprint = domain_fingerprint(
        ap.signals.tags, ap.signals.mentions_files,
    )

    ap.raw_text = text
    ap.compute_id()

    return ap


def write_jsonl(prompts: list[dict], output_path: Path) -> None:
    """Write annotated prompts as JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for prompt in prompts:
            f.write(json.dumps(prompt, ensure_ascii=False) + "\n")
