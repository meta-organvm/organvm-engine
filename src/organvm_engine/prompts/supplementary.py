"""Bridge module for supplementary prompt sources (SYS-073).

Architecture decision: the engine handles structured session extraction
(Claude JSONL, Gemini JSON, Codex JSONL). A separate pipeline at
praxis-perpetua/prompt-corpus/ingest-supplementary.py handles
supplementary sources (Clipboard, ChatGPT MD, Claude /export TXT,
SpecStory). This module bridges the two at narration time by discovering,
loading, and merging the supplementary JSONL into the engine's stream.

Deduplication uses SHA-256 of the first 200 characters of prompt text.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# The canonical filename produced by ingest-supplementary.py.
SUPPLEMENTARY_FILENAME = "supplementary-prompts.jsonl"

# Subdirectory within the corpus where prompt data lives.
PROMPT_CORPUS_SUBDIR = "prompt-corpus"


def _text_hash(text: str) -> str:
    """SHA-256 hash of the first 200 characters, used for deduplication."""
    return hashlib.sha256(text[:200].encode("utf-8")).hexdigest()


def discover_supplementary_prompts(corpus_dir: Path) -> Path | None:
    """Locate supplementary-prompts.jsonl within the corpus directory.

    Checks two locations:
    1. corpus_dir / prompt-corpus / supplementary-prompts.jsonl
    2. corpus_dir / supplementary-prompts.jsonl (flat layout fallback)

    Returns the path if found, None otherwise.
    """
    primary = corpus_dir / PROMPT_CORPUS_SUBDIR / SUPPLEMENTARY_FILENAME
    if primary.is_file():
        return primary

    fallback = corpus_dir / SUPPLEMENTARY_FILENAME
    if fallback.is_file():
        return fallback

    return None


def load_supplementary_prompts(jsonl_path: Path) -> list[dict]:
    """Read supplementary-prompts.jsonl and return normalized entries.

    Each entry is expected to follow the AnnotatedPrompt.to_dict() schema
    produced by ingest-supplementary.py. Malformed lines are silently
    skipped to avoid blocking the merge on a single bad record.
    """
    entries: list[dict] = []

    with jsonl_path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Minimum viable entry: must have text somewhere we can hash.
            text = _extract_text(entry)
            if not text:
                continue

            entries.append(entry)

    return entries


def merge_prompt_streams(
    engine_prompts: list[dict],
    supplementary_prompts: list[dict],
) -> list[dict]:
    """Merge engine and supplementary prompt streams.

    Deduplication: SHA-256 of first 200 chars of prompt text. Engine
    prompts take priority (added first, so their hash claims the slot).

    Sort: by timestamp ascending, with empty/missing timestamps sorted
    to the end.
    """
    seen: set[str] = set()
    merged: list[dict] = []

    for entry in engine_prompts:
        text = _extract_text(entry)
        if not text:
            continue
        h = _text_hash(text)
        if h not in seen:
            seen.add(h)
            merged.append(entry)

    for entry in supplementary_prompts:
        text = _extract_text(entry)
        if not text:
            continue
        h = _text_hash(text)
        if h not in seen:
            seen.add(h)
            merged.append(entry)

    merged.sort(key=_timestamp_sort_key)
    return merged


def _extract_text(entry: dict) -> str:
    """Extract prompt text from an entry dict.

    Handles both the AnnotatedPrompt.to_dict() layout (content.text or
    raw_text) and flat dicts with a top-level text field.
    """
    # AnnotatedPrompt layout: raw_text is the full text.
    raw = entry.get("raw_text", "")
    if raw:
        return raw

    # Nested content.text (may be truncated to 500 chars in engine output,
    # but still usable for dedup hashing).
    content = entry.get("content", {})
    if isinstance(content, dict):
        ct = content.get("text", "")
        if ct:
            return ct

    # Flat dict fallback.
    return entry.get("text", "")


def _timestamp_sort_key(entry: dict) -> tuple[int, str]:
    """Sort key: entries with timestamps first (ascending), then the rest."""
    ts = ""

    # AnnotatedPrompt layout: source.timestamp
    source = entry.get("source", {})
    if isinstance(source, dict):
        ts = source.get("timestamp", "") or ""

    # Flat dict fallback
    if not ts:
        ts = entry.get("timestamp", "") or ""

    if ts:
        return (0, ts)
    return (1, "")
