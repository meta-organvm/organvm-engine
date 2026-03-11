"""Orchestrate audit layers and build chain-of-command reports.

Runs layers sequentially, composes findings into a unified report,
and supports scope filtering by organ or repo.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.audit import AUDIT_LAYERS
from organvm_engine.audit.types import InfrastructureAuditReport, LayerReport


def run_audit(
    registry: dict,
    workspace: Path,
    corpus_dir: Path | None = None,
    scope_organ: str | None = None,
    scope_repo: str | None = None,
    layers: list[str] | None = None,
) -> InfrastructureAuditReport:
    """Run infrastructure audit across specified layers.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root path.
        corpus_dir: Path to corpus directory (for absorption layer).
        scope_organ: Filter to specific organ registry key.
        scope_repo: Filter to specific repo name.
        layers: Which layers to run. Defaults to all 6.

    Returns:
        InfrastructureAuditReport with all findings.
    """
    report = InfrastructureAuditReport(
        scope_organ=scope_organ,
        scope_repo=scope_repo,
    )

    run_layers = layers or list(AUDIT_LAYERS)

    for layer_name in run_layers:
        if layer_name not in AUDIT_LAYERS:
            continue
        layer_report = _run_layer(
            layer_name, registry, workspace, corpus_dir, scope_organ,
        )
        report.layers[layer_name] = layer_report

    # If scoped to a specific repo, filter findings post-hoc
    if scope_repo:
        for _layer_name, layer_report in report.layers.items():
            layer_report.findings = [
                f for f in layer_report.findings
                if f.repo in (scope_repo, "")
                or scope_repo in f.repo  # handle org/repo format
            ]

    return report


def _run_layer(
    layer_name: str,
    registry: dict,
    workspace: Path,
    corpus_dir: Path | None,
    scope_organ: str | None,
) -> LayerReport:
    """Run a single audit layer."""
    if layer_name == "filesystem":
        from organvm_engine.audit.filesystem import audit_filesystem
        return audit_filesystem(registry, workspace, scope_organ)

    if layer_name == "reconcile":
        from organvm_engine.audit.reconcile import audit_reconcile
        return audit_reconcile(registry, workspace, scope_organ)

    if layer_name == "seeds":
        from organvm_engine.audit.seeds import audit_seeds
        return audit_seeds(registry, workspace, scope_organ)

    if layer_name == "edges":
        from organvm_engine.audit.edges import audit_edges
        return audit_edges(workspace, scope_organ)

    if layer_name == "content":
        from organvm_engine.audit.content import audit_content
        return audit_content(registry, workspace, scope_organ)

    if layer_name == "absorption":
        from organvm_engine.audit.absorption import audit_absorption
        return audit_absorption(workspace, corpus_dir)

    return LayerReport(layer=layer_name)
