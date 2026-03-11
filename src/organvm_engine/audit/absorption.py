"""Layer 6: Absorption deposit scanning.

Scans known deposit locations (intake/, sessions, soak-test, .specstory/)
and reports sizes, file counts, and staleness. Stat-only — never reads
file contents.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from organvm_engine.audit.types import Finding, LayerReport, Severity

# Default deposit locations relative to workspace or home
_DEPOSIT_SPECS = [
    {
        "name": "intake",
        "relative_to": "workspace",
        "path": "intake",
        "description": "Unsorted inbound material",
    },
    {
        "name": "sessions",
        "relative_to": "home",
        "path": ".claude/projects",
        "description": "Claude session transcripts",
    },
    {
        "name": "soak-test",
        "relative_to": "corpus",
        "path": "data/soak-test",
        "description": "Soak test reports",
    },
]


def _scan_deposit(path: Path) -> dict:
    """Stat a deposit directory without reading file contents.

    Returns:
        Dict with keys: exists, file_count, total_bytes, newest_mtime, oldest_mtime.
    """
    result: dict = {
        "exists": False,
        "file_count": 0,
        "total_bytes": 0,
        "newest_mtime": 0.0,
        "oldest_mtime": float("inf"),
    }
    if not path.is_dir():
        return result

    result["exists"] = True
    try:
        for root, _dirs, files in os.walk(path):
            for fname in files:
                fpath = Path(root) / fname
                try:
                    st = fpath.stat()
                    result["file_count"] += 1
                    result["total_bytes"] += st.st_size
                    result["newest_mtime"] = max(result["newest_mtime"], st.st_mtime)
                    result["oldest_mtime"] = min(result["oldest_mtime"], st.st_mtime)
                except OSError:
                    continue
    except PermissionError:
        pass

    if result["file_count"] == 0:
        result["oldest_mtime"] = 0.0

    return result


def _format_bytes(n: int) -> str:
    """Format byte count as human-readable."""
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f}MB"
    return f"{n / (1024 * 1024 * 1024):.1f}GB"


def _days_since(timestamp: float) -> int:
    """Days since a unix timestamp."""
    if timestamp <= 0:
        return -1
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - dt).days


def audit_absorption(
    workspace: Path,
    corpus_dir: Path | None = None,
    verbose: bool = False,
) -> LayerReport:
    """Run absorption deposit audit.

    Args:
        workspace: Workspace root path.
        corpus_dir: Path to corpus directory. Derived from workspace if None.
        verbose: Include per-deposit detail findings.

    Returns:
        LayerReport with absorption findings.
    """
    report = LayerReport(layer="absorption")
    home = Path.home()

    if corpus_dir is None:
        corpus_dir = workspace / "meta-organvm" / "organvm-corpvs-testamentvm"

    deposits: list[dict] = []
    for spec in _DEPOSIT_SPECS:
        if spec["relative_to"] == "workspace":
            base = workspace
        elif spec["relative_to"] == "home":
            base = home
        elif spec["relative_to"] == "corpus":
            base = corpus_dir
        else:
            continue

        path = base / spec["path"]
        scan = _scan_deposit(path)
        scan["name"] = spec["name"]
        scan["description"] = spec["description"]
        scan["path"] = str(path)
        deposits.append(scan)

    # Scan .specstory/ directories across workspace
    specstory_count = 0
    specstory_repos: list[str] = []
    try:
        for organ_dir in sorted(workspace.iterdir()):
            if not organ_dir.is_dir() or organ_dir.name.startswith("."):
                continue
            for repo_dir in sorted(organ_dir.iterdir()):
                if not repo_dir.is_dir():
                    continue
                specstory = repo_dir / ".specstory"
                if specstory.is_dir():
                    specstory_count += 1
                    specstory_repos.append(f"{organ_dir.name}/{repo_dir.name}")
    except (PermissionError, OSError):
        pass

    if specstory_count > 0:
        deposits.append({
            "name": ".specstory",
            "description": f"SpecStory directories in {specstory_count} repos",
            "exists": True,
            "file_count": specstory_count,
            "total_bytes": 0,
            "newest_mtime": 0.0,
            "oldest_mtime": 0.0,
            "repos": specstory_repos,
        })

    # Generate findings
    total_bytes = 0
    total_files = 0
    for dep in deposits:
        if not dep["exists"]:
            if verbose:
                report.findings.append(Finding(
                    severity=Severity.INFO,
                    layer="absorption",
                    organ="SYSTEM",
                    repo="",
                    message=f"Deposit '{dep['name']}' not found at {dep['path']}",
                ))
            continue

        total_bytes += dep["total_bytes"]
        total_files += dep["file_count"]
        days = _days_since(dep.get("newest_mtime", 0))

        severity = Severity.INFO
        if dep["total_bytes"] > 100 * 1024 * 1024:  # > 100MB
            severity = Severity.WARNING

        msg = (
            f"{dep['name']}: {dep['file_count']} files, "
            f"{_format_bytes(dep['total_bytes'])}"
        )
        if days >= 0:
            msg += f", last modified {days}d ago"

        report.findings.append(Finding(
            severity=severity,
            layer="absorption",
            organ="SYSTEM",
            repo="",
            message=msg,
        ))

    # Summary
    report.findings.append(Finding(
        severity=Severity.INFO,
        layer="absorption",
        organ="SYSTEM",
        repo="",
        message=(
            f"Total deposits: {_format_bytes(total_bytes)} across "
            f"{total_files} files in {len([d for d in deposits if d['exists']])} "
            f"locations"
        ),
        suggestion="Run `alchemia intake` to triage unabsorbed material"
        if total_bytes > 50 * 1024 * 1024
        else "",
    ))

    return report
