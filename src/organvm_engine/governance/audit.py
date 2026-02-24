"""Full system audit against governance rules."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from organvm_engine.governance.rules import load_governance_rules, get_audit_thresholds, get_organ_requirements
from organvm_engine.governance.dependency_graph import validate_dependencies


@dataclass
class AuditResult:
    """Result of a full governance audit."""

    critical: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    dependency_result: object = None

    @property
    def passed(self) -> bool:
        return len(self.critical) == 0

    def summary(self) -> str:
        lines = ["Governance Audit Report", "=" * 40]
        if self.critical:
            lines.append(f"\nCRITICAL ({len(self.critical)}):")
            for c in self.critical:
                lines.append(f"  {c}")
        if self.warnings:
            lines.append(f"\nWARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  {w}")
        if self.info:
            lines.append(f"\nINFO ({len(self.info)}):")
            for i in self.info:
                lines.append(f"  {i}")
        if self.passed and not self.warnings:
            lines.append("\nAll governance checks passed.")
        lines.append(f"\nResult: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


def run_audit(
    registry: dict,
    rules: dict | None = None,
) -> AuditResult:
    """Run a full governance audit.

    Checks:
    - Missing READMEs (critical)
    - Circular dependencies (critical)
    - Back-edge violations (critical)
    - Empty organs (critical)
    - Stale repos (warning)
    - Missing changelogs / CI (warning)
    - Organ-specific requirements

    Args:
        registry: Loaded registry dict.
        rules: Governance rules dict. Loaded from default if None.

    Returns:
        AuditResult with all findings.
    """
    if rules is None:
        rules = load_governance_rules()

    result = AuditResult()
    thresholds = get_audit_thresholds(rules)
    critical_config = thresholds.get("critical", {})
    warning_config = thresholds.get("warning", {})

    # Dependency validation
    dep_result = validate_dependencies(registry)
    result.dependency_result = dep_result

    if dep_result.cycles:
        result.critical.append(
            f"Circular dependencies detected: {len(dep_result.cycles)} cycle(s)"
        )
    if dep_result.back_edges:
        result.critical.append(
            f"Back-edge violations: {len(dep_result.back_edges)} back-edge(s)"
        )

    result.info.append(
        f"Dependency graph: {dep_result.total_edges} edges, "
        f"{len(dep_result.cross_organ)} cross-organ directions"
    )

    # Per-organ checks
    organs = registry.get("organs", {})
    stale_days = warning_config.get("stale_repo_days", 90)
    now = datetime.now(timezone.utc)

    for organ_key, organ_data in organs.items():
        repos = organ_data.get("repositories", [])
        active = [r for r in repos if r.get("implementation_status") != "ARCHIVED"]

        # Empty organ check
        if not repos and critical_config.get("organ_has_zero_repos"):
            result.critical.append(f"{organ_key}: has zero repositories")

        # Organ-specific requirements
        reqs = get_organ_requirements(rules, organ_key)
        min_repos = reqs.get("min_repos", 0)
        if len(active) < min_repos:
            result.warnings.append(
                f"{organ_key}: has {len(active)} active repos, requires {min_repos}"
            )

        for repo in active:
            name = repo.get("name", "?")

            # Missing README check
            doc_status = repo.get("documentation_status", "")
            if not doc_status or doc_status == "EMPTY":
                if critical_config.get("missing_readme"):
                    result.critical.append(f"{organ_key}/{name}: missing README")

            # Missing CI
            if not repo.get("ci_workflow") and warning_config.get("missing_ci_workflow"):
                result.warnings.append(f"{organ_key}/{name}: no CI workflow")

            # Missing CHANGELOG
            if not repo.get("platinum_status") and warning_config.get("missing_changelog"):
                result.warnings.append(f"{organ_key}/{name}: not platinum (missing CHANGELOG/ADRs)")

            # Staleness check
            last_validated = repo.get("last_validated", "")
            if last_validated:
                try:
                    lv = datetime.fromisoformat(last_validated)
                    if lv.tzinfo is None:
                        lv = lv.replace(tzinfo=timezone.utc)
                    days_ago = (now - lv).days
                    if days_ago > stale_days:
                        result.warnings.append(
                            f"{organ_key}/{name}: stale ({days_ago} days since validation)"
                        )
                except ValueError:
                    result.warnings.append(
                        f"{organ_key}/{name}: malformed last_validated date '{last_validated}'"
                    )

    return result
