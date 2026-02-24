"""Parse README.md files to extract content by heading."""

from __future__ import annotations

import re
from pathlib import Path


def parse_readme(path: Path) -> dict[str, str]:
    """Extract sections from a README.md by heading.

    Returns a dict mapping lowercase heading text to the body content
    under that heading. For example, "## Problem" -> "problem": "body text".

    Headings are normalized: stripped, lowercased, with leading '#' removed.
    Only ## and ### headings are captured as section keys.
    """
    if not path.exists():
        return {}

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        match = re.match(r"^(#{2,3})\s+(.+)$", line)
        if match:
            # Save previous section
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = match.group(2).strip().lower()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    # Save final section
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def extract_first_paragraph(text: str) -> str:
    """Extract the first non-empty paragraph from markdown text."""
    lines = []
    in_para = False
    in_code_block = False
    for line in text.splitlines():
        stripped = line.strip()
        # Track code fences
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if in_para:
                break
            continue
        if in_code_block:
            continue
        if not stripped:
            if in_para:
                break
            continue
        # Skip markdown artifacts
        if stripped.startswith(("![", "|", "---", "===", "- [x]", "- [ ]")):
            if in_para:
                break
            continue
        in_para = True
        lines.append(stripped)

    return " ".join(lines)
