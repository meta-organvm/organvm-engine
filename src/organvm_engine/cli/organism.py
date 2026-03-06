"""CLI handler for the organism command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from organvm_engine.metrics.organism import compute_organism
from organvm_engine.metrics.views import project_organism_cli
from organvm_engine.registry.loader import load_registry
from organvm_engine.registry.query import resolve_organ_key


def cmd_organism(args) -> int:
    """Display the system organism at any zoom level."""
    registry = load_registry(args.registry)

    workspace = getattr(args, "workspace", None)
    if workspace:
        workspace = Path(workspace).expanduser().resolve()
    else:
        import os
        env = os.environ.get("ORGANVM_WORKSPACE_DIR")
        if env:
            workspace = Path(env).expanduser().resolve()
        else:
            default = Path.home() / "Workspace"
            workspace = default if default.is_dir() else None

    include_omega = getattr(args, "omega", False)
    organism = compute_organism(
        registry, workspace=workspace, include_omega=include_omega,
    )

    organ = getattr(args, "organ", None)
    if organ:
        organ = resolve_organ_key(organ)
    repo = getattr(args, "repo", None)
    use_json = getattr(args, "json", False)

    result = project_organism_cli(organism, organ=organ, repo=repo)

    if use_json:
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    # Human-readable summary
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1

    if repo and "repo" in result:
        _print_repo(result)
    elif organ and "organ_id" in result:
        _print_organ(result)
    else:
        _print_system(result)
    return 0


def _print_system(d: dict) -> None:
    print(f"System: {d['total_repos']} repos, "
          f"{d['sys_pct']}% avg gate completion")
    print(f"  Promo-ready: {d['total_promo_ready']}  "
          f"Stale: {d['total_stale']}")
    print()
    for o in d.get("organs", []):
        print(f"  {o['organ_id']:<16} {o['count']:>3} repos  "
              f"{o['avg_pct']:>3}% avg  "
              f"{o['promo_ready']} ready")


def _print_organ(d: dict) -> None:
    print(f"{d['organ_id']} ({d['organ_name']}): "
          f"{d['count']} repos, {d['avg_pct']}% avg")
    print()
    for r in d.get("repos", []):
        marker = "+" if r.get("promo_ready") else " "
        print(f"  {marker} {r['repo']:<45} {r['pct']:>3}% "
              f"({r['score']}/{r['total']})")


def _print_repo(d: dict) -> None:
    print(f"{d['repo']} ({d['organ']})")
    print(f"  Profile: {d['profile']}  Tier: {d['tier']}  "
          f"Promo: {d['promo']}")
    print(f"  Score: {d['score']}/{d['total']} ({d['pct']}%)")
    print()
    for g in d.get("gates", []):
        if not g["applicable"]:
            continue
        marker = "pass" if g["passed"] else "FAIL"
        print(f"  [{marker:>4}] {g['name']:<10} {g['detail']}")
        if g.get("next_action"):
            print(f"           -> {g['next_action']}")


def cmd_organism_snapshot(args) -> int:
    """Write a system-organism.json snapshot to the corpus."""
    registry = load_registry(args.registry)

    workspace = getattr(args, "workspace", None)
    if workspace:
        workspace = Path(workspace).expanduser().resolve()
    else:
        import os
        env = os.environ.get("ORGANVM_WORKSPACE_DIR")
        if env:
            workspace = Path(env).expanduser().resolve()
        else:
            default = Path.home() / "Workspace"
            workspace = default if default.is_dir() else None

    include_omega = getattr(args, "omega", False)
    organism = compute_organism(
        registry, workspace=workspace, include_omega=include_omega,
    )

    data = organism.to_dict()
    dry_run = not getattr(args, "write", False)

    # Write to corpus data/organism/
    from organvm_engine.paths import corpus_dir

    out_dir = corpus_dir() / "data" / "organism"
    date_str = organism.generated[:10]
    out_path = out_dir / f"system-organism-{date_str}.json"

    print(f"\n  Organism Snapshot — {organism.total_repos} repos, "
          f"{organism.sys_pct}% avg")
    print(f"  {'─' * 50}")
    print(f"  Organs: {len(organism.organs)}")
    print(f"  Promo-ready: {organism.total_promo_ready}")
    print(f"  Stale: {organism.total_stale}")

    if dry_run:
        print(f"\n  [DRY RUN] Would write to {out_path}")
        print("  Re-run with --write to apply.")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as f:
            json.dump(data, f, indent=2, default=str)
            f.write("\n")
        print(f"\n  Snapshot written: {out_path}")

    return 0
