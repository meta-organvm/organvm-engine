"""CLI smoke tests for institutional primitives and formations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from organvm_engine.cli import main


@pytest.fixture
def institutional_state_root(tmp_path, monkeypatch):
    import organvm_engine.primitives.archivist as archivist_mod
    import organvm_engine.primitives.guardian as guardian_mod
    import organvm_engine.primitives.inst_ledger as ledger_mod
    import organvm_engine.primitives.mandator as mandator_mod

    monkeypatch.setattr(guardian_mod, "_DEFAULT_BASE", tmp_path / "guardian")
    monkeypatch.setattr(ledger_mod, "_DEFAULT_BASE", tmp_path / "ledger")
    monkeypatch.setattr(archivist_mod, "_DEFAULT_BASE", tmp_path / "archivist")
    monkeypatch.setattr(mandator_mod, "_DEFAULT_BASE", tmp_path / "mandator")
    return tmp_path


def _run_cli(args: list[str]) -> int:
    with patch("sys.argv", ["organvm", *args]):
        return main()


def test_primitive_guardian_commands_smoke(
    institutional_state_root: Path,
    capsys,
) -> None:
    deadline = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    rc = _run_cli([
        "primitive",
        "guardian",
        "add-watch",
        "--category",
        "deadline",
        "--description",
        "Lease renewal",
        "--threshold",
        deadline,
        "--direction",
        "approaching",
        "--alert-window",
        "7",
    ])
    assert rc == 0
    assert "Watch added:" in capsys.readouterr().out

    rc = _run_cli(["primitive", "guardian", "watchlist", "--json"])
    assert rc == 0
    watchlist = json.loads(capsys.readouterr().out)
    assert len(watchlist) == 1
    assert watchlist[0]["description"] == "Lease renewal"

    rc = _run_cli(["primitive", "guardian", "check"])
    assert rc == 0
    output = capsys.readouterr().out
    assert "alert(s)" in output
    assert "Lease renewal" in output


def test_primitive_ledger_commands_smoke(
    institutional_state_root: Path,
    capsys,
) -> None:
    rc = _run_cli([
        "primitive",
        "ledger",
        "record",
        "--category",
        "income",
        "--amount",
        "5000",
        "--description",
        "Monthly salary",
        "--direction",
        "inflow",
        "--recurring",
        "--frequency",
        "monthly",
    ])
    assert rc == 0
    assert "Recorded:" in capsys.readouterr().out

    rc = _run_cli([
        "primitive",
        "ledger",
        "record",
        "--category",
        "expense",
        "--amount",
        "1800",
        "--description",
        "Rent",
        "--direction",
        "outflow",
        "--recurring",
        "--frequency",
        "monthly",
    ])
    assert rc == 0
    assert "Recorded:" in capsys.readouterr().out

    rc = _run_cli(["primitive", "ledger", "snapshot", "--json"])
    assert rc == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert snapshot["monthly_inflow"] == 5000.0
    assert snapshot["monthly_outflow"] == 1800.0

    rc = _run_cli(["primitive", "ledger", "entries", "--json"])
    assert rc == 0
    entries = json.loads(capsys.readouterr().out)
    assert len(entries) == 2
    assert {entry["category"] for entry in entries} == {"income", "expense"}


def test_formation_commands_smoke(
    institutional_state_root: Path,
    capsys,
) -> None:
    deadline = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    context = json.dumps({
        "situation": "Lease renewal deadline approaching",
        "data": {
            "deadline": deadline,
            "category": "housing",
        },
        "interests": ["Housing stability"],
        "objectives": ["Renew lease on favorable terms"],
    })

    rc = _run_cli(["formation", "list", "--json"])
    assert rc == 0
    formations = json.loads(capsys.readouterr().out)
    assert any(formation["name"] == "aegis" for formation in formations)

    rc = _run_cli(["formation", "show", "aegis"])
    assert rc == 0
    shown = capsys.readouterr().out
    assert "FORM-INST-001" in shown
    assert "guardian" in shown
    assert "mandator" in shown

    rc = _run_cli(["formation", "invoke", "aegis", "--context", context, "--json"])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["output"] is not None
    assert len(result["audit_trail"]) > 0
