"""Individual primacy governance check.

Implements: AX-003 (Individual Primacy) — structural encoding that the system
never optimizes away human agency.

This check validates that governance rules include human-in-the-loop provisions:
1. Promotion transitions require human approval (not fully automated)
2. Governance rules include explicit individual primacy provisions
3. AI agents in seed.yaml have bounded scope (not unrestricted)

The check is advisory in v1 — it reports findings but does not block operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Required human-in-the-loop provisions in governance rules
_HITL_PROVISIONS = (
    "human_approval_required",
    "human_review_required",
    "individual_primacy",
)

# Promotion states that should require human approval
_HUMAN_GATED_TRANSITIONS = (
    "PUBLIC_PROCESS",
    "GRADUATED",
)

# AI agent scope values considered unrestricted
_UNRESTRICTED_SCOPES = frozenset({"full", "unrestricted", "all"})


@dataclass
class PrimacyFinding:
    """A single finding from the individual primacy check."""

    severity: str  # "critical", "warning", "info"
    message: str
    context: str = ""  # e.g., organ/repo or rule section


@dataclass
class PrimacyReport:
    """Result of the individual primacy governance check."""

    findings: list[PrimacyFinding] = field(default_factory=list)
    provisions_present: list[str] = field(default_factory=list)
    provisions_missing: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """The check passes if there are no critical findings."""
        return not any(f.severity == "critical" for f in self.findings)

    @property
    def human_gated(self) -> bool:
        """Whether human-gated transitions are properly configured."""
        return "human_approval_required" in self.provisions_present

    def summary(self) -> str:
        """Human-readable summary of the primacy check."""
        lines = ["Individual Primacy Check (AX-003)", "=" * 40]
        if self.provisions_present:
            lines.append(f"\nProvisions present: {', '.join(self.provisions_present)}")
        if self.provisions_missing:
            lines.append(f"Provisions missing: {', '.join(self.provisions_missing)}")
        if self.findings:
            for f in self.findings:
                lines.append(f"  [{f.severity.upper()}] {f.message}")
                if f.context:
                    lines.append(f"         context: {f.context}")
        result = "PASS" if self.passed else "FAIL"
        lines.append(f"\nResult: {result}")
        return "\n".join(lines)


def check_individual_primacy(
    rules: dict[str, Any],
    seeds: dict[str, dict] | None = None,
) -> PrimacyReport:
    """Run the individual primacy governance check.

    Validates that:
    1. Governance rules contain human-in-the-loop provisions
    2. Critical promotion transitions are not fully automated
    3. AI agents in seeds have bounded scope

    Args:
        rules: Governance rules dict (from load_governance_rules).
        seeds: Optional dict mapping "org/repo" to parsed seed dicts.
               When provided, AI agent scope is also checked.

    Returns:
        PrimacyReport with all findings.
    """
    report = PrimacyReport()

    # Check 1: Human-in-the-loop provisions in governance rules
    _check_hitl_provisions(rules, report)

    # Check 2: Promotion transitions require human gating
    _check_promotion_gating(rules, report)

    # Check 3: AI agent scope bounds (when seeds provided)
    if seeds:
        _check_ai_agent_scope(seeds, report)

    return report


def _check_hitl_provisions(rules: dict[str, Any], report: PrimacyReport) -> None:
    """Check that governance rules include human-in-the-loop provisions."""
    # Check top-level governance keys for individual primacy provisions
    for provision in _HITL_PROVISIONS:
        if provision in rules:
            report.provisions_present.append(provision)
        else:
            report.provisions_missing.append(provision)

    # Also check inside audit_thresholds and dependency_rules
    audit = rules.get("audit_thresholds", {})
    dep_rules = rules.get("dependency_rules", {})
    promo_rules = rules.get("promotion_rules", {})

    for _section_name, section in [
        ("audit_thresholds", audit),
        ("dependency_rules", dep_rules),
        ("promotion_rules", promo_rules),
    ]:
        if not isinstance(section, dict):
            continue
        for provision in _HITL_PROVISIONS:
            if provision in section:
                if provision not in report.provisions_present:
                    report.provisions_present.append(provision)
                if provision in report.provisions_missing:
                    report.provisions_missing.remove(provision)

    if not report.provisions_present:
        report.findings.append(PrimacyFinding(
            severity="critical",
            message=(
                "No human-in-the-loop provisions found in governance rules. "
                "AX-003 requires structural encoding of individual primacy."
            ),
            context="governance-rules (top-level + sub-sections)",
        ))
    elif report.provisions_missing:
        for missing in report.provisions_missing:
            report.findings.append(PrimacyFinding(
                severity="warning",
                message=f"Provision '{missing}' not found in governance rules.",
                context="governance-rules",
            ))


def _check_promotion_gating(rules: dict[str, Any], report: PrimacyReport) -> None:
    """Check that critical promotions require human approval."""
    promo_rules = rules.get("promotion_rules", {})
    state_machine = rules.get("state_machine", {})

    # If there is an explicit human_approval_required flag, honor it
    if promo_rules.get("human_approval_required"):
        report.findings.append(PrimacyFinding(
            severity="info",
            message="Promotion rules explicitly require human approval.",
            context="promotion_rules.human_approval_required",
        ))
        return

    # Check if the state machine transitions for critical states have conditions
    transitions = state_machine.get("transitions", {})
    for state, targets in transitions.items():
        if not isinstance(targets, (list, dict)):
            continue
        target_list = targets if isinstance(targets, list) else list(targets.keys())
        for target in target_list:
            if target in _HUMAN_GATED_TRANSITIONS:
                # Look for conditions that suggest human review
                # In the current model, transitions are just lists —
                # no conditions means no human gating is enforced
                report.findings.append(PrimacyFinding(
                    severity="warning",
                    message=(
                        f"Transition {state} -> {target} has no explicit "
                        "human approval requirement."
                    ),
                    context=f"state_machine.transitions.{state}",
                ))


def _check_ai_agent_scope(seeds: dict[str, dict], report: PrimacyReport) -> None:
    """Check that AI agents in seeds have bounded scope."""
    from organvm_engine.seed.ownership import get_ai_agents

    for identity, seed in seeds.items():
        agents = get_ai_agents(seed)
        for agent in agents:
            scope = agent.get("scope", "")
            if isinstance(scope, str) and scope.lower() in _UNRESTRICTED_SCOPES:
                report.findings.append(PrimacyFinding(
                    severity="critical",
                    message=(
                        f"AI agent '{agent.get('type', 'unknown')}' has "
                        f"unrestricted scope '{scope}'. "
                        "AX-003 requires bounded AI agent access."
                    ),
                    context=identity,
                ))
            elif not scope:
                report.findings.append(PrimacyFinding(
                    severity="warning",
                    message=(
                        f"AI agent '{agent.get('type', 'unknown')}' has no "
                        "declared scope. Consider adding explicit bounds."
                    ),
                    context=identity,
                ))
