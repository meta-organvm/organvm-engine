"""Prompt & pipeline data audit — analysis functions.

All functions take loaded JSONL data (lists of dicts) and return structured
results. No file I/O.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime

# SHA-256 of empty string — produced when prompts have no tags/refs
EMPTY_FINGERPRINT = "e3b0c44298fc1c14"

# ── Noise detection patterns ────────────────────────────────────

_NOISE_PATTERNS: list[tuple[str, re.Pattern[str] | None, str | None]] = [
    ("tool_loaded", None, "Tool loaded."),
    ("request_interrupted", re.compile(
        r"^\[Request interrupted by user",
        re.IGNORECASE,
    ), None),
    ("task_notification", re.compile(r"<task-notification>"), None),
    ("system_reminder", re.compile(r"<system-reminder>"), None),
    ("clear_command", re.compile(r"^/clear\s*$"), None),
    ("empty", None, None),  # handled specially
    ("single_word_system", None, None),  # handled specially
]

_GENERIC_TAGS = frozenset({
    "python", "bash", "pytest", "javascript", "typescript", "node",
    "npm", "git", "json", "yaml", "markdown", "html", "css",
})


def _classify_noise(text: str) -> str | None:
    """Return noise type string if text is noise, else None."""
    stripped = text.strip()

    if not stripped:
        return "empty"

    if stripped == "Tool loaded.":
        return "tool_loaded"

    if stripped.startswith("[Request interrupted by user"):
        return "request_interrupted"

    if "<task-notification>" in stripped:
        return "task_notification"

    if "<system-reminder>" in stripped:
        return "system_reminder"

    if re.match(r"^/clear\s*$", stripped):
        return "clear_command"

    # Single word that isn't an imperative verb
    words = stripped.split()
    if len(words) == 1 and len(stripped) < 20 and stripped.startswith("<"):
        return "single_word_system"

    return None


def audit_noise(prompts: list[dict]) -> dict:
    """Classify each prompt as signal or noise."""
    total = len(prompts)
    noise_by_type: Counter[str] = Counter()
    noise_ids: list[str] = []
    signal_count = 0

    for p in prompts:
        text = p.get("raw_text", "") or p.get("content", {}).get("text", "")
        noise_type = _classify_noise(text)
        if noise_type:
            noise_by_type[noise_type] += 1
            noise_ids.append(p.get("id", ""))
        else:
            signal_count += 1

    noise_count = total - signal_count
    return {
        "total": total,
        "signal_count": signal_count,
        "noise_count": noise_count,
        "noise_pct": round(noise_count / total * 100, 1) if total else 0,
        "noise_by_type": dict(noise_by_type.most_common()),
        "noise_ids": noise_ids,
    }


# ── Completion funnel ───────────────────────────────────────────

def audit_completion(
    tasks: list[dict],
    prompts: list[dict],
    links: list[dict],
) -> dict:
    """Track the funnel: plans -> tasks -> linked prompts -> completed tasks."""
    # Build lookup sets
    linked_task_ids: set[str] = set()
    high_quality_linked: set[str] = set()
    for link in links:
        linked_task_ids.add(link.get("task_id", ""))
        if link.get("jaccard", 0) >= 0.30:
            high_quality_linked.add(link.get("task_id", ""))

    # Per-project aggregation
    by_project: dict[str, dict] = {}
    by_organ: dict[str, dict] = {}
    by_agent: dict[str, dict] = {}
    plan_task_counts: dict[str, dict] = {}  # plan_file -> {total, completed, linked}

    for t in tasks:
        tid = t.get("id", "")
        project = t.get("project", {})
        proj_key = f"{project.get('organ', '?')}/{project.get('repo', '?')}"
        organ = project.get("organ", "unknown")
        agent = t.get("source", {}).get("agent", "unknown")
        plan_file = t.get("source", {}).get("plan_file", "unknown")
        status = t.get("status", "pending").lower()
        is_completed = status in ("done", "complete", "completed")
        is_linked = tid in linked_task_ids
        is_hq_linked = tid in high_quality_linked

        for key, bucket in [(proj_key, by_project), (organ, by_organ), (agent, by_agent)]:
            if key not in bucket:
                bucket[key] = {
                    "total": 0, "completed": 0, "linked": 0, "hq_linked": 0,
                    "plans": set(),
                }
            bucket[key]["total"] += 1
            if is_completed:
                bucket[key]["completed"] += 1
            if is_linked:
                bucket[key]["linked"] += 1
            if is_hq_linked:
                bucket[key]["hq_linked"] += 1
            bucket[key]["plans"].add(plan_file)

        if plan_file not in plan_task_counts:
            plan_task_counts[plan_file] = {"total": 0, "completed": 0, "hq_linked": 0}
        plan_task_counts[plan_file]["total"] += 1
        if is_completed:
            plan_task_counts[plan_file]["completed"] += 1
        if is_hq_linked:
            plan_task_counts[plan_file]["hq_linked"] += 1

    # Ghost plans: 0 completed AND 0 high-quality links
    ghost_plans = [
        {"plan": pf, "tasks": info["total"]}
        for pf, info in sorted(plan_task_counts.items(), key=lambda x: -x[1]["total"])
        if info["completed"] == 0 and info["hq_linked"] == 0 and info["total"] > 0
    ]

    # Convert sets to counts for JSON serialization
    def _serialize(bucket: dict) -> dict:
        return {
            k: {**v, "plans": len(v["plans"])} for k, v in bucket.items()
        }

    total_tasks = len(tasks)
    _done = ("done", "complete", "completed")
    completed = sum(1 for t in tasks if t.get("status", "").lower() in _done)
    plans_seen = {t.get("source", {}).get("plan_file", "") for t in tasks}

    return {
        "funnel_summary": {
            "plans_parsed": len(plans_seen),
            "total_tasks": total_tasks,
            "tasks_with_links": len(linked_task_ids & {t.get("id", "") for t in tasks}),
            "tasks_with_hq_links": len(high_quality_linked & {t.get("id", "") for t in tasks}),
            "completed_tasks": completed,
            "completion_rate": round(completed / total_tasks * 100, 1) if total_tasks else 0,
            "linkage_rate": round(
                len(high_quality_linked & {t.get("id", "") for t in tasks})
                / total_tasks * 100, 1,
            ) if total_tasks else 0,
        },
        "by_project": _serialize(by_project),
        "by_organ": _serialize(by_organ),
        "by_agent": _serialize(by_agent),
        "ghost_plans": ghost_plans[:50],
        "ghost_plan_count": len(ghost_plans),
    }


# ── Prompt effectiveness ────────────────────────────────────────

def audit_effectiveness(
    prompts: list[dict],
    tasks: list[dict],
    links: list[dict],
) -> dict:
    """Cross-reference prompt characteristics against task completion."""
    # Build task completion lookup
    task_status: dict[str, bool] = {}
    for t in tasks:
        tid = t.get("id", "")
        task_status[tid] = t.get("status", "").lower() in ("done", "complete", "completed")

    # Build prompt -> linked task IDs
    prompt_to_tasks: dict[str, list[str]] = defaultdict(list)
    for link in links:
        if link.get("jaccard", 0) >= 0.30:
            prompt_to_tasks[link.get("prompt_id", "")].append(link.get("task_id", ""))

    # By prompt type
    by_type: dict[str, dict] = {}
    by_size: dict[str, dict] = {}
    specificity_bins: dict[str, dict] = {"high": {"total": 0, "completed": 0},
                                          "low": {"total": 0, "completed": 0}}

    for p in prompts:
        pid = p.get("id", "")
        ptype = p.get("classification", {}).get("prompt_type", "unknown")
        size_class = p.get("classification", {}).get("size_class", "unknown")
        linked_tasks = prompt_to_tasks.get(pid, [])
        completed_count = sum(1 for tid in linked_tasks if task_status.get(tid, False))

        for key, bucket in [(ptype, by_type), (size_class, by_size)]:
            if key not in bucket:
                bucket[key] = {"prompts": 0, "linked_tasks": 0, "completed_tasks": 0}
            bucket[key]["prompts"] += 1
            bucket[key]["linked_tasks"] += len(linked_tasks)
            bucket[key]["completed_tasks"] += completed_count

        # Specificity: has file mentions AND tool mentions = high
        signals = p.get("signals", {})
        has_files = bool(signals.get("mentions_files"))
        has_tools = bool(signals.get("mentions_tools"))
        has_tags = len(signals.get("tags", [])) > 2
        spec = "high" if (has_files or has_tools) and has_tags else "low"
        specificity_bins[spec]["total"] += len(linked_tasks)
        specificity_bins[spec]["completed"] += completed_count

    # Arc pattern analysis from threading
    by_arc: dict[str, dict] = {}
    thread_types: dict[str, Counter[str]] = defaultdict(Counter)
    for p in prompts:
        thread_id = p.get("threading", {}).get("thread_id", "")
        ptype = p.get("classification", {}).get("prompt_type", "unknown")
        if thread_id:
            thread_types[thread_id][ptype] += 1

    # Classify thread arc patterns
    for _thread_id, type_counts in thread_types.items():
        total_in_thread = sum(type_counts.values())
        if total_in_thread <= 2:
            pattern = "single-shot"
        elif type_counts.get("correction", 0) / total_in_thread > 0.20:
            pattern = "iterative-correction"
        elif list(type_counts.most_common(1))[0][0] == "plan_invocation":
            pattern = "plan-then-execute"
        else:
            pattern = "steady-build"

        if pattern not in by_arc:
            by_arc[pattern] = {"threads": 0}
        by_arc[pattern]["threads"] += 1

    # Correction analysis
    correction_threads = sum(
        1 for tid, tc in thread_types.items()
        if sum(tc.values()) > 2 and tc.get("correction", 0) / sum(tc.values()) > 0.20
    )
    total_threads = len(thread_types)

    return {
        "by_type": by_type,
        "by_size": by_size,
        "by_arc_pattern": by_arc,
        "correction_analysis": {
            "threads_with_high_correction": correction_threads,
            "total_threads": total_threads,
            "correction_rate": round(
                correction_threads / total_threads * 100, 1,
            ) if total_threads else 0,
        },
        "specificity_analysis": specificity_bins,
    }


# ── Session patterns ────────────────────────────────────────────

def audit_sessions(prompts: list[dict]) -> dict:
    """Analyze session-level behavior patterns."""
    sessions: dict[str, list[dict]] = defaultdict(list)
    for p in prompts:
        sid = p.get("source", {}).get("session_id", "")
        if sid:
            sessions[sid].append(p)

    # Session length distribution
    lengths = [len(v) for v in sessions.values()]
    length_buckets = {"1": 0, "2-5": 0, "6-10": 0, "11-20": 0, "21-50": 0, "51+": 0}
    for length in lengths:
        if length == 1:
            length_buckets["1"] += 1
        elif length <= 5:
            length_buckets["2-5"] += 1
        elif length <= 10:
            length_buckets["6-10"] += 1
        elif length <= 20:
            length_buckets["11-20"] += 1
        elif length <= 50:
            length_buckets["21-50"] += 1
        else:
            length_buckets["51+"] += 1

    # Session duration
    durations_minutes: list[float] = []
    for _sid, session_prompts in sessions.items():
        timestamps = [
            _parse_ts(p.get("source", {}).get("timestamp"))
            for p in session_prompts
        ]
        valid_ts = [t for t in timestamps if t is not None]
        if len(valid_ts) >= 2:
            duration = (max(valid_ts) - min(valid_ts)).total_seconds() / 60
            durations_minutes.append(duration)

    dur_buckets = {"<5m": 0, "5-15m": 0, "15-30m": 0, "30-60m": 0, "1-2h": 0, "2h+": 0}
    for d in durations_minutes:
        if d < 5:
            dur_buckets["<5m"] += 1
        elif d < 15:
            dur_buckets["5-15m"] += 1
        elif d < 30:
            dur_buckets["15-30m"] += 1
        elif d < 60:
            dur_buckets["30-60m"] += 1
        elif d < 120:
            dur_buckets["1-2h"] += 1
        else:
            dur_buckets["2h+"] += 1

    # Productive sessions (ending with git_ops)
    productive = 0
    for _sid, session_prompts in sessions.items():
        sorted_ps = sorted(
            session_prompts,
            key=lambda p: p.get("source", {}).get("prompt_index", 0),
        )
        if sorted_ps:
            last_type = sorted_ps[-1].get("classification", {}).get("prompt_type", "")
            if last_type == "git_ops":
                productive += 1

    # Hourly distribution
    hourly: Counter[int] = Counter()
    daily: Counter[str] = Counter()
    for p in prompts:
        ts = _parse_ts(p.get("source", {}).get("timestamp"))
        if ts:
            hourly[ts.hour] += 1
            daily[ts.strftime("%A")] += 1

    # Context switches per day
    day_projects: dict[str, set[str]] = defaultdict(set)
    for p in prompts:
        ts = p.get("source", {}).get("timestamp", "")
        slug = p.get("source", {}).get("project_slug", "")
        if ts and len(ts) >= 10 and slug:
            day_projects[ts[:10]].add(slug)

    context_switches = {
        day: len(projects) for day, projects in sorted(day_projects.items())
    }
    avg_switches = (
        sum(context_switches.values()) / len(context_switches)
        if context_switches else 0
    )

    # Session churn
    single_prompt = sum(1 for v in sessions.values() if len(v) == 1)
    multi_prompt = sum(1 for v in sessions.values() if len(v) > 1)

    return {
        "total_sessions": len(sessions),
        "length_dist": length_buckets,
        "duration_dist": dur_buckets,
        "productive_sessions": productive,
        "productive_pct": round(productive / len(sessions) * 100, 1) if sessions else 0,
        "context_switches": {
            "avg_projects_per_day": round(avg_switches, 1),
            "max_projects_in_day": max(context_switches.values()) if context_switches else 0,
        },
        "hourly": dict(sorted(hourly.items())),
        "daily": dict(daily.most_common()),
        "churn": {
            "single_prompt_sessions": single_prompt,
            "multi_prompt_sessions": multi_prompt,
            "churn_ratio": round(
                single_prompt / len(sessions) * 100, 1,
            ) if sessions else 0,
        },
    }


# ── Linking quality ─────────────────────────────────────────────

def audit_links(
    links: list[dict],
    tasks: list[dict],
    prompts: list[dict],
) -> dict:
    """Evaluate whether the links are meaningful."""
    # Jaccard distribution (0.05 buckets)
    jaccard_dist: dict[str, int] = {}
    for bucket_start in range(0, 100, 5):
        low = bucket_start / 100
        high = (bucket_start + 5) / 100
        label = f"{low:.2f}-{high:.2f}"
        jaccard_dist[label] = 0

    for link in links:
        j = link.get("jaccard", 0)
        bucket_idx = min(int(j * 20), 19)
        low = bucket_idx * 5 / 100
        high = (bucket_idx + 1) * 5 / 100
        label = f"{low:.2f}-{high:.2f}"
        jaccard_dist[label] = jaccard_dist.get(label, 0) + 1

    # Empty fingerprint contamination
    prompt_fps: dict[str, str] = {}
    for p in prompts:
        prompt_fps[p.get("id", "")] = p.get("domain_fingerprint", "")
    task_fps: dict[str, str] = {}
    for t in tasks:
        task_fps[t.get("id", "")] = t.get("domain_fingerprint", "")

    empty_fp_count = 0
    for link in links:
        t_fp = task_fps.get(link.get("task_id", ""), "")
        p_fp = prompt_fps.get(link.get("prompt_id", ""), "")
        if t_fp.startswith(EMPTY_FINGERPRINT) or p_fp.startswith(EMPTY_FINGERPRINT):
            empty_fp_count += 1

    # Tag specificity: generic vs domain-specific
    generic_tag_links = 0
    for link in links:
        shared = link.get("shared_tags", [])
        if shared and all(t.lower() in _GENERIC_TAGS for t in shared):
            generic_tag_links += 1

    # Fan-out analysis
    task_link_counts: Counter[str] = Counter()
    for link in links:
        task_link_counts[link.get("task_id", "")] += 1

    high_fanout = [
        {"task_id": tid, "link_count": count}
        for tid, count in task_link_counts.most_common()
        if count > 100
    ]

    # Threshold analysis
    threshold_analysis: dict[str, dict] = {}
    for threshold in (0.15, 0.20, 0.30, 0.40, 0.50):
        above = [lk for lk in links if lk.get("jaccard", 0) >= threshold]
        tasks_with_links = len({lk.get("task_id", "") for lk in above})
        threshold_analysis[f"{threshold:.2f}"] = {
            "links": len(above),
            "tasks_with_links": tasks_with_links,
            "pct_of_total": round(len(above) / len(links) * 100, 1) if links else 0,
        }

    return {
        "total_links": len(links),
        "jaccard_dist": jaccard_dist,
        "empty_fp_count": empty_fp_count,
        "empty_fp_pct": round(empty_fp_count / len(links) * 100, 1) if links else 0,
        "generic_tag_links": generic_tag_links,
        "generic_tag_pct": round(generic_tag_links / len(links) * 100, 1) if links else 0,
        "high_fanout_tasks": high_fanout[:20],
        "high_fanout_count": len(high_fanout),
        "threshold_analysis": threshold_analysis,
    }


# ── Recommendations ─────────────────────────────────────────────

def generate_recommendations(
    noise: dict,
    completion: dict,
    effectiveness: dict,
    sessions: dict,
    links_audit: dict,
) -> list[dict]:
    """Synthesize findings into actionable recommendations."""
    recs: list[dict] = []

    # Noise filtering
    if noise["noise_pct"] > 20:
        recs.append({
            "priority": "P0",
            "category": "data_quality",
            "finding": f"{noise['noise_pct']}% of prompts are noise",
            "recommendation": (
                "Filter noise prompts before narration"
                " — add pre-filter to narrator.py"
            ),
            "expected_impact": f"Remove {noise['noise_count']} noise entries from analysis",
        })

    # Completion rate
    funnel = completion.get("funnel_summary", {})
    if funnel.get("completion_rate", 0) < 10:
        recs.append({
            "priority": "P0",
            "category": "completion",
            "finding": f"Only {funnel.get('completion_rate', 0)}% task completion rate",
            "recommendation": (
                "Run `organvm atoms reconcile --write`"
                " to update completion from git history"
            ),
            "expected_impact": "Accurate completion data from git evidence",
        })

    # Ghost plans
    ghost_count = completion.get("ghost_plan_count", 0)
    if ghost_count > 5:
        recs.append({
            "priority": "P1",
            "category": "planning",
            "finding": f"{ghost_count} ghost plans (0 completion, 0 quality links)",
            "recommendation": "Review ghost plans — archive abandoned ones, complete viable ones",
            "expected_impact": "Cleaner plan inventory, focused effort",
        })

    # Jaccard threshold
    threshold = links_audit.get("threshold_analysis", {})
    t015 = threshold.get("0.15", {})
    t030 = threshold.get("0.30", {})
    if t015 and t030:
        reduction = t015.get("links", 0) - t030.get("links", 0)
        if reduction > 0 and t015.get("links", 0) > 0:
            pct = round(reduction / t015["links"] * 100, 1)
            if pct > 50:
                recs.append({
                    "priority": "P0",
                    "category": "linking",
                    "finding": (
                        f"Raising threshold 0.15→0.30 removes {pct}% of links"
                    ),
                    "recommendation": "Raise default threshold to 0.30 in linker.py",
                    "expected_impact": f"Eliminate {reduction} low-quality links",
                })

    # Empty fingerprint contamination
    if links_audit.get("empty_fp_pct", 0) > 10:
        recs.append({
            "priority": "P1",
            "category": "linking",
            "finding": f"{links_audit['empty_fp_pct']}% of links involve empty-fingerprint items",
            "recommendation": "Skip prompts/tasks with empty-string fingerprint in linker",
            "expected_impact": "Remove meaningless content-free matches",
        })

    # Generic tag links
    if links_audit.get("generic_tag_pct", 0) > 30:
        recs.append({
            "priority": "P1",
            "category": "linking",
            "finding": f"{links_audit['generic_tag_pct']}% of links based only on generic tags",
            "recommendation": "Add tag specificity weighting or minimum unique-tag requirement",
            "expected_impact": "Higher precision in task-prompt matching",
        })

    # High fanout
    if links_audit.get("high_fanout_count", 0) > 5:
        recs.append({
            "priority": "P1",
            "category": "linking",
            "finding": (
                f"{links_audit['high_fanout_count']} tasks"
                " have >100 links (likely false positives)"
            ),
            "recommendation": "Cap fan-out or require minimum 2 unique tags for linking",
            "expected_impact": "Fewer false positive matches",
        })

    # Session churn
    churn = sessions.get("churn", {})
    if churn.get("churn_ratio", 0) > 40:
        recs.append({
            "priority": "P2",
            "category": "workflow",
            "finding": f"{churn['churn_ratio']}% of sessions are single-prompt",
            "recommendation": "Investigate single-prompt sessions — may indicate workflow friction",
            "expected_impact": "Better understanding of session abandonment",
        })

    # Correction rate
    corr = effectiveness.get("correction_analysis", {})
    if corr.get("correction_rate", 0) > 15:
        recs.append({
            "priority": "P2",
            "category": "effectiveness",
            "finding": f"{corr['correction_rate']}% of threads have high correction rates",
            "recommendation": "Review corrective threads for prompt clarity improvements",
            "expected_impact": "Fewer wasted AI turns from miscommunication",
        })

    return sorted(recs, key=lambda r: r["priority"])


# ── Utility ─────────────────────────────────────────────────────

def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
