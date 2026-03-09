"""Canonical project slug derivation — shared across prompts, plans, and sessions.

A project slug is a short, human-readable identifier for a project. The canonical
form is the Workspace-relative path with forward slashes:

    meta-organvm/organvm-engine
    organvm-iii-ergon/peer-audited--behavioral-blockchain
    4444J99/application-pipeline

For paths outside ~/Workspace, we fall back to home-relative paths:

    4jp/dotfiles
    Legal/padavano-v-mdc--employment-lawsuit

The module also provides normalization for plan-directory slugs, which use
flat hyphenated names (e.g., 'meta-organvm-stakeholder-portal' → 'meta-organvm/stakeholder-portal').
"""

from __future__ import annotations

from pathlib import Path

# Lazy-loaded to avoid circular imports
_ORGAN_DIR_SET: set[str] | None = None
_PLAN_DIR_ALIASES: dict[str, str] | None = None


def _get_organ_dirs() -> set[str]:
    """Get the set of organ directory names."""
    global _ORGAN_DIR_SET
    if _ORGAN_DIR_SET is None:
        from organvm_engine.organ_config import ORGANS
        _ORGAN_DIR_SET = {v["dir"] for v in ORGANS.values()}
    return _ORGAN_DIR_SET


def slug_from_path(path: str) -> str:
    """Derive canonical project slug from a full filesystem path.

    Handles:
    - ~/Workspace/X/Y → X/Y
    - ~/X → 4jp/X (home-relative)
    - /Volumes/X → Volumes/X
    """
    parts = path.rstrip("/").split("/")

    # Try Workspace-relative
    try:
        ws_idx = parts.index("Workspace")
        slug_parts = parts[ws_idx + 1:]
        if slug_parts:
            return "/".join(slug_parts)
    except ValueError:
        pass

    # Home-relative fallback
    home = str(Path.home())
    if path.startswith(home):
        rel = path[len(home):].strip("/")
        if rel:
            # Prefix with username for clarity
            username = Path.home().name
            return f"{username}/{rel}"

    # Absolute fallback: last 2 components
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return parts[-1] if parts else "unknown"


def slug_from_plan_dir(plan_dir_name: str) -> str:
    """Normalize a flat plan directory name to canonical slug form.

    Plan directories under ~/.claude/plans/ use flat hyphenated names.
    This function reconstructs the slashed form where possible:

        meta-organvm-stakeholder-portal → meta-organvm/stakeholder-portal
        organvm-iii-ergon               → organvm-iii-ergon
        ivviiviivvi-github              → ivviiviivvi/.github
        application-pipeline            → application-pipeline (no org prefix known)
    """
    aliases = _get_plan_dir_aliases()
    if plan_dir_name in aliases:
        return aliases[plan_dir_name]

    # Try to match organ prefix
    organ_dirs = _get_organ_dirs()
    for organ_dir in sorted(organ_dirs, key=len, reverse=True):
        prefix = organ_dir + "-"
        if plan_dir_name.startswith(prefix):
            rest = plan_dir_name[len(prefix):]
            if rest:
                return f"{organ_dir}/{rest}"

    return plan_dir_name


def normalize_slug(raw_slug: str) -> str:
    """Normalize any slug to canonical form.

    Accepts either a full path, a plan directory name, or an already-canonical slug.
    Returns the canonical slash-separated form.
    """
    # Already looks like a path
    if raw_slug.startswith("/"):
        return slug_from_path(raw_slug)

    # Contains slashes — already structured, just clean up
    if "/" in raw_slug:
        return raw_slug.rstrip("/")

    # Flat name — try plan directory normalization
    return slug_from_plan_dir(raw_slug)


def _get_plan_dir_aliases() -> dict[str, str]:
    """Build a mapping of known flat plan dir names → canonical slugs.

    This handles special cases that can't be derived from organ prefixes alone.
    """
    global _PLAN_DIR_ALIASES
    if _PLAN_DIR_ALIASES is not None:
        return _PLAN_DIR_ALIASES

    _PLAN_DIR_ALIASES = {
        # Special cases where the flat name doesn't follow organ-prefix convention
        "ivviiviivvi-github": "ivviiviivvi/.github",
        "_root": "_root",
        "workspace-cross-project": "workspace-cross-project",
    }
    return _PLAN_DIR_ALIASES
