"""Tests for prompt & pipeline data audit."""

from __future__ import annotations

import json

from organvm_engine.prompts.audit import (
    audit_completion,
    audit_effectiveness,
    audit_links,
    audit_noise,
    audit_sessions,
    generate_recommendations,
)
from organvm_engine.prompts.audit_report import generate_audit_report


# ── Fixtures ────────────────────────────────────────────────────

def _make_prompt(
    pid: str = "p1",
    text: str = "implement the function",
    prompt_type: str = "command",
    size_class: str = "short",
    session_id: str = "s1",
    project_slug: str = "meta-organvm/organvm-engine",
    timestamp: str = "2026-02-15T10:00:00Z",
    prompt_index: int = 0,
    tags: list[str] | None = None,
    mentions_files: list[str] | None = None,
    mentions_tools: list[str] | None = None,
    thread_id: str = "t1",
    domain_fingerprint: str = "abc123",
) -> dict:
    return {
        "id": pid,
        "raw_text": text,
        "source": {
            "session_id": session_id,
            "agent": "claude",
            "project_slug": project_slug,
            "timestamp": timestamp,
            "prompt_index": prompt_index,
            "prompt_count": 5,
        },
        "content": {"text": text[:500], "char_count": len(text)},
        "classification": {
            "prompt_type": prompt_type,
            "size_class": size_class,
            "session_position": "middle",
        },
        "signals": {
            "tags": tags or ["python"],
            "mentions_files": mentions_files or [],
            "mentions_tools": mentions_tools or [],
        },
        "threading": {"thread_id": thread_id, "thread_label": "test/work"},
        "domain_fingerprint": domain_fingerprint,
    }


def _make_task(
    tid: str = "t1",
    status: str = "pending",
    organ: str = "META",
    repo: str = "organvm-engine",
    tags: list[str] | None = None,
    plan_file: str = "plan-a.md",
    domain_fingerprint: str = "abc123",
) -> dict:
    return {
        "id": tid,
        "title": f"Task {tid}",
        "status": status,
        "tags": tags or ["python"],
        "files_touched": [{"path": "src/main.py", "action": "create"}],
        "project": {"organ": organ, "repo": repo},
        "source": {"plan_file": plan_file, "agent": "claude"},
        "domain_fingerprint": domain_fingerprint,
    }


def _make_link(
    task_id: str = "t1",
    prompt_id: str = "p1",
    jaccard: float = 0.5,
    shared_tags: list[str] | None = None,
) -> dict:
    return {
        "task_id": task_id,
        "prompt_id": prompt_id,
        "jaccard": jaccard,
        "shared_tags": shared_tags or ["python"],
        "shared_refs": [],
    }


# ── Noise detection tests ──────────────────────────────────────

class TestNoiseDetection:
    def test_tool_loaded(self):
        prompts = [_make_prompt(text="Tool loaded.")]
        result = audit_noise(prompts)
        assert result["noise_count"] == 1
        assert "tool_loaded" in result["noise_by_type"]

    def test_request_interrupted(self):
        prompts = [_make_prompt(text="[Request interrupted by user for tool use]")]
        result = audit_noise(prompts)
        assert result["noise_count"] == 1
        assert "request_interrupted" in result["noise_by_type"]

    def test_task_notification(self):
        prompts = [_make_prompt(text="<task-notification>something</task-notification>")]
        result = audit_noise(prompts)
        assert result["noise_count"] == 1
        assert "task_notification" in result["noise_by_type"]

    def test_system_reminder(self):
        prompts = [_make_prompt(text="<system-reminder>context</system-reminder>")]
        result = audit_noise(prompts)
        assert result["noise_count"] == 1
        assert "system_reminder" in result["noise_by_type"]

    def test_clear_command(self):
        prompts = [_make_prompt(text="/clear")]
        result = audit_noise(prompts)
        assert result["noise_count"] == 1
        assert "clear_command" in result["noise_by_type"]

    def test_empty(self):
        prompts = [_make_prompt(text="")]
        result = audit_noise(prompts)
        assert result["noise_count"] == 1
        assert "empty" in result["noise_by_type"]

    def test_real_prompt_is_signal(self):
        prompts = [_make_prompt(text="Implement the following plan: add validation")]
        result = audit_noise(prompts)
        assert result["signal_count"] == 1
        assert result["noise_count"] == 0

    def test_noise_summary_counts(self):
        prompts = [
            _make_prompt(pid="p1", text="Tool loaded."),
            _make_prompt(pid="p2", text="Implement the function"),
            _make_prompt(pid="p3", text=""),
        ]
        result = audit_noise(prompts)
        assert result["noise_count"] + result["signal_count"] == result["total"]
        assert result["total"] == 3


# ── Completion funnel tests ────────────────────────────────────

class TestCompletionFunnel:
    def test_basic_funnel(self):
        tasks = [
            _make_task(tid="t1", status="pending"),
            _make_task(tid="t2", status="completed"),
        ]
        prompts = [_make_prompt()]
        links = [_make_link(task_id="t1", jaccard=0.5)]

        result = audit_completion(tasks, prompts, links)
        funnel = result["funnel_summary"]
        assert funnel["total_tasks"] == 2
        assert funnel["completed_tasks"] == 1
        assert funnel["tasks_with_hq_links"] == 1

    def test_by_organ(self):
        tasks = [
            _make_task(tid="t1", organ="META"),
            _make_task(tid="t2", organ="III"),
            _make_task(tid="t3", organ="META"),
        ]
        result = audit_completion(tasks, [], [])
        assert "META" in result["by_organ"]
        assert "III" in result["by_organ"]
        assert result["by_organ"]["META"]["total"] == 2
        assert result["by_organ"]["III"]["total"] == 1

    def test_ghost_plans_detected(self):
        tasks = [
            _make_task(tid="t1", status="pending", plan_file="ghost-plan.md"),
            _make_task(tid="t2", status="pending", plan_file="ghost-plan.md"),
        ]
        result = audit_completion(tasks, [], [])
        assert result["ghost_plan_count"] > 0
        ghost_names = [g["plan"] for g in result["ghost_plans"]]
        assert "ghost-plan.md" in ghost_names


# ── Effectiveness tests ────────────────────────────────────────

class TestEffectiveness:
    def test_by_type(self):
        prompts = [
            _make_prompt(pid="p1", prompt_type="plan_invocation"),
            _make_prompt(pid="p2", prompt_type="command"),
        ]
        tasks = [_make_task(tid="t1", status="completed")]
        links = [
            _make_link(task_id="t1", prompt_id="p1", jaccard=0.5),
            _make_link(task_id="t1", prompt_id="p2", jaccard=0.5),
        ]
        result = audit_effectiveness(prompts, tasks, links)
        assert "plan_invocation" in result["by_type"]
        assert "command" in result["by_type"]
        assert result["by_type"]["plan_invocation"]["completed_tasks"] == 1

    def test_specificity(self):
        prompts = [
            _make_prompt(
                pid="p1",
                mentions_files=["src/main.py"],
                mentions_tools=["pytest"],
                tags=["python", "testing", "validation"],
            ),
            _make_prompt(pid="p2", mentions_files=[], mentions_tools=[], tags=["python"]),
        ]
        tasks = [_make_task(tid="t1", status="completed")]
        links = [
            _make_link(task_id="t1", prompt_id="p1", jaccard=0.5),
            _make_link(task_id="t1", prompt_id="p2", jaccard=0.5),
        ]
        result = audit_effectiveness(prompts, tasks, links)
        spec = result["specificity_analysis"]
        assert spec["high"]["completed"] >= spec["low"]["completed"]


# ── Session pattern tests ──────────────────────────────────────

class TestSessionPatterns:
    def test_length_distribution(self):
        prompts = [
            _make_prompt(pid=f"p{i}", session_id="s1", prompt_index=i)
            for i in range(5)
        ]
        result = audit_sessions(prompts)
        assert result["length_dist"]["2-5"] == 1

    def test_churn_ratio(self):
        prompts = [
            _make_prompt(pid="p1", session_id="s1"),
            _make_prompt(pid="p2", session_id="s2"),
            _make_prompt(pid="p3", session_id="s3", prompt_index=0),
            _make_prompt(pid="p4", session_id="s3", prompt_index=1),
        ]
        result = audit_sessions(prompts)
        churn = result["churn"]
        assert churn["single_prompt_sessions"] == 2
        assert churn["multi_prompt_sessions"] == 1


# ── Linking quality tests ──────────────────────────────────────

class TestLinkingQuality:
    def test_empty_fingerprint_flagged(self):
        prompts = [_make_prompt(domain_fingerprint="e3b0c44298fc1c14")]
        tasks = [_make_task(domain_fingerprint="abc123")]
        links = [_make_link(task_id="t1", prompt_id="p1")]
        result = audit_links(links, tasks, prompts)
        assert result["empty_fp_count"] == 1

    def test_fanout_detection(self):
        tasks = [_make_task(tid="t1")]
        prompts = [_make_prompt(pid=f"p{i}") for i in range(150)]
        links = [_make_link(task_id="t1", prompt_id=f"p{i}") for i in range(150)]
        result = audit_links(links, tasks, prompts)
        assert result["high_fanout_count"] == 1
        assert result["high_fanout_tasks"][0]["task_id"] == "t1"

    def test_threshold_analysis(self):
        links = [
            _make_link(jaccard=0.10),
            _make_link(jaccard=0.20, prompt_id="p2"),
            _make_link(jaccard=0.35, prompt_id="p3"),
            _make_link(jaccard=0.55, prompt_id="p4"),
        ]
        result = audit_links(links, [], [])
        ta = result["threshold_analysis"]
        assert ta["0.15"]["links"] == 3  # 0.20, 0.35, 0.55
        assert ta["0.30"]["links"] == 2  # 0.35, 0.55
        assert ta["0.50"]["links"] == 1  # 0.55


# ── Recommendations tests ──────────────────────────────────────

class TestRecommendations:
    def test_recommendations_generated(self):
        noise = {"noise_pct": 40, "noise_count": 100, "signal_count": 150, "total": 250,
                 "noise_by_type": {}, "noise_ids": []}
        completion = {"funnel_summary": {"completion_rate": 2, "total_tasks": 100},
                      "ghost_plan_count": 10, "ghost_plans": []}
        effectiveness = {"correction_analysis": {"correction_rate": 5, "threads_with_high_correction": 2,
                                                  "total_threads": 40}}
        sessions = {"churn": {"churn_ratio": 50, "single_prompt_sessions": 50}}
        links_audit = {
            "empty_fp_pct": 20,
            "generic_tag_pct": 40,
            "high_fanout_count": 10,
            "threshold_analysis": {
                "0.15": {"links": 10000, "tasks_with_links": 500, "pct_of_total": 100},
                "0.30": {"links": 2000, "tasks_with_links": 300, "pct_of_total": 20},
            },
        }
        recs = generate_recommendations(noise, completion, effectiveness, sessions, links_audit)
        assert len(recs) > 0
        assert all(
            set(r.keys()) >= {"priority", "category", "finding", "recommendation", "expected_impact"}
            for r in recs
        )
        # Should have P0 recs for noise, completion, and threshold
        p0s = [r for r in recs if r["priority"] == "P0"]
        assert len(p0s) >= 2


# ── Report rendering tests ─────────────────────────────────────

class TestReport:
    def test_report_markdown_structure(self):
        results = {
            "noise": {"total": 100, "signal_count": 60, "noise_count": 40,
                      "noise_pct": 40, "noise_by_type": {"tool_loaded": 30, "empty": 10}},
            "completion": {
                "funnel_summary": {"plans_parsed": 10, "total_tasks": 50,
                                   "tasks_with_links": 30, "tasks_with_hq_links": 20,
                                   "completed_tasks": 5, "completion_rate": 10,
                                   "linkage_rate": 40},
                "by_organ": {}, "by_project": {}, "by_agent": {},
                "ghost_plans": [], "ghost_plan_count": 0,
            },
            "effectiveness": {
                "by_type": {}, "by_size": {},
                "by_arc_pattern": {},
                "correction_analysis": {"correction_rate": 5,
                                        "threads_with_high_correction": 2,
                                        "total_threads": 40},
                "specificity_analysis": {
                    "high": {"total": 10, "completed": 5},
                    "low": {"total": 20, "completed": 2},
                },
            },
            "sessions": {
                "total_sessions": 50,
                "length_dist": {"1": 10, "2-5": 20},
                "duration_dist": {"<5m": 5},
                "productive_sessions": 10, "productive_pct": 20,
                "context_switches": {"avg_projects_per_day": 3, "max_projects_in_day": 7},
                "hourly": {10: 50, 14: 30},
                "daily": {"Monday": 100},
                "churn": {"single_prompt_sessions": 10, "multi_prompt_sessions": 40,
                          "churn_ratio": 20},
            },
            "links": {
                "total_links": 1000, "jaccard_dist": {},
                "empty_fp_count": 50, "empty_fp_pct": 5,
                "generic_tag_links": 200, "generic_tag_pct": 20,
                "high_fanout_tasks": [], "high_fanout_count": 0,
                "threshold_analysis": {},
            },
            "recommendations": [
                {"priority": "P0", "category": "data_quality",
                 "finding": "test finding", "recommendation": "test rec",
                 "expected_impact": "test impact"},
            ],
        }

        report = generate_audit_report(results)

        # All major sections present
        assert "# Prompt & Pipeline Data Audit" in report
        assert "## Executive Summary" in report
        assert "## Data Quality" in report
        assert "## Completion Funnel" in report
        assert "## Prompt Effectiveness" in report
        assert "## Session Patterns" in report
        assert "## Linking Quality" in report
        assert "## Recommendations" in report
        assert "Overall Health Grade" in report


# ── CLI integration smoke test ─────────────────────────────────

class TestCLI:
    def test_cli_audit_dry_run(self, tmp_path):
        """Verify CLI wiring loads without errors (no real data)."""
        from organvm_engine.cli.prompts import cmd_prompts_audit
        import argparse

        args = argparse.Namespace(
            output=str(tmp_path / "report.md"),
            json=False,
            noise_only=False,
        )

        # Monkeypatch atoms_dir to tmp_path
        import organvm_engine.paths as paths_mod
        original = paths_mod.atoms_dir

        def fake_atoms_dir():
            return tmp_path

        paths_mod.atoms_dir = fake_atoms_dir
        try:
            # No data files → should return 1 with message
            result = cmd_prompts_audit(args)
            assert result == 1
        finally:
            paths_mod.atoms_dir = original

    def test_cli_audit_with_data(self, tmp_path):
        """Full CLI run with minimal synthetic data."""
        from organvm_engine.cli.prompts import cmd_prompts_audit
        import argparse

        # Write minimal JSONL data
        prompts_data = [
            _make_prompt(pid="p1", text="Implement validation"),
            _make_prompt(pid="p2", text="Tool loaded."),
        ]
        tasks_data = [_make_task(tid="t1")]
        links_data = [_make_link(task_id="t1", prompt_id="p1", jaccard=0.5)]

        for name, data in [
            ("annotated-prompts.jsonl", prompts_data),
            ("atomized-tasks.jsonl", tasks_data),
            ("atom-links.jsonl", links_data),
        ]:
            path = tmp_path / name
            with path.open("w") as f:
                for item in data:
                    f.write(json.dumps(item) + "\n")

        import organvm_engine.paths as paths_mod
        original = paths_mod.atoms_dir

        def fake_atoms_dir():
            return tmp_path

        paths_mod.atoms_dir = fake_atoms_dir
        try:
            args = argparse.Namespace(
                output=str(tmp_path / "AUDIT-REPORT.md"),
                json=False,
                noise_only=False,
            )
            result = cmd_prompts_audit(args)
            assert result == 0
            assert (tmp_path / "AUDIT-REPORT.md").exists()

            report = (tmp_path / "AUDIT-REPORT.md").read_text()
            assert "Prompt & Pipeline Data Audit" in report
        finally:
            paths_mod.atoms_dir = original
