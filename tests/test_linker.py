"""Tests for Recs 3-5: linker threshold, empty fingerprint, generic tag filters."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from organvm_engine.atoms.linker import compute_links
from organvm_engine.prompts.audit import EMPTY_FINGERPRINT


def _write_jsonl(path: Path, items: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


# ── Rec 3: Default threshold ─────────────────────────────────

def test_linker_default_threshold():
    """Verify compute_links signature default is 0.30."""
    sig = inspect.signature(compute_links)
    assert sig.parameters["threshold"].default == 0.30


# ── Rec 4: Empty fingerprint filtering ───────────────────────

def test_linker_skips_empty_fingerprint(tmp_path):
    """Task with empty fingerprint produces no links."""
    tasks = [
        {
            "id": "task-empty-fp",
            "tags": ["python", "organvm"],
            "files_touched": ["src/foo.py"],
            "domain_fingerprint": EMPTY_FINGERPRINT + "9afbf4c8996fb924",
        },
    ]
    prompts = [
        {
            "id": "prompt-1",
            "signals": {"tags": ["python", "organvm"], "mentions_files": ["src/foo.py"]},
            "domain_fingerprint": "abcd1234abcd1234",
            "threading": {"thread_id": "t1"},
        },
    ]
    _write_jsonl(tmp_path / "tasks.jsonl", tasks)
    _write_jsonl(tmp_path / "prompts.jsonl", prompts)

    links = compute_links(tmp_path / "tasks.jsonl", tmp_path / "prompts.jsonl")
    assert len(links) == 0


def test_linker_skips_empty_fingerprint_prompt(tmp_path):
    """Prompt with empty fingerprint produces no links."""
    tasks = [
        {
            "id": "task-real",
            "tags": ["python", "organvm"],
            "files_touched": ["src/foo.py"],
            "domain_fingerprint": "abcd1234abcd1234",
        },
    ]
    prompts = [
        {
            "id": "prompt-empty-fp",
            "signals": {"tags": ["python", "organvm"], "mentions_files": ["src/foo.py"]},
            "domain_fingerprint": EMPTY_FINGERPRINT + "9afbf4c8996fb924",
            "threading": {"thread_id": "t1"},
        },
    ]
    _write_jsonl(tmp_path / "tasks.jsonl", tasks)
    _write_jsonl(tmp_path / "prompts.jsonl", prompts)

    links = compute_links(tmp_path / "tasks.jsonl", tmp_path / "prompts.jsonl")
    assert len(links) == 0


def test_linker_keeps_real_fingerprint(tmp_path):
    """Task with real fingerprint still links normally."""
    tasks = [
        {
            "id": "task-real",
            "tags": ["python", "organvm", "registry"],
            "files_touched": ["src/registry.py"],
            "domain_fingerprint": "abcd1234abcd1234",
        },
    ]
    prompts = [
        {
            "id": "prompt-real",
            "signals": {
                "tags": ["python", "organvm", "registry"],
                "mentions_files": ["src/registry.py"],
            },
            "domain_fingerprint": "efgh5678efgh5678",
            "threading": {"thread_id": "t1"},
        },
    ]
    _write_jsonl(tmp_path / "tasks.jsonl", tasks)
    _write_jsonl(tmp_path / "prompts.jsonl", prompts)

    links = compute_links(tmp_path / "tasks.jsonl", tmp_path / "prompts.jsonl")
    assert len(links) > 0
    assert links[0].task_id == "task-real"
    assert links[0].prompt_id == "prompt-real"


# ── Rec 5: Generic tag specificity ───────────────────────────

def test_linker_skips_generic_only(tmp_path):
    """Link with only generic shared tags and no shared refs is skipped."""
    tasks = [
        {
            "id": "task-generic",
            "tags": ["python", "bash"],
            "files_touched": ["scripts/deploy.sh"],
            "domain_fingerprint": "aaaa1111aaaa1111",
        },
    ]
    prompts = [
        {
            "id": "prompt-generic",
            "signals": {
                "tags": ["python", "bash"],
                "mentions_files": ["unrelated/file.py"],
            },
            "domain_fingerprint": "bbbb2222bbbb2222",
            "threading": {"thread_id": "t1"},
        },
    ]
    _write_jsonl(tmp_path / "tasks.jsonl", tasks)
    _write_jsonl(tmp_path / "prompts.jsonl", prompts)

    links = compute_links(
        tmp_path / "tasks.jsonl", tmp_path / "prompts.jsonl",
        threshold=0.01,  # very low to ensure Jaccard passes
    )
    assert len(links) == 0


def test_linker_keeps_specific_tags(tmp_path):
    """Link with specific tags passes through."""
    tasks = [
        {
            "id": "task-specific",
            "tags": ["python", "organvm", "registry"],
            "files_touched": [],
            "domain_fingerprint": "cccc3333cccc3333",
        },
    ]
    prompts = [
        {
            "id": "prompt-specific",
            "signals": {
                "tags": ["python", "organvm", "registry"],
                "mentions_files": [],
            },
            "domain_fingerprint": "dddd4444dddd4444",
            "threading": {"thread_id": "t1"},
        },
    ]
    _write_jsonl(tmp_path / "tasks.jsonl", tasks)
    _write_jsonl(tmp_path / "prompts.jsonl", prompts)

    links = compute_links(
        tmp_path / "tasks.jsonl", tmp_path / "prompts.jsonl",
        threshold=0.01,
    )
    assert len(links) > 0
    assert "organvm" in links[0].shared_tags


def test_linker_keeps_generic_with_refs(tmp_path):
    """Generic tags + shared file refs still link."""
    tasks = [
        {
            "id": "task-refs",
            "tags": ["python"],
            "files_touched": ["src/shared.py"],
            "domain_fingerprint": "eeee5555eeee5555",
        },
    ]
    prompts = [
        {
            "id": "prompt-refs",
            "signals": {
                "tags": ["python"],
                "mentions_files": ["src/shared.py"],
            },
            "domain_fingerprint": "ffff6666ffff6666",
            "threading": {"thread_id": "t1"},
        },
    ]
    _write_jsonl(tmp_path / "tasks.jsonl", tasks)
    _write_jsonl(tmp_path / "prompts.jsonl", prompts)

    links = compute_links(
        tmp_path / "tasks.jsonl", tmp_path / "prompts.jsonl",
        threshold=0.01,
    )
    assert len(links) > 0
    assert "src/shared.py" in links[0].shared_refs


# ── Rec 2: Pipeline reconcile default ────────────────────────

def test_pipeline_reconcile_default():
    """Verify reconcile defaults to True in argparse."""
    from organvm_engine.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["atoms", "pipeline", "--write"])
    assert args.reconcile is True


def test_pipeline_skip_reconcile():
    """Verify --skip-reconcile overrides default."""
    from organvm_engine.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["atoms", "pipeline", "--write", "--skip-reconcile"])
    assert args.skip_reconcile is True
