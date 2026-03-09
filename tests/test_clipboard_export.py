"""Tests for prompts/clipboard/export.py — JSON and Markdown export."""

import json

from organvm_engine.prompts.clipboard.export import export_json, export_markdown
from organvm_engine.prompts.clipboard.schema import (
    ClipboardExportStats,
    ClipboardPrompt,
    ClipboardSession,
)


def _make_prompt(
    id: int = 1,
    category: str = "code_generation",
    confidence: str = "high",
    source_app: str = "Claude",
    text: str = "implement the feature",
    timestamp: str = "2026-03-01T10:00:00",
    session_id: int | None = None,
    position: int | None = None,
    session_size: int | None = None,
) -> ClipboardPrompt:
    return ClipboardPrompt(
        id=id,
        content_hash="abc123",
        date="2026-03-01",
        time="10:00:00",
        timestamp=timestamp,
        source_app=source_app,
        bundle_id="com.test.app",
        category=category,
        confidence=confidence,
        signals=["imperative_verb"],
        word_count=len(text.split()),
        char_count=len(text),
        multi_turn=False,
        file_refs=[],
        tech_mentions=[],
        text=text,
        session_id=session_id,
        position_in_session=position,
        session_size=session_size,
    )


def _make_stats() -> ClipboardExportStats:
    return ClipboardExportStats(
        total_items=100,
        prompts_found=50,
        dupes_removed=5,
        unique_prompts=45,
        date_range="2026-03-01 to 2026-03-08",
        rejection_reasons={"too_short": 30, "no_signal": 15},
        total_sessions=10,
        multi_prompt_sessions=5,
        multi_app_sessions=2,
        avg_session_size=4.5,
        max_session_size=12,
    )


def _make_session(
    session_id: int = 1,
    size: int = 3,
    prompt_ids: list[int] | None = None,
) -> ClipboardSession:
    return ClipboardSession(
        session_id=session_id,
        start="2026-03-01T10:00:00",
        end="2026-03-01T10:30:00",
        duration_minutes=30.0,
        size=size,
        apps={"Claude": 2, "Cursor": 1},
        categories={"code_generation": 3},
        dominant_category="code_generation",
        multi_app=True,
        prompt_ids=prompt_ids or [1, 2, 3],
    )


class TestExportJson:
    def test_writes_valid_json(self, tmp_path):
        output = tmp_path / "export.json"
        prompts = [_make_prompt(id=1), _make_prompt(id=2)]
        stats = _make_stats()
        sessions = [_make_session()]

        export_json(prompts, stats, sessions, output)

        assert output.exists()
        data = json.loads(output.read_text())
        assert data["total"] == 2
        assert len(data["prompts"]) == 2
        assert len(data["sessions"]) == 1
        assert "generated" in data

    def test_stats_included(self, tmp_path):
        output = tmp_path / "export.json"
        export_json([_make_prompt()], _make_stats(), [], output)
        data = json.loads(output.read_text())
        assert data["stats"]["total_items"] == 100
        assert data["stats"]["prompts_found"] == 50

    def test_session_structure(self, tmp_path):
        output = tmp_path / "export.json"
        session = _make_session(session_id=42, size=5, prompt_ids=[1, 2, 3, 4, 5])
        export_json([], _make_stats(), [session], output)
        data = json.loads(output.read_text())
        s = data["sessions"][0]
        assert s["session_id"] == 42
        assert s["size"] == 5
        assert s["multi_app"] is True

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "nested" / "dir" / "export.json"
        export_json([], _make_stats(), [], output)
        assert output.exists()

    def test_empty_export(self, tmp_path):
        output = tmp_path / "empty.json"
        stats = _make_stats()
        export_json([], stats, [], output)
        data = json.loads(output.read_text())
        assert data["total"] == 0
        assert data["prompts"] == []
        assert data["sessions"] == []


class TestExportMarkdown:
    def test_writes_markdown(self, tmp_path):
        output = tmp_path / "export.md"
        prompts = [_make_prompt(id=1, category="code_generation")]
        stats = _make_stats()
        sessions = [_make_session(session_id=1, size=3, prompt_ids=[1])]

        export_markdown(prompts, stats, sessions, output)

        text = output.read_text()
        assert "# AI Prompts" in text
        assert "code_generation" in text

    def test_category_summary(self, tmp_path):
        output = tmp_path / "export.md"
        prompts = [
            _make_prompt(id=1, category="code_generation"),
            _make_prompt(id=2, category="debugging"),
        ]
        export_markdown(prompts, _make_stats(), [], output)
        text = output.read_text()
        assert "## Summary by Category" in text
        assert "code_generation" in text
        assert "debugging" in text

    def test_app_summary(self, tmp_path):
        output = tmp_path / "export.md"
        prompts = [
            _make_prompt(id=1, source_app="Claude"),
            _make_prompt(id=2, source_app="Cursor"),
        ]
        export_markdown(prompts, _make_stats(), [], output)
        text = output.read_text()
        assert "## Summary by Source App" in text
        assert "Claude" in text
        assert "Cursor" in text

    def test_confidence_distribution(self, tmp_path):
        output = tmp_path / "export.md"
        prompts = [_make_prompt(confidence="high")]
        export_markdown(prompts, _make_stats(), [], output)
        text = output.read_text()
        assert "## Confidence Distribution" in text
        assert "| high |" in text

    def test_session_statistics(self, tmp_path):
        output = tmp_path / "export.md"
        sessions = [_make_session(size=3)]
        export_markdown(
            [_make_prompt(id=i) for i in range(3)],
            _make_stats(),
            sessions,
            output,
        )
        text = output.read_text()
        assert "## Session Statistics" in text

    def test_sessions_timeline(self, tmp_path):
        output = tmp_path / "export.md"
        prompts = [
            _make_prompt(id=1, session_id=1, position=1, session_size=3),
            _make_prompt(id=2, session_id=1, position=2, session_size=3),
            _make_prompt(id=3, session_id=1, position=3, session_size=3),
        ]
        sessions = [_make_session(session_id=1, size=3, prompt_ids=[1, 2, 3])]
        export_markdown(prompts, _make_stats(), sessions, output)
        text = output.read_text()
        assert "## Sessions Timeline" in text

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "deep" / "path" / "export.md"
        export_markdown([], _make_stats(), [], output)
        assert output.exists()

    def test_prompts_by_category(self, tmp_path):
        output = tmp_path / "export.md"
        prompts = [_make_prompt(id=1, category="architecture")]
        export_markdown(prompts, _make_stats(), [], output)
        text = output.read_text()
        assert "## Prompts by Category" in text
        assert "architecture" in text
