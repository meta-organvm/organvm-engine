"""Provider prompting guidelines as structured data.

Populated from cross-provider research (Anthropic, Google, OpenAI, Grok, Perplexity).
Each provider's guidelines describe the optimal prompting patterns for that platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderGuidelines:
    """Prompting guidelines for a specific AI provider."""

    provider: str
    system_prompt_support: bool
    max_context: str
    thinking_mode: str | None
    preferred_format: str
    key_patterns: list[str] = field(default_factory=list)


PROVIDER_GUIDELINES: dict[str, ProviderGuidelines] = {
    "anthropic": ProviderGuidelines(
        provider="anthropic",
        system_prompt_support=True,
        max_context="200K tokens",
        thinking_mode="extended thinking (budget_tokens)",
        preferred_format="XML tags",
        key_patterns=[
            "Use XML tags (<instructions>, <context>, <example>) for structure",
            "System prompt for persistent context, user messages for per-turn input",
            "Prefill assistant turn to steer output format",
            "Chain of thought via <thinking> tags or extended thinking mode",
            "Role prompting: assign expert persona in system prompt",
            "Provide 3-5 diverse examples for few-shot learning",
        ],
    ),
    "google": ProviderGuidelines(
        provider="google",
        system_prompt_support=True,
        max_context="1M tokens (Gemini 1.5 Pro)",
        thinking_mode="thinking mode (thinkingConfig)",
        preferred_format="markdown",
        key_patterns=[
            "System instructions for persistent behavioral guidelines",
            "Leverage long context for large document analysis",
            "Use grounding with Google Search for factual tasks",
            "Structured output via response_mime_type and response_schema",
            "Multimodal: inline images/audio/video directly in prompts",
            "Temperature 0 for deterministic, higher for creative tasks",
        ],
    ),
    "openai": ProviderGuidelines(
        provider="openai",
        system_prompt_support=True,
        max_context="128K tokens (GPT-4o)",
        thinking_mode="reasoning effort (o1/o3 models)",
        preferred_format="markdown",
        key_patterns=[
            "System message sets behavior, user message sets task",
            "Structured Outputs via json_schema response_format",
            "Use delimiters (triple quotes, XML tags) to separate sections",
            "Specify output length and format explicitly",
            "For complex tasks, decompose into subtasks with chained calls",
            "Few-shot examples in conversation history",
        ],
    ),
    "grok": ProviderGuidelines(
        provider="grok",
        system_prompt_support=True,
        max_context="128K tokens",
        thinking_mode="think mode (budget_tokens)",
        preferred_format="markdown",
        key_patterns=[
            "System prompt for persona and constraints",
            "Real-time data access via X/Twitter integration",
            "DeepSearch for multi-step research queries",
            "Concise prompts for conversational tasks",
            "Explicit instructions for tone (witty vs formal)",
            "Image understanding and generation supported",
        ],
    ),
    "perplexity": ProviderGuidelines(
        provider="perplexity",
        system_prompt_support=True,
        max_context="128K tokens",
        thinking_mode=None,
        preferred_format="markdown",
        key_patterns=[
            "Optimized for search-augmented generation",
            "System prompt constrains response style, not search behavior",
            "Use search_domain_filter to restrict source domains",
            "search_recency_filter for time-sensitive queries",
            "Citations returned automatically with source URLs",
            "Best for factual, research-oriented queries with grounding",
        ],
    ),
}


def get_guidelines(provider: str) -> ProviderGuidelines | None:
    """Look up guidelines by provider name (case-insensitive)."""
    return PROVIDER_GUIDELINES.get(provider.lower())


def agent_to_provider(agent: str) -> str | None:
    """Map agent file type to provider key.

    e.g. 'CLAUDE.md' -> 'anthropic', 'GEMINI.md' -> 'google'
    """
    mapping = {
        "claude": "anthropic",
        "gemini": "google",
        "chatgpt": "openai",
        "grok": "grok",
        "perplexity": "perplexity",
    }
    return mapping.get(agent.lower().replace(".md", ""))
