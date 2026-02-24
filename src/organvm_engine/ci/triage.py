"""CI failure triage from soak-test data.

Reads the latest soak snapshot, categorizes CI failures by organ and
failure type, and produces a prioritized triage report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.paths import soak_dir as _default_soak_dir


@dataclass
class CITriageReport:
    """Categorized CI failure triage."""
    date: str = ""
    total_checked: int = 0
    passing: int = 0
    failing: int = 0
    pass_rate: float = 0.0
    by_organ: dict[str, list[dict]] = field(default_factory=dict)
    phantom_candidates: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        lines.append(f"CI Triage Report — {self.date}")
        lines.append(f"{'─' * 60}")
        lines.append(
            f"  {self.passing}/{self.total_checked} passing "
            f"({self.pass_rate:.0%}), {self.failing} failing"
        )

        if self.by_organ:
            lines.append(f"\n  Failures by Organ")
            lines.append(f"  {'─' * 50}")
            for organ, repos in sorted(self.by_organ.items()):
                lines.append(f"    {organ} ({len(repos)} failing):")
                for repo in repos:
                    phantom = " [PHANTOM?]" if repo["name"] in self.phantom_candidates else ""
                    lines.append(f"      - {repo['name']}{phantom}")

        if self.phantom_candidates:
            lines.append(f"\n  Phantom Candidates ({len(self.phantom_candidates)})")
            lines.append(f"  {'─' * 50}")
            lines.append(
                "  These repos may have schedule-only workflows that report "
                "failure when no code has changed."
            )
            for name in self.phantom_candidates:
                lines.append(f"    - {name}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "total_checked": self.total_checked,
            "passing": self.passing,
            "failing": self.failing,
            "pass_rate": self.pass_rate,
            "by_organ": self.by_organ,
            "phantom_candidates": self.phantom_candidates,
        }


# Repos known to use schedule-only workflows (no push/PR trigger)
_SCHEDULE_ONLY_PATTERNS = {
    ".github",
    "announcement-templates",
    "social-automation",
    "distribution-strategy",
}


def triage(soak_dir: Path | str | None = None) -> CITriageReport:
    """Read latest soak snapshot and categorize CI failures.

    Args:
        soak_dir: Path to soak-test data directory.

    Returns:
        CITriageReport with categorized failures.
    """
    d = Path(soak_dir) if soak_dir else _default_soak_dir()
    report = CITriageReport()

    if not d.is_dir():
        return report

    snapshots = sorted(d.glob("daily-*.json"))
    if not snapshots:
        return report

    with open(snapshots[-1]) as f:
        latest = json.load(f)

    report.date = latest.get("date", "unknown")

    ci = latest.get("ci", {})
    report.total_checked = ci.get("total_checked", 0)
    report.passing = ci.get("passing", 0)
    report.failing = ci.get("failing", 0)
    report.pass_rate = (
        report.passing / report.total_checked
        if report.total_checked > 0
        else 0.0
    )

    # Categorize failures by organ
    failing_repos = ci.get("failing_repos", [])
    for entry in failing_repos:
        if isinstance(entry, str):
            # Simple string format: "organ/repo"
            parts = entry.split("/", 1)
            if len(parts) == 2:
                organ, repo_name = parts
            else:
                organ, repo_name = "UNKNOWN", entry
            entry_dict = {"name": repo_name, "organ": organ}
        elif isinstance(entry, dict):
            organ = entry.get("organ", "UNKNOWN")
            repo_name = entry.get("name", entry.get("repo", "unknown"))
            entry_dict = entry
        else:
            continue

        report.by_organ.setdefault(organ, []).append(entry_dict)

        # Check for phantom candidates
        if repo_name in _SCHEDULE_ONLY_PATTERNS:
            report.phantom_candidates.append(repo_name)

    return report
