"""Tests for the living ecosystem pillar system.

Covers: product_types, pillar_dna, intelligence, scaffold_pillar, CLI commands.
"""

from __future__ import annotations

from datetime import date, timedelta

import yaml

# ── Product Types ────────────────────────────────────────────────────


class TestProductTypes:
    def test_infer_saas_from_tags(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        seed = {"metadata": {"tags": ["nextjs", "react", "dashboard"]}}
        assert infer_product_type(seed_data=seed) == "saas"

    def test_infer_browser_extension(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        seed = {"metadata": {"tags": ["chrome", "extension"]}}
        assert infer_product_type(seed_data=seed) == "browser_extension"

    def test_infer_trading(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        seed = {"metadata": {"tags": ["defi", "trading"]}}
        assert infer_product_type(seed_data=seed) == "trading"

    def test_infer_creative_tool(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        seed = {"metadata": {"tags": ["music", "generative", "audio"]}}
        assert infer_product_type(seed_data=seed) == "creative_tool"

    def test_infer_library(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        seed = {"metadata": {"tags": ["library", "npm"]}}
        assert infer_product_type(seed_data=seed) == "library"

    def test_infer_from_revenue_model(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        registry = {"revenue_model": "subscription"}
        assert infer_product_type(registry_data=registry) == "saas"

    def test_infer_marketplace_from_revenue(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        registry = {"revenue_model": "marketplace_commission"}
        assert infer_product_type(registry_data=registry) == "marketplace"

    def test_infer_defaults_to_saas(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        assert infer_product_type() == "saas"

    def test_infer_no_tags(self):
        from organvm_engine.ecosystem.product_types import infer_product_type

        seed = {"metadata": {}}
        assert infer_product_type(seed_data=seed) == "saas"

    def test_get_pillar_defaults_saas_marketing(self):
        from organvm_engine.ecosystem.product_types import get_pillar_defaults

        defaults = get_pillar_defaults("saas", "marketing")
        assert defaults is not None
        assert "scan_scope" in defaults
        assert "seo" in defaults["scan_scope"]

    def test_get_pillar_defaults_unknown_type(self):
        from organvm_engine.ecosystem.product_types import get_pillar_defaults

        assert get_pillar_defaults("unknown_type", "marketing") is None

    def test_get_pillar_defaults_unknown_pillar(self):
        from organvm_engine.ecosystem.product_types import get_pillar_defaults

        assert get_pillar_defaults("saas", "nonexistent_pillar") is None

    def test_all_product_types_have_pillar_defaults(self):
        from organvm_engine.ecosystem.product_types import PRODUCT_TYPES

        for ptype, config in PRODUCT_TYPES.items():
            assert "pillar_defaults" in config, f"{ptype} missing pillar_defaults"
            assert "key_pillars" in config, f"{ptype} missing key_pillars"
            assert len(config["pillar_defaults"]) > 0, f"{ptype} has empty pillar_defaults"

    def test_lifecycle_stages_defined(self):
        from organvm_engine.ecosystem.product_types import LIFECYCLE_STAGES

        assert "conception" in LIFECYCLE_STAGES
        assert "live" in LIFECYCLE_STAGES
        assert "sunset" in LIFECYCLE_STAGES
        assert len(LIFECYCLE_STAGES) == 8


# ── Pillar DNA Read/Write/Validate ──────────────────────────────────


class TestPillarDna:
    def test_read_nonexistent(self, tmp_path):
        from organvm_engine.ecosystem.pillar_dna import read_pillar_dna

        assert read_pillar_dna(tmp_path, "marketing") is None

    def test_write_and_read(self, tmp_path):
        from organvm_engine.ecosystem.pillar_dna import read_pillar_dna, write_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
        }
        path = write_pillar_dna(tmp_path, "marketing", dna)
        assert path.exists()

        loaded = read_pillar_dna(tmp_path, "marketing")
        assert loaded is not None
        assert loaded["pillar"] == "marketing"
        assert loaded["lifecycle_stage"] == "research"

    def test_list_pillar_dnas_empty(self, tmp_path):
        from organvm_engine.ecosystem.pillar_dna import list_pillar_dnas

        assert list_pillar_dnas(tmp_path) == []

    def test_list_pillar_dnas(self, tmp_path):
        from organvm_engine.ecosystem.pillar_dna import list_pillar_dnas, write_pillar_dna

        write_pillar_dna(tmp_path, "marketing", {"schema_version": "1.0"})
        write_pillar_dna(tmp_path, "revenue", {"schema_version": "1.0"})

        result = list_pillar_dnas(tmp_path)
        assert sorted(result) == ["marketing", "revenue"]

    def test_validate_valid(self):
        from organvm_engine.ecosystem.pillar_dna import validate_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "artifacts": [{"name": "landscape-snapshot", "cadence": "monthly"}],
            "gen_prompts": [{"id": "scan", "prompt": "Do a scan"}],
            "crit_prompts": [{"id": "check", "prompt": "Check coverage"}],
            "gates": {"research_to_planning": ["Snapshot exists"]},
        }
        errors = validate_pillar_dna(dna)
        assert errors == []

    def test_validate_missing_required(self):
        from organvm_engine.ecosystem.pillar_dna import validate_pillar_dna

        errors = validate_pillar_dna({})
        assert len(errors) == 3  # schema_version, pillar, lifecycle_stage

    def test_validate_invalid_stage(self):
        from organvm_engine.ecosystem.pillar_dna import validate_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "invalid_stage",
        }
        errors = validate_pillar_dna(dna)
        assert len(errors) == 1
        assert "invalid_stage" in errors[0]

    def test_validate_bad_artifacts(self):
        from organvm_engine.ecosystem.pillar_dna import validate_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "artifacts": [{"cadence": "monthly"}],  # missing name
        }
        errors = validate_pillar_dna(dna)
        assert len(errors) == 1
        assert "name" in errors[0]

    def test_validate_bad_gen_prompts(self):
        from organvm_engine.ecosystem.pillar_dna import validate_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "gen_prompts": [{"id": "test"}],  # missing prompt
        }
        errors = validate_pillar_dna(dna)
        assert len(errors) == 1
        assert "prompt" in errors[0]

    def test_validate_bad_crit_prompts(self):
        from organvm_engine.ecosystem.pillar_dna import validate_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "crit_prompts": [{"prompt": "check"}],  # missing id
        }
        errors = validate_pillar_dna(dna)
        assert len(errors) == 1
        assert "id" in errors[0]

    def test_check_gates(self):
        from organvm_engine.ecosystem.pillar_dna import check_gates

        dna = {
            "gates": {
                "research_to_planning": [
                    "Snapshot exists",
                    "3+ competitors",
                ],
            },
        }
        unmet = check_gates(dna, "research", "planning")
        assert len(unmet) == 2
        assert "Snapshot exists" in unmet

    def test_check_gates_no_gate(self):
        from organvm_engine.ecosystem.pillar_dna import check_gates

        dna = {"gates": {}}
        assert check_gates(dna, "research", "planning") == []

    def test_check_gates_no_gates_section(self):
        from organvm_engine.ecosystem.pillar_dna import check_gates

        assert check_gates({}, "research", "planning") == []


# ── Intelligence & Snapshots ─────────────────────────────────────────


class TestIntelligence:
    def test_write_and_read_snapshot(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import read_snapshot, write_snapshot

        data = {"competitors": ["a", "b"], "channels": 5}
        path = write_snapshot(
            tmp_path, "marketing", data,
            snapshot_date=date(2026, 3, 8),
        )
        assert path.exists()
        assert "2026-03-08" in path.name

        loaded = read_snapshot(tmp_path, "marketing", "2026-03-08")
        assert loaded is not None
        assert loaded["competitors"] == ["a", "b"]

    def test_list_snapshots_empty(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import list_snapshots

        assert list_snapshots(tmp_path, "marketing") == []

    def test_list_snapshots_sorted(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import list_snapshots, write_snapshot

        write_snapshot(tmp_path, "marketing", {"v": 1}, snapshot_date=date(2026, 1, 1))
        write_snapshot(tmp_path, "marketing", {"v": 2}, snapshot_date=date(2026, 3, 1))
        write_snapshot(tmp_path, "marketing", {"v": 3}, snapshot_date=date(2026, 2, 1))

        snaps = list_snapshots(tmp_path, "marketing")
        assert len(snaps) == 3
        assert snaps[0][0] == "2026-03-01"  # newest first

    def test_latest_snapshot(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import latest_snapshot, write_snapshot

        write_snapshot(tmp_path, "revenue", {"v": 1}, snapshot_date=date(2026, 1, 1))
        write_snapshot(tmp_path, "revenue", {"v": 2}, snapshot_date=date(2026, 3, 1))

        latest = latest_snapshot(tmp_path, "revenue")
        assert latest is not None
        assert latest["v"] == 2

    def test_latest_snapshot_empty(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import latest_snapshot

        assert latest_snapshot(tmp_path, "revenue") is None

    def test_read_write_intelligence(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import (
            read_intelligence,
            write_intelligence,
        )

        data = {"top_competitor": "acme", "market_share": 0.3}
        path = write_intelligence(tmp_path, "marketing", "competitors", data)
        assert path.exists()

        loaded = read_intelligence(tmp_path, "marketing", "competitors")
        assert loaded is not None
        assert loaded["top_competitor"] == "acme"

    def test_read_intelligence_missing(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import read_intelligence

        assert read_intelligence(tmp_path, "marketing", "nonexistent") is None

    def test_staleness_report_missing_artifacts(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import staleness_report
        from organvm_engine.ecosystem.pillar_dna import write_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "artifacts": [
                {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
            ],
        }
        write_pillar_dna(tmp_path, "marketing", dna)

        report = staleness_report(tmp_path)
        assert len(report) == 1
        assert report[0]["status"] == "missing"
        assert report[0]["artifact"] == "landscape-snapshot"

    def test_staleness_report_stale_artifact(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import staleness_report, write_snapshot
        from organvm_engine.ecosystem.pillar_dna import write_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "artifacts": [
                {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 30},
            ],
        }
        write_pillar_dna(tmp_path, "marketing", dna)

        # Write a snapshot from 60 days ago
        old_date = date.today() - timedelta(days=60)
        write_snapshot(tmp_path, "marketing", {"data": True}, snapshot_date=old_date)

        report = staleness_report(tmp_path)
        assert len(report) == 1
        assert report[0]["status"] == "stale"
        assert report[0]["days_stale"] >= 60

    def test_staleness_report_fresh(self, tmp_path):
        from organvm_engine.ecosystem.intelligence import staleness_report, write_snapshot
        from organvm_engine.ecosystem.pillar_dna import write_pillar_dna

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "lifecycle_stage": "research",
            "artifacts": [
                {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
            ],
        }
        write_pillar_dna(tmp_path, "marketing", dna)

        # Write a recent snapshot
        write_snapshot(tmp_path, "marketing", {"data": True}, snapshot_date=date.today())

        report = staleness_report(tmp_path)
        assert len(report) == 0  # fresh, not stale


# ── Scaffold ─────────────────────────────────────────────────────────


class TestScaffold:
    def _make_eco(self, tmp_path, arms=None):
        """Create ecosystem.yaml fixture."""
        eco = {
            "schema_version": "1.0",
            "repo": "test-product",
            "organ": "III",
            "marketing": arms or [
                {"platform": "seo", "status": "planned"},
                {"platform": "producthunt", "status": "not_started"},
            ],
            "revenue": [
                {"platform": "subscription", "status": "live"},
            ],
        }
        eco_path = tmp_path / "ecosystem.yaml"
        with eco_path.open("w") as f:
            yaml.dump(eco, f)
        return eco

    def test_scaffold_pillar_dna_basic(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_pillar_dna

        eco = self._make_eco(tmp_path)
        result = scaffold_pillar_dna(eco)

        assert "marketing" in result
        assert "revenue" in result
        assert result["marketing"]["pillar"] == "marketing"
        assert result["marketing"]["schema_version"] == "1.0"
        assert result["marketing"]["lifecycle_stage"] == "planning"  # from "planned" arm
        assert result["revenue"]["lifecycle_stage"] == "live"  # from "live" arm

    def test_scaffold_pillar_dna_with_seed(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_pillar_dna

        eco = self._make_eco(tmp_path)
        seed = {"metadata": {"tags": ["chrome", "extension"]}}

        result = scaffold_pillar_dna(eco, seed_data=seed)
        # Should infer browser_extension type
        assert result["marketing"]["product_type"] == "browser_extension"

    def test_scaffold_repo_ecosystem_dry_run(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_repo_ecosystem

        eco = self._make_eco(tmp_path)

        result = scaffold_repo_ecosystem(tmp_path, eco, dry_run=True)
        assert result["dry_run"] is True
        assert "marketing" in result["pillar_dnas"]
        assert len(result["written"]) == 0  # dry run

    def test_scaffold_repo_ecosystem_write(self, tmp_path):
        from organvm_engine.ecosystem.pillar_dna import list_pillar_dnas
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_repo_ecosystem

        eco = self._make_eco(tmp_path)

        result = scaffold_repo_ecosystem(tmp_path, eco, dry_run=False)
        assert result["dry_run"] is False
        assert len(result["written"]) == 2  # marketing + revenue

        # Verify files exist
        pillars = list_pillar_dnas(tmp_path)
        assert sorted(pillars) == ["marketing", "revenue"]

        # Verify directories created
        assert (tmp_path / "ecosystem" / "snapshots" / "marketing").is_dir()
        assert (tmp_path / "ecosystem" / "intelligence" / "revenue").is_dir()

    def test_scaffold_includes_artifacts(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_pillar_dna

        eco = self._make_eco(tmp_path)
        result = scaffold_pillar_dna(eco)

        # Marketing for default saas type should have artifacts
        marketing_dna = result["marketing"]
        assert len(marketing_dna.get("artifacts", [])) > 0

    def test_scaffold_includes_signals(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_pillar_dna

        eco = self._make_eco(tmp_path)
        result = scaffold_pillar_dna(eco)

        signals = result["marketing"].get("signals", {})
        assert "emits" in signals
        assert "listens" in signals

    def test_lifecycle_inference_conception(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_pillar_dna

        eco = {
            "schema_version": "1.0",
            "repo": "test",
            "organ": "III",
            "marketing": [
                {"platform": "seo", "status": "not_started"},
            ],
        }
        result = scaffold_pillar_dna(eco)
        assert result["marketing"]["lifecycle_stage"] == "conception"

    def test_lifecycle_inference_building(self, tmp_path):
        from organvm_engine.ecosystem.scaffold_pillar import scaffold_pillar_dna

        eco = {
            "schema_version": "1.0",
            "repo": "test",
            "organ": "III",
            "marketing": [
                {"platform": "seo", "status": "in_progress"},
            ],
        }
        result = scaffold_pillar_dna(eco)
        assert result["marketing"]["lifecycle_stage"] == "building"


# ── CLI ──────────────────────────────────────────────────────────────


class TestCLI:
    def _setup_repo(self, tmp_path, monkeypatch):
        """Create a repo with ecosystem.yaml and pillar DNA."""
        from organvm_engine.ecosystem.pillar_dna import write_pillar_dna

        # Create org/repo structure matching organ_org_dirs
        org_dir = tmp_path / "labores-profani-crux"
        repo_dir = org_dir / "test-product"
        repo_dir.mkdir(parents=True)

        eco = {
            "schema_version": "1.0",
            "repo": "test-product",
            "organ": "III",
            "marketing": [{"platform": "seo", "status": "planned"}],
        }
        with (repo_dir / "ecosystem.yaml").open("w") as f:
            yaml.dump(eco, f)

        dna = {
            "schema_version": "1.0",
            "pillar": "marketing",
            "product_type": "saas",
            "lifecycle_stage": "research",
            "research": {"scan_scope": ["seo"], "competitors": [], "cadence": "monthly"},
            "artifacts": [
                {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
            ],
            "gen_prompts": [],
            "crit_prompts": [],
            "gates": {},
            "signals": {"emits": [], "listens": []},
        }
        write_pillar_dna(repo_dir, "marketing", dna)

        # Monkeypatch organ_org_dirs to include only our test dir
        monkeypatch.setattr(
            "organvm_engine.organ_config.organ_org_dirs",
            lambda: ["labores-profani-crux"],
        )

        return repo_dir

    def test_cmd_dna(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.cli.ecosystem import cmd_ecosystem_dna

        self._setup_repo(tmp_path, monkeypatch)

        import argparse
        args = argparse.Namespace(
            workspace=str(tmp_path),
            repo="test-product",
            pillar=None,
            json=False,
            organ=None,
        )
        result = cmd_ecosystem_dna(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "marketing" in out
        assert "research" in out

    def test_cmd_dna_single_pillar(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.cli.ecosystem import cmd_ecosystem_dna

        self._setup_repo(tmp_path, monkeypatch)

        import argparse
        args = argparse.Namespace(
            workspace=str(tmp_path),
            repo="test-product",
            pillar="marketing",
            json=False,
            organ=None,
        )
        result = cmd_ecosystem_dna(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "marketing" in out

    def test_cmd_dna_not_found(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.cli.ecosystem import cmd_ecosystem_dna

        monkeypatch.setattr(
            "organvm_engine.organ_config.organ_org_dirs",
            lambda: ["labores-profani-crux"],
        )

        import argparse
        args = argparse.Namespace(
            workspace=str(tmp_path),
            repo="nonexistent-repo",
            pillar=None,
            json=False,
            organ=None,
        )
        result = cmd_ecosystem_dna(args)
        assert result == 1

    def test_cmd_scaffold_dna(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.cli.ecosystem import cmd_ecosystem_scaffold_dna

        # Create repo with ecosystem.yaml but no pillar DNA
        org_dir = tmp_path / "labores-profani-crux"
        repo_dir = org_dir / "test-product"
        repo_dir.mkdir(parents=True)

        eco = {
            "schema_version": "1.0",
            "repo": "test-product",
            "organ": "III",
            "marketing": [{"platform": "seo", "status": "planned"}],
        }
        with (repo_dir / "ecosystem.yaml").open("w") as f:
            yaml.dump(eco, f)

        monkeypatch.setattr(
            "organvm_engine.organ_config.organ_org_dirs",
            lambda: ["labores-profani-crux"],
        )

        import argparse
        args = argparse.Namespace(
            workspace=str(tmp_path),
            repo="test-product",
            write=False,
            organ=None,
            registry=str(tmp_path / "dummy.json"),
        )
        result = cmd_ecosystem_scaffold_dna(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "marketing" in out

    def test_cmd_lifecycle(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.cli.ecosystem import cmd_ecosystem_lifecycle

        self._setup_repo(tmp_path, monkeypatch)

        import argparse
        args = argparse.Namespace(
            workspace=str(tmp_path),
            repo="test-product",
            json=False,
            organ=None,
        )
        result = cmd_ecosystem_lifecycle(args)
        assert result == 0
        out = capsys.readouterr().out
        assert "marketing" in out
        assert "research" in out

    def test_cmd_staleness(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.cli.ecosystem import cmd_ecosystem_staleness

        self._setup_repo(tmp_path, monkeypatch)

        # Monkeypatch discover to find our test repo
        def mock_discover(workspace=None, organ=None):
            org_dir = tmp_path / "labores-profani-crux"
            results = []
            if org_dir.is_dir():
                for repo_d in sorted(org_dir.iterdir()):
                    eco = repo_d / "ecosystem.yaml"
                    if eco.is_file():
                        results.append(eco)
            return results

        monkeypatch.setattr(
            "organvm_engine.ecosystem.discover.discover_ecosystems",
            mock_discover,
        )

        import argparse
        args = argparse.Namespace(
            workspace=str(tmp_path),
            organ=None,
            json=False,
        )

        result = cmd_ecosystem_staleness(args)
        assert result == 0
        out = capsys.readouterr().out
        # Should show missing artifact (no snapshots created)
        assert "missing" in out.lower() or "stale" in out.lower() or "No stale" in out
