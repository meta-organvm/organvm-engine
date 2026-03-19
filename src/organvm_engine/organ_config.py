"""Canonical organ definitions — single source of truth.

Implements: SPEC-006, AX-000-006
Resolves: engine #17 (CONFLICT — topology hardcoded)

All organ key/directory/registry/GitHub-org mappings live here.
No other module should define its own organ mapping dicts.

Topology is data-driven: load_organ_topology() reads from an external
config file (JSON or YAML). If no config file is found or parsing fails,
FALLBACK_ORGAN_MAP is used. get_organ_map() is the single accessor —
callers should prefer it over direct ORGANS access.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback (hardcoded) topology — backward compatibility guarantee
# ---------------------------------------------------------------------------

# Each organ entry: short CLI key → metadata dict
FALLBACK_ORGAN_MAP: dict[str, dict[str, str]] = {
    "I": {"dir": "organvm-i-theoria", "registry_key": "ORGAN-I", "org": "ivviiviivvi"},
    "II": {
        "dir": "organvm-ii-poiesis",
        "registry_key": "ORGAN-II",
        "org": "omni-dromenon-machina",
    },
    "III": {
        "dir": "organvm-iii-ergon",
        "registry_key": "ORGAN-III",
        "org": "labores-profani-crux",
    },
    "IV": {"dir": "organvm-iv-taxis", "registry_key": "ORGAN-IV", "org": "organvm-iv-taxis"},
    "V": {"dir": "organvm-v-logos", "registry_key": "ORGAN-V", "org": "organvm-v-logos"},
    "VI": {
        "dir": "organvm-vi-koinonia",
        "registry_key": "ORGAN-VI",
        "org": "organvm-vi-koinonia",
    },
    "VII": {
        "dir": "organvm-vii-kerygma",
        "registry_key": "ORGAN-VII",
        "org": "organvm-vii-kerygma",
    },
    "META": {"dir": "meta-organvm", "registry_key": "META-ORGANVM", "org": "meta-organvm"},
    # LIMINAL/PERSONAL (4444J99/) is a workspace convention, not a tracked organ.
    # It exists in the workspace as ~/Workspace/4444J99/ but is outside the
    # organ system — no registry entry, no governance, no seed contracts.
    "LIMINAL": {"dir": "4444J99", "registry_key": "PERSONAL", "org": "4444j99"},
}

# Backward-compatible alias — existing code imports ORGANS directly
ORGANS: dict[str, dict[str, str]] = FALLBACK_ORGAN_MAP

# Module-level cache for loaded topology
_loaded_topology: dict[str, dict[str, str]] | None = None
_topology_source: str = "fallback"


# ---------------------------------------------------------------------------
# Data-driven topology loader
# ---------------------------------------------------------------------------

def _validate_organ_entry(key: str, entry: dict[str, Any]) -> list[str]:
    """Validate that an organ entry has all required fields."""
    errors: list[str] = []
    for required in ("dir", "registry_key", "org"):
        if required not in entry:
            errors.append(f"Organ '{key}' missing required field: '{required}'")
        elif not isinstance(entry[required], str):
            errors.append(
                f"Organ '{key}' field '{required}' must be str, "
                f"got {type(entry[required]).__name__}",
            )
    return errors


def load_organ_topology(
    config_path: Path | str | None = None,
) -> dict[str, dict[str, str]]:
    """Load organ definitions from an external config file.

    Searches for organ topology in this order:
    1. Explicit config_path argument (JSON or YAML)
    2. 'organs' section within governance-rules.json
    3. Dedicated organ-topology.yaml or organ-topology.json in corpus dir

    If no config file is found or parsing fails, returns FALLBACK_ORGAN_MAP.

    Args:
        config_path: Explicit path to a topology config file.

    Returns:
        Dict of organ key → metadata dict (same shape as FALLBACK_ORGAN_MAP).
    """
    global _loaded_topology, _topology_source

    # Try explicit path first
    if config_path is not None:
        result = _load_from_path(Path(config_path))
        if result is not None:
            _loaded_topology = result
            _topology_source = str(config_path)
            return result

    # Try governance-rules.json organs section
    try:
        from organvm_engine.paths import governance_rules_path

        gov_path = governance_rules_path()
        if gov_path.is_file():
            with gov_path.open() as f:
                gov_rules = json.load(f)
            if "organ_topology" in gov_rules:
                result = _parse_topology_dict(gov_rules["organ_topology"])
                if result is not None:
                    _loaded_topology = result
                    _topology_source = f"{gov_path}#organ_topology"
                    return result
    except Exception:
        logger.debug("Could not load topology from governance-rules.json", exc_info=True)

    # Try dedicated topology files in corpus dir
    try:
        from organvm_engine.paths import corpus_dir

        corpus = corpus_dir()
        for filename in ("organ-topology.json", "organ-topology.yaml", "organ-topology.yml"):
            candidate = corpus / filename
            if candidate.is_file():
                result = _load_from_path(candidate)
                if result is not None:
                    _loaded_topology = result
                    _topology_source = str(candidate)
                    return result
    except Exception:
        logger.debug("Could not load dedicated topology file", exc_info=True)

    # Fallback
    _loaded_topology = None
    _topology_source = "fallback"
    return FALLBACK_ORGAN_MAP


def _load_from_path(path: Path) -> dict[str, dict[str, str]] | None:
    """Load and validate a topology file (JSON or YAML)."""
    if not path.is_file():
        return None

    try:
        suffix = path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError:
                logger.debug("PyYAML not available for %s", path)
                return None
            with path.open() as f:
                data = yaml.safe_load(f)
        else:
            with path.open() as f:
                data = json.load(f)
    except Exception:
        logger.debug("Failed to parse topology file: %s", path, exc_info=True)
        return None

    return _parse_topology_dict(data)


def _parse_topology_dict(data: Any) -> dict[str, dict[str, str]] | None:
    """Validate and normalize a raw topology dict.

    Expects either:
      {"organs": {"I": {"dir": ..., "registry_key": ..., "org": ...}, ...}}
    or the inner dict directly.
    """
    if not isinstance(data, dict):
        return None

    # Unwrap optional 'organs' wrapper
    organs_data = data.get("organs", data)
    if not isinstance(organs_data, dict):
        return None

    # Validate each entry
    result: dict[str, dict[str, str]] = {}
    all_errors: list[str] = []
    for key, entry in organs_data.items():
        if not isinstance(entry, dict):
            all_errors.append(f"Organ '{key}' must be a dict")
            continue
        errors = _validate_organ_entry(key, entry)
        if errors:
            all_errors.extend(errors)
            continue
        result[key] = {
            "dir": str(entry["dir"]),
            "registry_key": str(entry["registry_key"]),
            "org": str(entry["org"]),
        }

    if all_errors:
        logger.warning("Topology validation errors: %s", "; ".join(all_errors))

    # Only accept if at least some organs loaded successfully
    if not result:
        return None

    return result


# ---------------------------------------------------------------------------
# Primary accessor — all callers should use this
# ---------------------------------------------------------------------------

def get_organ_map() -> dict[str, dict[str, str]]:
    """Return the active organ topology map.

    Returns the loaded topology if load_organ_topology() has been called,
    otherwise returns FALLBACK_ORGAN_MAP. This function never triggers
    a filesystem read — call load_organ_topology() explicitly to load
    from a config file.

    Returns:
        Dict of organ key → metadata dict.
    """
    if _loaded_topology is not None:
        return _loaded_topology
    return FALLBACK_ORGAN_MAP


def get_topology_source() -> str:
    """Return description of where the current topology was loaded from."""
    return _topology_source


def reset_topology() -> None:
    """Reset the cached topology to fallback. Useful for testing."""
    global _loaded_topology, _topology_source
    _loaded_topology = None
    _topology_source = "fallback"


# ---------------------------------------------------------------------------
# Derived accessors — use get_organ_map() internally
# ---------------------------------------------------------------------------

def organ_dir_map() -> dict[str, str]:
    """Map CLI short keys (I, II, META, ...) → workspace directory names."""
    return {k: v["dir"] for k, v in get_organ_map().items()}


def registry_key_to_dir() -> dict[str, str]:
    """Map registry keys (ORGAN-I, META-ORGANVM, ...) → workspace directory names."""
    return {v["registry_key"]: v["dir"] for v in get_organ_map().values()}


def organ_aliases() -> dict[str, str]:
    """Map CLI short keys (I, II, META, ...) → registry keys (ORGAN-I, META-ORGANVM, ...)."""
    return {k: v["registry_key"] for k, v in get_organ_map().items()}


def organ_org_dirs() -> list[str]:
    """List of all organ workspace directory names (for seed discovery)."""
    return [v["dir"] for v in get_organ_map().values() if v["registry_key"] != "PERSONAL"]


def dir_to_registry_key() -> dict[str, str]:
    """Map workspace directory names → registry keys."""
    return {v["dir"]: v["registry_key"] for v in get_organ_map().values()}
