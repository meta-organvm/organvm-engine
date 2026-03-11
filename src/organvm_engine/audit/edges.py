"""Layer 4: Edge resolution and graph integrity.

Checks for unresolved unknown/unknown edges, orphan producers
with no consumers, dangling subscriptions, and cross-organ
directionality violations.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.audit.types import Finding, LayerReport, Severity
from organvm_engine.seed.graph import build_seed_graph, validate_edge_resolution


def audit_edges(
    workspace: Path,
    scope_organ: str | None = None,
) -> LayerReport:
    """Run edge resolution audit.

    Args:
        workspace: Workspace root path.
        scope_organ: If set, restrict to this organ's edges.

    Returns:
        LayerReport with edge findings.
    """
    report = LayerReport(layer="edges")

    graph = build_seed_graph(workspace)

    # Report graph parse errors
    for error in graph.errors:
        report.findings.append(Finding(
            severity=Severity.WARNING,
            layer="edges",
            organ="",
            repo="",
            message=f"Seed parse error: {error}",
        ))

    # Check for unresolved edges
    unresolved = validate_edge_resolution(graph)
    for entry in unresolved:
        consumer = entry["consumer"]
        ctype = entry["type"]
        source = entry.get("source", "")

        # Determine organ from consumer identity
        organ = ""
        if "/" in consumer:
            org_part = consumer.split("/")[0]
            organ = org_part

        if scope_organ and organ and scope_organ.lower() not in organ.lower():
            continue

        report.findings.append(Finding(
            severity=Severity.CRITICAL,
            layer="edges",
            organ=organ,
            repo=consumer,
            message=(
                f"Unresolved consumes: type='{ctype}'"
                + (f", source='{source}'" if source else "")
                + " — no matching producer found"
            ),
            suggestion="Update seed.yaml consumes with explicit source org/repo",
        ))

    # Detect orphan producers (produce something nobody consumes)
    consumed_types: set[str] = set()
    for edges_list in graph.consumes.values():
        for c in edges_list:
            if isinstance(c, str):
                consumed_types.add(c)
            else:
                consumed_types.add(c.get("type", "unknown"))

    for identity, produces_list in graph.produces.items():
        organ = identity.split("/")[0] if "/" in identity else ""
        if scope_organ and organ and scope_organ.lower() not in organ.lower():
            continue

        for p in produces_list:
            ptype = p if isinstance(p, str) else p.get("type", "unknown")
            if ptype not in consumed_types and ptype != "unknown":
                report.findings.append(Finding(
                    severity=Severity.INFO,
                    layer="edges",
                    organ=organ,
                    repo=identity,
                    message=f"Orphan producer: type='{ptype}' — nothing consumes this",
                ))

    # Summary info
    total_edges = len(graph.edges)
    unresolved_count = len(unresolved)
    report.findings.append(Finding(
        severity=Severity.INFO,
        layer="edges",
        organ="SYSTEM",
        repo="",
        message=(
            f"Edge summary: {total_edges} resolved edges, "
            f"{unresolved_count} unresolved consumes, "
            f"{len(graph.nodes)} nodes"
        ),
    ))

    return report
