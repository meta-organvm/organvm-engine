"""Pitch deck CLI commands."""

import argparse


def cmd_pitch_generate(args: argparse.Namespace) -> int:
    from organvm_engine.pitchdeck.sync import generate_single

    result = generate_single(
        repo_name=args.repo,
        workspace=args.workspace if hasattr(args, "workspace") else None,
        registry_path=args.registry,
        dry_run=args.dry_run,
    )

    action = result.get("action", "error")
    if action == "error":
        print(f"  ERROR: {result.get('error', 'Unknown error')}")
        return 1
    elif action == "bespoke":
        print(f"  SKIP: {args.repo} has a bespoke pitch deck at {result['path']}")
        return 0
    elif action == "dry_run":
        html_content = result.get("html", "")
        print(
            f"  [DRY RUN] Would write {len(html_content):,} bytes "
            f"to {result['path']}"
        )
        return 0
    else:
        print(f"  Generated: {result['path']}")
        return 0


def cmd_pitch_sync(args: argparse.Namespace) -> int:
    from organvm_engine.pitchdeck.sync import sync_pitchdecks

    organs = [args.organ] if args.organ else None
    result = sync_pitchdecks(
        workspace=args.workspace if hasattr(args, "workspace") else None,
        registry_path=args.registry,
        dry_run=args.dry_run,
        organs=organs,
        tier_filter=args.tier,
    )

    prefix = "[DRY RUN] " if result["dry_run"] else ""
    print(f"  {prefix}Pitch Deck Sync Results")
    print(f"  {'─' * 40}")
    print(f"  Generated: {len(result['generated'])}")
    for g in result["generated"]:
        print(f"    - {g['organ']}/{g['repo']} ({g['tier']})")
    print(f"  Skipped:   {len(result['skipped'])}")
    print(f"  Bespoke:   {len(result['bespoke'])}")
    for b in result["bespoke"]:
        print(f"    - {b} (preserved)")
    if result["errors"]:
        print(f"  Errors:    {len(result['errors'])}")
        for e in result["errors"]:
            print(f"    - {e['repo']}: {e['error']}")

    return 1 if result["errors"] else 0
