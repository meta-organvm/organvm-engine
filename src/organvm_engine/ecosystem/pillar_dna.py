"""Read, write, and validate pillar DNA lifecycle contracts.

Each repo can have ecosystem/pillar-dna/<pillar>.yaml files that define
the lifecycle contract for a business pillar — research scope, artifacts,
gen/crit prompts, and advancement gates.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from organvm_engine.ecosystem.product_types import LIFECYCLE_STAGES

PILLAR_DNA_DIR = "ecosystem/pillar-dna"


def read_pillar_dna(repo_path: Path | str, pillar: str) -> dict | None:
    """Read pillar DNA for a specific pillar in a repo.

    Returns None if the file doesn't exist.
    """
    dna_path = Path(repo_path) / PILLAR_DNA_DIR / f"{pillar}.yaml"
    if not dna_path.is_file():
        return None
    with dna_path.open() as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return None
    return data


def write_pillar_dna(repo_path: Path | str, pillar: str, data: dict) -> Path:
    """Write pillar DNA to the standard location.

    Creates the pillar-dna directory if needed.
    Returns the path written.
    """
    dna_dir = Path(repo_path) / PILLAR_DNA_DIR
    dna_dir.mkdir(parents=True, exist_ok=True)
    dna_path = dna_dir / f"{pillar}.yaml"
    with dna_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return dna_path


def list_pillar_dnas(repo_path: Path | str) -> list[str]:
    """Discover existing pillar DNA files in a repo.

    Returns list of pillar names (derived from filenames).
    """
    dna_dir = Path(repo_path) / PILLAR_DNA_DIR
    if not dna_dir.is_dir():
        return []
    return sorted(
        p.stem for p in dna_dir.iterdir()
        if p.is_file() and p.suffix in (".yaml", ".yml")
    )


def validate_pillar_dna(data: dict) -> list[str]:
    """Validate pillar DNA structure.

    Returns list of error messages (empty = valid).
    """
    errors: list[str] = []

    if "schema_version" not in data:
        errors.append("Missing required field: schema_version")
    elif data["schema_version"] != "1.0":
        errors.append(f"Unsupported schema_version: {data['schema_version']}")

    if "pillar" not in data:
        errors.append("Missing required field: pillar")
    elif not isinstance(data["pillar"], str):
        errors.append("Field 'pillar' must be a string")

    if "lifecycle_stage" not in data:
        errors.append("Missing required field: lifecycle_stage")
    elif data["lifecycle_stage"] not in LIFECYCLE_STAGES:
        errors.append(
            f"Invalid lifecycle_stage '{data['lifecycle_stage']}', "
            f"must be one of {LIFECYCLE_STAGES}",
        )

    # Validate artifacts
    artifacts = data.get("artifacts")
    if artifacts is not None:
        if not isinstance(artifacts, list):
            errors.append("Field 'artifacts' must be a list")
        else:
            for i, art in enumerate(artifacts):
                if not isinstance(art, dict):
                    errors.append(f"artifacts[{i}]: must be a mapping")
                elif "name" not in art:
                    errors.append(f"artifacts[{i}]: missing required field 'name'")

    # Validate gen_prompts
    gen_prompts = data.get("gen_prompts")
    if gen_prompts is not None:
        if not isinstance(gen_prompts, list):
            errors.append("Field 'gen_prompts' must be a list")
        else:
            for i, gp in enumerate(gen_prompts):
                if not isinstance(gp, dict):
                    errors.append(f"gen_prompts[{i}]: must be a mapping")
                    continue
                if "id" not in gp:
                    errors.append(f"gen_prompts[{i}]: missing required field 'id'")
                if "prompt" not in gp:
                    errors.append(f"gen_prompts[{i}]: missing required field 'prompt'")

    # Validate crit_prompts
    crit_prompts = data.get("crit_prompts")
    if crit_prompts is not None:
        if not isinstance(crit_prompts, list):
            errors.append("Field 'crit_prompts' must be a list")
        else:
            for i, cp in enumerate(crit_prompts):
                if not isinstance(cp, dict):
                    errors.append(f"crit_prompts[{i}]: must be a mapping")
                    continue
                if "id" not in cp:
                    errors.append(f"crit_prompts[{i}]: missing required field 'id'")
                if "prompt" not in cp:
                    errors.append(f"crit_prompts[{i}]: missing required field 'prompt'")

    # Validate gates
    gates = data.get("gates")
    if gates is not None:
        if not isinstance(gates, dict):
            errors.append("Field 'gates' must be a mapping")
        else:
            for gate_name, criteria in gates.items():
                if not isinstance(criteria, list):
                    errors.append(f"gates.{gate_name}: must be a list of strings")

    return errors


def check_gates(
    dna: dict,
    current_stage: str,
    target_stage: str,
) -> list[str]:
    """Return unmet gate criteria for a stage transition.

    Gate names are constructed as '{current}_to_{target}'. If no gate
    is defined for the transition, returns an empty list (no blocking).
    """
    gates = dna.get("gates", {})
    if not isinstance(gates, dict):
        return []

    gate_key = f"{current_stage}_to_{target_stage}"
    criteria = gates.get(gate_key)
    if not criteria or not isinstance(criteria, list):
        return []

    # All gate criteria are returned as "unmet" — actual evaluation
    # requires checking against real artifact/arm state, which is the
    # caller's responsibility. This returns the criteria text for display.
    return list(criteria)
