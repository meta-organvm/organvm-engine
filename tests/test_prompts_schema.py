"""Tests for prompts/schema.py — dataclass definitions and serialization."""

from organvm_engine.prompts.schema import (
    AnnotatedPrompt,
    NarrateResult,
    PromptClassification,
    PromptContent,
    PromptSignals,
    PromptSource,
    PromptThreading,
    RawPrompt,
)


class TestAnnotatedPrompt:
    def test_compute_id_deterministic(self):
        ap = AnnotatedPrompt()
        ap.source.session_id = "session-123"
        ap.source.prompt_index = 5
        ap.compute_id()
        first_id = ap.id

        ap2 = AnnotatedPrompt()
        ap2.source.session_id = "session-123"
        ap2.source.prompt_index = 5
        ap2.compute_id()
        assert ap2.id == first_id

    def test_compute_id_different_inputs(self):
        ap1 = AnnotatedPrompt()
        ap1.source.session_id = "session-a"
        ap1.source.prompt_index = 0
        ap1.compute_id()

        ap2 = AnnotatedPrompt()
        ap2.source.session_id = "session-b"
        ap2.source.prompt_index = 0
        ap2.compute_id()

        assert ap1.id != ap2.id

    def test_compute_id_is_12_chars(self):
        ap = AnnotatedPrompt()
        ap.source.session_id = "abc"
        ap.source.prompt_index = 0
        ap.compute_id()
        assert len(ap.id) == 12

    def test_to_dict_structure(self):
        ap = AnnotatedPrompt()
        ap.source = PromptSource(
            session_id="s1", agent="claude", project_slug="proj/repo",
        )
        ap.content = PromptContent(text="hello world", char_count=11, word_count=2, line_count=1)
        ap.classification = PromptClassification(prompt_type="command", size_class="terse")
        ap.signals = PromptSignals(opening_phrase="hello world", imperative_verb="")
        ap.threading = PromptThreading(thread_id="t1", thread_label="label")
        ap.domain_fingerprint = "abc123"
        ap.raw_text = "hello world"
        ap.compute_id()

        d = ap.to_dict()

        assert d["source"]["session_id"] == "s1"
        assert d["source"]["agent"] == "claude"
        assert d["content"]["char_count"] == 11
        assert d["classification"]["prompt_type"] == "command"
        assert d["signals"]["opening_phrase"] == "hello world"
        assert d["threading"]["thread_id"] == "t1"
        assert d["domain_fingerprint"] == "abc123"
        assert d["id"] == ap.id

    def test_to_dict_truncates_text(self):
        ap = AnnotatedPrompt()
        ap.content.text = "x" * 1000
        d = ap.to_dict()
        assert len(d["content"]["text"]) == 500

    def test_defaults(self):
        ap = AnnotatedPrompt()
        assert ap.id == ""
        assert ap.source.session_id == ""
        assert ap.content.text == ""
        assert ap.classification.prompt_type == "command"
        assert ap.signals.opening_phrase == ""
        assert ap.threading.arc_position == "development"
        assert ap.domain_fingerprint == ""


class TestRawPrompt:
    def test_fields(self):
        rp = RawPrompt(text="hello", timestamp="2026-01-01T00:00:00Z", index=3)
        assert rp.text == "hello"
        assert rp.timestamp == "2026-01-01T00:00:00Z"
        assert rp.index == 3

    def test_defaults(self):
        rp = RawPrompt(text="test")
        assert rp.timestamp is None
        assert rp.index == 0


class TestNarrateResult:
    def test_fields(self):
        result = NarrateResult(
            prompts=[{"id": "p1"}],
            sessions_processed=10,
            sessions_skipped=2,
            thread_count=5,
            errors=[("s1:0", "parse error")],
            type_counts={"command": 8, "question": 2},
            size_counts={"short": 5, "medium": 5},
            arc_pattern_counts={"steady-build": 3},
            noise_skipped=4,
        )
        assert result.sessions_processed == 10
        assert result.thread_count == 5
        assert result.noise_skipped == 4
        assert len(result.errors) == 1

    def test_defaults(self):
        result = NarrateResult(
            prompts=[], sessions_processed=0, sessions_skipped=0,
            thread_count=0, errors=[],
        )
        assert result.type_counts == {}
        assert result.noise_skipped == 0


class TestPromptSource:
    def test_defaults(self):
        ps = PromptSource()
        assert ps.session_id == ""
        assert ps.agent == ""
        assert ps.timestamp is None
        assert ps.prompt_index == 0


class TestPromptSignals:
    def test_mutable_defaults(self):
        s1 = PromptSignals()
        s2 = PromptSignals()
        s1.mentions_files.append("test.py")
        assert s2.mentions_files == []
