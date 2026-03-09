"""Prompt classification — type, size, signals, and verb extraction."""

from __future__ import annotations

import re

from organvm_engine.plans.atomizer import (
    BACKTICK_PATH_RE,
    STANDALONE_PATH_RE,
)

# ── Prompt type detection (first-match cascade) ──────────────────

GIT_OPS_RE = re.compile(
    r"^(stage|commit|push|merge|rebase)\b|"
    r"\bgit\s+(add|commit|push|pull)\b|"
    r"\bstage\s+all\b",
    re.IGNORECASE,
)

PLAN_INVOCATION_RE = re.compile(
    r"implement the following plan|"
    r"planContent|"
    r"^#\s+Plan:",
    re.IGNORECASE,
)

CONTINUATION_STARTERS = re.compile(
    r"^(now|also|next|then|continue|proceed|ok|go ahead|yes|do it|"
    r"looks good|perfect|great|sounds good|that works|approved|lgtm)\b",
    re.IGNORECASE,
)

CORRECTION_RE = re.compile(
    r"^(no|wait|actually|instead|revert|undo|rollback|stop)\b|"
    r"that's wrong|not what i|that broke|you didn't",
    re.IGNORECASE,
)

QUESTION_STARTERS = re.compile(
    r"^(what|how|why|where|when|which|is|are|can|could|should|does|do|will|would)\b",
    re.IGNORECASE,
)

CONTEXT_SETTING_RE = re.compile(
    r"this session is|the goal is|background:|context:",
    re.IGNORECASE,
)

EXPLORATION_RE = re.compile(
    r"\b(look at|explore|investigate|show me|what's in|find|search|check)\b",
    re.IGNORECASE,
)

CREATION_VERBS_RE = re.compile(
    r"\b(create|implement|build|add|write|generate|make)\b",
    re.IGNORECASE,
)

# ── Imperative verb extraction ───────────────────────────────────

POLITE_PREFIX_RE = re.compile(
    r"^(?:please\s+|can you\s+|could you\s+|let's\s+|let us\s+)",
    re.IGNORECASE,
)

IMPERATIVE_VERBS = {
    "implement", "create", "add", "fix", "update", "remove", "delete",
    "stage", "commit", "deploy", "test", "run", "explore", "check",
    "build", "write", "refactor", "move", "rename", "install", "configure",
    "push", "merge", "rebase", "pull", "set", "make", "change", "show",
    "list", "find", "search", "read", "review", "analyze", "generate",
    "extract", "parse", "validate", "verify", "clean", "organize", "debug",
    "investigate", "upgrade", "migrate", "wire", "export", "import",
    "scaffold", "initialize", "init", "setup", "start", "stop", "restart",
    "enable", "disable", "open", "close", "fetch", "send", "sync",
    "restore", "reset", "apply", "render", "compile", "format", "lint",
    "annotate", "document", "log", "monitor", "profile", "benchmark",
    "proceed", "continue",
}

# ── Tool mentions ────────────────────────────────────────────────

KNOWN_TOOLS = [
    "git", "pytest", "ruff", "npm", "yarn", "pnpm", "bun", "deno",
    "docker", "cargo", "pip", "poetry", "uv", "brew", "homebrew",
    "make", "cmake", "go", "rustup", "terraform", "kubectl",
    "playwright", "cypress", "vitest", "jest", "eslint", "prettier",
    "mypy", "pyright", "black", "isort", "flake8", "bandit",
    "gh", "curl", "wget", "jq", "sed", "awk", "grep", "find",
    "node", "python", "ruby", "tsc", "tsx", "esbuild", "vite",
    "next", "astro", "vercel", "netlify", "cloudflare", "wrangler",
]


def classify_prompt_type(text: str, prompt_index: int) -> str:
    """Classify prompt type using first-match cascade."""
    stripped = text.strip()

    if GIT_OPS_RE.search(stripped):
        return "git_ops"

    if PLAN_INVOCATION_RE.search(stripped):
        return "plan_invocation"

    if prompt_index > 0 and CONTINUATION_STARTERS.match(stripped):
        return "continuation"

    if CORRECTION_RE.search(stripped):
        return "correction"

    if stripped.rstrip().endswith("?") or QUESTION_STARTERS.match(stripped):
        return "question"

    if CONTEXT_SETTING_RE.search(stripped):
        return "context_setting"
    if len(stripped) > 1000 and not _has_imperative_opening(stripped):
        return "context_setting"

    if EXPLORATION_RE.search(stripped) and not CREATION_VERBS_RE.search(stripped):
        return "exploration"

    return "command"


def classify_size(char_count: int) -> str:
    """Classify prompt by character count."""
    if char_count < 50:
        return "terse"
    if char_count < 200:
        return "short"
    if char_count < 2000:
        return "medium"
    return "long"


def classify_session_position(index: int, total: int) -> str:
    """Classify position within session."""
    if total <= 1:
        return "only"
    if index == 0:
        return "opening"
    if index == total - 1:
        return "closing"
    pct = index / total
    if pct < 0.2:
        return "early"
    if pct > 0.8:
        return "late"
    return "middle"


def extract_imperative_verb(text: str) -> str:
    """Extract the first imperative verb from text."""
    first_line = text.strip().split("\n")[0]
    cleaned = POLITE_PREFIX_RE.sub("", first_line).strip()
    first_word = cleaned.split()[0].lower().rstrip(".,;:!?") if cleaned.split() else ""
    if first_word in IMPERATIVE_VERBS:
        return first_word
    return ""


def extract_opening_phrase(text: str) -> str:
    """Extract the first 5 words as opening phrase."""
    words = text.strip().split()[:5]
    return " ".join(w.lower() for w in words) if words else ""


def extract_file_mentions(text: str) -> list[str]:
    """Extract file path mentions from text."""
    files: list[str] = []
    seen: set[str] = set()

    for pattern in (BACKTICK_PATH_RE, STANDALONE_PATH_RE):
        for m in pattern.finditer(text):
            path = m.group(1)
            if path not in seen and not path.startswith("http"):
                seen.add(path)
                files.append(path)

    return files


def extract_tool_mentions(text: str) -> list[str]:
    """Extract mentions of known tools."""
    lower = text.lower()
    found = []
    for tool in KNOWN_TOOLS:
        pattern = re.escape(tool)
        if re.search(rf"(?:^|[\s`/.,;:(]){pattern}(?:$|[\s`/.,;:)])", lower):
            found.append(tool)
    return found


def _has_imperative_opening(text: str) -> bool:
    """Check if text starts with an imperative verb."""
    first_line = text.strip().split("\n")[0]
    cleaned = POLITE_PREFIX_RE.sub("", first_line).strip()
    first_word = cleaned.split()[0].lower().rstrip(".,;:!?") if cleaned.split() else ""
    return first_word in IMPERATIVE_VERBS
