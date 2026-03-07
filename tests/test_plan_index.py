"""Tests for plans/index.py — PlanEntry, PlanIndex, build_plan_index."""

from __future__ import annotations

from pathlib import Path

import pytest

from organvm_engine.plans.index import (
    PlanEntry,
    _build_entry_from_plan,
    _domain_fingerprint,
    build_plan_index,
    index_to_json,
    render_index_table,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan_file(tmp_path, slug="test-plan", date="2026-01-15",
                    agent="claude", organ="III", repo="my-repo",
                    content="# Test Plan\n\n- [ ] Task 1\n- [x] Task 2\n"):
    """Create a plan file on disk and return a PlanFile-like object."""
    plan_dir = tmp_path / "organvm-iii-ergon" / repo / ".claude" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{date}-{slug}.md"
    plan_path.write_text(content)

    class FakePlanFile:
        def __init__(self):
            self.path = plan_path
            self.project = str(plan_dir.parent.parent)
            self.slug = slug
            self.date = date
            self.title = "Test Plan"
            self.size_bytes = len(content)
            self.has_verification = False
            self.status = "active"
            self.agent = agent
            self.organ = organ
            self.repo = repo
            self.version = 1
            self.location_tier = "project"

        @property
        def qualified_id(self):
            return f"{self.agent}:{self.organ or '?'}:{self.repo or '?'}:{self.slug}"

    return FakePlanFile()


# ---------------------------------------------------------------------------
# _domain_fingerprint
# ---------------------------------------------------------------------------

class TestDomainFingerprint:
    def test_empty_inputs(self):
        fp = _domain_fingerprint([], [])
        assert isinstance(fp, str)
        assert len(fp) == 16

    def test_same_inputs_same_hash(self):
        fp1 = _domain_fingerprint(["python", "pytest"], ["src/foo.py"])
        fp2 = _domain_fingerprint(["python", "pytest"], ["src/foo.py"])
        assert fp1 == fp2

    def test_different_inputs_different_hash(self):
        fp1 = _domain_fingerprint(["python"], ["src/foo.py"])
        fp2 = _domain_fingerprint(["rust"], ["src/bar.rs"])
        assert fp1 != fp2

    def test_order_independent(self):
        fp1 = _domain_fingerprint(["pytest", "python"], ["b.py", "a.py"])
        fp2 = _domain_fingerprint(["python", "pytest"], ["a.py", "b.py"])
        assert fp1 == fp2

    def test_case_normalized(self):
        fp1 = _domain_fingerprint(["Python"], [])
        fp2 = _domain_fingerprint(["python"], [])
        assert fp1 == fp2


# ---------------------------------------------------------------------------
# _build_entry_from_plan
# ---------------------------------------------------------------------------

class TestBuildEntry:
    def test_basic_entry(self, tmp_path):
        pf = _make_plan_file(tmp_path)
        entry = _build_entry_from_plan(pf, tmp_path)
        assert isinstance(entry, PlanEntry)
        assert entry.qualified_id == "claude:III:my-repo:test-plan"
        assert entry.agent == "claude"
        assert entry.organ == "III"
        assert entry.slug == "test-plan"
        assert entry.status == "active"
        assert entry.task_count >= 0

    def test_entry_with_verification(self, tmp_path):
        content = "# Plan\n\n## Verification\n\n- Check X\n"
        pf = _make_plan_file(tmp_path, content=content)
        entry = _build_entry_from_plan(pf, tmp_path)
        assert entry.archetype is not None

    def test_entry_with_file_refs(self, tmp_path):
        content = "# Plan\n\n- [ ] Edit `src/foo.py`\n- [ ] Create `src/bar.py`\n"
        pf = _make_plan_file(tmp_path, content=content)
        entry = _build_entry_from_plan(pf, tmp_path)
        assert isinstance(entry.file_refs, list)
        assert isinstance(entry.domain_fingerprint, str)

    def test_missing_file(self, tmp_path):
        pf = _make_plan_file(tmp_path)
        pf.path.unlink()
        entry = _build_entry_from_plan(pf, tmp_path)
        assert entry.task_count == 0
        assert entry.tags == []


# ---------------------------------------------------------------------------
# PlanEntry serialization
# ---------------------------------------------------------------------------

class TestPlanEntrySerialization:
    def test_asdict(self, tmp_path):
        from dataclasses import asdict

        pf = _make_plan_file(tmp_path)
        entry = _build_entry_from_plan(pf, tmp_path)
        d = asdict(entry)
        assert "qualified_id" in d
        assert "domain_fingerprint" in d
        assert isinstance(d["tags"], list)


# ---------------------------------------------------------------------------
# build_plan_index
# ---------------------------------------------------------------------------

class TestBuildPlanIndex:
    def test_empty_workspace(self, tmp_path):
        index = build_plan_index(workspace=tmp_path)
        assert index.total_plans == 0
        assert index.entries == []
        assert index.stale_candidates == []

    def test_with_plans(self, tmp_path):
        # Create plan files in workspace structure
        plan_dir = tmp_path / "organvm-iii-ergon" / "my-repo" / ".claude" / "plans"
        plan_dir.mkdir(parents=True)
        (plan_dir / "2026-01-15-feature-x.md").write_text(
            "# Feature X\n\n- [ ] Task 1\n"
        )
        (plan_dir / "2026-01-20-feature-y.md").write_text(
            "# Feature Y\n\n- [x] Done\n"
        )

        index = build_plan_index(workspace=tmp_path)
        assert index.total_plans == 2
        assert len(index.entries) == 2

    def test_stale_detection(self, tmp_path):
        plan_dir = tmp_path / "organvm-iii-ergon" / "my-repo" / ".claude" / "plans"
        plan_dir.mkdir(parents=True)
        # Very old plan with no completed tasks
        (plan_dir / "2025-01-01-old-plan.md").write_text(
            "# Old Plan\n\n- [ ] Never started\n"
        )

        index = build_plan_index(workspace=tmp_path, stale_days=30)
        assert len(index.stale_candidates) >= 1


# ---------------------------------------------------------------------------
# index_to_json
# ---------------------------------------------------------------------------

class TestIndexToJson:
    def test_valid_json(self, tmp_path):
        import json

        index = build_plan_index(workspace=tmp_path)
        result = index_to_json(index)
        parsed = json.loads(result)
        assert "generated" in parsed
        assert "total_plans" in parsed
        assert "entries" in parsed
        assert isinstance(parsed["entries"], list)


# ---------------------------------------------------------------------------
# render_index_table
# ---------------------------------------------------------------------------

class TestRenderIndexTable:
    def test_empty_index(self, tmp_path):
        index = build_plan_index(workspace=tmp_path)
        output = render_index_table(index)
        assert "0 plans" in output

    def test_with_data(self, tmp_path):
        plan_dir = tmp_path / "organvm-iii-ergon" / "test-repo" / ".claude" / "plans"
        plan_dir.mkdir(parents=True)
        (plan_dir / "2026-03-01-my-plan.md").write_text("# My Plan\n- [ ] A\n")

        index = build_plan_index(workspace=tmp_path)
        output = render_index_table(index)
        assert "Plan Index" in output
        assert "1 plans" in output
