"""CLI commands for the exit interview protocol.

Usage:
    organvm exit-interview discover [--gate-dir <path>]
    organvm exit-interview generate [--gate <name>] [--gate-dir <path>]
    organvm exit-interview counter [--gate <name>] [--gate-dir <path>]
    organvm exit-interview rectify [--gate <name>] [--gate-dir <path>]
    organvm exit-interview plan [--gate <name>] [--format {yaml|plan|issues}]
    organvm exit-interview full [--gate-dir <path>] [--dry-run]
    organvm exit-interview orphans [--gate-dir <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from organvm_engine.paths import workspace_root


def _default_gate_dir() -> Path:
    """Default gate contract directory: ~/Workspace/a-organvm/."""
    return workspace_root() / "a-organvm"


def _resolve_gate_dir(args: argparse.Namespace) -> Path:
    gate_dir = Path(getattr(args, "gate_dir", None) or _default_gate_dir())
    if not gate_dir.is_dir():
        print(f"error: gate directory not found: {gate_dir}", file=sys.stderr)
        sys.exit(1)
    return gate_dir


def cmd_exit_interview_discover(args: argparse.Namespace) -> int:
    """Phase 0: parse gate contracts, build demand/supply maps."""
    from organvm_engine.governance.exit_interview.discovery import discover

    gate_dir = _resolve_gate_dir(args)
    ws_root = workspace_root()

    result = discover(gate_dir, workspace_root=ws_root)
    print(result.summary())

    if getattr(args, "json", False):
        print(yaml.dump(result.to_dict(), default_flow_style=False, sort_keys=False, width=120))

    return 0


def cmd_exit_interview_generate(args: argparse.Namespace) -> int:
    """Phase 1: generate V1 testimony for all (or one) gate's sources."""
    from organvm_engine.governance.exit_interview.discovery import discover
    from organvm_engine.governance.exit_interview.testimony import generate_all_testimonies

    gate_dir = _resolve_gate_dir(args)
    ws_root = workspace_root()

    result = discover(gate_dir, workspace_root=ws_root)
    gate_filter = getattr(args, "gate", None)

    # Filter supply map if --gate specified
    supply = result.supply_map.entries
    if gate_filter:
        supply = {
            k: v for k, v in supply.items()
            if any(d.gate_name == gate_filter for d in v.demands)
        }

    testimonies = generate_all_testimonies(supply, ws_root)

    for key, testimony in sorted(testimonies.items()):
        print(f"--- {key}")
        print(yaml.dump(testimony.to_dict(), default_flow_style=False, sort_keys=False, width=120))

    print(f"\nGenerated {len(testimonies)} testimonies")
    return 0


def cmd_exit_interview_counter(args: argparse.Namespace) -> int:
    """Phase 2: generate V2 counter-testimony from gate contracts."""
    from organvm_engine.governance.exit_interview.counter_testimony import (
        generate_all_counter_testimonies,
    )
    from organvm_engine.governance.exit_interview.discovery import load_gate_contracts

    gate_dir = _resolve_gate_dir(args)
    contracts = load_gate_contracts(gate_dir)

    gate_filter = getattr(args, "gate", None)
    if gate_filter:
        contracts = [c for c in contracts if c.name == gate_filter]

    counter = generate_all_counter_testimonies(contracts)

    for key, ct in sorted(counter.items()):
        print(f"--- {key}")
        print(yaml.dump(ct.to_dict(), default_flow_style=False, sort_keys=False, width=120))

    print(f"\nGenerated {len(counter)} counter-testimonies")
    return 0


def cmd_exit_interview_rectify(args: argparse.Namespace) -> int:
    """Phase 3: three-voice rectification."""
    from organvm_engine.governance.exit_interview.counter_testimony import (
        generate_all_counter_testimonies,
    )
    from organvm_engine.governance.exit_interview.discovery import discover
    from organvm_engine.governance.exit_interview.rectification import rectify_all
    from organvm_engine.governance.exit_interview.testimony import generate_all_testimonies

    gate_dir = _resolve_gate_dir(args)
    ws_root = workspace_root()

    result = discover(gate_dir, workspace_root=ws_root)

    gate_filter = getattr(args, "gate", None)
    contracts = result.contracts
    if gate_filter:
        contracts = [c for c in contracts if c.name == gate_filter]

    testimonies = generate_all_testimonies(result.supply_map.entries, ws_root)
    counter = generate_all_counter_testimonies(contracts)

    reports = rectify_all(contracts, testimonies, counter, ws_root, result.orphans)

    for report in reports:
        print(f"\n{'=' * 60}")
        print(f"GATE: {report.gate_name} (status: {report.gate_status})")
        print(f"Alignment: {report.alignment_score:.1%}")
        print(f"Modules: {report.v1_modules_claimed} claimed, {report.testified} testified, {report.orphaned} orphaned")

        for path, verdicts in report.module_verdicts.items():
            print(f"\n  {path}:")
            for v in verdicts:
                marker = "+" if v.verdict.value == "ALIGNED" else "-"
                print(f"    [{marker}] {v.dimension}: {v.verdict.value}")
                if v.remediation:
                    print(f"        -> {v.remediation}")

        if report.remediation:
            print(f"\n  Remediation items: {len(report.remediation)}")
            for item in report.remediation:
                print(f"    [{item.priority.value}] {item.action}")

    return 0


def cmd_exit_interview_plan(args: argparse.Namespace) -> int:
    """Phase 4: generate remediation plan."""
    from organvm_engine.governance.exit_interview.counter_testimony import (
        generate_all_counter_testimonies,
    )
    from organvm_engine.governance.exit_interview.discovery import discover
    from organvm_engine.governance.exit_interview.rectification import rectify_all
    from organvm_engine.governance.exit_interview.remediation import (
        render_issues,
        render_plan,
        render_yaml,
    )
    from organvm_engine.governance.exit_interview.testimony import generate_all_testimonies

    gate_dir = _resolve_gate_dir(args)
    ws_root = workspace_root()

    result = discover(gate_dir, workspace_root=ws_root)

    gate_filter = getattr(args, "gate", None)
    contracts = result.contracts
    if gate_filter:
        contracts = [c for c in contracts if c.name == gate_filter]

    testimonies = generate_all_testimonies(result.supply_map.entries, ws_root)
    counter = generate_all_counter_testimonies(contracts)
    reports = rectify_all(contracts, testimonies, counter, ws_root, result.orphans)

    fmt = getattr(args, "format", "plan")
    if fmt == "yaml":
        print(render_yaml(reports))
    elif fmt == "issues":
        issues = render_issues(reports)
        print(json.dumps(issues, indent=2))
    else:
        print(render_plan(reports))

    return 0


def cmd_exit_interview_full(args: argparse.Namespace) -> int:
    """Run all phases: discover → generate → counter → rectify → plan."""
    from organvm_engine.governance.exit_interview.counter_testimony import (
        generate_all_counter_testimonies,
    )
    from organvm_engine.governance.exit_interview.discovery import discover
    from organvm_engine.governance.exit_interview.rectification import rectify_all
    from organvm_engine.governance.exit_interview.remediation import (
        compute_summary,
        render_plan,
    )
    from organvm_engine.governance.exit_interview.testimony import generate_all_testimonies

    gate_dir = _resolve_gate_dir(args)
    ws_root = workspace_root()

    print("Phase 0: Discovery...")
    result = discover(gate_dir, workspace_root=ws_root)
    print(f"  {len(result.contracts)} gate contracts, {len(result.supply_map.entries)} V1 modules, {len(result.orphans)} orphans")

    print("Phase 1: V1 Testimony...")
    testimonies = generate_all_testimonies(result.supply_map.entries, ws_root)
    print(f"  {len(testimonies)} testimonies generated")

    print("Phase 2: V2 Counter-Testimony...")
    counter = generate_all_counter_testimonies(result.contracts)
    print(f"  {len(counter)} counter-testimonies generated")

    print("Phase 3: Rectification...")
    reports = rectify_all(result.contracts, testimonies, counter, ws_root, result.orphans)
    summary = compute_summary(reports)
    print(f"  Overall alignment: {summary['overall_alignment']:.1%}")
    print(f"  Verdict distribution: {summary['verdict_counts']}")

    print("Phase 4: Remediation Plan...")
    plan = render_plan(reports)

    dry_run = getattr(args, "dry_run", True) and not getattr(args, "write", False)
    if dry_run:
        print("\n--- REMEDIATION PLAN (dry-run) ---\n")
        print(plan)
    else:
        from organvm_engine.paths import corpus_dir
        output_dir = Path(corpus_dir()) / "data" / "exit-interview"
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = output_dir / "remediation-plan.md"
        plan_path.write_text(plan, encoding="utf-8")
        print(f"  Plan written to {plan_path}")

        # Also write YAML
        from organvm_engine.governance.exit_interview.remediation import render_yaml
        yaml_path = output_dir / "rectification-full.yaml"
        yaml_path.write_text(render_yaml(reports), encoding="utf-8")
        print(f"  YAML written to {yaml_path}")

    return 0


def cmd_exit_interview_orphans(args: argparse.Namespace) -> int:
    """Show V1 governance modules not claimed by any gate contract."""
    from organvm_engine.governance.exit_interview.discovery import discover

    gate_dir = _resolve_gate_dir(args)
    ws_root = workspace_root()

    result = discover(gate_dir, workspace_root=ws_root)

    if not result.orphans:
        print("No orphaned governance modules found.")
        return 0

    print(f"Orphaned V1 governance modules ({len(result.orphans)}):")
    print("(Not referenced by any gate contract — review for knowledge loss)")
    print()
    for orphan in result.orphans:
        rec = f"  -> {orphan.recommendation}" if orphan.recommendation else ""
        print(f"  {orphan.v1_path} ({orphan.artifact_type}){rec}")

    return 0
