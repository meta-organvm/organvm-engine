"""Unified CLI for the organvm system.

Usage:
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
    organvm dispatch validate <file>
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

    # dispatch
    dis = sub.add_parser("dispatch", help="Dispatch operations")
    dis_sub = dis.add_subparsers(dest="subcommand")
    val = dis_sub.add_parser("validate", help="Validate a dispatch payload")
    val.add_argument("file", help="Path to dispatch payload JSON")

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
        ("seed", "discover"): cmd_seed_discover,
        ("seed", "validate"): cmd_seed_validate,
        ("seed", "graph"): cmd_seed_graph,
        ("metrics", "calculate"): cmd_metrics_calculate,
        ("dispatch", "validate"): cmd_dispatch_validate,
    }

    handler = dispatch.get((args.command, getattr(args, "subcommand", None)))
    if handler:
        return handler(args)

    parser.parse_args([args.command, "--help"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
