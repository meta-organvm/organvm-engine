"""Tests for tool checkout line (command-level coordination)."""

from __future__ import annotations

import json
import time

import pytest

from organvm_engine.coordination.tool_lock import (
    CHECKOUT_TTL_SECONDS,
    ToolCheckout,
    _build_active_checkouts,
    classify_command,
    tool_checkin,
    tool_checkout,
    tool_queue,
)


@pytest.fixture(autouse=True)
def isolated_claims_file(tmp_path, monkeypatch):
    """Route all events to a temp file."""
    claims_file = tmp_path / "claims.jsonl"
    monkeypatch.setenv("ORGANVM_CLAIMS_FILE", str(claims_file))
    return claims_file


class TestClassifyCommand:
    def test_pytest_is_heavy(self):
        assert classify_command("pytest tests/ -v") == "heavy"

    def test_npm_test_is_heavy(self):
        assert classify_command("npm test") == "heavy"

    def test_npm_run_build_is_heavy(self):
        assert classify_command("npm run build") == "heavy"

    def test_pip_install_is_heavy(self):
        assert classify_command("pip install -e '.[dev]'") == "heavy"

    def test_cargo_test_is_heavy(self):
        assert classify_command("cargo test") == "heavy"

    def test_ruff_is_medium(self):
        assert classify_command("ruff check src/") == "medium"

    def test_git_commit_is_medium(self):
        assert classify_command("git commit -m 'feat: add'") == "medium"

    def test_git_push_is_medium(self):
        assert classify_command("git push origin main") == "medium"

    def test_pyright_is_medium(self):
        assert classify_command("pyright") == "medium"

    def test_git_status_is_light(self):
        assert classify_command("git status") == "light"

    def test_ls_is_light(self):
        assert classify_command("ls -la") == "light"

    def test_echo_is_light(self):
        assert classify_command("echo hello") == "light"


class TestToolCheckout:
    def test_light_command_always_clears(self):
        result = tool_checkout(
            handle="claude-forge",
            command_hint="git status",
        )
        assert result["cleared"] is True
        assert result["weight"] == "light"
        assert result["checkout_id"] == ""

    def test_heavy_command_clears_when_empty(self):
        result = tool_checkout(
            handle="claude-forge",
            command_hint="pytest tests/ -v",
        )
        assert result["cleared"] is True
        assert result["weight"] == "heavy"
        assert result["checkout_id"] != ""

    def test_heavy_command_blocked_when_lane_full(self):
        # First agent checks out heavy
        tool_checkout(
            handle="claude-forge",
            command_hint="pytest engine/ -v",
        )
        # Second agent tries heavy — blocked
        result = tool_checkout(
            handle="gemini-scout",
            command_hint="pytest mcp/ -v",
        )
        assert result["cleared"] is False
        assert result["wait"] is True
        assert result["queue_length"] == 1
        assert result["queue"][0]["holder"] == "claude-forge"

    def test_medium_allows_two(self):
        tool_checkout(
            handle="claude-forge",
            command_hint="ruff check src/",
        )
        result = tool_checkout(
            handle="gemini-scout",
            command_hint="git commit -m 'fix'",
        )
        assert result["cleared"] is True

    def test_medium_blocks_at_three(self):
        tool_checkout(handle="claude-forge", command_hint="ruff check src/")
        tool_checkout(handle="gemini-scout", command_hint="git commit -m 'fix'")
        result = tool_checkout(
            handle="codex-bolt",
            command_hint="pyright",
        )
        assert result["cleared"] is False
        assert result["wait"] is True

    def test_weight_override(self):
        result = tool_checkout(
            handle="claude-forge",
            command_hint="some unknown command",
            weight="heavy",
        )
        assert result["weight"] == "heavy"
        assert result["cleared"] is True


class TestToolCheckin:
    def test_basic_checkin(self):
        co = tool_checkout(
            handle="claude-forge",
            command_hint="pytest tests/ -v",
        )
        result = tool_checkin(co["checkout_id"])
        assert result["released"] is True
        assert result["handle"] == "claude-forge"

    def test_checkin_frees_lane(self):
        co = tool_checkout(
            handle="claude-forge",
            command_hint="pytest tests/ -v",
        )
        tool_checkin(co["checkout_id"])
        # Lane should be free now
        result = tool_checkout(
            handle="gemini-scout",
            command_hint="pytest mcp/ -v",
        )
        assert result["cleared"] is True

    def test_checkin_empty_id(self):
        result = tool_checkin("")
        assert result["released"] is True
        assert "light" in result.get("note", "").lower()

    def test_checkin_already_released(self):
        result = tool_checkin("nonexistent")
        assert result["released"] is True


class TestToolQueue:
    def test_empty_queue(self):
        q = tool_queue()
        assert q["active_checkouts"] == 0
        assert q["heavy_lane"]["occupied"] == 0
        assert q["medium_lane"]["occupied"] == 0

    def test_queue_shows_checkouts(self):
        tool_checkout(
            handle="claude-forge",
            command_hint="pytest tests/ -v",
        )
        tool_checkout(
            handle="gemini-scout",
            command_hint="ruff check src/",
        )
        q = tool_queue()
        assert q["active_checkouts"] == 2
        assert q["heavy_lane"]["occupied"] == 1
        assert q["medium_lane"]["occupied"] == 1

    def test_queue_after_checkin(self):
        co = tool_checkout(
            handle="claude-forge",
            command_hint="pytest tests/ -v",
        )
        tool_checkin(co["checkout_id"])
        q = tool_queue()
        assert q["active_checkouts"] == 0


class TestAutoExpiry:
    def test_expired_checkout_not_active(self):
        co = ToolCheckout(
            checkout_id="old",
            handle="claude-forge",
            tool="bash",
            command_hint="pytest tests/",
            weight="heavy",
            timestamp=time.time() - CHECKOUT_TTL_SECONDS - 60,
        )
        assert co.is_expired
        assert not co.is_active

    def test_expired_checkout_frees_lane(
        self, tmp_path, monkeypatch,
    ):
        """Expired checkouts should not block new ones."""
        claims_file = tmp_path / "expired_claims.jsonl"
        monkeypatch.setenv("ORGANVM_CLAIMS_FILE", str(claims_file))

        # Write an old checkout event
        old_event = {
            "event_type": "tool.checkout",
            "checkout_id": "old1",
            "handle": "claude-forge",
            "tool": "bash",
            "command_hint": "pytest old/",
            "weight": "heavy",
            "timestamp": time.time() - CHECKOUT_TTL_SECONDS - 60,
        }
        claims_file.write_text(json.dumps(old_event) + "\n")

        # New heavy checkout should clear
        result = tool_checkout(
            handle="gemini-scout",
            command_hint="pytest new/ -v",
        )
        assert result["cleared"] is True


class TestBuildActiveCheckouts:
    def test_empty(self):
        assert _build_active_checkouts([]) == []

    def test_checkout_creates_entry(self):
        events = [
            {
                "event_type": "tool.checkout",
                "checkout_id": "co1",
                "handle": "claude-forge",
                "tool": "bash",
                "command_hint": "pytest",
                "weight": "heavy",
                "timestamp": time.time(),
            },
        ]
        result = _build_active_checkouts(events)
        assert len(result) == 1
        assert result[0].handle == "claude-forge"

    def test_checkin_releases(self):
        now = time.time()
        events = [
            {
                "event_type": "tool.checkout",
                "checkout_id": "co1",
                "handle": "claude-forge",
                "tool": "bash",
                "command_hint": "pytest",
                "weight": "heavy",
                "timestamp": now,
            },
            {
                "event_type": "tool.checkin",
                "checkout_id": "co1",
                "timestamp": now + 30,
            },
        ]
        result = _build_active_checkouts(events)
        assert len(result) == 0
