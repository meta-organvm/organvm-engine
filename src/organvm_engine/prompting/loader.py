"""Load prompting guidelines from standards data or SOP files.

Provides a unified interface for retrieving provider-specific prompting
guidelines, whether from the built-in standards or from SOP files on disk.
"""

from __future__ import annotations

from organvm_engine.prompting.standards import (
    ProviderGuidelines,
    agent_to_provider,
    get_guidelines,
)


def load_guidelines(agent: str) -> ProviderGuidelines | None:
    """Load prompting guidelines for a given agent name.

    Args:
        agent: Agent identifier — 'claude', 'gemini', 'CLAUDE.md', etc.

    Returns:
        ProviderGuidelines if found, None otherwise.
    """
    provider = agent_to_provider(agent)
    if not provider:
        return None
    return get_guidelines(provider)


def format_guidelines_hint(guidelines: ProviderGuidelines) -> str:
    """Format guidelines as a concise markdown hint for context file injection."""
    lines = [
        f"**Prompting ({guidelines.provider.title()})**: "
        f"context {guidelines.max_context}, "
        f"format: {guidelines.preferred_format}",
    ]
    if guidelines.thinking_mode:
        lines[0] += f", thinking: {guidelines.thinking_mode}"
    return lines[0]
