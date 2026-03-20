"""CLI commands for network testament — external mirror mapping and engagement.

Subcommands:
    organvm network scan [--organ X] [--repo X] [--dry-run]
    organvm network map [--organ X] [--repo X] [--json]
    organvm network log <repo> <project> --action <type> --detail "..."
    organvm network status [--organ X] [--json]
    organvm network synthesize [--period weekly|monthly] [--write]
    organvm network suggest [--organ X] [--repo X]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from organvm_engine.network import ENGAGEMENT_FORMS, MIRROR_LENSES


def _workspace_root(args: argparse.Namespace) -> Path:
    from organvm_engine.paths import workspace_root

    ws = getattr(args, "workspace", None)
    return Path(ws) if ws else workspace_root()


def cmd_network_scan(args: argparse.Namespace) -> int:
    """Scan repos for potential mirrors and suggest additions."""
    from organvm_engine.network.scanner import scan_repo_dependencies

    workspace = _workspace_root(args)
    repo_filter = getattr(args, "repo", None)
    dry_run = not getattr(args, "write", False)

    # Walk workspace looking for repos
    scanned = 0
    total_mirrors = 0

    for organ_dir in sorted(workspace.iterdir()):
        if not organ_dir.is_dir() or organ_dir.name.startswith("."):
            continue
        organ_name = getattr(args, "organ", None)
        if organ_name and organ_dir.name != organ_name:
            continue

        for repo_dir in sorted(organ_dir.iterdir()):
            if not repo_dir.is_dir() or repo_dir.name.startswith("."):
                continue
            if repo_filter and repo_dir.name != repo_filter:
                continue

            mirrors = scan_repo_dependencies(repo_dir)
            if mirrors:
                scanned += 1
                total_mirrors += len(mirrors)
                print(f"\n{organ_dir.name}/{repo_dir.name}: {len(mirrors)} technical mirrors")
                for m in mirrors:
                    print(f"  - {m.project} ({m.relevance})")

    if dry_run:
        print(f"\n[dry-run] Scanned repos with findings: {scanned}, mirrors: {total_mirrors}")
        print("Run with --write to update network-map.yaml files")
    return 0


def cmd_network_map(args: argparse.Namespace) -> int:
    """Show the network map for a repo or organ."""
    from organvm_engine.network.mapper import discover_network_maps

    workspace = _workspace_root(args)
    repo_filter = getattr(args, "repo", None)
    as_json = getattr(args, "json", False)

    pairs = discover_network_maps(workspace)

    if repo_filter:
        pairs = [(p, m) for p, m in pairs if m.repo == repo_filter]

    if not pairs:
        print("No network maps found.")
        return 0

    if as_json:
        data = [m.to_dict() for _, m in pairs]
        print(json.dumps(data, indent=2))
    else:
        for path, nmap in pairs:
            print(f"\n{nmap.organ}/{nmap.repo} ({nmap.mirror_count} mirrors)")
            for lens in ("technical", "parallel", "kinship"):
                entries = nmap.mirrors_by_lens(lens)
                if entries:
                    print(f"  {lens}:")
                    for e in entries:
                        print(f"    - {e.project} [{e.platform}] — {e.relevance}")

    return 0


def cmd_network_log(args: argparse.Namespace) -> int:
    """Record an engagement action to the ledger."""
    from organvm_engine.network.ledger import create_engagement, log_engagement

    repo = args.repo
    project = args.project
    lens = args.lens
    action_type = args.action
    detail = args.detail
    url = getattr(args, "url", None)
    outcome = getattr(args, "outcome", None)
    tags_raw = getattr(args, "tags", None)
    tags = tags_raw.split(",") if tags_raw else []

    if lens not in MIRROR_LENSES:
        print(f"Invalid lens: {lens}. Must be one of: {', '.join(sorted(MIRROR_LENSES))}")
        return 1
    if action_type not in ENGAGEMENT_FORMS:
        print(
            f"Invalid action: {action_type}. Must be one of: {', '.join(sorted(ENGAGEMENT_FORMS))}"
        )
        return 1

    entry = create_engagement(
        organvm_repo=repo,
        external_project=project,
        lens=lens,
        action_type=action_type,
        action_detail=detail,
        url=url,
        outcome=outcome,
        tags=tags,
    )
    log_engagement(entry)
    print(f"Logged: {action_type} on {project} (lens={lens})")
    print(f"  Detail: {detail}")
    if url:
        print(f"  URL: {url}")
    return 0


def cmd_network_status(args: argparse.Namespace) -> int:
    """Show network health: coverage, density, velocity."""
    from organvm_engine.network.ledger import ledger_summary
    from organvm_engine.network.mapper import discover_network_maps
    from organvm_engine.network.metrics import (
        convergence_points,
        mirror_coverage,
        network_density,
    )

    workspace = _workspace_root(args)
    as_json = getattr(args, "json", False)

    pairs = discover_network_maps(workspace)
    maps = [m for _, m in pairs]
    summary = ledger_summary()
    density = network_density(maps, 59)  # TODO: compute from registry
    coverage = mirror_coverage(maps)
    convergences = convergence_points(maps)

    if as_json:
        print(json.dumps({
            "density": density,
            "coverage": coverage,
            "maps_count": len(maps),
            "total_mirrors": sum(m.mirror_count for m in maps),
            "ledger": summary,
            "convergence_points": len(convergences),
        }, indent=2))
    else:
        print("Network Testament Status")
        print(f"  Maps: {len(maps)} repos with network-map.yaml")
        print(f"  Mirrors: {sum(m.mirror_count for m in maps)} total")
        print(f"  Density: {density:.1%}")
        print(f"  Coverage — technical: {coverage['technical']:.0%}"
              f" | parallel: {coverage['parallel']:.0%}"
              f" | kinship: {coverage['kinship']:.0%}")
        print(f"  Convergence points: {len(convergences)}")
        print(f"  Ledger: {summary['total_actions']} actions"
              f" across {summary['unique_projects']} projects")

    return 0


def cmd_network_synthesize(args: argparse.Namespace) -> int:
    """Generate narrative testament."""
    from organvm_engine.network.synthesizer import synthesize_testament, write_testament

    workspace = _workspace_root(args)
    period = getattr(args, "period", "monthly")
    write = getattr(args, "write", False)

    content = synthesize_testament(workspace, period=period, total_active_repos=59)
    print(content)

    if write:
        testament_dir = workspace / "meta-organvm" / "praxis-perpetua" / "testament"
        out = write_testament(content, testament_dir, period)
        print(f"\nWritten to: {out}")

    return 0


def cmd_network_suggest(args: argparse.Namespace) -> int:
    """AI-informed suggestions for next engagement actions."""
    # Stub — will be enriched with AI suggestions via MCP/LLM
    from organvm_engine.network.mapper import discover_network_maps
    from organvm_engine.network.metrics import convergence_points

    workspace = _workspace_root(args)
    pairs = discover_network_maps(workspace)
    maps = [m for _, m in pairs]

    convergences = convergence_points(maps)
    if convergences:
        print("High-value convergence points (mirrored by multiple repos):")
        for project, repos in sorted(convergences.items(), key=lambda x: -len(x[1])):
            print(f"  {project} ← {', '.join(repos)}")
        print("\nConsider deepening engagement with these projects first.")
    else:
        print("No convergence points found yet. Run `organvm network scan` to populate maps.")

    return 0
