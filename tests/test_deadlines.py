"""Tests for the deadline parser module."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from organvm_engine.deadlines.parser import (
    Deadline,
    parse_deadlines,
    filter_upcoming,
    format_deadlines,
    _parse_month_day,
    _parse_approx_month,
)


@pytest.fixture
def todo_dir(tmp_path):
    """Create a corpus dir with a rolling-todo.md containing various deadline patterns."""
    ops_dir = tmp_path / "docs" / "operations"
    ops_dir.mkdir(parents=True)

    # Use dates relative to "today" for reliable testing
    today = date.today()
    soon = today + timedelta(days=5)
    later = today + timedelta(days=45)
    past = today - timedelta(days=10)

    # Format month names
    def fmt(d):
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months[d.month - 1]} {d.day}"

    content = f"""# Rolling TODO

## NEEDS TIME

- [ ] **F4.** Submit NEH Summer Programs — **deadline {fmt(soon)}** (~2 hrs)
  - Source: funding-strategy

- [ ] **F5.** Submit Creative Capital — **deadline {fmt(later)}, 3pm ET** (~4 hrs)
  - HIGHEST-FIT TARGET

- [ ] **F7.** Submit Rauschenberg — **opens {fmt(soon)}, closes {fmt(later)}** (~1 hr)

- [ ] **F18.** Submit Whiting Grant — **~{date(today.year, later.month, 1).strftime('%b')} {today.year}** (~4 hrs)

- [x] **E5.** Completed task — **deadline {fmt(soon)}** — done already

- [ ] **F99.** No deadline here — just a regular TODO item

- [ ] **F6.** Past deadline — **deadline {fmt(past)}** (~2 hrs)
"""
    (ops_dir / "rolling-todo.md").write_text(content)
    return tmp_path


class TestParseMonthDay:
    def test_valid_date(self):
        result = _parse_month_day("Mar", "6", 2026)
        assert result == date(2026, 3, 6)

    def test_full_month_name(self):
        result = _parse_month_day("March", "6", 2026)
        assert result == date(2026, 3, 6)

    def test_invalid_month(self):
        assert _parse_month_day("Xyz", "6") is None

    def test_case_insensitive(self):
        result = _parse_month_day("APR", "15", 2026)
        assert result == date(2026, 4, 15)


class TestParseApproxMonth:
    def test_single_month(self):
        result = _parse_approx_month("Apr", 2026)
        assert result == date(2026, 4, 15)

    def test_range(self):
        result = _parse_approx_month("Apr-May", 2026)
        assert result == date(2026, 5, 15)

    def test_invalid(self):
        assert _parse_approx_month("Xyz") is None


class TestParseDeadlines:
    def test_finds_deadlines(self, todo_dir):
        deadlines = parse_deadlines(corpus_dir=todo_dir)
        # Should find F4, F5, F6, F7, F18 but NOT E5 (completed) or F99 (no deadline)
        ids = {d.item_id for d in deadlines}
        assert "F4" in ids
        assert "F5" in ids
        assert "E5" not in ids  # completed
        assert "F99" not in ids  # no deadline

    def test_sorted_by_date(self, todo_dir):
        deadlines = parse_deadlines(corpus_dir=todo_dir)
        dates = [d.deadline_date for d in deadlines]
        assert dates == sorted(dates)

    def test_approximate_flag(self, todo_dir):
        deadlines = parse_deadlines(corpus_dir=todo_dir)
        f18 = next((d for d in deadlines if d.item_id == "F18"), None)
        assert f18 is not None
        assert f18.approximate is True

    def test_nonexistent_dir(self, tmp_path):
        deadlines = parse_deadlines(corpus_dir=tmp_path / "nope")
        assert deadlines == []

    def test_missing_todo(self, tmp_path):
        (tmp_path / "docs" / "operations").mkdir(parents=True)
        deadlines = parse_deadlines(corpus_dir=tmp_path)
        assert deadlines == []


class TestFilterUpcoming:
    def test_filters_by_days(self, todo_dir):
        deadlines = parse_deadlines(corpus_dir=todo_dir)
        filtered = filter_upcoming(deadlines, days=10)
        # Only items within 10 days
        for d in filtered:
            assert d.days_remaining <= 10

    def test_includes_past(self, todo_dir):
        deadlines = parse_deadlines(corpus_dir=todo_dir)
        filtered = filter_upcoming(deadlines, days=0)
        # Past and today's items
        for d in filtered:
            assert d.days_remaining <= 0


class TestDeadline:
    def test_days_remaining(self):
        d = Deadline(
            item_id="F1",
            description="Test",
            deadline_date=date.today() + timedelta(days=5),
        )
        assert d.days_remaining == 5

    def test_urgency_this_week(self):
        d = Deadline(
            item_id="F1",
            description="Test",
            deadline_date=date.today() + timedelta(days=3),
        )
        assert d.urgency == "THIS WEEK"

    def test_urgency_overdue(self):
        d = Deadline(
            item_id="F1",
            description="Test",
            deadline_date=date.today() - timedelta(days=1),
        )
        assert d.urgency == "OVERDUE"

    def test_urgency_later(self):
        d = Deadline(
            item_id="F1",
            description="Test",
            deadline_date=date.today() + timedelta(days=60),
        )
        assert d.urgency == "LATER"


class TestFormatDeadlines:
    def test_empty_list(self):
        result = format_deadlines([])
        assert "No upcoming" in result

    def test_formats_output(self, todo_dir):
        deadlines = parse_deadlines(corpus_dir=todo_dir)
        output = format_deadlines(deadlines)
        assert "ID" in output
        assert "Date" in output
