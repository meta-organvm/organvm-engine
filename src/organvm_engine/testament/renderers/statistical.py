"""Statistical renderers — SVG-based charts for system metrics.

Density maps, timelines, distribution charts. All rendered as raw SVG.
"""

from __future__ import annotations

import math

from organvm_engine.testament.renderers.svg import Palette, _esc, _svg_header, _text


def render_status_distribution(
    status_counts: dict[str, int],
    palette: Palette | None = None,
    width: int = 500,
    height: int = 500,
) -> str:
    """Render promotion status distribution as a donut chart.

    Each status gets a proportional arc segment.
    """
    p = palette or Palette()
    total = sum(status_counts.values())
    if total == 0:
        return _empty_chart(width, height, "No data", p)

    cx, cy = width / 2, height / 2
    outer_r = min(width, height) * 0.38
    inner_r = outer_r * 0.55

    # Color mapping for statuses
    status_colors = {
        "GRADUATED": p.accent,
        "PUBLIC_PROCESS": "#4ade80",
        "CANDIDATE": "#60a5fa",
        "LOCAL": p.muted,
        "ARCHIVED": "#6b7280",
    }

    svg = [_svg_header(width, height, "Status Distribution")]
    svg.append(f'<rect width="{width}" height="{height}" fill="{p.background}"/>')

    angle = -math.pi / 2
    gap = 0.03
    items = sorted(status_counts.items(), key=lambda kv: kv[1], reverse=True)

    for status, count in items:
        sweep = (count / total) * (2 * math.pi - len(items) * gap)
        end_angle = angle + sweep
        color = status_colors.get(status, p.secondary)

        # Arc path
        x1 = cx + outer_r * math.cos(angle)
        y1 = cy + outer_r * math.sin(angle)
        x2 = cx + outer_r * math.cos(end_angle)
        y2 = cy + outer_r * math.sin(end_angle)
        ix1 = cx + inner_r * math.cos(end_angle)
        iy1 = cy + inner_r * math.sin(end_angle)
        ix2 = cx + inner_r * math.cos(angle)
        iy2 = cy + inner_r * math.sin(angle)

        large = 1 if sweep > math.pi else 0
        path = (
            f"M {x1:.1f} {y1:.1f} "
            f"A {outer_r:.1f} {outer_r:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} "
            f"L {ix1:.1f} {iy1:.1f} "
            f"A {inner_r:.1f} {inner_r:.1f} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z"
        )
        svg.append(f'<path d="{path}" fill="{color}" opacity="0.8"/>')

        # Label at midpoint
        mid = angle + sweep / 2
        label_r = (outer_r + inner_r) / 2
        lx = cx + label_r * math.cos(mid)
        ly = cy + label_r * math.sin(mid)
        if sweep > 0.3:
            svg.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" class="stat" '
                f'text-anchor="middle" dominant-baseline="central" '
                f'fill="{p.background}" font-size="9">{count}</text>',
            )

        angle = end_angle + gap

    # Center hole
    from organvm_engine.testament.renderers.svg import _circle
    svg.append(_circle(cx, cy, inner_r - 1, p.background))

    # Center text
    svg.append(_text(cx, cy - 6, str(total), "big", fill=p.text))
    svg.append(_text(cx, cy + 14, "repos", "stat", fill=p.muted))

    # Legend
    legend_y = height - 20 - len(items) * 16
    for i, (status, count) in enumerate(items):
        ly = legend_y + i * 16
        color = status_colors.get(status, p.secondary)
        svg.append(
            f'<rect x="20" y="{ly - 8}" width="10" height="10" '
            f'fill="{color}" rx="2"/>',
        )
        svg.append(
            f'<text x="36" y="{ly}" class="stat" text-anchor="start" '
            f'fill="{p.text}">{_esc(status)} ({count})</text>',
        )

    svg.append(_text(width / 2, 25, "Promotion Status Distribution", "title", fill=p.text))
    svg.append('</svg>')
    return '\n'.join(svg)


def render_repo_heatmap(
    organ_repo_data: dict[str, list[dict]],
    palette: Palette | None = None,
    width: int = 800,
    height: int = 400,
) -> str:
    """Render a heatmap of repos per organ, colored by promotion status.

    Each repo is a small square. Organs are rows.
    """
    p = palette or Palette()

    status_colors = {
        "GRADUATED": p.accent,
        "PUBLIC_PROCESS": "#4ade80",
        "CANDIDATE": "#60a5fa",
        "LOCAL": "#374151",
        "ARCHIVED": "#1f2937",
    }

    svg = [_svg_header(width, height, "Repository Heatmap")]
    svg.append(f'<rect width="{width}" height="{height}" fill="{p.background}"/>')
    svg.append(_text(width / 2, 25, "Repository Heatmap by Organ", "title", fill=p.text))

    margin_left = 100
    margin_top = 50
    cell_size = 14
    cell_gap = 2
    max_cols = (width - margin_left - 30) // (cell_size + cell_gap)

    organ_labels = {
        "I": "Theoria", "II": "Poiesis", "III": "Ergon", "IV": "Taxis",
        "V": "Logos", "VI": "Koinonia", "VII": "Kerygma", "META": "Meta",
    }
    organ_order = ["META", "I", "II", "III", "IV", "V", "VI", "VII"]

    row = 0
    for organ_key in organ_order:
        repos = organ_repo_data.get(organ_key, [])
        if not repos:
            continue

        y = margin_top + row * (cell_size + cell_gap + 8)
        label = f"{organ_labels.get(organ_key, organ_key)} ({len(repos)})"
        svg.append(
            _text(margin_left - 8, y + cell_size / 2 + 3, label,
                  "stat", anchor="end", fill=p.muted),
        )

        for col, repo in enumerate(repos[:max_cols]):
            x = margin_left + col * (cell_size + cell_gap)
            status = repo.get("promotion_status", repo.get("status", "LOCAL"))
            color = status_colors.get(status, "#374151")
            name = repo.get("name", "")
            svg.append(
                f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                f'fill="{color}" rx="2" opacity="0.85">'
                f'<title>{_esc(name)} ({_esc(status)})</title></rect>',
            )

        row += 1

    # Legend
    lx = 20
    ly = height - 20
    for status, color in status_colors.items():
        svg.append(f'<rect x="{lx}" y="{ly - 8}" width="8" height="8" fill="{color}" rx="1"/>')
        svg.append(
            f'<text x="{lx + 12}" y="{ly}" class="stat" fill="{p.text}" '
            f'font-size="8">{_esc(status)}</text>',
        )
        lx += len(status) * 6 + 30

    svg.append('</svg>')
    return '\n'.join(svg)


def _empty_chart(width: int, height: int, message: str, palette: Palette) -> str:
    """Render an empty chart placeholder."""
    svg = [_svg_header(width, height, message)]
    svg.append(f'<rect width="{width}" height="{height}" fill="{palette.background}"/>')
    svg.append(_text(width / 2, height / 2, message, "stat", fill=palette.muted))
    svg.append('</svg>')
    return '\n'.join(svg)
