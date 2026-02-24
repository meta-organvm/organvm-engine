"""Workspace reproduction from superproject state.

Enables cloning an entire organ (or the full workspace) from
superproject remotes and the workspace manifest.
"""

import json
import subprocess
from pathlib import Path

from organvm_engine.git.superproject import ORGAN_DIR_MAP, SUPERPROJECT_REMOTES, _run_git
from organvm_engine.seed.discover import DEFAULT_WORKSPACE


def reproduce_workspace(
    target: Path | str,
    manifest_path: Path | str | None = None,
    organs: list[str] | None = None,
    shallow: bool = False,
) -> dict:
    """Reproduce the full workspace (or selected organs) from superprojects.

    Clones each organ superproject, then initializes submodules.

    Args:
        target: Target directory to create workspace in.
        manifest_path: Path to workspace-manifest.json. If None, uses
            built-in SUPERPROJECT_REMOTES.
        organs: List of organ keys to clone. If None, clones all.
        shallow: If True, use --depth=1 for faster cloning.

    Returns:
        Dict with: target, cloned_organs, errors.
    """
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)

    # Load manifest if provided
    remotes = dict(SUPERPROJECT_REMOTES)
    if manifest_path:
        manifest = json.loads(Path(manifest_path).read_text())
        for entry in manifest.get("organs", []):
            dir_name = entry.get("directory")
            remote = entry.get("superproject_remote")
            if dir_name and remote:
                remotes[dir_name] = remote

    # Filter to requested organs
    if organs:
        organ_dirs = []
        for o in organs:
            key = o.upper()
            if key in ORGAN_DIR_MAP:
                organ_dirs.append(ORGAN_DIR_MAP[key])
            else:
                organ_dirs.append(o)  # Try as directory name
        remotes = {k: v for k, v in remotes.items() if k in organ_dirs}

    cloned = []
    errors = []

    for organ_dir, remote_url in sorted(remotes.items()):
        organ_target = target_path / organ_dir
        if organ_target.exists():
            errors.append(f"{organ_dir}: already exists, skipping")
            continue

        clone_args = ["clone"]
        if shallow:
            clone_args += ["--depth", "1"]
        clone_args += [remote_url, str(organ_target)]

        result = subprocess.run(
            ["git"] + clone_args,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            errors.append(f"{organ_dir}: clone failed — {result.stderr.strip()}")
            continue

        # Initialize submodules
        sub_args = ["submodule", "update", "--init"]
        if shallow:
            sub_args += ["--depth", "1"]

        sub_result = _run_git(sub_args, organ_target, timeout=300)
        if sub_result.returncode != 0:
            errors.append(f"{organ_dir}: submodule init failed — {sub_result.stderr.strip()}")

        cloned.append(organ_dir)

    return {
        "target": str(target_path),
        "cloned_organs": cloned,
        "errors": errors,
    }


def clone_organ(
    organ: str,
    target: Path | str | None = None,
    shallow: bool = False,
) -> dict:
    """Clone a single organ superproject with all submodules.

    Args:
        organ: Organ identifier (I, II, ..., META, LIMINAL).
        target: Target directory. Defaults to ~/Workspace/<organ-dir>.
        shallow: If True, use --depth=1.

    Returns:
        Dict with clone results.
    """
    organ_dir = ORGAN_DIR_MAP.get(organ.upper())
    if not organ_dir:
        raise ValueError(f"Unknown organ: {organ}")

    remote_url = SUPERPROJECT_REMOTES.get(organ_dir)
    if not remote_url:
        raise ValueError(f"No superproject remote for {organ_dir}")

    target_path = Path(target) if target else DEFAULT_WORKSPACE / organ_dir

    if target_path.exists():
        return {"error": f"Target already exists: {target_path}"}

    clone_args = ["clone", "--recurse-submodules"]
    if shallow:
        clone_args += ["--depth", "1", "--shallow-submodules"]
    clone_args += [remote_url, str(target_path)]

    result = subprocess.run(
        ["git"] + clone_args,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        return {"error": f"Clone failed: {result.stderr.strip()}"}

    # Count submodules
    sub_result = _run_git(["submodule", "status"], target_path)
    submodule_count = len([
        line for line in sub_result.stdout.strip().split("\n") if line.strip()
    ]) if sub_result.returncode == 0 else 0

    return {
        "organ": organ_dir,
        "target": str(target_path),
        "submodules": submodule_count,
        "shallow": shallow,
    }
