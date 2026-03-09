"""Scaffold pillar DNA from ecosystem.yaml and product type inference.

Generates per-pillar lifecycle contracts by merging product-type defaults
with repo-specific data from ecosystem.yaml arms.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.ecosystem import HEADER_FIELDS
from organvm_engine.ecosystem.pillar_dna import write_pillar_dna
from organvm_engine.ecosystem.product_types import (
    DEFAULT_CRIT_PROMPTS,
    DEFAULT_GEN_PROMPTS,
    get_pillar_defaults,
    infer_product_type,
)


def _infer_lifecycle_stage(arms: list[dict]) -> str:
    """Infer lifecycle stage from arm statuses."""
    statuses = {a.get("status", "not_started") for a in arms}
    if "live" in statuses:
        return "live"
    if "in_progress" in statuses:
        return "building"
    if "planned" in statuses:
        return "planning"
    return "conception"


def _build_gates() -> dict[str, list[str]]:
    """Return default lifecycle gates."""
    return {
        "research_to_planning": [
            "At least one landscape snapshot exists",
            "3+ competitors profiled",
        ],
        "planning_to_building": [
            "Channel strategy artifact exists",
            "Priority arms identified with next_actions",
        ],
        "building_to_live": [
            "At least one arm has status: live",
        ],
    }


def scaffold_pillar_dna(
    ecosystem_data: dict,
    seed_data: dict | None = None,
    registry_data: dict | None = None,
) -> dict[str, dict]:
    """Generate per-pillar DNA from ecosystem.yaml + product type inference.

    Args:
        ecosystem_data: Parsed ecosystem.yaml.
        seed_data: Parsed seed.yaml (optional).
        registry_data: Registry entry for this repo (optional).

    Returns:
        Dict mapping pillar name to DNA dict.
    """
    product_type = infer_product_type(seed_data, registry_data)

    # Extract pillars from ecosystem.yaml
    pillars: dict[str, list[dict]] = {
        k: v for k, v in ecosystem_data.items()
        if k not in HEADER_FIELDS and isinstance(v, list)
    }

    result: dict[str, dict] = {}
    for pillar_name, arms in pillars.items():
        defaults = get_pillar_defaults(product_type, pillar_name)
        stage = _infer_lifecycle_stage(arms)

        dna: dict = {
            "schema_version": "1.0",
            "pillar": pillar_name,
            "product_type": product_type,
            "lifecycle_stage": stage,
        }

        # Research section
        scan_scope = defaults.get("scan_scope", []) if defaults else []
        dna["research"] = {
            "scan_scope": scan_scope,
            "competitors": [],
            "cadence": "monthly",
        }

        # Artifacts
        artifacts = defaults.get("artifacts", []) if defaults else []
        dna["artifacts"] = artifacts

        # Gen/crit prompts from defaults
        dna["gen_prompts"] = DEFAULT_GEN_PROMPTS.get(pillar_name, [])
        dna["crit_prompts"] = DEFAULT_CRIT_PROMPTS.get(pillar_name, [])

        # Gates
        dna["gates"] = _build_gates()

        # Signals
        dna["signals"] = {
            "emits": [
                "signal:pillar-stage-change",
                "signal:new-competitor-found",
            ],
            "listens": [
                "signal:ecosystem-arm-live",
                "signal:market-shift-detected",
            ],
        }

        result[pillar_name] = dna

    return result


def scaffold_repo_ecosystem(
    repo_path: Path | str,
    ecosystem_data: dict,
    seed_data: dict | None = None,
    registry_data: dict | None = None,
    dry_run: bool = True,
) -> dict:
    """Create full ecosystem/ directory structure for a repo.

    Args:
        repo_path: Path to the repo root.
        ecosystem_data: Parsed ecosystem.yaml.
        seed_data: Parsed seed.yaml (optional).
        registry_data: Registry entry (optional).
        dry_run: If True, don't write files.

    Returns:
        Dict with 'pillar_dnas' (dict of pillar→dna), 'written' (list of paths).
    """
    pillar_dnas = scaffold_pillar_dna(ecosystem_data, seed_data, registry_data)

    written: list[str] = []
    repo = Path(repo_path)

    if not dry_run:
        # Create directory structure
        for pillar_name in pillar_dnas:
            (repo / "ecosystem" / "snapshots" / pillar_name).mkdir(
                parents=True, exist_ok=True,
            )
            (repo / "ecosystem" / "intelligence" / pillar_name).mkdir(
                parents=True, exist_ok=True,
            )
            path = write_pillar_dna(repo, pillar_name, pillar_dnas[pillar_name])
            written.append(str(path))

    return {
        "pillar_dnas": pillar_dnas,
        "written": written,
        "dry_run": dry_run,
    }


def sync_pillar_dnas(
    workspace: Path | str,
    organ: str | None = None,
    dry_run: bool = True,
) -> dict:
    """Scaffold pillar DNA for all repos with ecosystem.yaml.

    Args:
        workspace: Workspace root.
        organ: Optional organ filter.
        dry_run: If True, don't write files.

    Returns:
        Dict with 'scaffolded', 'skipped', 'errors' lists.
    """
    from organvm_engine.ecosystem.discover import discover_ecosystems
    from organvm_engine.ecosystem.pillar_dna import list_pillar_dnas
    from organvm_engine.ecosystem.reader import read_ecosystem
    from organvm_engine.seed.reader import read_seed

    eco_paths = discover_ecosystems(workspace, organ=organ)

    scaffolded: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for eco_path in eco_paths:
        repo_path = eco_path.parent
        repo_name = repo_path.name

        try:
            eco_data = read_ecosystem(eco_path)
        except Exception as exc:
            errors.append(f"{repo_name}: {exc}")
            continue

        # Skip if pillar DNA already exists
        existing = list_pillar_dnas(repo_path)
        if existing:
            skipped.append(repo_name)
            continue

        # Try to load seed
        seed = None
        seed_path = repo_path / "seed.yaml"
        if seed_path.is_file():
            import contextlib

            with contextlib.suppress(Exception):
                seed = read_seed(seed_path)

        try:
            scaffold_repo_ecosystem(
                repo_path=repo_path,
                ecosystem_data=eco_data,
                seed_data=seed,
                dry_run=dry_run,
            )
            scaffolded.append(repo_name)
        except Exception as exc:
            errors.append(f"{repo_name}: {exc}")

    return {
        "scaffolded": scaffolded,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }
