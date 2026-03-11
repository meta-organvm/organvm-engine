"""CLI handler for the audit command group."""

from __future__ import annotations

from organvm_engine.audit import AUDIT_LAYERS
from organvm_engine.paths import resolve_workspace


def _load_and_run(args, layers=None, scope_organ=None, scope_repo=None):
    """Shared helper: load registry, resolve workspace, run audit."""
    from organvm_engine.audit.coordinator import run_audit
    from organvm_engine.registry.loader import load_registry

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return None
    registry = load_registry(args.registry)
    organ = scope_organ or getattr(args, "organ", None)

    # Resolve organ alias to registry key
    if organ:
        from organvm_engine.organ_config import organ_aliases
        aliases = organ_aliases()
        organ = aliases.get(organ, organ)

    return run_audit(
        registry=registry,
        workspace=workspace,
        scope_organ=organ,
        scope_repo=scope_repo,
        layers=layers,
    )


def _output_report(report, args) -> int:
    """Format and output a report."""
    from organvm_engine.audit.report import format_json, format_text

    text = format_json(report) if getattr(args, "json", False) else format_text(report)

    output = getattr(args, "output", None)
    if output:
        from pathlib import Path
        Path(output).write_text(text)
        print(f"Report written to {output}")
    else:
        print(text)

    return 1 if report.critical_count > 0 else 0


def cmd_audit_full(args) -> int:
    """Run all 6 audit layers."""
    report = _load_and_run(args)
    if report is None:
        return 1
    return _output_report(report, args)


def cmd_audit_layer(args) -> int:
    """Run a single audit layer."""
    layer = args.layer
    if layer not in AUDIT_LAYERS:
        print(f"Error: unknown layer '{layer}'. Choose from: {', '.join(AUDIT_LAYERS)}")
        return 1
    report = _load_and_run(args, layers=[layer])
    if report is None:
        return 1
    return _output_report(report, args)


def cmd_audit_repo(args) -> int:
    """Run audit scoped to a single repo."""
    report = _load_and_run(args, scope_repo=args.repo)
    if report is None:
        return 1
    return _output_report(report, args)


def cmd_audit_organ(args) -> int:
    """Run audit scoped to an organ."""
    report = _load_and_run(args, scope_organ=args.organ_key)
    if report is None:
        return 1
    return _output_report(report, args)


def cmd_audit_absorption(args) -> int:
    """Run only the absorption layer with optional verbose output."""
    from organvm_engine.audit.absorption import audit_absorption
    from organvm_engine.audit.types import InfrastructureAuditReport

    workspace = resolve_workspace(args)
    if not workspace:
        print("Error: cannot resolve workspace")
        return 1

    verbose = getattr(args, "verbose", False)
    layer_report = audit_absorption(workspace, verbose=verbose)

    report = InfrastructureAuditReport()
    report.layers["absorption"] = layer_report

    return _output_report(report, args)
