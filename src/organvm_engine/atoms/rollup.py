"""Per-organ rollup from centralized atom pipeline outputs.

Reads JSONL from data/atoms/, aggregates by organ, writes per-organ
rollup JSON to each organ superproject's .atoms/ directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.organ_config import ORGANS

# SHA-256 of empty string — no signal, skip in rollups
_EMPTY_FINGERPRINT_PREFIX = "e3b0c44298fc"


def _dir_to_cli_key() -> dict[str, str]:
    """Map workspace directory names → CLI short keys."""
    return {v["dir"]: k for k, v in ORGANS.items()}


def organ_key_from_slug(project_slug: str) -> str | None:
    """Resolve organ CLI key from a project slug like 'organvm-iii-ergon/some-repo'.

    Returns None for unresolvable slugs (unknown dirs, single-segment slugs).
    """
    parts = project_slug.split("/", 1)
    if len(parts) < 2:
        return None
    dir_name = parts[0]
    lookup = _dir_to_cli_key()
    return lookup.get(dir_name)


@dataclass
class OrganRollup:
    organ_key: str       # "III"
    organ_dir: str       # "organvm-iii-ergon"
    registry_key: str    # "ORGAN-III"

    total_tasks: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    pending_by_repo: dict[str, list[dict]] = field(default_factory=dict)

    cross_organ_links: list[dict] = field(default_factory=list)

    prompt_type_dist: dict[str, int] = field(default_factory=dict)
    session_freq: dict[str, int] = field(default_factory=dict)

    domain_fingerprints: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "organ_key": self.organ_key,
            "organ_dir": self.organ_dir,
            "registry_key": self.registry_key,
            "total_tasks": self.total_tasks,
            "pending_tasks": self.pending_tasks,
            "completed_tasks": self.completed_tasks,
            "pending_by_repo": self.pending_by_repo,
            "cross_organ_links": self.cross_organ_links,
            "prompt_type_dist": self.prompt_type_dist,
            "session_freq": self.session_freq,
            "domain_fingerprints": self.domain_fingerprints,
        }


def _load_jsonl(path: Path) -> list[dict]:
    """Load JSONL file into list of dicts. Returns empty list if missing."""
    if not path.exists():
        return []
    items = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            stripped = raw.strip()
            if stripped:
                items.append(json.loads(stripped))
    return items


def _make_rollup(key: str) -> OrganRollup:
    info = ORGANS[key]
    return OrganRollup(
        organ_key=key,
        organ_dir=info["dir"],
        registry_key=info["registry_key"],
    )


def build_rollups(atoms_dir: Path) -> dict[str, OrganRollup]:
    """Build per-organ rollups from centralized pipeline outputs.

    Args:
        atoms_dir: Directory containing atomized-tasks.jsonl, annotated-prompts.jsonl,
                   atom-links.jsonl.

    Returns:
        Dict mapping organ CLI key → OrganRollup.
    """
    rollups: dict[str, OrganRollup] = {}

    # --- Tasks ---
    tasks = _load_jsonl(atoms_dir / "atomized-tasks.jsonl")
    task_organ_map: dict[str, str] = {}  # task_id → organ_key

    for t in tasks:
        organ = t.get("project", {}).get("organ")
        if not organ or organ not in ORGANS:
            # Skip unattributed tasks (organ is None, "_root", or unknown)
            continue
        if organ not in rollups:
            rollups[organ] = _make_rollup(organ)

        r = rollups[organ]
        r.total_tasks += 1
        task_id = t.get("id", "")
        task_organ_map[task_id] = organ

        status = t.get("status", "").lower()
        if status in ("pending", "todo", "open", "blocked"):
            r.pending_tasks += 1
            repo = t.get("project", {}).get("repo") or "_unattributed"
            r.pending_by_repo.setdefault(repo, []).append({
                "id": task_id,
                "title": t.get("title", ""),
                "status": t.get("status", ""),
                "tags": t.get("tags", []),
            })
        elif status in ("done", "complete", "completed"):
            r.completed_tasks += 1

        # Domain fingerprints from tasks (skip empty-string hash)
        fp = t.get("domain_fingerprint")
        if fp and not fp.startswith(_EMPTY_FINGERPRINT_PREFIX):
            r.domain_fingerprints[fp] = r.domain_fingerprints.get(fp, 0) + 1

    # --- Prompts ---
    prompts = _load_jsonl(atoms_dir / "annotated-prompts.jsonl")
    prompt_organ_map: dict[str, str] = {}  # prompt_id → organ_key

    for p in prompts:
        slug = p.get("source", {}).get("project_slug", "")
        organ = organ_key_from_slug(slug)
        if not organ:
            continue
        if organ not in rollups:
            rollups[organ] = _make_rollup(organ)

        r = rollups[organ]
        prompt_id = p.get("id", "")
        prompt_organ_map[prompt_id] = organ

        # Prompt type distribution
        ptype = p.get("classification", {}).get("prompt_type", "unknown")
        r.prompt_type_dist[ptype] = r.prompt_type_dist.get(ptype, 0) + 1

        # Session frequency by repo
        repo = slug.split("/", 1)[1] if "/" in slug else slug
        r.session_freq[repo] = r.session_freq.get(repo, 0) + 1

        # Domain fingerprints from prompts (skip empty-string hash)
        fp = p.get("domain_fingerprint")
        if fp and not fp.startswith(_EMPTY_FINGERPRINT_PREFIX):
            r.domain_fingerprints[fp] = r.domain_fingerprints.get(fp, 0) + 1

    # --- Links (cross-organ detection) ---
    links = _load_jsonl(atoms_dir / "atom-links.jsonl")
    for link in links:
        task_organ = task_organ_map.get(link.get("task_id", ""))
        prompt_organ = prompt_organ_map.get(link.get("prompt_id", ""))
        if task_organ and prompt_organ and task_organ != prompt_organ:
            # Cross-organ link — add to both organs
            link_entry = {
                "task_id": link.get("task_id", ""),
                "prompt_id": link.get("prompt_id", ""),
                "task_organ": task_organ,
                "prompt_organ": prompt_organ,
                "jaccard": link.get("jaccard", 0),
            }
            if task_organ in rollups:
                rollups[task_organ].cross_organ_links.append(link_entry)
            if prompt_organ in rollups:
                rollups[prompt_organ].cross_organ_links.append(link_entry)

    return rollups


def write_rollups(
    rollups: dict[str, OrganRollup],
    workspace: Path,
    dry_run: bool = True,
) -> list[str]:
    """Write per-organ rollup JSON to each organ's .atoms/ directory.

    Args:
        rollups: Dict of organ CLI key → OrganRollup.
        workspace: Workspace root (e.g. ~/Workspace).
        dry_run: If True, return paths but don't write.

    Returns:
        List of paths that were (or would be) written.
    """
    written: list[str] = []
    for _key, rollup in sorted(rollups.items()):
        organ_dir = workspace / rollup.organ_dir
        if not organ_dir.is_dir():
            continue
        out_path = organ_dir / ".atoms" / "organ-rollup.json"
        written.append(str(out_path))
        if not dry_run:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(rollup.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    return written


def load_rollup(organ_dir: Path) -> dict | None:
    """Read organ-rollup.json from an organ directory. Returns None if missing."""
    path = organ_dir / ".atoms" / "organ-rollup.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_repo_task_queue(rollup: dict, repo_name: str) -> dict | None:
    """Extract repo-specific task slice from a rollup dict.

    Returns {"pending_count": N, "tasks": [...]} or None.
    """
    pending = rollup.get("pending_by_repo", {}).get(repo_name)
    if pending is None:
        return None
    return {"pending_count": len(pending), "tasks": pending}
