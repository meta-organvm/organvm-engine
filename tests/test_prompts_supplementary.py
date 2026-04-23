"""Tests for prompts/supplementary.py — bridge module for supplementary prompt sources."""

import json

from organvm_engine.prompts.supplementary import (
    discover_supplementary_prompts,
    load_supplementary_prompts,
    merge_prompt_streams,
)


def _make_engine_prompt(text: str, timestamp: str = "") -> dict:
    """Build a minimal engine-style prompt dict (AnnotatedPrompt.to_dict layout)."""
    return {
        "id": f"eng-{text[:8]}",
        "source": {
            "session_id": "s1",
            "agent": "claude",
            "project_dir": "/tmp/proj",
            "project_slug": "proj",
            "timestamp": timestamp,
            "prompt_index": 0,
            "prompt_count": 1,
        },
        "content": {
            "text": text[:500],
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": 1,
        },
        "classification": {"prompt_type": "command", "size_class": "short"},
        "signals": {"tags": []},
        "threading": {"thread_id": "", "thread_label": ""},
        "domain_fingerprint": "",
        "raw_text": text,
    }


def _make_supp_prompt(text: str, agent: str = "chatgpt", timestamp: str = "") -> dict:
    """Build a minimal supplementary prompt dict."""
    return {
        "id": f"sup-{text[:8]}",
        "source": {
            "session_id": "supp-s1",
            "agent": agent,
            "project_dir": "/tmp/supp",
            "project_slug": "supp",
            "timestamp": timestamp,
            "prompt_index": 0,
            "prompt_count": 1,
        },
        "content": {
            "text": text[:500],
            "char_count": len(text),
            "word_count": len(text.split()),
            "line_count": 1,
        },
        "classification": {"prompt_type": "unclassified", "size_class": "short"},
        "signals": {"tags": ["supplementary:chatgpt"]},
        "threading": {"thread_id": "", "thread_label": ""},
        "domain_fingerprint": "",
    }


class TestDiscoverSupplementaryPrompts:
    def test_discover_returns_none_when_missing(self, tmp_path):
        """No supplementary file exists at all."""
        assert discover_supplementary_prompts(tmp_path) is None

    def test_discover_returns_path_when_exists(self, tmp_path):
        """File at prompt-corpus/supplementary-prompts.jsonl is found."""
        subdir = tmp_path / "prompt-corpus"
        subdir.mkdir()
        jsonl = subdir / "supplementary-prompts.jsonl"
        jsonl.write_text("{}\n")

        result = discover_supplementary_prompts(tmp_path)
        assert result is not None
        assert result == jsonl

    def test_discover_finds_flat_layout(self, tmp_path):
        """Fallback: file directly in corpus_dir."""
        jsonl = tmp_path / "supplementary-prompts.jsonl"
        jsonl.write_text("{}\n")

        result = discover_supplementary_prompts(tmp_path)
        assert result == jsonl

    def test_discover_prefers_prompt_corpus_subdir(self, tmp_path):
        """When both locations exist, prompt-corpus/ takes priority."""
        flat = tmp_path / "supplementary-prompts.jsonl"
        flat.write_text('{"location": "flat"}\n')

        subdir = tmp_path / "prompt-corpus"
        subdir.mkdir()
        nested = subdir / "supplementary-prompts.jsonl"
        nested.write_text('{"location": "nested"}\n')

        result = discover_supplementary_prompts(tmp_path)
        assert result == nested


class TestLoadSupplementaryPrompts:
    def test_load_parses_entries(self, tmp_path):
        """Valid JSONL entries are loaded."""
        jsonl = tmp_path / "supplementary-prompts.jsonl"
        entries = [
            _make_supp_prompt("First prompt about testing"),
            _make_supp_prompt("Second prompt about deployment"),
        ]
        jsonl.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        loaded = load_supplementary_prompts(jsonl)
        assert len(loaded) == 2

    def test_load_skips_malformed_lines(self, tmp_path):
        """Malformed JSON lines are silently skipped."""
        jsonl = tmp_path / "supplementary-prompts.jsonl"
        good = _make_supp_prompt("Valid prompt content here")
        jsonl.write_text(
            json.dumps(good) + "\n"
            "not valid json\n"
            "{malformed\n",
        )

        loaded = load_supplementary_prompts(jsonl)
        assert len(loaded) == 1

    def test_load_skips_empty_text(self, tmp_path):
        """Entries with no extractable text are skipped."""
        jsonl = tmp_path / "supplementary-prompts.jsonl"
        empty_entry = {"id": "x", "content": {"text": ""}, "source": {}}
        jsonl.write_text(json.dumps(empty_entry) + "\n")

        loaded = load_supplementary_prompts(jsonl)
        assert len(loaded) == 0

    def test_load_handles_empty_file(self, tmp_path):
        """Empty file returns empty list."""
        jsonl = tmp_path / "supplementary-prompts.jsonl"
        jsonl.write_text("")

        loaded = load_supplementary_prompts(jsonl)
        assert loaded == []


class TestMergePromptStreams:
    def test_merge_deduplicates(self):
        """Prompts with identical first-200-char text are deduplicated."""
        same_text = "Implement the feature for SYS-073 bridge module"
        engine = [_make_engine_prompt(same_text, timestamp="2026-01-01T00:00:00Z")]
        supp = [_make_supp_prompt(same_text, timestamp="2026-01-01T00:00:00Z")]

        merged = merge_prompt_streams(engine, supp)
        assert len(merged) == 1
        # Engine prompt wins (added first).
        assert merged[0]["id"].startswith("eng-")

    def test_merge_preserves_order(self):
        """Merged results are sorted by timestamp ascending."""
        engine = [
            _make_engine_prompt("Third prompt in sequence", timestamp="2026-01-03T00:00:00Z"),
            _make_engine_prompt("First prompt in sequence", timestamp="2026-01-01T00:00:00Z"),
        ]
        supp = [
            _make_supp_prompt("Second prompt in sequence", timestamp="2026-01-02T00:00:00Z"),
        ]

        merged = merge_prompt_streams(engine, supp)
        assert len(merged) == 3
        timestamps = [m["source"]["timestamp"] for m in merged]
        assert timestamps == [
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            "2026-01-03T00:00:00Z",
        ]

    def test_merge_handles_empty_supplementary(self):
        """When supplementary is empty, engine prompts pass through unchanged in order."""
        engine = [
            _make_engine_prompt("Prompt alpha", timestamp="2026-01-02T00:00:00Z"),
            _make_engine_prompt("Prompt beta", timestamp="2026-01-01T00:00:00Z"),
        ]

        merged = merge_prompt_streams(engine, [])
        assert len(merged) == 2
        # Should be sorted by timestamp.
        assert merged[0]["source"]["timestamp"] == "2026-01-01T00:00:00Z"
        assert merged[1]["source"]["timestamp"] == "2026-01-02T00:00:00Z"

    def test_merge_handles_empty_engine(self):
        """When engine is empty, supplementary prompts pass through."""
        supp = [_make_supp_prompt("Only supplementary prompt", timestamp="2026-01-01T00:00:00Z")]

        merged = merge_prompt_streams([], supp)
        assert len(merged) == 1

    def test_merge_handles_both_empty(self):
        """Both empty yields empty."""
        merged = merge_prompt_streams([], [])
        assert merged == []

    def test_merge_no_timestamp_sorts_last(self):
        """Entries without timestamps sort after those with timestamps."""
        engine = [
            _make_engine_prompt("Has timestamp", timestamp="2026-01-01T00:00:00Z"),
        ]
        supp = [
            _make_supp_prompt("No timestamp at all"),
        ]

        merged = merge_prompt_streams(engine, supp)
        assert len(merged) == 2
        assert merged[0]["source"]["timestamp"] == "2026-01-01T00:00:00Z"
        assert merged[1]["source"]["timestamp"] == ""

    def test_dedup_uses_first_200_chars(self):
        """Two prompts identical in first 200 chars but different after are still deduped."""
        prefix = "A" * 200
        engine = [_make_engine_prompt(prefix + " engine suffix", timestamp="2026-01-01T00:00:00Z")]
        supp = [_make_supp_prompt(prefix + " supplementary suffix", timestamp="2026-01-02T00:00:00Z")]

        merged = merge_prompt_streams(engine, supp)
        assert len(merged) == 1

    def test_dedup_different_text_both_kept(self):
        """Prompts with different text are both kept."""
        engine = [_make_engine_prompt("Completely unique engine prompt")]
        supp = [_make_supp_prompt("Completely unique supplementary prompt")]

        merged = merge_prompt_streams(engine, supp)
        assert len(merged) == 2
