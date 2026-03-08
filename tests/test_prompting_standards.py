"""Tests for the prompting standards module."""

from __future__ import annotations

import pytest

from organvm_engine.prompting.standards import (
    PROVIDER_GUIDELINES,
    ProviderGuidelines,
    agent_to_provider,
    get_guidelines,
)
from organvm_engine.prompting.loader import (
    format_guidelines_hint,
    load_guidelines,
)


class TestProviderGuidelines:
    """Tests for the PROVIDER_GUIDELINES registry."""

    def test_all_five_providers_present(self):
        expected = {"anthropic", "google", "openai", "grok", "perplexity"}
        assert set(PROVIDER_GUIDELINES.keys()) == expected

    @pytest.mark.parametrize("provider", ["anthropic", "google", "openai", "grok", "perplexity"])
    def test_each_provider_has_required_fields(self, provider: str):
        g = PROVIDER_GUIDELINES[provider]
        assert isinstance(g, ProviderGuidelines)
        assert g.provider == provider
        assert isinstance(g.system_prompt_support, bool)
        assert g.max_context
        assert g.preferred_format
        assert len(g.key_patterns) >= 3

    def test_anthropic_uses_xml_tags(self):
        g = PROVIDER_GUIDELINES["anthropic"]
        assert g.preferred_format == "XML tags"
        assert g.thinking_mode is not None

    def test_google_has_1m_context(self):
        g = PROVIDER_GUIDELINES["google"]
        assert "1M" in g.max_context

    def test_perplexity_no_thinking_mode(self):
        g = PROVIDER_GUIDELINES["perplexity"]
        assert g.thinking_mode is None


class TestGetGuidelines:
    """Tests for the get_guidelines lookup function."""

    def test_case_insensitive_lookup(self):
        assert get_guidelines("Anthropic") is not None
        assert get_guidelines("GOOGLE") is not None

    def test_unknown_provider_returns_none(self):
        assert get_guidelines("unknown_provider") is None


class TestAgentToProvider:
    """Tests for the agent_to_provider mapping."""

    @pytest.mark.parametrize(
        "agent,expected",
        [
            ("claude", "anthropic"),
            ("CLAUDE.md", "anthropic"),
            ("gemini", "google"),
            ("GEMINI.md", "google"),
            ("chatgpt", "openai"),
            ("grok", "grok"),
            ("perplexity", "perplexity"),
        ],
    )
    def test_known_agents(self, agent: str, expected: str):
        assert agent_to_provider(agent) == expected

    def test_unknown_agent_returns_none(self):
        assert agent_to_provider("unknown_agent") is None


class TestLoadGuidelines:
    """Tests for the unified load_guidelines interface."""

    def test_load_by_agent_name(self):
        g = load_guidelines("claude")
        assert g is not None
        assert g.provider == "anthropic"

    def test_load_by_filename(self):
        g = load_guidelines("GEMINI.md")
        assert g is not None
        assert g.provider == "google"

    def test_unknown_returns_none(self):
        assert load_guidelines("unknown") is None


class TestFormatGuidelinesHint:
    """Tests for the hint formatting function."""

    def test_hint_contains_provider(self):
        g = PROVIDER_GUIDELINES["anthropic"]
        hint = format_guidelines_hint(g)
        assert "Anthropic" in hint
        assert "200K" in hint
        assert "XML tags" in hint

    def test_hint_includes_thinking_when_present(self):
        g = PROVIDER_GUIDELINES["anthropic"]
        hint = format_guidelines_hint(g)
        assert "thinking" in hint

    def test_hint_omits_thinking_when_none(self):
        g = PROVIDER_GUIDELINES["perplexity"]
        hint = format_guidelines_hint(g)
        assert "thinking" not in hint

    def test_guidelines_are_frozen(self):
        g = PROVIDER_GUIDELINES["anthropic"]
        with pytest.raises(AttributeError):
            g.provider = "hacked"  # type: ignore[misc]
