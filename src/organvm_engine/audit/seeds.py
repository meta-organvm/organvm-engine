"""Layer 3: Seed completeness and identity validation.

Checks that each seed.yaml has required fields, flagship repos
declare produces/consumes, and identity matches directory structure.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.audit.types import Finding, LayerReport, Severity
from organvm_engine.organ_config import registry_key_to_dir
from organvm_engine.registry.query import all_repos
from organvm_engine.seed.discover import discover_seeds
from organvm_engine.seed.reader import get_consumes, get_produces, read_seed

# Required fields in every seed.yaml
REQUIRED_FIELDS = ("repo", "organ", "tier")

# Additional fields expected for flagship repos
FLAGSHIP_FIELDS = ("description",)


def audit_seeds(
    registry: dict,
    workspace: Path,
    scope_organ: str | None = None,
) -> LayerReport:
    """Run seed completeness audit.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root path.
        scope_organ: If set, restrict to this registry key.

    Returns:
        LayerReport with seed validation findings.
    """
    report = LayerReport(layer="seeds")
    key_to_dir = registry_key_to_dir()
    dir_to_key = {v: k for k, v in key_to_dir.items()}

    # Build flagship set from registry
    flagships: set[str] = set()
    for _, repo_data in all_repos(registry):
        if repo_data.get("tier") == "flagship":
            flagships.add(repo_data.get("name", ""))

    seed_paths = discover_seeds(workspace)
    for seed_path in seed_paths:
        repo_name = seed_path.parent.name
        organ_dir_name = seed_path.parent.parent.name
        organ_key = dir_to_key.get(organ_dir_name, "")

        if scope_organ and organ_key != scope_organ:
            continue

        try:
            seed_data = read_seed(seed_path)
        except Exception as exc:
            report.findings.append(Finding(
                severity=Severity.CRITICAL,
                layer="seeds",
                organ=organ_key,
                repo=repo_name,
                message=f"Cannot parse seed.yaml: {exc}",
            ))
            continue

        # Required fields
        for field_name in REQUIRED_FIELDS:
            if not seed_data.get(field_name):
                report.findings.append(Finding(
                    severity=Severity.WARNING,
                    layer="seeds",
                    organ=organ_key,
                    repo=repo_name,
                    message=f"Missing required field '{field_name}' in seed.yaml",
                ))

        # Identity vs directory
        expected_repo = seed_data.get("repo", "")
        if expected_repo and expected_repo != repo_name:
            report.findings.append(Finding(
                severity=Severity.WARNING,
                layer="seeds",
                organ=organ_key,
                repo=repo_name,
                message=(
                    f"Seed declares repo='{expected_repo}' but directory is "
                    f"'{repo_name}'"
                ),
            ))

        # Flagship checks
        if repo_name in flagships:
            for field_name in FLAGSHIP_FIELDS:
                if not seed_data.get(field_name):
                    report.findings.append(Finding(
                        severity=Severity.INFO,
                        layer="seeds",
                        organ=organ_key,
                        repo=repo_name,
                        message=f"Flagship repo missing '{field_name}' in seed.yaml",
                    ))

            produces = get_produces(seed_data)
            consumes = get_consumes(seed_data)
            if not produces and not consumes:
                report.findings.append(Finding(
                    severity=Severity.WARNING,
                    layer="seeds",
                    organ=organ_key,
                    repo=repo_name,
                    message="Flagship repo has no produces/consumes edges",
                    suggestion="Add produces/consumes declarations to seed.yaml",
                ))

    return report
