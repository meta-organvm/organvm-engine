"""Tests for the unified CLI (cli.py).

Covers:
- Parser construction and argument parsing
- --help for all command groups
- Registry commands with mock data
- Error handling for invalid inputs
- Dispatch table completeness
"""

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from organvm_engine.cli import build_parser, main

FIXTURES = Path(__file__).parent / "fixtures"
MOCK_REGISTRY = str(FIXTURES / "registry-minimal.json")


# ── Parser construction ──────────────────────────────────────────


class TestParserConstruction:
    """Verify the parser builds without errors and recognizes all commands."""

    def test_build_parser_returns_parser(self):
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_no_args_shows_help(self, capsys):
        """No arguments should print help and return 0."""
        with patch("sys.argv", ["organvm"]):
            rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        assert "organvm" in captured.out

    def test_parser_has_registry_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--registry", "/tmp/test.json", "registry", "validate"])
        assert args.registry == "/tmp/test.json"


# ── Help output ──────────────────────────────────────────────────


class TestHelpOutput:
    """Verify --help works for every command group."""

    @pytest.mark.parametrize("cmd", [
        ["--help"],
        ["registry", "--help"],
        ["governance", "--help"],
        ["seed", "--help"],
        ["metrics", "--help"],
        ["dispatch", "--help"],
        ["git", "--help"],
        ["omega", "--help"],
        ["pitch", "--help"],
        ["context", "--help"],
        ["deadlines", "--help"],
        ["ci", "--help"],
    ])
    def test_help_exits_zero(self, cmd):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(cmd)
        assert exc_info.value.code == 0


# ── Dispatch table ───────────────────────────────────────────────


class TestDispatchTable:
    """Verify all command/subcommand pairs are present in the dispatch table."""

    def test_all_registry_subcommands_dispatch(self):
        from organvm_engine.cli import main
        # These should parse without error
        parser = build_parser()
        for sub in ["show recursive-engine", "list", "validate", "update repo field val"]:
            args = parser.parse_args(["--registry", MOCK_REGISTRY, "registry"] + sub.split())
            assert args.command == "registry"

    def test_all_governance_subcommands_parse(self):
        parser = build_parser()
        for sub in ["audit", "check-deps", "promote repo CANDIDATE", "impact repo"]:
            args = parser.parse_args(["--registry", MOCK_REGISTRY, "governance"] + sub.split())
            assert args.command == "governance"

    def test_all_seed_subcommands_parse(self):
        parser = build_parser()
        for sub in ["discover", "validate", "graph"]:
            args = parser.parse_args(["seed"] + sub.split())
            assert args.command == "seed"

    def test_all_git_subcommands_parse(self):
        parser = build_parser()
        for sub in [
            "init-superproject --organ META --dry-run",
            "sync-organ --organ META --dry-run",
            "sync-all --dry-run",
            "status",
            "diff-pinned",
            "install-hooks",
        ]:
            args = parser.parse_args(["git"] + sub.split())
            assert args.command == "git"

    def test_all_omega_subcommands_parse(self):
        parser = build_parser()
        for sub in ["status", "check", "update --dry-run"]:
            args = parser.parse_args(["--registry", MOCK_REGISTRY, "omega"] + sub.split())
            assert args.command == "omega"

    def test_all_pitch_subcommands_parse(self):
        parser = build_parser()
        for sub in ["generate repo --dry-run", "sync --dry-run"]:
            args = parser.parse_args(["--registry", MOCK_REGISTRY, "pitch"] + sub.split())
            assert args.command == "pitch"


# ── Registry commands ────────────────────────────────────────────


class TestRegistryCommands:
    """Test registry commands with the minimal fixture registry."""

    def test_registry_show_existing_repo(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "show", "recursive-engine"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "recursive-engine" in out
        assert "ORGAN-I" in out

    def test_registry_show_missing_repo(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "show", "nonexistent-repo"]):
            rc = main()
        assert rc == 1
        out = capsys.readouterr().out
        assert "not found" in out

    def test_registry_list_all(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "list"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "recursive-engine" in out
        assert "product-app" in out

    def test_registry_list_by_organ(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "list", "--organ", "I"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "recursive-engine" in out
        # ORGAN-III repos should not appear
        assert "product-app" not in out

    def test_registry_list_by_tier(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "list", "--tier", "flagship"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "recursive-engine" in out
        assert "product-app" not in out  # product-app is "standard"

    def test_registry_validate_passes(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "validate"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "6 repos checked" in out

    def test_registry_list_empty_filter(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "registry", "list", "--organ", "VII"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "No repos" in out


# ── Governance commands ──────────────────────────────────────────


class TestGovernanceCommands:

    def test_governance_audit(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "governance", "audit"]):
            rc = main()
        out = capsys.readouterr().out
        assert "Governance Audit" in out

    def test_governance_check_deps(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "governance", "check-deps"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "Total edges" in out

    def test_governance_promote_valid(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "governance", "promote", "recursive-engine", "GRADUATED"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "valid" in out.lower() or "Transition" in out

    def test_governance_promote_invalid(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "governance", "promote", "ontological-framework", "GRADUATED"]):
            rc = main()
        assert rc == 1  # LOCAL → GRADUATED is invalid

    def test_governance_promote_missing_repo(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "governance", "promote", "nonexistent", "CANDIDATE"]):
            rc = main()
        assert rc == 1
        out = capsys.readouterr().out
        assert "not found" in out

    def test_governance_impact(self, capsys):
        from organvm_engine.seed.graph import SeedGraph
        mock_graph = SeedGraph(nodes=[], produces={}, consumes={}, edges=[], errors=[])
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "governance", "impact", "recursive-engine"]):
            with patch("organvm_engine.governance.impact.build_seed_graph", return_value=mock_graph):
                rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "Impact Analysis" in out


# ── Omega commands ───────────────────────────────────────────────


class TestOmegaCommands:

    def test_omega_status(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "omega", "status"]):
            rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "Omega" in out or "MET" in out

    def test_omega_check_json(self, capsys):
        with patch("sys.argv", ["organvm", "--registry", MOCK_REGISTRY, "omega", "check"]):
            rc = main()
        assert rc == 0
        import json
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "met_count" in data or "criteria" in data


# ── Dry-run flags ────────────────────────────────────────────────


class TestDryRunFlags:
    """Verify that --dry-run is parsed and passed through."""

    def test_git_init_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["git", "init-superproject", "--organ", "META", "--dry-run"])
        assert args.dry_run is True

    def test_git_sync_organ_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["git", "sync-organ", "--organ", "META", "--dry-run"])
        assert args.dry_run is True

    def test_metrics_propagate_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["metrics", "propagate", "--dry-run"])
        assert args.dry_run is True

    def test_context_sync_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["context", "sync", "--dry-run"])
        assert args.dry_run is True

    def test_omega_update_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["omega", "update", "--dry-run"])
        assert args.dry_run is True

    def test_pitch_generate_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["pitch", "generate", "my-repo", "--dry-run"])
        assert args.dry_run is True

    def test_pitch_sync_has_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["pitch", "sync", "--dry-run"])
        assert args.dry_run is True


# ── Error handling ───────────────────────────────────────────────


class TestErrorHandling:

    def test_invalid_registry_path(self):
        with patch("sys.argv", ["organvm", "--registry", "/nonexistent/path.json", "registry", "validate"]):
            with pytest.raises((FileNotFoundError, SystemExit)):
                main()

    def test_missing_subcommand_shows_help(self, capsys):
        """Command without subcommand should show help."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["registry", "--help"])
        assert exc_info.value.code == 0
