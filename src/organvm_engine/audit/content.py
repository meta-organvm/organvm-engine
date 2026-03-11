"""Layer 5: Content artifact verification.

Checks that declared artifacts actually exist: README.md, CI workflows
on disk, CHANGELOG for platinum repos, docs/ directory state.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.audit.types import Finding, LayerReport, Severity
from organvm_engine.ci.mandate import _check_ci_workflows, _resolve_repo_path
from organvm_engine.organ_config import registry_key_to_dir
from organvm_engine.registry.query import all_repos


def audit_content(
    registry: dict,
    workspace: Path,
    scope_organ: str | None = None,
) -> LayerReport:
    """Run content artifact audit.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root path.
        scope_organ: If set, restrict to this registry key.

    Returns:
        LayerReport with content findings.
    """
    report = LayerReport(layer="content")
    key_to_dir = registry_key_to_dir()

    for organ_key, repo_data in all_repos(registry):
        if scope_organ and organ_key != scope_organ:
            continue

        name = repo_data.get("name", "")
        org = repo_data.get("org", "")
        impl_status = repo_data.get("implementation_status", "")
        if not name or impl_status == "ARCHIVED":
            continue

        repo_path = _resolve_repo_path(org, name, organ_key, workspace, key_to_dir)
        if repo_path is None:
            continue  # filesystem layer handles missing repos

        # README.md
        has_readme = (
            (repo_path / "README.md").is_file()
            or (repo_path / "readme.md").is_file()
        )
        if not has_readme:
            report.findings.append(Finding(
                severity=Severity.WARNING,
                layer="content",
                organ=organ_key,
                repo=name,
                message="No README.md found",
                suggestion="Create a README.md with project overview",
            ))

        # CI workflow drift
        registry_ci = repo_data.get("ci_workflow", "")
        disk_workflows = _check_ci_workflows(repo_path)
        if registry_ci and not disk_workflows:
            report.findings.append(Finding(
                severity=Severity.WARNING,
                layer="content",
                organ=organ_key,
                repo=name,
                message=(
                    f"Registry claims CI workflow '{registry_ci}' "
                    f"but no workflow files on disk"
                ),
            ))
        elif not registry_ci and disk_workflows:
            report.findings.append(Finding(
                severity=Severity.INFO,
                layer="content",
                organ=organ_key,
                repo=name,
                message=(
                    f"Has CI workflows on disk ({', '.join(disk_workflows)}) "
                    f"but registry ci_workflow is empty"
                ),
                suggestion="Update registry ci_workflow field",
            ))

        # CHANGELOG for platinum repos
        is_platinum = repo_data.get("platinum_status", False)
        if is_platinum:
            has_changelog = (
                (repo_path / "CHANGELOG.md").is_file()
                or (repo_path / "CHANGELOG").is_file()
                or (repo_path / "CHANGES.md").is_file()
            )
            if not has_changelog:
                report.findings.append(Finding(
                    severity=Severity.WARNING,
                    layer="content",
                    organ=organ_key,
                    repo=name,
                    message="Platinum repo has no CHANGELOG",
                    suggestion="Add CHANGELOG.md to maintain release history",
                ))

        # docs/ directory for flagship repos
        tier = repo_data.get("tier", "")
        if tier == "flagship" and not (repo_path / "docs").is_dir():
                report.findings.append(Finding(
                    severity=Severity.INFO,
                    layer="content",
                    organ=organ_key,
                    repo=name,
                    message="Flagship repo has no docs/ directory",
                ))

    return report
