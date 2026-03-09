"""Tests for prompts/threading.py — episode clustering, thread assignment, arc patterns."""


from organvm_engine.prompts.schema import (
    AnnotatedPrompt,
    PromptClassification,
    PromptSignals,
    PromptSource,
    PromptThreading,
)
from organvm_engine.prompts.threading import (
    assign_arc_positions,
    assign_threads,
    classify_arc_pattern,
    cluster_into_episodes,
)


def _make_prompt(
    session_id: str = "s1",
    project_slug: str = "meta-organvm/organvm-engine",
    timestamp: str | None = "2026-03-01T10:00:00Z",
    prompt_index: int = 0,
    prompt_type: str = "command",
    imperative_verb: str = "implement",
) -> AnnotatedPrompt:
    ap = AnnotatedPrompt()
    ap.source = PromptSource(
        session_id=session_id,
        project_slug=project_slug,
        timestamp=timestamp,
        prompt_index=prompt_index,
    )
    ap.classification = PromptClassification(prompt_type=prompt_type)
    ap.signals = PromptSignals(imperative_verb=imperative_verb)
    ap.threading = PromptThreading()
    return ap


# ── cluster_into_episodes ──────────────────────────────────────


class TestClusterIntoEpisodes:
    def test_single_prompt(self):
        p = _make_prompt()
        episodes = cluster_into_episodes([p])
        assert len(episodes) == 1
        assert len(episodes[0]) == 1

    def test_same_session_same_episode(self):
        p1 = _make_prompt(timestamp="2026-03-01T10:00:00Z", prompt_index=0)
        p2 = _make_prompt(timestamp="2026-03-01T10:05:00Z", prompt_index=1)
        episodes = cluster_into_episodes([p1, p2])
        assert len(episodes) == 1
        assert len(episodes[0]) == 2

    def test_large_time_gap_splits_episode(self):
        p1 = _make_prompt(timestamp="2026-03-01T10:00:00Z", prompt_index=0)
        p2 = _make_prompt(timestamp="2026-03-03T10:00:00Z", prompt_index=1)
        episodes = cluster_into_episodes([p1, p2], gap_hours=24.0)
        assert len(episodes) == 2

    def test_different_projects_separate_episodes(self):
        p1 = _make_prompt(project_slug="project-a", timestamp="2026-03-01T10:00:00Z")
        p2 = _make_prompt(project_slug="project-b", timestamp="2026-03-01T10:01:00Z")
        episodes = cluster_into_episodes([p1, p2])
        assert len(episodes) == 2

    def test_no_timestamps_same_session(self):
        p1 = _make_prompt(timestamp=None, prompt_index=0)
        p2 = _make_prompt(timestamp=None, prompt_index=1)
        episodes = cluster_into_episodes([p1, p2])
        assert len(episodes) == 1

    def test_empty_list(self):
        assert cluster_into_episodes([]) == []

    def test_different_sessions_within_gap(self):
        p1 = _make_prompt(
            session_id="s1", timestamp="2026-03-01T10:00:00Z", prompt_index=0,
        )
        p2 = _make_prompt(
            session_id="s2", timestamp="2026-03-01T11:00:00Z", prompt_index=0,
        )
        episodes = cluster_into_episodes([p1, p2], gap_hours=24.0)
        # Same project, within gap — should be one episode
        assert len(episodes) == 1

    def test_custom_gap_hours(self):
        p1 = _make_prompt(timestamp="2026-03-01T10:00:00Z")
        p2 = _make_prompt(timestamp="2026-03-01T13:00:00Z", prompt_index=1)
        # 3 hour gap, threshold at 2 hours
        episodes = cluster_into_episodes([p1, p2], gap_hours=2.0)
        assert len(episodes) == 2


# ── assign_threads ─────────────────────────────────────────────


class TestAssignThreads:
    def test_assigns_thread_id(self):
        p = _make_prompt()
        episodes = [[p]]
        thread_map = assign_threads(episodes)
        assert len(thread_map) == 1
        assert p.threading.thread_id != ""
        assert p.threading.thread_label != ""

    def test_thread_label_contains_slug(self):
        p = _make_prompt(project_slug="meta-organvm/engine")
        episodes = [[p]]
        assign_threads(episodes)
        assert "meta-organvm/engine" in p.threading.thread_label

    def test_thread_label_contains_verb(self):
        p = _make_prompt(imperative_verb="deploy")
        episodes = [[p]]
        assign_threads(episodes)
        assert "deploy" in p.threading.thread_label

    def test_multiple_episodes_distinct_ids(self):
        p1 = _make_prompt(project_slug="proj-a")
        p2 = _make_prompt(project_slug="proj-b")
        episodes = [[p1], [p2]]
        thread_map = assign_threads(episodes)
        assert len(thread_map) == 2
        assert p1.threading.thread_id != p2.threading.thread_id

    def test_empty_episode_skipped(self):
        thread_map = assign_threads([[]])
        assert len(thread_map) == 0

    def test_dominant_verb_selection(self):
        prompts = [
            _make_prompt(imperative_verb="create", prompt_index=0),
            _make_prompt(imperative_verb="create", prompt_index=1),
            _make_prompt(imperative_verb="fix", prompt_index=2),
        ]
        episodes = [prompts]
        assign_threads(episodes)
        assert "create" in prompts[0].threading.thread_label

    def test_date_range_in_label(self):
        p1 = _make_prompt(timestamp="2026-03-01T10:00:00Z", prompt_index=0)
        p2 = _make_prompt(timestamp="2026-03-05T10:00:00Z", prompt_index=1)
        episodes = [[p1, p2]]
        assign_threads(episodes)
        label = p1.threading.thread_label
        assert "2026-03-01" in label
        assert "2026-03-05" in label


# ── assign_arc_positions ───────────────────────────────────────


class TestAssignArcPositions:
    def _make_episode(self, n: int, types: list[str] | None = None) -> list[AnnotatedPrompt]:
        types = types or ["command"] * n
        return [
            _make_prompt(prompt_type=types[i], prompt_index=i)
            for i in range(n)
        ]

    def test_single_prompt(self):
        ep = self._make_episode(1)
        assign_arc_positions([ep])
        # Single prompt in episode
        assert ep[0].threading.arc_position in ("setup", "development")

    def test_opening_is_setup(self):
        ep = self._make_episode(20)
        assign_arc_positions([ep])
        assert ep[0].threading.arc_position == "setup"

    def test_late_is_resolution_or_maintenance(self):
        ep = self._make_episode(20)
        assign_arc_positions([ep])
        assert ep[-1].threading.arc_position in ("resolution", "maintenance")

    def test_middle_is_development(self):
        ep = self._make_episode(10)
        assign_arc_positions([ep])
        assert ep[5].threading.arc_position == "development"

    def test_plan_invocation_is_setup(self):
        ep = self._make_episode(10, ["plan_invocation"] + ["command"] * 9)
        assign_arc_positions([ep])
        assert ep[0].threading.arc_position == "setup"

    def test_late_git_ops_is_resolution(self):
        types = ["command"] * 9 + ["git_ops"]
        ep = self._make_episode(10, types)
        assign_arc_positions([ep])
        assert ep[9].threading.arc_position == "resolution"

    def test_empty_episode_no_crash(self):
        assign_arc_positions([[]])


# ── classify_arc_pattern ───────────────────────────────────────


class TestClassifyArcPattern:
    def test_single_shot_short(self):
        ep = [_make_prompt(), _make_prompt(prompt_index=1)]
        assert classify_arc_pattern(ep) == "single-shot"

    def test_plan_then_execute(self):
        types = ["plan_invocation"] + ["command"] * 4
        ep = [
            _make_prompt(prompt_type=t, prompt_index=i)
            for i, t in enumerate(types)
        ]
        assert classify_arc_pattern(ep) == "plan-then-execute"

    def test_iterative_correction(self):
        types = ["command", "correction", "command", "correction", "correction"]
        ep = [
            _make_prompt(prompt_type=t, prompt_index=i)
            for i, t in enumerate(types)
        ]
        assert classify_arc_pattern(ep) == "iterative-correction"

    def test_exploration_first(self):
        types = ["question"] + ["command"] * 4
        ep = [
            _make_prompt(prompt_type=t, prompt_index=i)
            for i, t in enumerate(types)
        ]
        assert classify_arc_pattern(ep) == "exploration-first"

    def test_steady_build(self):
        types = ["command"] * 5
        ep = [
            _make_prompt(prompt_type=t, prompt_index=i)
            for i, t in enumerate(types)
        ]
        assert classify_arc_pattern(ep) == "steady-build"

    def test_empty_returns_single_shot(self):
        assert classify_arc_pattern([]) == "single-shot"
