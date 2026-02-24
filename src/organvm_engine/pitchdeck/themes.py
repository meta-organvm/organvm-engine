"""Theme resolution — maps organ aesthetics to CSS custom properties.

Calls resolve_aesthetic_chain() from alchemia, then maps the prose
modifiers to concrete hex colors, font stacks, and CSS values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PitchTheme:
    """Resolved CSS theme for a pitch deck."""

    # Core palette
    bg_primary: str = "#0f0f23"
    bg_secondary: str = "#1a1a2e"
    accent: str = "#e94560"
    text_primary: str = "#d4d4d8"
    text_muted: str = "#6b7280"
    gold: str = "#d4a853"

    # Typography
    font_heading: str = "'Georgia', 'Palatino Linotype', serif"
    font_body: str = "-apple-system, 'Segoe UI', sans-serif"
    font_mono: str = "'SF Mono', 'Fira Code', 'Consolas', monospace"

    # Section backgrounds
    hero_bg: str = "#0f0f23"
    section_bg: str = "#111127"
    card_bg: str = "rgba(255,255,255,0.04)"
    card_border: str = "rgba(233,69,96,0.2)"

    # Extra
    organ_badge_color: str = "#e94560"

    def to_css_vars(self) -> str:
        """Render as CSS custom property declarations."""
        return f"""\
  --bg-primary: {self.bg_primary};
  --bg-secondary: {self.bg_secondary};
  --accent: {self.accent};
  --text-primary: {self.text_primary};
  --text-muted: {self.text_muted};
  --gold: {self.gold};
  --font-heading: {self.font_heading};
  --font-body: {self.font_body};
  --font-mono: {self.font_mono};
  --hero-bg: {self.hero_bg};
  --section-bg: {self.section_bg};
  --card-bg: {self.card_bg};
  --card-border: {self.card_border};
  --organ-badge: {self.organ_badge_color};"""


# ── Per-organ concrete palettes ──────────────────────────────────────
# These translate the prose modifiers from organ-aesthetic.yaml into
# actual hex values suitable for dark-mode pitch decks.

ORGAN_PALETTES: dict[str, dict[str, str]] = {
    "ORGAN-I": {
        "bg_primary": "#0c0f1a",
        "bg_secondary": "#141831",
        "accent": "#6366f1",
        "hero_bg": "#0c0f1a",
        "section_bg": "#10132a",
        "card_border": "rgba(99,102,241,0.2)",
        "organ_badge_color": "#6366f1",
        "gold": "#94a3b8",
        "font_heading": "'Palatino Linotype', 'Book Antiqua', Georgia, serif",
    },
    "ORGAN-II": {
        "bg_primary": "#120a1e",
        "bg_secondary": "#1e0f35",
        "accent": "#e94560",
        "hero_bg": "#120a1e",
        "section_bg": "#160d28",
        "card_border": "rgba(233,69,96,0.2)",
        "organ_badge_color": "#e94560",
        "gold": "#d4a853",
        "font_heading": "'Georgia', 'Palatino Linotype', serif",
    },
    "ORGAN-III": {
        "bg_primary": "#0a0f1e",
        "bg_secondary": "#0f1730",
        "accent": "#3b82f6",
        "hero_bg": "#0a0f1e",
        "section_bg": "#0d1328",
        "card_border": "rgba(59,130,246,0.2)",
        "organ_badge_color": "#3b82f6",
        "gold": "#94a3b8",
        "font_heading": "-apple-system, 'Segoe UI', 'Helvetica Neue', sans-serif",
        "font_body": "-apple-system, 'Segoe UI', 'Helvetica Neue', sans-serif",
    },
    "ORGAN-IV": {
        "bg_primary": "#0a0f0a",
        "bg_secondary": "#0f1a0f",
        "accent": "#22c55e",
        "hero_bg": "#0a0f0a",
        "section_bg": "#0d150d",
        "card_border": "rgba(34,197,94,0.2)",
        "organ_badge_color": "#22c55e",
        "gold": "#4ade80",
        "font_heading": "'SF Mono', 'Fira Code', 'Consolas', monospace",
        "font_body": "'SF Mono', 'Fira Code', 'Consolas', monospace",
    },
    "ORGAN-V": {
        "bg_primary": "#14100a",
        "bg_secondary": "#1e1810",
        "accent": "#f59e0b",
        "hero_bg": "#14100a",
        "section_bg": "#181208",
        "card_border": "rgba(245,158,11,0.2)",
        "organ_badge_color": "#f59e0b",
        "gold": "#f59e0b",
        "font_heading": "'Georgia', 'Palatino Linotype', 'Times New Roman', serif",
    },
    "ORGAN-VI": {
        "bg_primary": "#140f0a",
        "bg_secondary": "#1e1610",
        "accent": "#f59e0b",
        "hero_bg": "#140f0a",
        "section_bg": "#181008",
        "card_border": "rgba(245,158,11,0.2)",
        "organ_badge_color": "#d97706",
        "gold": "#f59e0b",
        "font_heading": "'Georgia', serif",
    },
    "ORGAN-VII": {
        "bg_primary": "#14081a",
        "bg_secondary": "#200e2e",
        "accent": "#ef4444",
        "hero_bg": "#14081a",
        "section_bg": "#1a0b24",
        "card_border": "rgba(239,68,68,0.2)",
        "organ_badge_color": "#ef4444",
        "gold": "#ef4444",
        "font_heading": "-apple-system, 'Segoe UI', sans-serif",
    },
    "META-ORGANVM": {
        "bg_primary": "#0f0f23",
        "bg_secondary": "#1a1a2e",
        "accent": "#e94560",
        "hero_bg": "#0f0f23",
        "section_bg": "#111127",
        "card_border": "rgba(233,69,96,0.2)",
        "organ_badge_color": "#e94560",
        "gold": "#d4a853",
        "font_heading": "'Georgia', 'Palatino Linotype', serif",
    },
    "PERSONAL": {
        "bg_primary": "#0f0f23",
        "bg_secondary": "#1a1a2e",
        "accent": "#e94560",
        "hero_bg": "#0f0f23",
        "section_bg": "#111127",
        "card_border": "rgba(233,69,96,0.2)",
        "organ_badge_color": "#e94560",
        "gold": "#d4a853",
        "font_heading": "'Georgia', 'Palatino Linotype', serif",
    },
}


def resolve_theme(
    organ_key: str,
    aesthetic_chain: dict[str, Any] | None = None,
) -> PitchTheme:
    """Resolve a pitch deck theme for the given organ.

    If an aesthetic chain (from resolve_aesthetic_chain()) is provided,
    it's used to override the base taste.yaml palette. Otherwise, falls
    back to the hardcoded ORGAN_PALETTES dict.

    Args:
        organ_key: Registry organ key (e.g., "ORGAN-I", "META-ORGANVM").
        aesthetic_chain: Optional pre-resolved aesthetic chain dict.

    Returns:
        A PitchTheme with concrete CSS values.
    """
    theme = PitchTheme()

    # Apply organ-specific palette
    overrides = ORGAN_PALETTES.get(organ_key, {})
    for key, value in overrides.items():
        if hasattr(theme, key):
            setattr(theme, key, value)

    # If an aesthetic chain is provided, use its root palette for base colors
    if aesthetic_chain:
        palette = aesthetic_chain.get("palette", {})
        if palette.get("primary"):
            theme.bg_secondary = palette["primary"]
        if palette.get("background"):
            theme.bg_primary = palette["background"]
        if palette.get("accent") and organ_key not in ORGAN_PALETTES:
            theme.accent = palette["accent"]
        if palette.get("text"):
            theme.text_primary = palette["text"]
        if palette.get("muted"):
            theme.text_muted = palette["muted"]

    return theme
