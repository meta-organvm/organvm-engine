"""Plan hygiene — sweep rules engine and archive operations.

Identifies plans eligible for archival (superseded, completed, orphaned subplans,
stale) and moves them to ``plans/archive/YYYY-MM/`` directories.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from organvm_engine.plans.index import PlanEntry


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SweepCandidate:
    """A plan flagged for potential archival."""

    entry: "PlanEntry"
    reason: str  # superseded | completed | orphan_subplan | stale
    confidence: str  # auto | review
    archive_target: str  # computed destination path


@dataclass
class ArchiveResult:
    """Outcome of an archive operation."""

    moved: int = 0
    skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


@dataclass
class PlanSprawl:
    """High-level sprawl metrics for the plan corpus."""

    total_active: int
    sweep_candidates: int
    oldest_untouched_days: int
    sprawl_level: str  # clean | growing | sprawling | critical


# ---------------------------------------------------------------------------
# Archive path computation
# ---------------------------------------------------------------------------

_DATE_PREFIX_RE = re.compile(r"^(\d{4})-(\d{2})")


def compute_archive_path(plan_path: Path) -> Path:
    """Compute the archive destination for a plan file.

    Finds the nearest ``plans/`` ancestor and targets
    ``<plans_dir>/archive/YYYY-MM/<filename>``.
    """
    # Walk up to find the plans/ directory
    plans_dir = _find_plans_ancestor(plan_path)

    # Extract YYYY-MM from filename date prefix, fallback to mtime
    m = _DATE_PREFIX_RE.match(plan_path.name)
    if m:
        year_month = f"{m.group(1)}-{m.group(2)}"
    else:
        try:
            mtime = plan_path.stat().st_mtime
            dt = datetime.fromtimestamp(mtime)
            year_month = dt.strftime("%Y-%m")
        except OSError:
            year_month = datetime.now(timezone.utc).strftime("%Y-%m")

    target = plans_dir / "archive" / year_month / plan_path.name

    # Handle collision
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        parent = target.parent
        n = 2
        while True:
            candidate = parent / f"{stem}-{n}{suffix}"
            if not candidate.exists():
                return candidate
            n += 1

    return target


def _find_plans_ancestor(plan_path: Path) -> Path:
    """Find the nearest ``plans/`` directory in the path ancestry."""
    for parent in plan_path.parents:
        if parent.name == "plans":
            return parent
    # Fallback: use the file's parent directory
    return plan_path.parent


# ---------------------------------------------------------------------------
# Sweep rules
# ---------------------------------------------------------------------------

ARCHIVAL_REASONS = {
    "superseded": "Higher version exists for same slug",
    "completed": "All tasks marked complete",
    "orphan_subplan": "Parent plan is archived or superseded",
    "stale": "No progress, older than threshold",
}


def sweep_candidates(
    entries: list["PlanEntry"],
    stale_days: int = 14,
) -> list[SweepCandidate]:
    """Identify plans eligible for archival.

    Rules (applied in priority order):
    1. superseded — status already set by lifecycle inference (auto)
    2. completed — all tasks done (auto)
    3. orphan_subplan — agent subplan whose parent is archived/superseded (auto)
    4. stale — active, tasks > 0 but 0 completed, age > stale_days (review)
    5. stale — active, no tasks at all, age > stale_days (review)
    """
    candidates: list[SweepCandidate] = []
    seen_ids: set[str] = set()

    # Build lookup for parent status (for orphan detection)
    status_by_slug: dict[str, str] = {}
    for e in entries:
        status_by_slug[e.slug] = e.status

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for e in entries:
        if e.status == "archived":
            continue

        reason = None
        confidence = "auto"

        # Rule 1: superseded
        if e.status == "superseded":
            reason = "superseded"

        # Rule 2: completed
        elif e.task_count > 0 and e.completed_count == e.task_count:
            reason = "completed"

        # Rule 3: orphan subplan
        elif _is_orphan_subplan(e, entries):
            reason = "orphan_subplan"

        # Rule 4/5: stale
        elif e.status == "active":
            age = _age_days(e.date, today)
            if (
                age is not None
                and age > stale_days
                and ((e.task_count > 0 and e.completed_count == 0) or e.task_count == 0)
            ):
                reason = "stale"
                confidence = "review"

        if reason and e.qualified_id not in seen_ids:
            seen_ids.add(e.qualified_id)
            archive_target = str(compute_archive_path(Path(e.path)))
            candidates.append(SweepCandidate(
                entry=e,
                reason=reason,
                confidence=confidence,
                archive_target=archive_target,
            ))

    return candidates


_SUBPLAN_RE = re.compile(r"-agent-a[0-9a-f]+$", re.IGNORECASE)


def _is_orphan_subplan(
    entry: "PlanEntry",
    all_entries: list["PlanEntry"],
) -> bool:
    """Check if entry is an agent subplan whose parent is archived/superseded."""
    if not _SUBPLAN_RE.search(entry.slug):
        return False

    parent_slug = _SUBPLAN_RE.sub("", entry.slug)
    for candidate in all_entries:
        if candidate.slug == parent_slug and candidate.agent == entry.agent:
            return candidate.status in ("archived", "superseded")
    # No parent found at all — treat as orphan
    return True


def _age_days(date_str: str, today_str: str) -> int | None:
    """Compute age in days between two YYYY-MM-DD strings."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        t = datetime.strptime(today_str, "%Y-%m-%d")
        return (t - d).days
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Archive operation
# ---------------------------------------------------------------------------

def archive_plans(
    candidates: list[SweepCandidate],
    dry_run: bool = True,
) -> ArchiveResult:
    """Move plan files to their archive targets.

    Args:
        candidates: Plans to archive.
        dry_run: If True (default), report what would happen without moving.
    """
    result = ArchiveResult()

    for c in candidates:
        src = Path(c.entry.path)
        dst = Path(c.archive_target)

        if not src.exists():
            result.skipped += 1
            result.details.append(f"SKIP (missing): {src}")
            continue

        if dry_run:
            result.moved += 1
            result.details.append(f"WOULD MOVE: {src} -> {dst}")
        else:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                result.moved += 1
                result.details.append(f"MOVED: {src} -> {dst}")
            except OSError as e:
                result.errors.append((str(src), str(e)))
                result.details.append(f"ERROR: {src} — {e}")

    result.skipped = len(candidates) - result.moved - len(result.errors)
    return result


# ---------------------------------------------------------------------------
# Sprawl metrics
# ---------------------------------------------------------------------------

def compute_sprawl(entries: list["PlanEntry"]) -> PlanSprawl:
    """Compute high-level sprawl metrics from plan entries."""
    active = [e for e in entries if e.status == "active"]
    total_active = len(active)

    candidates = sweep_candidates(entries)
    sweep_count = len(candidates)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    oldest = 0
    for e in active:
        age = _age_days(e.date, today)
        if age is not None and age > oldest:
            oldest = age

    if total_active < 20:
        level = "clean"
    elif total_active < 50:
        level = "growing"
    elif total_active < 100:
        level = "sprawling"
    else:
        level = "critical"

    return PlanSprawl(
        total_active=total_active,
        sweep_candidates=sweep_count,
        oldest_untouched_days=oldest,
        sprawl_level=level,
    )
