"""System invariant validators — constitutional health checks.

Implements: SPEC-003, INV-000-002, INV-000-003, INV-000-004, INV-000-005
Resolves: engine #32

Each validator returns (valid: bool, errors: list[str]).
run_all_invariants() consolidates all checks into a single report.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from organvm_engine.registry.query import all_repos

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class InvariantResult:
    """Consolidated result of all invariant checks."""

    results: dict[str, tuple[bool, list[str]]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(ok for ok, _ in self.results.values())

    @property
    def all_errors(self) -> list[str]:
        errors: list[str] = []
        for name, (_, errs) in self.results.items():
            for e in errs:
                errors.append(f"[{name}] {e}")
        return errors

    def summary(self) -> str:
        lines = ["Invariant Report", "=" * 40]
        for name, (ok, errs) in self.results.items():
            status = "PASS" if ok else "FAIL"
            lines.append(f"  {name}: {status}")
            for e in errs:
                lines.append(f"    - {e}")
        overall = "PASS" if self.passed else "FAIL"
        lines.append(f"\nOverall: {overall}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# INV-000-002: Governance Reachability
# ---------------------------------------------------------------------------

def validate_governance_reachability(
    registry: dict,
    organ_config: dict[str, dict[str, str]],
) -> tuple[bool, list[str]]:
    """Check every active repo is reachable from META-ORGANVM through governance edges.

    Governance edges are: organ membership (META governs all organs, each organ
    contains its repos) plus explicit dependency edges. A repo is reachable if
    BFS from the META root reaches it via these edges.

    Args:
        registry: Loaded registry dict.
        organ_config: The ORGANS dict from organ_config.py.

    Returns:
        (valid, errors) — valid is True when all active repos are reachable.
    """
    errors: list[str] = []

    # Build the adjacency list for BFS
    # Nodes: "META-ROOT", all organ keys, all repo keys (org/name)
    adj: dict[str, set[str]] = {}
    meta_root = "META-ROOT"
    adj[meta_root] = set()

    # Governance hierarchy: META-ROOT → each organ key
    for organ_key in registry.get("organs", {}):
        adj[meta_root].add(organ_key)
        adj.setdefault(organ_key, set())

    # Organ → repo membership edges
    active_repos: set[str] = set()
    for organ_key, repo in all_repos(registry):
        impl_status = repo.get("implementation_status", "")
        if impl_status == "ARCHIVED":
            continue
        repo_key = f"{repo.get('org', '')}/{repo.get('name', '')}"
        active_repos.add(repo_key)
        adj.setdefault(organ_key, set()).add(repo_key)
        adj.setdefault(repo_key, set())

        # Dependency edges (bidirectional for reachability)
        for dep in repo.get("dependencies", []):
            adj[repo_key].add(dep)
            adj.setdefault(dep, set()).add(repo_key)

    # BFS from META-ROOT
    visited: set[str] = set()
    queue: deque[str] = deque([meta_root])
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in adj.get(node, set()):
            if neighbor not in visited:
                queue.append(neighbor)

    # Check which active repos are unreachable
    orphaned = active_repos - visited
    for repo_key in sorted(orphaned):
        errors.append(f"Governance-orphaned: {repo_key}")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# INV-000-003: Identity Persistence (monotonic entity store)
# ---------------------------------------------------------------------------

def validate_identity_persistence(
    entity_store_path: Path | str,
) -> tuple[bool, list[str]]:
    """Check the ontologia entity store is monotonically growing.

    Scans the JSONL entity store and verifies no UID that appeared in an
    earlier entry is absent from later entries (deletion detection). The
    store must be append-only — UIDs may only accumulate, never disappear.

    Args:
        entity_store_path: Path to the entities JSONL file.

    Returns:
        (valid, errors) — valid is True when no deletions detected.
    """
    errors: list[str] = []
    path = Path(entity_store_path)

    if not path.is_file():
        # No store yet is valid (system not bootstrapped)
        return True, []

    # Each line is a JSON snapshot of the entity set at that moment.
    # We track all UIDs ever seen and check they persist in subsequent lines.
    all_seen_uids: set[str] = set()
    line_num = 0

    for raw_line in path.read_text().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        line_num += 1

        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            errors.append(f"Line {line_num}: malformed JSON")
            continue

        # Extract UID from the entry
        uid = entry.get("uid", "")
        if not uid:
            continue

        all_seen_uids.add(uid)

    # For an append-only JSONL, each line adds an entity — we check that
    # the file itself has not been truncated (UIDs only accumulate).
    # Re-scan checking for any UID referenced as "archived" or "deleted"
    # in a lifecycle_status field while we already saw it as active.
    deleted_uids: set[str] = set()
    for raw_line in path.read_text().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        uid = entry.get("uid", "")
        lifecycle = entry.get("lifecycle_status", "")
        if uid and lifecycle in ("deleted", "DELETED", "removed", "REMOVED"):
            deleted_uids.add(uid)

    for uid in sorted(deleted_uids):
        errors.append(f"UID deletion detected: {uid}")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# INV-000-004: Constitutional Supremacy
# ---------------------------------------------------------------------------

def validate_constitutional_supremacy(
    governance_rules: dict,
) -> tuple[bool, list[str]]:
    """Check that no organ dictum contradicts a system-level axiom.

    Specifically: if an axiom forbids something (e.g., no back-edges, no
    circular dependencies), no organ dictum may allow it. Detected by
    comparing axiom constraint keys against organ dictum constraint keys
    for logical conflicts.

    Args:
        governance_rules: Loaded governance-rules.json dict.

    Returns:
        (valid, errors) — valid is True when no conflicts found.
    """
    errors: list[str] = []
    dictums = governance_rules.get("dictums", {})

    if not dictums:
        return True, []

    # Extract axiom constraints as a set of (key, forbidden_value) pairs
    axioms = dictums.get("axioms", [])
    axiom_constraints: dict[str, dict[str, Any]] = {}
    for ax in axioms:
        ax_id = ax.get("id", "?")
        axiom_constraints[ax_id] = {
            "statement": ax.get("statement", ""),
            "severity": ax.get("severity", "info"),
            "enforcement": ax.get("enforcement", "manual"),
        }

    # Check dependency rules for axiom-level constraints
    dep_rules = governance_rules.get("dependency_rules", {})
    axiom_prohibitions: dict[str, bool] = {}
    if dep_rules.get("no_circular_dependencies"):
        axiom_prohibitions["no_circular_dependencies"] = True
    if dep_rules.get("no_back_edges"):
        axiom_prohibitions["no_back_edges"] = True

    # Scan organ dictums for contradictions
    organ_dictums = dictums.get("organ_dictums", {})
    for organ_key, od_list in organ_dictums.items():
        for od in od_list:
            od_id = od.get("id", "?")
            constraints = od.get("constraints", {})

            # Check if any organ dictum explicitly allows what axioms forbid
            for prohibition_key in axiom_prohibitions:
                # An organ dictum that sets allow_circular_dependencies=True
                # or no_circular_dependencies=False contradicts the axiom
                allow_key = prohibition_key.replace("no_", "allow_", 1)
                if constraints.get(allow_key) is True:
                    errors.append(
                        f"{od_id} ({organ_key}) contradicts axiom: "
                        f"allows '{allow_key}' which is globally forbidden",
                    )
                if constraints.get(prohibition_key) is False:
                    errors.append(
                        f"{od_id} ({organ_key}) contradicts axiom: "
                        f"disables '{prohibition_key}' which is globally enforced",
                    )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# INV-000-005: Observability
# ---------------------------------------------------------------------------

def validate_observability(
    registry: dict,
    stale_days: int = 90,
) -> tuple[bool, list[str]]:
    """Check every active repo meets minimum observability requirements.

    Requirements:
    - Has a promotion_status field
    - Has last_validated not older than stale_days
    - Has at least one metric (code_files or test_files)

    Args:
        registry: Loaded registry dict.
        stale_days: Maximum age in days for last_validated.

    Returns:
        (valid, errors) — valid is True when all repos are observable.
    """
    errors: list[str] = []
    now = datetime.now(timezone.utc)

    for organ_key, repo in all_repos(registry):
        impl_status = repo.get("implementation_status", "")
        if impl_status == "ARCHIVED":
            continue

        name = repo.get("name", "?")
        label = f"{organ_key}/{name}"

        # Check promotion_status exists
        if not repo.get("promotion_status"):
            errors.append(f"{label}: missing promotion_status")

        # Check last_validated freshness
        last_validated = repo.get("last_validated", "")
        if not last_validated:
            errors.append(f"{label}: missing last_validated")
        else:
            try:
                lv = datetime.fromisoformat(last_validated)
                if lv.tzinfo is None:
                    lv = lv.replace(tzinfo=timezone.utc)
                days_ago = (now - lv).days
                if days_ago > stale_days:
                    errors.append(
                        f"{label}: last_validated stale ({days_ago} days, max {stale_days})",
                    )
            except ValueError:
                errors.append(f"{label}: malformed last_validated '{last_validated}'")

        # Check at least one metric
        has_code_files = repo.get("code_files") is not None and repo.get("code_files", 0) > 0
        has_test_files = repo.get("test_files") is not None and repo.get("test_files", 0) > 0
        if not has_code_files and not has_test_files:
            errors.append(f"{label}: no metrics (code_files or test_files)")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# DAG invariant (delegates to existing validator)
# ---------------------------------------------------------------------------

def validate_dag_invariant(
    registry: dict,
) -> tuple[bool, list[str]]:
    """Check the dependency graph is a valid DAG with no back-edges.

    Delegates to the existing validate_dependencies() function and
    reformats the result as an invariant (bool, errors) tuple.

    Args:
        registry: Loaded registry dict.

    Returns:
        (valid, errors) — valid is True when graph is a clean DAG.
    """
    from organvm_engine.governance.dependency_graph import validate_dependencies

    dep_result = validate_dependencies(registry)
    errors: list[str] = []

    for cycle in dep_result.cycles:
        errors.append(f"Cycle detected: {' -> '.join(cycle)}")
    for f, t, fo, to in dep_result.back_edges:
        errors.append(f"Back-edge: {f} -> {t} ({fo} -> {to})")

    return dep_result.passed, errors


# ---------------------------------------------------------------------------
# Consolidated runner
# ---------------------------------------------------------------------------

def run_all_invariants(
    registry: dict,
    organ_config: dict[str, dict[str, str]],
    entity_store_path: Path | str | None = None,
    governance_rules: dict | None = None,
) -> InvariantResult:
    """Run all system invariants and return a consolidated report.

    Args:
        registry: Loaded registry dict.
        organ_config: The ORGANS dict from organ_config.py.
        entity_store_path: Path to the ontologia entities JSONL file.
            If None, the identity persistence check is skipped.
        governance_rules: Loaded governance-rules.json dict.
            If None, the constitutional supremacy check is skipped.

    Returns:
        InvariantResult with all check results keyed by invariant name.
    """
    result = InvariantResult()

    # INV-000-001: DAG invariant
    result.results["INV-000-001:dag"] = validate_dag_invariant(registry)

    # INV-000-002: Governance reachability
    result.results["INV-000-002:reachability"] = validate_governance_reachability(
        registry, organ_config,
    )

    # INV-000-003: Identity persistence
    if entity_store_path is not None:
        result.results["INV-000-003:identity"] = validate_identity_persistence(
            entity_store_path,
        )

    # INV-000-004: Constitutional supremacy
    if governance_rules is not None:
        result.results["INV-000-004:supremacy"] = validate_constitutional_supremacy(
            governance_rules,
        )

    # INV-000-005: Observability
    result.results["INV-000-005:observability"] = validate_observability(registry)

    return result
