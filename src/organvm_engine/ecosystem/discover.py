"""Discover ecosystem.yaml files across the workspace."""

from __future__ import annotations

from pathlib import Path

from organvm_engine.ecosystem import ECOSYSTEM_FILENAME
from organvm_engine.organ_config import organ_org_dirs
from organvm_engine.paths import workspace_root

ORGAN_ORGS = organ_org_dirs()


def discover_ecosystems(
    workspace: Path | str | None = None,
    organ: str | None = None,
) -> list[Path]:
    """Walk the workspace and find all ecosystem.yaml files.

    Structure: ~/Workspace/<org>/<repo>/ecosystem.yaml

    Args:
        workspace: Root workspace directory. Defaults to ~/Workspace.
        organ: CLI short key (e.g. "III") to filter to one organ.

    Returns:
        Sorted list of paths to ecosystem.yaml files found.
    """
    ws = Path(workspace) if workspace else workspace_root()

    if organ:
        from organvm_engine.organ_config import organ_dir_map
        dir_map = organ_dir_map()
        organ_dir_name = dir_map.get(organ)
        if not organ_dir_name:
            return []
        scan_orgs = [organ_dir_name]
    else:
        scan_orgs = ORGAN_ORGS

    ecosystems: list[Path] = []
    for org_name in scan_orgs:
        org_dir = ws / org_name
        if not org_dir.is_dir():
            continue
        for repo_dir in sorted(org_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            eco_file = repo_dir / ECOSYSTEM_FILENAME
            if eco_file.is_file():
                ecosystems.append(eco_file)

    return sorted(ecosystems)
