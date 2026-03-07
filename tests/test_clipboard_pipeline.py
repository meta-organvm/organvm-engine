"""Tests for clipboard pipeline orchestration."""

from __future__ import annotations

from unittest.mock import patch

from organvm_engine.prompts.clipboard.classifier import build_prompt_record
from organvm_engine.prompts.clipboard.export import export_json, export_markdown
from organvm_engine.prompts.clipboard.pipeline import run_pipeline
from organvm_engine.prompts.clipboard.schema import (
    ClipboardExportStats,
    ClipboardItem,
)
from organvm_engine.prompts.clipboard.session import compute_sessions, deduplicate


def _make_items() -> list[ClipboardItem]:
    """Create a small set of test clipboard items."""
    return [
        ClipboardItem(
            id=1, app="Claude", bundle_id="com.anthropic.claude",
            timestamp="2025-01-15T10:00:00", date="2025-01-15", time="10:00:00",
            text="Create a Python function that validates email addresses using regex",
        ),
        ClipboardItem(
            id=2, app="Claude", bundle_id="com.anthropic.claude",
            timestamp="2025-01-15T10:05:00", date="2025-01-15", time="10:05:00",
            text="How do I add type hints to this function?",
        ),
        ClipboardItem(
            id=3, app="Claude", bundle_id="com.anthropic.claude",
            timestamp="2025-01-15T11:00:00", date="2025-01-15", time="11:00:00",
            text="Deploy the Solana smart contract on devnet with anchor test",
        ),
    ]


class TestPipelineIntegration:
    def test_classify_dedup_session(self):
        """Test the classify -> dedup -> session-cluster chain."""
        items = _make_items()

        # Classify
        from organvm_engine.prompts.clipboard.classifier import classify_as_prompt

        prompts = []
        for item in items:
            is_prompt, signals = classify_as_prompt(item)
            assert is_prompt, f"Item {item.id} should be classified as prompt"
            prompts.append(build_prompt_record(item, signals))

        # Dedup
        deduped, dupe_count = deduplicate(prompts)
        assert len(deduped) == 3
        assert dupe_count == 0

        # Session cluster
        sessions, summaries = compute_sessions(deduped)
        # Items 1 & 2 are 5 min apart (same session), item 3 is 55 min later (new session)
        assert len(summaries) == 2
        assert summaries[0].size == 2
        assert summaries[1].size == 1

    def test_export_json(self, tmp_path):
        items = _make_items()
        from organvm_engine.prompts.clipboard.classifier import classify_as_prompt

        prompts = []
        for item in items:
            is_prompt, signals = classify_as_prompt(item)
            if is_prompt:
                prompts.append(build_prompt_record(item, signals))

        deduped, dupe_count = deduplicate(prompts)
        _sessions, summaries = compute_sessions(deduped)

        stats = ClipboardExportStats(
            total_items=3, prompts_found=3, dupes_removed=0,
            unique_prompts=3, date_range="2025-01-15 to 2025-01-15",
            rejection_reasons={}, total_sessions=2,
            multi_prompt_sessions=1, multi_app_sessions=0,
            avg_session_size=1.5, max_session_size=2,
        )

        json_path = tmp_path / "export.json"
        export_json(deduped, stats, summaries, json_path)
        assert json_path.exists()

        import json

        data = json.loads(json_path.read_text())
        assert data["total"] == 3
        assert len(data["prompts"]) == 3
        assert len(data["sessions"]) == 2
        assert "stats" in data

    def test_export_markdown(self, tmp_path):
        items = _make_items()
        from organvm_engine.prompts.clipboard.classifier import classify_as_prompt

        prompts = []
        for item in items:
            is_prompt, signals = classify_as_prompt(item)
            if is_prompt:
                prompts.append(build_prompt_record(item, signals))

        deduped, _ = deduplicate(prompts)
        _, summaries = compute_sessions(deduped)

        stats = ClipboardExportStats(
            total_items=3, prompts_found=3, dupes_removed=0,
            unique_prompts=3, date_range="2025-01-15 to 2025-01-15",
            rejection_reasons={}, total_sessions=2,
            multi_prompt_sessions=1, multi_app_sessions=0,
            avg_session_size=1.5, max_session_size=2,
        )

        md_path = tmp_path / "export.md"
        export_markdown(deduped, stats, summaries, md_path)
        assert md_path.exists()

        content = md_path.read_text()
        assert "AI Prompts" in content
        assert "Summary by Category" in content
        assert "Session Statistics" in content

    def test_run_pipeline_dry_run(self):
        """Test run_pipeline with mocked load_items."""
        items = _make_items()
        with patch(
            "organvm_engine.prompts.clipboard.pipeline.load_items",
            return_value=items,
        ):
            result = run_pipeline(dry_run=True)

        assert result.stats.total_items == 3
        assert result.stats.unique_prompts == 3
        assert len(result.prompts) == 3
        assert len(result.session_summaries) == 2

    def test_run_pipeline_empty(self):
        """Test run_pipeline with no items."""
        with patch(
            "organvm_engine.prompts.clipboard.pipeline.load_items",
            return_value=[],
        ):
            result = run_pipeline(dry_run=True)

        assert result.stats.total_items == 0
        assert len(result.prompts) == 0
