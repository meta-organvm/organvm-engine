"""Workspace-wide ecosystem scaffold + audit."""

from __future__ import annotations

from pathlib import Path

import yaml

from organvm_engine.ecosystem import ECOSYSTEM_FILENAME
from organvm_engine.ecosystem.discover import discover_ecosystems
from organvm_engine.ecosystem.reader import read_ecosystem
from organvm_engine.ecosystem.templates import scaffold_ecosystem
from organvm_engine.organ_config import organ_dir_map
from organvm_engine.paths import workspace_root
from organvm_engine.registry.loader import load_registry
from organvm_engine.registry.query import all_repos
from organvm_engine.seed.discover import discover_seeds
from organvm_engine.seed.reader import read_seed


def sync_ecosystems(
    registry_path: str | Path | None = None,
    workspace: str | Path | None = None,
    organ: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Scaffold ecosystem.yaml for products that don't have one.

    Args:
        registry_path: Path to registry-v2.json.
        workspace: Workspace root.
        organ: CLI short key to filter to one organ.
        dry_run: If True, report what would be created without writing.

    Returns:
        Summary dict with created, skipped, and error counts.
    """
    ws = Path(workspace) if workspace else workspace_root()
    registry = load_registry(registry_path)

    # Find existing ecosystem files
    existing = discover_ecosystems(ws, organ=organ)
    existing_repos: set[str] = set()
    for eco_path in existing:
        try:
            data = read_ecosystem(eco_path)
            existing_repos.add(data.get("repo", eco_path.parent.name))
        except Exception:
            existing_repos.add(eco_path.parent.name)

    # Find seed files for cross-referencing
    seed_map: dict[str, dict] = {}
    seeds = discover_seeds(ws)
    for seed_path in seeds:
        try:
            sd = read_seed(seed_path)
            seed_map[sd.get("repo", seed_path.parent.name)] = sd
        except Exception:
            pass

    # Load kerygma profiles if available
    kerygma_map = _load_kerygma_profiles(ws)

    # Resolve organ filter
    dir_map = organ_dir_map()
    if organ:
        target_dir = dir_map.get(organ)
        filter_organ_key = None
        for key, val in dir_map.items():
            if val == target_dir:
                from organvm_engine.organ_config import organ_aliases
                aliases = organ_aliases()
                filter_organ_key = aliases.get(key)
                break
    else:
        filter_organ_key = None

    created: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for organ_key, repo_data in all_repos(registry):
        repo_name = repo_data.get("name", "")
        if not repo_name:
            continue

        # Filter by organ
        if filter_organ_key and organ_key != filter_organ_key:
            continue

        # Skip if already has ecosystem
        if repo_name in existing_repos:
            skipped.append(repo_name)
            continue

        # Skip archived/infrastructure
        tier = repo_data.get("tier", "standard")
        if tier in ("archive", "infrastructure"):
            skipped.append(repo_name)
            continue

        # Find the repo directory
        from organvm_engine.organ_config import registry_key_to_dir
        rk2d = registry_key_to_dir()
        organ_dir_name = rk2d.get(organ_key)
        if not organ_dir_name:
            continue
        repo_dir = ws / organ_dir_name / repo_name
        if not repo_dir.is_dir():
            continue

        # Derive organ short key
        organ_short = _organ_key_to_short(organ_key)

        # Build scaffold
        seed = seed_map.get(repo_name)
        kerygma = kerygma_map.get(repo_name)

        try:
            eco_data = scaffold_ecosystem(
                repo_name=repo_name,
                organ=organ_short,
                registry_data=repo_data,
                seed_data=seed,
                kerygma_profile=kerygma,
                display_name=repo_data.get("description"),
            )
        except Exception as e:
            errors.append(f"{repo_name}: {e}")
            continue

        eco_path = repo_dir / ECOSYSTEM_FILENAME
        if dry_run:
            created.append(repo_name)
        else:
            try:
                with eco_path.open("w") as f:
                    yaml.dump(eco_data, f, default_flow_style=False, sort_keys=False)
                created.append(repo_name)
            except Exception as e:
                errors.append(f"{repo_name}: write failed: {e}")

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def _organ_key_to_short(organ_key: str) -> str:
    """Convert registry key (ORGAN-III) to CLI short key (III)."""
    from organvm_engine.organ_config import ORGANS
    for short_key, meta in ORGANS.items():
        if meta["registry_key"] == organ_key:
            return short_key
    return organ_key


def _load_kerygma_profiles(workspace: Path) -> dict[str, dict]:
    """Load kerygma profiles from ORGAN-VII if available."""
    profiles_dir = workspace / "organvm-vii-kerygma" / "kerygma-profiles" / "profiles"
    if not profiles_dir.is_dir():
        return {}

    kerygma: dict[str, dict] = {}
    for profile_path in sorted(profiles_dir.glob("*.yaml")):
        try:
            with profile_path.open() as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                repo = data.get("repo", profile_path.stem)
                kerygma[repo] = data
        except Exception:
            pass

    return kerygma
