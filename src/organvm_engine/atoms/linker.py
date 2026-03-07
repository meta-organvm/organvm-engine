"""Cross-system Jaccard matcher linking atomized tasks to annotated prompts.

Reads both JSONL outputs and finds content-based matches using domain sets
(tags + file references). Supports per-prompt and per-thread matching.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.domain import domain_set
from organvm_engine.plans.graph import jaccard_similarity
from organvm_engine.prompts.audit import _GENERIC_TAGS, EMPTY_FINGERPRINT


@dataclass
class AtomLink:
    """A content-based link between a task and a prompt (or thread)."""
    task_id: str
    prompt_id: str
    jaccard: float
    shared_tags: list[str] = field(default_factory=list)
    shared_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "prompt_id": self.prompt_id,
            "jaccard": round(self.jaccard, 4),
            "shared_tags": self.shared_tags,
            "shared_refs": self.shared_refs,
        }


def _load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    items = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if stripped:
                items.append(json.loads(stripped))
    return items


def _extract_task_domain(task: dict) -> tuple[list[str], list[str]]:
    """Extract tags and file_refs from an atomized task dict."""
    tags = task.get("tags", [])
    files_touched = task.get("files_touched", [])
    file_refs = [
        ft["path"] if isinstance(ft, dict) else ft
        for ft in files_touched
    ]
    return tags, file_refs


def _extract_prompt_domain(prompt: dict) -> tuple[list[str], list[str]]:
    """Extract tags and file mentions from an annotated prompt dict."""
    signals = prompt.get("signals", {})
    tags = signals.get("tags", [])
    file_refs = signals.get("mentions_files", [])
    return tags, file_refs


def compute_links(
    tasks_path: Path,
    prompts_path: Path,
    threshold: float = 0.30,
    by_thread: bool = False,
) -> list[AtomLink]:
    """Compute content-based links between tasks and prompts.

    Args:
        tasks_path: Path to atomized-tasks.jsonl.
        prompts_path: Path to annotated-prompts.jsonl.
        threshold: Minimum Jaccard similarity to emit a link.
        by_thread: If True, aggregate prompts per thread before comparison
            (higher recall, coarser granularity).

    Returns:
        List of AtomLink objects sorted by Jaccard descending.
    """
    tasks = _load_jsonl(tasks_path)
    prompts = _load_jsonl(prompts_path)

    # Filter out items with empty-string fingerprints (no content DNA)
    tasks = [t for t in tasks
             if not t.get("domain_fingerprint", "").startswith(EMPTY_FINGERPRINT)]
    prompts = [p for p in prompts
               if not p.get("domain_fingerprint", "").startswith(EMPTY_FINGERPRINT)]

    # Build task domain sets
    task_domains: list[tuple[str, set[str], list[str], list[str]]] = []
    for t in tasks:
        tid = t.get("id", "")
        tags, refs = _extract_task_domain(t)
        ds = domain_set(tags, refs)
        if ds:
            task_domains.append((tid, ds, tags, refs))

    if by_thread:
        return _link_by_thread(task_domains, prompts, threshold)
    return _link_by_prompt(task_domains, prompts, threshold)


def _link_by_prompt(
    task_domains: list[tuple[str, set[str], list[str], list[str]]],
    prompts: list[dict],
    threshold: float,
) -> list[AtomLink]:
    """Per-prompt matching (fine-grained)."""
    links: list[AtomLink] = []

    for p in prompts:
        pid = p.get("id", "")
        p_tags, p_refs = _extract_prompt_domain(p)
        p_set = domain_set(p_tags, p_refs)
        if not p_set:
            continue

        for tid, t_set, t_tags, t_refs in task_domains:
            j = jaccard_similarity(p_set, t_set)
            if j >= threshold:
                t_lower = {t.lower() for t in t_tags}
                p_lower = {t.lower() for t in p_tags}
                shared_tags = sorted(t_lower & p_lower)
                shared_refs = sorted(set(t_refs) & set(p_refs))
                # Skip links based only on generic tags with no shared refs
                specific_tags = [t for t in shared_tags if t not in _GENERIC_TAGS]
                if not specific_tags and not shared_refs:
                    continue
                links.append(AtomLink(
                    task_id=tid,
                    prompt_id=pid,
                    jaccard=j,
                    shared_tags=shared_tags,
                    shared_refs=shared_refs,
                ))

    links.sort(key=lambda x: -x.jaccard)
    return links


def _link_by_thread(
    task_domains: list[tuple[str, set[str], list[str], list[str]]],
    prompts: list[dict],
    threshold: float,
) -> list[AtomLink]:
    """Per-thread matching: aggregate all prompts in a thread into one domain set."""
    # Group prompts by thread_id
    thread_prompts: dict[str, list[dict]] = defaultdict(list)
    for p in prompts:
        thread_id = p.get("threading", {}).get("thread_id", "")
        if thread_id:
            thread_prompts[thread_id].append(p)

    links: list[AtomLink] = []

    for thread_id, t_prompts in thread_prompts.items():
        # Aggregate domain set across all prompts in thread
        all_tags: list[str] = []
        all_refs: list[str] = []
        for p in t_prompts:
            p_tags, p_refs = _extract_prompt_domain(p)
            all_tags.extend(p_tags)
            all_refs.extend(p_refs)

        thread_set = domain_set(all_tags, all_refs)
        if not thread_set:
            continue

        for tid, t_set, t_tags, t_refs in task_domains:
            j = jaccard_similarity(thread_set, t_set)
            if j >= threshold:
                t_lower = {t.lower() for t in t_tags}
                a_lower = {t.lower() for t in all_tags}
                shared_tags = sorted(t_lower & a_lower)
                shared_refs = sorted(set(t_refs) & set(all_refs))
                # Skip links based only on generic tags with no shared refs
                specific_tags = [t for t in shared_tags if t not in _GENERIC_TAGS]
                if not specific_tags and not shared_refs:
                    continue
                links.append(AtomLink(
                    task_id=tid,
                    prompt_id=f"thread:{thread_id}",
                    jaccard=j,
                    shared_tags=shared_tags,
                    shared_refs=shared_refs,
                ))

    links.sort(key=lambda x: -x.jaccard)
    return links
