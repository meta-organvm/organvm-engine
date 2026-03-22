"""Tests for organvm taxonomy CLI commands."""

import argparse
import json

from organvm_engine.cli.taxonomy import cmd_taxonomy_audit, cmd_taxonomy_classify


def _make_args(**kwargs):
    defaults = {"organ": None, "as_json": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_classify_returns_zero(registry, monkeypatch):
    monkeypatch.setattr(
        "organvm_engine.cli.taxonomy.load_registry", lambda: registry,
    )
    result = cmd_taxonomy_classify(_make_args())
    assert result == 0


def test_audit_returns_zero(registry, monkeypatch):
    monkeypatch.setattr(
        "organvm_engine.cli.taxonomy.load_registry", lambda: registry,
    )
    result = cmd_taxonomy_audit(_make_args())
    assert result == 0


def test_classify_with_organ_filter(registry, monkeypatch):
    monkeypatch.setattr(
        "organvm_engine.cli.taxonomy.load_registry", lambda: registry,
    )
    result = cmd_taxonomy_classify(_make_args(organ="ORGAN-I"))
    assert result == 0


def test_audit_with_organ_filter(registry, monkeypatch):
    monkeypatch.setattr(
        "organvm_engine.cli.taxonomy.load_registry", lambda: registry,
    )
    result = cmd_taxonomy_audit(_make_args(organ="ORGAN-I"))
    assert result == 0


def test_classify_json_output(registry, monkeypatch, capsys):
    monkeypatch.setattr(
        "organvm_engine.cli.taxonomy.load_registry", lambda: registry,
    )
    result = cmd_taxonomy_classify(_make_args(as_json=True))
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "heuristic" in data[0]
    assert "recorded" in data[0]


def test_audit_json_output(registry, monkeypatch, capsys):
    monkeypatch.setattr(
        "organvm_engine.cli.taxonomy.load_registry", lambda: registry,
    )
    result = cmd_taxonomy_audit(_make_args(as_json=True))
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert "total" in data
    assert "classified" in data
    assert "drift" in data
