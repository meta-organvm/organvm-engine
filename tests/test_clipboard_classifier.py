"""Tests for clipboard prompt classifier."""

from __future__ import annotations

from organvm_engine.prompts.clipboard.classifier import (
    categorize,
    classify_as_prompt,
    compute_confidence,
    compute_content_hash,
    compute_word_count,
    has_multiple_md_headers,
    is_bullet_heavy,
    is_file_path_only,
    is_url_only,
    looks_like_code_block,
)
from organvm_engine.prompts.clipboard.schema import ClipboardItem


def _item(text: str, app: str = "Claude", bundle_id: str = "com.anthropic.claude") -> ClipboardItem:
    return ClipboardItem(
        id=1, app=app, bundle_id=bundle_id,
        timestamp="2025-01-15T10:00:00", date="2025-01-15", time="10:00:00",
        text=text,
    )


class TestClassifyAsPrompt:
    def test_imperative_opener_from_ai_app(self):
        item = _item("Create a Python function that validates email addresses")
        is_prompt, signals = classify_as_prompt(item)
        assert is_prompt
        assert "imperative_opener" in signals

    def test_question_form(self):
        item = _item("How do I configure ruff for a new project?")
        is_prompt, signals = classify_as_prompt(item)
        assert is_prompt
        assert "question_form" in signals

    def test_url_only_rejected(self):
        item = _item("https://github.com/example/repo")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["url_only"]

    def test_file_path_only_rejected(self):
        item = _item("/Users/test/Workspace/project/src/main.py")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["filepath_only"]

    def test_terminal_noise_rejected(self):
        item = _item("╭─ some terminal output ─╮\n│ content │")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["terminal_noise"]

    def test_bare_shell_command_rejected(self):
        # Bare shell commands (single-line, no newline) are rejected
        # The regex requires the command keyword + space + whitespace (e.g. "python3 -m ...")
        item = _item("python3  -m pytest tests/ -v", app="VSCode", bundle_id="com.vscode")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["bare_shell"]

    def test_terminal_no_opener_rejected(self):
        # Terminal items without imperative/question opener are rejected
        item = _item("some random terminal output text here", app="Terminal", bundle_id="com.apple.Terminal")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["terminal_no_opener"]

    def test_code_start_from_non_ai_app(self):
        item = _item("import os\nimport sys\nprint('hello')", app="VSCode", bundle_id="com.vscode")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["code_start"]

    def test_code_start_from_ai_app_accepted(self):
        # AI app code is kept (user may have pasted code as prompt context)
        item = _item("import os\nExplain what this module does")
        is_prompt, signals = classify_as_prompt(item)
        assert is_prompt

    def test_ai_response_rejected(self):
        item = _item(
            "Here's how you can implement that:\n" + "x" * 300,
            app="Safari", bundle_id="com.apple.Safari",
        )
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["ai_response"]

    def test_too_large_rejected(self):
        item = _item("x" * 25000)
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["too_large"]

    def test_finder_rejected(self):
        item = _item("some selection text with enough chars", app="Finder", bundle_id="com.apple.finder")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["finder_selection"]

    def test_too_short_without_strong_signal(self):
        item = _item("ok", app="Notes", bundle_id="com.apple.Notes")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["too_short"]

    def test_ai_context_marker(self):
        item = _item("Given the following code, explain the bug:\ndef foo(): pass")
        is_prompt, signals = classify_as_prompt(item)
        assert is_prompt
        assert "ai_context_marker" in signals

    def test_body_instructional(self):
        item = _item("Here is the task. We need to implement the new feature and deploy it.")
        is_prompt, signals = classify_as_prompt(item)
        assert is_prompt
        assert "body_instructional" in signals

    def test_browser_prompt(self):
        item = _item(
            "How do I set up a Next.js project with TypeScript?",
            app="Chrome", bundle_id="com.google.chrome",
        )
        is_prompt, signals = classify_as_prompt(item)
        assert is_prompt
        assert "browser_prompt" in signals

    def test_env_exports_only_rejected(self):
        item = _item("export FOO=bar\nexport BAZ=qux\nexport HELLO=world")
        is_prompt, signals = classify_as_prompt(item)
        assert not is_prompt
        assert signals == ["env_exports_only"]


class TestCategorize:
    def test_blockchain_category(self):
        assert categorize("Deploy the Solana smart contract on devnet") == "Blockchain/Truth"

    def test_organvm_category(self):
        assert categorize("Update the organvm registry with new seed.yaml") == "ORGANVM System"

    def test_general_fallback(self):
        assert categorize("Hello world, this is a generic text") == "General AI Usage"

    def test_highest_score_wins(self):
        # Multiple blockchain keywords should win over a single github keyword
        text = "Deploy the Solana anchor smart contract on the blockchain ledger"
        assert categorize(text) == "Blockchain/Truth"


class TestHelpers:
    def test_compute_word_count(self):
        assert compute_word_count("hello world foo bar") == 4

    def test_compute_content_hash_deterministic(self):
        h1 = compute_content_hash("hello world")
        h2 = compute_content_hash("hello world")
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_content_hash_normalizes_whitespace(self):
        h1 = compute_content_hash("hello   world")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_is_url_only(self):
        assert is_url_only("https://example.com")
        assert not is_url_only("check https://example.com")

    def test_is_file_path_only(self):
        assert is_file_path_only("/usr/local/bin/python3")
        assert is_file_path_only("~/Workspace/project/file.py")
        assert not is_file_path_only("Look at /usr/local/bin")

    def test_has_multiple_md_headers(self):
        text = "# H1\n## H2\n### H3\nsome text"
        assert has_multiple_md_headers(text)
        assert not has_multiple_md_headers("# Just one header\ntext")

    def test_is_bullet_heavy(self):
        text = "- item 1\n- item 2\n- item 3\n- item 4\n- item 5"
        assert is_bullet_heavy(text)
        text2 = "line 1\nline 2\nline 3\nline 4"
        assert not is_bullet_heavy(text2)

    def test_looks_like_code_block(self):
        text = "    line 1\n    line 2\n    line 3\n    line 4"
        assert looks_like_code_block(text)

    def test_compute_confidence_high(self):
        item = _item("test")
        assert compute_confidence(item, ["a", "b", "c"]) == "high"

    def test_compute_confidence_medium(self):
        item = _item("test", app="Notes", bundle_id="com.apple.Notes")
        assert compute_confidence(item, ["a", "b"]) == "medium"

    def test_compute_confidence_low(self):
        item = _item("test", app="Notes", bundle_id="com.apple.Notes")
        assert compute_confidence(item, ["a"]) == "low"
