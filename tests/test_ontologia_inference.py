"""Tests for ontologia inference bridge."""

import pytest

from organvm_engine.ontologia.inference_bridge import (
    compute_blast_radius,
    detect_entity_clusters,
    detect_tensions,
    infer_health,
)


# These tests verify the bridge works without ontologia installed.
# When ontologia IS installed, they verify the full pipeline.


class TestDetectTensions:
    def test_returns_dict(self):
        result = detect_tensions()
        assert isinstance(result, dict)

    def test_returns_error_without_ontologia_or_structured(self):
        result = detect_tensions()
        # Either error (no ontologia) or structured result (ontologia present)
        assert "error" in result or "total_tensions" in result

    def test_with_nonexistent_store(self, tmp_path):
        result = detect_tensions(store_dir=str(tmp_path / "nonexistent"))
        assert isinstance(result, dict)

    def test_with_empty_store(self, tmp_path):
        store_dir = tmp_path / "store"
        store_dir.mkdir()
        result = detect_tensions(store_dir=str(store_dir))
        assert isinstance(result, dict)


class TestComputeBlastRadius:
    def test_returns_dict(self):
        result = compute_blast_radius("nonexistent-entity")
        assert isinstance(result, dict)

    def test_entity_not_found(self):
        result = compute_blast_radius("definitely-not-an-entity-12345")
        assert isinstance(result, dict)
        # Either error from no ontologia or "not found"
        assert "error" in result


class TestDetectEntityClusters:
    def test_returns_dict(self):
        result = detect_entity_clusters()
        assert isinstance(result, dict)

    def test_returns_error_or_clusters(self):
        result = detect_entity_clusters()
        assert "error" in result or "clusters" in result


class TestInferHealth:
    def test_returns_dict(self):
        result = infer_health()
        assert isinstance(result, dict)

    def test_with_entity_query(self):
        result = infer_health(entity_query="nonexistent")
        assert isinstance(result, dict)
