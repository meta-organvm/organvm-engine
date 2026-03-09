"""CLI handler for the ecosystem command group."""

from __future__ import annotations

import json
import sys

from organvm_engine.paths import resolve_workspace


def cmd_ecosystem_show(args) -> int:
    """Display the full ecosystem profile for a repo."""
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.reader import get_pillars, read_ecosystem

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    ecosystems = discover_ecosystems(workspace)
    for eco_path in ecosystems:
        try:
            data = read_ecosystem(eco_path)
        except Exception:
            continue
        if data.get("repo") == args.repo or eco_path.parent.name == args.repo:
            if getattr(args, "json", False):
                json.dump(data, sys.stdout, indent=2, default=str)
                sys.stdout.write("\n")
            else:
                _print_ecosystem(data)
            return 0

    print(f"No ecosystem.yaml found for '{args.repo}'")
    return 1


def cmd_ecosystem_list(args) -> int:
    """List products with/without ecosystem profiles."""
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.reader import get_pillars, read_ecosystem
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.query import all_repos

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    registry = load_registry(args.registry)

    existing = discover_ecosystems(workspace, organ=organ)
    existing_repos: set[str] = set()
    for eco_path in existing:
        try:
            data = read_ecosystem(eco_path)
            existing_repos.add(data.get("repo", eco_path.parent.name))
        except Exception:
            existing_repos.add(eco_path.parent.name)

    # Resolve organ filter to registry key
    filter_key = None
    if organ:
        from organvm_engine.organ_config import organ_aliases
        aliases = organ_aliases()
        filter_key = aliases.get(organ)

    print(f"{'Repo':<50} {'Ecosystem':<12} {'Organ'}")
    print(f"{'─' * 50} {'─' * 12} {'─' * 15}")
    for organ_key, repo_data in all_repos(registry):
        if filter_key and organ_key != filter_key:
            continue
        name = repo_data.get("name", "")
        tier = repo_data.get("tier", "standard")
        if tier in ("archive", "infrastructure"):
            continue
        has = "yes" if name in existing_repos else "no"
        print(f"{name:<50} {has:<12} {organ_key}")

    return 0


def cmd_ecosystem_coverage(args) -> int:
    """Display Product x Pillar coverage matrix."""
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.query import coverage_matrix
    from organvm_engine.ecosystem.reader import read_ecosystem

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    ecosystems_data = _load_all(workspace, organ)

    if not ecosystems_data:
        print("No ecosystem profiles found.")
        return 0

    matrix = coverage_matrix(ecosystems_data)

    if getattr(args, "json", False):
        json.dump(matrix, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    # Collect all pillar names
    all_pillars: set[str] = set()
    for repo_data in matrix.values():
        all_pillars.update(repo_data.keys())
    pillars = sorted(all_pillars)

    # Header
    header = f"{'Repo':<40}"
    for p in pillars:
        header += f" {p[:8]:>8}"
    print(header)
    print("─" * len(header))

    for repo, coverage in sorted(matrix.items()):
        row = f"{repo:<40}"
        for p in pillars:
            if p in coverage:
                total = coverage[p].get("total", 0)
                live = coverage[p].get("live", 0)
                row += f" {live}/{total:>5}"
            else:
                row += f" {'—':>8}"
        print(row)

    return 0


def cmd_ecosystem_audit(args) -> int:
    """Show gaps and suggestions for ecosystem profiles."""
    from organvm_engine.ecosystem.query import gaps

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    ecosystems_data = _load_all(workspace, organ)

    if not ecosystems_data:
        print("No ecosystem profiles found.")
        return 0

    for eco in ecosystems_data:
        repo = eco.get("repo", "unknown")
        gap_list = gaps(eco)
        if gap_list:
            print(f"\n{repo}:")
            for g in gap_list:
                print(f"  - {g}")

    return 0


def cmd_ecosystem_scaffold(args) -> int:
    """Generate a scaffold for a single repo."""
    import yaml

    from organvm_engine.ecosystem.templates import scaffold_ecosystem
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.registry.query import find_repo
    from organvm_engine.seed.reader import read_seed

    registry = load_registry(args.registry)
    found = find_repo(registry, args.repo)
    if found is None:
        print(f"Repository '{args.repo}' not found in registry")
        return 1

    organ_key, repo_data = found
    workspace = resolve_workspace(args)

    # Try to load seed
    seed = None
    if workspace:
        from organvm_engine.organ_config import registry_key_to_dir
        rk2d = registry_key_to_dir()
        organ_dir = rk2d.get(organ_key)
        if organ_dir:
            seed_path = workspace / organ_dir / args.repo / "seed.yaml"
            if seed_path.is_file():
                try:
                    seed = read_seed(seed_path)
                except Exception:
                    pass

    from organvm_engine.ecosystem.sync import _organ_key_to_short
    organ_short = _organ_key_to_short(organ_key)

    eco = scaffold_ecosystem(
        repo_name=args.repo,
        organ=organ_short,
        registry_data=repo_data,
        seed_data=seed,
        display_name=repo_data.get("description"),
    )

    output = yaml.dump(eco, default_flow_style=False, sort_keys=False)
    print(output)

    if not getattr(args, "dry_run", True):
        if workspace:
            from organvm_engine.organ_config import registry_key_to_dir
            rk2d = registry_key_to_dir()
            organ_dir = rk2d.get(organ_key)
            if organ_dir:
                eco_path = workspace / organ_dir / args.repo / "ecosystem.yaml"
                with eco_path.open("w") as f:
                    yaml.dump(eco, f, default_flow_style=False, sort_keys=False)
                print(f"Written: {eco_path}")

    return 0


def cmd_ecosystem_sync(args) -> int:
    """Scaffold ecosystem.yaml for all products missing one."""
    from organvm_engine.ecosystem.sync import sync_ecosystems

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    dry_run = not getattr(args, "write", False)

    result = sync_ecosystems(
        registry_path=args.registry,
        workspace=workspace,
        organ=organ,
        dry_run=dry_run,
    )

    prefix = "[DRY RUN] " if result["dry_run"] else ""
    print(f"\n{prefix}Ecosystem sync results:")
    print(f"  Created: {len(result['created'])}")
    print(f"  Skipped: {len(result['skipped'])}")
    print(f"  Errors:  {len(result['errors'])}")

    if result["created"]:
        print(f"\n  {prefix}{'Would create' if dry_run else 'Created'}:")
        for repo in result["created"]:
            print(f"    - {repo}")

    if result["errors"]:
        print("\n  Errors:")
        for err in result["errors"]:
            print(f"    - {err}")

    return 0


def cmd_ecosystem_matrix(args) -> int:
    """Cross-product view of one pillar."""
    from organvm_engine.ecosystem.query import pillar_view

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    ecosystems_data = _load_all(workspace, organ)

    if not ecosystems_data:
        print("No ecosystem profiles found.")
        return 0

    pillar = args.pillar
    view = pillar_view(ecosystems_data, pillar)

    if getattr(args, "json", False):
        json.dump(view, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    if not view:
        print(f"No products have arms in pillar '{pillar}'")
        return 0

    print(f"\nPillar: {pillar}")
    print(f"{'─' * 60}")
    for repo, arms in sorted(view.items()):
        print(f"\n  {repo}:")
        for arm in arms:
            status = arm.get("status", "?")
            platform = arm.get("platform", "?")
            priority = arm.get("priority", "")
            prio_str = f" [{priority}]" if priority else ""
            print(f"    {platform:<30} {status}{prio_str}")

    return 0


def cmd_ecosystem_actions(args) -> int:
    """Show prioritized next-action list."""
    from organvm_engine.ecosystem.query import next_actions

    workspace = resolve_workspace(args)
    organ = getattr(args, "organ", None)
    ecosystems_data = _load_all(workspace, organ)

    if not ecosystems_data:
        print("No ecosystem profiles found.")
        return 0

    actions = next_actions(ecosystems_data)

    if getattr(args, "json", False):
        json.dump(actions, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    if not actions:
        print("No next actions found.")
        return 0

    print(f"{'Priority':<10} {'Repo':<35} {'Pillar':<12} {'Platform':<25} Action")
    print(f"{'─' * 10} {'─' * 35} {'─' * 12} {'─' * 25} {'─' * 30}")
    for a in actions:
        print(
            f"{a['priority']:<10} {a['repo']:<35} "
            f"{a['pillar']:<12} {a['platform']:<25} "
            f"{a['next_action']}"
        )

    return 0


def cmd_ecosystem_validate(args) -> int:
    """Validate all ecosystem.yaml files."""
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.reader import read_ecosystem, validate_ecosystem

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    organ = getattr(args, "organ", None)
    paths = discover_ecosystems(workspace, organ=organ)

    total = 0
    invalid = 0
    all_errors: list[tuple[str, list[str]]] = []

    for eco_path in paths:
        total += 1
        try:
            data = read_ecosystem(eco_path)
        except Exception as exc:
            invalid += 1
            all_errors.append((str(eco_path), [f"Parse error: {exc}"]))
            continue

        errors = validate_ecosystem(data)
        if errors:
            invalid += 1
            repo = data.get("repo", eco_path.parent.name)
            all_errors.append((repo, errors))

    if getattr(args, "json", False):
        result = {
            "total": total,
            "valid": total - invalid,
            "invalid": invalid,
            "errors": {k: v for k, v in all_errors},
        }
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1 if invalid else 0

    print(f"\nEcosystem validation: {total - invalid}/{total} valid")
    if all_errors:
        for name, errs in all_errors:
            print(f"\n  {name}:")
            for e in errs:
                print(f"    - {e}")
        return 1

    print("All ecosystem.yaml files are valid.")
    return 0


def _print_ecosystem(data: dict) -> None:
    """Pretty-print an ecosystem profile."""
    from organvm_engine.ecosystem.reader import get_pillars

    print(f"\n  {data.get('display_name', data.get('repo', '?'))}")
    print(f"  Repo: {data.get('repo')}  Organ: {data.get('organ')}")
    print(f"  {'─' * 50}")

    pillars = get_pillars(data)
    for pillar_name, arms in pillars.items():
        print(f"\n  {pillar_name}:")
        for arm in arms:
            status = arm.get("status", "?")
            platform = arm.get("platform", "?")
            priority = arm.get("priority", "")
            prio_str = f" [{priority}]" if priority else ""
            na = arm.get("next_action", "")
            na_str = f" → {na}" if na else ""
            print(f"    {platform:<30} {status}{prio_str}{na_str}")


def cmd_ecosystem_dna(args) -> int:
    """Show pillar DNA for a repo."""
    import yaml

    from organvm_engine.ecosystem.pillar_dna import list_pillar_dnas, read_pillar_dna

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    repo_path = _find_repo_path(workspace, args.repo)
    if not repo_path:
        print(f"Repository '{args.repo}' not found in workspace")
        return 1

    pillar_filter = getattr(args, "pillar", None)

    if pillar_filter:
        dna = read_pillar_dna(repo_path, pillar_filter)
        if not dna:
            print(f"No pillar DNA for '{pillar_filter}' in {args.repo}")
            return 1
        if getattr(args, "json", False):
            json.dump(dna, sys.stdout, indent=2, default=str)
            sys.stdout.write("\n")
        else:
            print(yaml.dump(dna, default_flow_style=False, sort_keys=False))
        return 0

    pillars = list_pillar_dnas(repo_path)
    if not pillars:
        print(f"No pillar DNA files found for '{args.repo}'")
        return 1

    all_dna: dict[str, dict] = {}
    for p in pillars:
        dna = read_pillar_dna(repo_path, p)
        if dna:
            all_dna[p] = dna

    if getattr(args, "json", False):
        json.dump(all_dna, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        for name, dna in all_dna.items():
            print(f"\n{'═' * 60}")
            print(f"  {name} — {dna.get('lifecycle_stage', '?')} ({dna.get('product_type', '?')})")
            print(f"{'═' * 60}")
            research = dna.get("research", {})
            if research.get("scan_scope"):
                print(f"  Scan: {', '.join(research['scan_scope'])}")
            artifacts = dna.get("artifacts", [])
            if artifacts:
                print(f"  Artifacts: {len(artifacts)}")
                for a in artifacts:
                    print(f"    - {a.get('name', '?')} ({a.get('cadence', '?')})")

    return 0


def cmd_ecosystem_scaffold_dna(args) -> int:
    """Generate pillar DNA from ecosystem.yaml for a repo."""
    import yaml

    from organvm_engine.ecosystem.reader import read_ecosystem
    from organvm_engine.ecosystem.scaffold_pillar import scaffold_repo_ecosystem

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    repo_path = _find_repo_path(workspace, args.repo)
    if not repo_path:
        print(f"Repository '{args.repo}' not found in workspace")
        return 1

    eco_file = repo_path / "ecosystem.yaml"
    if not eco_file.is_file():
        print(f"No ecosystem.yaml found in {args.repo}")
        return 1

    eco_data = read_ecosystem(eco_file)

    # Try to load seed
    seed = None
    seed_path = repo_path / "seed.yaml"
    if seed_path.is_file():
        from organvm_engine.seed.reader import read_seed
        try:
            seed = read_seed(seed_path)
        except Exception:
            pass

    dry_run = not getattr(args, "write", False)
    result = scaffold_repo_ecosystem(
        repo_path=repo_path,
        ecosystem_data=eco_data,
        seed_data=seed,
        dry_run=dry_run,
    )

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}Pillar DNA scaffold for {args.repo}:")
    for pillar, dna in result["pillar_dnas"].items():
        stage = dna.get("lifecycle_stage", "?")
        ptype = dna.get("product_type", "?")
        arts = len(dna.get("artifacts", []))
        print(f"  {pillar}: stage={stage}, type={ptype}, artifacts={arts}")

    if result["written"]:
        print(f"\n  Written:")
        for p in result["written"]:
            print(f"    {p}")

    return 0


def cmd_ecosystem_sync_dna(args) -> int:
    """Scaffold pillar DNA for all repos with ecosystem.yaml."""
    from organvm_engine.ecosystem.scaffold_pillar import sync_pillar_dnas

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    organ = getattr(args, "organ", None)
    dry_run = not getattr(args, "write", False)

    result = sync_pillar_dnas(workspace=workspace, organ=organ, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}Pillar DNA sync results:")
    print(f"  Scaffolded: {len(result['scaffolded'])}")
    print(f"  Skipped (already have DNA): {len(result['skipped'])}")
    print(f"  Errors: {len(result['errors'])}")

    if result["scaffolded"]:
        print(f"\n  {prefix}{'Would scaffold' if dry_run else 'Scaffolded'}:")
        for repo in result["scaffolded"]:
            print(f"    - {repo}")

    if result["errors"]:
        print("\n  Errors:")
        for err in result["errors"]:
            print(f"    - {err}")

    return 0


def cmd_ecosystem_staleness(args) -> int:
    """Show staleness report for pillar DNA artifacts."""
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.intelligence import staleness_report

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    organ = getattr(args, "organ", None)
    eco_paths = discover_ecosystems(workspace, organ=organ)

    all_stale: dict[str, list[dict]] = {}
    for eco_path in eco_paths:
        repo_path = eco_path.parent
        repo_name = repo_path.name
        try:
            report = staleness_report(repo_path)
            if report:
                all_stale[repo_name] = report
        except Exception:
            pass

    if getattr(args, "json", False):
        json.dump(all_stale, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    if not all_stale:
        print("No stale artifacts found (or no pillar DNA exists).")
        return 0

    total = sum(len(v) for v in all_stale.values())
    print(f"\nStaleness report: {total} issues across {len(all_stale)} repos\n")
    for repo, items in sorted(all_stale.items()):
        print(f"  {repo}:")
        for item in items:
            status = item["status"]
            pillar = item["pillar"]
            name = item["artifact"]
            if status == "missing":
                print(f"    {pillar}/{name}: MISSING (never created)")
            else:
                days = item["days_stale"]
                threshold = item["staleness_days"]
                print(f"    {pillar}/{name}: {days}d old (threshold: {threshold}d)")

    return 0


def cmd_ecosystem_lifecycle(args) -> int:
    """Show lifecycle stages for all pillars in a repo."""
    from organvm_engine.ecosystem.pillar_dna import (
        check_gates,
        list_pillar_dnas,
        read_pillar_dna,
    )
    from organvm_engine.ecosystem.product_types import LIFECYCLE_STAGES

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    repo_path = _find_repo_path(workspace, args.repo)
    if not repo_path:
        print(f"Repository '{args.repo}' not found in workspace")
        return 1

    pillars = list_pillar_dnas(repo_path)
    if not pillars:
        print(f"No pillar DNA files found for '{args.repo}'")
        return 1

    if getattr(args, "json", False):
        result: dict[str, dict] = {}
        for p in pillars:
            dna = read_pillar_dna(repo_path, p)
            if dna:
                stage = dna.get("lifecycle_stage", "conception")
                idx = LIFECYCLE_STAGES.index(stage) if stage in LIFECYCLE_STAGES else 0
                next_stage = LIFECYCLE_STAGES[idx + 1] if idx + 1 < len(LIFECYCLE_STAGES) else None
                gates = check_gates(dna, stage, next_stage) if next_stage else []
                result[p] = {
                    "stage": stage,
                    "next_stage": next_stage,
                    "gates_to_next": gates,
                }
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"\nLifecycle stages for {args.repo}:\n")
    for p in pillars:
        dna = read_pillar_dna(repo_path, p)
        if not dna:
            continue
        stage = dna.get("lifecycle_stage", "conception")
        ptype = dna.get("product_type", "?")
        idx = LIFECYCLE_STAGES.index(stage) if stage in LIFECYCLE_STAGES else 0
        progress = f"[{'█' * (idx + 1)}{'░' * (len(LIFECYCLE_STAGES) - idx - 1)}]"
        print(f"  {p:<20} {progress} {stage} ({ptype})")

        next_stage = LIFECYCLE_STAGES[idx + 1] if idx + 1 < len(LIFECYCLE_STAGES) else None
        if next_stage:
            gates = check_gates(dna, stage, next_stage)
            if gates:
                print(f"  {'':20} Gates to {next_stage}:")
                for g in gates:
                    print(f"  {'':20}   ☐ {g}")

    return 0


def _find_repo_path(workspace, repo_name: str):
    """Find a repo path in the workspace by name."""
    from organvm_engine.organ_config import organ_org_dirs

    for org_dir_name in organ_org_dirs():
        candidate = workspace / org_dir_name / repo_name
        if candidate.is_dir():
            return candidate
    return None


def _load_all(workspace, organ=None) -> list[dict]:
    """Load all ecosystem profiles."""
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.reader import read_ecosystem

    paths = discover_ecosystems(workspace, organ=organ)
    data: list[dict] = []
    for p in paths:
        try:
            data.append(read_ecosystem(p))
        except Exception:
            pass
    return data
