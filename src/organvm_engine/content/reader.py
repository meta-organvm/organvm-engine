"""Parse and discover content pipeline posts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Directory name pattern: YYYY-MM-DD-{slug}
_POST_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-.+$")


@dataclass
class ContentPost:
    """A content pipeline post parsed from meta.yaml."""

    slug: str
    title: str
    date: str
    hook: str
    status: str
    source_session: str
    context: str
    tags: list[str]
    distribution: dict[str, Any]
    engagement: dict[str, Any]
    redacted_items: list[str]
    directory: Path
