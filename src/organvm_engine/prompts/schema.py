"""Data definitions for prompt narrative analysis."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PromptSource:
    """Where a prompt came from."""
    session_id: str = ""
    agent: str = ""
    project_dir: str = ""
    project_slug: str = ""
    timestamp: Optional[str] = None
    prompt_index: int = 0
    prompt_count: int = 0


@dataclass
class PromptContent:
    """Raw content metrics."""
    text: str = ""
    char_count: int = 0
    word_count: int = 0
    line_count: int = 0


@dataclass
class PromptClassification:
    """Classification signals."""
    prompt_type: str = "command"
    size_class: str = "short"
    session_position: str = "middle"
    is_continuation: bool = False
    is_interrupted: bool = False


@dataclass
class PromptSignals:
    """Extracted semantic signals."""
    opening_phrase: str = ""
    imperative_verb: str = ""
    mentions_files: list[str] = field(default_factory=list)
    mentions_tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class PromptThreading:
    """Narrative thread assignment."""
    thread_id: str = ""
    thread_label: str = ""
    arc_position: str = "development"


@dataclass
class AnnotatedPrompt:
    """Fully enriched prompt with all analysis layers."""
    id: str = ""
    source: PromptSource = field(default_factory=PromptSource)
    content: PromptContent = field(default_factory=PromptContent)
    classification: PromptClassification = field(default_factory=PromptClassification)
    signals: PromptSignals = field(default_factory=PromptSignals)
    threading: PromptThreading = field(default_factory=PromptThreading)
    domain_fingerprint: str = ""
    raw_text: str = ""

    def compute_id(self) -> None:
        key = f"{self.source.session_id}|{self.source.prompt_index}"
        self.id = hashlib.sha256(key.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": {
                "session_id": self.source.session_id,
                "agent": self.source.agent,
                "project_dir": self.source.project_dir,
                "project_slug": self.source.project_slug,
                "timestamp": self.source.timestamp,
                "prompt_index": self.source.prompt_index,
                "prompt_count": self.source.prompt_count,
            },
            "content": {
                "text": self.content.text[:500],
                "char_count": self.content.char_count,
                "word_count": self.content.word_count,
                "line_count": self.content.line_count,
            },
            "classification": {
                "prompt_type": self.classification.prompt_type,
                "size_class": self.classification.size_class,
                "session_position": self.classification.session_position,
                "is_continuation": self.classification.is_continuation,
                "is_interrupted": self.classification.is_interrupted,
            },
            "signals": {
                "opening_phrase": self.signals.opening_phrase,
                "imperative_verb": self.signals.imperative_verb,
                "mentions_files": self.signals.mentions_files,
                "mentions_tools": self.signals.mentions_tools,
                "tags": self.signals.tags,
            },
            "threading": {
                "thread_id": self.threading.thread_id,
                "thread_label": self.threading.thread_label,
                "arc_position": self.threading.arc_position,
            },
            "domain_fingerprint": self.domain_fingerprint,
            "raw_text": self.raw_text,
        }


@dataclass
class RawPrompt:
    """Minimal prompt extracted from a session before enrichment."""
    text: str
    timestamp: Optional[str] = None
    index: int = 0


@dataclass
class NarrateResult:
    """Result of narrating all prompts."""
    prompts: list[dict]
    sessions_processed: int
    sessions_skipped: int
    thread_count: int
    errors: list[tuple[str, str]]
    type_counts: dict[str, int] = field(default_factory=dict)
    size_counts: dict[str, int] = field(default_factory=dict)
    arc_pattern_counts: dict[str, int] = field(default_factory=dict)
