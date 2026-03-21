"""Conversation corpus surface discovery and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from organvm_engine.paths import PathConfig, resolve_path_config

SURFACE_FILENAMES = {
    "manifest": "surface-manifest.json",
    "context": "mcp-context.json",
    "bundle": "surface-bundle.json",
}

SCHEMA_FILES = {
    "manifest": "conversation-corpus-surface-manifest.schema.json",
    "context": "conversation-corpus-mcp-context.schema.json",
    "bundle": "conversation-corpus-surface-bundle.schema.json",
}


def schema_definitions_dir(
    workspace: Path | str | None = None,
    *,
    config: PathConfig | None = None,
) -> Path | None:
    """Resolve the canonical schema-definitions directory."""
    candidates: list[Path] = []
    if workspace is not None:
        candidates.append(Path(workspace).expanduser().resolve() / "meta-organvm" / "schema-definitions")

    cfg = resolve_path_config(config)
    candidates.extend(
        [
            cfg.workspace_root().resolve() / "meta-organvm" / "schema-definitions",
            Path(__file__).resolve().parents[4] / "schema-definitions",
            Path.home() / "Workspace" / "meta-organvm" / "schema-definitions",
        ],
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def schema_path(
    schema_key: str,
    workspace: Path | str | None = None,
    *,
    config: PathConfig | None = None,
) -> Path | None:
    """Resolve a specific surface schema path."""
    schema_root = schema_definitions_dir(workspace, config=config)
    if schema_root is None:
        return None
    filename = SCHEMA_FILES[schema_key]
    path = schema_root / "schemas" / filename
    return path if path.is_file() else None


def collect_conversation_corpus_surfaces(
    workspace: Path | str | None = None,
    *,
    config: PathConfig | None = None,
    repo: str | None = None,
) -> dict[str, Any]:
    """Discover and validate conversation corpus surfaces in a workspace."""
    cfg = resolve_path_config(config)
    workspace_root = (
        Path(workspace).expanduser().resolve() if workspace is not None else cfg.workspace_root().resolve()
    )

    surfaces = []
    for repo_root in _candidate_repositories(workspace_root, repo=repo):
        surface = _inspect_repo(repo_root, workspace_root)
        if surface is not None:
            surfaces.append(surface)

    surfaces.sort(key=lambda item: (item["organization"], item["repo"]))
    valid_count = sum(1 for item in surfaces if item["state"] == "valid")
    partial_count = sum(1 for item in surfaces if item["state"] == "partial")
    invalid_count = sum(1 for item in surfaces if item["state"] == "invalid")
    error_count = sum(
        validation["error_count"]
        for item in surfaces
        for validation in item["validation"].values()
        if validation is not None
    )

    return {
        "workspace": str(workspace_root),
        "surface_count": len(surfaces),
        "valid_count": valid_count,
        "partial_count": partial_count,
        "invalid_count": invalid_count,
        "error_count": error_count,
        "surfaces": surfaces,
    }


def render_conversation_corpus_surfaces(report: dict[str, Any]) -> str:
    """Render discovered conversation corpus surfaces as text."""
    lines = [
        "Conversation Corpus Surfaces",
        "----------------------------------------",
        f"Workspace: {report['workspace']}",
        f"Discovered: {report['surface_count']}",
        f"Valid: {report['valid_count']}",
        f"Partial: {report['partial_count']}",
        f"Invalid: {report['invalid_count']}",
        f"Errors: {report['error_count']}",
    ]
    if not report["surfaces"]:
        lines.append("")
        lines.append("No conversation corpus surfaces found.")
        return "\n".join(lines)

    for surface in report["surfaces"]:
        summary = surface["summary"]
        lines.extend(
            [
                "",
                f"{surface['organization']}/{surface['repo']} [{surface['state']}]",
                f"  Repo root: {surface['repo_root']}",
                f"  Default corpus: {summary.get('default_corpus_id') or 'n/a'}",
                (
                    "  Providers: "
                    f"{summary.get('provider_count', 0)} total / "
                    f"{summary.get('healthy_provider_count', 0)} healthy"
                ),
                f"  Open review items: {summary.get('open_review_count', 0)}",
                (
                    "  Files: "
                    f"bundle={'yes' if surface['files']['bundle'] else 'no'}, "
                    f"manifest={'yes' if surface['files']['manifest'] else 'no'}, "
                    f"context={'yes' if surface['files']['context'] else 'no'}"
                ),
            ],
        )
    return "\n".join(lines)


def _candidate_repositories(workspace_root: Path, repo: str | None = None) -> list[Path]:
    from organvm_engine.git.superproject import ORGAN_DIR_MAP

    repo_filter = _normalize_repo_filter(repo)
    candidates: list[Path] = []
    seen: set[Path] = set()
    for organ_dir in sorted(set(ORGAN_DIR_MAP.values())):
        organ_path = workspace_root / organ_dir
        if not organ_path.is_dir():
            continue
        for child in sorted(organ_path.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if repo_filter and child.name != repo_filter:
                continue
            if child in seen:
                continue
            seen.add(child)
            candidates.append(child)
    return candidates


def _inspect_repo(repo_root: Path, workspace_root: Path) -> dict[str, Any] | None:
    surface_dir = repo_root / "reports" / "surfaces"
    if not surface_dir.is_dir():
        return None

    files = {
        key: str(path.resolve()) if path.is_file() else None
        for key, path in {
            name: surface_dir / filename for name, filename in SURFACE_FILENAMES.items()
        }.items()
    }
    if not any(files.values()):
        return None

    payloads: dict[str, dict[str, Any] | None] = {}
    validation: dict[str, dict[str, Any] | None] = {}
    for key, file_path in files.items():
        if file_path is None:
            payloads[key] = None
            validation[key] = None
            continue
        payload, result = _load_and_validate(Path(file_path), key, workspace_root)
        payloads[key] = payload
        validation[key] = result

    return {
        "repo": repo_root.name,
        "organization": repo_root.parent.name,
        "repo_root": str(repo_root.resolve()),
        "surface_dir": str(surface_dir.resolve()),
        "files": files,
        "state": _surface_state(files, validation),
        "summary": _surface_summary(payloads, validation),
        "manifest": payloads["manifest"],
        "context": payloads["context"],
        "bundle": payloads["bundle"],
        "validation": validation,
    }


def _load_and_validate(
    file_path: Path,
    schema_key: str,
    workspace_root: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        payload = json.loads(file_path.read_text())
    except json.JSONDecodeError as exc:
        return None, {
            "schema_name": schema_key,
            "schema_path": "",
            "valid": False,
            "error_count": 1,
            "errors": [f"(root): invalid JSON - {exc}"],
        }

    resolved_schema_path = schema_path(schema_key, workspace_root)
    if resolved_schema_path is None:
        return payload, {
            "schema_name": schema_key,
            "schema_path": "",
            "valid": False,
            "error_count": 1,
            "errors": [f"(root): schema file not found for {schema_key}"],
        }

    try:
        import jsonschema
    except ImportError:
        return payload, {
            "schema_name": schema_key,
            "schema_path": str(resolved_schema_path),
            "valid": False,
            "error_count": 1,
            "errors": ["(root): jsonschema is not installed"],
        }

    schema_payload = json.loads(resolved_schema_path.read_text())
    validator = jsonschema.Draft202012Validator(schema_payload)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "(root)"
        messages.append(f"{location}: {error.message}")

    return payload, {
        "schema_name": schema_key,
        "schema_path": str(resolved_schema_path),
        "valid": not errors,
        "error_count": len(errors),
        "errors": messages,
    }


def _surface_state(
    files: dict[str, str | None],
    validation: dict[str, dict[str, Any] | None],
) -> str:
    present = [key for key, path in files.items() if path is not None]
    if any((validation[key] or {}).get("valid") is False for key in present):
        return "invalid"
    if len(present) < len(SURFACE_FILENAMES):
        return "partial"
    return "valid"


def _surface_summary(
    payloads: dict[str, dict[str, Any] | None],
    validation: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    manifest = payloads["manifest"] or {}
    context = payloads["context"] or {}
    bundle = payloads["bundle"] or {}
    context_summary = context.get("summary") or {}
    manifest_registry = manifest.get("registry") or {}
    context_registry = context.get("registry") or {}

    bundle_valid = (bundle.get("summary") or {}).get("valid")
    if bundle_valid is None:
        bundle_valid = all(
            result["valid"] for result in validation.values() if result is not None
        )

    return {
        "valid": bundle_valid,
        "default_corpus_id": manifest_registry.get("default_corpus_id")
        or context_registry.get("default_corpus_id"),
        "registered_corpus_count": context_summary.get("registered_corpus_count")
        or manifest_registry.get("corpus_count", 0),
        "active_corpus_count": context_summary.get("active_corpus_count")
        or manifest_registry.get("active_corpus_count", 0),
        "provider_count": context_summary.get("provider_count", 0),
        "healthy_provider_count": context_summary.get("healthy_provider_count", 0),
        "open_review_count": context_summary.get("open_review_count", 0),
        "provider_names": [
            provider.get("provider")
            for provider in (context.get("providers") or [])
            if provider.get("provider")
        ],
    }


def _normalize_repo_filter(repo: str | None) -> str | None:
    if not repo:
        return None
    return repo.split("/")[-1]
