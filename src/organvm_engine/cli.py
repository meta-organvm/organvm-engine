"""Unified CLI for the organvm system.

Usage:
    organvm status
    organvm registry show <repo>
    organvm registry list [--organ X] [--status X] [--tier X]
    organvm registry validate
    organvm registry update <repo> <field> <value>
    organvm governance audit
    organvm governance check-deps
    organvm governance promote <repo> <target-state>
    organvm seed discover
    organvm seed validate
    organvm seed graph
    organvm metrics calculate
    organvm metrics propagate [--cross-repo] [--dry-run]
    organvm metrics refresh [--cross-repo] [--dry-run]
    organvm dispatch validate <file>
    organvm git init-superproject --organ {I|II|III|IV|V|VI|VII|META|LIMINAL}
    organvm git add-submodule --organ X --repo <name> [--url <url>]
    organvm git sync-organ --organ X [--message "msg"]
    organvm git sync-all [--dry-run]
    organvm git status [--organ X]
    organvm git reproduce-workspace [--organ X] [--shallow] [--manifest <path>]
    organvm git diff-pinned [--organ X]
    organvm git install-hooks [--organ X]
    organvm omega status
    organvm omega check
    organvm context sync [--dry-run] [--organ X]
"""

import argparse
import json
import sys
from pathlib import Path

from organvm_engine.registry.loader import load_registry, save_registry, DEFAULT_REGISTRY_PATH
from organvm_engine.registry.query import find_repo, list_repos
from organvm_engine.registry.validator import validate_registry
from organvm_engine.registry.updater import update_repo


# ── Registry commands ────────────────────────────────────────────────


def cmd_registry_show(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    result = find_repo(registry, args.repo)
    if not result:
        print(f"ERROR: Repo '{args.repo}' not found in registry")
        return 1

    organ_key, repo = result
    print(f"\n  {repo['name']}")
    print(f"  {'─' * max(len(repo['name']), 40)}")
    print(f"  Organ:       {organ_key}")
    for key, value in repo.items():
        if key == "name":
            continue
        if isinstance(value, list):
            print(f"  {key + ':':<20}{', '.join(str(v) for v in value)}")
        elif isinstance(value, dict):
            print(f"  {key + ':':<20}{json.dumps(value, indent=None)}")
        else:
            print(f"  {key + ':':<20}{value}")
    print()
    return 0


def cmd_registry_list(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    results = list_repos(
        registry,
        organ=args.organ,
        status=args.status,
        tier=args.tier,
        public_only=args.public,
    )

    if not results:
        print("No repos match the given filters.")
        return 0

    print(f"\n  {'Name':<45} {'Organ':<15} {'Status':<12} {'Tier':<12}")
    print(f"  {'─' * 84}")
    for organ_key, repo in results:
        print(
            f"  {repo['name']:<45} {organ_key:<15} "
            f"{repo.get('implementation_status', '?'):<12} "
            f"{repo.get('tier', '?'):<12}"
        )
    print(f"\n  {len(results)} repo(s)")
    return 0


def cmd_registry_validate(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    result = validate_registry(registry)
    print(result.summary())
    return 0 if result.passed else 1


def cmd_registry_update(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)

    # Type coercion — only for known boolean/integer fields
    BOOL_FIELDS = {"public", "platinum_status", "archived"}
    INT_FIELDS = set()  # No integer fields currently

    value: str | bool | int = args.value
    if args.field in BOOL_FIELDS:
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
    elif args.field in INT_FIELDS:
        try:
            value = int(value)
        except ValueError:
            pass

    ok, msg = update_repo(registry, args.repo, args.field, value)
    print(f"  {msg}")
    if ok:
        save_registry(registry, args.registry)
        print("  Registry saved.")
    return 0 if ok else 1


# ── Governance commands ──────────────────────────────────────────────


def cmd_governance_audit(args: argparse.Namespace) -> int:
    from organvm_engine.governance.audit import run_audit

    registry = load_registry(args.registry)
    rules_path = args.rules if hasattr(args, "rules") and args.rules else None

    if rules_path:
        from organvm_engine.governance.rules import load_governance_rules
        rules = load_governance_rules(rules_path)
    else:
        rules = None

    result = run_audit(registry, rules)
    print(result.summary())
    return 0 if result.passed else 1


def cmd_governance_checkdeps(args: argparse.Namespace) -> int:
    from organvm_engine.governance.dependency_graph import validate_dependencies

    registry = load_registry(args.registry)
    result = validate_dependencies(registry)

    print(f"Dependency Graph Validation")
    print(f"{'─' * 40}")
    print(f"  Total edges: {result.total_edges}")
    print(f"  Missing targets: {len(result.missing_targets)}")
    print(f"  Self-dependencies: {len(result.self_deps)}")
    print(f"  Back-edges: {len(result.back_edges)}")
    print(f"  Cycles: {len(result.cycles)}")

    if result.cross_organ:
        print(f"\n  Cross-organ directions:")
        for direction, count in sorted(result.cross_organ.items()):
            print(f"    {direction}: {count}")

    if result.violations:
        print(f"\n  Violations:")
        for v in result.violations:
            print(f"    {v}")

    print(f"\n  Result: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


def cmd_governance_promote(args: argparse.Namespace) -> int:
    from organvm_engine.governance.state_machine import check_transition

    registry = load_registry(args.registry)
    result = find_repo(registry, args.repo)
    if not result:
        print(f"ERROR: Repo '{args.repo}' not found")
        return 1

    organ_key, repo = result
    current = repo.get("promotion_status", "LOCAL")
    ok, msg = check_transition(current, args.target)
    print(f"  {msg}")

    if ok:
        print(f"  Transition is valid. Use 'organvm registry update' to apply.")
    return 0 if ok else 1


def cmd_governance_impact(args: argparse.Namespace) -> int:
    from organvm_engine.governance.impact import calculate_impact

    registry = load_registry(args.registry)
    report = calculate_impact(args.repo, registry, args.workspace if hasattr(args, 'workspace') else None)
    
    print(report.summary())
    return 0


# ── Seed commands ────────────────────────────────────────────────────


def cmd_seed_discover(args: argparse.Namespace) -> int:
    from organvm_engine.seed.discover import discover_seeds

    seeds = discover_seeds(args.workspace)
    print(f"Found {len(seeds)} seed.yaml files:\n")
    for path in seeds:
        # Show as org/repo
        parts = path.parts
        repo = parts[-2]
        org = parts[-3]
        print(f"  {org}/{repo}")
    return 0


def cmd_seed_validate(args: argparse.Namespace) -> int:
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed

    seeds = discover_seeds(args.workspace)
    errors = 0

    for path in seeds:
        try:
            seed = read_seed(path)
            required = ["schema_version", "organ", "repo", "org"]
            missing = [f for f in required if f not in seed]
            if missing:
                print(f"  FAIL {path.parent.name}: missing {', '.join(missing)}")
                errors += 1
            else:
                print(f"  PASS {seed.get('org')}/{seed.get('repo')}")
        except Exception as e:
            print(f"  FAIL {path}: {e}")
            errors += 1

    print(f"\n{len(seeds) - errors} passed, {errors} failed")
    return 1 if errors > 0 else 0


def cmd_seed_graph(args: argparse.Namespace) -> int:
    from organvm_engine.seed.graph import build_seed_graph

    graph = build_seed_graph(args.workspace)
    print(graph.summary())
    return 0


# ── Metrics commands ─────────────────────────────────────────────────


def cmd_metrics_calculate(args: argparse.Namespace) -> int:
    from organvm_engine.metrics.calculator import compute_metrics, write_metrics

    registry = load_registry(args.registry)
    computed = compute_metrics(registry)

    output = Path(args.output) if args.output else (
        Path(args.registry).parent / "system-metrics.json"
    )
    write_metrics(computed, output)

    print(f"Metrics written to {output}")
    print(f"  Repos: {computed['total_repos']} ({computed['active_repos']} ACTIVE)")
    print(f"  Organs: {computed['operational_organs']}/{computed['total_organs']} operational")
    print(f"  CI: {computed['ci_workflows']}")
    print(f"  Dependencies: {computed['dependency_edges']} edges")
    return 0


def cmd_metrics_propagate(args: argparse.Namespace) -> int:
    from organvm_engine.metrics.propagator import (
        propagate_cross_repo,
        propagate_metrics,
        resolve_manifest_files,
        load_manifest,
    )

    corpus_root = Path(args.registry).parent
    metrics_path = corpus_root / "system-metrics.json"

    if not metrics_path.exists():
        print(f"ERROR: {metrics_path} not found. Run 'organvm metrics calculate' first.",
              file=sys.stderr)
        return 1

    with open(metrics_path) as f:
        metrics = json.load(f)

    mode = "DRY RUN" if args.dry_run else "PROPAGATING"

    if args.cross_repo:
        manifest_path = Path(args.targets) if args.targets else (corpus_root / "metrics-targets.yaml")
        if not manifest_path.exists():
            print(f"ERROR: {manifest_path} not found.", file=sys.stderr)
            return 1

        result = propagate_cross_repo(metrics, manifest_path, corpus_root, dry_run=args.dry_run)
        print(f"[{mode}] Cross-repo propagation complete")
        print(f"  JSON copies: {result.json_copies}")
        print(f"  Markdown: {result.replacements} replacement(s) across {result.files_changed} file(s)")
    else:
        # Corpus-only: use the built-in whitelist from the standalone script
        whitelist_globs = [
            "README.md", "CLAUDE.md", "applications/*.md", "applications/shared/*.md",
            "docs/applications/*.md", "docs/applications/cover-letters/*.md",
            "docs/essays/09-ai-conductor-methodology.md", "docs/operations/*.md",
        ]
        files = []
        for pattern in whitelist_globs:
            files.extend(sorted(corpus_root.glob(pattern)))
        # Deduplicate
        seen = set()
        unique = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        result = propagate_metrics(metrics, unique, dry_run=args.dry_run)
        print(f"[{mode}] Corpus-only propagation complete")
        print(f"  {result.replacements} replacement(s) across {result.files_changed} file(s)")

    if result.details:
        for d in result.details[:20]:
            print(f"    {d}")
        if len(result.details) > 20:
            print(f"    ... and {len(result.details) - 20} more")

    return 0


def cmd_metrics_refresh(args: argparse.Namespace) -> int:
    from organvm_engine.metrics.calculator import compute_metrics, write_metrics

    # Step 1: Calculate
    registry = load_registry(args.registry)
    computed = compute_metrics(registry)

    corpus_root = Path(args.registry).parent
    output = corpus_root / "system-metrics.json"

    if not args.dry_run:
        write_metrics(computed, output)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}[1/2] Metrics calculated → {output}")
    print(f"  Repos: {computed['total_repos']} ({computed['active_repos']} ACTIVE)")

    # Step 2: Propagate
    args_ns = argparse.Namespace(
        registry=args.registry,
        cross_repo=args.cross_repo,
        targets=getattr(args, "targets", None),
        dry_run=args.dry_run,
    )
    print(f"[2/2] Propagating...")
    return cmd_metrics_propagate(args_ns)


# ── Dispatch commands ────────────────────────────────────────────────


def cmd_dispatch_validate(args: argparse.Namespace) -> int:
    from organvm_engine.dispatch.payload import validate_payload

    with open(args.file) as f:
        payload = json.load(f)

    ok, errors = validate_payload(payload)
    if ok:
        print(f"PASS: {args.file}")
    else:
        print(f"FAIL: {args.file}")
        for e in errors:
            print(f"  {e}")
    return 0 if ok else 1


# ── Git commands ────────────────────────────────────────────────────


def cmd_git_init_superproject(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import init_superproject

    result = init_superproject(
        organ=args.organ,
        workspace=args.workspace,
        registry_path=args.registry,
        dry_run=args.dry_run,
    )

    if result.get("already_initialized") and not args.dry_run:
        print(f"  Re-initialized superproject for {result['organ_dir']}")
    else:
        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"  {prefix}Initialized superproject: {result['organ_dir']}")

    print(f"  Submodules: {result['repos_registered']}")
    print(f"  Remote: {result['remote']}")
    if args.dry_run:
        for repo in result.get("repos", []):
            print(f"    - {repo}")
    return 0


def cmd_git_add_submodule(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import add_submodule

    result = add_submodule(
        organ=args.organ,
        repo_name=args.repo,
        repo_url=args.url,
        workspace=args.workspace,
    )

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return 1

    print(f"  Added submodule: {result['added']}")
    print(f"  URL: {result['url']}")
    return 0


def cmd_git_sync_organ(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import sync_organ

    result = sync_organ(
        organ=args.organ,
        message=args.message,
        workspace=args.workspace,
        dry_run=args.dry_run,
    )

    if not result["changed"]:
        print(f"  {result['organ']}: no submodule pointer changes")
        return 0

    prefix = "[DRY RUN] " if result.get("dry_run") else ""
    print(f"  {prefix}{result['organ']}: {len(result['changed'])} submodule(s) updated")
    for path in result["changed"]:
        print(f"    - {path}")
    return 0


def cmd_git_sync_all(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import ORGAN_DIR_MAP, sync_organ

    total_changed = 0
    for organ_key in ORGAN_DIR_MAP:
        try:
            result = sync_organ(
                organ=organ_key,
                workspace=args.workspace,
                dry_run=args.dry_run,
            )
            if result["changed"]:
                prefix = "[DRY RUN] " if result.get("dry_run") else ""
                print(f"  {prefix}{result['organ']}: {len(result['changed'])} updated")
                for path in result["changed"]:
                    print(f"    - {path}")
                total_changed += len(result["changed"])
        except (RuntimeError, FileNotFoundError):
            continue  # Skip organs without superprojects

    if total_changed == 0:
        print("  No submodule pointer changes across any organ.")
    else:
        print(f"\n  Total: {total_changed} submodule pointer(s) changed")
    return 0


def cmd_git_status(args: argparse.Namespace) -> int:
    from organvm_engine.git.status import show_drift

    drift = show_drift(organ=args.organ, workspace=args.workspace)

    if not drift:
        scope = f"organ {args.organ}" if args.organ else "all organs"
        print(f"  No drift detected across {scope}.")
        return 0

    print(f"  {'Organ':<30} {'Repo':<40} {'Pinned':<10} {'Current':<10} {'Status'}")
    print(f"  {'─' * 100}")
    for d in drift:
        ahead_info = ""
        if d.get("ahead"):
            ahead_info = f" (+{d['ahead']})"
        if d.get("behind"):
            ahead_info += f" (-{d['behind']})"
        print(
            f"  {d['organ']:<30} {d['repo']:<40} "
            f"{d['pinned_sha']:<10} {d['current_sha']:<10} "
            f"{d['status']}{ahead_info}"
        )
    print(f"\n  {len(drift)} submodule(s) with drift")
    return 0


def cmd_git_reproduce(args: argparse.Namespace) -> int:
    from organvm_engine.git.reproduce import reproduce_workspace

    organs = [args.organ] if args.organ else None
    result = reproduce_workspace(
        target=args.target,
        manifest_path=args.manifest,
        organs=organs,
        shallow=args.shallow,
    )

    print(f"  Target: {result['target']}")
    print(f"  Cloned: {len(result['cloned_organs'])} organ(s)")
    for o in result["cloned_organs"]:
        print(f"    - {o}")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"    - {e}")
        return 1
    return 0


def cmd_git_diff_pinned(args: argparse.Namespace) -> int:
    from organvm_engine.git.status import diff_pinned

    diffs = diff_pinned(organ=args.organ, workspace=args.workspace)

    if not diffs:
        print("  No pinned diffs found.")
        return 0

    for d in diffs:
        print(f"\n  {d['organ']}/{d['repo']}")
        print(f"  Pinned: {d['pinned_sha']}  Current: {d['current_sha']}")
        if d["commit_log"]:
            for commit in d["commit_log"]:
                print(f"    {commit}")
        else:
            print("    (no commits between pinned and current)")

    return 0


def cmd_git_install_hooks(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import install_hooks

    result = install_hooks(organ=args.organ, workspace=args.workspace)

    if result["installed"]:
        print(f"Hooks installed in {len(result['installed'])} superproject(s):")
        for o in result["installed"]:
            print(f"  - {o}")
    if result["errors"]:
        print(f"Errors installing hooks: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  - {e['organ']}: {e['error']}")
        return 1
    return 0


# ── Context commands ───────────────────────────────────────────────


def cmd_context_sync(args: argparse.Namespace) -> int:
    from organvm_engine.contextmd.sync import sync_all

    organs = [args.organ] if args.organ else None
    result = sync_all(
        workspace=args.workspace,
        registry_path=args.registry,
        dry_run=args.dry_run,
        organs=organs,
    )

    print(f"System Context Sync Results")
    print(f"{'─' * 40}")
    print(f"  Updated: {len(result['updated'])}")
    print(f"  Created: {len(result['created'])}")
    print(f"  Skipped: {len(result['skipped'])}")
    if result["errors"]:
        print(f"  Errors:  {len(result['errors'])}")
        for e in result["errors"]:
            print(f"    - {e['path']}: {e['error']}")

    if result.get("dry_run"):
        print(f"\n[DRY RUN] No files were modified.")

    return 1 if result["errors"] else 0


# ── Omega commands ────────────────────────────────────────────────


def cmd_omega_status(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import evaluate

    registry = load_registry(args.registry)
    scorecard = evaluate(registry=registry)
    print(f"\n{scorecard.summary()}\n")
    return 0


def cmd_omega_check(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import evaluate

    registry = load_registry(args.registry)
    scorecard = evaluate(registry=registry)
    print(json.dumps(scorecard.to_dict(), indent=2))
    return 0


def cmd_omega_update(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import evaluate, write_snapshot, diff_snapshots

    registry = load_registry(args.registry)
    scorecard = evaluate(registry=registry)

    # Show what changed
    changes = diff_snapshots(scorecard)
    print(f"\n  Omega Update — {scorecard.met_count}/{scorecard.total} MET")
    print(f"  {'─' * 50}")
    for change in changes:
        print(f"  {change}")

    if args.dry_run:
        print(f"\n  [DRY RUN] Would write snapshot to data/omega/")
    else:
        path = write_snapshot(scorecard)
        print(f"\n  Snapshot written: {path}")

    return 0


# ── Deadline commands ────────────────────────────────────────────


def cmd_deadlines(args: argparse.Namespace) -> int:
    from organvm_engine.deadlines.parser import parse_deadlines, filter_upcoming, format_deadlines

    deadlines = parse_deadlines()

    if args.all:
        filtered = deadlines
    else:
        filtered = filter_upcoming(deadlines, days=args.days)

    print(f"\n  Upcoming Deadlines (next {args.days} days)")
    print(f"  {'═' * 60}")
    print(format_deadlines(filtered))
    print(f"\n  {len(filtered)} deadline(s) shown ({len(deadlines)} total)\n")
    return 0


# ── CI commands ──────────────────────────────────────────────────


def cmd_ci_triage(args: argparse.Namespace) -> int:
    from organvm_engine.ci.triage import triage

    report = triage()
    print(f"\n{report.summary()}\n")
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    return 0


# ── Status command ───────────────────────────────────────────────


def cmd_status(args: argparse.Namespace) -> int:
    from organvm_engine.omega.scorecard import evaluate, analyze_soak_streak
    from organvm_engine.metrics.calculator import compute_metrics

    registry = load_registry(args.registry)
    metrics = compute_metrics(registry)
    scorecard = evaluate(registry=registry)
    soak = scorecard.soak

    print(f"\n  ORGANVM System Pulse")
    print(f"  {'═' * 50}")

    # Repo counts by organ
    print(f"\n  Organs ({metrics['operational_organs']}/{metrics['total_organs']} operational)")
    print(f"  {'─' * 50}")
    for organ_key, organ_data in metrics["per_organ"].items():
        print(f"    {organ_key:<18} {organ_data['repos']:>3} repos  ({organ_data['name']})")
    print(f"    {'─' * 40}")
    print(f"    {'Total':<18} {metrics['total_repos']:>3} repos  ({metrics['active_repos']} active)")

    # Soak test
    print(f"\n  Soak Test (VIGILIA)")
    print(f"  {'─' * 50}")
    if soak.total_snapshots > 0:
        pct = min(100, int(soak.streak_days / soak.target_days * 100))
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"    Streak:    {soak.streak_days}/{soak.target_days} days [{bar}] {pct}%")
        print(f"    Remaining: {soak.days_remaining} days")
        if soak.critical_incidents > 0:
            print(f"    Incidents: {soak.critical_incidents}")
    else:
        print(f"    No soak data found.")

    # Omega score
    print(f"\n  Omega Score")
    print(f"  {'─' * 50}")
    pct = int(scorecard.met_count / scorecard.total * 100) if scorecard.total else 0
    print(f"    {scorecard.met_count}/{scorecard.total} MET ({pct}%), {scorecard.in_progress_count} in progress")

    # CI
    print(f"\n  Infrastructure")
    print(f"  {'─' * 50}")
    print(f"    CI workflows:  {metrics['ci_workflows']}")
    print(f"    Dep edges:     {metrics['dependency_edges']}")

    print()
    return 0


# ── CLI argument parsing ─────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organvm",
        description="Unified CLI for the organvm eight-organ system",
    )
    parser.add_argument(
        "--registry", default=str(DEFAULT_REGISTRY_PATH),
        help="Path to registry-v2.json",
    )
    sub = parser.add_subparsers(dest="command")

    # registry
    reg = sub.add_parser("registry", help="Registry operations")
    reg_sub = reg.add_subparsers(dest="subcommand")

    show = reg_sub.add_parser("show", help="Show a registry entry")
    show.add_argument("repo")

    ls = reg_sub.add_parser("list", help="List repos with filters")
    ls.add_argument("--organ", default=None)
    ls.add_argument("--status", default=None)
    ls.add_argument("--tier", default=None)
    ls.add_argument("--public", action="store_true")

    reg_sub.add_parser("validate", help="Validate registry")

    upd = reg_sub.add_parser("update", help="Update a registry field")
    upd.add_argument("repo")
    upd.add_argument("field")
    upd.add_argument("value")

    # governance
    gov = sub.add_parser("governance", help="Governance operations")
    gov_sub = gov.add_subparsers(dest="subcommand")
    aud = gov_sub.add_parser("audit", help="Full governance audit")
    aud.add_argument("--rules", default=None, help="Path to governance-rules.json")

    gov_sub.add_parser("check-deps", help="Validate dependency graph")

    prom = gov_sub.add_parser("promote", help="Check promotion eligibility")
    prom.add_argument("repo")
    prom.add_argument("target", help="Target promotion state")

    imp = gov_sub.add_parser("impact", help="Calculate blast radius of a repo change")
    imp.add_argument("repo", help="Repository name")

    # seed
    seed = sub.add_parser("seed", help="Seed.yaml operations")
    seed.add_argument("--workspace", default=None, help="Workspace root directory")
    seed_sub = seed.add_subparsers(dest="subcommand")
    seed_sub.add_parser("discover", help="Find all seed.yaml files")
    seed_sub.add_parser("validate", help="Validate all seed.yaml files")
    seed_sub.add_parser("graph", help="Build produces/consumes graph")

    # metrics
    met = sub.add_parser("metrics", help="Metrics operations")
    met_sub = met.add_subparsers(dest="subcommand")
    calc = met_sub.add_parser("calculate", help="Compute current metrics")
    calc.add_argument("--output", default=None, help="Output file path")

    prop = met_sub.add_parser("propagate", help="Propagate metrics to documentation files")
    prop.add_argument("--cross-repo", action="store_true",
                      help="Read metrics-targets.yaml and propagate to all registered consumers")
    prop.add_argument("--targets", default=None,
                      help="Path to metrics-targets.yaml (default: corpus root)")
    prop.add_argument("--dry-run", action="store_true",
                      help="Preview changes without writing")

    refresh = met_sub.add_parser("refresh", help="Calculate + propagate in one step")
    refresh.add_argument("--cross-repo", action="store_true",
                         help="Propagate to all registered consumers")
    refresh.add_argument("--targets", default=None,
                         help="Path to metrics-targets.yaml")
    refresh.add_argument("--dry-run", action="store_true",
                         help="Preview changes without writing")

    # dispatch
    dis = sub.add_parser("dispatch", help="Dispatch operations")
    dis_sub = dis.add_subparsers(dest="subcommand")
    val = dis_sub.add_parser("validate", help="Validate a dispatch payload")
    val.add_argument("file", help="Path to dispatch payload JSON")

    # git
    git = sub.add_parser("git", help="Hierarchical superproject management")
    git.add_argument("--workspace", default=None, help="Workspace root directory")
    git_sub = git.add_subparsers(dest="subcommand")

    git_init = git_sub.add_parser("init-superproject", help="Initialize organ superproject")
    git_init.add_argument("--organ", required=True, help="Organ key (I, II, ..., META, LIMINAL)")
    git_init.add_argument("--dry-run", action="store_true", help="Report without making changes")

    git_add = git_sub.add_parser("add-submodule", help="Add submodule to organ superproject")
    git_add.add_argument("--organ", required=True, help="Organ key")
    git_add.add_argument("--repo", required=True, help="Repository name")
    git_add.add_argument("--url", default=None, help="Git URL (auto-derived if omitted)")

    git_sync = git_sub.add_parser("sync-organ", help="Sync submodule pointers")
    git_sync.add_argument("--organ", required=True, help="Organ key")
    git_sync.add_argument("--message", default=None, help="Commit message")
    git_sync.add_argument("--dry-run", action="store_true", help="Report without committing")

    git_sync_all = git_sub.add_parser("sync-all", help="Sync all organ superprojects")
    git_sync_all.add_argument("--dry-run", action="store_true", help="Report without committing")

    git_status = git_sub.add_parser("status", help="Show submodule drift")
    git_status.add_argument("--organ", default=None, help="Specific organ (default: all)")

    git_reproduce = git_sub.add_parser("reproduce-workspace", help="Clone workspace from superprojects")
    git_reproduce.add_argument("--target", required=True, help="Target directory")
    git_reproduce.add_argument("--organ", default=None, help="Single organ to clone")
    git_reproduce.add_argument("--shallow", action="store_true", help="Shallow clone")
    git_reproduce.add_argument("--manifest", default=None, help="Path to workspace-manifest.json")

    git_diff = git_sub.add_parser("diff-pinned", help="Show detailed diff between pinned and current")
    git_diff.add_argument("--organ", default=None, help="Specific organ (default: all)")

    git_hooks = git_sub.add_parser("install-hooks", help="Install git context sync hooks")
    git_hooks.add_argument("--organ", default=None, help="Specific organ (default: all)")

    # deadlines
    dl = sub.add_parser("deadlines", help="Show upcoming deadlines from rolling-todo")
    dl.add_argument("--days", type=int, default=30, help="Show deadlines within N days (default 30)")
    dl.add_argument("--all", action="store_true", help="Show all deadlines regardless of date")

    # ci
    ci = sub.add_parser("ci", help="CI health operations")
    ci_sub = ci.add_subparsers(dest="subcommand")
    ci_triage = ci_sub.add_parser("triage", help="Categorize CI failures from soak data")
    ci_triage.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # omega
    om = sub.add_parser("omega", help="Omega scorecard operations")
    om_sub = om.add_subparsers(dest="subcommand")
    om_sub.add_parser("status", help="Display omega scorecard summary")
    om_sub.add_parser("check", help="Machine-readable omega status (JSON)")
    om_update = om_sub.add_parser("update", help="Evaluate and write omega snapshot")
    om_update.add_argument("--dry-run", action="store_true", help="Preview without writing")

    # status (top-level)
    sub.add_parser("status", help="One-command system health pulse")

    # context
    ctx = sub.add_parser("context", help="System context file management")
    ctx.add_argument("--workspace", default=None, help="Workspace root directory")
    ctx_sub = ctx.add_subparsers(dest="subcommand")
    c_sync = ctx_sub.add_parser("sync", help="Sync CLAUDE.md, GEMINI.md, and AGENTS.md")
    c_sync.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    c_sync.add_argument("--organ", default=None, help="Filter to specific organ")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        ("registry", "show"): cmd_registry_show,
        ("registry", "list"): cmd_registry_list,
        ("registry", "validate"): cmd_registry_validate,
        ("registry", "update"): cmd_registry_update,
        ("governance", "audit"): cmd_governance_audit,
        ("governance", "check-deps"): cmd_governance_checkdeps,
        ("governance", "promote"): cmd_governance_promote,
        ("governance", "impact"): cmd_governance_impact,
        ("seed", "discover"): cmd_seed_discover,
        ("seed", "validate"): cmd_seed_validate,
        ("seed", "graph"): cmd_seed_graph,
        ("metrics", "calculate"): cmd_metrics_calculate,
        ("metrics", "propagate"): cmd_metrics_propagate,
        ("metrics", "refresh"): cmd_metrics_refresh,
        ("dispatch", "validate"): cmd_dispatch_validate,
        ("git", "init-superproject"): cmd_git_init_superproject,
        ("git", "add-submodule"): cmd_git_add_submodule,
        ("git", "sync-organ"): cmd_git_sync_organ,
        ("git", "sync-all"): cmd_git_sync_all,
        ("git", "status"): cmd_git_status,
        ("git", "reproduce-workspace"): cmd_git_reproduce,
        ("git", "diff-pinned"): cmd_git_diff_pinned,
        ("git", "install-hooks"): cmd_git_install_hooks,
        ("ci", "triage"): cmd_ci_triage,
        ("context", "sync"): cmd_context_sync,
        ("omega", "status"): cmd_omega_status,
        ("omega", "check"): cmd_omega_check,
        ("omega", "update"): cmd_omega_update,
    }

    # Handle top-level commands (no subcommand)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "deadlines":
        return cmd_deadlines(args)

    handler = dispatch.get((args.command, getattr(args, "subcommand", None)))
    if handler:
        return handler(args)

    parser.parse_args([args.command, "--help"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
