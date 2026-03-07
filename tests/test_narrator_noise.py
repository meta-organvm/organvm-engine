"""Tests for Rec 1: pre-narration noise filter in narrator.py."""

from __future__ import annotations

from unittest.mock import patch

from organvm_engine.prompts.audit import _classify_noise


def test_classify_noise_tool_loaded():
    assert _classify_noise("Tool loaded.") == "tool_loaded"


def test_classify_noise_request_interrupted():
    assert _classify_noise("[Request interrupted by user") == "request_interrupted"


def test_classify_noise_empty():
    assert _classify_noise("") == "empty"
    assert _classify_noise("   ") == "empty"


def test_classify_noise_task_notification():
    assert _classify_noise("<task-notification>foo</task-notification>") == "task_notification"


def test_classify_noise_system_reminder():
    assert _classify_noise("<system-reminder>bar</system-reminder>") == "system_reminder"


def test_classify_noise_clear():
    assert _classify_noise("/clear") == "clear_command"


def test_classify_noise_real_prompt():
    assert _classify_noise("Implement the audit recommendations") is None
    assert _classify_noise("Fix the bug in linker.py") is None
    assert _classify_noise("Add tests for the new feature") is None


def test_narrator_skips_noise():
    """Verify noise prompts are excluded from narration output."""
    from pathlib import Path

    from organvm_engine.prompts.schema import RawPrompt
    from organvm_engine.session.agents import AgentSession

    fake_session = AgentSession(
        agent="claude",
        session_id="test-noise-session",
        file_path=Path("/fake/transcript.jsonl"),
        project_dir="/fake/project",
        started=None,
        ended=None,
        size_bytes=0,
    )

    raw_prompts = [
        RawPrompt(text="Tool loaded.", index=0),
        RawPrompt(text="Implement feature X", index=1),
        RawPrompt(text="", index=2),
        RawPrompt(text="<system-reminder>context</system-reminder>", index=3),
        RawPrompt(text="Fix the bug in linker.py", index=4),
    ]

    with (
        patch("organvm_engine.prompts.narrator.discover_all_sessions", return_value=[fake_session]),
        patch("organvm_engine.prompts.narrator.extract_prompts", return_value=raw_prompts),
    ):
        from organvm_engine.prompts.narrator import narrate_prompts

        result = narrate_prompts()

    # 3 noise prompts skipped (Tool loaded, empty, system-reminder)
    assert result.noise_skipped == 3
    # 2 signal prompts kept
    assert len(result.prompts) == 2


def test_narrator_keeps_signal():
    """Verify real prompts pass through the noise filter."""
    from pathlib import Path

    from organvm_engine.prompts.schema import RawPrompt
    from organvm_engine.session.agents import AgentSession

    fake_session = AgentSession(
        agent="claude",
        session_id="test-signal-session",
        file_path=Path("/fake/transcript.jsonl"),
        project_dir="/fake/project",
        started=None,
        ended=None,
        size_bytes=0,
    )

    raw_prompts = [
        RawPrompt(text="Implement the five audit recommendations from the plan", index=0),
        RawPrompt(text="Run the tests and fix any failures", index=1),
    ]

    with (
        patch("organvm_engine.prompts.narrator.discover_all_sessions", return_value=[fake_session]),
        patch("organvm_engine.prompts.narrator.extract_prompts", return_value=raw_prompts),
    ):
        from organvm_engine.prompts.narrator import narrate_prompts

        result = narrate_prompts()

    assert result.noise_skipped == 0
    assert len(result.prompts) == 2
