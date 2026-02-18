"""Load and query governance-rules.json."""

import json
from pathlib import Path

DEFAULT_RULES_PATH = (
    Path.home() / "Workspace" / "meta-organvm" / "organvm-corpvs-testamentvm" / "governance-rules.json"
)


def load_governance_rules(path: Path | str | None = None) -> dict:
    """Load governance-rules.json.

    Args:
        path: Path to rules file. Defaults to corpus repo location.

    Returns:
        Parsed governance rules dict.
    """
    rules_path = Path(path) if path else DEFAULT_RULES_PATH
    with open(rules_path) as f:
        return json.load(f)


def get_dependency_rules(rules: dict) -> dict:
    """Extract dependency rules section."""
    return rules.get("dependency_rules", {})


def get_promotion_rules(rules: dict) -> dict:
    """Extract promotion rules section."""
    return rules.get("promotion_rules", {})


def get_audit_thresholds(rules: dict) -> dict:
    """Extract audit threshold section."""
    return rules.get("audit_thresholds", {})


def get_organ_requirements(rules: dict, organ_key: str) -> dict:
    """Get requirements for a specific organ."""
    return rules.get("organ_requirements", {}).get(organ_key, {})
