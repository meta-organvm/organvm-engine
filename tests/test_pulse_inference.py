"""Tests for inference bridge, advisories, default policies, and related CLI."""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

# ---------------------------------------------------------------------------
# InferenceSummary
# ---------------------------------------------------------------------------

class TestInferenceSummary:
    def test_default_zeroed(self):
        from organvm_engine.pulse.inference_bridge import InferenceSummary

        s = InferenceSummary()
        assert s.tension_count == 0
        assert s.cluster_count == 0
        assert s.inference_score == 0.0
        assert s.tensions == []
        assert s.clusters == []

    def test_to_dict_roundtrip(self):
        from organvm_engine.pulse.inference_bridge import InferenceSummary

        s = InferenceSummary(
            tensions=[{"type": "orphan", "entity_ids": ["ent1"], "severity": 0.5}],
            tension_count=1,
            clusters=[{"entity_ids": ["e1", "e2"], "cohesion": 0.8, "size": 2}],
            cluster_count=1,
            overcoupled_entities=["e3"],
            orphaned_entities=["ent1"],
            naming_conflicts=["slug conflict"],
            inference_score=0.85,
        )
        d = s.to_dict()
        assert d["tension_count"] == 1
        assert d["cluster_count"] == 1
        assert d["inference_score"] == 0.85
        assert len(d["tensions"]) == 1
        assert len(d["clusters"]) == 1
        assert d["overcoupled_entities"] == ["e3"]
        assert d["orphaned_entities"] == ["ent1"]


class TestInferenceScore:
    def test_no_tensions(self):
        from organvm_engine.pulse.inference_bridge import _compute_inference_score

        assert _compute_inference_score(0, 100) == 1.0

    def test_some_tensions(self):
        from organvm_engine.pulse.inference_bridge import _compute_inference_score

        score = _compute_inference_score(10, 100)
        assert 0.0 < score < 1.0
        assert score == pytest.approx(0.9)

    def test_no_entities(self):
        from organvm_engine.pulse.inference_bridge import _compute_inference_score

        assert _compute_inference_score(0, 0) == 1.0

    def test_many_tensions_clamps(self):
        from organvm_engine.pulse.inference_bridge import _compute_inference_score

        score = _compute_inference_score(200, 100)
        assert score == 0.0


class TestRunInference:
    def test_returns_zeroed_when_ontologia_unavailable(self, monkeypatch):
        """If ontologia can't be imported, return zeroed summary."""
        # Simulate ImportError
        import builtins

        from organvm_engine.pulse import inference_bridge

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("ontologia"):
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = inference_bridge.run_inference()
        assert result.tension_count == 0
        assert result.inference_score == 0.0


class TestBlastRadius:
    def test_returns_error_when_unavailable(self, monkeypatch):
        """blast_radius returns error dict when ontologia unavailable."""
        import builtins

        from organvm_engine.pulse import inference_bridge

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("ontologia"):
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = inference_bridge.blast_radius("some-entity")
        assert "error" in result


# ---------------------------------------------------------------------------
# Advisory
# ---------------------------------------------------------------------------

class TestAdvisory:
    def test_to_dict_from_dict(self):
        from organvm_engine.pulse.advisories import Advisory

        adv = Advisory(
            advisory_id="abc123",
            policy_id="flag-stale",
            action="flag",
            entity_id="ORGAN-I/repo-1",
            entity_name="repo-1",
            description="Flag stale: repo-1",
            severity="warning",
            timestamp="2026-03-13T00:00:00",
            evidence={"is_stale": True},
        )
        d = adv.to_dict()
        roundtripped = Advisory.from_dict(d)
        assert roundtripped.advisory_id == "abc123"
        assert roundtripped.policy_id == "flag-stale"
        assert roundtripped.severity == "warning"
        assert not roundtripped.acknowledged

    def test_default_acknowledged_false(self):
        from organvm_engine.pulse.advisories import Advisory

        adv = Advisory.from_dict({"advisory_id": "x", "policy_id": "y",
                                   "action": "flag", "entity_id": "e",
                                   "entity_name": "n", "description": "d",
                                   "severity": "info", "timestamp": "t"})
        assert adv.acknowledged is False


class TestAdvisoryId:
    def test_deterministic(self):
        from organvm_engine.pulse.advisories import _make_advisory_id

        id1 = _make_advisory_id("policy-a", "entity-1")
        id2 = _make_advisory_id("policy-a", "entity-1")
        assert id1 == id2
        assert len(id1) == 12

    def test_different_inputs(self):
        from organvm_engine.pulse.advisories import _make_advisory_id

        id1 = _make_advisory_id("policy-a", "entity-1")
        id2 = _make_advisory_id("policy-b", "entity-1")
        assert id1 != id2


class TestSeverityMapping:
    def test_flag_is_warning(self):
        from organvm_engine.pulse.advisories import _severity_from_action

        assert _severity_from_action("flag") == "warning"

    def test_promote_is_info(self):
        from organvm_engine.pulse.advisories import _severity_from_action

        assert _severity_from_action("promote") == "info"

    def test_unknown_is_info(self):
        from organvm_engine.pulse.advisories import _severity_from_action

        assert _severity_from_action("zzzz") == "info"

    def test_deprecate_is_critical(self):
        from organvm_engine.pulse.advisories import _severity_from_action

        assert _severity_from_action("deprecate") == "critical"


class TestBuildRepoState:
    def test_basic(self):
        from organvm_engine.pulse.advisories import _build_repo_state

        state = _build_repo_state({
            "promotion_status": "CANDIDATE",
            "ci_workflow": "ci.yml",
            "platinum_status": True,
            "implementation_status": "ACTIVE",
            "last_validated": "2020-01-01T00:00:00+00:00",
        })
        assert state["promotion_status"] == "CANDIDATE"
        assert state["ci_workflow"] is True
        assert state["is_stale"] is True  # 2020 is > 30 days ago

    def test_not_stale(self):
        from datetime import datetime, timezone

        from organvm_engine.pulse.advisories import _build_repo_state

        recent = datetime.now(timezone.utc).isoformat()
        state = _build_repo_state({"last_validated": recent})
        assert state["is_stale"] is False


class TestStoreAndRead:
    def test_store_and_read(self, tmp_path, monkeypatch):
        from organvm_engine.pulse import advisories

        monkeypatch.setattr(
            advisories, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        from organvm_engine.pulse.advisories import Advisory, read_advisories, store_advisories

        advs = [
            Advisory(
                advisory_id="aaa",
                policy_id="test",
                action="flag",
                entity_id="e1",
                entity_name="test-repo",
                description="Test advisory",
                severity="info",
                timestamp="2026-03-13T00:00:00",
            ),
        ]
        store_advisories(advs)

        result = read_advisories()
        assert len(result) == 1
        assert result[0].advisory_id == "aaa"

    def test_acknowledge(self, tmp_path, monkeypatch):
        from organvm_engine.pulse import advisories

        monkeypatch.setattr(
            advisories, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        from organvm_engine.pulse.advisories import (
            Advisory,
            acknowledge_advisory,
            read_advisories,
            store_advisories,
        )

        store_advisories([
            Advisory(
                advisory_id="bbb",
                policy_id="test",
                action="flag",
                entity_id="e2",
                entity_name="test-repo-2",
                description="Test advisory 2",
                severity="warning",
                timestamp="2026-03-13T00:00:00",
            ),
        ])

        assert acknowledge_advisory("bbb") is True
        result = read_advisories()
        assert result[0].acknowledged is True

    def test_acknowledge_not_found(self, tmp_path, monkeypatch):
        from organvm_engine.pulse import advisories

        monkeypatch.setattr(
            advisories, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        from organvm_engine.pulse.advisories import acknowledge_advisory

        assert acknowledge_advisory("nonexistent") is False

    def test_unacked_only_filter(self, tmp_path, monkeypatch):
        from organvm_engine.pulse import advisories

        monkeypatch.setattr(
            advisories, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        from organvm_engine.pulse.advisories import (
            Advisory,
            acknowledge_advisory,
            read_advisories,
            store_advisories,
        )

        store_advisories([
            Advisory("c1", "p1", "flag", "e1", "r1", "d1", "info", "t1"),
            Advisory("c2", "p2", "flag", "e2", "r2", "d2", "info", "t2"),
        ])
        acknowledge_advisory("c1")

        all_result = read_advisories()
        assert len(all_result) == 2

        unacked = read_advisories(unacked_only=True)
        assert len(unacked) == 1
        assert unacked[0].advisory_id == "c2"

    def test_empty_file(self, tmp_path, monkeypatch):
        from organvm_engine.pulse import advisories

        monkeypatch.setattr(
            advisories, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        from organvm_engine.pulse.advisories import read_advisories

        assert read_advisories() == []


# ---------------------------------------------------------------------------
# Default policies
# ---------------------------------------------------------------------------

class TestDefaultPolicies:
    def test_policies_load(self):
        from organvm_engine.pulse.default_policies import DEFAULT_POLICIES

        # If ontologia is installed, should have 6 policies
        # If not, empty list (graceful degradation)
        assert isinstance(DEFAULT_POLICIES, list)

    def test_policies_have_ids(self):
        from organvm_engine.pulse.default_policies import DEFAULT_POLICIES

        if not DEFAULT_POLICIES:
            pytest.skip("ontologia not available")
        ids = {p.policy_id for p in DEFAULT_POLICIES}
        assert "auto-promote-candidate" in ids
        assert "flag-orphan" in ids
        assert "flag-stale" in ids

    def test_auto_promote_evaluates(self):
        from organvm_engine.pulse.default_policies import DEFAULT_POLICIES

        if not DEFAULT_POLICIES:
            pytest.skip("ontologia not available")

        promote = next(p for p in DEFAULT_POLICIES if p.policy_id == "auto-promote-candidate")
        state = {
            "promotion_status": "CANDIDATE",
            "ci_workflow": True,
            "platinum_status": True,
            "implementation_status": "ACTIVE",
        }
        assert promote.evaluate(state) is True

    def test_auto_promote_rejects_non_candidate(self):
        from organvm_engine.pulse.default_policies import DEFAULT_POLICIES

        if not DEFAULT_POLICIES:
            pytest.skip("ontologia not available")

        promote = next(p for p in DEFAULT_POLICIES if p.policy_id == "auto-promote-candidate")
        state = {
            "promotion_status": "PUBLIC_PROCESS",
            "ci_workflow": True,
            "platinum_status": True,
            "implementation_status": "ACTIVE",
        }
        assert promote.evaluate(state) is False


# ---------------------------------------------------------------------------
# evaluate_all_policies
# ---------------------------------------------------------------------------

class TestEvaluateAllPolicies:
    def test_with_minimal_registry(self, tmp_path, monkeypatch):
        """Test policy evaluation against a minimal registry fixture."""
        from organvm_engine.pulse import advisories as adv_mod
        from organvm_engine.pulse.advisories import evaluate_all_policies

        monkeypatch.setattr(
            adv_mod, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        # Provide a minimal registry with one CANDIDATE repo that has CI+platinum
        registry = {
            "version": "2.0",
            "organs": {
                "ORGAN-I": {
                    "name": "Theoria",
                    "repositories": [
                        {
                            "name": "test-repo",
                            "promotion_status": "CANDIDATE",
                            "ci_workflow": "ci.yml",
                            "platinum_status": True,
                            "implementation_status": "ACTIVE",
                            "last_validated": "2026-03-13T00:00:00",
                        },
                    ],
                },
            },
        }

        import organvm_engine.registry.loader as loader_mod

        monkeypatch.setattr(loader_mod, "load_registry", lambda *a, **kw: registry)

        result = evaluate_all_policies()
        # Should find auto-promote-candidate if policies loaded
        from organvm_engine.pulse.default_policies import DEFAULT_POLICIES

        if DEFAULT_POLICIES:
            promote_advs = [a for a in result if a.policy_id == "auto-promote-candidate"]
            assert len(promote_advs) == 1
            assert promote_advs[0].entity_name == "test-repo"


# ---------------------------------------------------------------------------
# AMMOI inference fields
# ---------------------------------------------------------------------------

class TestAmmoiInferenceFields:
    def test_new_fields_in_dataclass(self):
        from organvm_engine.pulse.ammoi import AMMOI

        ammoi = AMMOI()
        assert ammoi.cluster_count == 0
        assert ammoi.orphan_count == 0
        assert ammoi.overcoupled_count == 0
        assert ammoi.inference_score == 0.0

    def test_to_dict_includes_inference(self):
        from organvm_engine.pulse.ammoi import AMMOI

        ammoi = AMMOI(cluster_count=3, orphan_count=2, overcoupled_count=1, inference_score=0.9)
        d = ammoi.to_dict()
        assert d["cluster_count"] == 3
        assert d["orphan_count"] == 2
        assert d["overcoupled_count"] == 1
        assert d["inference_score"] == 0.9

    def test_from_dict_reads_inference(self):
        from organvm_engine.pulse.ammoi import AMMOI

        d = {
            "cluster_count": 5,
            "orphan_count": 3,
            "overcoupled_count": 2,
            "inference_score": 0.75,
        }
        ammoi = AMMOI.from_dict(d)
        assert ammoi.cluster_count == 5
        assert ammoi.orphan_count == 3
        assert ammoi.overcoupled_count == 2
        assert ammoi.inference_score == 0.75

    def test_from_dict_backwards_compatible(self):
        """Old AMMOI data without inference fields should load fine."""
        from organvm_engine.pulse.ammoi import AMMOI

        d = {
            "timestamp": "2026-03-13T00:00:00",
            "system_density": 0.5,
            "total_entities": 100,
        }
        ammoi = AMMOI.from_dict(d)
        assert ammoi.cluster_count == 0
        assert ammoi.inference_score == 0.0


class TestCompressedText:
    def test_includes_cluster_count(self):
        from organvm_engine.pulse.ammoi import AMMOI, _build_compressed_text

        ammoi = AMMOI(
            system_density=0.5,
            active_edges=50,
            tension_count=3,
            cluster_count=2,
            event_frequency_24h=10,
        )
        text = _build_compressed_text(ammoi)
        assert "C:2" in text
        assert "T:3" in text


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class TestEventTypes:
    def test_inference_completed_exists(self):
        from organvm_engine.pulse.types import (
            ALL_ENGINE_EVENT_TYPES,
            INFERENCE_COMPLETED,
        )

        assert INFERENCE_COMPLETED == "pulse.inference_completed"
        assert INFERENCE_COMPLETED in ALL_ENGINE_EVENT_TYPES

    def test_advisory_generated_exists(self):
        from organvm_engine.pulse.types import (
            ADVISORY_GENERATED,
            ALL_ENGINE_EVENT_TYPES,
        )

        assert ADVISORY_GENERATED == "pulse.advisory_generated"
        assert ADVISORY_GENERATED in ALL_ENGINE_EVENT_TYPES

    def test_edges_synced_exists(self):
        from organvm_engine.pulse.types import (
            ALL_ENGINE_EVENT_TYPES,
            EDGES_SYNCED,
        )

        assert EDGES_SYNCED == "pulse.edges_synced"
        assert EDGES_SYNCED in ALL_ENGINE_EVENT_TYPES


# ---------------------------------------------------------------------------
# SessionBriefing enrichment
# ---------------------------------------------------------------------------

class TestSessionBriefingEnrichment:
    def test_new_fields_exist(self):
        from organvm_engine.pulse.continuity import SessionBriefing

        briefing = SessionBriefing()
        assert briefing.active_tensions == []
        assert briefing.pending_advisories == []

    def test_to_dict_includes_new_fields(self):
        from organvm_engine.pulse.continuity import SessionBriefing

        briefing = SessionBriefing(
            active_tensions=[{"type": "orphan", "severity": 0.5}],
            pending_advisories=[{"action": "flag", "entity_name": "test"}],
        )
        d = briefing.to_dict()
        assert len(d["active_tensions"]) == 1
        assert len(d["pending_advisories"]) == 1


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------

class TestCLITensions:
    def test_tensions_json(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_tensions
        from organvm_engine.pulse.inference_bridge import InferenceSummary

        def mock_inference(*a, **kw):
            return InferenceSummary(
                tensions=[{"type": "orphan", "entity_ids": ["e1"], "severity": 0.5,
                           "description": "test orphan"}],
                tension_count=1,
                orphaned_entities=["e1"],
                inference_score=0.9,
            )

        import organvm_engine.pulse.inference_bridge as bridge

        monkeypatch.setattr(bridge, "run_inference", mock_inference)

        args = Namespace(json=True, workspace=None)
        ret = cmd_pulse_tensions(args)
        assert ret == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["tension_count"] == 1

    def test_tensions_human(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_tensions
        from organvm_engine.pulse.inference_bridge import InferenceSummary

        def mock_inference(*a, **kw):
            return InferenceSummary(tension_count=0)

        import organvm_engine.pulse.inference_bridge as bridge

        monkeypatch.setattr(bridge, "run_inference", mock_inference)

        args = Namespace(json=False, workspace=None)
        ret = cmd_pulse_tensions(args)
        assert ret == 0
        assert "No tensions" in capsys.readouterr().out


class TestCLIClusters:
    def test_clusters_json(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_clusters
        from organvm_engine.pulse.inference_bridge import InferenceSummary

        def mock_inference(*a, **kw):
            return InferenceSummary(
                clusters=[{"entity_ids": ["e1", "e2"], "cohesion": 0.9, "size": 2}],
                cluster_count=1,
            )

        import organvm_engine.pulse.inference_bridge as bridge

        monkeypatch.setattr(bridge, "run_inference", mock_inference)

        args = Namespace(json=True, workspace=None)
        ret = cmd_pulse_clusters(args)
        assert ret == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["count"] == 1

    def test_no_clusters(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_clusters
        from organvm_engine.pulse.inference_bridge import InferenceSummary

        def mock_inference(*a, **kw):
            return InferenceSummary()

        import organvm_engine.pulse.inference_bridge as bridge

        monkeypatch.setattr(bridge, "run_inference", mock_inference)

        args = Namespace(json=False, workspace=None)
        ret = cmd_pulse_clusters(args)
        assert ret == 0
        assert "No clusters" in capsys.readouterr().out


class TestCLIAdvisories:
    def test_advisories_json(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.pulse import advisories as adv_mod
        from organvm_engine.pulse.advisories import Advisory, store_advisories

        monkeypatch.setattr(
            adv_mod, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        store_advisories([
            Advisory("x1", "test", "flag", "e1", "repo-1", "desc", "info", "t1"),
        ])

        from organvm_engine.cli.cmd_pulse import cmd_pulse_advisories

        args = Namespace(json=True, ack_id=None, limit=20, unacked=False)
        ret = cmd_pulse_advisories(args)
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1

    def test_ack_advisory(self, tmp_path, monkeypatch, capsys):
        from organvm_engine.pulse import advisories as adv_mod
        from organvm_engine.pulse.advisories import Advisory, store_advisories

        monkeypatch.setattr(
            adv_mod, "_advisories_path",
            lambda: tmp_path / "advisories.jsonl",
        )

        store_advisories([
            Advisory("y1", "test", "flag", "e1", "repo-1", "desc", "info", "t1"),
        ])

        from organvm_engine.cli.cmd_pulse import cmd_pulse_advisories

        args = Namespace(json=False, ack_id="y1", limit=20, unacked=False)
        ret = cmd_pulse_advisories(args)
        assert ret == 0
        assert "acknowledged" in capsys.readouterr().out


class TestCLIBlast:
    def test_blast_json_error(self, monkeypatch, capsys):
        import organvm_engine.pulse.inference_bridge as bridge
        from organvm_engine.cli.cmd_pulse import cmd_pulse_blast

        monkeypatch.setattr(
            bridge, "blast_radius",
            lambda e: {"error": "ontologia not available"},
        )

        args = Namespace(json=True, entity="test-entity")
        ret = cmd_pulse_blast(args)
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert "error" in data

    def test_blast_human_error(self, monkeypatch, capsys):
        import organvm_engine.pulse.inference_bridge as bridge
        from organvm_engine.cli.cmd_pulse import cmd_pulse_blast

        monkeypatch.setattr(
            bridge, "blast_radius",
            lambda e: {"error": "not found"},
        )

        args = Namespace(json=False, entity="test-entity")
        ret = cmd_pulse_blast(args)
        assert ret == 1  # error
        assert "Error" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Pulse __init__ exports
# ---------------------------------------------------------------------------

class TestPulseExports:
    def test_inference_bridge_exported(self):
        from organvm_engine.pulse import InferenceSummary, blast_radius, run_inference

        assert InferenceSummary is not None
        assert callable(run_inference)
        assert callable(blast_radius)

    def test_advisory_exported(self):
        from organvm_engine.pulse import (
            Advisory,
            acknowledge_advisory,
            evaluate_all_policies,
            read_advisories,
            store_advisories,
        )

        assert Advisory is not None
        assert callable(evaluate_all_policies)
        assert callable(store_advisories)
        assert callable(read_advisories)
        assert callable(acknowledge_advisory)


# ---------------------------------------------------------------------------
# Edge bridge
# ---------------------------------------------------------------------------

class TestEdgeSyncResult:
    def test_default_zeroed(self):
        from organvm_engine.pulse.edge_bridge import EdgeSyncResult

        r = EdgeSyncResult()
        assert r.created == 0
        assert r.skipped == 0
        assert r.unresolved == 0

    def test_to_dict(self):
        from organvm_engine.pulse.edge_bridge import EdgeSyncResult

        r = EdgeSyncResult(created=5, skipped=3, unresolved=2)
        d = r.to_dict()
        assert d["created"] == 5
        assert d["skipped"] == 3
        assert d["unresolved"] == 2
        assert d["total_seed_edges"] == 10


class TestResolveNode:
    def test_exact_match(self):
        from organvm_engine.pulse.edge_bridge import _resolve_seed_node

        mapping = {"ivviiviivvi/repo-a": "uid-1"}
        assert _resolve_seed_node("ivviiviivvi/repo-a", mapping) == "uid-1"

    def test_repo_part_fallback(self):
        from organvm_engine.pulse.edge_bridge import _resolve_seed_node

        mapping = {"repo-a": "uid-1"}
        assert _resolve_seed_node("ivviiviivvi/repo-a", mapping) == "uid-1"

    def test_no_match(self):
        from organvm_engine.pulse.edge_bridge import _resolve_seed_node

        mapping = {"other-repo": "uid-2"}
        assert _resolve_seed_node("org/missing", mapping) is None


class TestSeedToRelationMapping:
    def test_mapping_values(self):
        from organvm_engine.pulse.edge_bridge import _SEED_TO_RELATION

        assert _SEED_TO_RELATION["produces"] == "produces_for"
        assert _SEED_TO_RELATION["consumes"] == "consumes_from"
        assert _SEED_TO_RELATION["subscribes"] == "subscribes_to"
        assert _SEED_TO_RELATION["dependency"] == "depends_on"


class TestSyncSeedEdgesImportFail:
    def test_returns_empty_when_unavailable(self, monkeypatch):
        import builtins

        from organvm_engine.pulse import edge_bridge

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("ontologia"):
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = edge_bridge.sync_seed_edges()
        assert result.created == 0
        assert result.unresolved == 0


class TestCLIEdges:
    def test_edges_json(self, monkeypatch, capsys):
        from organvm_engine.cli.cmd_pulse import cmd_pulse_edges

        # Mock ontologia store
        class MockEdge:
            def __init__(self, rel=None, pid=None, cid=None, sid=None, tid=None, rt=None):
                self.parent_id = pid or ""
                self.child_id = cid or ""
                self.source_id = sid or ""
                self.target_id = tid or ""
                self.relation_type = rt or ""

            def is_active(self, at=None):
                return True

        class MockEI:
            def all_hierarchy_edges(self):
                return [MockEdge(pid="o1", cid="r1")]

            def all_relation_edges(self):
                return [MockEdge(sid="r1", tid="r2", rt="produces_for")]

        class MockStore:
            edge_index = MockEI()

            def list_entities(self, entity_type=None):
                return []


        # Patch the import inside the function
        import sys as _sys
        mock_ontologia = type(_sys)("ontologia.registry.store")
        mock_ontologia.open_store = MockStore
        monkeypatch.setitem(_sys.modules, "ontologia.registry.store", mock_ontologia)

        mock_identity = type(_sys)("ontologia.entity.identity")
        mock_identity.EntityType = type("ET", (), {"ORGAN": "organ"})()
        monkeypatch.setitem(_sys.modules, "ontologia.entity.identity", mock_identity)

        args = Namespace(json=True, edges_action=None, workspace=None)
        ret = cmd_pulse_edges(args)
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data["hierarchy_edges"] == 1
        assert data["relation_edges"] == 1

    def test_edges_sync_json(self, monkeypatch, capsys):
        import organvm_engine.pulse.edge_bridge as bridge
        from organvm_engine.cli.cmd_pulse import cmd_pulse_edges
        from organvm_engine.pulse.edge_bridge import EdgeSyncResult

        monkeypatch.setattr(
            bridge, "sync_seed_edges",
            lambda *a, **kw: EdgeSyncResult(created=3, skipped=1, unresolved=2),
        )

        args = Namespace(json=True, edges_action="sync", workspace=None)
        ret = cmd_pulse_edges(args)
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data["created"] == 3
