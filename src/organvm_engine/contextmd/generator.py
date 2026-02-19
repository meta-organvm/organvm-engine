"""CLAUDE.md section generator.

Takes registry data + seed data and produces the markdown content
for auto-generated sections at each level (repo, organ, workspace).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def generate_repo_section(
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
) -> str:
    """Generate the auto-generated section for a repo-level CLAUDE.md / GEMINI.md."""
    from organvm_engine.registry.query import find_repo
    from organvm_engine.contextmd.templates import (
        REPO_SECTION, format_produces_edge, format_consumes_edge, format_no_edges
    )
    
    result = find_repo(registry, repo_name)
    if not result:
        return f"<!-- ERROR: Repo '{repo_name}' not found -->"
        
    organ_key, repo_data = result
    organ_data = registry.get("organs", {}).get(organ_key, {})
    
    # Format edges
    edges = []
    if seed:
        for p in seed.get("produces", []) or []:
            if isinstance(p, dict):
                edges.append(format_produces_edge(p.get("target", "unknown"), p.get("artifact", "unknown"), p.get("event", "")))
            else:
                edges.append(f"- **Produces** → `{p}`")
        for c in seed.get("consumes", []) or []:
            if isinstance(c, dict):
                edges.append(format_consumes_edge(c.get("source", "unknown"), c.get("artifact", "unknown"), c.get("event", "")))
            else:
                edges.append(f"- **Consumes** ← `{c}`")
            
    edges_block = "\n".join(edges) if edges else format_no_edges()
    
    # Format siblings
    siblings = [r.get("name") for r in organ_data.get("repositories", []) if r.get("name") != repo_name]
    siblings_block = ", ".join(f"`{s}`" for s in siblings[:15])
    if len(siblings) > 15:
        siblings_block += f" ... and {len(siblings) - 15} more"
        
    # Governance notes
    gov = []
    if organ_key == "ORGAN-III":
        gov.append("- Strictly unidirectional flow: I→II→III. No dependencies on Theory (I).")
    elif organ_key == "ORGAN-II":
        gov.append("- Consumes Theory (I) concepts, produces artifacts for Commerce (III).")
    elif organ_key == "ORGAN-I":
        gov.append("- Foundational theory layer. No upstream dependencies.")
        
    governance_block = "\n".join(gov) if gov else "- *Standard ORGANVM governance applies*"

    return REPO_SECTION.format(
        organ_key=organ_key,
        organ_name=organ_data.get("name", organ_key),
        tier=repo_data.get("tier", "standard"),
        promotion_status=repo_data.get("promotion_status", "LOCAL"),
        org=org,
        repo_name=repo_name,
        edges_block=edges_block,
        siblings_block=siblings_block,
        governance_block=governance_block,
        timestamp=_timestamp()
    )


def generate_agents_section(
    repo_name: str,
    org: str,
    registry: dict,
    seed: dict | None = None,
) -> str:
    """Generate the auto-generated section for AGENTS.md."""
    from organvm_engine.registry.query import find_repo
    from organvm_engine.contextmd.templates import AGENTS_SECTION
    
    result = find_repo(registry, repo_name)
    if not result:
        return f"<!-- ERROR: Repo '{repo_name}' not found -->"
        
    organ_key, _ = result
    organ_data = registry.get("organs", {}).get(organ_key, {})
    
    # Format subscriptions
    subs = []
    if seed:
        for s in seed.get("subscriptions", []) or []:
            subs.append(f"- Event: `{s.get('event')}` → Action: {s.get('action')}")
    subs_block = "\n".join(subs) if subs else "- *No active event subscriptions*"
    
    # Format produces/consumes for agents
    prod = []
    cons = []
    if seed:
        for p in seed.get("produces", []) or []:
            if isinstance(p, dict):
                art = p.get("artifact") or p.get("type") or "unknown"
                target = p.get("target")
                if not target and p.get("consumers"):
                    targets = []
                    for consumer in p.get("consumers"):
                        if isinstance(consumer, dict):
                            targets.append(consumer.get("organ") or consumer.get("repo") or "unknown")
                        else:
                            targets.append(str(consumer))
                    target = ", ".join(targets)
                target = target or "unspecified"
                prod.append(f"- **Produce** `{art}` for `{target}`")
            else:
                prod.append(f"- **Produce** `{p}`")
        for c in seed.get("consumes", []) or []:
            if isinstance(c, dict):
                art = c.get("artifact") or c.get("type") or "unknown"
                source = c.get("source") or "unspecified"
                cons.append(f"- **Consume** `{art}` from `{source}`")
            else:
                cons.append(f"- **Consume** `{c}`")
            
    produces_block = "\n".join(prod) if prod else "- *No production responsibilities*"
    consumes_block = "\n".join(cons) if cons else "- *No external dependencies*"
    
    # Simple governance for agents
    gov = ["- Adhere to unidirectional flow: I→II→III", "- Never commit secrets or credentials"]

    return AGENTS_SECTION.format(
        organ_key=organ_key,
        organ_name=organ_data.get("name", organ_key),
        subscriptions_block=subs_block,
        produces_block=produces_block,
        consumes_block=consumes_block,
        governance_block="\n".join(gov),
        timestamp=_timestamp()
    )


def generate_organ_section(
    organ_key: str,
    registry: dict,
    seeds: list[dict] | None = None,
) -> str:
    """Generate the auto-generated section for an organ-level CLAUDE.md."""
    from organvm_engine.contextmd.templates import ORGAN_SECTION
    
    organ_data = registry.get("organs", {}).get(organ_key, {})
    if not organ_data:
        return f"<!-- ERROR: Organ '{organ_key}' not found -->"
        
    repos = organ_data.get("repositories", [])
    
    # Format repo list
    repo_lines = []
    for r in repos[:20]:
        repo_lines.append(f"- `{r.get('name')}` ({r.get('tier')}, {r.get('promotion_status')})")
    repo_list_block = "\n".join(repo_lines)
    if len(repos) > 20:
        repo_list_block += f"\n- ... and {len(repos) - 20} more"
        
    # Aggregate promotion distribution
    dist = {}
    for r in repos:
        s = r.get("promotion_status", "LOCAL")
        dist[s] = dist.get(s, 0) + 1
    promotion_block = ", ".join(f"{k}: {v}" for k, v in sorted(dist.items()))

    return ORGAN_SECTION.format(
        organ_key=organ_key,
        organ_name=organ_data.get("name", organ_key),
        repo_count=len(repos),
        flagship_count=len([r for r in repos if r.get("tier") == "flagship"]),
        standard_count=len([r for r in repos if r.get("tier") == "standard"]),
        infra_count=len([r for r in repos if r.get("tier") == "infrastructure"]),
        organ_edges_block="- *Edges computed from system-wide seed graph*",
        repo_list_block=repo_list_block,
        promotion_block=promotion_block,
        timestamp=_timestamp()
    )


def generate_workspace_section(
    registry: dict,
    seeds: list[dict] | None = None,
) -> str:
    """Generate the auto-generated section for the workspace-level CLAUDE.md."""
    from organvm_engine.contextmd.templates import WORKSPACE_SECTION
    
    organs = registry.get("organs", {})
    total_repos = 0
    rows = []
    
    for key, data in organs.items():
        repos = data.get("repositories", [])
        total_repos += len(repos)
        flagship = len([r for r in repos if r.get("tier") == "flagship"])
        # Status distribution
        s_dist = {}
        for r in repos:
            s = r.get("promotion_status", "LOCAL")
            s_dist[s] = s_dist.get(s, 0) + 1
        status_str = f"{s_dist.get('GRADUATED', 0)}G, {s_dist.get('PUBLIC_PROCESS', 0)}P"
        
        rows.append(f"| {key} | {len(repos)} | {flagship} | {status_str} |")
        
    return WORKSPACE_SECTION.format(
        total_repos=total_repos,
        organ_count=len(organs),
        organ_table_rows="\n".join(rows),
        seed_coverage=f"{len(seeds) if seeds else 0}/{total_repos}",
        ci_count="TBD",
        omega_met=8,
        omega_total=17,
        timestamp=_timestamp()
    )


def _timestamp() -> str:
    """Return ISO 8601 timestamp for sync tracking."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
