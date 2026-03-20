"""Tests for per-organ registry split and merge."""

import json
from pathlib import Path

import pytest

from organvm_engine.registry.loader import load_registry
from organvm_engine.registry.split import merge_registry, split_registry

FIXTURES = Path(__file__).parent / "fixtures"


class TestSplitRegistry:
    def test_split_creates_per_organ_files(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(reg, tmp_path)
        files = sorted(tmp_path.glob("*.json"))
        names = [f.stem for f in files]
        assert "ORGAN-I" in names
        assert "ORGAN-II" in names
        assert "META-ORGANVM" in names
        assert "_meta" in names

    def test_split_meta_file_has_version(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(reg, tmp_path)
        meta = json.loads((tmp_path / "_meta.json").read_text())
        assert meta["version"] == "2.0"
        assert "organs" not in meta

    def test_split_organ_file_has_repos(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(reg, tmp_path)
        organ_i = json.loads((tmp_path / "ORGAN-I.json").read_text())
        assert "repositories" in organ_i
        assert len(organ_i["repositories"]) == 2

    def test_split_preserves_organ_metadata(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(reg, tmp_path)
        organ_i = json.loads((tmp_path / "ORGAN-I.json").read_text())
        assert organ_i["name"] == "Theory"

    def test_split_creates_output_dir(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        out = tmp_path / "nested" / "dir"
        split_registry(reg, out)
        assert out.is_dir()
        assert (out / "_meta.json").is_file()

    def test_split_guard_rejects_small_registry(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        with pytest.raises(ValueError, match="Refusing to split"):
            split_registry(reg, tmp_path, min_repo_count=100)

    def test_split_guard_allows_when_sufficient(self, tmp_path):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(reg, tmp_path, min_repo_count=3)
        assert (tmp_path / "_meta.json").is_file()

    def test_split_empty_organs(self, tmp_path):
        reg = {"version": "2.0", "organs": {"ORGAN-X": {"name": "Empty", "repositories": []}}}
        split_registry(reg, tmp_path)
        organ_x = json.loads((tmp_path / "ORGAN-X.json").read_text())
        assert organ_x["repositories"] == []


class TestMergeRegistry:
    def test_roundtrip_split_merge(self, tmp_path):
        original = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(original, tmp_path)
        merged = merge_registry(tmp_path)
        assert set(merged["organs"].keys()) == set(original["organs"].keys())
        assert merged["version"] == original["version"]

    def test_roundtrip_repo_count(self, tmp_path):
        original = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(original, tmp_path)
        merged = merge_registry(tmp_path)
        orig_count = sum(
            len(o.get("repositories", []))
            for o in original["organs"].values()
        )
        merged_count = sum(
            len(o.get("repositories", []))
            for o in merged["organs"].values()
        )
        assert merged_count == orig_count

    def test_merge_empty_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            merge_registry(tmp_path)

    def test_merge_preserves_repo_fields(self, tmp_path):
        original = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(original, tmp_path)
        merged = merge_registry(tmp_path)
        orig_repo = original["organs"]["ORGAN-I"]["repositories"][0]
        merged_repo = merged["organs"]["ORGAN-I"]["repositories"][0]
        assert orig_repo["name"] == merged_repo["name"]
        assert orig_repo.get("promotion_status") == merged_repo.get("promotion_status")

    def test_merge_sorted_organ_order(self, tmp_path):
        original = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(original, tmp_path)
        merged = merge_registry(tmp_path)
        keys = list(merged["organs"].keys())
        assert keys == sorted(keys)

    def test_merge_corrupted_organ_file_raises(self, tmp_path):
        """Corrupted per-organ file should fail fast, not silently drop data."""
        original = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(original, tmp_path)
        (tmp_path / "ORGAN-I.json").write_text("{corrupted json")
        with pytest.raises(json.JSONDecodeError):
            merge_registry(tmp_path)


class TestLoaderDetection:
    def test_load_from_directory(self, tmp_path):
        original = load_registry(FIXTURES / "registry-minimal.json")
        split_registry(original, tmp_path)
        loaded = load_registry(tmp_path)
        assert set(loaded["organs"].keys()) == set(original["organs"].keys())

    def test_load_from_file_still_works(self):
        reg = load_registry(FIXTURES / "registry-minimal.json")
        assert "organs" in reg
