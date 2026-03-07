"""Tests for clipboard session clustering and deduplication."""

from __future__ import annotations

from organvm_engine.prompts.clipboard.schema import ClipboardPrompt
from organvm_engine.prompts.clipboard.session import compute_sessions, deduplicate


def _prompt(
    id: int,
    timestamp: str,
    text: str = "test prompt",
    content_hash: str | None = None,
) -> ClipboardPrompt:
    return ClipboardPrompt(
        id=id,
        content_hash=content_hash or f"hash_{id}",
        date=timestamp[:10],
        time=timestamp[11:19],
        timestamp=timestamp,
        source_app="Claude",
        bundle_id="com.anthropic.claude",
        category="General AI Usage",
        confidence="medium",
        signals=["imperative_opener"],
        word_count=len(text.split()),
        char_count=len(text),
        multi_turn=False,
        file_refs=[],
        tech_mentions=[],
        text=text,
    )


class TestDeduplicate:
    def test_exact_hash_dedup(self):
        prompts = [
            _prompt(1, "2025-01-15T10:00:00", "hello world", content_hash="abc123"),
            _prompt(2, "2025-01-15T10:05:00", "hello world", content_hash="abc123"),
            _prompt(3, "2025-01-15T10:10:00", "different text", content_hash="def456"),
        ]
        result, dupe_count = deduplicate(prompts)
        assert len(result) == 2
        assert dupe_count == 1
        assert result[0].id == 1
        assert result[1].id == 3

    def test_prefix_dedup(self):
        prefix = "x" * 150
        prompts = [
            _prompt(1, "2025-01-15T10:00:00", prefix + " ending A", content_hash="h1"),
            _prompt(2, "2025-01-15T10:05:00", prefix + " ending B", content_hash="h2"),
        ]
        result, dupe_count = deduplicate(prompts)
        assert len(result) == 1
        assert dupe_count == 1

    def test_no_dupes(self):
        prompts = [
            _prompt(1, "2025-01-15T10:00:00", "alpha", content_hash="h1"),
            _prompt(2, "2025-01-15T10:05:00", "beta", content_hash="h2"),
        ]
        result, dupe_count = deduplicate(prompts)
        assert len(result) == 2
        assert dupe_count == 0

    def test_empty_input(self):
        result, dupe_count = deduplicate([])
        assert result == []
        assert dupe_count == 0


class TestComputeSessions:
    def test_single_session(self):
        prompts = [
            _prompt(1, "2025-01-15T10:00:00"),
            _prompt(2, "2025-01-15T10:10:00"),
            _prompt(3, "2025-01-15T10:20:00"),
        ]
        sessions, summaries = compute_sessions(prompts)
        assert len(sessions) == 1
        assert len(summaries) == 1
        assert summaries[0].size == 3
        assert summaries[0].duration_minutes == 20.0

    def test_gap_splits_sessions(self):
        prompts = [
            _prompt(1, "2025-01-15T10:00:00"),
            _prompt(2, "2025-01-15T10:10:00"),
            _prompt(3, "2025-01-15T11:00:00"),  # 50 min gap > 30 min threshold
        ]
        sessions, summaries = compute_sessions(prompts)
        assert len(sessions) == 2
        assert len(summaries) == 2
        assert summaries[0].size == 2
        assert summaries[1].size == 1

    def test_session_fields_attached(self):
        prompts = [
            _prompt(1, "2025-01-15T10:00:00"),
            _prompt(2, "2025-01-15T10:10:00"),
        ]
        sessions, summaries = compute_sessions(prompts)
        p0 = sessions[0][0]
        p1 = sessions[0][1]
        assert p0.session_id == 0
        assert p0.position_in_session == 1
        assert p0.session_size == 2
        assert p0.prev_gap_minutes is None
        assert p0.next_gap_minutes == 10.0
        assert p1.position_in_session == 2
        assert p1.prev_gap_minutes == 10.0
        assert p1.next_gap_minutes is None

    def test_empty_input(self):
        sessions, summaries = compute_sessions([])
        assert sessions == []
        assert summaries == []

    def test_single_prompt(self):
        prompts = [_prompt(1, "2025-01-15T10:00:00")]
        sessions, summaries = compute_sessions(prompts)
        assert len(sessions) == 1
        assert summaries[0].size == 1
        assert summaries[0].duration_minutes == 0.0

    def test_multi_app_detection(self):
        p1 = _prompt(1, "2025-01-15T10:00:00")
        p1.source_app = "Claude"
        p2 = _prompt(2, "2025-01-15T10:10:00")
        p2.source_app = "ChatGPT"
        sessions, summaries = compute_sessions([p1, p2])
        assert summaries[0].multi_app is True
        assert summaries[0].apps == {"Claude": 1, "ChatGPT": 1}

    def test_dominant_category(self):
        p1 = _prompt(1, "2025-01-15T10:00:00")
        p1.category = "MCP/Tooling"
        p2 = _prompt(2, "2025-01-15T10:10:00")
        p2.category = "MCP/Tooling"
        p3 = _prompt(3, "2025-01-15T10:20:00")
        p3.category = "GitHub/CI/CD"
        sessions, summaries = compute_sessions([p1, p2, p3])
        assert summaries[0].dominant_category == "MCP/Tooling"
