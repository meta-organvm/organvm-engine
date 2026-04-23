"""CLI commands for institutional formations.

    organvm formation list
    organvm formation show <name>
    organvm formation invoke <name> --context <json>
"""

from __future__ import annotations

import argparse
import json
import sys

from organvm_engine.formations.aegis import AEGIS_SPEC, build_default_engine
from organvm_engine.formations.registry import FormationRegistry
from organvm_engine.primitives.types import (
    InstitutionalContext,
    PrincipalPosition,
)


def _default_formation_registry() -> FormationRegistry:
    reg = FormationRegistry()
    reg.register(AEGIS_SPEC)
    return reg


# ---------------------------------------------------------------------------
# formation list
# ---------------------------------------------------------------------------


def cmd_formation_list(args: argparse.Namespace) -> int:
    reg = _default_formation_registry()
    specs = reg.list_all()

    if getattr(args, "json", False):
        rows = [
            {
                "id": s.formation_id,
                "name": s.name,
                "type": s.formation_type,
                "description": s.description,
                "primitives": s.primitives_used,
            }
            for s in specs
        ]
        print(json.dumps(rows, indent=2))
    else:
        for s in specs:
            print(f"  {s.formation_id}  {s.name:<12} [{s.formation_type}]")
            print(f"    {s.description}")
            print(f"    Primitives: {', '.join(s.primitives_used)}")
            print()
    return 0


# ---------------------------------------------------------------------------
# formation show
# ---------------------------------------------------------------------------


def cmd_formation_show(args: argparse.Namespace) -> int:
    reg = _default_formation_registry()
    spec = reg.get(args.name)
    if not spec:
        print(f"Unknown formation: {args.name}", file=sys.stderr)
        return 1

    print(f"Formation: {spec.name} ({spec.formation_id})")
    print(f"Type: {spec.formation_type}")
    print(f"Description: {spec.description}")
    print(f"Trigger: {spec.trigger_description}")
    print(f"Primitives: {', '.join(spec.primitives_used)}")
    print()
    print("Escalation policy:")
    for prim_name, policy in spec.escalation_policy.items():
        print(f"  {prim_name}: {policy}")

    if spec.build_graph:
        graph = spec.build_graph()
        print(f"\nGraph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        stages = graph.execution_order()
        for i, stage in enumerate(stages):
            names = [f"{n.primitive_name}({n.frame.frame_type.value if n.frame else '?'})" for n in stage]
            connector = " || " if len(stage) > 1 else ""
            print(f"  Stage {i}: {connector.join(names)}")
    return 0


# ---------------------------------------------------------------------------
# formation invoke
# ---------------------------------------------------------------------------


def cmd_formation_invoke(args: argparse.Namespace) -> int:
    engine = build_default_engine()

    if args.name not in engine.list_formations():
        print(f"Unknown formation: {args.name}", file=sys.stderr)
        return 1

    try:
        ctx_data = json.loads(args.context) if args.context else {}
    except json.JSONDecodeError as e:
        print(f"Invalid JSON context: {e}", file=sys.stderr)
        return 1

    context = InstitutionalContext(
        situation=ctx_data.get("situation", ""),
        data=ctx_data.get("data", ctx_data),
        tags=ctx_data.get("tags", []),
    )
    position = PrincipalPosition(
        interests=ctx_data.get("interests", []),
        objectives=ctx_data.get("objectives", []),
        constraints=ctx_data.get("constraints", []),
    )

    result = engine.execute_formation(args.name, context, position)

    if getattr(args, "json", False):
        from dataclasses import asdict
        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        print(f"Formation: {args.name}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Escalation: {result.escalation_flag}")
        print(f"Mode: {result.execution_mode.value}")
        print(f"Stakes: {result.stakes.value}")
        if result.metadata:
            for k, v in result.metadata.items():
                print(f"  {k}: {v}")
        print("\nOutput:")
        print(json.dumps(result.output, indent=2, default=str))
        print(f"\nAudit trail ({len(result.audit_trail)} entries):")
        for ae in result.audit_trail:
            print(
                f"  [{ae.primitive_name}] {ae.operation} "
                f"— {ae.rationale[:60]}",
            )
    return 0
