"""Tests for the ecosystem discovery system."""

from pathlib import Path

import pytest
import yaml

from organvm_engine.ecosystem import ECOSYSTEM_FILENAME, HEADER_FIELDS
from organvm_engine.ecosystem.query import (
    coverage_matrix,
    gaps,
    next_actions,
    pillar_view,
    status_summary,
)
from organvm_engine.ecosystem.reader import get_pillars, read_ecosystem, validate_ecosystem
from organvm_engine.ecosystem.taxonomy import (
    ARM_PRIORITY,
    ARM_STATUS,
    DEFAULT_PILLARS,
    suggest_pillars,
)
from organvm_engine.ecosystem.templates import scaffold_ecosystem

FIXTURES = Path(__file__).parent / "fixtures"


# ── Constants ──────────────────────────────────────────────────────


class TestConstants:
    def test_ecosystem_filename(self):
        assert ECOSYSTEM_FILENAME == "ecosystem.yaml"

    def test_header_fields(self):
        assert "schema_version" in HEADER_FIELDS
        assert "repo" in HEADER_FIELDS
        assert "organ" in HEADER_FIELDS
        assert "display_name" in HEADER_FIELDS


# ── Taxonomy ───────────────────────────────────────────────────────


class TestTaxonomy:
    def test_default_pillars_has_core(self):
        assert "delivery" in DEFAULT_PILLARS
        assert "revenue" in DEFAULT_PILLARS
        assert "marketing" in DEFAULT_PILLARS
        assert "community" in DEFAULT_PILLARS
        assert "content" in DEFAULT_PILLARS
        assert "listings" in DEFAULT_PILLARS

    def test_each_pillar_has_description_and_platforms(self):
        for name, info in DEFAULT_PILLARS.items():
            assert "description" in info, f"{name} missing description"
            assert "suggested_platforms" in info, f"{name} missing suggested_platforms"
            assert len(info["suggested_platforms"]) > 0, f"{name} has no platforms"

    def test_arm_status_values(self):
        assert "not_started" in ARM_STATUS
        assert "live" in ARM_STATUS
        assert "deprecated" in ARM_STATUS

    def test_arm_priority_values(self):
        assert "critical" in ARM_PRIORITY
        assert "deferred" in ARM_PRIORITY

    def test_suggest_pillars_always_includes_delivery_revenue(self):
        result = suggest_pillars()
        assert "delivery" in result
        assert "revenue" in result

    def test_suggest_pillars_with_saas_seed(self):
        seed = {"metadata": {"tags": ["saas", "nextjs"]}}
        result = suggest_pillars(seed_data=seed)
        assert "marketing" in result
        assert "content" in result

    def test_suggest_pillars_with_browser_extension(self):
        seed = {"metadata": {"tags": ["chrome", "extension"]}}
        result = suggest_pillars(seed_data=seed)
        assert "listings" in result

    def test_suggest_pillars_with_revenue_model(self):
        result = suggest_pillars(registry_data={"revenue_model": "subscription"})
        assert "marketing" in result


# ── Reader ─────────────────────────────────────────────────────────


class TestReader:
    def test_read_ecosystem_fixture(self):
        data = read_ecosystem(FIXTURES / "ecosystem-sample.yaml")
        assert data["repo"] == "test-product"
        assert data["organ"] == "III"
        assert data["schema_version"] == "1.0"

    def test_read_ecosystem_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            read_ecosystem("/nonexistent/ecosystem.yaml")

    def test_read_ecosystem_bad_yaml(self, tmp_path):
        bad = tmp_path / "ecosystem.yaml"
        bad.write_text("not a mapping\n")
        with pytest.raises(ValueError, match="not a YAML mapping"):
            read_ecosystem(bad)

    def test_validate_valid(self):
        data = read_ecosystem(FIXTURES / "ecosystem-sample.yaml")
        errors = validate_ecosystem(data)
        assert errors == []

    def test_validate_missing_version(self):
        data = {"repo": "x", "organ": "III"}
        errors = validate_ecosystem(data)
        assert any("schema_version" in e for e in errors)

    def test_validate_wrong_version(self):
        data = {"schema_version": "2.0", "repo": "x", "organ": "III"}
        errors = validate_ecosystem(data)
        assert any("Unsupported" in e for e in errors)

    def test_validate_missing_repo(self):
        data = {"schema_version": "1.0", "organ": "III"}
        errors = validate_ecosystem(data)
        assert any("repo" in e for e in errors)

    def test_validate_missing_organ(self):
        data = {"schema_version": "1.0", "repo": "x"}
        errors = validate_ecosystem(data)
        assert any("organ" in e for e in errors)

    def test_validate_pillar_not_list(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": "not a list",
        }
        errors = validate_ecosystem(data)
        assert any("must be a list" in e for e in errors)

    def test_validate_arm_missing_platform(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"status": "live"}],
        }
        errors = validate_ecosystem(data)
        assert any("platform" in e for e in errors)

    def test_validate_arm_missing_status(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"platform": "web_app"}],
        }
        errors = validate_ecosystem(data)
        assert any("status" in e for e in errors)

    def test_validate_arm_invalid_status(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"platform": "web_app", "status": "INVALID"}],
        }
        errors = validate_ecosystem(data)
        assert any("invalid status" in e for e in errors)

    def test_validate_arm_invalid_priority(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"platform": "web_app", "status": "live", "priority": "WRONG"}],
        }
        errors = validate_ecosystem(data)
        assert any("invalid priority" in e for e in errors)

    def test_validate_custom_pillar_accepted(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "partnerships": [{"platform": "aws_marketplace", "status": "planned"}],
        }
        errors = validate_ecosystem(data)
        assert errors == []

    def test_validate_custom_metadata_accepted(self):
        data = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "revenue": [{"platform": "subscription", "status": "live", "stripe_id": "prod_123"}],
        }
        errors = validate_ecosystem(data)
        assert errors == []

    def test_get_pillars(self):
        data = read_ecosystem(FIXTURES / "ecosystem-sample.yaml")
        pillars = get_pillars(data)
        assert "delivery" in pillars
        assert "revenue" in pillars
        assert "repo" not in pillars
        assert "schema_version" not in pillars


# ── Discover ───────────────────────────────────────────────────────


class TestDiscover:
    def test_discover_in_empty_workspace(self, tmp_path):
        from organvm_engine.ecosystem.discover import discover_ecosystems
        result = discover_ecosystems(tmp_path)
        assert result == []

    def test_discover_finds_files(self, tmp_path):
        from organvm_engine.ecosystem.discover import discover_ecosystems

        # Create a fake organ/repo structure
        organ_dir = tmp_path / "organvm-iii-ergon"
        repo_dir = organ_dir / "my-product"
        repo_dir.mkdir(parents=True)
        eco_file = repo_dir / "ecosystem.yaml"
        eco_file.write_text("schema_version: '1.0'\nrepo: my-product\norgan: III\n")

        result = discover_ecosystems(tmp_path)
        assert len(result) == 1
        assert result[0] == eco_file


# ── Query ──────────────────────────────────────────────────────────


class TestQuery:
    @pytest.fixture
    def sample_ecosystems(self):
        return [
            {
                "schema_version": "1.0", "repo": "product-a", "organ": "III",
                "delivery": [
                    {"platform": "web_app", "status": "live"},
                    {"platform": "mobile_app_ios", "status": "planned"},
                ],
                "revenue": [
                    {"platform": "subscription", "status": "live"},
                ],
            },
            {
                "schema_version": "1.0", "repo": "product-b", "organ": "III",
                "delivery": [
                    {"platform": "cli", "status": "in_progress"},
                ],
                "marketing": [
                    {"platform": "producthunt", "status": "not_started",
                     "next_action": "Prepare launch", "priority": "high"},
                ],
            },
        ]

    def test_coverage_matrix(self, sample_ecosystems):
        matrix = coverage_matrix(sample_ecosystems)
        assert "product-a" in matrix
        assert "product-b" in matrix
        assert matrix["product-a"]["delivery"]["total"] == 2
        assert matrix["product-a"]["delivery"]["live"] == 1
        assert matrix["product-a"]["revenue"]["total"] == 1

    def test_pillar_view(self, sample_ecosystems):
        view = pillar_view(sample_ecosystems, "delivery")
        assert "product-a" in view
        assert "product-b" in view
        assert len(view["product-a"]) == 2
        assert len(view["product-b"]) == 1

    def test_pillar_view_missing(self, sample_ecosystems):
        view = pillar_view(sample_ecosystems, "listings")
        assert view == {}

    def test_gaps_all_pillars_present(self):
        eco = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"platform": "web_app", "status": "live"}],
            "revenue": [{"platform": "sub", "status": "planned"}],
            "marketing": [{"platform": "seo", "status": "in_progress"}],
            "community": [{"platform": "discord", "status": "live"}],
            "content": [{"platform": "blog", "status": "live"}],
            "listings": [{"platform": "gumroad", "status": "live"}],
        }
        gap_list = gaps(eco)
        assert gap_list == []

    def test_gaps_missing_pillar(self):
        eco = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"platform": "web_app", "status": "live"}],
        }
        gap_list = gaps(eco)
        assert any("revenue" in g for g in gap_list)
        assert any("marketing" in g for g in gap_list)

    def test_gaps_all_not_started(self):
        eco = {
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [{"platform": "web_app", "status": "not_started"}],
            "revenue": [{"platform": "sub", "status": "live"}],
            "marketing": [{"platform": "seo", "status": "live"}],
            "community": [{"platform": "discord", "status": "live"}],
            "content": [{"platform": "blog", "status": "live"}],
            "listings": [{"platform": "gumroad", "status": "live"}],
        }
        gap_list = gaps(eco)
        assert any("all are not_started" in g for g in gap_list)

    def test_next_actions(self, sample_ecosystems):
        actions = next_actions(sample_ecosystems)
        assert len(actions) == 1
        assert actions[0]["repo"] == "product-b"
        assert actions[0]["next_action"] == "Prepare launch"

    def test_next_actions_sorted_by_priority(self):
        ecosystems = [{
            "schema_version": "1.0", "repo": "x", "organ": "III",
            "delivery": [
                {"platform": "a", "status": "planned", "next_action": "low task", "priority": "low"},
                {"platform": "b", "status": "planned", "next_action": "critical task", "priority": "critical"},
            ],
        }]
        actions = next_actions(ecosystems)
        assert actions[0]["priority"] == "critical"
        assert actions[1]["priority"] == "low"

    def test_status_summary(self, sample_ecosystems):
        summary = status_summary(sample_ecosystems)
        assert summary["total_products"] == 2
        assert summary["total_arms"] == 5
        assert summary["by_status"]["live"] == 2
        assert summary["by_status"]["planned"] == 1


# ── Templates ──────────────────────────────────────────────────────


class TestTemplates:
    def test_scaffold_minimal(self):
        eco = scaffold_ecosystem("my-repo", "III")
        assert eco["schema_version"] == "1.0"
        assert eco["repo"] == "my-repo"
        assert eco["organ"] == "III"

    def test_scaffold_with_registry(self):
        registry_data = {
            "revenue_model": "subscription",
            "revenue_status": "pre-launch",
        }
        eco = scaffold_ecosystem("my-repo", "III", registry_data=registry_data)
        assert "revenue" in eco
        assert eco["revenue"][0]["platform"] == "subscription"
        assert eco["revenue"][0]["status"] == "planned"

    def test_scaffold_with_live_revenue(self):
        registry_data = {
            "revenue_model": "freemium",
            "revenue_status": "live",
        }
        eco = scaffold_ecosystem("my-repo", "III", registry_data=registry_data)
        assert eco["revenue"][0]["status"] == "live"

    def test_scaffold_with_seed_tags(self):
        seed_data = {
            "metadata": {
                "tags": ["nextjs", "react"],
                "language": "typescript",
            },
        }
        eco = scaffold_ecosystem("my-repo", "III", seed_data=seed_data)
        assert "delivery" in eco
        platforms = [a["platform"] for a in eco["delivery"]]
        assert "web_app" in platforms

    def test_scaffold_with_browser_extension_tags(self):
        seed_data = {
            "metadata": {
                "tags": ["chrome", "extension"],
            },
        }
        eco = scaffold_ecosystem("my-repo", "III", seed_data=seed_data)
        platforms = [a["platform"] for a in eco.get("delivery", [])]
        assert "browser_extension_chrome" in platforms

    def test_scaffold_with_deployment_url(self):
        seed_data = {
            "metadata": {
                "tags": ["nextjs"],
                "deployment_url": "https://my-app.vercel.app",
            },
        }
        eco = scaffold_ecosystem("my-repo", "III", seed_data=seed_data)
        web_arm = eco["delivery"][0]
        assert web_arm["status"] == "live"
        assert web_arm["url"] == "https://my-app.vercel.app"

    def test_scaffold_with_display_name(self):
        eco = scaffold_ecosystem("my-repo", "III", display_name="My Product")
        assert eco["display_name"] == "My Product"

    def test_scaffold_with_kerygma_discord(self):
        kerygma = {
            "repo": "my-repo",
            "channels": {"discord": {"url": "https://discord.gg/123"}},
        }
        eco = scaffold_ecosystem("my-repo", "III", kerygma_profile=kerygma)
        assert "community" in eco
        platforms = [a["platform"] for a in eco["community"]]
        assert "discord" in platforms

    def test_scaffold_validates(self):
        eco = scaffold_ecosystem(
            "my-repo", "III",
            registry_data={"revenue_model": "subscription", "revenue_status": "pre-launch"},
            seed_data={"metadata": {"tags": ["nextjs"]}},
        )
        errors = validate_ecosystem(eco)
        assert errors == []


# ── Sync ───────────────────────────────────────────────────────────


class TestSync:
    def test_sync_dry_run(self, tmp_path, monkeypatch):
        """sync_ecosystems in dry_run mode should not write files."""
        from organvm_engine.ecosystem.sync import sync_ecosystems

        # Create minimal registry
        registry = {
            "version": "2.0",
            "schema_version": "0.5",
            "organs": {
                "ORGAN-III": {
                    "name": "Ergon",
                    "repositories": [
                        {"name": "test-repo", "org": "test", "tier": "standard",
                         "implementation_status": "ACTIVE"},
                    ],
                },
            },
        }
        import json
        reg_path = tmp_path / "registry.json"
        with reg_path.open("w") as f:
            json.dump(registry, f)

        # Create the repo directory
        repo_dir = tmp_path / "organvm-iii-ergon" / "test-repo"
        repo_dir.mkdir(parents=True)

        result = sync_ecosystems(
            registry_path=reg_path,
            workspace=tmp_path,
            organ="III",
            dry_run=True,
        )

        assert "test-repo" in result["created"]
        # File should NOT exist in dry_run
        assert not (repo_dir / "ecosystem.yaml").exists()

    def test_sync_skips_existing(self, tmp_path):
        """sync_ecosystems should skip repos that already have ecosystem.yaml."""
        import json

        from organvm_engine.ecosystem.sync import sync_ecosystems
        registry = {
            "version": "2.0",
            "schema_version": "0.5",
            "organs": {
                "ORGAN-III": {
                    "name": "Ergon",
                    "repositories": [
                        {"name": "has-eco", "org": "test", "tier": "standard"},
                    ],
                },
            },
        }
        reg_path = tmp_path / "registry.json"
        with reg_path.open("w") as f:
            json.dump(registry, f)

        # Create repo with existing ecosystem.yaml
        repo_dir = tmp_path / "organvm-iii-ergon" / "has-eco"
        repo_dir.mkdir(parents=True)
        eco = {"schema_version": "1.0", "repo": "has-eco", "organ": "III"}
        with (repo_dir / "ecosystem.yaml").open("w") as f:
            yaml.dump(eco, f)

        result = sync_ecosystems(
            registry_path=reg_path,
            workspace=tmp_path,
            organ="III",
            dry_run=True,
        )
        assert "has-eco" in result["skipped"]

    def test_sync_skips_infrastructure(self, tmp_path):
        """sync_ecosystems should skip infrastructure tier repos."""
        import json

        from organvm_engine.ecosystem.sync import sync_ecosystems
        registry = {
            "version": "2.0",
            "schema_version": "0.5",
            "organs": {
                "ORGAN-III": {
                    "name": "Ergon",
                    "repositories": [
                        {"name": "infra-repo", "org": "test", "tier": "infrastructure"},
                    ],
                },
            },
        }
        reg_path = tmp_path / "registry.json"
        with reg_path.open("w") as f:
            json.dump(registry, f)

        repo_dir = tmp_path / "organvm-iii-ergon" / "infra-repo"
        repo_dir.mkdir(parents=True)

        result = sync_ecosystems(
            registry_path=reg_path,
            workspace=tmp_path,
            organ="III",
            dry_run=True,
        )
        assert "infra-repo" in result["skipped"]


# ── Schema validation ──────────────────────────────────────────────


class TestSchemaIntegration:
    def test_fixture_validates_against_schema(self):
        """The sample fixture should validate against the JSON Schema."""
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        import json
        schema_path = (
            Path(__file__).resolve().parent.parent.parent
            / "schema-definitions" / "schemas" / "ecosystem-v1.schema.json"
        )
        if not schema_path.exists():
            pytest.skip("Schema file not at expected path")

        with schema_path.open() as f:
            schema = json.load(f)

        data = read_ecosystem(FIXTURES / "ecosystem-sample.yaml")
        validator = jsonschema.Draft202012Validator(schema)
        errors = [e.message for e in validator.iter_errors(data)]
        assert errors == [], f"Schema validation errors: {errors}"
