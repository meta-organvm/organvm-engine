"""Tests for prompts/classifier.py — prompt type classification and signal extraction."""


from organvm_engine.prompts.classifier import (
    classify_prompt_type,
    classify_session_position,
    classify_size,
    extract_file_mentions,
    extract_imperative_verb,
    extract_opening_phrase,
    extract_tool_mentions,
)

# ── classify_prompt_type ──────────────────────────────────────────


class TestClassifyPromptType:
    def test_git_ops_stage(self):
        assert classify_prompt_type("stage all changes", 0) == "git_ops"

    def test_git_ops_commit(self):
        assert classify_prompt_type("git commit -m 'fix bug'", 0) == "git_ops"

    def test_git_ops_push(self):
        assert classify_prompt_type("push to remote", 0) == "git_ops"

    def test_git_ops_merge(self):
        assert classify_prompt_type("merge feature branch", 0) == "git_ops"

    def test_plan_invocation(self):
        assert classify_prompt_type("implement the following plan:", 0) == "plan_invocation"

    def test_plan_invocation_planContent(self):
        assert classify_prompt_type("planContent: some plan data", 0) == "plan_invocation"

    def test_plan_invocation_heading(self):
        assert classify_prompt_type("# Plan: big refactor", 0) == "plan_invocation"

    def test_continuation_at_index_zero(self):
        # Continuation requires index > 0
        assert classify_prompt_type("now do the next step", 0) != "continuation"

    def test_continuation_at_index_nonzero(self):
        assert classify_prompt_type("now do the next step", 1) == "continuation"

    def test_continuation_yes(self):
        assert classify_prompt_type("yes", 2) == "continuation"

    def test_continuation_lgtm(self):
        assert classify_prompt_type("lgtm", 3) == "continuation"

    def test_continuation_go_ahead(self):
        assert classify_prompt_type("go ahead", 1) == "continuation"

    def test_correction(self):
        assert classify_prompt_type("no that's wrong, fix it", 1) == "correction"

    def test_correction_wait(self):
        assert classify_prompt_type("wait, actually do something else", 0) == "correction"

    def test_correction_undo(self):
        assert classify_prompt_type("undo that last change", 0) == "correction"

    def test_correction_revert(self):
        assert classify_prompt_type("revert the changes", 0) == "correction"

    def test_question_what(self):
        assert classify_prompt_type("what does this function do?", 0) == "question"

    def test_question_how(self):
        assert classify_prompt_type("how do I configure the CLI?", 0) == "question"

    def test_question_trailing_mark(self):
        assert classify_prompt_type("is this the right approach?", 0) == "question"

    def test_context_setting(self):
        assert classify_prompt_type("this session is about fixing registry bugs", 0) == "context_setting"

    def test_context_setting_background(self):
        assert classify_prompt_type("background: we need to refactor the CLI", 0) == "context_setting"

    def test_context_setting_long_text(self):
        long = "A" * 1200  # >1000 chars without imperative opening
        assert classify_prompt_type(long, 0) == "context_setting"

    def test_exploration(self):
        assert classify_prompt_type("look at the test directory", 0) == "exploration"

    def test_exploration_investigate(self):
        assert classify_prompt_type("investigate why tests fail", 0) == "exploration"

    def test_exploration_overridden_by_creation(self):
        # If both exploration and creation verbs present, not classified as exploration
        assert classify_prompt_type("look at the tests and create new ones", 0) == "command"

    def test_command_default(self):
        assert classify_prompt_type("implement the feature", 0) == "command"

    def test_command_simple(self):
        assert classify_prompt_type("add error handling to the parser", 0) == "command"

    def test_empty_string(self):
        result = classify_prompt_type("", 0)
        assert isinstance(result, str)

    def test_git_ops_priority_over_continuation(self):
        # git_ops comes before continuation in cascade
        assert classify_prompt_type("commit the changes", 1) == "git_ops"


# ── classify_size ────────────────────────────────────────────────


class TestClassifySize:
    def test_terse(self):
        assert classify_size(10) == "terse"

    def test_terse_boundary(self):
        assert classify_size(49) == "terse"

    def test_short(self):
        assert classify_size(50) == "short"

    def test_short_boundary(self):
        assert classify_size(199) == "short"

    def test_medium(self):
        assert classify_size(200) == "medium"

    def test_medium_boundary(self):
        assert classify_size(1999) == "medium"

    def test_long(self):
        assert classify_size(2000) == "long"

    def test_very_long(self):
        assert classify_size(50000) == "long"


# ── classify_session_position ─────────────────────────────────────


class TestClassifySessionPosition:
    def test_only(self):
        assert classify_session_position(0, 1) == "only"

    def test_opening(self):
        assert classify_session_position(0, 10) == "opening"

    def test_closing(self):
        assert classify_session_position(9, 10) == "closing"

    def test_early(self):
        assert classify_session_position(1, 10) == "early"

    def test_late(self):
        # 0.8 is boundary — > 0.8 is "late", so need index 9 in 11
        assert classify_session_position(9, 11) == "late"

    def test_middle(self):
        assert classify_session_position(5, 10) == "middle"


# ── extract_imperative_verb ───────────────────────────────────────


class TestExtractImperativeVerb:
    def test_simple_verb(self):
        assert extract_imperative_verb("create a new file") == "create"

    def test_polite_prefix(self):
        assert extract_imperative_verb("please fix the bug") == "fix"

    def test_can_you_prefix(self):
        assert extract_imperative_verb("can you update the config?") == "update"

    def test_lets_prefix(self):
        assert extract_imperative_verb("let's build the module") == "build"

    def test_no_verb(self):
        assert extract_imperative_verb("the system is broken") == ""

    def test_empty(self):
        assert extract_imperative_verb("") == ""

    def test_unknown_word(self):
        assert extract_imperative_verb("xyzzy something") == ""

    def test_verb_with_punctuation(self):
        assert extract_imperative_verb("deploy! now!") == "deploy"


# ── extract_opening_phrase ────────────────────────────────────────


class TestExtractOpeningPhrase:
    def test_basic(self):
        result = extract_opening_phrase("Please fix the broken test suite")
        assert result == "please fix the broken test"

    def test_short(self):
        result = extract_opening_phrase("fix it")
        assert result == "fix it"

    def test_empty(self):
        assert extract_opening_phrase("") == ""

    def test_caps_normalized(self):
        result = extract_opening_phrase("CREATE the New Feature NOW")
        assert result == "create the new feature now"


# ── extract_file_mentions ─────────────────────────────────────────


class TestExtractFileMentions:
    def test_backtick_path(self):
        result = extract_file_mentions("look at `src/main.py`")
        assert "src/main.py" in result

    def test_standalone_path(self):
        result = extract_file_mentions("edit src/organvm_engine/cli.py")
        assert any("cli.py" in f for f in result)

    def test_no_http(self):
        result = extract_file_mentions("see https://example.com/test.py")
        assert all(not f.startswith("http") for f in result)

    def test_no_paths(self):
        result = extract_file_mentions("just some text without paths")
        assert result == []

    def test_dedup(self):
        result = extract_file_mentions("`src/main.py` and also `src/main.py`")
        assert len([f for f in result if f == "src/main.py"]) == 1


# ── extract_tool_mentions ─────────────────────────────────────────


class TestExtractToolMentions:
    def test_git(self):
        assert "git" in extract_tool_mentions("run git status")

    def test_pytest(self):
        assert "pytest" in extract_tool_mentions("run pytest tests/")

    def test_ruff(self):
        assert "ruff" in extract_tool_mentions("check with ruff")

    def test_npm(self):
        assert "npm" in extract_tool_mentions("npm install the package")

    def test_multiple_tools(self):
        result = extract_tool_mentions("run ruff and then pytest")
        assert "ruff" in result
        assert "pytest" in result

    def test_no_tools(self):
        result = extract_tool_mentions("write some code")
        assert result == []

    def test_tool_in_backticks(self):
        result = extract_tool_mentions("use `docker` to build")
        assert "docker" in result
