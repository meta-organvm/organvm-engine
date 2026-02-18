"""Shared test fixtures for organvm-engine."""

from pathlib import Path

import pytest

from organvm_engine.registry.loader import load_registry

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def registry():
    return load_registry(FIXTURES / "registry-minimal.json")
