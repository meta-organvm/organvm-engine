"""Tests for pulse CLI subcommands — scan, ammoi, history, start, stop, status."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ns(**kwargs) -> Namespace:
    """Build a Namespace with defaults for the pulse CLI."""
    defaults = {"json": False, "command": "pulse"}
    defaults.update(kwargs)
    return Namespace(**defaults)


# ---------------------------------------------------------------------------
# cmd_pulse_scan
# ---------------------------------------------------------------------------


class TestCmdPulseScan:
    def test_returns_zero(self, monkeypatch, tmp_path):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_scan
        from organvm_engine.pulse import rhythm

        monkeypatch.setattr(
            "organvm_engine.cli.cmd_pulse._resolve_workspace_path",
            lambda _: tmp_path,
        )
        monkeypatch.setattr(rhythm, "pulse_once", lambda **kw: _make_stub_ammoi())
        result = cmd_pulse_scan(_ns(subcommand="scan", no_sensors=False))
        assert result == 0

    def test_json_output(self, monkeypatch, tmp_path, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_scan
        from organvm_engine.pulse import rhythm

        monkeypatch.setattr(
            "organvm_engine.cli.cmd_pulse._resolve_workspace_path",
            lambda _: tmp_path,
        )
        monkeypatch.setattr(rhythm, "pulse_once", lambda **kw: _make_stub_ammoi())
        result = cmd_pulse_scan(_ns(subcommand="scan", no_sensors=False, json=True))
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "system_density" in data


# ---------------------------------------------------------------------------
# cmd_pulse_ammoi
# ---------------------------------------------------------------------------


class TestCmdPulseAmmoi:
    def test_returns_zero(self, monkeypatch, tmp_path):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_ammoi
        from organvm_engine.pulse import ammoi as ammoi_mod

        monkeypatch.setattr(
            "organvm_engine.cli.cmd_pulse._resolve_workspace_path",
            lambda _: tmp_path,
        )
        monkeypatch.setattr(ammoi_mod, "compute_ammoi", lambda **kw: _make_stub_ammoi())
        result = cmd_pulse_ammoi(_ns(subcommand="ammoi", organ=None, repo=None))
        assert result == 0


# ---------------------------------------------------------------------------
# cmd_pulse_history
# ---------------------------------------------------------------------------


class TestCmdPulseHistory:
    def test_empty_history(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_history

        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.pulse_history",
            lambda **kw: [],
        )
        result = cmd_pulse_history(_ns(subcommand="history", days=30))
        assert result == 0
        assert "No AMMOI history" in capsys.readouterr().out

    def test_json_empty(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_history

        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.pulse_history",
            lambda **kw: [],
        )
        result = cmd_pulse_history(_ns(subcommand="history", days=30, json=True))
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_with_snapshots(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_history

        snapshots = [
            {
                "timestamp": "2026-03-13T10:00:00",
                "system_density": 0.42,
                "total_entities": 100,
                "active_edges": 50,
                "event_frequency_24h": 7,
            },
        ]
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.pulse_history",
            lambda **kw: snapshots,
        )
        result = cmd_pulse_history(_ns(subcommand="history", days=30))
        assert result == 0
        out = capsys.readouterr().out
        assert "42.0%" in out


# ---------------------------------------------------------------------------
# cmd_pulse_start
# ---------------------------------------------------------------------------


class TestCmdPulseStart:
    def test_installs_and_starts(self, monkeypatch, tmp_path, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_start

        plist_path = tmp_path / "test.plist"
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.install_launchagent",
            lambda interval=900: str(plist_path),
        )
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.PLIST_LABEL",
            "com.test.pulse",
        )
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.launchagent_status",
            lambda: {"installed": True, "running": True},
        )
        # Mock subprocess.run for launchctl calls
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stderr": ""})(),
        )
        result = cmd_pulse_start(_ns(subcommand="start", interval=900))
        assert result == 0
        out = capsys.readouterr().out
        assert "installed and started" in out

    def test_json_output(self, monkeypatch, tmp_path, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_start

        plist_path = tmp_path / "test.plist"
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.install_launchagent",
            lambda interval=900: str(plist_path),
        )
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.launchagent_status",
            lambda: {"installed": True, "running": True},
        )
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stderr": ""})(),
        )
        result = cmd_pulse_start(_ns(subcommand="start", interval=900, json=True))
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["installed"] is True


# ---------------------------------------------------------------------------
# cmd_pulse_stop
# ---------------------------------------------------------------------------


class TestCmdPulseStop:
    def test_stop_when_installed(self, monkeypatch, tmp_path, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_stop

        plist = tmp_path / "test.plist"
        plist.write_text("<plist/>")
        monkeypatch.setattr("organvm_engine.pulse.rhythm.PLIST_PATH", plist)
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.uninstall_launchagent",
            lambda: True,
        )
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: type("R", (), {"returncode": 0})(),
        )
        result = cmd_pulse_stop(_ns(subcommand="stop"))
        assert result == 0
        assert "stopped and removed" in capsys.readouterr().out

    def test_stop_when_not_installed(self, monkeypatch, tmp_path, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_stop

        plist = tmp_path / "nonexistent.plist"
        monkeypatch.setattr("organvm_engine.pulse.rhythm.PLIST_PATH", plist)
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.uninstall_launchagent",
            lambda: False,
        )
        result = cmd_pulse_stop(_ns(subcommand="stop"))
        assert result == 0
        assert "not installed" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# cmd_pulse_status
# ---------------------------------------------------------------------------


class TestCmdPulseStatus:
    def test_not_installed(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_status

        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.launchagent_status",
            lambda: {"installed": False, "running": False, "plist_path": "/tmp/x", "log_path": "/tmp/y"},
        )
        result = cmd_pulse_status(_ns(subcommand="status"))
        assert result == 0
        out = capsys.readouterr().out
        assert "NOT INSTALLED" in out

    def test_running(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_status

        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.launchagent_status",
            lambda: {
                "installed": True,
                "running": True,
                "plist_path": "/tmp/x",
                "log_path": "/tmp/y",
                "pid": "12345",
                "log_lines": 42,
                "last_log": "[pulse] cycle=1 density=42.0%",
            },
        )
        # Mock _read_history to avoid real file reads
        monkeypatch.setattr(
            "organvm_engine.pulse.ammoi._read_history",
            lambda limit=1: [],
        )
        result = cmd_pulse_status(_ns(subcommand="status"))
        assert result == 0
        out = capsys.readouterr().out
        assert "RUNNING" in out
        assert "12345" in out

    def test_json_output(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_status

        status_data = {"installed": True, "running": False, "plist_path": "/tmp/x", "log_path": "/tmp/y"}
        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.launchagent_status",
            lambda: status_data,
        )
        result = cmd_pulse_status(_ns(subcommand="status", json=True))
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["installed"] is True


# ---------------------------------------------------------------------------
# pulse_daemon
# ---------------------------------------------------------------------------


class TestPulseDaemon:
    def test_runs_max_cycles(self, monkeypatch, tmp_path):
        from organvm_engine.pulse.rhythm import pulse_daemon

        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.pulse_once",
            lambda **kw: _make_stub_ammoi(),
        )
        # Should complete without hanging
        pulse_daemon(interval=0, workspace=tmp_path, max_cycles=2)

    def test_handles_error_gracefully(self, monkeypatch, tmp_path, capsys):
        from organvm_engine.pulse.rhythm import pulse_daemon

        call_count = 0

        def _failing_pulse(**kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("test failure")
            return _make_stub_ammoi()

        monkeypatch.setattr(
            "organvm_engine.pulse.rhythm.pulse_once",
            _failing_pulse,
        )
        pulse_daemon(interval=0, workspace=tmp_path, max_cycles=2)
        err = capsys.readouterr().err
        assert "test failure" in err


# ---------------------------------------------------------------------------
# LaunchAgent management
# ---------------------------------------------------------------------------


class TestLaunchAgentManagement:
    def test_install_creates_plist(self, monkeypatch, tmp_path):
        from organvm_engine.pulse import rhythm

        plist = tmp_path / "test.plist"
        monkeypatch.setattr(rhythm, "PLIST_PATH", plist)
        monkeypatch.setattr(rhythm, "LOG_PATH", tmp_path / "test.log")
        rhythm.install_launchagent(interval=300)
        assert plist.exists()
        content = plist.read_text()
        assert "com.4jp.organvm.pulse" in content
        assert "<integer>300</integer>" in content

    def test_uninstall_removes_plist(self, monkeypatch, tmp_path):
        from organvm_engine.pulse import rhythm

        plist = tmp_path / "test.plist"
        plist.write_text("<plist/>")
        monkeypatch.setattr(rhythm, "PLIST_PATH", plist)
        assert rhythm.uninstall_launchagent() is True
        assert not plist.exists()

    def test_uninstall_returns_false_when_missing(self, monkeypatch, tmp_path):
        from organvm_engine.pulse import rhythm

        plist = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(rhythm, "PLIST_PATH", plist)
        assert rhythm.uninstall_launchagent() is False

    def test_status_not_installed(self, monkeypatch, tmp_path):
        from organvm_engine.pulse import rhythm

        plist = tmp_path / "nonexistent.plist"
        monkeypatch.setattr(rhythm, "PLIST_PATH", plist)
        status = rhythm.launchagent_status()
        assert status["installed"] is False
        assert status["running"] is False

    def test_generate_plist_content(self):
        from organvm_engine.pulse.rhythm import _generate_plist

        content = _generate_plist(interval=600)
        assert "StartInterval" in content
        assert "<integer>600</integer>" in content
        assert "com.4jp.organvm.pulse" in content


# ---------------------------------------------------------------------------
# Stub AMMOI
# ---------------------------------------------------------------------------


def _make_stub_ammoi():
    """Create a minimal AMMOI instance for testing."""
    from organvm_engine.pulse.ammoi import AMMOI

    return AMMOI(
        timestamp="2026-03-13T10:00:00Z",
        system_density=0.42,
        total_entities=100,
        active_edges=50,
        active_loops=0,
        tension_count=0,
        event_frequency_24h=7,
        density_delta_24h=0.0,
        density_delta_7d=0.0,
        density_delta_30d=0.0,
        organs={},
        pulse_count=1,
        pulse_interval=900,
        compressed_text="test snapshot",
    )
