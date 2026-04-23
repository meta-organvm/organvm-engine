"""CLI commands for institutional primitives.

    organvm primitive list
    organvm primitive inspect <name>
    organvm primitive invoke <name> --context <json> --frame <type>
    organvm primitive guardian add-watch ...
    organvm primitive guardian watchlist
    organvm primitive guardian check
    organvm primitive ledger record ...
    organvm primitive ledger snapshot
    organvm primitive ledger entries
"""

from __future__ import annotations

import argparse
import json
import sys

from organvm_engine.primitives.archivist import Archivist
from organvm_engine.primitives.assessor import Assessor
from organvm_engine.primitives.counselor import Counselor
from organvm_engine.primitives.guardian import Guardian, GuardianState, WatchItem
from organvm_engine.primitives.inst_ledger import InstitutionalLedger
from organvm_engine.primitives.mandator import Mandator
from organvm_engine.primitives.registry import PrimitiveRegistry
from organvm_engine.primitives.types import (
    Frame,
    FrameType,
    InstitutionalContext,
    PrincipalPosition,
)


def _default_registry() -> PrimitiveRegistry:
    reg = PrimitiveRegistry()
    reg.register(Assessor())
    reg.register(Guardian())
    reg.register(InstitutionalLedger())
    reg.register(Counselor())
    reg.register(Archivist())
    reg.register(Mandator())
    return reg


# ---------------------------------------------------------------------------
# primitive list
# ---------------------------------------------------------------------------


def cmd_primitive_list(args: argparse.Namespace) -> int:
    reg = _default_registry()
    prims = reg.list_all()
    if getattr(args, "json", False):
        rows = [
            {
                "id": p.PRIMITIVE_ID,
                "name": p.PRIMITIVE_NAME,
                "cluster": p.CLUSTER,
                "default_stakes": p.DEFAULT_STAKES.value,
            }
            for p in prims
        ]
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'ID':<20} {'Name':<15} {'Cluster':<12} {'Stakes'}")
        print("-" * 60)
        for p in prims:
            print(
                f"{p.PRIMITIVE_ID:<20} {p.PRIMITIVE_NAME:<15} "
                f"{p.CLUSTER:<12} {p.DEFAULT_STAKES.value}",
            )
    return 0


# ---------------------------------------------------------------------------
# primitive inspect
# ---------------------------------------------------------------------------


def cmd_primitive_inspect(args: argparse.Namespace) -> int:
    reg = _default_registry()
    prim = reg.get_by_name(args.name)
    if not prim:
        print(f"Unknown primitive: {args.name}", file=sys.stderr)
        return 1
    info = {
        "id": prim.PRIMITIVE_ID,
        "name": prim.PRIMITIVE_NAME,
        "cluster": prim.CLUSTER,
        "default_stakes": prim.DEFAULT_STAKES.value,
        "type": type(prim).__name__,
    }
    if getattr(args, "json", False):
        print(json.dumps(info, indent=2))
    else:
        for k, v in info.items():
            print(f"  {k}: {v}")
    return 0


# ---------------------------------------------------------------------------
# primitive invoke
# ---------------------------------------------------------------------------


def cmd_primitive_invoke(args: argparse.Namespace) -> int:
    reg = _default_registry()
    prim = reg.get_by_name(args.name)
    if not prim:
        print(f"Unknown primitive: {args.name}", file=sys.stderr)
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
    frame_type = FrameType(args.frame) if args.frame else FrameType.OPERATIONAL
    frame = Frame(frame_type=frame_type)
    position = PrincipalPosition()

    result = prim.invoke(context, frame, position)

    if getattr(args, "json", False):
        from dataclasses import asdict
        print(json.dumps(asdict(result), indent=2, default=str))
    else:
        print(f"Primitive: {prim.PRIMITIVE_NAME}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Escalation: {result.escalation_flag}")
        print(f"Mode: {result.execution_mode.value}")
        print(f"Stakes: {result.stakes.value}")
        print("\nOutput:")
        print(json.dumps(result.output, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------------
# primitive guardian *
# ---------------------------------------------------------------------------


def cmd_primitive_guardian_add_watch(args: argparse.Namespace) -> int:
    state = GuardianState()
    item = WatchItem(
        category=args.category,
        description=args.description,
        watched_value=getattr(args, "watched_value", ""),
        threshold=args.threshold,
        direction=args.direction,
        alert_window_days=getattr(args, "alert_window", 7),
    )
    state.add_watch(item)
    print(f"Watch added: {item.item_id} ({item.description})")
    return 0


def cmd_primitive_guardian_watchlist(args: argparse.Namespace) -> int:
    state = GuardianState()
    items = state.get_watchlist()
    if not items:
        print("Watchlist is empty.")
        return 0
    if getattr(args, "json", False):
        from dataclasses import asdict
        print(json.dumps([asdict(i) for i in items], indent=2))
    else:
        for item in items:
            status_marker = "!" if item.status == "triggered" else " "
            print(
                f"  [{status_marker}] {item.item_id} "
                f"[{item.category}] {item.description} "
                f"(threshold={item.threshold}, dir={item.direction})",
            )
    return 0


def cmd_primitive_guardian_check(args: argparse.Namespace) -> int:
    guardian = Guardian()
    context = InstitutionalContext(situation="Manual guardian check")
    frame = Frame(FrameType.OPERATIONAL)
    position = PrincipalPosition()

    result = guardian.invoke(context, frame, position)
    alerts = result.output

    if not alerts:
        print("No alerts triggered.")
        return 0

    print(f"{len(alerts)} alert(s):")
    for alert in alerts:
        sev = alert.get("severity", "info")
        msg = alert.get("message", "")
        marker = "!!!" if sev == "critical" else "! " if sev == "warning" else "  "
        print(f"  {marker} [{sev}] {msg}")
    return 0


# ---------------------------------------------------------------------------
# primitive ledger *
# ---------------------------------------------------------------------------


def cmd_primitive_ledger_record(args: argparse.Namespace) -> int:
    ledger = InstitutionalLedger()
    context = InstitutionalContext(
        situation="Manual ledger entry",
        data={
            "mode": "record",
            "category": args.category,
            "amount": float(args.amount) if args.amount else None,
            "description": getattr(args, "description", ""),
            "direction": getattr(args, "direction", ""),
            "counterparty": getattr(args, "counterparty", ""),
            "recurring": getattr(args, "recurring", False),
            "frequency": getattr(args, "frequency", "one-time"),
        },
    )
    frame = Frame(FrameType.FINANCIAL)
    position = PrincipalPosition()

    result = ledger.invoke(context, frame, position)
    entry = result.output
    print(f"Recorded: {entry.get('entry_id', '')} — {args.category} ${args.amount}")
    return 0


def cmd_primitive_ledger_snapshot(args: argparse.Namespace) -> int:
    ledger = InstitutionalLedger()
    context = InstitutionalContext(
        situation="Economic snapshot",
        data={"mode": "snapshot"},
    )
    frame = Frame(FrameType.FINANCIAL)
    position = PrincipalPosition()

    result = ledger.invoke(context, frame, position)
    snap = result.output

    if getattr(args, "json", False):
        print(json.dumps(snap, indent=2, default=str))
    else:
        print(f"  Net position:   ${snap.get('net_position', 0):.2f}")
        print(f"  Total assets:   ${snap.get('total_assets', 0):.2f}")
        print(f"  Total liabilities: ${snap.get('total_liabilities', 0):.2f}")
        print(f"  Monthly inflow: ${snap.get('monthly_inflow', 0):.2f}")
        print(f"  Monthly outflow: ${snap.get('monthly_outflow', 0):.2f}")
        runway = snap.get("runway_months", 0)
        if runway == float("inf"):
            print("  Runway:         ∞ (positive cash flow)")
        else:
            print(f"  Runway:         {runway:.1f} months")
        alerts = snap.get("alerts", [])
        if alerts:
            print("\n  Alerts:")
            for a in alerts:
                print(f"    ⚠ {a}")
    return 0


def cmd_primitive_ledger_entries(args: argparse.Namespace) -> int:
    ledger = InstitutionalLedger()
    entries = ledger.store.load_entries()

    category = getattr(args, "category", "")
    if category:
        entries = [e for e in entries if e.category == category]

    if not entries:
        print("No entries found.")
        return 0

    if getattr(args, "json", False):
        from dataclasses import asdict
        print(json.dumps([asdict(e) for e in entries], indent=2))
    else:
        for e in entries[-20:]:  # last 20
            amt = f"${e.amount:.2f}" if e.amount else "N/A"
            print(
                f"  {e.entry_id} [{e.category}] {e.description[:50]} "
                f"— {amt} ({e.direction})",
            )
    return 0
