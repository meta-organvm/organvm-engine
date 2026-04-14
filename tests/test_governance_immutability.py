"""Tests for IMMUTABILITY predicate enforcement (SYS-082).

Validates governance-amendments.jsonl hash chain integrity
and constitutional lock verification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from organvm_engine.governance.immutability import (
    load_amendments,
    record_amendment,
    validate_constitutional_locks,
)


def _make_rules(tmp_path: Path, locked_paths: list[str] | None = None) -> Path:
    """Create a minimal governance-rules.json in tmp_path."""
    rules = {
        "version": "3.0",
        "_constitutional_locks": {
            "locked_paths": locked_paths or ["dictums.axioms"],
            "lock_policy": "append_only_amend_never_delete",
            "amendment_log": "governance-amendments.jsonl",
        },
        "dictums": {
            "axioms": [
                {"id": "AX-1", "name": "Test Axiom", "statement": "Test."}
            ]
        },
        "dependency_rules": {
            "no_circular_dependencies": True,
            "no_back_edges": True,
        },
    }
    path = tmp_path / "governance-rules.json"
    path.write_text(json.dumps(rules, indent=2), encoding="utf-8")
    return path


def _make_genesis(tmp_path: Path, rules_path: Path) -> Path:
    """Create a genesis amendment entry."""
    import hashlib

    content = rules_path.read_bytes()
    file_hash = "sha256:" + hashlib.sha256(content).hexdigest()

    genesis = {
        "sequence": 0,
        "timestamp": "2026-04-14T00:00:00Z",
        "author": "test",
        "field_path": "__genesis__",
        "operation": "GENESIS",
        "old_value_hash": "sha256:" + "0" * 64,
        "new_value_hash": file_hash,
        "justification": "Test genesis.",
        "prev_hash": "sha256:" + "0" * 64,
    }
    to_hash = {k: v for k, v in genesis.items() if k != "hash"}
    canonical = json.dumps(to_hash, sort_keys=True, separators=(",", ":"))
    genesis["hash"] = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    amendments_path = tmp_path / "governance-amendments.jsonl"
    amendments_path.write_text(json.dumps(genesis) + "\n", encoding="utf-8")
    return amendments_path


class TestGenesisAmendment:
    def test_genesis_created(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        amendments_path = _make_genesis(tmp_path, rules_path)
        entries = load_amendments(amendments_path)
        assert len(entries) == 1
        assert entries[0]["operation"] == "GENESIS"
        assert entries[0]["sequence"] == 0

    def test_genesis_validates(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        amendments_path = _make_genesis(tmp_path, rules_path)
        valid, errors = validate_constitutional_locks(rules_path, amendments_path)
        assert valid, f"Validation errors: {errors}"


class TestTamperingDetection:
    def test_locked_path_missing_detected(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path, locked_paths=["nonexistent.path"])
        amendments_path = _make_genesis(tmp_path, rules_path)
        valid, errors = validate_constitutional_locks(rules_path, amendments_path)
        assert not valid
        assert any("not found" in e for e in errors)

    def test_no_amendments_file_detected(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        valid, errors = validate_constitutional_locks(
            rules_path, tmp_path / "nonexistent.jsonl"
        )
        assert not valid
        assert any("No amendment log" in e for e in errors)


class TestChainIntegrity:
    def test_chain_with_three_amendments(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        amendments_path = _make_genesis(tmp_path, rules_path)

        # Record two more amendments
        record_amendment(
            rules_path, amendments_path,
            "dictums.axioms", "old1", "new1",
            "First amendment", "test", "EXTEND",
        )
        record_amendment(
            rules_path, amendments_path,
            "dictums.axioms", "new1", "new2",
            "Second amendment", "test", "AMEND",
        )

        entries = load_amendments(amendments_path)
        assert len(entries) == 3

        valid, errors = validate_constitutional_locks(rules_path, amendments_path)
        assert valid, f"Chain errors: {errors}"

    def test_corrupted_hash_detected(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        amendments_path = _make_genesis(tmp_path, rules_path)

        # Corrupt the genesis hash
        entries = load_amendments(amendments_path)
        entries[0]["hash"] = "sha256:" + "f" * 64
        amendments_path.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n",
            encoding="utf-8",
        )

        valid, errors = validate_constitutional_locks(rules_path, amendments_path)
        assert not valid
        assert any("hash mismatch" in e for e in errors)


class TestAmendmentRecording:
    def test_records_old_and_new_hashes(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        amendments_path = _make_genesis(tmp_path, rules_path)

        entry = record_amendment(
            rules_path, amendments_path,
            "dictums.axioms", ["old"], ["new"],
            "Test", "test",
        )
        assert entry["old_value_hash"].startswith("sha256:")
        assert entry["new_value_hash"].startswith("sha256:")
        assert entry["old_value_hash"] != entry["new_value_hash"]

    def test_sequence_increments(self, tmp_path: Path) -> None:
        rules_path = _make_rules(tmp_path)
        amendments_path = _make_genesis(tmp_path, rules_path)

        e1 = record_amendment(
            rules_path, amendments_path, "x", 1, 2, "a", "test"
        )
        e2 = record_amendment(
            rules_path, amendments_path, "y", 3, 4, "b", "test"
        )
        assert e1["sequence"] == 1
        assert e2["sequence"] == 2


class TestNonLockedPaths:
    def test_non_locked_mutation_passes(self, tmp_path: Path) -> None:
        """Modifying a non-locked path should not cause validation failure."""
        rules_path = _make_rules(tmp_path, locked_paths=["dictums.axioms"])
        amendments_path = _make_genesis(tmp_path, rules_path)

        # Modify a non-locked field
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        rules["version"] = "4.0"
        rules_path.write_text(json.dumps(rules, indent=2), encoding="utf-8")

        valid, errors = validate_constitutional_locks(rules_path, amendments_path)
        assert valid, f"Non-locked mutation should pass: {errors}"
