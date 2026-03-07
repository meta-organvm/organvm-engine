"""Session clustering and deduplication for clipboard prompts."""

from __future__ import annotations

import re
from datetime import datetime

from organvm_engine.prompts.clipboard.schema import ClipboardPrompt, ClipboardSession

SESSION_GAP_MINUTES = 30


def deduplicate(prompts: list[ClipboardPrompt]) -> tuple[list[ClipboardPrompt], int]:
    """Remove exact and near-duplicate prompts. Keep earliest occurrence."""
    seen_hashes: dict[str, int] = {}
    deduped: list[ClipboardPrompt] = []
    dupe_count = 0

    for p in prompts:
        h = p.content_hash
        if h in seen_hashes:
            dupe_count += 1
            continue
        seen_hashes[h] = len(deduped)
        deduped.append(p)

    # Also catch near-dupes: same first 150 chars normalized
    prefix_seen: dict[str, int] = {}
    final: list[ClipboardPrompt] = []
    for p in deduped:
        prefix = re.sub(r"\s+", " ", p.text[:150].strip().lower())
        if prefix in prefix_seen:
            dupe_count += 1
            continue
        prefix_seen[prefix] = len(final)
        final.append(p)

    return final, dupe_count


def compute_sessions(
    prompts: list[ClipboardPrompt],
) -> tuple[list[list[ClipboardPrompt]], list[ClipboardSession]]:
    """Group prompts into sessions by temporal proximity.

    Uses a 30-minute gap threshold to split sessions.

    Returns:
        (sessions, session_summaries) where each session is a list of prompts
        with session fields attached, and session_summaries is a list of
        ClipboardSession metadata objects.
    """
    if not prompts:
        return [], []

    sessions: list[list[ClipboardPrompt]] = [[prompts[0]]]
    gaps: dict[int, float] = {}

    for i in range(1, len(prompts)):
        prev_ts = datetime.fromisoformat(prompts[i - 1].timestamp)
        curr_ts = datetime.fromisoformat(prompts[i].timestamp)
        gap = (curr_ts - prev_ts).total_seconds() / 60.0
        gaps[i] = gap

        if gap > SESSION_GAP_MINUTES:
            sessions.append([prompts[i]])
        else:
            sessions[-1].append(prompts[i])

    session_summaries: list[ClipboardSession] = []

    for sid, session in enumerate(sessions):
        start_ts = session[0].timestamp
        end_ts = session[-1].timestamp
        start_dt = datetime.fromisoformat(start_ts)
        end_dt = datetime.fromisoformat(end_ts)
        duration = (end_dt - start_dt).total_seconds() / 60.0

        app_counts: dict[str, int] = {}
        cat_counts: dict[str, int] = {}
        prompt_ids: list[int] = []

        for pos, p in enumerate(session):
            app_counts[p.source_app] = app_counts.get(p.source_app, 0) + 1
            cat_counts[p.category] = cat_counts.get(p.category, 0) + 1
            prompt_ids.append(p.id)

            p.session_id = sid
            p.position_in_session = pos + 1
            p.session_size = len(session)

            # Compute gap to previous prompt within session
            if pos > 0:
                prev_dt = datetime.fromisoformat(session[pos - 1].timestamp)
                cur_dt = datetime.fromisoformat(p.timestamp)
                p.prev_gap_minutes = round((cur_dt - prev_dt).total_seconds() / 60.0, 1)
            else:
                p.prev_gap_minutes = None

            # Compute gap to next prompt within session
            if pos < len(session) - 1:
                next_dt = datetime.fromisoformat(session[pos + 1].timestamp)
                cur_dt = datetime.fromisoformat(p.timestamp)
                p.next_gap_minutes = round((next_dt - cur_dt).total_seconds() / 60.0, 1)
            else:
                p.next_gap_minutes = None

        dominant_cat = max(cat_counts, key=lambda k: cat_counts[k])
        multi_app = len(app_counts) > 1

        summary = ClipboardSession(
            session_id=sid,
            start=start_ts,
            end=end_ts,
            duration_minutes=round(duration, 1),
            size=len(session),
            apps=app_counts,
            categories=cat_counts,
            dominant_category=dominant_cat,
            multi_app=multi_app,
            prompt_ids=prompt_ids,
        )
        session_summaries.append(summary)

    return sessions, session_summaries
