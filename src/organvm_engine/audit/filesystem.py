"""Layer 1: Filesystem verification.

Checks that repos declared in the registry exist on disk,
detects orphan directories not in the registry, and verifies
basic repo structure (.git/, seed.yaml presence).
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.audit.types import Finding, LayerReport, Severity
from organvm_engine.organ_config import registry_key_to_dir
from organvm_engine.registry.query import all_repos


def audit_filesystem(
    registry: dict,
    workspace: Path,
    scope_organ: str | None = None,
) -> LayerReport:
    """Run filesystem layer audit.

    Args:
        registry: Loaded registry dict.
        workspace: Workspace root path.
        scope_organ: If set, restrict to this registry key (e.g. "ORGAN-I").

    Returns:
        LayerReport with filesystem findings.
    """
    report = LayerReport(layer="filesystem")
    key_to_dir = registry_key_to_dir()

    # Build set of (organ_key, repo_name) from registry
    registry_repos: dict[str, set[str]] = {}
    for organ_key, repo_data in all_repos(registry):
        if scope_organ and organ_key != scope_organ:
            continue
        registry_repos.setdefault(organ_key, set()).add(repo_data.get("name", ""))

    # Check each registry repo exists on disk
    for organ_key, repo_names in registry_repos.items():
        organ_dir_name = key_to_dir.get(organ_key)
        if not organ_dir_name:
            report.findings.append(Finding(
                severity=Severity.WARNING,
                layer="filesystem",
                organ=organ_key,
                repo="",
                message=f"No directory mapping for organ key '{organ_key}'",
            ))
            continue

        organ_dir = workspace / organ_dir_name
        if not organ_dir.is_dir():
            report.findings.append(Finding(
                severity=Severity.CRITICAL,
                layer="filesystem",
                organ=organ_key,
                repo="",
                message=f"Organ directory '{organ_dir_name}' does not exist on disk",
                suggestion=f"Create {organ_dir} or update organ_config mappings",
            ))
            continue

        for repo_name in sorted(repo_names):
            if not repo_name:
                continue
            repo_path = organ_dir / repo_name
            if not repo_path.is_dir():
                report.findings.append(Finding(
                    severity=Severity.CRITICAL,
                    layer="filesystem",
                    organ=organ_key,
                    repo=repo_name,
                    message=f"Repo '{repo_name}' in registry but not on disk",
                    suggestion="Clone the repo or remove from registry",
                ))
                continue

            # Check .git presence
            if not (repo_path / ".git").exists():
                report.findings.append(Finding(
                    severity=Severity.WARNING,
                    layer="filesystem",
                    organ=organ_key,
                    repo=repo_name,
                    message="Directory exists but has no .git — not a git repo",
                ))

            # Check seed.yaml presence
            if not (repo_path / "seed.yaml").is_file():
                report.findings.append(Finding(
                    severity=Severity.WARNING,
                    layer="filesystem",
                    organ=organ_key,
                    repo=repo_name,
                    message="No seed.yaml found",
                    suggestion="Create seed.yaml with `organvm seed scaffold`",
                ))

    # Detect orphan directories (on disk but not in registry)
    for organ_key, organ_dir_name in key_to_dir.items():
        if scope_organ and organ_key != scope_organ:
            continue
        organ_dir = workspace / organ_dir_name
        if not organ_dir.is_dir():
            continue

        registered = registry_repos.get(organ_key, set())
        try:
            for entry in sorted(organ_dir.iterdir()):
                if not entry.is_dir():
                    continue
                name = entry.name
                # Skip hidden dirs and common non-repo dirs
                if name.startswith(".") or name in ("node_modules", "__pycache__", ".venv"):
                    continue
                if name not in registered:
                    report.findings.append(Finding(
                        severity=Severity.INFO,
                        layer="filesystem",
                        organ=organ_key,
                        repo=name,
                        message=f"Directory '{name}' exists on disk but not in registry",
                        suggestion="Register with `organvm registry update` or remove",
                    ))
        except PermissionError:
            report.findings.append(Finding(
                severity=Severity.WARNING,
                layer="filesystem",
                organ=organ_key,
                repo="",
                message=f"Cannot read organ directory '{organ_dir_name}'",
            ))

    return report
