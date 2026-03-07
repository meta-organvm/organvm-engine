"""Classify clipboard items as AI prompts and categorize them."""

from __future__ import annotations

import hashlib
import re

from organvm_engine.prompts.clipboard.schema import ClipboardItem, ClipboardPrompt

# ── Categories ──────────────────────────────────────────────────────────────

CATEGORIES: dict[str, list[str]] = {
    "Blockchain/Truth": [
        "blockchain", "truth machine", "wager", "escrow", "solana",
        "anchor", "ledger", "perpetual", "defi", "futures",
        "smart contract", "on-chain", "web3", "token",
    ],
    "Portfolio/Career": [
        "portfolio", "4444j99", "resume", "cv ", " cv,", "job search",
        "interview", "career", "hiring", "recruiter", "linkedin",
    ],
    "ORGANVM System": [
        "organvm", "organ-", "registry", "seed.yaml", "conductor",
        "governance", "corpvs", "promotion", "eight-organ", "world root",
        "theoria", "poiesis", "ergon", "taxis", "logos", "koinonia",
        "kerygma",
    ],
    "Adaptive Syllabus/Education": [
        "syllabus", "koinonia", "learning", "curriculum", "enc1101",
        "pedagogy", "course", "student", "assignment", "rubric",
        "semester", "class ",
    ],
    "Modular Synthesis/Audio": [
        "eurorack", "module", "cv bus", "domain router", "rack",
        "firmware", "synthesis", "oscillator", "vcf", "vca",
        "midi", "daw", "audio", "patch",
    ],
    "MCP/Tooling": [
        "mcp", "mcp server", "tool server", "orchestrat",
        "claude code", "skill", "claude-in-chrome",
    ],
    "GitHub/CI/CD": [
        "github", "workflow", "deploy", "pull request", " pr ",
        "actions", "ci/cd", "pipeline", "ci ", "release",
        "branch", "merge",
    ],
    "Regulatory/Legal": [
        "cftc", "gdpr", "compliance", "kyc", "legal", "regulation",
        "regulatory", "lawsuit", "discovery", "deposition",
        "litigation", "counsel", "attorney",
    ],
    "Creative/Art": [
        "generative art", "sacred geometry", "p5.js", "three.js",
        "canvas", "visual", "algorithmic", "procedural",
        "animation", "shader", "webgl",
    ],
    "Writing/Content": [
        "essay", "blog", "article", "draft", "editorial",
        "narrative", "writing", "prose", "publish",
    ],
    "Data/Research": [
        "dataset", "ingest", "scrape", "extract", "parse",
        "research", "analysis", "ETL", "pipeline",
    ],
    "Infrastructure/DevOps": [
        "docker", "kubernetes", "terraform", "gcloud", "aws",
        "server", "dns", "ssl", "nginx", "cloudflare",
        "vercel", "netlify", "homebrew",
    ],
    "Personal/Life": [
        "apartment", "lease", "rent", "insurance", "medical",
        "doctor", "pharmacy", "bank", "budget", "tax",
        "moving", "travel",
    ],
}

# ── App sets ────────────────────────────────────────────────────────────────

AI_INPUT_APPS = {
    "Claude", "ChatGPT", "Gemini", "Codex", "Copilot", "Perplexity",
    "Jules", "Antigravity", "Comet",
}

AUTHORING_APPS = {
    "Stickies", "Notes", "TextEdit", "Mail", "Messages",
    "loginwindow",
}

AI_BUNDLE_IDS = {
    "com.openai.chat", "com.anthropic.claude",
    "com.google.android.apps.bard",
}

BROWSER_BUNDLE_IDS = {
    "com.google.chrome", "com.apple.Safari", "org.mozilla.firefox",
    "company.thebrowser.Browser", "com.microsoft.edgemac",
}

TERMINAL_APPS = {"Terminal", "Warp", "kitty", "iTerm2"}

# ── Regex patterns ──────────────────────────────────────────────────────────

IMPERATIVE_FIRST_LINE = re.compile(
    r"^(implement|create|build|analyze|review|explain|write|design|fix|add|"
    r"convert|refactor|execute|ingest|devise|generate|configure|set up|setup|"
    r"install|deploy|update|remove|delete|migrate|extract|list|show|find|"
    r"search|compare|merge|split|optimize|debug|test|check|verify|validate|"
    r"plan|outline|summarize|describe|define|map|connect|integrate|automate|"
    r"make|run|parse|fetch|pull|push|apply|emit|compose|scaffold|bootstrap|"
    r"transform|encode|decode|compile|render|expose|wrap|mount|unmount|"
    r"rewrite|rework|restructure|reorganize|rename|move|copy|clone|fork|"
    r"fold|tighten|polish|clean|draft|prepare|provision|register|"
    r"give me|tell me|help me|can you|could you|would you|please|i want|"
    r"i need|let'?s|we need|we should|how do|how to|how can|what is|what are|"
    r"why does|why is|is there|do you|does this|use the|take the|look at|"
    r"go through|walk me|figure out|come up with|put together|break down|"
    r"set the|change the|modify the|adjust the|tweak the|turn the|open the|"
    r"close the|start the|stop the|read the|load the|save the|export the|"
    r"import the|send the|get the|grab the|try |ensure|now )",
    re.IGNORECASE,
)

QUESTION_FIRST_LINE = re.compile(
    r"^(how |what |why |where |when |which |can |could |would |should |"
    r"is it |is this |are there |do you |does |will |have you |"
    r"has |did |were |was )",
    re.IGNORECASE,
)

AI_CONTEXT_MARKERS = re.compile(
    r"(given the|based on|using the context|here is the|here are the|"
    r"the following|consider the|assume that|suppose that|"
    r"you are a|act as|pretend you|your role|system prompt|"
    r"<context>|<instructions>|<task>|ROLE:|CONTEXT:|TASK:)",
    re.IGNORECASE,
)

BODY_INSTRUCTIONAL = re.compile(
    r"(need to|should |want to|make sure|we need|i need|"
    r"let'?s |plan |todo|to-do|priority|step \d|"
    r"implement|deploy|configure|set up|integrate|"
    r"full speed|autonomous|operational by|"
    r"launch|execute|provision|register|"
    r"assigned workstream|workstream)",
    re.IGNORECASE,
)

CODE_STARTS = re.compile(
    r"^(\{|\[|import |from \w+ import|//|#!|<!DOCTYPE|<div|<html|<\?xml|"
    r"package |const |let |var |function |class \w|def \w|pub |fn \w|"
    r"export (default |{)|require\(|@import|@charset|"
    r"BEGIN|CREATE TABLE|SELECT |INSERT |ALTER |DROP |GRANT |"
    r"using |namespace |#include|#pragma|"
    r"<script|<style|<link |<meta )",
)

TERMINAL_NOISE = re.compile(r"[╭╮╰╯│─┌┐└┘]|❯|\x1b\[|\[0m|\[1m|\[0;")

BARE_SHELL_CMD = re.compile(
    r"^(python3?|pip3?|npm|npx|yarn|pnpm|bun|cargo|go |git |docker |"
    r"kubectl |brew |curl |wget |ssh |scp |rsync |chmod |chown |mkdir |"
    r"rm |cp |mv |cat |ls |cd |source |eval |echo |printf |sed |awk |"
    r"grep |find |tar |zip |unzip |make |cmake |gcc |clang |rustc |"
    r"node |deno |sudo |env |export |which |type |man |head |tail |"
    r"wc |sort |uniq |xargs |tee |touch |ln |df |du |ps |kill |"
    r"gcloud |gh |sqlite3 |uvicorn |flask |gunicorn |"
    r"top |htop |open |pbcopy|pbpaste)\s",
    re.IGNORECASE,
)

AI_RESPONSE_OPENERS = re.compile(
    r"^(here'?s |i'?ll |let me |sure[,!]|of course|absolutely|great |"
    r"certainly|i understand|i can help|i'?d be happy|thank you|"
    r"you'?re welcome|no problem|that'?s a great|based on my|"
    r"as an ai|i don'?t have|you(?:'?re| are) (right|correct)|"
    r"good (question|point)|to (answer|address|summarize)|"
    r"the (error|issue|problem|solution|answer|result|output) )",
    re.IGNORECASE,
)

MULTILINE_SHELL = re.compile(
    r"^(export \w+=|source |eval |#!/|set -[euo])",
)

TECH_PATTERN = re.compile(
    r"\b(python|typescript|javascript|rust|go|swift|react|next\.?js|"
    r"node\.?js|docker|kubernetes|terraform|postgres|sqlite|redis|"
    r"github|vercel|netlify|cloudflare|gcloud|aws|supabase|neon|"
    r"playwright|pytest|vitest|jest|tailwind|css|html|json|yaml|"
    r"openai|anthropic|claude|gemini|gpt|llm|mcp|"
    r"solana|anchor|ethereum|web3|"
    r"p5\.?js|three\.?js|webgl|canvas|"
    r"eurorack|midi|daw)\b",
    re.IGNORECASE,
)

# ── Helper functions ────────────────────────────────────────────────────────


def has_multiple_md_headers(text: str) -> bool:
    return len(re.findall(r"^#{1,3} ", text, re.MULTILINE)) >= 3


def is_bullet_heavy(text: str) -> bool:
    lines = text.strip().split("\n")
    if len(lines) < 4:
        return False
    bullet_lines = sum(1 for line in lines if re.match(r"^\s*[-*\u2022]\s", line))
    return bullet_lines / len(lines) > 0.5


def looks_like_code_block(text: str) -> bool:
    lines = text.strip().split("\n")
    if len(lines) < 3:
        return False
    code_lines = sum(
        1 for line in lines
        if line.startswith("    ") or line.startswith("\t") or line.startswith("```")
    )
    return code_lines / len(lines) > 0.6


def is_url_only(text: str) -> bool:
    return bool(re.match(r"^https?://\S+$", text.strip()))


def is_file_path_only(text: str) -> bool:
    t = text.strip()
    return len(t) < 300 and bool(re.match(r"^[/~$][\w/.@\-{}$]+$", t))


def is_ai_app(item: ClipboardItem) -> bool:
    return item.app in AI_INPUT_APPS or item.bundle_id in AI_BUNDLE_IDS


def is_authoring_app(item: ClipboardItem) -> bool:
    return item.app in AUTHORING_APPS


def is_browser(item: ClipboardItem) -> bool:
    return item.bundle_id in BROWSER_BUNDLE_IDS


def is_only_env_exports(text: str) -> bool:
    """Text that is purely export VAR=... lines (shell env setup, not a prompt)."""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if not lines:
        return True
    export_lines = sum(1 for line in lines if re.match(r"^(export \w+=|#|$)", line))
    return len(lines) > 1 and export_lines / len(lines) > 0.7


def compute_confidence(item: ClipboardItem, signals: list[str]) -> str:
    """Return high/medium/low confidence based on accumulated signals."""
    score = len(signals)
    if is_ai_app(item):
        score += 2
    if score >= 3:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


# ── Classification ──────────────────────────────────────────────────────────


def classify_as_prompt(item: ClipboardItem) -> tuple[bool, list[str]]:
    """Classify whether a clipboard item is an AI prompt.

    Returns:
        (is_prompt, list_of_matching_signals_or_rejection_reasons)
    """
    text = item.text
    lines = text.split("\n")
    first_line = lines[0].strip()
    tlen = len(text)
    signals: list[str] = []

    is_terminal = item.app in TERMINAL_APPS

    # ── Hard negatives ──
    if is_url_only(text):
        return False, ["url_only"]
    if is_file_path_only(text):
        return False, ["filepath_only"]
    if TERMINAL_NOISE.search(text[:500]):
        return False, ["terminal_noise"]
    if is_only_env_exports(text):
        return False, ["env_exports_only"]
    if tlen > 20000:
        return False, ["too_large"]
    if item.app == "Finder":
        return False, ["finder_selection"]
    if "\n" not in text.strip() and BARE_SHELL_CMD.match(first_line):
        return False, ["bare_shell"]
    if MULTILINE_SHELL.match(first_line) and tlen < 500:
        shell_lines = sum(
            1 for line in lines
            if BARE_SHELL_CMD.match(line.strip()) or MULTILINE_SHELL.match(line.strip())
            or not line.strip()
        )
        if shell_lines / len(lines) > 0.7:
            return False, ["shell_script"]
    if is_terminal:
        has_login_banner = "Last login:" in text[:100]
        has_prompt_char = "%" in first_line or "$" in first_line
        if has_login_banner or has_prompt_char:
            return False, ["terminal_banner"]
    if CODE_STARTS.match(first_line) and not is_ai_app(item) and not is_authoring_app(item):
        return False, ["code_start"]
    if AI_RESPONSE_OPENERS.match(first_line) and tlen > 200:
        return False, ["ai_response"]
    if has_multiple_md_headers(text) and tlen > 500 and not is_ai_app(item):
        return False, ["md_headers"]
    if is_bullet_heavy(text) and tlen > 800 and not is_ai_app(item):
        return False, ["bullet_heavy"]
    if looks_like_code_block(text) and not is_ai_app(item):
        return False, ["code_block"]

    # ── Positive signals ──
    if IMPERATIVE_FIRST_LINE.match(first_line):
        signals.append("imperative_opener")
    if QUESTION_FIRST_LINE.match(first_line):
        signals.append("question_form")
    if AI_CONTEXT_MARKERS.search(text[:500]):
        signals.append("ai_context_marker")
    if BODY_INSTRUCTIONAL.search(text):
        signals.append("body_instructional")
    if is_ai_app(item):
        signals.append("ai_app")
    if (
        is_authoring_app(item)
        and tlen > 40
        and (BODY_INSTRUCTIONAL.search(text) or IMPERATIVE_FIRST_LINE.match(first_line))
    ):
        signals.append("authoring_app_instructional")
    if (
        is_browser(item)
        and 30 < tlen < 3000
        and not has_multiple_md_headers(text)
        and not is_bullet_heavy(text)
        and (IMPERATIVE_FIRST_LINE.match(first_line) or QUESTION_FIRST_LINE.match(first_line))
    ):
        signals.append("browser_prompt")
    if is_terminal:
        has_first_line_signal = (
            "imperative_opener" in signals or "question_form" in signals
        )
        if not has_first_line_signal:
            return False, ["terminal_no_opener"]

    # ── Decision ──
    if tlen < 30:
        if "ai_app" in signals and len(signals) >= 2:
            return True, signals
        return False, ["too_short"]
    if signals:
        return True, signals
    if (
        is_ai_app(item)
        and tlen < 3000
        and not has_multiple_md_headers(text)
        and not is_bullet_heavy(text)
    ):
        return True, ["ai_app_fallback"]

    return False, ["no_signal"]


# ── Categorization ──────────────────────────────────────────────────────────


def categorize(text: str) -> str:
    """Assign the best-matching category based on keyword frequency."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for cat, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=lambda k: scores[k])
    return "General AI Usage"


def compute_word_count(text: str) -> int:
    return len(text.split())


def compute_content_hash(text: str) -> str:
    """Normalize and hash for dedup."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def build_prompt_record(item: ClipboardItem, signals: list[str]) -> ClipboardPrompt:
    """Build a classified prompt record from a raw clipboard item."""
    text = item.text
    category = categorize(text)
    content_hash = compute_content_hash(text)
    confidence = compute_confidence(item, signals)
    word_count = compute_word_count(text)

    is_multi_turn = bool(re.search(r"\n---\n|\n\n(Human|User|Assistant|AI):", text))

    file_refs = re.findall(r"(?:^|\s)([~/](?:\w[\w\-.]*/)[\w\-./]+\.\w{1,10})\b", text)
    file_refs = list(dict.fromkeys(file_refs))[:10]

    techs = list(dict.fromkeys(m.lower() for m in TECH_PATTERN.findall(text)))

    return ClipboardPrompt(
        id=item.id,
        content_hash=content_hash,
        date=item.date,
        time=item.time,
        timestamp=item.timestamp,
        source_app=item.app,
        bundle_id=item.bundle_id,
        category=category,
        confidence=confidence,
        signals=signals,
        word_count=word_count,
        char_count=len(text),
        multi_turn=is_multi_turn,
        file_refs=file_refs,
        tech_mentions=techs,
        text=text,
    )
