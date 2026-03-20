"""Split and merge registry-v2.json into per-organ files.

The split format:
    <dir>/_meta.json          — version, schema_version, summary (no organs)
    <dir>/ORGAN-I.json        — {name, repositories, ...} for ORGAN-I
    <dir>/ORGAN-II.json       — {name, repositories, ...} for ORGAN-II
    <dir>/META-ORGANVM.json   — etc.

merge_registry() reassembles the exact same dict structure as
the original monolithic registry-v2.json.
"""

from __future__ import annotations

import json
from pathlib import Path


def split_registry(
    registry: dict,
    output_dir: Path | str,
    *,
    min_repo_count: int = 0,
) -> list[Path]:
    """Split a monolithic registry into per-organ files + metadata.

    Args:
        registry: Loaded registry dict.
        output_dir: Directory to write per-organ files into.
        min_repo_count: If > 0, refuse to split registries with fewer
            repos than this threshold (production safety guard).

    Returns:
        List of files written.

    Raises:
        ValueError: If min_repo_count guard is triggered.
    """
    out = Path(output_dir)

    # Production safety guard (mirrors loader.save_registry's 50-repo guard)
    if min_repo_count > 0:
        total = sum(
            len(organ.get("repositories", []))
            for organ in registry.get("organs", {}).values()
            if isinstance(organ, dict)
        )
        if total < min_repo_count:
            raise ValueError(
                f"Refusing to split registry with only {total} repos "
                f"(minimum: {min_repo_count}). This looks like test fixture data.",
            )

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Write _meta.json (everything except organs)
    meta = {k: v for k, v in registry.items() if k != "organs"}
    meta_path = out / "_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    written.append(meta_path)

    # Write per-organ files
    for organ_key, organ_data in registry.get("organs", {}).items():
        organ_path = out / f"{organ_key}.json"
        organ_path.write_text(json.dumps(organ_data, indent=2) + "\n")
        written.append(organ_path)

    return written


def merge_registry(registry_dir: Path | str) -> dict:
    """Merge per-organ files back into a monolithic registry dict.

    Args:
        registry_dir: Directory containing _meta.json + per-organ files.

    Returns:
        Merged registry dict (same structure as registry-v2.json).

    Raises:
        FileNotFoundError: If _meta.json is missing.
    """
    rdir = Path(registry_dir)
    meta_path = rdir / "_meta.json"

    if not meta_path.is_file():
        raise FileNotFoundError(f"No _meta.json found in {rdir}")

    registry = json.loads(meta_path.read_text())
    registry["organs"] = {}

    for organ_file in sorted(rdir.glob("*.json")):
        if organ_file.name == "_meta.json":
            continue
        organ_key = organ_file.stem
        organ_data = json.loads(organ_file.read_text())
        registry["organs"][organ_key] = organ_data

    return registry
