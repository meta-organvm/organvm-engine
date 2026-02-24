"""Tests for the metrics module."""

import json
from pathlib import Path

import pytest

from organvm_engine.metrics.calculator import compute_metrics
from organvm_engine.registry.loader import load_registry

FIXTURES = Path(__file__).parent / "fixtures"


class TestCalculator:
    def test_compute_totals(self, registry):
        m = compute_metrics(registry)
        assert m["total_repos"] == 6
        assert m["active_repos"] == 6
        assert m["total_organs"] == 4

    def test_per_organ_counts(self, registry):
        m = compute_metrics(registry)
        assert m["per_organ"]["ORGAN-I"]["repos"] == 2
        assert m["per_organ"]["ORGAN-II"]["repos"] == 1

    def test_ci_count(self, registry):
        m = compute_metrics(registry)
        # Only recursive-engine has ci_workflow in fixture
        assert m["ci_workflows"] == 1

    def test_dependency_count(self, registry):
        m = compute_metrics(registry)
        # recursive-engine has 0 deps, ontological has 1, metasystem has 1, product has 0
        assert m["dependency_edges"] == 2
