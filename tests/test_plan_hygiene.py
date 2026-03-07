"""Tests for plans/hygiene.py — sweep rules, archive paths, and sprawl metrics."""

from __future__ import annotations

from pathlib import Path

import pytest

from organvm_engine.plans.hygiene import (
    ArchiveResult,
    SweepCandidate,
    archive_plans,
    compute_archive_path,
    compute_sprawl,
    sweep_candidates,
    _age_days,
    _find_plans_ancestor,
    _is_orphan_subplan,
)
from organvm_engine.plans.index import PlanEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    *,
    slug: str = "test-plan",
    status: str = "active",
    task_count: int = 0,
    completed_count: int = 0,
    date: str = "2026-01-01",
    agent: str = "claude",
    organ: str | None = "META",
    repo: str | None = "engine",
    path: str = "/tmp/plans/2026-01-01-test-plan.md",
    version: int = 1,
) -> PlanEntry:
    return PlanEntry(
        qualified_id=f"{agent}:{organ or '?'}:{repo or '?'}:{slug}",
        path=path,
        agent=agent,
        organ=organ,
        repo=repo,
        slug=slug,
        date=date,
        version=version,
        status=status,
        title=f"Test Plan: {slug}",
        size_bytes=1024,
        has_verification=False,
        archetype=None,
        task_count=task_count,
        completed_count=completed_count,
        tags=[],
        file_refs=[],
        domain_fingerprint="abc123",
    )


# ---------------------------------------------------------------------------
# TestSweepCandidates
# ---------------------------------------------------------------------------

class TestSweepCandidates:
    def test_superseded_flagged(self):
        e = _entry(status="superseded")
        result = sweep_candidates([e])
        assert len(result) == 1
        assert result[0].reason == "superseded"
        assert result[0].confidence == "auto"

    def test_completed_flagged(self):
        e = _entry(task_count=5, completed_count=5)
        result = sweep_candidates([e])
        assert len(result) == 1
        assert result[0].reason == "completed"
        assert result[0].confidence == "auto"

    def test_partial_completion_not_flagged(self):
        e = _entry(task_count=5, completed_count=3)
        result = sweep_candidates([e])
        assert len(result) == 0

    def test_stale_with_tasks(self):
        e = _entry(task_count=3, completed_count=0, date="2025-01-01")
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 1
        assert result[0].reason == "stale"
        assert result[0].confidence == "review"

    def test_stale_empty_plan(self):
        e = _entry(task_count=0, completed_count=0, date="2025-01-01")
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 1
        assert result[0].reason == "stale"
        assert result[0].confidence == "review"

    def test_recent_not_stale(self):
        e = _entry(task_count=3, completed_count=0, date="2099-01-01")
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 0

    def test_archived_excluded(self):
        e = _entry(status="archived")
        result = sweep_candidates([e])
        assert len(result) == 0

    def test_no_duplicates(self):
        """Same entry should not appear twice even if multiple rules match."""
        e = _entry(status="superseded", task_count=5, completed_count=5)
        result = sweep_candidates([e])
        assert len(result) == 1
        assert result[0].reason == "superseded"  # superseded has higher priority


# ---------------------------------------------------------------------------
# TestSweepSuperseded
# ---------------------------------------------------------------------------

class TestSweepSuperseded:
    def test_v1_superseded_by_v2(self):
        v1 = _entry(slug="my-plan", version=1, status="superseded",
                     path="/tmp/plans/2026-01-01-my-plan.md")
        v2 = _entry(slug="my-plan", version=2, status="active", date="2099-01-01",
                     path="/tmp/plans/2026-01-01-my-plan-v2.md")
        result = sweep_candidates([v1, v2])
        reasons = {c.entry.slug: c.reason for c in result}
        assert "my-plan" in reasons
        assert reasons["my-plan"] == "superseded"
        # v2 should not be flagged
        flagged_versions = [c.entry.version for c in result]
        assert 2 not in flagged_versions

    def test_cross_agent_superseded(self):
        claude = _entry(slug="shared-plan", agent="claude", status="superseded")
        gemini = _entry(slug="shared-plan", agent="gemini", status="active", date="2099-01-01")
        result = sweep_candidates([claude, gemini])
        assert len(result) == 1
        assert result[0].entry.agent == "claude"

    def test_active_not_superseded(self):
        e = _entry(status="active", date="2099-01-01")
        result = sweep_candidates([e])
        assert all(c.reason != "superseded" for c in result)


# ---------------------------------------------------------------------------
# TestSweepCompleted
# ---------------------------------------------------------------------------

class TestSweepCompleted:
    def test_all_done(self):
        e = _entry(task_count=10, completed_count=10)
        result = sweep_candidates([e])
        assert len(result) == 1
        assert result[0].reason == "completed"

    def test_partial_not_flagged(self):
        e = _entry(task_count=10, completed_count=9)
        result = sweep_candidates([e])
        assert len(result) == 0

    def test_zero_task_not_completed(self):
        """A plan with 0 tasks is not 'completed' — it's empty."""
        e = _entry(task_count=0, completed_count=0, date="2099-01-01")
        result = sweep_candidates([e])
        completed = [c for c in result if c.reason == "completed"]
        assert len(completed) == 0


# ---------------------------------------------------------------------------
# TestSweepOrphanSubplan
# ---------------------------------------------------------------------------

class TestSweepOrphanSubplan:
    def test_parent_archived_is_orphan(self):
        parent = _entry(slug="big-plan", status="archived")
        child = _entry(
            slug="big-plan-agent-a1b2c3",
            path="/tmp/plans/2026-01-01-big-plan-agent-a1b2c3.md",
        )
        result = sweep_candidates([parent, child])
        orphans = [c for c in result if c.reason == "orphan_subplan"]
        assert len(orphans) == 1
        assert orphans[0].entry.slug == "big-plan-agent-a1b2c3"

    def test_parent_active_not_orphan(self):
        parent = _entry(slug="big-plan", status="active", date="2099-01-01")
        child = _entry(
            slug="big-plan-agent-a1b2c3",
            date="2099-01-01",
            path="/tmp/plans/2026-01-01-big-plan-agent-a1b2c3.md",
        )
        result = sweep_candidates([parent, child])
        orphans = [c for c in result if c.reason == "orphan_subplan"]
        assert len(orphans) == 0

    def test_no_parent_is_orphan(self):
        """Subplan with no matching parent is treated as orphan."""
        child = _entry(
            slug="missing-parent-agent-a1b2c3",
            path="/tmp/plans/2026-01-01-missing-parent-agent-a1b2c3.md",
        )
        result = sweep_candidates([child])
        orphans = [c for c in result if c.reason == "orphan_subplan"]
        assert len(orphans) == 1


# ---------------------------------------------------------------------------
# TestSweepStale
# ---------------------------------------------------------------------------

class TestSweepStale:
    def test_at_threshold_not_stale(self):
        """Plan exactly at stale_days is not stale (must exceed)."""
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc)
        threshold_date = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        e = _entry(task_count=3, completed_count=0, date=threshold_date)
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 0

    def test_beyond_threshold_is_stale(self):
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc)
        old_date = (today - timedelta(days=15)).strftime("%Y-%m-%d")
        e = _entry(task_count=3, completed_count=0, date=old_date)
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 1
        assert result[0].confidence == "review"

    def test_with_progress_not_stale(self):
        e = _entry(task_count=5, completed_count=1, date="2025-01-01")
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 0

    def test_invalid_date_skipped(self):
        e = _entry(task_count=3, completed_count=0, date="bad-date")
        result = sweep_candidates([e], stale_days=14)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# TestComputeArchivePath
# ---------------------------------------------------------------------------

class TestComputeArchivePath:
    def test_dated_filename(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        f = plans_dir / "2026-03-06-my-plan.md"
        f.write_text("# Plan")
        result = compute_archive_path(f)
        assert result == plans_dir / "archive" / "2026-03" / "2026-03-06-my-plan.md"

    def test_nested_plans_dir(self, tmp_path):
        plans_dir = tmp_path / ".claude" / "plans"
        plans_dir.mkdir(parents=True)
        f = plans_dir / "2025-12-01-old-plan.md"
        f.write_text("# Old")
        result = compute_archive_path(f)
        assert result == plans_dir / "archive" / "2025-12" / "2025-12-01-old-plan.md"

    def test_mtime_fallback(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        f = plans_dir / "undated-plan.md"
        f.write_text("# Undated")
        result = compute_archive_path(f)
        # Should use mtime-derived YYYY-MM
        assert "archive" in str(result)
        assert result.name == "undated-plan.md"

    def test_collision_suffix(self, tmp_path):
        plans_dir = tmp_path / "plans"
        archive_dir = plans_dir / "archive" / "2026-03"
        archive_dir.mkdir(parents=True)
        existing = archive_dir / "2026-03-06-plan.md"
        existing.write_text("# Already here")

        f = plans_dir / "2026-03-06-plan.md"
        (plans_dir).mkdir(exist_ok=True)
        f.write_text("# Duplicate")
        result = compute_archive_path(f)
        assert result.name == "2026-03-06-plan-2.md"

    def test_double_collision(self, tmp_path):
        plans_dir = tmp_path / "plans"
        archive_dir = plans_dir / "archive" / "2026-03"
        archive_dir.mkdir(parents=True)
        (archive_dir / "2026-03-06-plan.md").write_text("v1")
        (archive_dir / "2026-03-06-plan-2.md").write_text("v2")

        f = plans_dir / "2026-03-06-plan.md"
        plans_dir.mkdir(exist_ok=True)
        f.write_text("v3")
        result = compute_archive_path(f)
        assert result.name == "2026-03-06-plan-3.md"

    def test_no_plans_ancestor(self, tmp_path):
        """File not under a plans/ dir — falls back to parent."""
        f = tmp_path / "2026-03-06-random.md"
        f.write_text("# Random")
        result = compute_archive_path(f)
        assert result.parent == tmp_path / "archive" / "2026-03"


# ---------------------------------------------------------------------------
# TestArchivePlans
# ---------------------------------------------------------------------------

class TestArchivePlans:
    def _candidate(self, src: Path, dst: Path) -> SweepCandidate:
        entry = _entry(path=str(src))
        return SweepCandidate(
            entry=entry,
            reason="superseded",
            confidence="auto",
            archive_target=str(dst),
        )

    def test_dry_run_no_move(self, tmp_path):
        src = tmp_path / "plans" / "old.md"
        src.parent.mkdir()
        src.write_text("# Old")
        dst = tmp_path / "plans" / "archive" / "2026-03" / "old.md"

        c = self._candidate(src, dst)
        result = archive_plans([c], dry_run=True)
        assert result.moved == 1
        assert src.exists()
        assert not dst.exists()

    def test_write_moves_file(self, tmp_path):
        src = tmp_path / "plans" / "old.md"
        src.parent.mkdir()
        src.write_text("# Old")
        dst = tmp_path / "plans" / "archive" / "2026-03" / "old.md"

        c = self._candidate(src, dst)
        result = archive_plans([c], dry_run=False)
        assert result.moved == 1
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "# Old"

    def test_creates_archive_dirs(self, tmp_path):
        src = tmp_path / "plans" / "old.md"
        src.parent.mkdir()
        src.write_text("# Old")
        dst = tmp_path / "plans" / "archive" / "2026-01" / "old.md"

        c = self._candidate(src, dst)
        archive_plans([c], dry_run=False)
        assert dst.parent.is_dir()

    def test_missing_source_skipped(self, tmp_path):
        src = tmp_path / "nonexistent.md"
        dst = tmp_path / "archive" / "nonexistent.md"
        c = self._candidate(src, dst)
        result = archive_plans([c], dry_run=False)
        assert result.skipped == 1
        assert result.moved == 0

    def test_multiple_files(self, tmp_path):
        candidates = []
        for i in range(3):
            src = tmp_path / "plans" / f"plan-{i}.md"
            src.parent.mkdir(exist_ok=True)
            src.write_text(f"# Plan {i}")
            dst = tmp_path / "plans" / "archive" / "2026-03" / f"plan-{i}.md"
            candidates.append(self._candidate(src, dst))

        result = archive_plans(candidates, dry_run=False)
        assert result.moved == 3


# ---------------------------------------------------------------------------
# TestComputeSprawl
# ---------------------------------------------------------------------------

class TestComputeSprawl:
    def test_clean(self):
        entries = [_entry(date="2099-01-01") for _ in range(10)]
        sprawl = compute_sprawl(entries)
        assert sprawl.sprawl_level == "clean"
        assert sprawl.total_active == 10

    def test_growing(self):
        entries = [_entry(slug=f"p-{i}", date="2099-01-01") for i in range(30)]
        sprawl = compute_sprawl(entries)
        assert sprawl.sprawl_level == "growing"

    def test_sprawling(self):
        entries = [_entry(slug=f"p-{i}", date="2099-01-01") for i in range(70)]
        sprawl = compute_sprawl(entries)
        assert sprawl.sprawl_level == "sprawling"

    def test_critical(self):
        entries = [_entry(slug=f"p-{i}", date="2099-01-01") for i in range(120)]
        sprawl = compute_sprawl(entries)
        assert sprawl.sprawl_level == "critical"

    def test_archived_excluded_from_active(self):
        entries = [
            _entry(slug="active", date="2099-01-01"),
            _entry(slug="archived", status="archived"),
        ]
        sprawl = compute_sprawl(entries)
        assert sprawl.total_active == 1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestAgeDays:
    def test_same_day(self):
        assert _age_days("2026-03-06", "2026-03-06") == 0

    def test_one_week(self):
        assert _age_days("2026-02-27", "2026-03-06") == 7

    def test_invalid_date(self):
        assert _age_days("bad", "2026-03-06") is None


class TestFindPlansAncestor:
    def test_finds_plans_dir(self, tmp_path):
        plans = tmp_path / "project" / ".claude" / "plans"
        plans.mkdir(parents=True)
        f = plans / "some-plan.md"
        assert _find_plans_ancestor(f) == plans

    def test_fallback_to_parent(self, tmp_path):
        f = tmp_path / "random" / "file.md"
        assert _find_plans_ancestor(f) == tmp_path / "random"
