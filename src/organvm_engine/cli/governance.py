"""Governance CLI commands."""

import argparse

from organvm_engine.registry.loader import load_registry
from organvm_engine.registry.query import find_repo


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

    print("Dependency Graph Validation")
    print("─" * 40)
    print(f"  Total edges: {result.total_edges}")
    print(f"  Missing targets: {len(result.missing_targets)}")
    print(f"  Self-dependencies: {len(result.self_deps)}")
    print(f"  Back-edges: {len(result.back_edges)}")
    print(f"  Cycles: {len(result.cycles)}")

    if result.cross_organ:
        print("\n  Cross-organ directions:")
        for direction, count in sorted(result.cross_organ.items()):
            print(f"    {direction}: {count}")

    if result.violations:
        print("\n  Violations:")
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
        print("  Transition is valid. Use 'organvm registry update' to apply.")
    return 0 if ok else 1


def cmd_governance_impact(args: argparse.Namespace) -> int:
    from organvm_engine.governance.impact import calculate_impact

    registry = load_registry(args.registry)
    workspace = args.workspace if hasattr(args, "workspace") else None
    report = calculate_impact(args.repo, registry, workspace)

    print(report.summary())
    return 0
