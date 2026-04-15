"""Consumer-specific view projections from SystemOrganism.

Each function is a pure transform: SystemOrganism -> dict.
No consumer should compute metrics directly — all derive from these views.

The fabrica projection (project_fabrica_dashboard) is independent of
SystemOrganism — it reads directly from the fabrica store and heartbeat
logs. It lives here for consumer uniformity: all dashboard projections
import from this module.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from organvm_engine.metrics.organism import SystemOrganism


def project_progress_api(organism: SystemOrganism) -> dict:
    """Dashboard /progress/api shape.

    Returns:
        Dict with total, sys_pct, profiles, and projects list.
    """
    projects = [r.to_dict() for r in organism.all_repos]
    return {
        "total": organism.total_repos,
        "sys_pct": organism.sys_pct,
        "profiles": organism.profile_counts(),
        "projects": projects,
    }


def project_mcp_health(organism: SystemOrganism) -> dict:
    """MCP server system_health() shape.

    Returns:
        Dict matching the existing health.py:system_health() output.
    """
    repos = organism.all_repos
    total = organism.total_repos

    archived = sum(1 for r in repos if r.promo == "ARCHIVED")
    active = total - archived

    # Gate-based coverage
    ci_count = 0
    test_count = 0
    docs_count = 0
    for r in repos:
        for g in r.gates:
            if g.name == "CI" and g.applicable and g.passed:
                ci_count += 1
            elif g.name == "TESTS" and g.applicable and g.passed:
                test_count += 1
            elif g.name == "DOCS" and g.applicable and g.passed:
                docs_count += 1

    def ratio(count: int) -> float:
        return round(count / total, 4) if total else 0.0

    promo_dist = {
        "LOCAL": 0, "CANDIDATE": 0, "PUBLIC_PROCESS": 0,
        "GRADUATED": 0, "ARCHIVED": 0,
    }
    for r in repos:
        if r.promo in promo_dist:
            promo_dist[r.promo] += 1

    by_organ: dict[str, dict[str, int]] = {}
    for o in organism.organs:
        organ_archived = sum(
            1 for r in o.repos if r.promo == "ARCHIVED"
        )
        by_organ[o.organ_id] = {
            "total": o.count,
            "active": o.count - organ_archived,
            "archived": organ_archived,
        }

    return {
        "total_repos": total,
        "active_repos": active,
        "archived_repos": archived,
        "ci_coverage": ratio(ci_count),
        "test_coverage": ratio(test_count),
        "docs_coverage": ratio(docs_count),
        "promotion_distribution": promo_dist,
        "by_organ": by_organ,
        "generated": organism.generated,
    }


def project_system_metrics(organism: SystemOrganism) -> dict:
    """Legacy system-metrics.json computed section shape.

    Returns:
        Dict compatible with calculator.py:compute_metrics() output.
    """
    repos = organism.all_repos
    per_organ: dict[str, dict] = {}
    for o in organism.organs:
        per_organ[o.organ_id] = {
            "name": o.organ_name,
            "repos": o.count,
        }

    from collections import defaultdict
    status_dist: defaultdict[str, int] = defaultdict(int)
    ci_count = 0
    for r in repos:
        status_dist[r.impl] += 1
        for g in r.gates:
            if g.name == "CI" and g.applicable and g.passed:
                ci_count += 1

    return {
        "total_repos": organism.total_repos,
        "active_repos": status_dist.get("ACTIVE", 0),
        "archived_repos": status_dist.get("ARCHIVED", 0),
        "total_organs": len(organism.organs),
        "ci_workflows": ci_count,
        "per_organ": per_organ,
        "implementation_status": dict(sorted(status_dist.items())),
    }


def project_gate_stats(organism: SystemOrganism) -> dict:
    """Gate statistics with failing repos per gate.

    Returns:
        Dict with gates list, each having name, applicable, passed,
        failed, rate, and failing_repos.
    """
    repos = organism.all_repos
    from organvm_engine.metrics.gates import GATE_ORDER

    stats = []
    for g_name in GATE_ORDER:
        applicable_repos = []
        passed_repos = []
        for r in repos:
            gate = next(
                (x for x in r.gates if x.name == g_name), None,
            )
            if gate and gate.applicable:
                applicable_repos.append(r.repo)
                if gate.passed:
                    passed_repos.append(r.repo)
        failed_repos = [
            name for name in applicable_repos
            if name not in set(passed_repos)
        ]
        n_app = len(applicable_repos)
        n_pass = len(passed_repos)
        stats.append({
            "name": g_name,
            "applicable": n_app,
            "passed": n_pass,
            "failed": n_app - n_pass,
            "rate": int(n_pass / n_app * 100) if n_app else 0,
            "failing_repos": failed_repos,
        })
    return {"gates": stats}


def project_blockers(organism: SystemOrganism) -> dict:
    """Promotion readiness and blockers report.

    Returns:
        Dict with ready and blocked lists.
    """
    repos = organism.all_repos
    ready = []
    blocked = []
    for r in repos:
        if r.promo_ready and r.promo != "GRADUATED":
            ready.append({
                "repo": r.repo,
                "organ": r.organ,
                "promo": r.promo,
                "next": r.next_promo,
            })
        elif (
            not r.promo_ready
            and r.promo not in ("GRADUATED", "ARCHIVED")
        ):
            blocked.append({
                "repo": r.repo,
                "organ": r.organ,
                "promo": r.promo,
                "blockers": r.blockers,
                "next_actions": r.next_actions,
            })
    return {"ready": ready, "blocked": blocked}


def project_organism_cli(
    organism: SystemOrganism,
    organ: str | None = None,
    repo: str | None = None,
) -> dict:
    """CLI organism output — zoom to organ or repo level.

    Args:
        organism: Full system organism.
        organ: Optional organ filter.
        repo: Optional repo filter (requires organ or searches all).

    Returns:
        Dict at the appropriate zoom level.
    """
    if repo:
        rp = organism.find_repo(repo)
        if rp:
            return rp.to_dict()
        return {"error": f"Repo '{repo}' not found"}

    if organ:
        o = organism.find_organ(organ)
        if o:
            return o.to_dict()
        return {"error": f"Organ '{organ}' not found"}

    return organism.to_dict()


# ---------------------------------------------------------------------------
# Fabrica dashboard projection (SPEC-024 Phase 7)
# ---------------------------------------------------------------------------


def _format_age(seconds: float) -> str:
    """Format elapsed seconds as a human-readable age string."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    days = int(seconds / 86400)
    hours = int((seconds % 86400) / 3600)
    return f"{days}d {hours}h" if hours else f"{days}d"


def _load_latest_heartbeat() -> dict[str, Any] | None:
    """Read the latest heartbeat report from the fabrica logs directory.

    Returns None if no report exists or the file is unreadable.
    """
    from organvm_engine.fabrica.store import fabrica_dir

    report_path = fabrica_dir() / "logs" / "heartbeat-latest.json"
    if not report_path.is_file():
        return None
    try:
        return json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def project_fabrica_dashboard(
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Dashboard projection for the fabrica section.

    Aggregates fabrica state into a shape optimized for dashboard rendering:
    - Active relay cycles with phase, age, and dispatch count
    - Dispatch records with backend, status, target, and time since dispatch
    - Health summary (active/completed/failed/pending_review)
    - Last heartbeat timestamp and result

    Args:
        now: Current timestamp for age calculation. Defaults to time.time().
             Exposed for deterministic testing.

    Returns:
        Dict with cycles, health, and heartbeat sections.
    """
    from organvm_engine.fabrica.mcp_tools import fabrica_health, fabrica_status

    if now is None:
        now = time.time()

    # --- Relay cycles with computed fields ---
    raw_status = fabrica_status(limit=100)
    cycles: list[dict[str, Any]] = []
    for cycle in raw_status.get("cycles", []):
        age_seconds = now - cycle.get("timestamp", now)

        # Shape each dispatch record for display
        dispatch_rows: list[dict[str, Any]] = []
        for d in cycle.get("dispatches", []):
            dispatched_at = d.get("dispatched_at", 0)
            since_dispatch = now - dispatched_at if dispatched_at else 0

            dispatch_rows.append({
                "id": d.get("id", ""),
                "backend": d.get("backend", "unknown"),
                "status": d.get("status", "unknown"),
                "target": d.get("target", ""),
                "dispatched_at": dispatched_at,
                "time_since_dispatch": _format_age(since_dispatch),
                "pr_url": d.get("pr_url"),
                "verdict": d.get("verdict"),
            })

        cycles.append({
            "packet_id": cycle.get("packet_id", ""),
            "raw_text": cycle.get("raw_text", ""),
            "source": cycle.get("source", ""),
            "organ_hint": cycle.get("organ_hint"),
            "tags": cycle.get("tags", []),
            "current_phase": cycle.get("current_phase", "unknown"),
            "age": _format_age(age_seconds),
            "age_seconds": age_seconds,
            "dispatch_count": cycle.get("dispatch_count", 0),
            "vector_count": cycle.get("vector_count", 0),
            "transition_count": cycle.get("transition_count", 0),
            "dispatches": dispatch_rows,
        })

    # --- Health summary ---
    raw_health = fabrica_health()
    health_summary: dict[str, Any] = {
        "total_packets": raw_health.get("total_packets", 0),
        "total_dispatches": raw_health.get("total_dispatches", 0),
        "total_transitions": raw_health.get("total_transitions", 0),
        "by_phase": raw_health.get("by_phase", {}),
        "by_backend": raw_health.get("by_backend", {}),
        "active": raw_health.get("summary", {}).get("active", 0),
        "completed": raw_health.get("summary", {}).get("completed", 0),
        "failed": raw_health.get("summary", {}).get("failed", 0),
        "pending_review": raw_health.get("summary", {}).get("pending_review", 0),
    }

    # --- Last heartbeat ---
    heartbeat_report = _load_latest_heartbeat()
    heartbeat: dict[str, Any]
    if heartbeat_report:
        hb_ts = heartbeat_report.get("timestamp", 0)
        heartbeat = {
            "available": True,
            "timestamp": hb_ts,
            "timestamp_iso": datetime.fromtimestamp(
                hb_ts, tz=timezone.utc,
            ).isoformat() if hb_ts else None,
            "age": _format_age(now - hb_ts) if hb_ts else "unknown",
            "polled": heartbeat_report.get("polled", 0),
            "changed": heartbeat_report.get("changed", 0),
            "errors": heartbeat_report.get("errors", 0),
            "duration_seconds": heartbeat_report.get("duration_seconds", 0.0),
        }
    else:
        heartbeat = {
            "available": False,
            "timestamp": None,
            "timestamp_iso": None,
            "age": None,
            "polled": 0,
            "changed": 0,
            "errors": 0,
            "duration_seconds": 0.0,
        }

    return {
        "total_cycles": len(cycles),
        "cycles": cycles,
        "health": health_summary,
        "heartbeat": heartbeat,
        "generated": datetime.now(timezone.utc).isoformat(),
    }
