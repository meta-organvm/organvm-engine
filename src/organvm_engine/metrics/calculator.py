"""Compute system-wide metrics from registry."""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter (between --- markers) from markdown text."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]
    return text


def _count_file_words(path: Path) -> int:
    """Count words in a single file, stripping frontmatter and HTML tags."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return 0
    text = _strip_frontmatter(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(text.split())


def count_words(workspace: Path) -> dict:
    """Count words across the workspace by category.

    Walks the filesystem to count words in READMEs, essays, corpus docs,
    and org profile READMEs.

    Args:
        workspace: Path to the workspace root (e.g. ~/Workspace).

    Returns:
        Dict with keys: readmes, essays, corpus, org_profiles, total.
    """
    from organvm_engine.organ_config import ORGANS

    readme_words = 0
    for organ_info in ORGANS.values():
        organ_dir = workspace / organ_info["dir"]
        if not organ_dir.is_dir():
            continue
        for entry in sorted(organ_dir.iterdir()):
            if not entry.is_dir():
                continue
            readme = entry / "README.md"
            if readme.is_file():
                readme_words += _count_file_words(readme)

    essay_words = 0
    essays_dir = workspace / "organvm-v-logos" / "public-process" / "_posts"
    if essays_dir.is_dir():
        for md in sorted(essays_dir.glob("*.md")):
            essay_words += _count_file_words(md)

    corpus_words = 0
    corpus_dir = workspace / "meta-organvm" / "organvm-corpvs-testamentvm" / "docs"
    if corpus_dir.is_dir():
        for md in sorted(corpus_dir.rglob("*.md")):
            corpus_words += _count_file_words(md)

    profile_words = 0
    for organ_info in ORGANS.values():
        profile = workspace / organ_info["dir"] / ".github" / "profile" / "README.md"
        if profile.is_file():
            profile_words += _count_file_words(profile)

    total = readme_words + essay_words + corpus_words + profile_words

    return {
        "readmes": readme_words,
        "essays": essay_words,
        "corpus": corpus_words,
        "org_profiles": profile_words,
        "total": total,
    }


def format_word_count(total: int) -> tuple[str, int, str]:
    """Format a word count into display strings.

    Display strings are rounded to the nearest 1K to reduce propagation
    churn — the numeric value stays precise.

    Args:
        total: Total word count.

    Returns:
        Tuple of (total_words, total_words_numeric, total_words_short).
        e.g. ("~842,000+", 842000, "842K+")
    """
    rounded = round(total, -3) if total >= 500 else total
    total_words = f"~{rounded:,}+"
    total_words_numeric = total
    k = rounded // 1000
    total_words_short = f"{k}K+"
    return total_words, total_words_numeric, total_words_short


_CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".tsx", ".jsx"}
_TEST_PATTERNS = {"test_", "_test.", ".test.", ".spec."}
_SKIP_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", ".tox", "dist", "build"}


def count_code_files(workspace: Path) -> dict:
    """Count code and test files across the workspace.

    Walks all organ directories counting source files by extension and
    identifying test files by naming convention.

    Args:
        workspace: Path to the workspace root (e.g. ~/Workspace).

    Returns:
        Dict with keys: code_files, test_files, repos_with_tests.
    """
    from organvm_engine.organ_config import ORGANS

    code_files = 0
    test_files = 0
    repos_with_tests = 0

    for organ_info in ORGANS.values():
        organ_dir = workspace / organ_info["dir"]
        if not organ_dir.is_dir():
            continue
        for repo_dir in sorted(organ_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            has_tests = (repo_dir / "tests").is_dir()
            if has_tests:
                repos_with_tests += 1
            for path in repo_dir.rglob("*"):
                if not path.is_file():
                    continue
                # Skip vendored/virtual directories
                if any(skip in path.parts for skip in _SKIP_DIRS):
                    continue
                if path.suffix in _CODE_EXTENSIONS:
                    code_files += 1
                    name = path.name
                    if any(pat in name for pat in _TEST_PATTERNS):
                        test_files += 1

    return {
        "code_files": code_files,
        "test_files": test_files,
        "repos_with_tests": repos_with_tests,
    }


def compute_metrics(registry: dict, workspace: Path | None = None) -> dict:
    """Derive all computable metrics from registry-v2.json.

    Args:
        registry: Loaded registry dict.
        workspace: Optional workspace root for word counting. If provided,
            word counts are auto-computed and included in the result.

    Returns:
        Dict with computed metrics (total_repos, per_organ, status distribution, etc.).
    """
    organs = registry.get("organs", {})
    repos = []
    per_organ = {}

    for organ_key, organ_data in organs.items():
        organ_repos = organ_data.get("repositories", [])
        repos.extend(organ_repos)
        per_organ[organ_key] = {
            "name": organ_data.get("name", organ_key),
            "repos": len(organ_repos),
        }

    status_dist: dict[str, int] = defaultdict(int)
    ci_count = 0
    dep_count = 0

    for repo in repos:
        status_dist[repo.get("implementation_status", "UNKNOWN")] += 1
        if repo.get("ci_workflow"):
            ci_count += 1
        dep_count += len(repo.get("dependencies", []))

    operational = sum(
        1 for o in organs.values()
        if o.get("launch_status") == "OPERATIONAL"
    )

    result = {
        "total_repos": len(repos),
        "active_repos": status_dist.get("ACTIVE", 0),
        "archived_repos": status_dist.get("ARCHIVED", 0),
        "total_organs": len(organs),
        "operational_organs": operational,
        "ci_workflows": ci_count,
        "dependency_edges": dep_count,
        "per_organ": per_organ,
        "implementation_status": dict(sorted(status_dist.items())),
    }

    if workspace is not None:
        wc = count_words(workspace)
        result["word_counts"] = wc
        tw, tw_num, tw_short = format_word_count(wc["total"])
        result["total_words"] = tw
        result["total_words_numeric"] = tw_num
        result["total_words_short"] = tw_short

        cf = count_code_files(workspace)
        result["code_files"] = cf["code_files"]
        result["test_files"] = cf["test_files"]
        result["repos_with_tests"] = cf["repos_with_tests"]

    return result


def write_metrics(
    computed: dict,
    output_path: Path | str,
    manual: dict | None = None,
) -> None:
    """Write system-metrics.json with computed and manual sections.

    Args:
        computed: Computed metrics dict.
        output_path: Output file path.
        manual: Manual section to preserve. Loaded from existing file if None.
    """
    out = Path(output_path)

    resolved_manual: dict
    if manual is not None:
        resolved_manual = manual
    elif out.exists():
        with open(out) as f:
            existing = json.load(f)
        resolved_manual = existing.get("manual", {})
    else:
        resolved_manual = {
            "_note": "Edit these by hand. calculate-metrics.py preserves this section.",
        }

    # Migrate fields from manual to computed when auto-computed
    if "word_counts" in computed:
        for key in ("total_words", "total_words_numeric", "total_words_short"):
            resolved_manual.pop(key, None)
    if "code_files" in computed:
        for key in ("code_files", "test_files", "repos_with_tests"):
            resolved_manual.pop(key, None)

    metrics = {
        "schema_version": "1.0",
        "generated": datetime.now(timezone.utc).isoformat(),
        "computed": computed,
        "manual": resolved_manual,
    }

    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")
