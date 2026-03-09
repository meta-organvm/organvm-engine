"""Tests for prompts/clipboard/schema.py — clipboard dataclass serialization."""

from organvm_engine.prompts.clipboard.schema import (
    ClipboardExportStats,
    ClipboardItem,
    ClipboardPrompt,
    ClipboardSession,
)


class TestClipboardPrompt:
    def test_to_dict_without_session(self):
        p = ClipboardPrompt(
            id=1, content_hash="abc", date="2026-03-01", time="10:00:00",
            timestamp="2026-03-01T10:00:00", source_app="Claude",
            bundle_id="com.claude", category="code_generation",
            confidence="high", signals=["verb"], word_count=10,
            char_count=50, multi_turn=False, file_refs=["test.py"],
            tech_mentions=["python"], text="implement feature",
        )
        d = p.to_dict()
        assert d["id"] == 1
        assert d["category"] == "code_generation"
        assert d["file_refs"] == ["test.py"]
        assert "session_id" not in d

    def test_to_dict_with_session(self):
        p = ClipboardPrompt(
            id=1, content_hash="abc", date="2026-03-01", time="10:00:00",
            timestamp="2026-03-01T10:00:00", source_app="Claude",
            bundle_id="com.claude", category="code_generation",
            confidence="high", signals=[], word_count=10, char_count=50,
            multi_turn=False, file_refs=[], tech_mentions=[],
            text="test", session_id=5, position_in_session=2,
            session_size=3, prev_gap_minutes=1.5, next_gap_minutes=2.0,
        )
        d = p.to_dict()
        assert d["session_id"] == 5
        assert d["position_in_session"] == 2
        assert d["session_size"] == 3
        assert d["prev_gap_minutes"] == 1.5
        assert d["next_gap_minutes"] == 2.0


class TestClipboardExportStats:
    def test_to_dict(self):
        stats = ClipboardExportStats(
            total_items=100, prompts_found=50, dupes_removed=5,
            unique_prompts=45, date_range="2026-03-01 to 2026-03-08",
            rejection_reasons={"too_short": 30},
            total_sessions=10, multi_prompt_sessions=5,
            multi_app_sessions=2, avg_session_size=4.5,
            max_session_size=12,
            session_size_distribution={1: 5, 2: 3, 5: 2},
        )
        d = stats.to_dict()
        assert d["total_items"] == 100
        assert d["unique_prompts"] == 45
        assert d["rejection_reasons"]["too_short"] == 30
        # Keys are converted to strings
        assert d["session_size_distribution"]["1"] == 5
        assert d["session_size_distribution"]["2"] == 3

    def test_to_dict_empty_distribution(self):
        stats = ClipboardExportStats(
            total_items=0, prompts_found=0, dupes_removed=0,
            unique_prompts=0, date_range="", rejection_reasons={},
            total_sessions=0, multi_prompt_sessions=0,
            multi_app_sessions=0, avg_session_size=0.0,
            max_session_size=0,
        )
        d = stats.to_dict()
        assert d["session_size_distribution"] == {}


class TestClipboardItem:
    def test_fields(self):
        item = ClipboardItem(
            id=42, app="Claude", bundle_id="com.claude",
            timestamp="2026-03-01T10:00:00", date="2026-03-01",
            time="10:00:00", text="hello world",
        )
        assert item.id == 42
        assert item.app == "Claude"
        assert item.text == "hello world"


class TestClipboardSession:
    def test_fields(self):
        session = ClipboardSession(
            session_id=1, start="2026-03-01T10:00:00",
            end="2026-03-01T10:30:00", duration_minutes=30.0,
            size=5, apps={"Claude": 3, "Cursor": 2},
            categories={"code_generation": 5},
            dominant_category="code_generation",
            multi_app=True, prompt_ids=[1, 2, 3, 4, 5],
        )
        assert session.session_id == 1
        assert session.size == 5
        assert session.multi_app is True
        assert len(session.prompt_ids) == 5
