"""Narrative threading — episode clustering, thread labeling, arc assignment."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta

from organvm_engine.prompts.schema import AnnotatedPrompt


def derive_project_slug(project_dir: str) -> str:
    """Derive canonical project slug from a full project directory path."""
    from organvm_engine.project_slug import slug_from_path
    return slug_from_path(project_dir)


def cluster_into_episodes(
    prompts: list[AnnotatedPrompt],
    gap_hours: float = 24.0,
) -> list[list[AnnotatedPrompt]]:
    """Group prompts by project, then split into episodes by time gap.

    Returns a list of episodes (each a list of AnnotatedPrompts).
    """
    # Group by project_slug
    by_project: dict[str, list[AnnotatedPrompt]] = {}
    for p in prompts:
        slug = p.source.project_slug
        by_project.setdefault(slug, []).append(p)

    episodes: list[list[AnnotatedPrompt]] = []
    gap = timedelta(hours=gap_hours)

    for slug in sorted(by_project):
        project_prompts = by_project[slug]
        # Sort by timestamp then prompt_index
        project_prompts.sort(
            key=lambda p: (p.source.timestamp or "", p.source.prompt_index),
        )

        if not project_prompts:
            continue

        current_episode: list[AnnotatedPrompt] = [project_prompts[0]]

        for i in range(1, len(project_prompts)):
            prev_ts = _parse_ts(project_prompts[i - 1].source.timestamp)
            curr_ts = _parse_ts(project_prompts[i].source.timestamp)

            if prev_ts and curr_ts and (curr_ts - prev_ts) > gap:
                episodes.append(current_episode)
                current_episode = [project_prompts[i]]
            elif project_prompts[i].source.session_id != project_prompts[i - 1].source.session_id:
                # Same project, different session — check if timestamps exist
                if prev_ts and curr_ts:
                    if (curr_ts - prev_ts) > gap:
                        episodes.append(current_episode)
                        current_episode = [project_prompts[i]]
                    else:
                        current_episode.append(project_prompts[i])
                else:
                    current_episode.append(project_prompts[i])
            else:
                current_episode.append(project_prompts[i])

        if current_episode:
            episodes.append(current_episode)

    return episodes


def assign_threads(episodes: list[list[AnnotatedPrompt]]) -> dict[str, str]:
    """Assign thread IDs and labels to each episode.

    Returns a mapping of thread_id -> thread_label.
    """
    thread_map: dict[str, str] = {}

    for ep_idx, episode in enumerate(episodes):
        if not episode:
            continue

        slug = episode[0].source.project_slug
        first_ts = episode[0].source.timestamp or "unknown"
        first_date = first_ts[:10] if len(first_ts) >= 10 else first_ts

        # Find last date
        last_ts = episode[-1].source.timestamp or first_ts
        last_date = last_ts[:10] if len(last_ts) >= 10 else last_ts

        # Dominant verb
        verb_counts: Counter[str] = Counter()
        for p in episode:
            v = p.signals.imperative_verb
            if v:
                verb_counts[v] += 1
        dominant_verb = verb_counts.most_common(1)[0][0] if verb_counts else "work"

        # Thread ID
        thread_key = f"{slug}|{first_date}|{ep_idx}"
        thread_id = hashlib.sha256(thread_key.encode()).hexdigest()[:12]

        # Thread label
        date_range = first_date if first_date == last_date else f"{first_date}..{last_date}"
        thread_label = f"{slug}/{dominant_verb}-{date_range}"

        thread_map[thread_id] = thread_label

        for p in episode:
            p.threading.thread_id = thread_id
            p.threading.thread_label = thread_label

    return thread_map


def assign_arc_positions(episodes: list[list[AnnotatedPrompt]]) -> None:
    """Assign arc positions within each episode thread."""
    for episode in episodes:
        total = len(episode)
        if total == 0:
            continue

        for i, p in enumerate(episode):
            pct = i / total if total > 1 else 0.5
            ptype = p.classification.prompt_type

            # Type overrides
            if ptype == "plan_invocation":
                p.threading.arc_position = "setup"
            elif ptype == "git_ops" and pct > 0.8:
                p.threading.arc_position = "resolution"
            elif pct < 0.20:
                if ptype in ("context_setting", "exploration", "plan_invocation"):
                    p.threading.arc_position = "setup"
                else:
                    p.threading.arc_position = "setup" if pct < 0.1 else "development"
            elif pct > 0.95:
                p.threading.arc_position = "maintenance"
            elif pct > 0.85:
                p.threading.arc_position = "resolution"
            else:
                p.threading.arc_position = "development"


def classify_arc_pattern(episode: list[AnnotatedPrompt]) -> str:
    """Classify the overall narrative pattern of an episode."""
    if len(episode) <= 2:
        return "single-shot"

    type_counts: Counter[str] = Counter()
    for p in episode:
        type_counts[p.classification.prompt_type] += 1

    total = len(episode)
    first_type = episode[0].classification.prompt_type

    correction_pct = type_counts.get("correction", 0) / total

    if first_type == "plan_invocation":
        return "plan-then-execute"

    if correction_pct > 0.20:
        return "iterative-correction"

    if first_type in ("question", "exploration"):
        return "exploration-first"

    return "steady-build"


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
