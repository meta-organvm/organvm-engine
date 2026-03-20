"""Testament — the system's generative self-portrait.

Every computational function in ORGANVM that transforms data is also a generative
function capable of producing a publishable artifact in its natural medium.
"""

from organvm_engine.testament.catalog import TestamentArtifact
from organvm_engine.testament.manifest import ArtifactModality, ArtifactType, OrganOutputProfile

__all__ = ["ArtifactModality", "ArtifactType", "OrganOutputProfile", "TestamentArtifact"]
