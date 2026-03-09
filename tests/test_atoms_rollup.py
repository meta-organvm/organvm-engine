"""Tests for atoms/rollup.py — per-organ fanout from centralized pipeline outputs."""

import json
from pathlib import Path

from organvm_engine.atoms.rollup import (
    OrganRollup,
    build_rollups,
    load_repo_task_queue,
    load_rollup,
    organ_key_from_slug,
    write_rollups,
)

# ── organ_key_from_slug ──────────────────────────────────────────


class TestOrganKeyFromSlug:
    def test_known_organ(self):
        assert organ_key_from_slug("organvm-iii-ergon/some-repo") == "III"

    def test_meta(self):
        assert organ_key_from_slug("meta-organvm/engine") == "META"

    def test_personal(self):
        assert organ_key_from_slug("4444J99/portfolio") == "LIMINAL"

    def test_unknown(self):
        assert organ_key_from_slug("unknown/repo") is None

    def test_single_segment(self):
        assert organ_key_from_slug("just-name") is None

    def test_organ_i(self):
        assert organ_key_from_slug("organvm-i-theoria/some-engine") == "I"

    def test_organ_vii(self):
        assert organ_key_from_slug("organvm-vii-kerygma/profiles") == "VII"


# ── build_rollups ────────────────────────────────────────────────


def _write_jsonl(path: Path, items: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


class TestBuildRollups:
    def test_empty(self, tmp_path):
        rollups = build_rollups(tmp_path)
        assert rollups == {}

    def test_groups_by_organ(self, tmp_path):
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "engine"}, "status": "pending"},
            {"id": "t2", "project": {"organ": "III", "repo": "tool"}, "status": "done"},
            {"id": "t3", "project": {"organ": "I", "repo": "lib"}, "status": "done"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)

        rollups = build_rollups(tmp_path)
        assert "I" in rollups
        assert "III" in rollups
        assert rollups["I"].total_tasks == 2
        assert rollups["III"].total_tasks == 1

    def test_pending_by_repo(self, tmp_path):
        tasks = [
            {"id": "t1", "project": {"organ": "II", "repo": "art"}, "status": "pending",
             "title": "Fix art", "tags": ["art"]},
            {"id": "t2", "project": {"organ": "II", "repo": "art"}, "status": "todo",
             "title": "New art", "tags": ["creative"]},
            {"id": "t3", "project": {"organ": "II", "repo": "perf"}, "status": "done"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)

        rollups = build_rollups(tmp_path)
        r = rollups["II"]
        assert r.pending_tasks == 2
        assert r.completed_tasks == 1
        assert "art" in r.pending_by_repo
        assert len(r.pending_by_repo["art"]) == 2
        assert "perf" not in r.pending_by_repo

    def test_prompt_resolution(self, tmp_path):
        prompts = [
            {
                "id": "p1",
                "source": {"project_slug": "organvm-iii-ergon/tool-a"},
                "classification": {"prompt_type": "directive"},
            },
            {
                "id": "p2",
                "source": {"project_slug": "meta-organvm/engine"},
                "classification": {"prompt_type": "question"},
            },
        ]
        _write_jsonl(tmp_path / "annotated-prompts.jsonl", prompts)

        rollups = build_rollups(tmp_path)
        assert "III" in rollups
        assert rollups["III"].prompt_type_dist["directive"] == 1
        assert "META" in rollups
        assert rollups["META"].prompt_type_dist["question"] == 1

    def test_cross_organ_links(self, tmp_path):
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "eng"}, "status": "pending"},
        ]
        prompts = [
            {
                "id": "p1",
                "source": {"project_slug": "organvm-iii-ergon/tool"},
                "classification": {"prompt_type": "fix"},
            },
        ]
        links = [
            {"task_id": "t1", "prompt_id": "p1", "jaccard": 0.5,
             "shared_tags": ["python"], "shared_refs": []},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        _write_jsonl(tmp_path / "annotated-prompts.jsonl", prompts)
        _write_jsonl(tmp_path / "atom-links.jsonl", links)

        rollups = build_rollups(tmp_path)
        assert len(rollups["I"].cross_organ_links) == 1
        assert len(rollups["III"].cross_organ_links) == 1
        assert rollups["I"].cross_organ_links[0]["task_organ"] == "I"
        assert rollups["I"].cross_organ_links[0]["prompt_organ"] == "III"

    def test_missing_prompts_ok(self, tmp_path):
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "x"}, "status": "pending"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        # No prompts file
        rollups = build_rollups(tmp_path)
        assert rollups["I"].total_tasks == 1
        assert sum(rollups["I"].prompt_type_dist.values()) == 0

    def test_missing_links_ok(self, tmp_path):
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "x"}, "status": "pending"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        # No links file
        rollups = build_rollups(tmp_path)
        assert rollups["I"].cross_organ_links == []

    def test_skips_null_organ(self, tmp_path):
        """Tasks with None organ don't create a rollup entry."""
        tasks = [
            {"id": "t1", "project": {"organ": None, "repo": "x"}, "status": "pending"},
            {"id": "t2", "project": {"organ": "_root", "repo": "_global"}, "status": "pending"},
            {"id": "t3", "project": {}, "status": "done"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        rollups = build_rollups(tmp_path)
        assert rollups == {}

    def test_unattributed_repo(self, tmp_path):
        """Tasks with organ but None repo use '_unattributed'."""
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": None}, "status": "pending",
             "title": "Global task", "tags": []},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        rollups = build_rollups(tmp_path)
        assert "_unattributed" in rollups["I"].pending_by_repo

    def test_skips_empty_fingerprint(self, tmp_path):
        """SHA-256 of empty string excluded from fingerprint counts."""
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "x"}, "status": "pending",
             "domain_fingerprint": "e3b0c44298fc1c14b8a2e1d4"},
            {"id": "t2", "project": {"organ": "I", "repo": "x"}, "status": "pending",
             "domain_fingerprint": "fp:real-signal"},
        ]
        prompts = [
            {
                "id": "p1",
                "source": {"project_slug": "organvm-i-theoria/x"},
                "classification": {"prompt_type": "fix"},
                "domain_fingerprint": "e3b0c44298fc1c14b8a2e1d4",
            },
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        _write_jsonl(tmp_path / "annotated-prompts.jsonl", prompts)
        rollups = build_rollups(tmp_path)
        fps = rollups["I"].domain_fingerprints
        assert "fp:real-signal" in fps
        assert not any(k.startswith("e3b0c44298fc") for k in fps)

    def test_domain_fingerprints(self, tmp_path):
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "x"}, "status": "pending",
             "domain_fingerprint": "fp:python"},
            {"id": "t2", "project": {"organ": "I", "repo": "x"}, "status": "done",
             "domain_fingerprint": "fp:python"},
        ]
        prompts = [
            {
                "id": "p1",
                "source": {"project_slug": "organvm-i-theoria/x"},
                "classification": {"prompt_type": "fix"},
                "domain_fingerprint": "fp:rust",
            },
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)
        _write_jsonl(tmp_path / "annotated-prompts.jsonl", prompts)

        rollups = build_rollups(tmp_path)
        fps = rollups["I"].domain_fingerprints
        assert fps["fp:python"] == 2
        assert fps["fp:rust"] == 1


# ── write_rollups ────────────────────────────────────────────────


class TestWriteRollups:
    def _make_rollups(self):
        return {
            "I": OrganRollup(
                organ_key="I",
                organ_dir="organvm-i-theoria",
                registry_key="ORGAN-I",
                total_tasks=5,
                pending_tasks=2,
            ),
        }

    def test_correct_paths(self, tmp_path):
        organ_dir = tmp_path / "organvm-i-theoria"
        organ_dir.mkdir()
        rollups = self._make_rollups()
        paths = write_rollups(rollups, tmp_path, dry_run=False)
        assert len(paths) == 1
        assert paths[0].endswith(".atoms/organ-rollup.json")
        out = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        assert out["organ_key"] == "I"
        assert out["total_tasks"] == 5

    def test_dry_run(self, tmp_path):
        organ_dir = tmp_path / "organvm-i-theoria"
        organ_dir.mkdir()
        rollups = self._make_rollups()
        paths = write_rollups(rollups, tmp_path, dry_run=True)
        assert len(paths) == 1
        assert not Path(paths[0]).exists()

    def test_creates_dir(self, tmp_path):
        organ_dir = tmp_path / "organvm-i-theoria"
        organ_dir.mkdir()
        rollups = self._make_rollups()
        write_rollups(rollups, tmp_path, dry_run=False)
        assert (organ_dir / ".atoms").is_dir()

    def test_skips_missing_organ_dir(self, tmp_path):
        # Don't create the organ dir
        rollups = self._make_rollups()
        paths = write_rollups(rollups, tmp_path, dry_run=False)
        assert paths == []


# ── load_rollup ──────────────────────────────────────────────────


class TestLoadRollup:
    def test_exists(self, tmp_path):
        atoms_dir = tmp_path / ".atoms"
        atoms_dir.mkdir()
        data = {"organ_key": "I", "total_tasks": 10}
        (atoms_dir / "organ-rollup.json").write_text(
            json.dumps(data), encoding="utf-8",
        )
        result = load_rollup(tmp_path)
        assert result == data

    def test_missing(self, tmp_path):
        assert load_rollup(tmp_path) is None


# ── load_repo_task_queue ─────────────────────────────────────────


class TestLoadRepoTaskQueue:
    def test_found(self):
        rollup = {
            "pending_by_repo": {
                "my-repo": [
                    {"id": "t1", "title": "Fix bug", "status": "pending", "tags": ["fix"]},
                ],
            },
        }
        result = load_repo_task_queue(rollup, "my-repo")
        assert result is not None
        assert result["pending_count"] == 1
        assert result["tasks"][0]["id"] == "t1"

    def test_missing_repo(self):
        rollup = {"pending_by_repo": {"other": []}}
        assert load_repo_task_queue(rollup, "my-repo") is None


# ── CLI integration ──────────────────────────────────────────────


class TestCliFanout:
    def test_dry_run(self, tmp_path, capsys):
        tasks = [
            {"id": "t1", "project": {"organ": "I", "repo": "eng"}, "status": "pending",
             "title": "Do thing"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)

        # Create organ dir
        organ_dir = tmp_path / "workspace" / "organvm-i-theoria"
        organ_dir.mkdir(parents=True)

        import argparse

        from organvm_engine.cli.atoms import cmd_atoms_fanout

        args = argparse.Namespace(
            atoms_dir=str(tmp_path),
            workspace=str(tmp_path / "workspace"),
            write=False,
        )
        rc = cmd_atoms_fanout(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DRY RUN]" in out
        assert "I" in out
        # File should NOT exist
        assert not (organ_dir / ".atoms" / "organ-rollup.json").exists()

    def test_write(self, tmp_path, capsys):
        tasks = [
            {"id": "t1", "project": {"organ": "META", "repo": "engine"}, "status": "pending",
             "title": "Build rollup"},
        ]
        _write_jsonl(tmp_path / "atomized-tasks.jsonl", tasks)

        organ_dir = tmp_path / "workspace" / "meta-organvm"
        organ_dir.mkdir(parents=True)

        import argparse

        from organvm_engine.cli.atoms import cmd_atoms_fanout

        args = argparse.Namespace(
            atoms_dir=str(tmp_path),
            workspace=str(tmp_path / "workspace"),
            write=True,
        )
        rc = cmd_atoms_fanout(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DRY RUN]" not in out
        # File should exist
        rollup_path = organ_dir / ".atoms" / "organ-rollup.json"
        assert rollup_path.exists()
        data = json.loads(rollup_path.read_text(encoding="utf-8"))
        assert data["organ_key"] == "META"
        assert data["pending_tasks"] == 1


# ── Context injection ────────────────────────────────────────────


class TestAtomsContext:
    def test_with_rollup(self, tmp_path, monkeypatch):
        """Context injection shows task queue when rollup exists."""
        import organvm_engine.paths as paths_mod

        monkeypatch.setattr(paths_mod, "_DEFAULT_WORKSPACE", tmp_path)
        monkeypatch.delenv("ORGANVM_WORKSPACE_DIR", raising=False)

        # Set up organ dir + rollup
        organ_dir = tmp_path / "organvm-iii-ergon"
        organ_dir.mkdir()
        atoms = organ_dir / ".atoms"
        atoms.mkdir()
        rollup = {
            "organ_key": "III",
            "pending_by_repo": {
                "my-tool": [
                    {"id": "t1", "title": "Add feature", "status": "pending",
                     "tags": ["feat"]},
                ],
            },
            "cross_organ_links": [{"task_organ": "I", "prompt_organ": "III"}],
        }
        (atoms / "organ-rollup.json").write_text(
            json.dumps(rollup), encoding="utf-8",
        )

        from organvm_engine.contextmd.generator import _build_atoms_context

        result = _build_atoms_context("my-tool", "ORGAN-III")
        assert "pending tasks" in result
        assert "t1" in result
        assert "Add feature" in result

    def test_no_rollup(self, tmp_path, monkeypatch):
        """Shows 'run pipeline' hint when no rollup exists."""
        import organvm_engine.paths as paths_mod

        monkeypatch.setattr(paths_mod, "_DEFAULT_WORKSPACE", tmp_path)
        monkeypatch.delenv("ORGANVM_WORKSPACE_DIR", raising=False)

        organ_dir = tmp_path / "organvm-iii-ergon"
        organ_dir.mkdir()

        from organvm_engine.contextmd.generator import _build_atoms_context

        result = _build_atoms_context("my-tool", "ORGAN-III")
        assert "organvm atoms pipeline" in result

    def test_no_pending(self, tmp_path, monkeypatch):
        """Returns empty string when rollup exists but no pending tasks for repo."""
        import organvm_engine.paths as paths_mod

        monkeypatch.setattr(paths_mod, "_DEFAULT_WORKSPACE", tmp_path)
        monkeypatch.delenv("ORGANVM_WORKSPACE_DIR", raising=False)

        organ_dir = tmp_path / "organvm-iii-ergon"
        atoms = organ_dir / ".atoms"
        atoms.mkdir(parents=True)
        rollup = {
            "organ_key": "III",
            "pending_by_repo": {
                "other-repo": [{"id": "t1", "title": "X", "status": "pending", "tags": []}],
            },
            "cross_organ_links": [],
        }
        (atoms / "organ-rollup.json").write_text(
            json.dumps(rollup), encoding="utf-8",
        )

        from organvm_engine.contextmd.generator import _build_atoms_context

        result = _build_atoms_context("my-tool", "ORGAN-III")
        assert result == ""
