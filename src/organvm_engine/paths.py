"""Workspace path resolution.

Resolves canonical paths to ORGANVM data sources. Uses environment
variables when available, falls back to conventional defaults.

Environment variables:
    ORGANVM_WORKSPACE_DIR — workspace root (default: ~/Workspace)
    ORGANVM_CORPUS_DIR — corpus repo (default: <workspace>/meta-organvm/organvm-corpvs-testamentvm)
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_WORKSPACE = Path.home() / "Workspace"
_DEFAULT_CORPUS_SUBPATH = "meta-organvm/organvm-corpvs-testamentvm"


def workspace_root() -> Path:
    """Return the workspace root directory."""
    return Path(os.environ.get("ORGANVM_WORKSPACE_DIR", str(_DEFAULT_WORKSPACE)))


def corpus_dir() -> Path:
    """Return the path to organvm-corpvs-testamentvm."""
    env = os.environ.get("ORGANVM_CORPUS_DIR")
    if env:
        return Path(env)
    return workspace_root() / _DEFAULT_CORPUS_SUBPATH


def registry_path() -> Path:
    """Return the path to registry-v2.json."""
    return corpus_dir() / "registry-v2.json"


def governance_rules_path() -> Path:
    """Return the path to governance-rules.json."""
    return corpus_dir() / "governance-rules.json"


def soak_dir() -> Path:
    """Return the path to the soak-test data directory."""
    return corpus_dir() / "data" / "soak-test"
