"""Parse and validate ecosystem.yaml files."""

from __future__ import annotations

from pathlib import Path

import yaml

from organvm_engine.ecosystem import HEADER_FIELDS
from organvm_engine.ecosystem.taxonomy import ARM_PRIORITY, ARM_STATUS


def read_ecosystem(path: Path | str) -> dict:
    """Read and parse an ecosystem.yaml file.

    Args:
        path: Path to ecosystem.yaml.

    Returns:
        Parsed ecosystem dict.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    eco_path = Path(path)
    with eco_path.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"ecosystem.yaml at {eco_path} is not a YAML mapping")

    return data


def validate_ecosystem(data: dict) -> list[str]:
    """Validate ecosystem data structure.

    Checks:
    - Required header fields present
    - schema_version is "1.0"
    - Every pillar is a list of arms
    - Every arm has platform (string) and status (from enum)
    - Priority values are from the enum if present

    Returns:
        List of validation error messages (empty = valid).
    """
    errors: list[str] = []

    if "schema_version" not in data:
        errors.append("Missing required field: schema_version")
    elif data["schema_version"] != "1.0":
        errors.append(f"Unsupported schema_version: {data['schema_version']}")

    if "repo" not in data:
        errors.append("Missing required field: repo")
    if "organ" not in data:
        errors.append("Missing required field: organ")

    # Validate each pillar
    for key, value in data.items():
        if key in HEADER_FIELDS:
            continue

        if not isinstance(value, list):
            errors.append(f"Pillar '{key}' must be a list, got {type(value).__name__}")
            continue

        for i, arm in enumerate(value):
            prefix = f"Pillar '{key}' arm [{i}]"
            if not isinstance(arm, dict):
                errors.append(f"{prefix}: must be a mapping, got {type(arm).__name__}")
                continue

            if "platform" not in arm:
                errors.append(f"{prefix}: missing required field 'platform'")
            elif not isinstance(arm["platform"], str):
                errors.append(f"{prefix}: 'platform' must be a string")

            if "status" not in arm:
                errors.append(f"{prefix}: missing required field 'status'")
            elif arm["status"] not in ARM_STATUS:
                errors.append(
                    f"{prefix}: invalid status '{arm['status']}', "
                    f"must be one of {ARM_STATUS}",
                )

            if "priority" in arm and arm["priority"] not in ARM_PRIORITY:
                errors.append(
                    f"{prefix}: invalid priority '{arm['priority']}', "
                    f"must be one of {ARM_PRIORITY}",
                )

    return errors


def get_pillars(data: dict) -> dict[str, list[dict]]:
    """Extract just the pillar data from an ecosystem dict."""
    return {k: v for k, v in data.items() if k not in HEADER_FIELDS and isinstance(v, list)}
