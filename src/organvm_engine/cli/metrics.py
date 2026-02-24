"""Metrics CLI commands."""

import argparse
import json
import sys
from pathlib import Path

from organvm_engine.registry.loader import load_registry


def cmd_metrics_calculate(args: argparse.Namespace) -> int:
    from organvm_engine.cli import _resolve_workspace
    from organvm_engine.metrics.calculator import compute_metrics, write_metrics

    registry = load_registry(args.registry)
    workspace = _resolve_workspace(args)
    computed = compute_metrics(registry, workspace=workspace)

    output = Path(args.output) if args.output else (
        Path(args.registry).parent / "system-metrics.json"
    )
    write_metrics(computed, output)

    print(f"Metrics written to {output}")
    print(f"  Repos: {computed['total_repos']} ({computed['active_repos']} ACTIVE)")
    print(
        f"  Organs: {computed['operational_organs']}/{computed['total_organs']}"
        " operational"
    )
    print(f"  CI: {computed['ci_workflows']}")
    print(f"  Dependencies: {computed['dependency_edges']} edges")
    if "word_counts" in computed:
        wc = computed["word_counts"]
        print(
            f"  Words: {computed['total_words_short']} "
            f"(readmes={wc['readmes']:,}, essays={wc['essays']:,}, "
            f"corpus={wc['corpus']:,}, profiles={wc['org_profiles']:,})"
        )
    return 0


def cmd_metrics_propagate(args: argparse.Namespace) -> int:
    from organvm_engine.metrics.propagator import (
        propagate_cross_repo,
        propagate_metrics,
    )

    corpus_root = Path(args.registry).parent
    metrics_path = corpus_root / "system-metrics.json"

    if not metrics_path.exists():
        print(
            f"ERROR: {metrics_path} not found. "
            "Run 'organvm metrics calculate' first.",
            file=sys.stderr,
        )
        return 1

    with open(metrics_path) as f:
        metrics = json.load(f)

    mode = "DRY RUN" if args.dry_run else "PROPAGATING"

    if args.cross_repo:
        manifest_path = (
            Path(args.targets) if args.targets
            else (corpus_root / "metrics-targets.yaml")
        )
        if not manifest_path.exists():
            print(f"ERROR: {manifest_path} not found.", file=sys.stderr)
            return 1

        # Load registry for landing.json transform
        registry = load_registry(args.registry)

        result = propagate_cross_repo(
            metrics, manifest_path, corpus_root,
            dry_run=args.dry_run, registry=registry,
        )
        print(f"[{mode}] Cross-repo propagation complete")
        print(f"  JSON copies: {result.json_copies}")
        print(
            f"  Markdown: {result.replacements} replacement(s) "
            f"across {result.files_changed} file(s)"
        )
    else:
        # Corpus-only: use the built-in whitelist from the standalone script
        whitelist_globs = [
            "README.md", "CLAUDE.md",
            "applications/*.md", "applications/shared/*.md",
            "docs/applications/*.md",
            "docs/applications/cover-letters/*.md",
            "docs/essays/09-ai-conductor-methodology.md",
            "docs/operations/*.md",
        ]
        files: list[Path] = []
        for pattern in whitelist_globs:
            files.extend(sorted(corpus_root.glob(pattern)))
        # Deduplicate
        seen: set[Path] = set()
        unique: list[Path] = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        result = propagate_metrics(metrics, unique, dry_run=args.dry_run)
        print(f"[{mode}] Corpus-only propagation complete")
        print(
            f"  {result.replacements} replacement(s) "
            f"across {result.files_changed} file(s)"
        )

    if result.details:
        for d in result.details[:20]:
            print(f"    {d}")
        if len(result.details) > 20:
            print(f"    ... and {len(result.details) - 20} more")

    return 0


def cmd_metrics_count_words(args: argparse.Namespace) -> int:
    from organvm_engine.cli import _resolve_workspace
    from organvm_engine.metrics.calculator import count_words, format_word_count

    workspace = _resolve_workspace(args)
    if workspace is None:
        print(
            "ERROR: Could not determine workspace. "
            "Use --workspace or set ORGANVM_WORKSPACE_DIR.",
            file=sys.stderr,
        )
        return 1

    wc = count_words(workspace)
    tw, tw_num, tw_short = format_word_count(wc["total"])

    print("\n  Word Count Breakdown")
    print(f"  {'─' * 40}")
    print(f"    READMEs:      {wc['readmes']:>10,}")
    print(f"    Essays:       {wc['essays']:>10,}")
    print(f"    Corpus docs:  {wc['corpus']:>10,}")
    print(f"    Org profiles: {wc['org_profiles']:>10,}")
    print(f"    {'─' * 30}")
    print(f"    Total:        {wc['total']:>10,}  ({tw_short})")
    print()
    return 0


def cmd_metrics_refresh(args: argparse.Namespace) -> int:
    from organvm_engine.cli import _resolve_workspace
    from organvm_engine.metrics.calculator import compute_metrics, write_metrics

    # Step 1: Calculate
    registry = load_registry(args.registry)
    workspace = _resolve_workspace(args)
    computed = compute_metrics(registry, workspace=workspace)

    corpus_root = Path(args.registry).parent
    output = corpus_root / "system-metrics.json"

    if not args.dry_run:
        write_metrics(computed, output)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}[1/2] Metrics calculated -> {output}")
    print(f"  Repos: {computed['total_repos']} ({computed['active_repos']} ACTIVE)")

    # Step 2: Propagate
    args_ns = argparse.Namespace(
        registry=args.registry,
        cross_repo=args.cross_repo,
        targets=getattr(args, "targets", None),
        dry_run=args.dry_run,
    )
    print("[2/2] Propagating...")
    return cmd_metrics_propagate(args_ns)
