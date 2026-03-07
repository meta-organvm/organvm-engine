"""Tests for organvm_engine.atoms.linker — cross-system Jaccard matcher."""

import json
from pathlib import Path

import pytest

from organvm_engine.atoms.linker import (
    AtomLink,
    _extract_prompt_domain,
    _extract_task_domain,
    _load_jsonl,
    compute_links,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(tid: str, tags: list[str], files: list[str]) -> dict:
    return {
        "id": tid,
        "tags": tags,
        "files_touched": [{"path": f, "action": "modify"} for f in files],
    }


def _task_str_files(tid: str, tags: list[str], files: list[str]) -> dict:
    return {"id": tid, "tags": tags, "files_touched": files}


def _prompt(pid: str, tags: list[str], files: list[str],
            thread_id: str = "") -> dict:
    d: dict = {
        "id": pid,
        "signals": {"tags": tags, "mentions_files": files},
    }
    if thread_id:
        d["threading"] = {"thread_id": thread_id}
    return d


def _write_jsonl(path: Path, items: list[dict]) -> None:
    with open(path, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


# ---------------------------------------------------------------------------
# AtomLink
# ---------------------------------------------------------------------------

class TestAtomLink:
    def test_creation(self):
        link = AtomLink(
            task_id="t1", prompt_id="p1", jaccard=0.75,
            shared_tags=["python"], shared_refs=["src/a.py"],
        )
        assert link.task_id == "t1"
        assert link.jaccard == 0.75

    def test_to_dict_roundtrip(self):
        link = AtomLink(
            task_id="t1", prompt_id="p1", jaccard=0.33333,
            shared_tags=["go"], shared_refs=[],
        )
        d = link.to_dict()
        assert d["task_id"] == "t1"
        assert d["jaccard"] == 0.3333  # rounded to 4 decimals
        assert d["shared_tags"] == ["go"]
        assert d["shared_refs"] == []


# ---------------------------------------------------------------------------
# _load_jsonl
# ---------------------------------------------------------------------------

class TestLoadJsonl:
    def test_valid(self, tmp_path):
        p = tmp_path / "data.jsonl"
        _write_jsonl(p, [{"a": 1}, {"b": 2}])
        items = _load_jsonl(p)
        assert len(items) == 2
        assert items[0] == {"a": 1}

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        assert _load_jsonl(p) == []

    def test_blank_lines_skipped(self, tmp_path):
        p = tmp_path / "blanks.jsonl"
        p.write_text('{"x":1}\n\n\n{"y":2}\n')
        items = _load_jsonl(p)
        assert len(items) == 2


# ---------------------------------------------------------------------------
# _extract_task_domain / _extract_prompt_domain
# ---------------------------------------------------------------------------

class TestExtractDomains:
    def test_task_domain_dict_files(self):
        t = _task("t1", ["python"], ["src/a.py"])
        tags, refs = _extract_task_domain(t)
        assert tags == ["python"]
        assert refs == ["src/a.py"]

    def test_task_domain_string_files(self):
        t = _task_str_files("t1", ["go"], ["cmd/main.go"])
        tags, refs = _extract_task_domain(t)
        assert tags == ["go"]
        assert refs == ["cmd/main.go"]

    def test_prompt_domain(self):
        p = _prompt("p1", ["rust"], ["src/lib.rs"])
        tags, refs = _extract_prompt_domain(p)
        assert tags == ["rust"]
        assert refs == ["src/lib.rs"]

    def test_empty_signals(self):
        tags, refs = _extract_prompt_domain({"signals": {}})
        assert tags == []
        assert refs == []

    def test_missing_signals(self):
        tags, refs = _extract_prompt_domain({})
        assert tags == []
        assert refs == []


# ---------------------------------------------------------------------------
# compute_links
# ---------------------------------------------------------------------------

class TestComputeLinks:
    @pytest.fixture()
    def linked_data(self, tmp_path):
        """Two tasks and one prompt share python + src/foo.py; one task is disjoint."""
        tasks = [
            _task("t1", ["python", "fastapi"], ["src/foo.py", "src/bar.py"]),
            _task("t2", ["python"], ["src/foo.py"]),
            _task("t3", ["rust"], ["src/lib.rs"]),
        ]
        prompts = [
            _prompt("p1", ["python"], ["src/foo.py"]),
            _prompt("p2", ["java"], ["pom.xml"]),
        ]
        tp = tmp_path / "tasks.jsonl"
        pp = tmp_path / "prompts.jsonl"
        _write_jsonl(tp, tasks)
        _write_jsonl(pp, prompts)
        return tp, pp

    def test_exact_match(self, tmp_path):
        _write_jsonl(tmp_path / "t.jsonl", [_task("t1", ["python"], ["a.py"])])
        _write_jsonl(tmp_path / "p.jsonl", [_prompt("p1", ["python"], ["a.py"])])
        links = compute_links(tmp_path / "t.jsonl", tmp_path / "p.jsonl")
        assert len(links) == 1
        assert links[0].jaccard == 1.0

    def test_partial_match_above_threshold(self, linked_data):
        tp, pp = linked_data
        links = compute_links(tp, pp, threshold=0.15)
        # t1↔p1 and t2↔p1 should match; t3↔p1 should not
        task_ids = {l.task_id for l in links}
        assert "t1" in task_ids
        assert "t2" in task_ids
        assert "t3" not in task_ids

    def test_below_threshold_filtered(self, linked_data):
        tp, pp = linked_data
        links = compute_links(tp, pp, threshold=0.99)
        # Only exact or near-exact would pass; t2↔p1 is exact (both {tag:python, ref:src/foo.py})
        for link in links:
            assert link.jaccard >= 0.99

    def test_empty_inputs(self, tmp_path):
        _write_jsonl(tmp_path / "t.jsonl", [])
        _write_jsonl(tmp_path / "p.jsonl", [])
        assert compute_links(tmp_path / "t.jsonl", tmp_path / "p.jsonl") == []

    def test_sorted_descending(self, linked_data):
        tp, pp = linked_data
        links = compute_links(tp, pp, threshold=0.1)
        jaccards = [l.jaccard for l in links]
        assert jaccards == sorted(jaccards, reverse=True)

    def test_shared_tags_populated(self, linked_data):
        tp, pp = linked_data
        links = compute_links(tp, pp, threshold=0.15)
        for link in links:
            if link.task_id in ("t1", "t2"):
                assert "python" in link.shared_tags


class TestComputeLinksByThread:
    def test_by_thread_aggregates(self, tmp_path):
        tasks = [_task("t1", ["python", "fastapi"], ["src/app.py"])]
        prompts = [
            _prompt("p1", ["python"], [], thread_id="thread-a"),
            _prompt("p2", ["fastapi"], ["src/app.py"], thread_id="thread-a"),
        ]
        _write_jsonl(tmp_path / "t.jsonl", tasks)
        _write_jsonl(tmp_path / "p.jsonl", prompts)
        links = compute_links(
            tmp_path / "t.jsonl", tmp_path / "p.jsonl",
            by_thread=True,
        )
        assert len(links) >= 1
        assert links[0].prompt_id.startswith("thread:")

    def test_by_thread_no_thread_id(self, tmp_path):
        tasks = [_task("t1", ["python"], ["a.py"])]
        prompts = [_prompt("p1", ["python"], ["a.py"])]  # no thread_id
        _write_jsonl(tmp_path / "t.jsonl", tasks)
        _write_jsonl(tmp_path / "p.jsonl", prompts)
        links = compute_links(
            tmp_path / "t.jsonl", tmp_path / "p.jsonl",
            by_thread=True,
        )
        assert links == []  # prompts without thread_id are excluded in by_thread mode


class TestComputeLinksEdgeCases:
    def test_no_overlapping_content(self, tmp_path):
        _write_jsonl(tmp_path / "t.jsonl", [_task("t1", ["python"], ["a.py"])])
        _write_jsonl(tmp_path / "p.jsonl", [_prompt("p1", ["rust"], ["b.rs"])])
        assert compute_links(tmp_path / "t.jsonl", tmp_path / "p.jsonl") == []

    def test_single_task_single_prompt(self, tmp_path):
        _write_jsonl(tmp_path / "t.jsonl", [_task("t1", ["go"], ["cmd/main.go"])])
        _write_jsonl(tmp_path / "p.jsonl", [_prompt("p1", ["go"], ["cmd/main.go"])])
        links = compute_links(tmp_path / "t.jsonl", tmp_path / "p.jsonl")
        assert len(links) == 1
        assert links[0].jaccard == 1.0

    def test_empty_domain_task_skipped(self, tmp_path):
        _write_jsonl(tmp_path / "t.jsonl", [_task("t1", [], [])])
        _write_jsonl(tmp_path / "p.jsonl", [_prompt("p1", ["python"], ["a.py"])])
        assert compute_links(tmp_path / "t.jsonl", tmp_path / "p.jsonl") == []

    def test_empty_domain_prompt_skipped(self, tmp_path):
        _write_jsonl(tmp_path / "t.jsonl", [_task("t1", ["python"], ["a.py"])])
        _write_jsonl(tmp_path / "p.jsonl", [_prompt("p1", [], [])])
        assert compute_links(tmp_path / "t.jsonl", tmp_path / "p.jsonl") == []


# ---------------------------------------------------------------------------
# CLI handler
# ---------------------------------------------------------------------------

class TestCLI:
    def test_missing_files_exit_1(self, tmp_path):
        import argparse
        from organvm_engine.cli.atoms import cmd_atoms_link

        args = argparse.Namespace(
            tasks=str(tmp_path / "nope-tasks.jsonl"),
            prompts=str(tmp_path / "nope-prompts.jsonl"),
            threshold=0.15, by_thread=False, json=False, output=None,
        )
        assert cmd_atoms_link(args) == 1

    def test_valid_invocation(self, tmp_path):
        import argparse
        from organvm_engine.cli.atoms import cmd_atoms_link

        _write_jsonl(tmp_path / "t.jsonl", [_task("t1", ["py"], ["a.py"])])
        _write_jsonl(tmp_path / "p.jsonl", [_prompt("p1", ["py"], ["a.py"])])

        out = tmp_path / "links.json"
        args = argparse.Namespace(
            tasks=str(tmp_path / "t.jsonl"),
            prompts=str(tmp_path / "p.jsonl"),
            threshold=0.15, by_thread=False, json=True,
            output=str(out),
        )
        rc = cmd_atoms_link(args)
        assert rc == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data) == 1
        assert data[0]["task_id"] == "t1"


# ---------------------------------------------------------------------------
# Schema field coverage
# ---------------------------------------------------------------------------

class TestSchemaFields:
    def test_atomic_task_domain_fingerprint_in_dict(self, tmp_path):
        from organvm_engine.plans.atomizer import PlanParser

        plan = tmp_path / "plan.md"
        plan.write_text("# Test Plan\n\n- [x] Do something with `src/foo.py`\n")
        parser = PlanParser(
            plan.read_text().splitlines(), plan, tmp_path,
        )
        tasks = parser.parse()
        assert len(tasks) >= 1
        d = tasks[0].to_dict()
        assert "domain_fingerprint" in d
        assert isinstance(d["domain_fingerprint"], str)
        assert len(d["domain_fingerprint"]) == 16

    def test_annotated_prompt_domain_fingerprint_in_dict(self):
        from organvm_engine.prompts.schema import (
            AnnotatedPrompt,
            PromptSignals,
        )

        ap = AnnotatedPrompt()
        ap.signals = PromptSignals(tags=["python"], mentions_files=["a.py"])
        from organvm_engine.domain import domain_fingerprint
        ap.domain_fingerprint = domain_fingerprint(
            ap.signals.tags, ap.signals.mentions_files,
        )
        ap.compute_id()
        d = ap.to_dict()
        assert "domain_fingerprint" in d
        assert len(d["domain_fingerprint"]) == 16
