"""Runbook generator — produces operational runbooks from governance rules + policies + SOPs.

Generates structured markdown runbooks with trigger→check→action→verify format.
Positions Omega criterion #4 (runbooks validated).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Runbook templates
# ---------------------------------------------------------------------------

RUNBOOK_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "rb-repo-promotion",
        "title": "Repo Promotion Procedure",
        "source_policy": "pol-promote-ready",
        "source_sop": "SOP--promotion-and-state-transitions.md",
        "trigger": (
            "PromotionSensor detects a CANDIDATE repo with all promotion criteria met "
            "(CI workflow, platinum status, ACTIVE implementation)."
        ),
        "checks": [
            "Verify CI workflow passes on main branch",
            "Confirm platinum_status is true in registry",
            "Confirm implementation_status is ACTIVE",
            "Check for open blockers or known issues",
            "Verify seed.yaml is present and valid",
        ],
        "actions": [
            "Run `organvm governance promote <repo> PUBLIC_PROCESS`",
            "Update registry-v2.json with new promotion_status",
            "Verify promotion with `organvm registry show <repo>`",
            "Commit registry change with `registry: promote <repo> to PUBLIC_PROCESS`",
        ],
        "verification": [
            "Run `organvm registry validate` — no errors",
            "Run `organvm ontologia sense` — no unexpected signals",
            "Check soak dashboard for stability (next 24h)",
        ],
    },
    {
        "id": "rb-ci-failure-response",
        "title": "CI Failure Response",
        "source_policy": "pol-missing-ci",
        "source_sop": "SOP--cicd-resilience-and-recovery.md",
        "trigger": (
            "CISensor detects a missing CI workflow or a persistent CI failure "
            "on a non-infrastructure, non-archived repo."
        ),
        "checks": [
            "Identify the failing repo and its organ",
            "Check if the repo has an existing .github/workflows/ directory",
            "Check if failure is transient (infrastructure) or persistent (code)",
            "Review recent commits for potential cause",
        ],
        "actions": [
            "For missing CI: create ci.yml workflow based on repo type (Python/TS/docs)",
            "For failing CI: triage the failure (test, lint, build, dependency)",
            "Fix the root cause — do not disable the check",
            "Push fix and verify CI passes",
        ],
        "verification": [
            "CI workflow passes on main branch",
            "Run `organvm ontologia sense --sensor ci_sensor` — repo no longer flagged",
            "Update registry ci_workflow field if newly added",
        ],
    },
    {
        "id": "rb-registry-update",
        "title": "Registry Update Protocol",
        "source_policy": None,
        "source_sop": None,
        "trigger": (
            "A repo field needs updating in registry-v2.json "
            "(status change, new field, correction)."
        ),
        "checks": [
            "Read current registry entry with `organvm registry show <repo>`",
            "Verify the intended change is correct",
            "Check governance constraints (e.g., promotion requires prerequisites)",
        ],
        "actions": [
            "Run `organvm registry update <repo> <field> <value>`",
            "Or: targeted JSON edit in registry-v2.json (read-before-write)",
            "NEVER overwrite the entire registry file",
            "Commit with `registry: update <repo> <field>`",
        ],
        "verification": [
            "Run `organvm registry validate` — no errors",
            "Run `organvm registry show <repo>` — field reflects new value",
            "Verify entity count hasn't changed (guard against data loss)",
        ],
    },
    {
        "id": "rb-soak-incident",
        "title": "Soak Incident Handling",
        "source_policy": None,
        "source_sop": None,
        "trigger": (
            "SoakSensor detects validation failures or metric anomalies "
            "in the daily soak snapshot."
        ),
        "checks": [
            "Identify which repos are failing and why",
            "Check if failure is new (compare with previous snapshot)",
            "Determine if failure is blocking Omega #1/#3/#17 soak criteria",
        ],
        "actions": [
            "For test failures: fix the failing tests",
            "For dependency failures: update or pin the dependency",
            "For anomalies: investigate metric drift and root cause",
            "Run targeted tests: `pytest <repo>/tests/ -v`",
        ],
        "verification": [
            "All previously failing repos now pass",
            "Run `organvm ontologia snapshot --compare` — no new drift",
            "Soak streak remains unbroken",
        ],
    },
    {
        "id": "rb-entity-rename",
        "title": "Entity Rename Procedure",
        "source_policy": "pol-naming-drift",
        "source_sop": None,
        "trigger": (
            "Naming drift detected: entity primary name in ontologia doesn't match "
            "the repo name in the registry."
        ),
        "checks": [
            "Identify the entity with `organvm ontologia resolve <name>`",
            "Check name history with `organvm ontologia history <uid>`",
            "Determine which name is canonical (registry or ontologia)",
        ],
        "actions": [
            "If registry is canonical: update ontologia name record",
            "If ontologia is canonical: update registry name",
            "Record the rename event in ontologia event log",
            "Update any references (seed.yaml, documentation)",
        ],
        "verification": [
            "Run `organvm ontologia tensions` — naming conflict resolved",
            "Run `organvm ontologia resolve <name>` — resolves correctly",
            "Run `organvm registry show <repo>` — name consistent",
        ],
    },
    {
        "id": "rb-system-health-check",
        "title": "System Health Check",
        "source_policy": None,
        "source_sop": "SOP--autopoietic-systems-diagnostics.md",
        "trigger": (
            "Scheduled daily check, or triggered by incident/alert."
        ),
        "checks": [
            "Run `organvm ontologia sense` — review all sensor outputs",
            "Run `organvm ontologia tensions` — check for structural issues",
            "Run `organvm ontologia snapshot --compare` — check for drift",
            "Run `organvm omega status` — check scorecard progress",
        ],
        "actions": [
            "Address any HIGH severity tensions first",
            "Process policy violations from `organvm ontologia policies --evaluate`",
            "Create revisions for detected issues",
            "Update registry for any out-of-date fields",
        ],
        "verification": [
            "All high-severity tensions addressed or tracked",
            "No unacknowledged policy violations",
            "Omega score stable or improving",
            "Soak streak intact",
        ],
    },
]


# ---------------------------------------------------------------------------
# Runbook generation
# ---------------------------------------------------------------------------

def generate_runbook(template: dict[str, Any]) -> str:
    """Generate a single runbook as markdown from a template."""
    lines: list[str] = []
    lines.append(f"# {template['title']}")
    lines.append("")
    lines.append(f"**Runbook ID:** `{template['id']}`")
    lines.append(f"**Generated:** {_now_iso()[:19]}Z")

    if template.get("source_policy"):
        lines.append(f"**Source Policy:** `{template['source_policy']}`")
    if template.get("source_sop"):
        lines.append(f"**Source SOP:** `{template['source_sop']}`")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Trigger
    lines.append("## Trigger")
    lines.append("")
    lines.append(template["trigger"])
    lines.append("")

    # Checks
    lines.append("## Pre-Checks")
    lines.append("")
    for check in template["checks"]:
        lines.append(f"- [ ] {check}")
    lines.append("")

    # Actions
    lines.append("## Actions")
    lines.append("")
    for i, action in enumerate(template["actions"], 1):
        lines.append(f"{i}. {action}")
    lines.append("")

    # Verification
    lines.append("## Verification")
    lines.append("")
    for verify in template["verification"]:
        lines.append(f"- [ ] {verify}")
    lines.append("")

    lines.append("---")
    lines.append("*Auto-generated by organvm-engine runbook generator*")
    lines.append("")

    return "\n".join(lines)


def generate_all_runbooks(
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate all runbooks and write to disk.

    Returns:
        {"runbooks": [{"id": ..., "title": ..., "path": ...}], "count": int}
    """
    if output_dir is None:
        # Default to praxis-perpetua/runbooks/ if available
        try:
            from organvm_engine.paths import workspace_root
            praxis = workspace_root() / "meta-organvm" / "praxis-perpetua" / "runbooks"
        except Exception:
            praxis = Path.cwd() / "runbooks"
        output_dir = praxis

    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for template in RUNBOOK_TEMPLATES:
        content = generate_runbook(template)
        filename = f"{template['id']}.md"
        path = output_dir / filename
        path.write_text(content)
        results.append({
            "id": template["id"],
            "title": template["title"],
            "path": str(path),
        })

    # Write index
    index_lines = ["# Operational Runbooks", ""]
    index_lines.append(f"Generated: {_now_iso()[:19]}Z")
    index_lines.append(f"Total: {len(results)} runbooks")
    index_lines.append("")
    index_lines.append("| ID | Title | File |")
    index_lines.append("|---|---|---|")
    for r in results:
        index_lines.append(f"| `{r['id']}` | {r['title']} | [{r['id']}.md]({r['id']}.md) |")
    index_lines.append("")
    (output_dir / "INDEX.md").write_text("\n".join(index_lines))

    return {"runbooks": results, "count": len(results)}


def verify_runbooks(
    runbooks_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify that all expected runbooks exist and are current.

    Returns:
        {"valid": bool, "missing": [...], "stale": [...]}
    """
    if runbooks_dir is None:
        try:
            from organvm_engine.paths import workspace_root
            runbooks_dir = workspace_root() / "meta-organvm" / "praxis-perpetua" / "runbooks"
        except Exception:
            return {"valid": False, "error": "Cannot resolve runbooks directory"}

    if not runbooks_dir.is_dir():
        return {
            "valid": False,
            "missing": [t["id"] for t in RUNBOOK_TEMPLATES],
            "stale": [],
        }

    missing: list[str] = []
    stale: list[str] = []

    for template in RUNBOOK_TEMPLATES:
        path = runbooks_dir / f"{template['id']}.md"
        if not path.is_file():
            missing.append(template["id"])
        else:
            # Check if the file is older than 30 days
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                age = (datetime.now(timezone.utc) - mtime).days
                if age > 30:
                    stale.append(template["id"])
            except OSError:
                stale.append(template["id"])

    return {
        "valid": not missing,
        "missing": missing,
        "stale": stale,
        "total_expected": len(RUNBOOK_TEMPLATES),
        "found": len(RUNBOOK_TEMPLATES) - len(missing),
    }
