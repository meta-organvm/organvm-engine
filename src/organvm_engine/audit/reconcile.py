"""Layer 2: Registry ↔ Seed reconciliation.

Cross-checks registry entries against discovered seed.yaml files.
Detects count mismatches, repos in one source but not the other,
and field drift between registry and seed declarations.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.audit.types import Finding, LayerReport, Severity
from organvm_engine.organ_config import registry_key_to_dir
from organvm_engine.registry.query import all_repos
from organvm_engine.seed.discover import discover_seeds
from organvm_engine.seed.reader import read_seed


def audit_reconcile(
    registry: dict,
    workspace: Path,
    scope_organ: str | None = None,
) -> LayerReport:
    """Run registry↔seed reconciliation audit.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root path.
        scope_organ: If set, restrict to this registry key.

    Returns:
        LayerReport with reconciliation findings.
    """
    report = LayerReport(layer="reconcile")
    key_to_dir = registry_key_to_dir()

    # Build registry index: repo_name → (organ_key, repo_data)
    registry_index: dict[str, tuple[str, dict]] = {}
    for organ_key, repo_data in all_repos(registry):
        if scope_organ and organ_key != scope_organ:
            continue
        name = repo_data.get("name", "")
        if name:
            registry_index[name] = (organ_key, repo_data)

    # Build seed index: repo_name → (organ_key, seed_data, seed_path)
    seed_index: dict[str, tuple[str, dict, Path]] = {}
    seed_paths = discover_seeds(workspace)
    for seed_path in seed_paths:
        try:
            seed_data = read_seed(seed_path)
        except Exception:
            report.findings.append(Finding(
                severity=Severity.WARNING,
                layer="reconcile",
                organ="",
                repo=seed_path.parent.name,
                message=f"Cannot parse seed.yaml at {seed_path}",
            ))
            continue

        repo_name = seed_data.get("repo", seed_path.parent.name)

        # Determine organ key from seed path
        organ_dir_name = seed_path.parent.parent.name
        dir_to_key = {v: k for k, v in key_to_dir.items()}
        organ_key = dir_to_key.get(organ_dir_name, "")

        if scope_organ and organ_key != scope_organ:
            continue

        seed_index[repo_name] = (organ_key, seed_data, seed_path)

    # Count comparison
    reg_count = len(registry_index)
    seed_count = len(seed_index)
    if reg_count != seed_count:
        report.findings.append(Finding(
            severity=Severity.WARNING,
            layer="reconcile",
            organ="SYSTEM",
            repo="",
            message=(
                f"Registry has {reg_count} repos, seeds have {seed_count} "
                f"(delta: {seed_count - reg_count:+d})"
            ),
            suggestion="Align by registering new seeds or removing stale entries",
        ))

    # Repos in registry but not in seeds
    for name in sorted(set(registry_index) - set(seed_index)):
        organ_key = registry_index[name][0]
        report.findings.append(Finding(
            severity=Severity.WARNING,
            layer="reconcile",
            organ=organ_key,
            repo=name,
            message="In registry but no seed.yaml found",
            suggestion="Create seed.yaml for this repo",
        ))

    # Repos in seeds but not in registry
    for name in sorted(set(seed_index) - set(registry_index)):
        organ_key = seed_index[name][0]
        report.findings.append(Finding(
            severity=Severity.CRITICAL,
            layer="reconcile",
            organ=organ_key,
            repo=name,
            message="Has seed.yaml but not in registry",
            suggestion="Register with `organvm registry update`",
        ))

    # Field drift for repos in both
    for name in sorted(set(registry_index) & set(seed_index)):
        reg_organ, reg_data = registry_index[name]
        seed_organ, seed_data, _ = seed_index[name]

        # Organ mismatch
        seed_declared_organ = seed_data.get("organ", "")
        if seed_declared_organ and seed_declared_organ != reg_organ:
            # Normalize: seed might use short key, registry uses full key
            from organvm_engine.organ_config import organ_aliases
            aliases = organ_aliases()
            seed_registry_key = aliases.get(seed_declared_organ, seed_declared_organ)
            if seed_registry_key != reg_organ:
                report.findings.append(Finding(
                    severity=Severity.WARNING,
                    layer="reconcile",
                    organ=reg_organ,
                    repo=name,
                    message=(
                        f"Organ mismatch: registry says '{reg_organ}', "
                        f"seed says '{seed_declared_organ}'"
                    ),
                ))

        # Tier drift
        reg_tier = reg_data.get("tier", "")
        seed_tier = seed_data.get("tier", "")
        if reg_tier and seed_tier and reg_tier != seed_tier:
            report.findings.append(Finding(
                severity=Severity.INFO,
                layer="reconcile",
                organ=reg_organ,
                repo=name,
                message=f"Tier drift: registry='{reg_tier}', seed='{seed_tier}'",
            ))

        # Status drift
        reg_status = reg_data.get("promotion_status", "")
        seed_status = seed_data.get("promotion_status", "")
        if reg_status and seed_status and reg_status != seed_status:
            report.findings.append(Finding(
                severity=Severity.INFO,
                layer="reconcile",
                organ=reg_organ,
                repo=name,
                message=(
                    f"Promotion status drift: "
                    f"registry='{reg_status}', seed='{seed_status}'"
                ),
            ))

    return report
