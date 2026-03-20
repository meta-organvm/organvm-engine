"""Tests for the ledger CLI commands."""

from __future__ import annotations

import argparse
import json

from organvm_engine.cli.ledger import (
    cmd_ledger_checkpoint,
    cmd_ledger_genesis,
    cmd_ledger_log,
    cmd_ledger_status,
    cmd_ledger_verify,
)


def _args(**kwargs):
    """Create a mock argparse.Namespace with defaults."""
    defaults = {
        "chain_path": None,
        "json": False,
        "event": None,
        "full": False,
        "type": None,
        "tier": None,
        "limit": 20,
        "write": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestLedgerGenesis:

    def test_genesis_creates_chain(self, tmp_path):
        chain_path = tmp_path / "chain.jsonl"
        result = cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        assert result == 0
        assert chain_path.is_file()
        data = json.loads(chain_path.read_text().strip())
        assert data["event_type"] == "testament.genesis"
        assert data["sequence"] == 0
        assert data["hash"].startswith("sha256:")

    def test_genesis_refuses_existing_chain(self, tmp_path):
        chain_path = tmp_path / "chain.jsonl"
        chain_path.write_text('{"existing": true}\n')
        result = cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        assert result == 1

    def test_genesis_creates_parent_dirs(self, tmp_path):
        chain_path = tmp_path / "deep" / "nested" / "chain.jsonl"
        result = cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        assert result == 0
        assert chain_path.is_file()


class TestLedgerStatus:

    def test_status_no_chain(self, tmp_path, capsys):
        result = cmd_ledger_status(
            _args(chain_path=str(tmp_path / "empty.jsonl")),
        )
        assert result == 0

    def test_status_json_no_chain(self, tmp_path, capsys):
        result = cmd_ledger_status(
            _args(chain_path=str(tmp_path / "empty.jsonl"), json=True),
        )
        assert result == 0
        out = json.loads(capsys.readouterr().out)
        assert out["exists"] is False

    def test_status_with_events(self, tmp_path, capsys):
        chain_path = tmp_path / "chain.jsonl"
        cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        capsys.readouterr()  # discard genesis output
        result = cmd_ledger_status(
            _args(chain_path=str(chain_path), json=True),
        )
        assert result == 0
        out = json.loads(capsys.readouterr().out)
        assert out["exists"] is True
        assert out["valid"] is True
        assert out["event_count"] == 1


class TestLedgerVerify:

    def test_verify_no_chain(self, tmp_path):
        result = cmd_ledger_verify(
            _args(chain_path=str(tmp_path / "nope.jsonl")),
        )
        assert result == 1

    def test_verify_valid_chain(self, tmp_path):
        chain_path = tmp_path / "chain.jsonl"
        cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        result = cmd_ledger_verify(_args(chain_path=str(chain_path)))
        assert result == 0

    def test_verify_corrupted_chain(self, tmp_path):
        chain_path = tmp_path / "chain.jsonl"
        chain_path.write_text('{"tampered": true}\n')
        result = cmd_ledger_verify(_args(chain_path=str(chain_path)))
        assert result == 1


class TestLedgerLog:

    def test_log_empty_chain(self, tmp_path, capsys):
        result = cmd_ledger_log(
            _args(chain_path=str(tmp_path / "empty.jsonl")),
        )
        assert result == 0

    def test_log_with_events(self, tmp_path, capsys):
        chain_path = tmp_path / "chain.jsonl"
        cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        result = cmd_ledger_log(_args(chain_path=str(chain_path)))
        assert result == 0
        out = capsys.readouterr().out
        assert "testament.genesis" in out

    def test_log_json_output(self, tmp_path, capsys):
        chain_path = tmp_path / "chain.jsonl"
        cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        capsys.readouterr()  # discard genesis output
        result = cmd_ledger_log(
            _args(chain_path=str(chain_path), json=True),
        )
        assert result == 0
        events = json.loads(capsys.readouterr().out)
        assert len(events) == 1
        assert events[0]["event_type"] == "testament.genesis"

    def test_log_tier_filter(self, tmp_path, capsys):
        from organvm_engine.events.spine import EventSpine

        chain_path = tmp_path / "chain.jsonl"
        spine = EventSpine(chain_path)
        spine.emit(event_type="governance.promotion", entity_uid="e", actor="t")
        spine.emit(event_type="git.sync", entity_uid="e", actor="t")

        # Filter to governance only
        result = cmd_ledger_log(
            _args(chain_path=str(chain_path), tier="governance", limit=100),
        )
        assert result == 0
        out = capsys.readouterr().out
        assert "governance.promotion" in out
        assert "git.sync" not in out


class TestLedgerCheckpoint:

    def test_checkpoint_dry_run(self, tmp_path, capsys):
        chain_path = tmp_path / "chain.jsonl"
        cmd_ledger_genesis(_args(chain_path=str(chain_path)))
        result = cmd_ledger_checkpoint(_args(chain_path=str(chain_path)))
        assert result == 0
        out = capsys.readouterr().out
        assert "dry-run" in out

    def test_checkpoint_write(self, tmp_path, capsys):
        chain_path = tmp_path / "chain.jsonl"
        cmd_ledger_genesis(_args(chain_path=str(chain_path)))

        from organvm_engine.events.spine import EventSpine
        spine = EventSpine(chain_path)
        for i in range(5):
            spine.emit(event_type="test", entity_uid=f"e{i}", actor="t")

        result = cmd_ledger_checkpoint(
            _args(chain_path=str(chain_path), write=True),
        )
        assert result == 0
        out = capsys.readouterr().out
        assert "Checkpoint created" in out
        assert "Merkle root" in out

        # Verify checkpoint event was written
        events = spine.query(limit=100)
        checkpoint_events = [e for e in events if e.event_type == "testament.checkpoint"]
        assert len(checkpoint_events) == 1

    def test_checkpoint_empty_chain(self, tmp_path, capsys):
        chain_path = tmp_path / "empty.jsonl"
        chain_path.parent.mkdir(parents=True, exist_ok=True)
        chain_path.touch()
        result = cmd_ledger_checkpoint(
            _args(chain_path=str(chain_path), write=True),
        )
        assert result == 0
