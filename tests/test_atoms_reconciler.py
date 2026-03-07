"""Tests for atoms/reconciler.py — git-based task status reconciliation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from organvm_engine.atoms.reconciler import (
    ReconcileResult,
    apply_verdicts,
    reconcile_tasks,
    TaskVerdict,
)


def _write_tasks(path: Path, tasks: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


class TestReconcileTasks:
    def test_no_files_touched_returns_unknown(self, tmp_path):
        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {"id": "t1", "status": "pending", "project": {"organ": "I", "repo": "eng"}},
        ])
        result = reconcile_tasks(tasks_path, tmp_path)
        assert result.total_tasks == 1
        assert result.unknown == 1
        assert result.verdicts[0].verdict == "unknown"

    @patch("organvm_engine.atoms.reconciler._git_has_commits")
    def test_file_has_commits_returns_completed(self, mock_git, tmp_path):
        mock_git.return_value = True

        # Create organ/repo dir
        repo_dir = tmp_path / "organvm-i-theoria" / "eng"
        repo_dir.mkdir(parents=True)

        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {
                "id": "t1", "status": "pending",
                "project": {"organ": "I", "repo": "eng"},
                "files_touched": [{"path": "src/main.py"}],
            },
        ])
        result = reconcile_tasks(tasks_path, tmp_path)
        assert result.likely_completed == 1
        assert result.verdicts[0].verdict == "likely_completed"

    @patch("organvm_engine.atoms.reconciler._git_has_commits")
    def test_file_missing_no_history_returns_stale(self, mock_git, tmp_path):
        mock_git.return_value = False

        repo_dir = tmp_path / "organvm-i-theoria" / "eng"
        repo_dir.mkdir(parents=True)

        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {
                "id": "t1", "status": "pending",
                "project": {"organ": "I", "repo": "eng"},
                "files_touched": [{"path": "nonexistent/file.py"}],
            },
        ])
        result = reconcile_tasks(tasks_path, tmp_path)
        assert result.stale == 1
        assert result.verdicts[0].verdict == "stale"

    @patch("organvm_engine.atoms.reconciler._git_has_commits")
    def test_partial_commits_returns_partially_done(self, mock_git, tmp_path):
        # First file has commits, second doesn't
        mock_git.side_effect = [True, False]

        repo_dir = tmp_path / "organvm-i-theoria" / "eng"
        repo_dir.mkdir(parents=True)
        # Create the second file so it's not "stale"
        (repo_dir / "src").mkdir()
        (repo_dir / "src" / "other.py").write_text("pass")

        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {
                "id": "t1", "status": "pending",
                "project": {"organ": "I", "repo": "eng"},
                "files_touched": [
                    {"path": "src/main.py"},
                    {"path": "src/other.py"},
                ],
            },
        ])
        result = reconcile_tasks(tasks_path, tmp_path)
        assert result.partially_done == 1
        assert result.verdicts[0].verdict == "partially_done"

    def test_missing_tasks_file(self, tmp_path):
        result = reconcile_tasks(tmp_path / "nope.jsonl", tmp_path)
        assert result.total_tasks == 0

    def test_unknown_organ(self, tmp_path):
        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {
                "id": "t1", "status": "pending",
                "project": {"organ": "_root", "repo": "_global"},
                "files_touched": [{"path": "src/main.py"}],
            },
        ])
        result = reconcile_tasks(tasks_path, tmp_path)
        assert result.unknown == 1


class TestApplyVerdicts:
    def test_dry_run_no_rewrite(self, tmp_path):
        """reconcile_tasks alone doesn't modify the file."""
        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {"id": "t1", "status": "pending", "project": {"organ": "I", "repo": "eng"}},
        ])
        original = tasks_path.read_text()
        reconcile_tasks(tasks_path, tmp_path)
        assert tasks_path.read_text() == original

    def test_write_updates_status(self, tmp_path):
        tasks_path = tmp_path / "tasks.jsonl"
        _write_tasks(tasks_path, [
            {"id": "t1", "status": "pending"},
            {"id": "t2", "status": "pending"},
        ])

        verdicts = [
            TaskVerdict(task_id="t1", old_status="pending", verdict="likely_completed"),
            TaskVerdict(task_id="t2", old_status="pending", verdict="unknown"),
        ]

        updated = apply_verdicts(tasks_path, verdicts)
        assert updated == 1

        # Verify file content
        with tasks_path.open() as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert lines[0]["status"] == "completed"
        assert lines[0]["reconciled_status"] == "likely_completed"
        assert lines[1]["status"] == "pending"  # unknown → no change
