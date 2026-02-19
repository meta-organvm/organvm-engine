"""CLAUDE.md sync — walks workspace, updates auto-generated sections.

The sync process:
1. Load registry + seeds once
2. Walk each organ directory looking for CLAUDE.md files
3. For each file, inject or replace the auto-generated section
4. Optionally update the workspace-level CLAUDE.md

Preserves all manually-written content outside the AUTO markers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from organvm_engine.claudemd import AUTO_START, AUTO_END
from organvm_engine.claudemd.generator import (
    generate_organ_section,
    generate_repo_section,
    generate_workspace_section,
)


def sync_all(
    workspace: Path | str | None = None,
    registry_path: str | None = None,
    dry_run: bool = False,
    organs: list[str] | None = None,
) -> dict[str, Any]:
    """Sync auto-generated sections across all CLAUDE.md files."""
    from organvm_engine.registry.loader import load_registry, DEFAULT_REGISTRY_PATH
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed
    from organvm_engine.git.superproject import ORGAN_DIR_MAP
    
    ws = Path(workspace) if workspace else Path.home() / "Workspace"
    reg = load_registry(registry_path or DEFAULT_REGISTRY_PATH)
    
    # 1. Discover all seeds to have edge data
    seed_paths = discover_seeds(ws)
    all_seeds = []
    repo_to_seed = {}
    for p in seed_paths:
        try:
            s = read_seed(p)
            all_seeds.append(s)
            repo_to_seed[s.get("repo")] = s
        except Exception:
            continue
            
    updated = []
    created = []
    skipped = []
    errors = []
    
    target_organs = organs or list(ORGAN_DIR_MAP.keys())
    
    for organ_key in target_organs:
        organ_dir_name = ORGAN_DIR_MAP.get(organ_key)
        if not organ_dir_name:
            continue
            
        organ_path = ws / organ_dir_name
        if not organ_path.is_dir():
            continue
            
        # 2. Sync organ-level CLAUDE.md
        try:
            organ_section = generate_organ_section(organ_key, reg, all_seeds)
            action = _inject_section(organ_path / "CLAUDE.md", organ_section, dry_run)
            if action == "created": created.append(str(organ_path / "CLAUDE.md"))
            elif action == "updated": updated.append(str(organ_path / "CLAUDE.md"))
            else: skipped.append(str(organ_path / "CLAUDE.md"))
        except Exception as e:
            errors.append({"path": str(organ_path / "CLAUDE.md"), "error": str(e)})
            
        # 3. Sync repo-level CLAUDE.mds
        organ_data = reg.get("organs", {}).get(organ_key, {})
        org_name = organ_data.get("organization", "unknown")
        
        for repo_entry in organ_data.get("repositories", []):
            repo_name = repo_entry.get("name")
            repo_path = organ_path / repo_name
            if not repo_path.is_dir():
                continue
                
            try:
                res = sync_repo(
                    repo_path, repo_name, org_name, reg, 
                    repo_to_seed.get(repo_name), dry_run
                )
                if res["action"] == "created": created.append(res["path"])
                elif res["action"] == "updated": updated.append(res["path"])
                else: skipped.append(res["path"])
            except Exception as e:
                errors.append({"path": str(repo_path / "CLAUDE.md"), "error": str(e)})
                
    # 4. Sync workspace-level CLAUDE.md
    try:
        ws_section = generate_workspace_section(reg, all_seeds)
        action = _inject_section(ws / "CLAUDE.md", ws_section, dry_run)
        if action == "created": created.append(str(ws / "CLAUDE.md"))
        elif action == "updated": updated.append(str(ws / "CLAUDE.md"))
        else: skipped.append(str(ws / "CLAUDE.md"))
    except Exception as e:
        errors.append({"path": str(ws / "CLAUDE.md"), "error": str(e)})
        
    return {
        "updated": updated,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run
    }


def sync_repo(
    repo_path: Path,
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Sync a single repo's CLAUDE.md."""
    section = generate_repo_section(repo_name, org, registry, seed)
    file_path = repo_path / "CLAUDE.md"
    action = _inject_section(file_path, section, dry_run)
    return {"path": str(file_path), "action": action, "dry_run": dry_run}


def _inject_section(file_path: Path, new_section: str, dry_run: bool = False) -> str:
    """Inject or replace the auto-generated section in a CLAUDE.md file."""
    if not file_path.exists():
        if not dry_run:
            file_path.write_text(new_section + "\n")
        return "created"
        
    content = file_path.read_text()
    
    if AUTO_START in content and AUTO_END in content:
        # Replace existing section
        import re
        pattern = re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END)
        new_content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        if new_content == content:
            return "unchanged"
        if not dry_run:
            file_path.write_text(new_content)
        return "updated"
    else:
        # Append to end
        new_content = content.rstrip() + "\n\n" + new_section + "\n"
        if not dry_run:
            file_path.write_text(new_content)
        return "updated"
