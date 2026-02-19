"""Markdown templates for auto-generated CLAUDE.md sections.

Templates use str.format() with named placeholders. Each template
targets a specific level: workspace, organ, or repo.
"""

from __future__ import annotations

# ── Repo-level template ───────────────────────────────────────────

REPO_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## System Context (auto-generated — do not edit)

**Organ:** {organ_key} ({organ_name}) | **Tier:** {tier} | **Status:** {promotion_status}
**Org:** `{org}` | **Repo:** `{repo_name}`

### Edges
{edges_block}

### Siblings in {organ_name}
{siblings_block}

### Governance
{governance_block}

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""

# ── Organ-level template ──────────────────────────────────────────

ORGAN_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## Organ Map (auto-generated — do not edit)

**{organ_key}: {organ_name}** | {repo_count} repos | {flagship_count} flagship | {standard_count} standard | {infra_count} infrastructure

### Inter-Organ Edges
{organ_edges_block}

### Repos
{repo_list_block}

### Promotion Pipeline
{promotion_block}

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""

# ── Workspace-level template ──────────────────────────────────────

WORKSPACE_SECTION = """\
<!-- ORGANVM:AUTO:START -->
## System Overview (auto-generated — do not edit)

**{total_repos} repos** across **{organ_count} organs** + personal workspace

| Organ | Repos | Flagship | Status |
|-------|-------|----------|--------|
{organ_table_rows}

### System Health
- Seed coverage: {seed_coverage}
- CI workflows: {ci_count}
- Omega progress: {omega_met}/{omega_total} criteria met

*Last synced: {timestamp}*
<!-- ORGANVM:AUTO:END -->"""


# ── Edge formatting helpers ───────────────────────────────────────

def format_produces_edge(target: str, artifact: str, event: str = "") -> str:
    """Format a single produces edge as a markdown line."""
    event_str = f" (event: `{event}`)" if event else ""
    return f"- **Produces** → `{target}`: {artifact}{event_str}"


def format_consumes_edge(source: str, artifact: str, event: str = "") -> str:
    """Format a single consumes edge as a markdown line."""
    event_str = f" (event: `{event}`)" if event else ""
    return f"- **Consumes** ← `{source}`: {artifact}{event_str}"


def format_no_edges() -> str:
    """Placeholder when no edges exist."""
    return "- *No inter-repo edges declared in seed.yaml*"
