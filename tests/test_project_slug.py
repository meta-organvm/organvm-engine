"""Tests for project_slug.py — canonical project slug derivation."""

from pathlib import Path

from organvm_engine.project_slug import (
    normalize_slug,
    slug_from_path,
    slug_from_plan_dir,
)


class TestSlugFromPath:
    def test_workspace_relative(self):
        result = slug_from_path("/Users/4jp/Workspace/meta-organvm/organvm-engine")
        assert result == "meta-organvm/organvm-engine"

    def test_workspace_deep_path(self):
        result = slug_from_path("/Users/4jp/Workspace/organvm-iii-ergon/my-product")
        assert result == "organvm-iii-ergon/my-product"

    def test_home_relative_fallback(self):
        result = slug_from_path(str(Path.home() / "Documents" / "my-project"))
        username = Path.home().name
        assert result == f"{username}/Documents/my-project"

    def test_absolute_fallback(self):
        result = slug_from_path("/Volumes/External/projects/my-thing")
        assert result == "projects/my-thing"

    def test_single_component(self):
        result = slug_from_path("just-a-name")
        assert result == "just-a-name"

    def test_trailing_slash(self):
        result = slug_from_path("/Users/4jp/Workspace/meta-organvm/engine/")
        assert result == "meta-organvm/engine"

    def test_empty_string(self):
        result = slug_from_path("")
        assert isinstance(result, str)


class TestSlugFromPlanDir:
    def test_organ_prefix_match(self):
        result = slug_from_plan_dir("meta-organvm-stakeholder-portal")
        assert result == "meta-organvm/stakeholder-portal"

    def test_known_alias(self):
        result = slug_from_plan_dir("ivviiviivvi-github")
        assert result == "ivviiviivvi/.github"

    def test_root_alias(self):
        result = slug_from_plan_dir("_root")
        assert result == "_root"

    def test_no_match_returns_input(self):
        result = slug_from_plan_dir("something-unknown")
        assert result == "something-unknown"

    def test_organ_dir_prefix_longest_match(self):
        # Should match the longest organ dir prefix
        result = slug_from_plan_dir("organvm-iii-ergon-my-product")
        assert result == "organvm-iii-ergon/my-product"

    def test_organ_dir_exact_no_rest(self):
        # If the plan dir IS the organ dir, no split
        result = slug_from_plan_dir("meta-organvm")
        # No trailing hyphen, so no split — falls through
        assert isinstance(result, str)


class TestNormalizeSlug:
    def test_absolute_path(self):
        result = normalize_slug("/Users/4jp/Workspace/meta-organvm/engine")
        assert result == "meta-organvm/engine"

    def test_slash_separated(self):
        result = normalize_slug("meta-organvm/engine")
        assert result == "meta-organvm/engine"

    def test_slash_separated_trailing(self):
        result = normalize_slug("meta-organvm/engine/")
        assert result == "meta-organvm/engine"

    def test_flat_name(self):
        result = normalize_slug("meta-organvm-stakeholder-portal")
        assert result == "meta-organvm/stakeholder-portal"

    def test_unknown_flat_name(self):
        result = normalize_slug("random-thing")
        assert result == "random-thing"
