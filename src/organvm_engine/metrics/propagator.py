"""Propagate metrics from system-metrics.json into documentation files."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PropagationResult:
    """Result of a metrics propagation run."""

    replacements: int = 0
    files_changed: int = 0
    details: list[str] = field(default_factory=list)


def build_patterns(metrics: dict) -> list[tuple[str, re.Pattern, str]]:
    """Build regex patterns for metric replacement.

    Returns list of (metric_name, compiled_pattern, replacement_string).
    """
    c = metrics.get("computed", {})
    m = metrics.get("manual", {})

    total_repos = c.get("total_repos", 0)
    active_repos = c.get("active_repos", 0)
    essays = c.get("published_essays", 0)
    ci_workflows = c.get("ci_workflows", 0)
    dep_edges = c.get("dependency_edges", 0)

    total_words_numeric = str(m.get("total_words_numeric", 404000))
    total_words_formatted = f"{int(total_words_numeric):,}"
    total_words_short = m.get("total_words_short", "404K+")

    patterns = []

    def add(name: str, regex: str, replacement: str) -> None:
        patterns.append((name, re.compile(regex), replacement))

    # Total repos patterns
    add("total_repos", r"(\b)\d+( repositor(?:ies|y) across\b)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(coordinating )\d+( repo)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(Repos-)\d+", rf"\g<1>{total_repos}")
    add("total_repos", r"(\b)\d+(-repo system\b)", rf"\g<1>{total_repos}\2")
    add("total_repos", r"(across )\d+( repo)", rf"\g<1>{total_repos}\2")

    # Active repos
    add("active_repos", r"(\b)\d+( ACTIVE\b)", rf"\g<1>{active_repos}\2")

    # Essays
    add("published_essays", r"(\b)\d+(\+? published essays?\b)", rf"\g<1>{essays}\2")
    add("published_essays", r"(\b)\d+(\+? meta-system essays?\b)", rf"\g<1>{essays}\2")

    # CI workflows
    add("ci_workflows", r"(\b)\d+(\+ CI/CD workflows?\b)", rf"\g<1>{ci_workflows}\2")

    # Dependencies
    add("dependency_edges", r"(\b)\d+( dependency edges?\b)", rf"\g<1>{dep_edges}\2")

    # Word counts
    add("total_words", r"~\d{3},\d{3}\+?( words)", rf"~{total_words_formatted}+\1")
    add("total_words", r"~?\d{3}K\+?( words)", rf"~{total_words_short}\1")

    return patterns


# Lines containing these markers are historical and should not be updated
SKIP_MARKERS = [
    "Sprint (",
    "Phase 1 (",
    "Phase 2 (",
    "Phase 3 (",
    "Launch (",
    "Silver Sprint:",
    "Bronze Sprint",
    "Gold Sprint",
    "Platinum Sprint",
    "Previous:",
    "**Phase",
    "**Launch",
    "| COMPLETED |",
]


def propagate_metrics(
    metrics: dict,
    files: list[Path],
    dry_run: bool = False,
) -> PropagationResult:
    """Apply metric updates to documentation files.

    Args:
        metrics: Loaded system-metrics.json dict.
        files: List of file paths to update.
        dry_run: If True, don't write changes.

    Returns:
        PropagationResult with change details.
    """
    result = PropagationResult()
    patterns = build_patterns(metrics)

    for filepath in files:
        if not filepath.exists():
            continue

        lines = filepath.read_text().splitlines(keepends=True)
        new_lines = []
        file_changed = False

        for line in lines:
            # Skip historical lines
            if any(marker in line for marker in SKIP_MARKERS):
                new_lines.append(line)
                continue

            new_line = line
            for metric_name, pattern, replacement in patterns:
                candidate = pattern.sub(replacement, new_line)
                if candidate != new_line:
                    result.replacements += 1
                    result.details.append(f"{filepath.name}: {metric_name}")
                    new_line = candidate
                    file_changed = True

            new_lines.append(new_line)

        if file_changed:
            result.files_changed += 1
            if not dry_run:
                filepath.write_text("".join(new_lines))

    return result
