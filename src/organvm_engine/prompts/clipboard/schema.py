"""Data definitions for clipboard prompt extraction and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClipboardItem:
    """Raw item extracted from Paste.app database."""

    id: int
    app: str
    bundle_id: str
    timestamp: str
    date: str
    time: str
    text: str


@dataclass
class ClipboardPrompt:
    """Classified clipboard prompt with metadata."""

    id: int
    content_hash: str
    date: str
    time: str
    timestamp: str
    source_app: str
    bundle_id: str
    category: str
    confidence: str
    signals: list[str]
    word_count: int
    char_count: int
    multi_turn: bool
    file_refs: list[str]
    tech_mentions: list[str]
    text: str
    # Session fields (attached during session clustering)
    session_id: int | None = None
    position_in_session: int | None = None
    session_size: int | None = None
    prev_gap_minutes: float | None = None
    next_gap_minutes: float | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "content_hash": self.content_hash,
            "date": self.date,
            "time": self.time,
            "timestamp": self.timestamp,
            "source_app": self.source_app,
            "bundle_id": self.bundle_id,
            "category": self.category,
            "confidence": self.confidence,
            "signals": self.signals,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "multi_turn": self.multi_turn,
            "file_refs": self.file_refs,
            "tech_mentions": self.tech_mentions,
            "text": self.text,
        }
        if self.session_id is not None:
            d["session_id"] = self.session_id
            d["position_in_session"] = self.position_in_session
            d["session_size"] = self.session_size
            d["prev_gap_minutes"] = self.prev_gap_minutes
            d["next_gap_minutes"] = self.next_gap_minutes
        return d


@dataclass
class ClipboardSession:
    """Session summary computed from temporally clustered prompts."""

    session_id: int
    start: str
    end: str
    duration_minutes: float
    size: int
    apps: dict[str, int]
    categories: dict[str, int]
    dominant_category: str
    multi_app: bool
    prompt_ids: list[int]


@dataclass
class ClipboardExportStats:
    """Top-level statistics for a clipboard extraction run."""

    total_items: int
    prompts_found: int
    dupes_removed: int
    unique_prompts: int
    date_range: str
    rejection_reasons: dict[str, int]
    total_sessions: int
    multi_prompt_sessions: int
    multi_app_sessions: int
    avg_session_size: float
    max_session_size: int
    session_size_distribution: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_items": self.total_items,
            "prompts_found": self.prompts_found,
            "dupes_removed": self.dupes_removed,
            "unique_prompts": self.unique_prompts,
            "date_range": self.date_range,
            "rejection_reasons": self.rejection_reasons,
            "total_sessions": self.total_sessions,
            "multi_prompt_sessions": self.multi_prompt_sessions,
            "multi_app_sessions": self.multi_app_sessions,
            "avg_session_size": self.avg_session_size,
            "max_session_size": self.max_session_size,
            "session_size_distribution": {
                str(k): v for k, v in sorted(self.session_size_distribution.items())
            },
        }
