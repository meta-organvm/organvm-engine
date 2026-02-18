"""Load and save registry-v2.json."""

import json
import os
from pathlib import Path

# Default registry location — inside the corpus repo
_CORPUS_DIR = Path(os.environ.get(
    "ORGANVM_CORPUS_DIR",
    str(Path.home() / "Workspace" / "meta-organvm" / "organvm-corpvs-testamentvm"),
))
DEFAULT_REGISTRY_PATH = _CORPUS_DIR / "registry-v2.json"


def load_registry(path: Path | str | None = None) -> dict:
    """Load registry-v2.json from disk.

    Args:
        path: Path to registry file. Defaults to the corpus repo location.

    Returns:
        Parsed registry dict.
    """
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    with open(registry_path) as f:
        return json.load(f)


def save_registry(data: dict, path: Path | str | None = None) -> None:
    """Write registry-v2.json back to disk with consistent formatting.

    Args:
        data: Registry dict to write.
        path: Path to write to. Defaults to the corpus repo location.
    """
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    with open(registry_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
