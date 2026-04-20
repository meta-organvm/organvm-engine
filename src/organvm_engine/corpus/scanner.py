"""Corpus scanner — reads zettelkasten sidecar, Layer 2 frontmatter, and seed.yaml implements fields.

Phase 1 of the corpus knowledge graph pipeline (IRF-SYS-104).
Zero NLP. Pure structural scan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from organvm_engine.corpus.graph import CorpusGraph, GraphEdge, GraphNode


def _read_yaml_frontmatter(path: Path) -> dict[str, Any]:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _scan_zettelkasten(sidecar_path: Path, graph: CorpusGraph) -> None:
    """Read .zettel-index.yaml and create transcript + concept nodes."""
    data = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

    # Transcript nodes
    for trx_id, trx_data in data.get("transcripts", {}).items():
        graph.add_node(GraphNode(
            uid=trx_id,
            node_type="transcript",
            title=trx_data.get("title", trx_id),
            metadata={
                "file": trx_data.get("file", ""),
                "depth": trx_data.get("depth", 0),
                "qa_own": trx_data.get("qa_own", 0),
                "line_count": trx_data.get("line_count", 0),
                "layer2_extractions": trx_data.get("layer2_extractions", 0),
            },
        ))
        # Parent → child edges
        for child_id in trx_data.get("children", []):
            graph.add_edge(GraphEdge(
                source=trx_id,
                target=child_id,
                edge_type="BRANCHES_TO",
            ))

    # Compiled spec nodes
    for spec_id, spec_data in data.get("compiled_specs", {}).items():
        graph.add_node(GraphNode(
            uid=spec_id,
            node_type="spec",
            title=spec_data.get("title", spec_id),
            metadata={
                "file": spec_data.get("file", ""),
                "line_count": spec_data.get("line_count", 0),
                "compilation_quality": spec_data.get("compilation_quality", ""),
            },
        ))
        # COMPILES edges from source transcripts
        for src_trx in spec_data.get("source_transcripts", []):
            graph.add_edge(GraphEdge(
                source=src_trx,
                target=spec_id,
                edge_type="COMPILES",
            ))

    # Cross-trunk concept nodes
    for concept_id, concept_data in data.get("cross_trunk_concepts", {}).items():
        graph.add_node(GraphNode(
            uid=f"concept:{concept_id}",
            node_type="concept",
            title=concept_id,
            metadata={
                "description": concept_data.get("description", ""),
                "trunks": concept_data.get("trunks", []),
                "primary_source": concept_data.get("primary_source", ""),
            },
        ))
        # DEFINES edges from primary source transcript
        primary = concept_data.get("primary_source")
        if primary:
            graph.add_edge(GraphEdge(
                source=primary,
                target=f"concept:{concept_id}",
                edge_type="DEFINES",
            ))
        # REFERENCES edges from all present_in transcripts
        for trx_id in concept_data.get("present_in", []):
            if trx_id != primary:
                graph.add_edge(GraphEdge(
                    source=trx_id,
                    target=f"concept:{concept_id}",
                    edge_type="REFERENCES",
                ))


def _scan_layer2_frontmatter(corpus_dir: Path, graph: CorpusGraph) -> None:
    """Scan Layer 2 extracted module files for EXTRACTED_FROM edges."""
    # Walk all .md files in the corpus EXCEPT archive_original/ and .claude/
    for md_file in corpus_dir.rglob("*.md"):
        rel = md_file.relative_to(corpus_dir)
        if str(rel).startswith("archive_original/") or str(rel).startswith(".claude/"):
            continue
        fm = _read_yaml_frontmatter(md_file)
        if not fm.get("source_file") and not fm.get("source_files"):
            continue

        doc_uid = f"doc:{rel}"
        graph.add_node(GraphNode(
            uid=doc_uid,
            node_type="document",
            title=fm.get("title", md_file.stem),
            metadata={
                "file": str(rel),
                "status": fm.get("status", ""),
                "tags": fm.get("tags", []),
                "date_extracted": fm.get("date_extracted", ""),
                "source_qa_index": fm.get("source_qa_index"),
            },
        ))

        # EXTRACTED_FROM edge to source transcript via provenance
        source_file = fm.get("source_file") or ""
        if source_file:
            # Resolve source_file to TRX ID via provenance map
            # For now, create edge to the filename (linker resolves to TRX ID later)
            graph.add_edge(GraphEdge(
                source=doc_uid,
                target=f"transcript_file:{source_file}",
                edge_type="EXTRACTED_FROM",
                metadata={"source_qa_index": fm.get("source_qa_index")},
            ))


def _scan_seed_implements(workspace_root: Path, graph: CorpusGraph) -> None:
    """Scan seed.yaml implements[] fields for IMPLEMENTS edges."""
    for seed_path in workspace_root.rglob("seed.yaml"):
        # Skip deep paths (node_modules, .venv, etc.)
        rel = seed_path.relative_to(workspace_root)
        if any(p.startswith(".") or p in ("node_modules", ".venv", "__pycache__")
               for p in rel.parts):
            continue
        # Only go 3 levels deep
        if len(rel.parts) > 3:
            continue

        try:
            data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue

        if not data or not isinstance(data, dict):
            continue

        implements = data.get("implements", [])
        if not implements:
            continue

        repo_name = data.get("repo", seed_path.parent.name)
        org = data.get("org", "")
        repo_uid = f"repo:{org}/{repo_name}"

        graph.add_node(GraphNode(
            uid=repo_uid,
            node_type="repo",
            title=repo_name,
            metadata={
                "org": org,
                "organ": str(data.get("organ", "")),
                "promotion_status": data.get("metadata", {}).get("promotion_status", ""),
            },
        ))

        for impl in implements:
            concept = impl.get("concept", "")
            if not concept:
                continue
            concept_uid = f"concept:{concept}"
            graph.add_edge(GraphEdge(
                source=repo_uid,
                target=concept_uid,
                edge_type="IMPLEMENTS",
                metadata={"aspect": impl.get("aspect", "")},
            ))


def _resolve_provenance(sidecar_path: Path, graph: CorpusGraph) -> None:
    """Replace transcript_file: edges with actual TRX ID references."""
    data = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    provenance = data.get("layer2_provenance", {})

    resolved_edges: list[GraphEdge] = []
    for edge in graph.edges:
        if edge.target.startswith("transcript_file:"):
            filename = edge.target[len("transcript_file:"):]
            trx_id = provenance.get(filename)
            if trx_id:
                resolved_edges.append(GraphEdge(
                    source=edge.source,
                    target=trx_id,
                    edge_type=edge.edge_type,
                    metadata=edge.metadata,
                ))
            else:
                resolved_edges.append(edge)  # Keep unresolved for gap detection
        else:
            resolved_edges.append(edge)

    graph.edges = resolved_edges


# Numbered SPEC directories → human-meaningful concept IDs.
# Named SPECs (SPEC-019-system-manifestation) and pure-named dirs (era-model)
# derive their concept ID from the directory name itself.
_NUMBERED_SPEC_CONCEPTS: dict[str, str] = {
    "SPEC-000": "system_manifesto",
    "SPEC-001": "ontology_charter",
    "SPEC-002": "entity_primitives",
    "SPEC-003": "invariant_register",
    "SPEC-004": "logical_specification",
    "SPEC-005": "architectural_specification",
    "SPEC-006": "traceability_matrix",
    "SPEC-007": "verification_plan",
    "SPEC-008": "evolution_law",
    "SPEC-009": "architectural_patterns",
    "SPEC-010": "pipeline_stages",
    "SPEC-011": "system_dynamics",
    "SPEC-012": "workspace_topology",
    "SPEC-013": "agent_swarm_topology",
    "SPEC-014": "resource_compute_constraints",
    "SPEC-015": "escalation_attention_policy",
    "SPEC-016": "epistemic_routing",
    "SPEC-017": "agent_authority_matrix",
}

# Directories in specs/ that are not concepts
_SPEC_SKIP_DIRS = {"library", "sources", "__pycache__"}

# Files that indicate a directory defines a concept
_CONCEPT_INDICATORS = {"grounding.md", "specification.md", "spec.md"}


def _derive_concept_id(dirname: str) -> str | None:
    """Derive a concept ID from a SPEC directory name.

    Returns None if the directory is not a concept-defining SPEC.
    """
    # Exact match in numbered mapping
    if dirname in _NUMBERED_SPEC_CONCEPTS:
        return _NUMBERED_SPEC_CONCEPTS[dirname]

    # Named SPEC: SPEC-NNN-some-name → some_name
    if dirname.startswith("SPEC-") and "-" in dirname[5:]:
        # Strip SPEC-NNN- prefix, convert hyphens to underscores
        parts = dirname.split("-", 2)  # ['SPEC', 'NNN', 'rest-of-name']
        if len(parts) >= 3:
            return parts[2].replace("-", "_")

    # Pure named directory: era-model → era_model
    if not dirname.startswith("SPEC-"):
        return dirname.replace("-", "_")

    return None


def _scan_spec_directories(corpus_dir: Path, graph: CorpusGraph) -> None:
    """Discover concept nodes from SPEC directories in specs/.

    Each SPEC directory that contains a grounding.md, specification.md,
    or spec.md is treated as defining a concept. Concepts already present
    in the graph (from cross_trunk_concepts) are skipped.
    """
    specs_dir = corpus_dir / "specs"
    if not specs_dir.is_dir():
        return

    for entry in sorted(specs_dir.iterdir()):
        if not entry.is_dir():
            continue
        dirname = entry.name

        # Skip non-concept directories
        if dirname in _SPEC_SKIP_DIRS:
            continue

        # Must contain a concept-indicating file
        if not any((entry / f).is_file() for f in _CONCEPT_INDICATORS):
            continue

        concept_id = _derive_concept_id(dirname)
        if concept_id is None:
            continue

        uid = f"concept:{concept_id}"

        # Skip if concept already exists (from cross_trunk_concepts)
        if graph.get_node(uid) is not None:
            continue

        # Read description from grounding.md frontmatter or first heading
        description = ""
        for indicator in _CONCEPT_INDICATORS:
            indicator_path = entry / indicator
            if indicator_path.is_file():
                fm = _read_yaml_frontmatter(indicator_path)
                description = fm.get("description", fm.get("title", ""))
                if not description:
                    # Fall back to first markdown heading
                    text = indicator_path.read_text(encoding="utf-8", errors="ignore")
                    for line in text.splitlines():
                        if line.startswith("# "):
                            description = line[2:].strip()
                            break
                break

        graph.add_node(GraphNode(
            uid=uid,
            node_type="concept",
            title=concept_id,
            metadata={
                "description": description,
                "source": f"specs/{dirname}",
                "discovery": "spec_directory",
            },
        ))

        # DEFINES edge from the spec directory (as a source reference)
        graph.add_edge(GraphEdge(
            source=f"spec_dir:{dirname}",
            target=uid,
            edge_type="DEFINES",
        ))


def scan_corpus(
    corpus_dir: Path | str,
    workspace_root: Path | str | None = None,
) -> CorpusGraph:
    """Build the corpus knowledge graph from filesystem.

    Args:
        corpus_dir: Path to post-flood/ directory
        workspace_root: Path to ~/Workspace/ (for seed.yaml scanning)

    Returns:
        Populated CorpusGraph
    """
    corpus_dir = Path(corpus_dir)
    ws = Path(workspace_root) if workspace_root else corpus_dir.parent.parent

    graph = CorpusGraph()
    sidecar = corpus_dir / "archive_original" / ".zettel-index.yaml"

    if sidecar.is_file():
        _scan_zettelkasten(sidecar, graph)

    _scan_spec_directories(corpus_dir, graph)

    _scan_layer2_frontmatter(corpus_dir, graph)

    _scan_seed_implements(ws, graph)

    if sidecar.is_file():
        _resolve_provenance(sidecar, graph)

    return graph
