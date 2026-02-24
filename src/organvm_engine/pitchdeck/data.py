"""Pitch deck data assembly — merges pitch.yaml > seed.yaml > registry > README."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from organvm_engine.pitchdeck.readme_parser import parse_readme, extract_first_paragraph


@dataclass
class PitchDeckData:
    """All content needed to render a pitch deck."""

    # Identity
    repo_name: str
    display_name: str
    organ_key: str
    organ_name: str
    org: str
    tier: str

    # Content
    tagline: str = ""
    description: str = ""
    problem_cards: list[dict[str, str]] = field(default_factory=list)
    solution_text: str = ""
    features: list[dict[str, str]] = field(default_factory=list)
    architecture_text: str = ""
    tech_stack: list[str] = field(default_factory=list)

    # Positioning
    dependencies: list[str] = field(default_factory=list)
    siblings: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)

    # Links
    github_url: str = ""
    docs_url: str = ""
    demo_url: str = ""

    # ORGAN-III market section
    market_text: str = ""
    revenue_model: str = ""
    revenue_status: str = ""

    # Tags for badges
    tags: list[str] = field(default_factory=list)

    # Promotion status
    promotion_status: str = "LOCAL"


# Organ name lookup (registry key -> human name)
_ORGAN_NAMES = {
    "ORGAN-I": "Theoria",
    "ORGAN-II": "Poiesis",
    "ORGAN-III": "Ergon",
    "ORGAN-IV": "Taxis",
    "ORGAN-V": "Logos",
    "ORGAN-VI": "Koinonia",
    "ORGAN-VII": "Kerygma",
    "META-ORGANVM": "Meta",
    "PERSONAL": "Personal",
}


def _humanize_name(repo_name: str) -> str:
    """Convert repo-name--descriptor to a human-readable display name.

    Double-hyphen separates function from descriptor:
        peer-audited--behavioral-blockchain -> Peer Audited: Behavioral Blockchain
    Single hyphen separates words:
        recursive-engine -> Recursive Engine
    """
    if "--" in repo_name:
        parts = repo_name.split("--", 1)
        left = parts[0].replace("-", " ").title()
        right = parts[1].replace("-", " ").title()
        return f"{left}: {right}"
    return repo_name.replace("-", " ").title()


def _load_pitch_yaml(repo_path: Path) -> dict[str, Any]:
    """Load pitch.yaml from a repo if it exists."""
    pitch_path = repo_path / "pitch.yaml"
    if not pitch_path.exists():
        return {}
    try:
        with open(pitch_path) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def _load_seed_yaml(repo_path: Path) -> dict[str, Any]:
    """Load seed.yaml from a repo if it exists."""
    seed_path = repo_path / "seed.yaml"
    if not seed_path.exists():
        return {}
    try:
        with open(seed_path) as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def assemble(
    repo_name: str,
    organ_key: str,
    repo_entry: dict[str, Any],
    repo_path: Path | None = None,
    seed: dict[str, Any] | None = None,
) -> PitchDeckData:
    """Assemble pitch deck data from all sources.

    Priority: pitch.yaml > seed.yaml > registry > README.md
    Gracefully degrades — a repo with only registry data still works.
    """
    organ_name = _ORGAN_NAMES.get(organ_key, "Unknown")
    org = repo_entry.get("org", "")

    # Start with registry data
    data = PitchDeckData(
        repo_name=repo_name,
        display_name=_humanize_name(repo_name),
        organ_key=organ_key,
        organ_name=organ_name,
        org=org,
        tier=repo_entry.get("tier", "standard"),
        description=repo_entry.get("description", ""),
        dependencies=repo_entry.get("dependencies", []),
        promotion_status=repo_entry.get("promotion_status", "LOCAL"),
        github_url=f"https://github.com/{org}/{repo_name}" if org else "",
        tech_stack=repo_entry.get("tech_stack", []),
        revenue_model=repo_entry.get("revenue_model", ""),
        revenue_status=repo_entry.get("revenue_status", ""),
    )

    # Layer seed.yaml data
    if seed is None and repo_path:
        seed = _load_seed_yaml(repo_path)

    if seed:
        meta = seed.get("metadata", {})
        if meta.get("description"):
            data.description = meta["description"]
        if meta.get("tags"):
            data.tags = meta["tags"]

        # Extract produces/consumes
        for edge in seed.get("produces", []):
            if isinstance(edge, dict):
                data.produces.append(edge.get("artifact", str(edge)))
            else:
                data.produces.append(str(edge))
        for edge in seed.get("consumes", []):
            if isinstance(edge, dict):
                data.consumes.append(edge.get("artifact", str(edge)))
            else:
                data.consumes.append(str(edge))

    # Layer README data (fallback content)
    if repo_path:
        readme_sections = parse_readme(repo_path / "README.md")

        if not data.description and "what this is" in readme_sections:
            data.description = extract_first_paragraph(readme_sections["what this is"])

        # Problem cards from README
        for key in ("problem", "the problem", "motivation", "why"):
            if key in readme_sections:
                text = readme_sections[key]
                data.problem_cards = _extract_cards_from_text(text, max_cards=3)
                break

        # Solution
        for key in ("solution", "the solution", "approach", "how it works", "overview"):
            if key in readme_sections:
                data.solution_text = extract_first_paragraph(readme_sections[key])
                break

        # Features
        for key in ("features", "key features", "capabilities"):
            if key in readme_sections:
                data.features = _extract_list_items(readme_sections[key], max_items=6)
                break

        # Architecture
        for key in ("architecture", "technical architecture", "design", "stack"):
            if key in readme_sections:
                data.architecture_text = extract_first_paragraph(readme_sections[key])
                break

        # Market (ORGAN-III)
        if organ_key == "ORGAN-III":
            for key in ("market", "business model", "revenue", "pricing"):
                if key in readme_sections:
                    data.market_text = extract_first_paragraph(readme_sections[key])
                    break

    # Layer pitch.yaml data (highest priority)
    if repo_path:
        pitch = _load_pitch_yaml(repo_path)
        if pitch:
            if pitch.get("display_name"):
                data.display_name = pitch["display_name"]
            if pitch.get("tagline"):
                data.tagline = pitch["tagline"]
            if pitch.get("description"):
                data.description = pitch["description"]
            if pitch.get("problem"):
                cards = pitch["problem"]
                if isinstance(cards, list):
                    data.problem_cards = [
                        {"title": c.get("title", ""), "text": c.get("text", "")}
                        for c in cards
                    ]
            if pitch.get("solution"):
                data.solution_text = pitch["solution"]
            if pitch.get("features"):
                feats = pitch["features"]
                if isinstance(feats, list):
                    data.features = [
                        {"title": f.get("title", ""), "text": f.get("text", "")}
                        if isinstance(f, dict) else {"title": str(f), "text": ""}
                        for f in feats
                    ]
            if pitch.get("architecture"):
                data.architecture_text = pitch["architecture"]
            if pitch.get("tech_stack"):
                data.tech_stack = pitch["tech_stack"]
            if pitch.get("github_url"):
                data.github_url = pitch["github_url"]
            if pitch.get("docs_url"):
                data.docs_url = pitch["docs_url"]
            if pitch.get("demo_url"):
                data.demo_url = pitch["demo_url"]
            if pitch.get("market"):
                data.market_text = pitch["market"]

    # Generate tagline from description if not set
    if not data.tagline and data.description:
        # Use first sentence or first 100 chars
        desc = data.description
        dot = desc.find(".")
        if 0 < dot < 120:
            data.tagline = desc[: dot + 1]
        else:
            data.tagline = desc[:100].rstrip() + ("..." if len(desc) > 100 else "")

    # Get siblings from registry
    # (populated by sync.py, not here — caller provides if needed)

    return data


def _strip_bullet(line: str) -> str:
    """Strip markdown bullet prefix without consuming bold markers."""
    import re
    return re.sub(r"^[-*]\s+|^\d+\.\s+", "", line.strip())


def _extract_cards_from_text(text: str, max_cards: int = 3) -> list[dict[str, str]]:
    """Extract problem/feature cards from markdown list items or paragraphs."""
    import re

    cards: list[dict[str, str]] = []
    bold_pattern = re.compile(r"\*\*(.+?)\*\*\s*[\u2014\u2013:\-]*\s*(.*)")

    # Try bullet points first
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ", "1. ", "2. ", "3. ")):
            content = _strip_bullet(line)
            m = bold_pattern.match(content)
            if m:
                cards.append({"title": m.group(1), "text": m.group(2) or ""})
            else:
                cards.append({"title": content[:50], "text": content})
            if len(cards) >= max_cards:
                break

    # Fallback: split by paragraphs
    if not cards:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p in paragraphs[:max_cards]:
            first_line = p.splitlines()[0].strip()
            cards.append({"title": first_line[:50], "text": extract_first_paragraph(p)})

    return cards[:max_cards]


def _extract_list_items(text: str, max_items: int = 6) -> list[dict[str, str]]:
    """Extract list items as feature cards."""
    import re

    bold_pattern = re.compile(r"\*\*(.+?)\*\*\s*[\u2014\u2013:\-]*\s*(.*)")
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.", "6.")):
            continue
        content = _strip_bullet(line)
        m = bold_pattern.match(content)
        if m:
            items.append({"title": m.group(1), "text": m.group(2) or ""})
        else:
            items.append({"title": content[:60], "text": ""})
        if len(items) >= max_items:
            break

    return items
