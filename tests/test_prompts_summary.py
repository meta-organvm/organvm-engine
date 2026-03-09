"""Tests for prompts/summary.py — narrative summary markdown generation."""

from organvm_engine.prompts.schema import NarrateResult
from organvm_engine.prompts.summary import generate_narrative_summary


def _make_prompt_dict(
    session_id: str = "s1",
    project_slug: str = "meta-organvm/engine",
    timestamp: str = "2026-03-01T10:00:00Z",
    prompt_type: str = "command",
    size_class: str = "short",
    thread_id: str = "t1",
    thread_label: str = "meta-organvm/engine/implement-2026-03-01",
    imperative_verb: str = "implement",
    tags: list | None = None,
) -> dict:
    return {
        "id": f"{session_id}-0",
        "source": {
            "session_id": session_id,
            "agent": "claude",
            "project_dir": "/Workspace/meta-organvm/organvm-engine",
            "project_slug": project_slug,
            "timestamp": timestamp,
            "prompt_index": 0,
            "prompt_count": 1,
        },
        "content": {"text": "test", "char_count": 100, "word_count": 20, "line_count": 1},
        "classification": {
            "prompt_type": prompt_type,
            "size_class": size_class,
            "session_position": "opening",
            "is_continuation": False,
            "is_interrupted": False,
        },
        "signals": {
            "opening_phrase": "implement the feature",
            "imperative_verb": imperative_verb,
            "mentions_files": [],
            "mentions_tools": [],
            "tags": tags or [],
        },
        "threading": {
            "thread_id": thread_id,
            "thread_label": thread_label,
            "arc_position": "development",
        },
        "domain_fingerprint": "abc123",
        "raw_text": "implement the feature",
    }


class TestGenerateNarrativeSummary:
    def test_header(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict()],
            sessions_processed=1,
            sessions_skipped=0,
            thread_count=1,
            errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "# Prompt Narrative Analysis" in md
        assert "**Sessions**: 1" in md
        assert "**Prompts**: 1" in md
        assert "**Threads**: 1" in md

    def test_type_distribution_table(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict(prompt_type="command")],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Prompt Type Distribution" in md
        assert "| command |" in md

    def test_size_distribution_table(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict()],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Size Distribution" in md
        assert "| short |" in md

    def test_thread_table(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict(thread_id="t1", thread_label="proj/implement-2026")],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Top Narrative Threads" in md

    def test_temporal_activity(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict(timestamp="2026-03-01T10:00:00Z")],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Temporal Activity" in md
        assert "2026-03" in md

    def test_imperative_verbs(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict(imperative_verb="deploy")],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Top Imperative Verbs" in md
        assert "| deploy |" in md

    def test_arc_patterns(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict()],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
            arc_pattern_counts={"steady-build": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Narrative Arc Patterns" in md
        assert "steady-build" in md

    def test_tags(self):
        result = NarrateResult(
            prompts=[_make_prompt_dict(tags=["python", "testing"])],
            sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        assert "## Recurring Themes" in md
        assert "| python |" in md

    def test_empty_prompts(self):
        result = NarrateResult(
            prompts=[], sessions_processed=0, sessions_skipped=0,
            thread_count=0, errors=[],
        )
        md = generate_narrative_summary(result)
        assert "# Prompt Narrative Analysis" in md
        assert "**Prompts**: 0" in md

    def test_no_timestamp_skips_temporal(self):
        p = _make_prompt_dict(timestamp="")
        result = NarrateResult(
            prompts=[p], sessions_processed=1, sessions_skipped=0,
            thread_count=1, errors=[],
            type_counts={"command": 1},
            size_counts={"short": 1},
        )
        md = generate_narrative_summary(result)
        # Temporal section omitted when no valid timestamps
        assert "## Temporal Activity" not in md
