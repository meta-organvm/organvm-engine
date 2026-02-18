"""Validate registry-v2.json against schema and governance rules."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from organvm_engine.registry.query import all_repos, find_repo

# Valid enum values (kept in sync with schema-definitions)
VALID_STATUSES = {"ACTIVE", "PROTOTYPE", "SKELETON", "DESIGN_ONLY", "ARCHIVED"}
VALID_REVENUE_MODELS = {"subscription", "freemium", "one-time", "advertising", "marketplace", "internal", "none"}
VALID_REVENUE_STATUSES = {"pre-launch", "beta", "live", "deprecated", "n/a"}
VALID_PROMOTION_STATES = {"LOCAL", "CANDIDATE", "PUBLIC_PROCESS", "GRADUATED", "ARCHIVED"}
VALID_TIERS = {"flagship", "standard", "stub", "archive", "infrastructure"}

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
