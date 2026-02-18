"""Tests for the seed module."""

from pathlib import Path

import pytest

from organvm_engine.seed.reader import read_seed, get_produces, get_consumes, seed_identity

FIXTURES = Path(__file__).parent / "fixtures"


class TestReader:
    def test_read_valid_seed(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        assert seed["schema_version"] == "1.0"
        assert seed["organ"] == "I"
        assert seed["repo"] == "recursive-engine"

    def test_get_produces(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        produces = get_produces(seed)
        assert len(produces) == 1
        assert produces[0]["type"] == "theory"

    def test_get_consumes_empty(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        consumes = get_consumes(seed)
        assert consumes == []

    def test_seed_identity(self):
        seed = read_seed(FIXTURES / "seed-example.yaml")
        assert seed_identity(seed) == "organvm-i-theoria/recursive-engine"

    def test_read_missing_file(self):
        with pytest.raises(FileNotFoundError):
            read_seed("/nonexistent/seed.yaml")
