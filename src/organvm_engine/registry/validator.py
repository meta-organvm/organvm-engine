"""Validate registry-v2.json against schema and governance rules."""

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.registry.query import all_repos, find_repo

# Fallback enum values — used when schema-definitions is unavailable
_FALLBACK_STATUSES = {"ACTIVE", "PROTOTYPE", "SKELETON", "DESIGN_ONLY", "ARCHIVED"}
_FALLBACK_REVENUE_MODELS = {"subscription", "freemium", "one-time", "advertising", "marketplace", "internal", "none"}
_FALLBACK_REVENUE_STATUSES = {"pre-launch", "beta", "live", "deprecated", "n/a"}
_FALLBACK_PROMOTION_STATES = {"LOCAL", "CANDIDATE", "PUBLIC_PROCESS", "GRADUATED", "ARCHIVED"}
_FALLBACK_TIERS = {"flagship", "standard", "stub", "archive", "infrastructure"}


def _load_schema_enums() -> dict[str, set[str]]:
    """Load enum values from registry-v2 JSON schema.

    Searches for the schema file in known locations. Falls back to
    hardcoded values with a warning if the schema is unavailable.
    """
    candidates = [
        Path(__file__).resolve().parents[4] / "schema-definitions" / "schemas" / "registry-v2.schema.json",
        Path.home() / "Workspace" / "meta-organvm" / "schema-definitions" / "schemas" / "registry-v2.schema.json",
    ]

    for schema_path in candidates:
        if schema_path.is_file():
            try:
                schema = json.loads(schema_path.read_text())
                repo_props = schema.get("$defs", {}).get("repository", {}).get("properties", {})
                return {
                    "statuses": set(repo_props.get("implementation_status", {}).get("enum", [])),
                    "revenue_models": set(repo_props.get("revenue_model", {}).get("enum", [])),
                    "revenue_statuses": set(repo_props.get("revenue_status", {}).get("enum", [])),
                    "promotion_states": set(repo_props.get("promotion_status", {}).get("enum", [])),
                    "tiers": set(repo_props.get("tier", {}).get("enum", [])),
                }
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                warnings.warn(f"Failed to parse registry-v2 schema enums: {e}")
                break

    return {}


_schema_enums = _load_schema_enums()

VALID_STATUSES = _schema_enums.get("statuses") or _FALLBACK_STATUSES
VALID_REVENUE_MODELS = _schema_enums.get("revenue_models") or _FALLBACK_REVENUE_MODELS
VALID_REVENUE_STATUSES = _schema_enums.get("revenue_statuses") or _FALLBACK_REVENUE_STATUSES
VALID_PROMOTION_STATES = _schema_enums.get("promotion_states") or _FALLBACK_PROMOTION_STATES
VALID_TIERS = _schema_enums.get("tiers") or _FALLBACK_TIERS

REQUIRED_FIELDS = {"name", "org", "implementation_status", "public", "description"}
ORGAN_III_EXTRA = {"type", "revenue_model", "revenue_status"}


@dataclass
class ValidationResult:
    """Result of a registry validation run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_repos: int = 0

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [f"Registry Validation: {self.total_repos} repos checked"]
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  {e}")
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  {w}")
        if self.passed and not self.warnings:
            lines.append("All checks passed.")
        return "\n".join(lines)


def validate_registry(registry: dict) -> ValidationResult:
    """Run full validation on a registry dict.

    Checks:
    - Required fields present on all repos
    - Enum values valid (status, revenue, promotion, tier)
    - ORGAN-III repos have revenue fields
    - No back-edge dependencies in I->II->III chain
    - Dependency targets exist in registry
    - Count consistency (declared vs actual)

    Args:
        registry: Loaded registry dict.

    Returns:
        ValidationResult with errors and warnings.
    """
    result = ValidationResult()

    for organ_key, repo in all_repos(registry):
        result.total_repos += 1
        name = repo.get("name", f"<unnamed in {organ_key}>")

        # Required fields
        for f in REQUIRED_FIELDS:
            if f not in repo:
                result.errors.append(f"{name}: missing required field '{f}'")

        # Status enum
        status = repo.get("implementation_status")
        if status and status not in VALID_STATUSES:
            result.errors.append(
                f"{name}: invalid implementation_status '{status}' "
                f"(valid: {', '.join(sorted(VALID_STATUSES))})"
            )

        # Promotion status enum
        promo = repo.get("promotion_status")
        if promo and promo not in VALID_PROMOTION_STATES:
            result.errors.append(f"{name}: invalid promotion_status '{promo}'")

        # Tier enum
        tier = repo.get("tier")
        if tier and tier not in VALID_TIERS:
            result.errors.append(f"{name}: invalid tier '{tier}'")

        # ORGAN-III revenue fields
        if organ_key == "ORGAN-III":
            for f in ORGAN_III_EXTRA:
                if f not in repo:
                    result.warnings.append(f"{name}: ORGAN-III repo missing '{f}'")

            rm = repo.get("revenue_model")
            if rm and rm not in VALID_REVENUE_MODELS:
                result.errors.append(f"{name}: invalid revenue_model '{rm}'")

            rs = repo.get("revenue_status")
            if rs and rs not in VALID_REVENUE_STATUSES:
                result.errors.append(f"{name}: invalid revenue_status '{rs}'")

        # Dependency validation
        organ_num = {"ORGAN-I": 1, "ORGAN-II": 2, "ORGAN-III": 3}.get(organ_key)
        for dep in repo.get("dependencies", []):
            # Check target exists
            dep_name = dep.split("/")[-1] if "/" in dep else dep
            dep_result = find_repo(registry, dep_name)
            if not dep_result:
                result.warnings.append(f"{name}: dependency '{dep}' not found in registry")
                continue

            # Back-edge check
            dep_organ = dep_result[0]
            dep_num = {"ORGAN-I": 1, "ORGAN-II": 2, "ORGAN-III": 3}.get(dep_organ)
            if organ_num and dep_num and organ_num < dep_num:
                result.errors.append(
                    f"{name}: back-edge dependency on {dep} ({organ_key} -> {dep_organ})"
                )

    # Count consistency
    organs = registry.get("organs", {})
    for organ_key, organ in organs.items():
        declared = organ.get("repository_count")
        actual = len(organ.get("repositories", []))
        if declared is not None and declared != actual:
            result.warnings.append(
                f"{organ_key}: repository_count={declared} but found {actual}"
            )

    return result
