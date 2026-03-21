"""Tests for the testament play CLI command (sonic bridge) — issue #49."""

from __future__ import annotations

from pathlib import Path

from organvm_engine.cli import build_parser
from organvm_engine.cli.testament import cmd_testament_play

FIXTURES = Path(__file__).parent / "fixtures"
MOCK_REGISTRY = str(FIXTURES / "registry-minimal.json")


def test_build_parser_has_play_subcommand():
    parser = build_parser()
    args = parser.parse_args(["testament", "play"])
    assert args.command == "testament"
    assert args.subcommand == "play"


def test_build_parser_play_accepts_flags():
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--json", "--registry", "/tmp/r.json"])
    assert args.json is True
    assert args.registry == "/tmp/r.json"


def test_build_parser_play_osc_flag():
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--osc"])
    assert args.osc is True


def test_build_parser_play_yaml_flag():
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--yaml"])
    assert args.yaml is True


def test_play_default_output(capsys):
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--registry", MOCK_REGISTRY])
    rc = cmd_testament_play(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "testament:" in out
    assert "voices:" in out
    assert "OSC Messages" in out


def test_play_json_output(capsys):
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--json", "--registry", MOCK_REGISTRY])
    rc = cmd_testament_play(args)
    assert rc == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert "voices" in data
    assert "osc_messages" in data
    assert isinstance(data["osc_messages"], list)
    assert len(data["voices"]) == 8


def test_play_osc_only(capsys):
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--osc", "--registry", MOCK_REGISTRY])
    rc = cmd_testament_play(args)
    assert rc == 0
    out = capsys.readouterr().out
    lines = [l for l in out.strip().split("\n") if l.strip()]
    assert all(l.startswith("/testament/") for l in lines)


def test_play_yaml_only(capsys):
    parser = build_parser()
    args = parser.parse_args(["testament", "play", "--yaml", "--registry", MOCK_REGISTRY])
    rc = cmd_testament_play(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "testament:" in out
    assert "voices:" in out
    # YAML-only should not have OSC section
    assert "OSC Messages" not in out
