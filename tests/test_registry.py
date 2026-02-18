"""Tests for the registry module."""

import json
from pathlib import Path

import pytest

from organvm_engine.registry.loader import load_registry
from organvm_engine.registry.query import find_repo, all_repos, list_repos
from organvm_engine.registry.validator import validate_registry
from organvm_engine.registry.updater import update_repo


class TestLoader:
    def test_load_returns_dict(self, registry):
        assert isinstance(registry, dict)
        assert registry["version"] == "2.0"

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_registry("/nonexistent/path.json")


class TestQuery:
    def test_find_repo_exists(self, registry):
        result = find_repo(registry, "recursive-engine")
        assert result is not None
        organ_key, repo = result
        assert organ_key == "ORGAN-I"
        assert repo["name"] == "recursive-engine"

    def test_find_repo_missing(self, registry):
        assert find_repo(registry, "nonexistent") is None

    def test_all_repos_yields_all(self, registry):
        repos = list(all_repos(registry))
        assert len(repos) == 4

    def test_list_repos_by_organ(self, registry):
        results = list_repos(registry, organ="ORGAN-I")
        assert len(results) == 2
        assert all(ok == "ORGAN-I" for ok, _ in results)

    def test_list_repos_by_tier(self, registry):
        flagships = list_repos(registry, tier="flagship")
        assert len(flagships) == 2

    def test_list_repos_public_only(self, registry):
        public = list_repos(registry, public_only=True)
        assert len(public) == 4  # all are public in fixture


class TestValidator:
    def test_valid_registry_passes(self, registry):
        result = validate_registry(registry)
        assert result.passed
        assert result.total_repos == 4

    def test_missing_field_is_error(self):
        bad = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{"name": "test"}]
                }
            }
        }
        result = validate_registry(bad)
        assert not result.passed
        assert any("missing required" in e for e in result.errors)

    def test_invalid_status_is_error(self):
        bad = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{
                        "name": "test",
                        "org": "organvm-i-theoria",
                        "implementation_status": "BOGUS",
                        "public": True,
                        "description": "Test repo",
                    }]
                }
            }
        }
        result = validate_registry(bad)
        assert not result.passed
        assert any("BOGUS" in e for e in result.errors)

    def test_back_edge_detected(self):
        bad = {
            "organs": {
                "ORGAN-I": {
                    "repositories": [{
                        "name": "theory-repo",
                        "org": "organvm-i-theoria",
                        "implementation_status": "ACTIVE",
                        "public": True,
                        "description": "Theory",
                        "dependencies": ["organvm-ii-poiesis/art-repo"],
                    }]
                },
                "ORGAN-II": {
                    "repositories": [{
                        "name": "art-repo",
                        "org": "organvm-ii-poiesis",
                        "implementation_status": "ACTIVE",
                        "public": True,
                        "description": "Art",
                        "dependencies": [],
                    }]
                },
            }
        }
        result = validate_registry(bad)
        assert any("back-edge" in e for e in result.errors)


class TestUpdater:
    def test_update_valid_field(self, registry):
        ok, msg = update_repo(registry, "recursive-engine", "tier", "standard")
        assert ok
        _, repo = find_repo(registry, "recursive-engine")
        assert repo["tier"] == "standard"

    def test_update_invalid_status(self, registry):
        ok, msg = update_repo(registry, "recursive-engine", "implementation_status", "BOGUS")
        assert not ok

    def test_update_missing_repo(self, registry):
        ok, msg = update_repo(registry, "nonexistent", "tier", "standard")
        assert not ok
