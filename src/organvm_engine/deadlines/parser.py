"""Parse deadlines from rolling-todo.md.

Extracts deadline dates from markdown entries using several patterns:
- **deadline Mar 6** — explicit deadline
- **deadline April 2, 3pm ET** — explicit with time
- **opens Apr 14, closes May 12** — window (uses close date)
- **window Apr 1-Jun 1** — window (uses end date)
- **opens May 1** — open date (no close)
- **~Apr 2026** — approximate
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from organvm_engine.paths import corpus_dir as _default_corpus_dir

# Month name → number
_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Patterns to extract dates from bold markers
_DEADLINE_RE = re.compile(
    r"\*\*deadline\s+(\w+)\s+(\d{1,2})(?:,?\s+[^*]*)?\*\*",
    re.IGNORECASE,
)
_DEADLINE_FULL_RE = re.compile(
    r"\*\*deadline\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
_CLOSES_RE = re.compile(
    r"\*\*(?:opens\s+\w+\s+\d{1,2},?\s*)?closes\s+(\w+)\s+(\d{1,2})\*\*",
    re.IGNORECASE,
)
_WINDOW_RE = re.compile(
    r"\*\*window\s+\w+\s+\d{1,2}\s*[-–]\s*(\w+)\s+(\d{1,2})\*\*",
    re.IGNORECASE,
)
_OPENS_RE = re.compile(
    r"\*\*opens\s+(\w+)\s+(\d{1,2})\*\*",
    re.IGNORECASE,
)
_APPROX_RE = re.compile(
    r"\*\*~(\w+)(?:\s+(\d{4}))?\*\*",
    re.IGNORECASE,
)
# Item ID pattern: **F4.**, **X1.**, **E3.**, etc.
_ITEM_ID_RE = re.compile(r"\*\*([A-Z]\d+(?:-II)?)\.\*\*")


@dataclass
class Deadline:
    """A parsed deadline entry."""
    item_id: str
    description: str
    deadline_date: date
    approximate: bool = False
    source_line: str = ""

    @property
    def days_remaining(self) -> int:
        return (self.deadline_date - date.today()).days

    @property
    def urgency(self) -> str:
        d = self.days_remaining
        if d < 0:
            return "OVERDUE"
        if d <= 7:
            return "THIS WEEK"
        if d <= 14:
            return "SOON"
        if d <= 30:
            return "UPCOMING"
        return "LATER"


def _parse_month_day(month_str: str, day_str: str, year: int | None = None) -> date | None:
    """Parse a month name and day number into a date."""
    month = _MONTHS.get(month_str.lower())
    if not month:
        return None
    day = int(day_str)
    if year is None:
        year = date.today().year
        # If the date has already passed this year, assume next year
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d < date.today() - timedelta(days=90):
            d = date(year + 1, month, day)
        return d
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_approx_month(month_str: str, year: int | None = None) -> date | None:
    """Parse an approximate month into a date (uses the 15th)."""
    # Handle "Apr-May" ranges — use the later month
    if "-" in month_str:
        parts = month_str.split("-")
        month_str = parts[-1]

    month = _MONTHS.get(month_str.lower())
    if not month:
        return None
    if year is None:
        year = date.today().year
    try:
        return date(year, month, 15)
    except ValueError:
        return None


def parse_deadlines(
    corpus_dir: Path | str | None = None,
) -> list[Deadline]:
    """Parse all deadlines from rolling-todo.md.

    Args:
        corpus_dir: Path to the corpus directory.

    Returns:
        List of Deadline objects sorted by date.
    """
    d = Path(corpus_dir) if corpus_dir else _default_corpus_dir()
    todo_path = d / "docs" / "operations" / "rolling-todo.md"

    if not todo_path.exists():
        return []

    text = todo_path.read_text()
    deadlines = []

    for line in text.splitlines():
        # Skip completed items
        if line.strip().startswith("- [x]"):
            continue

        # Must have a checkbox to be an actionable item
        if not line.strip().startswith("- [ ]"):
            continue

        # Extract item ID
        id_match = _ITEM_ID_RE.search(line)
        item_id = id_match.group(1) if id_match else "?"

        # Extract description (text after the ID up to the first em-dash or deadline marker)
        desc = line.strip()
        desc = re.sub(r"^- \[ \] \*\*\w+(?:-II)?\.\*\*\s*", "", desc)
        # Trim at the first bold marker or long dash
        desc = re.split(r"\s*[—–]\s*(?:STAGED|Source|URL)", desc)[0].strip()
        # Trim trailing markdown
        desc = re.sub(r"\s*\*\*.*$", "", desc).strip()
        if not desc:
            desc = line.strip()[:80]

        # Try each pattern in priority order
        parsed_date = None
        approximate = False

        # Explicit deadline with year
        m = _DEADLINE_FULL_RE.search(line)
        if m:
            parsed_date = _parse_month_day(m.group(1), m.group(2), int(m.group(3)))

        # Explicit deadline without year
        if not parsed_date:
            m = _DEADLINE_RE.search(line)
            if m:
                parsed_date = _parse_month_day(m.group(1), m.group(2))

        # Window close date
        if not parsed_date:
            m = _CLOSES_RE.search(line)
            if m:
                parsed_date = _parse_month_day(m.group(1), m.group(2))

        # Window end date
        if not parsed_date:
            m = _WINDOW_RE.search(line)
            if m:
                parsed_date = _parse_month_day(m.group(1), m.group(2))

        # Opens date
        if not parsed_date:
            m = _OPENS_RE.search(line)
            if m:
                parsed_date = _parse_month_day(m.group(1), m.group(2))

        # Approximate month
        if not parsed_date:
            m = _APPROX_RE.search(line)
            if m:
                year = int(m.group(2)) if m.group(2) else None
                parsed_date = _parse_approx_month(m.group(1), year)
                approximate = True

        if parsed_date:
            deadlines.append(Deadline(
                item_id=item_id,
                description=desc,
                deadline_date=parsed_date,
                approximate=approximate,
                source_line=line.strip()[:120],
            ))

    deadlines.sort(key=lambda d: d.deadline_date)
    return deadlines


def filter_upcoming(
    deadlines: list[Deadline],
    days: int = 30,
) -> list[Deadline]:
    """Filter deadlines to those within N days from today."""
    cutoff = date.today() + timedelta(days=days)
    return [d for d in deadlines if d.deadline_date <= cutoff]


def format_deadlines(deadlines: list[Deadline]) -> str:
    """Format deadline list for terminal output."""
    if not deadlines:
        return "  No upcoming deadlines found."

    lines = []
    lines.append(f"  {'ID':<10} {'Date':<14} {'Days':<8} {'Urgency':<12} Description")
    lines.append(f"  {'─' * 80}")

    for d in deadlines:
        approx = "~" if d.approximate else " "
        days_str = f"{d.days_remaining:>4}d"
        lines.append(
            f"  {d.item_id:<10} {approx}{d.deadline_date.isoformat():<13} "
            f"{days_str:<8} {d.urgency:<12} {d.description[:45]}"
        )

    return "\n".join(lines)
