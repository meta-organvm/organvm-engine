"""Render pipeline — orchestrates artifact generation from system data.

Loads aesthetic profiles, iterates declared module sources, dispatches
to per-module renderers, writes output files, and catalogs results.
Renderers are imported lazily to avoid circular dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from organvm_engine.testament.aesthetic import (
    AestheticProfile,
    load_organ_aesthetic,
    load_taste,
)
from organvm_engine.testament.catalog import (
    TestamentArtifact,
    append_artifact,
)
from organvm_engine.testament.manifest import (
    MODULE_SOURCES,
    ORGAN_OUTPUT_MATRIX,
    ArtifactFormat,
    ArtifactType,
)

logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    """Outcome of rendering a single artifact."""

    artifact: TestamentArtifact
    content: str | bytes
    success: bool
    error: str | None = None


def _format_extension(fmt: ArtifactFormat) -> str:
    """Map an ArtifactFormat to a file extension."""
    extensions: dict[ArtifactFormat, str] = {
        ArtifactFormat.SVG: ".svg",
        ArtifactFormat.HTML: ".html",
        ArtifactFormat.MARKDOWN: ".md",
        ArtifactFormat.JSON: ".json",
        ArtifactFormat.LATEX: ".tex",
        ArtifactFormat.TXT: ".txt",
        ArtifactFormat.PNG: ".png",
    }
    return extensions.get(fmt, ".bin")


def _build_filename(artifact_type: ArtifactType, organ_key: str | None) -> str:
    """Build a descriptive filename for a rendered artifact."""
    parts = [artifact_type.source_module]
    if organ_key:
        parts.append(organ_key.lower())
    parts.append(artifact_type.modality.value)
    base = "-".join(parts)
    return base + _format_extension(artifact_type.format)


def _dispatch_renderer(
    artifact_type: ArtifactType,
    organ_key: str | None,
    output_dir: Path,
    aesthetic: AestheticProfile,
    registry_path: Path | None = None,
) -> RenderResult:
    """Dispatch to the appropriate renderer for an artifact type.

    Renderers are imported lazily inside this function to avoid circular
    dependencies and to allow the testament module to load without all
    renderer dependencies present.
    """
    filename = _build_filename(artifact_type, organ_key)
    output_path = output_dir / filename

    artifact = TestamentArtifact(
        modality=artifact_type.modality,
        format=artifact_type.format,
        source_module=artifact_type.source_module,
        organ=organ_key,
        title=artifact_type.description,
        description=f"{artifact_type.description} from {artifact_type.source_module}",
        path=str(output_path),
        metadata={
            "palette_primary": aesthetic.palette.primary,
            "palette_accent": aesthetic.palette.accent,
        },
    )

    # Attempt to import and invoke the module-specific renderer.
    # Each renderer module is expected at:
    #   organvm_engine.testament.renderers.<source_module>
    # with a render() function matching:
    #   render(artifact_type, organ_key, output_path, aesthetic, registry_path) -> str|bytes
    try:
        from importlib import import_module

        renderer_module_name = (
            f"organvm_engine.testament.renderers.{artifact_type.source_module}"
        )
        renderer = import_module(renderer_module_name)
        render_fn = getattr(renderer, "render", None)
        if render_fn is None:
            return RenderResult(
                artifact=artifact,
                content="",
                success=False,
                error=(
                    f"Renderer module {renderer_module_name} "
                    f"has no render() function"
                ),
            )
        content = render_fn(
            artifact_type, organ_key, output_path, aesthetic, registry_path,
        )
        return RenderResult(artifact=artifact, content=content, success=True)
    except ImportError:
        # No renderer implemented yet — this is expected for initial setup
        return RenderResult(
            artifact=artifact,
            content="",
            success=False,
            error=(
                f"No renderer found for module '{artifact_type.source_module}'"
            ),
        )
    except Exception as exc:
        return RenderResult(
            artifact=artifact,
            content="",
            success=False,
            error=f"Renderer error: {exc}",
        )


def render_artifact(
    artifact_type: ArtifactType,
    organ_key: str | None,
    output_dir: Path,
    aesthetic: AestheticProfile,
    registry_path: Path | None = None,
) -> RenderResult:
    """Render a single artifact type and catalog it on success."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result = _dispatch_renderer(
        artifact_type, organ_key, output_dir, aesthetic, registry_path,
    )
    if result.success:
        # Write the rendered content to disk
        output_path = Path(result.artifact.path)
        if isinstance(result.content, bytes):
            output_path.write_bytes(result.content)
        else:
            output_path.write_text(result.content)
        # Catalog the artifact
        append_artifact(result.artifact)
        logger.info(
            "Rendered %s -> %s",
            result.artifact.title,
            result.artifact.path,
        )
    else:
        logger.debug(
            "Skipped %s: %s",
            artifact_type.description,
            result.error,
        )
    return result


def render_all(
    output_dir: Path,
    dry_run: bool = True,
    registry_path: Path | None = None,
) -> list[RenderResult]:
    """Render all declared artifact types across all modules.

    When dry_run=True (default), builds the artifact list and dispatches
    renderers but does not write files or catalog results.
    """
    aesthetic = load_taste()
    results: list[RenderResult] = []

    for _module_name, artifact_types in MODULE_SOURCES.items():
        for artifact_type in artifact_types:
            if dry_run:
                artifact = TestamentArtifact(
                    modality=artifact_type.modality,
                    format=artifact_type.format,
                    source_module=artifact_type.source_module,
                    organ=None,
                    title=artifact_type.description,
                    description=(
                        f"[dry-run] {artifact_type.description} "
                        f"from {artifact_type.source_module}"
                    ),
                    path=str(
                        output_dir
                        / _build_filename(artifact_type, None),
                    ),
                )
                results.append(
                    RenderResult(
                        artifact=artifact,
                        content="",
                        success=True,
                        error=None,
                    ),
                )
            else:
                result = render_artifact(
                    artifact_type,
                    None,
                    output_dir,
                    aesthetic,
                    registry_path,
                )
                results.append(result)

    return results


def render_organ(
    organ_key: str,
    output_dir: Path,
    dry_run: bool = True,
    registry_path: Path | None = None,
) -> list[RenderResult]:
    """Render only artifacts whose modalities match a specific organ's profile.

    Filters MODULE_SOURCES to artifact types whose modality appears in the
    organ's primary or secondary modalities, then renders each one.
    """
    profile = ORGAN_OUTPUT_MATRIX.get(organ_key)
    if profile is None:
        logger.warning("Unknown organ key: %s", organ_key)
        return []

    all_modalities = set(profile.primary_modalities + profile.secondary_modalities)
    aesthetic = load_organ_aesthetic(organ_key)
    results: list[RenderResult] = []

    for _module_name, artifact_types in MODULE_SOURCES.items():
        for artifact_type in artifact_types:
            if artifact_type.modality not in all_modalities:
                continue

            if dry_run:
                artifact = TestamentArtifact(
                    modality=artifact_type.modality,
                    format=artifact_type.format,
                    source_module=artifact_type.source_module,
                    organ=organ_key,
                    title=artifact_type.description,
                    description=(
                        f"[dry-run] {artifact_type.description} "
                        f"from {artifact_type.source_module} "
                        f"for organ {organ_key}"
                    ),
                    path=str(
                        output_dir
                        / _build_filename(artifact_type, organ_key),
                    ),
                )
                results.append(
                    RenderResult(
                        artifact=artifact,
                        content="",
                        success=True,
                        error=None,
                    ),
                )
            else:
                result = render_artifact(
                    artifact_type,
                    organ_key,
                    output_dir,
                    aesthetic,
                    registry_path,
                )
                results.append(result)

    return results
