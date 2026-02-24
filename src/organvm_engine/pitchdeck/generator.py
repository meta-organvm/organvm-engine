"""Pitch deck HTML generator — assembles data + theme + template.

Takes a PitchDeckData and PitchTheme, fills the template placeholders,
and returns a complete HTML string ready to write to disk.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from organvm_engine.pitchdeck import PITCH_MARKER, PITCH_VERSION
from organvm_engine.pitchdeck.animations import generate_hero_canvas
from organvm_engine.pitchdeck.data import PitchDeckData
from organvm_engine.pitchdeck.templates import STANDARD_TEMPLATE, MARKET_SECTION_TEMPLATE
from organvm_engine.pitchdeck.themes import PitchTheme


def generate_pitch_deck(
    data: PitchDeckData,
    theme: PitchTheme,
) -> str:
    """Generate a complete single-file HTML pitch deck.

    Args:
        data: Assembled pitch deck content.
        theme: Resolved organ theme with CSS values.

    Returns:
        Complete HTML string.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker = f"{PITCH_MARKER} v{PITCH_VERSION} generated {now} -->"

    # Determine section numbering (ORGAN-III gets a market section)
    is_organ_iii = data.organ_key == "ORGAN-III"
    positioning_num = 6 if is_organ_iii else 5
    cta_num = 7 if is_organ_iii else 6

    # Build HTML fragments
    problem_cards_html = _render_problem_cards(data.problem_cards)
    features_html = _render_features(data.features)
    tech_badges_html = _render_tech_badges(data.tech_stack)
    edges_html = _render_edges(data.produces, data.consumes)
    siblings_html = _render_siblings(data.siblings)
    cta_links_html = _render_cta_links(data)
    market_section = _render_market_section(data) if is_organ_iii else ""

    # Hero animation
    hero_js = generate_hero_canvas(data.organ_key)

    # Organ key display (strip "ORGAN-" prefix for display)
    organ_key_display = data.organ_key.replace("ORGAN-", "").replace("META-ORGANVM", "META")

    return STANDARD_TEMPLATE.format(
        display_name=_esc(data.display_name),
        organ_name=_esc(data.organ_name),
        tagline=_esc(data.tagline),
        tagline_escaped=_attr_esc(data.tagline),
        description=_esc(data.description),
        tier=_esc(data.tier),
        pitch_marker=marker,
        css_vars=theme.to_css_vars(),
        organ_key_display=_esc(organ_key_display),
        problem_cards_html=problem_cards_html,
        solution_text=_esc(data.solution_text or data.description),
        features_html=features_html,
        tech_badges_html=tech_badges_html,
        architecture_text=_esc(data.architecture_text),
        market_section=market_section,
        positioning_section_num=positioning_num,
        cta_section_num=cta_num,
        edges_html=edges_html,
        siblings_html=siblings_html,
        cta_links_html=cta_links_html,
        hero_animation_js=hero_js,
    )


# ── HTML fragment renderers ──────────────────────────────────────────


def _render_problem_cards(cards: list[dict[str, str]]) -> str:
    """Render problem cards as HTML."""
    if not cards:
        return '      <div class="card visible"><h3>Under Construction</h3><p>Problem statement coming soon.</p></div>'

    lines = []
    for card in cards[:3]:
        title = _esc(card.get("title", ""))
        text = _esc(card.get("text", ""))
        lines.append(f'      <div class="card"><h3>{title}</h3><p>{text}</p></div>')
    return "\n".join(lines)


def _render_features(features: list[dict[str, str]]) -> str:
    """Render feature cards as HTML."""
    if not features:
        return '      <div class="feature-card visible"><h3>In Development</h3><p>Feature list coming soon.</p></div>'

    lines = []
    for feat in features[:6]:
        title = _esc(feat.get("title", ""))
        text = _esc(feat.get("text", ""))
        lines.append(f'      <div class="feature-card"><h3>{title}</h3><p>{text}</p></div>')
    return "\n".join(lines)


def _render_tech_badges(tech_stack: list[str]) -> str:
    """Render tech stack badges."""
    if not tech_stack:
        return '      <span class="tech-badge">Python</span>'

    lines = []
    for tech in tech_stack[:10]:
        lines.append(f'      <span class="tech-badge">{_esc(tech)}</span>')
    return "\n".join(lines)


def _render_edges(produces: list[str], consumes: list[str]) -> str:
    """Render produces/consumes edges."""
    lines = []
    for p in produces[:4]:
        lines.append(
            f'      <div class="edge-item"><span class="edge-dir">produces</span>{_esc(p)}</div>'
        )
    for c in consumes[:4]:
        lines.append(
            f'      <div class="edge-item"><span class="edge-dir">consumes</span>{_esc(c)}</div>'
        )
    if not lines:
        lines.append('      <div class="edge-item"><span class="edge-dir">standalone</span>No declared edges</div>')
    return "\n".join(lines)


def _render_siblings(siblings: list[str]) -> str:
    """Render sibling repo tags."""
    if not siblings:
        return ""
    lines = []
    for s in siblings[:12]:
        lines.append(f'      <span class="sibling-tag">{_esc(s)}</span>')
    return "\n".join(lines)


def _render_cta_links(data: PitchDeckData) -> str:
    """Render CTA action buttons."""
    links = []
    if data.github_url:
        links.append(f'      <a href="{_attr_esc(data.github_url)}" class="cta-btn" target="_blank" rel="noopener">View on GitHub</a>')
    if data.docs_url:
        links.append(f'      <a href="{_attr_esc(data.docs_url)}" class="cta-btn" target="_blank" rel="noopener">Documentation</a>')
    if data.demo_url:
        links.append(f'      <a href="{_attr_esc(data.demo_url)}" class="cta-btn" target="_blank" rel="noopener">Live Demo</a>')
    if not links:
        links.append('      <a href="#hero" class="cta-btn">Back to Top</a>')
    return "\n".join(links)


def _render_market_section(data: PitchDeckData) -> str:
    """Render the ORGAN-III market section."""
    badges = []
    if data.revenue_model:
        badges.append(f'        <span class="market-badge">{_esc(data.revenue_model)}</span>')
    if data.revenue_status:
        badges.append(f'        <span class="market-badge">{_esc(data.revenue_status)}</span>')

    return MARKET_SECTION_TEMPLATE.format(
        market_text=_esc(data.market_text or "Business model details coming soon."),
        market_badges_html="\n".join(badges) if badges else "",
    )


# ── Escaping helpers ─────────────────────────────────────────────────


def _esc(text: str) -> str:
    """Escape text for HTML content."""
    return html.escape(text, quote=False)


def _attr_esc(text: str) -> str:
    """Escape text for HTML attribute values."""
    return html.escape(text, quote=True)
