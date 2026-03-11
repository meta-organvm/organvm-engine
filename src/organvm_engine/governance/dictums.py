"""Dictum validation — machine-readable constitutional laws for the ORGANVM ecosystem.

Dictums are organized in three tiers:
- Axioms (AX-*): Universal structural invariants
- Organ dictums (OD-*): Per-organ constraints
- Repo rules (RR-*): Per-repository requirements

Each dictum declares an enforcement mode (automated/audit/manual) and severity
(critical/warning/info). Only automated and audit dictums have validators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DictumViolation:
    """A single dictum violation."""

    dictum_id: str
    dictum_name: str
    severity: str
    message: str
    organ: str | None = None
    repo: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "dictum_id": self.dictum_id,
            "dictum_name": self.dictum_name,
            "severity": self.severity,
            "message": self.message,
        }
        if self.organ:
            d["organ"] = self.organ
        if self.repo:
            d["repo"] = self.repo
        return d


@dataclass
class DictumReport:
    """Result of checking all dictums."""

    violations: list[DictumViolation] = field(default_factory=list)
    checked: int = 0
    passed: int = 0

    @property
    def all_passed(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        lines = ["Dictum Compliance Report", "=" * 40]
        lines.append(f"  Checked: {self.checked}")
        lines.append(f"  Passed: {self.passed}")
        lines.append(f"  Violations: {len(self.violations)}")
        if self.violations:
            by_sev: dict[str, list[DictumViolation]] = {}
            for v in self.violations:
                by_sev.setdefault(v.severity, []).append(v)
            for sev in ("critical", "warning", "info"):
                items = by_sev.get(sev, [])
                if items:
                    lines.append(f"\n  {sev.upper()} ({len(items)}):")
                    for v in items:
                        loc = ""
                        if v.organ:
                            loc = f"{v.organ}/"
                        if v.repo:
                            loc += v.repo
                        prefix = f"[{loc}] " if loc else ""
                        lines.append(f"    {v.dictum_id}: {prefix}{v.message}")
        lines.append(f"\n  Result: {'PASS' if self.all_passed else 'FAIL'}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "checked": self.checked,
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "all_passed": self.all_passed,
        }


# ── Loaders ──────────────────────────────────────────────────────


def get_dictums(rules: dict) -> dict:
    """Extract the dictums section from governance rules."""
    return rules.get("dictums", {})


def get_axioms(rules: dict) -> list[dict]:
    """Extract axiom dictums."""
    return get_dictums(rules).get("axioms", [])


def get_organ_dictum(rules: dict, organ_key: str) -> list[dict]:
    """Get dictums for a specific organ."""
    return get_dictums(rules).get("organ_dictums", {}).get(organ_key, [])


def get_repo_rules(rules: dict) -> list[dict]:
    """Extract repo-level rules."""
    return get_dictums(rules).get("repo_rules", [])


# ── Validators ───────────────────────────────────────────────────


def validate_dag_invariant(registry: dict) -> list[DictumViolation]:
    """AX-1: Validate that the dependency graph is a strict DAG (I→II→III)."""
    from organvm_engine.governance.dependency_graph import validate_dependencies

    dep_result = validate_dependencies(registry)
    violations: list[DictumViolation] = []

    for _from, _to, from_org, to_org in dep_result.back_edges:
        violations.append(DictumViolation(
            dictum_id="AX-1",
            dictum_name="DAG Invariant",
            severity="critical",
            message=f"Back-edge: {_from} → {_to} ({from_org} → {to_org})",
            organ=from_org,
            repo=_from.split("/", 1)[-1] if "/" in _from else _from,
        ))

    for cycle in dep_result.cycles:
        violations.append(DictumViolation(
            dictum_id="AX-1",
            dictum_name="DAG Invariant",
            severity="critical",
            message=f"Cycle detected: {' → '.join(cycle)}",
        ))

    return violations


def validate_epistemic_membranes(
    registry: dict,
    workspace: Path | None = None,
) -> list[DictumViolation]:
    """AX-2: Check that cross-organ edges are declared in seed.yaml."""
    violations: list[DictumViolation] = []

    if workspace is None:
        return violations

    from organvm_engine.registry.query import all_repos

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        deps = repo.get("dependencies", [])
        if not deps:
            continue
        # Check if repo has a seed.yaml
        org = repo.get("org", "")
        name = repo.get("name", "")
        seed_path = workspace / org / name / "seed.yaml"
        if not seed_path.exists():
            # Cross-organ deps without seed.yaml = undeclared coupling
            cross_organ_deps = []
            for dep in deps:
                dep_org = dep.split("/")[0] if "/" in dep else ""
                if dep_org and dep_org != org:
                    cross_organ_deps.append(dep)
            if cross_organ_deps:
                violations.append(DictumViolation(
                    dictum_id="AX-2",
                    dictum_name="Epistemic Membranes",
                    severity="critical",
                    message=(
                        f"Cross-organ dependencies {cross_organ_deps} "
                        "not declared — no seed.yaml found"
                    ),
                    organ=organ_key,
                    repo=name,
                ))

    return violations


def validate_ttl_eviction(
    registry: dict,
    rules: dict,
) -> list[DictumViolation]:
    """AX-3: Check staleness and INCUBATOR TTL."""
    violations: list[DictumViolation] = []
    thresholds = rules.get("audit_thresholds", {}).get("warning", {})
    stale_days = thresholds.get("stale_repo_days", 90)
    now = datetime.now(timezone.utc)

    from organvm_engine.registry.query import all_repos

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "?")
        promo_status = repo.get("promotion_status", "LOCAL")
        last_validated = repo.get("last_validated", "")

        if not last_validated:
            continue

        try:
            lv = datetime.fromisoformat(last_validated)
            if lv.tzinfo is None:
                lv = lv.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        days_ago = (now - lv).days

        # INCUBATOR 14-day TTL
        if promo_status == "INCUBATOR" and days_ago > 14:
            violations.append(DictumViolation(
                dictum_id="AX-3",
                dictum_name="TTL Eviction",
                severity="warning",
                message=(
                    f"INCUBATOR TTL expired ({days_ago} days, max 14). "
                    "Graduate or archive."
                ),
                organ=organ_key,
                repo=name,
            ))

        # General staleness
        if days_ago > stale_days:
            violations.append(DictumViolation(
                dictum_id="AX-3",
                dictum_name="TTL Eviction",
                severity="warning",
                message=f"Stale — {days_ago} days since validation (threshold: {stale_days})",
                organ=organ_key,
                repo=name,
            ))

    return violations


def validate_organ_iii_factory(registry: dict) -> list[DictumViolation]:
    """OD-III: Check ORGAN-III repos have revenue_model and CI."""
    violations: list[DictumViolation] = []
    organ_data = registry.get("organs", {}).get("ORGAN-III", {})

    for repo in organ_data.get("repositories", []):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        name = repo.get("name", "?")

        if not repo.get("revenue_model"):
            violations.append(DictumViolation(
                dictum_id="OD-III",
                dictum_name="Ergon Factory Gate",
                severity="warning",
                message="Missing revenue_model",
                organ="ORGAN-III",
                repo=name,
            ))

        if not repo.get("ci_workflow"):
            violations.append(DictumViolation(
                dictum_id="OD-III",
                dictum_name="Ergon Factory Gate",
                severity="warning",
                message="Missing CI workflow",
                organ="ORGAN-III",
                repo=name,
            ))

    return violations


def validate_seed_mandate(
    registry: dict,
    workspace: Path | None = None,
) -> list[DictumViolation]:
    """RR-1: Every non-archived repo must have a seed.yaml."""
    violations: list[DictumViolation] = []

    if workspace is None:
        return violations

    from organvm_engine.registry.query import all_repos

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        org = repo.get("org", "")
        name = repo.get("name", "")
        seed_path = workspace / org / name / "seed.yaml"
        if not seed_path.exists():
            violations.append(DictumViolation(
                dictum_id="RR-1",
                dictum_name="Seed Contract Mandate",
                severity="warning",
                message="No seed.yaml found",
                organ=organ_key,
                repo=name,
            ))

    return violations


def validate_event_handshake(
    registry: dict,
    workspace: Path | None = None,
) -> list[DictumViolation]:
    """RR-3: Event edges in seed.yaml must reference existing event types."""
    violations: list[DictumViolation] = []

    if workspace is None:
        return violations

    from organvm_engine.registry.query import all_repos
    from organvm_engine.seed.reader import read_seed

    for organ_key, repo in all_repos(registry):
        if repo.get("implementation_status") == "ARCHIVED":
            continue
        org = repo.get("org", "")
        name = repo.get("name", "")
        seed_path = workspace / org / name / "seed.yaml"
        if not seed_path.exists():
            continue

        try:
            seed = read_seed(seed_path)
        except Exception:
            continue

        # Check subscriptions for event types
        subs = seed.get("subscriptions", [])
        for sub in subs:
            event_type = sub if isinstance(sub, str) else sub.get("event", "")
            if event_type and "." not in event_type:
                violations.append(DictumViolation(
                    dictum_id="RR-3",
                    dictum_name="Event Handshake",
                    severity="warning",
                    message=f"Subscription '{event_type}' has no dotted namespace",
                    organ=organ_key,
                    repo=name,
                ))

    return violations


# ── Master runner ────────────────────────────────────────────────

# Maps validator names to functions
_VALIDATORS: dict[str, callable] = {
    "validate_dag_invariant": lambda reg, rules, ws: validate_dag_invariant(reg),
    "validate_epistemic_membranes": lambda reg, rules, ws: validate_epistemic_membranes(reg, ws),
    "validate_ttl_eviction": lambda reg, rules, ws: validate_ttl_eviction(reg, rules),
    "validate_organ_iii_factory": lambda reg, rules, ws: validate_organ_iii_factory(reg),
    "validate_seed_mandate": lambda reg, rules, ws: validate_seed_mandate(reg, ws),
    "validate_event_handshake": lambda reg, rules, ws: validate_event_handshake(reg, ws),
}


def check_all_dictums(
    registry: dict,
    rules: dict | None = None,
    workspace: Path | None = None,
) -> DictumReport:
    """Run all enforceable dictum validators.

    Skips dictums with enforcement='manual'.
    """
    if rules is None:
        from organvm_engine.governance.rules import load_governance_rules
        rules = load_governance_rules()

    report = DictumReport()
    dictums_data = get_dictums(rules)
    if not dictums_data:
        return report

    # Collect all dictums that have validators
    all_dictums: list[dict] = []
    all_dictums.extend(get_axioms(rules))
    for _organ_key, organ_dicts in dictums_data.get("organ_dictums", {}).items():
        all_dictums.extend(organ_dicts)
    all_dictums.extend(get_repo_rules(rules))

    for dictum in all_dictums:
        if dictum.get("enforcement") == "manual":
            continue

        validator_name = dictum.get("validator")
        if not validator_name:
            continue

        report.checked += 1
        validator_fn = _VALIDATORS.get(validator_name)
        if validator_fn is None:
            continue

        violations = validator_fn(registry, rules, workspace)
        if violations:
            report.violations.extend(violations)
        else:
            report.passed += 1

    return report


def list_all_dictums(rules: dict) -> list[dict]:
    """Return a flat list of all dictums with their level tag."""
    result: list[dict] = []
    dictums_data = get_dictums(rules)
    if not dictums_data:
        return result

    for ax in dictums_data.get("axioms", []):
        result.append({**ax, "level": "axiom"})

    for organ_key, organ_dicts in dictums_data.get("organ_dictums", {}).items():
        for od in organ_dicts:
            result.append({**od, "level": "organ", "organ": organ_key})

    for rr in dictums_data.get("repo_rules", []):
        result.append({**rr, "level": "repo"})

    return result
