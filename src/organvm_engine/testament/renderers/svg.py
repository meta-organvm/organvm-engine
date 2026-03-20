"""SVG renderers — raw SVG generation for system self-portraits.

No external dependencies. Generates SVG strings from system data
using the aesthetic cascade (taste.yaml palette) for all visual decisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Palette:
    """Minimal palette for rendering. Mirrors aesthetic.py but decoupled."""

    primary: str = "#1a1a2e"
    secondary: str = "#16213e"
    accent: str = "#e94560"
    background: str = "#0f0f23"
    text: str = "#d4d4d8"
    muted: str = "#6b7280"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svg_header(width: int, height: int, title: str = "") -> str:
    """SVG document header with embedded font and title."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">\n'
        f'<title>{_esc(title)}</title>\n'
        f'<style>\n'
        f'  text {{ font-family: "SF Mono", "Fira Code", monospace; }}\n'
        f'  .label {{ font-size: 11px; fill: currentColor; }}\n'
        f'  .title {{ font-size: 14px; font-weight: 600; fill: currentColor; }}\n'
        f'  .stat {{ font-size: 10px; fill: currentColor; opacity: 0.7; }}\n'
        f'  .big {{ font-size: 28px; font-weight: 700; fill: currentColor; }}\n'
        f'</style>\n'
    )


def _esc(s: str) -> str:
    """Escape XML special characters."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _circle(cx: float, cy: float, r: float, fill: str, opacity: float = 1.0,
            stroke: str | None = None, stroke_width: float = 1.0) -> str:
    """SVG circle element."""
    parts = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"']
    if opacity < 1.0:
        parts.append(f' opacity="{opacity:.2f}"')
    if stroke:
        parts.append(f' stroke="{stroke}" stroke-width="{stroke_width:.1f}"')
    parts.append('/>')
    return ''.join(parts)


def _line(x1: float, y1: float, x2: float, y2: float,
          stroke: str, width: float = 1.0, opacity: float = 0.4) -> str:
    """SVG line element."""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width:.1f}" opacity="{opacity:.2f}"/>'
    )


def _text(x: float, y: float, content: str, css_class: str = "label",
          anchor: str = "middle", fill: str | None = None) -> str:
    """SVG text element."""
    style = f' fill="{fill}"' if fill else ''
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css_class}" '
        f'text-anchor="{anchor}"{style}>{_esc(content)}</text>'
    )


def _arc_path(cx: float, cy: float, r: float,
              start_angle: float, end_angle: float) -> str:
    """SVG arc path data for a segment of a circle."""
    x1 = cx + r * math.cos(start_angle)
    y1 = cy + r * math.sin(start_angle)
    x2 = cx + r * math.cos(end_angle)
    y2 = cy + r * math.sin(end_angle)
    large = 1 if (end_angle - start_angle) > math.pi else 0
    return f"M {cx:.1f} {cy:.1f} L {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} Z"


def _arrow_marker(marker_id: str, color: str) -> str:
    """SVG marker definition for arrowheads."""
    return (
        f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" '
        f'refX="10" refY="5" markerWidth="6" markerHeight="6" '
        f'orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{color}" opacity="0.6"/>'
        f'</marker></defs>'
    )


# ---------------------------------------------------------------------------
# Organ position constants
# ---------------------------------------------------------------------------

# Canonical organ ordering for constellation layout
ORGAN_KEYS = ["I", "II", "III", "IV", "V", "VI", "VII", "META"]
ORGAN_LABELS = {
    "I": "Theoria", "II": "Poiesis", "III": "Ergon", "IV": "Taxis",
    "V": "Logos", "VI": "Koinonia", "VII": "Kerygma", "META": "Meta",
}

# Canonical dependency edges (unidirectional: I→II→III, IV orchestrates all)
CANONICAL_EDGES = [
    ("I", "II"), ("II", "III"),
    ("IV", "I"), ("IV", "II"), ("IV", "III"),
    ("IV", "V"), ("IV", "VI"), ("IV", "VII"),
    ("META", "IV"),
]


# ---------------------------------------------------------------------------
# Public renderers
# ---------------------------------------------------------------------------

def render_constellation(
    organ_repo_counts: dict[str, int] | None = None,
    palette: Palette | None = None,
    width: int = 800,
    height: int = 600,
) -> str:
    """Render the eight-organ system as a stellar constellation.

    Each organ is a node sized by its repo count, positioned on an ellipse.
    Dependency edges drawn as directed lines with arrowheads.
    """
    p = palette or Palette()
    counts = organ_repo_counts or {k: 10 for k in ORGAN_KEYS}

    cx, cy = width / 2, height / 2
    rx, ry = width * 0.35, height * 0.35

    # Position organs on an ellipse, META at top
    positions: dict[str, tuple[float, float]] = {}
    for i, key in enumerate(ORGAN_KEYS):
        angle = -math.pi / 2 + (2 * math.pi * i / len(ORGAN_KEYS))
        x = cx + rx * math.cos(angle)
        y = cy + ry * math.sin(angle)
        positions[key] = (x, y)

    svg = [_svg_header(width, height, "ORGANVM — System Constellation")]
    svg.append(f'<rect width="{width}" height="{height}" fill="{p.background}"/>')
    svg.append(_arrow_marker("arrow", p.accent))

    # Draw edges first (behind nodes)
    for src, dst in CANONICAL_EDGES:
        if src in positions and dst in positions:
            x1, y1 = positions[src]
            x2, y2 = positions[dst]
            # Shorten line to not overlap node circles
            dx, dy = x2 - x1, y2 - y1
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                src_r = _node_radius(counts.get(src, 5))
                dst_r = _node_radius(counts.get(dst, 5))
                ux, uy = dx / dist, dy / dist
                x1a = x1 + ux * (src_r + 4)
                y1a = y1 + uy * (src_r + 4)
                x2a = x2 - ux * (dst_r + 8)
                y2a = y2 - uy * (dst_r + 8)
                svg.append(
                    f'<line x1="{x1a:.1f}" y1="{y1a:.1f}" '
                    f'x2="{x2a:.1f}" y2="{y2a:.1f}" '
                    f'stroke="{p.muted}" stroke-width="1.2" '
                    f'opacity="0.35" marker-end="url(#arrow)"/>',
                )

    # Draw nodes
    for key in ORGAN_KEYS:
        x, y = positions[key]
        count = counts.get(key, 5)
        r = _node_radius(count)

        # Glow effect
        svg.append(_circle(x, y, r + 6, p.accent, opacity=0.08))
        svg.append(_circle(x, y, r + 3, p.accent, opacity=0.12))

        # Node
        fill = p.accent if key == "META" else p.secondary
        svg.append(_circle(x, y, r, fill, stroke=p.accent, stroke_width=1.5))

        # Label
        svg.append(_text(x, y - r - 10, ORGAN_LABELS.get(key, key), "label", fill=p.text))
        svg.append(_text(x, y + 4, key, "stat", fill=p.text))
        svg.append(_text(x, y + 16, f"{count}r", "stat", fill=p.muted))

    # Title
    svg.append(_text(cx, 30, "ORGANVM — System Constellation", "title", fill=p.text))
    svg.append(
        _text(cx, height - 15, f"{sum(counts.values())} repositories across 8 organs",
              "stat", fill=p.muted),
    )

    svg.append('</svg>')
    return '\n'.join(svg)


def render_omega_mandala(
    criteria: list[dict[str, object]] | None = None,
    met_count: int = 7,
    total: int = 17,
    palette: Palette | None = None,
    size: int = 500,
) -> str:
    """Render the omega scorecard as a radial mandala.

    Each criterion is a wedge of the circle. Met criteria are filled
    with the accent color; unmet are muted outlines.
    """
    p = palette or Palette()
    cx, cy = size / 2, size / 2
    outer_r = size * 0.38
    inner_r = size * 0.15

    crits = criteria or [{"id": i + 1, "met": i < met_count} for i in range(total)]

    svg = [_svg_header(size, size, f"Omega Scorecard — {met_count}/{total}")]
    svg.append(f'<rect width="{size}" height="{size}" fill="{p.background}"/>')

    # Draw wedges
    n = len(crits)
    gap = 0.02  # radians gap between wedges
    wedge_angle = (2 * math.pi - n * gap) / n

    for i, crit in enumerate(crits):
        start = -math.pi / 2 + i * (wedge_angle + gap)
        end = start + wedge_angle
        is_met = bool(crit.get("met", False))

        # Outer wedge
        path_outer = _arc_path(cx, cy, outer_r, start, end)
        fill = p.accent if is_met else p.primary
        opacity = 0.85 if is_met else 0.25
        svg.append(
            f'<path d="{path_outer}" fill="{fill}" opacity="{opacity:.2f}" '
            f'stroke="{p.muted}" stroke-width="0.5"/>',
        )

        # Inner cutout (draw background circle over center later)
        # Criterion number at midpoint
        mid = (start + end) / 2
        label_r = (outer_r + inner_r) / 2
        lx = cx + label_r * math.cos(mid)
        ly = cy + label_r * math.sin(mid)
        crit_id = crit.get("id", i + 1)
        text_fill = p.background if is_met else p.muted
        svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" class="stat" '
            f'text-anchor="middle" dominant-baseline="central" '
            f'fill="{text_fill}">#{crit_id}</text>',
        )

    # Inner circle (mask center)
    svg.append(_circle(cx, cy, inner_r, p.background))
    svg.append(_circle(cx, cy, inner_r - 2, p.secondary, opacity=0.3))

    # Center text
    svg.append(_text(cx, cy - 6, f"{met_count}", "big", fill=p.accent))
    svg.append(_text(cx, cy + 14, f"of {total}", "stat", fill=p.muted))

    # Title
    svg.append(_text(cx, 25, "Omega Scorecard", "title", fill=p.text))
    pct = int(100 * met_count / total) if total else 0
    svg.append(_text(cx, size - 15, f"{pct}% system maturity", "stat", fill=p.muted))

    svg.append('</svg>')
    return '\n'.join(svg)


def render_dependency_flow(
    edges: list[tuple[str, str]] | None = None,
    palette: Palette | None = None,
    width: int = 900,
    height: int = 400,
) -> str:
    """Render the unidirectional dependency flow as a left-to-right directed graph.

    Production core (I→II→III) flows left to right.
    META sits above as constitutional substrate.
    IV (Taxis) sits below as control plane.
    Interface layer (V/VI/VII) on the right.
    """
    p = palette or Palette()
    deps = edges or CANONICAL_EDGES

    # Layer positions (x, y)
    positions: dict[str, tuple[float, float]] = {
        "META": (width * 0.5, 60),
        "I": (width * 0.15, height * 0.45),
        "II": (width * 0.35, height * 0.45),
        "III": (width * 0.55, height * 0.45),
        "IV": (width * 0.35, height * 0.82),
        "V": (width * 0.72, height * 0.3),
        "VI": (width * 0.72, height * 0.5),
        "VII": (width * 0.72, height * 0.7),
    }

    svg = [_svg_header(width, height, "ORGANVM — Dependency Flow")]
    svg.append(f'<rect width="{width}" height="{height}" fill="{p.background}"/>')
    svg.append(_arrow_marker("dep-arrow", p.accent))

    # Layer labels
    svg.append(_text(width * 0.15, height * 0.25, "Production Core", "stat", fill=p.muted))
    svg.append(_text(width * 0.72, height * 0.15, "Interface Layer", "stat", fill=p.muted))
    svg.append(_text(width * 0.35, height * 0.97, "Control Plane", "stat", fill=p.muted))
    svg.append(_text(width * 0.5, 30, "Constitutional Substrate", "stat", fill=p.muted))

    # Edges
    for src, dst in deps:
        if src in positions and dst in positions:
            x1, y1 = positions[src]
            x2, y2 = positions[dst]
            dx, dy = x2 - x1, y2 - y1
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                ux, uy = dx / dist, dy / dist
                x1a, y1a = x1 + ux * 28, y1 + uy * 28
                x2a, y2a = x2 - ux * 32, y2 - uy * 32
                svg.append(
                    f'<line x1="{x1a:.1f}" y1="{y1a:.1f}" '
                    f'x2="{x2a:.1f}" y2="{y2a:.1f}" '
                    f'stroke="{p.muted}" stroke-width="1.5" '
                    f'opacity="0.4" marker-end="url(#dep-arrow)"/>',
                )

    # Nodes
    r = 22
    for key, (x, y) in positions.items():
        fill = p.accent if key == "META" else p.secondary
        svg.append(_circle(x, y, r + 4, p.accent, opacity=0.06))
        svg.append(_circle(x, y, r, fill, stroke=p.accent, stroke_width=1.2))
        svg.append(_text(x, y - 4, ORGAN_LABELS.get(key, key), "label", fill=p.text))
        svg.append(_text(x, y + 10, key, "stat", fill=p.muted))

    svg.append('</svg>')
    return '\n'.join(svg)


def render_density_bars(
    organ_densities: dict[str, float] | None = None,
    palette: Palette | None = None,
    width: int = 600,
    height: int = 350,
) -> str:
    """Render per-organ density as horizontal bars.

    Density values 0.0-1.0, rendered as filled bars with organ labels.
    """
    p = palette or Palette()
    densities = organ_densities or {k: 0.5 for k in ORGAN_KEYS}

    svg = [_svg_header(width, height, "ORGANVM — Organ Density")]
    svg.append(f'<rect width="{width}" height="{height}" fill="{p.background}"/>')

    margin_left = 110
    margin_right = 40
    margin_top = 50
    bar_height = 24
    bar_gap = 10
    max_bar_width = width - margin_left - margin_right

    svg.append(_text(width / 2, 25, "System Density by Organ", "title", fill=p.text))

    items = sorted(densities.items(), key=lambda kv: kv[1], reverse=True)
    for i, (key, density) in enumerate(items):
        y = margin_top + i * (bar_height + bar_gap)
        bar_w = max_bar_width * min(density, 1.0)

        # Background bar
        svg.append(
            f'<rect x="{margin_left}" y="{y}" width="{max_bar_width}" '
            f'height="{bar_height}" fill="{p.primary}" rx="3"/>',
        )
        # Filled bar
        if bar_w > 0:
            svg.append(
                f'<rect x="{margin_left}" y="{y}" width="{bar_w:.1f}" '
                f'height="{bar_height}" fill="{p.accent}" opacity="0.75" rx="3"/>',
            )
        # Label
        label = f"{ORGAN_LABELS.get(key, key)} ({key})"
        svg.append(
            _text(margin_left - 8, y + bar_height / 2 + 4, label,
                  "label", anchor="end", fill=p.text),
        )
        # Percentage
        pct = f"{int(density * 100)}%"
        svg.append(
            _text(margin_left + bar_w + 8, y + bar_height / 2 + 4, pct,
                  "stat", anchor="start", fill=p.muted),
        )

    svg.append('</svg>')
    return '\n'.join(svg)


def render_organ_card(
    organ_key: str,
    repo_count: int = 0,
    flagship_count: int = 0,
    status_counts: dict[str, int] | None = None,
    edges: int = 0,
    formation_types: list[str] | None = None,
    palette: Palette | None = None,
    width: int = 400,
    height: int = 280,
) -> str:
    """Render an identity card for a single organ."""
    p = palette or Palette()
    statuses = status_counts or {}
    formations = formation_types or []

    label = ORGAN_LABELS.get(organ_key, organ_key)
    svg = [_svg_header(width, height, f"ORGANVM — {label}")]

    # Background
    svg.append(f'<rect width="{width}" height="{height}" fill="{p.background}" rx="8"/>')
    svg.append(
        f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" '
        f'fill="none" stroke="{p.accent}" stroke-width="1" rx="7" opacity="0.4"/>',
    )

    # Header band
    svg.append(f'<rect x="0" y="0" width="{width}" height="50" fill="{p.secondary}" rx="8"/>')
    svg.append(f'<rect x="0" y="40" width="{width}" height="10" fill="{p.secondary}"/>')
    svg.append(_text(20, 32, f"ORGAN {organ_key}", "title", anchor="start", fill=p.accent))
    svg.append(_text(width - 20, 32, label, "title", anchor="end", fill=p.text))

    # Stats grid
    y_start = 75
    line_h = 22
    col1_x = 30
    col2_x = width / 2 + 20

    stats = [
        ("Repositories", str(repo_count)),
        ("Flagships", str(flagship_count)),
        ("Dependency edges", str(edges)),
    ]

    for s_name, s_val in statuses.items():
        stats.append((s_name, str(s_val)))

    for i, (name, val) in enumerate(stats[:8]):
        col_x = col1_x if i % 2 == 0 else col2_x
        row_y = y_start + (i // 2) * line_h
        svg.append(_text(col_x, row_y, name, "stat", anchor="start", fill=p.muted))
        svg.append(
            _text(col_x + 120, row_y, val, "label", anchor="start", fill=p.text),
        )

    # Formation types
    if formations:
        fy = y_start + ((len(stats) + 1) // 2) * line_h + 10
        svg.append(_text(col1_x, fy, "Formations:", "stat", anchor="start", fill=p.muted))
        svg.append(
            _text(col1_x + 90, fy, ", ".join(formations[:5]), "stat",
                  anchor="start", fill=p.text),
        )

    # Footer
    svg.append(
        _text(width / 2, height - 12, "ORGANVM TESTAMENT", "stat", fill=p.muted),
    )

    svg.append('</svg>')
    return '\n'.join(svg)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _node_radius(repo_count: int) -> float:
    """Compute node radius from repo count (min 12, max 35)."""
    return max(12.0, min(35.0, 10.0 + math.sqrt(repo_count) * 4))
