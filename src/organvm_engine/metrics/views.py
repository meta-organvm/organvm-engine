"""Consumer-specific view projections from SystemOrganism.

Each function is a pure transform: SystemOrganism -> dict.
No consumer should compute metrics directly — all derive from these views.
"""

from __future__ import annotations

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
