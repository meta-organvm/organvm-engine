"""Canonical organ definitions — single source of truth.

All organ key/directory/registry/GitHub-org mappings live here.
No other module should define its own organ mapping dicts.
"""

from __future__ import annotations

# Each organ entry: short CLI key → metadata dict
ORGANS: dict[str, dict[str, str]] = {
    "I":       {"dir": "organvm-i-theoria",    "registry_key": "ORGAN-I",       "org": "ivviiviivvi"},
    "II":      {"dir": "organvm-ii-poiesis",   "registry_key": "ORGAN-II",      "org": "omni-dromenon-machina"},
    "III":     {"dir": "organvm-iii-ergon",     "registry_key": "ORGAN-III",     "org": "labores-profani-crux"},
    "IV":      {"dir": "organvm-iv-taxis",      "registry_key": "ORGAN-IV",      "org": "organvm-iv-taxis"},
    "V":       {"dir": "organvm-v-logos",       "registry_key": "ORGAN-V",       "org": "organvm-v-logos"},
    "VI":      {"dir": "organvm-vi-koinonia",   "registry_key": "ORGAN-VI",      "org": "organvm-vi-koinonia"},
    "VII":     {"dir": "organvm-vii-kerygma",   "registry_key": "ORGAN-VII",     "org": "organvm-vii-kerygma"},
    "META":    {"dir": "meta-organvm",          "registry_key": "META-ORGANVM",  "org": "meta-organvm"},
    "LIMINAL": {"dir": "4444J99",               "registry_key": "PERSONAL",      "org": "4444j99"},
}


def organ_dir_map() -> dict[str, str]:
    """Map CLI short keys (I, II, META, ...) → workspace directory names."""
    return {k: v["dir"] for k, v in ORGANS.items()}


def registry_key_to_dir() -> dict[str, str]:
    """Map registry keys (ORGAN-I, META-ORGANVM, ...) → workspace directory names."""
    return {v["registry_key"]: v["dir"] for k, v in ORGANS.items()}


def organ_aliases() -> dict[str, str]:
    """Map CLI short keys (I, II, META, ...) → registry keys (ORGAN-I, META-ORGANVM, ...)."""
    return {k: v["registry_key"] for k, v in ORGANS.items()}


def organ_org_dirs() -> list[str]:
    """List of all organ workspace directory names (for seed discovery)."""
    return [v["dir"] for v in ORGANS.values() if v["registry_key"] != "PERSONAL"]


def dir_to_registry_key() -> dict[str, str]:
    """Map workspace directory names → registry keys."""
    return {v["dir"]: v["registry_key"] for k, v in ORGANS.items()}
