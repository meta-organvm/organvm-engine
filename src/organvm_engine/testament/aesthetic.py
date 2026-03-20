"""Aesthetic profile loading — reads taste.yaml and organ-aesthetic.yaml.

Cascading inheritance: taste.yaml (system-wide) -> organ-aesthetic.yaml
(per-organ overrides). Provides palette, typography, and tone data for
renderers that produce visual artifacts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from organvm_engine.organ_config import get_organ_map
from organvm_engine.paths import workspace_root as _workspace_root

logger = logging.getLogger(__name__)

_TASTE_SUBPATH = Path("meta-organvm") / "alchemia-ingestvm" / "taste.yaml"


@dataclass(frozen=True)
class Palette:
    """Color palette for artifact rendering."""

    primary: str = "#1a1a2e"
    secondary: str = "#16213e"
    accent: str = "#e94560"
    background: str = "#0f0f23"
    text: str = "#d4d4d8"
    muted: str = "#6b7280"


@dataclass(frozen=True)
class Typography:
    """Typography settings for artifact rendering."""

    headings: str = "serif"
    body: str = "sans-serif"
    code: str = "monospace"
    weight_preference: str = "medium"
    letter_spacing: str = "tight"


@dataclass(frozen=True)
class AestheticProfile:
    """Complete aesthetic profile: palette + typography + tone + visual keywords."""

    palette: Palette = Palette()
    typography: Typography = Typography()
    tone: dict[str, str] = field(default_factory=dict)
    visual_keywords: list[str] = field(default_factory=list)


def default_palette() -> Palette:
    """Return the system-wide default palette (taste.yaml values)."""
    return Palette()


def _parse_palette(data: dict[str, Any]) -> Palette:
    """Extract a Palette from a parsed YAML dict."""
    raw = data.get("palette", {})
    if not isinstance(raw, dict):
        return Palette()
    return Palette(
        primary=str(raw.get("primary", Palette.primary)),
        secondary=str(raw.get("secondary", Palette.secondary)),
        accent=str(raw.get("accent", Palette.accent)),
        background=str(raw.get("background", Palette.background)),
        text=str(raw.get("text", Palette.text)),
        muted=str(raw.get("muted", Palette.muted)),
    )


def _parse_typography(data: dict[str, Any]) -> Typography:
    """Extract Typography from a parsed YAML dict."""
    raw = data.get("typography", {})
    if not isinstance(raw, dict):
        return Typography()
    return Typography(
        headings=str(raw.get("headings", Typography.headings)),
        body=str(raw.get("body", Typography.body)),
        code=str(raw.get("code", Typography.code)),
        weight_preference=str(raw.get("weight_preference", Typography.weight_preference)),
        letter_spacing=str(raw.get("letter_spacing", Typography.letter_spacing)),
    )


def _parse_tone(data: dict[str, Any]) -> dict[str, str]:
    """Extract tone dict from a parsed YAML dict."""
    raw = data.get("tone", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _parse_visual_keywords(data: dict[str, Any]) -> list[str]:
    """Extract visual keywords from a parsed YAML dict."""
    vl = data.get("visual_language", {})
    if not isinstance(vl, dict):
        return []
    keywords = vl.get("keywords", [])
    if not isinstance(keywords, list):
        return []
    return [str(k) for k in keywords]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file, returning empty dict on failure."""
    if not path.is_file():
        logger.debug("YAML file not found: %s", path)
        return {}
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}


def load_taste(workspace_root: Path | None = None) -> AestheticProfile:
    """Load the system-wide taste.yaml from alchemia-ingestvm."""
    ws = workspace_root or _workspace_root()
    taste_path = ws / _TASTE_SUBPATH
    data = _load_yaml(taste_path)
    if not data:
        return AestheticProfile()
    return AestheticProfile(
        palette=_parse_palette(data),
        typography=_parse_typography(data),
        tone=_parse_tone(data),
        visual_keywords=_parse_visual_keywords(data),
    )


def load_organ_aesthetic(
    organ_key: str,
    workspace_root: Path | None = None,
) -> AestheticProfile:
    """Load organ-aesthetic.yaml and merge with the base taste.yaml.

    The organ-aesthetic file provides modifiers that describe how the organ
    diverges from the base taste. Since organ-aesthetic.yaml uses qualitative
    modifiers rather than concrete overrides, the base taste profile is
    returned with any organ-level palette/typography/tone overrides merged in.
    """
    base = load_taste(workspace_root)
    ws = workspace_root or _workspace_root()

    organ_map = get_organ_map()
    organ_info = organ_map.get(organ_key)
    if organ_info is None:
        logger.debug("Unknown organ key: %s", organ_key)
        return base

    organ_dir = organ_info.get("dir", "")
    aesthetic_path = ws / organ_dir / ".github" / "organ-aesthetic.yaml"
    data = _load_yaml(aesthetic_path)
    if not data:
        return base

    # organ-aesthetic.yaml uses qualitative modifiers (palette_shift,
    # typography_emphasis, etc.) rather than concrete color/font overrides.
    # We merge any concrete fields that exist, falling back to the base.
    modifiers = data.get("modifiers", {})
    if not isinstance(modifiers, dict):
        return base

    # If the organ file provides concrete palette/typography overrides,
    # use them; otherwise keep the base taste values.
    palette = _parse_palette(data) if "palette" in data else base.palette
    typography = _parse_typography(data) if "typography" in data else base.typography

    # Tone: merge organ tone into base tone
    tone = dict(base.tone)
    organ_tone = _parse_tone(data)
    tone.update(organ_tone)

    # Visual keywords: append organ-specific keywords
    keywords = list(base.visual_keywords)
    organ_keywords = _parse_visual_keywords(data)
    for kw in organ_keywords:
        if kw not in keywords:
            keywords.append(kw)

    return AestheticProfile(
        palette=palette,
        typography=typography,
        tone=tone,
        visual_keywords=keywords,
    )
