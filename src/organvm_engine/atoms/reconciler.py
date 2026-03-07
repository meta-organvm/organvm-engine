"""Git-based task status reconciliation.

Cross-references atomized tasks against git commit history to detect
which planned tasks were actually implemented.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.organ_config import ORGANS


@dataclass
class TaskVerdict:
    task_id: str
    old_status: str
    verdict: str  # likely_completed | partially_done | stale | unknown
    files_checked: int = 0
    files_with_commits: int = 0


@dataclass
class ReconcileResult:
    total_tasks: int = 0
    verdicts: list[TaskVerdict] = field(default_factory=list)
    likely_completed: int = 0
    partially_done: int = 0
    stale: int = 0
    unknown: int = 0


def _git_has_commits(repo_dir: Path, filepath: str, since: str | None = None) -> bool:
    """Check if a file has commits in the repo since a given date."""
    if not repo_dir.is_dir():
        return False
    cmd = ["git", "log", "--oneline", "-1", "--", filepath]
    if since:
        cmd.insert(3, f"--since={since}")
    try:
        result = subprocess.run(
            cmd, cwd=repo_dir, capture_output=True, text=True,
            timeout=10, check=False,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        return False


def _resolve_repo_dir(workspace: Path, organ: str | None, repo: str | None) -> Path | None:
    """Resolve the filesystem path to a repo directory."""
    if not organ or organ not in ORGANS:
        return None
    info = ORGANS[organ]
    organ_dir = workspace / info["dir"]
    if repo and repo not in ("_unattributed", "_global"):
        return organ_dir / repo
    return organ_dir


def reconcile_tasks(
    tasks_path: Path,
    workspace: Path,
    since: str | None = None,
) -> ReconcileResult:
    """Reconcile atomized tasks against git history.

    Args:
        tasks_path: Path to atomized-tasks.jsonl.
        workspace: Workspace root directory.
        since: Override git log --since (default: use each task's plan date).

    Returns:
        ReconcileResult with per-task verdicts.
    """
    result = ReconcileResult()

    if not tasks_path.exists():
        return result

    tasks: list[dict] = []
    with tasks_path.open(encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if stripped:
                tasks.append(json.loads(stripped))

    result.total_tasks = len(tasks)

    for task in tasks:
        task_id = task.get("id", "")
        old_status = task.get("status", "pending")
        files_touched = task.get("files_touched", [])
        project = task.get("project", {})
        organ = project.get("organ")
        repo = project.get("repo")

        # Can't reconcile without file paths
        if not files_touched:
            v = TaskVerdict(
                task_id=task_id, old_status=old_status, verdict="unknown",
            )
            result.verdicts.append(v)
            result.unknown += 1
            continue

        repo_dir = _resolve_repo_dir(workspace, organ, repo)
        if not repo_dir or not repo_dir.is_dir():
            v = TaskVerdict(
                task_id=task_id, old_status=old_status, verdict="unknown",
            )
            result.verdicts.append(v)
            result.unknown += 1
            continue

        # Use plan date as since if not overridden
        task_since = since or task.get("source", {}).get("plan_date")

        files_checked = 0
        files_with_commits = 0

        for ft in files_touched:
            filepath = ft.get("path", ft) if isinstance(ft, dict) else str(ft)
            if not filepath:
                continue
            files_checked += 1
            if _git_has_commits(repo_dir, filepath, since=task_since):
                files_with_commits += 1

        if files_checked == 0:
            verdict = "unknown"
        elif files_with_commits == files_checked:
            verdict = "likely_completed"
        elif files_with_commits > 0:
            verdict = "partially_done"
        else:
            # No commits on any file — check if files exist
            any_exists = any(
                (repo_dir / (ft.get("path", ft) if isinstance(ft, dict) else str(ft))).exists()
                for ft in files_touched
                if (ft.get("path", ft) if isinstance(ft, dict) else str(ft))
            )
            verdict = "stale" if not any_exists else "unknown"

        v = TaskVerdict(
            task_id=task_id,
            old_status=old_status,
            verdict=verdict,
            files_checked=files_checked,
            files_with_commits=files_with_commits,
        )
        result.verdicts.append(v)

        if verdict == "likely_completed":
            result.likely_completed += 1
        elif verdict == "partially_done":
            result.partially_done += 1
        elif verdict == "stale":
            result.stale += 1
        else:
            result.unknown += 1

    return result


def apply_verdicts(tasks_path: Path, verdicts: list[TaskVerdict]) -> int:
    """Rewrite tasks JSONL with updated statuses from reconciliation.

    Returns count of tasks updated.
    """
    verdict_map = {v.task_id: v.verdict for v in verdicts}

    tasks: list[dict] = []
    with tasks_path.open(encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if stripped:
                tasks.append(json.loads(stripped))

    updated = 0
    for task in tasks:
        tid = task.get("id", "")
        verdict = verdict_map.get(tid)
        if verdict and verdict != "unknown":
            task["reconciled_status"] = verdict
            if verdict == "likely_completed":
                task["status"] = "completed"
                updated += 1

    with tasks_path.open("w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")

    return updated
