"""Tests for workspace reproduction from superprojects."""

from unittest.mock import MagicMock, patch

import pytest

from organvm_engine.git.reproduce import clone_organ, reproduce_workspace


class TestCloneOrgan:
    def test_unknown_organ_raises(self):
        with pytest.raises(ValueError, match="Unknown organ"):
            clone_organ("NONEXISTENT")

    def test_target_exists_returns_error(self, tmp_path):
        target = tmp_path / "organvm-i-theoria"
        target.mkdir()
        result = clone_organ("I", target=target)
        assert "error" in result
        assert "already exists" in result["error"]

    @patch("organvm_engine.git.reproduce._run_git")
    @patch("organvm_engine.git.reproduce.subprocess.run")
    def test_shallow_flag_in_args(self, mock_run, mock_run_git, tmp_path):
        target = tmp_path / "organvm-i-theoria"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_git.return_value = MagicMock(returncode=0, stdout="", stderr="")
        clone_organ("I", target=target, shallow=True)
        args = mock_run.call_args[0][0]
        assert "--depth" in args
        assert "1" in args

    @patch("organvm_engine.git.reproduce.subprocess.run")
    def test_clone_failure_captured(self, mock_run, tmp_path):
        target = tmp_path / "organvm-i-theoria"
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: repo not found")
        result = clone_organ("I", target=target)
        assert "error" in result
        assert "Clone failed" in result["error"]


class TestReproduceWorkspace:
    @patch("organvm_engine.git.reproduce._run_git")
    @patch("organvm_engine.git.reproduce.subprocess.run")
    def test_creates_structure(self, mock_run, mock_run_git, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_git.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = reproduce_workspace(tmp_path / "ws", organs=["I"])
        assert "organvm-i-theoria" in result["cloned_organs"]
        assert result["errors"] == []

    @patch("organvm_engine.git.reproduce._run_git")
    @patch("organvm_engine.git.reproduce.subprocess.run")
    def test_filters_by_organ(self, mock_run, mock_run_git, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_git.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = reproduce_workspace(tmp_path / "ws", organs=["I"])
        assert len(result["cloned_organs"]) == 1
