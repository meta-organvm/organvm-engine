"""Content pipeline CLI commands."""

from __future__ import annotations

import argparse
import json


def cmd_content_list(args: argparse.Namespace) -> int:
    """List all content pipeline posts."""
    from organvm_engine.content.reader import discover_posts, filter_posts
    from organvm_engine.paths import content_dir

    posts = discover_posts(content_dir())
    status_filter = getattr(args, "status", None)
    tag_filter = getattr(args, "tag", None)
    filtered = filter_posts(posts, status=status_filter, tag=tag_filter)

    as_json = getattr(args, "json", False)
    if as_json:
        import dataclasses
        data = [dataclasses.asdict(p) for p in filtered]
        for item in data:
            item["directory"] = str(item["directory"])
        print(json.dumps(data, indent=2))
        return 0

    print(f"\n  Content Pipeline — {len(filtered)} posts")
    if not filtered:
        print("  (no posts found)\n")
        return 0

    print(f"\n  {'Date':<13} {'Slug':<25} {'Status':<11} {'Hook':<35} Distribution")
    print(f"  {'─' * 95}")

    for p in filtered:
        hook = f'"{p.hook[:30]}..."' if len(p.hook) > 30 else f'"{p.hook}"'
        dist_parts = []
        for ch in ("linkedin", "portfolio"):
            ch_data = p.distribution.get(ch, {})
            posted = ch_data.get("posted", False) if isinstance(ch_data, dict) else False
            label = ch[:2].upper()
            dist_parts.append(f"{label}:{'✓' if posted else '✗'}")
        dist = " ".join(dist_parts)
        print(f"  {p.date:<13} {p.slug:<25} {p.status:<11} {hook:<35} {dist}")

    print()
    return 0


def cmd_content_new(args: argparse.Namespace) -> int:
    """Scaffold a new content post directory."""
    from organvm_engine.content.scaffolder import scaffold_post
    from organvm_engine.paths import content_dir

    slug = args.slug
    title = getattr(args, "title", None)
    hook = getattr(args, "hook", None)
    session_id = getattr(args, "session", None)
    dry_run = getattr(args, "dry_run", False)

    try:
        result = scaffold_post(
            content_dir(), slug,
            title=title, hook=hook,
            session_id=session_id, dry_run=dry_run,
        )
    except ValueError as exc:
        print(f"  Error: {exc}")
        return 1

    if dry_run:
        print(f"  [dry-run] Would create: {result}")
    else:
        print(f"  Created: {result}")
        for f in sorted(result.iterdir()):
            print(f"    {f.name}")

    return 0


def cmd_content_status(args: argparse.Namespace) -> int:
    """Show weekly content cadence health check."""
    from organvm_engine.content.cadence import check_cadence
    from organvm_engine.content.reader import discover_posts
    from organvm_engine.paths import content_dir

    posts = discover_posts(content_dir())
    report = check_cadence(posts)

    as_json = getattr(args, "json", False)
    if as_json:
        import dataclasses
        data = dataclasses.asdict(report)
        data["posts_this_week"] = [
            {**dataclasses.asdict(p), "directory": str(p.directory)}
            for p in report.posts_this_week
        ]
        print(json.dumps(data, indent=2))
        return 0

    from datetime import date
    week_num = date.today().isocalendar()[1]

    print("\n  Content Cadence")
    print(f"  {'═' * 35}")

    if report.posts_this_week:
        slugs = ", ".join(p.slug for p in report.posts_this_week)
        print(f"\n  This week (W{week_num}):  {len(report.posts_this_week)} post(s) ({slugs})")
    else:
        print(f"\n  This week (W{week_num}):  0 posts")

    print(f"  Streak:           {report.streak} week(s)")
    print(f"  Last post:        {report.last_post_date or 'never'}")

    print(f"\n  Totals: {report.total_posts} posts "
          f"({report.published_count} published, {report.draft_count} draft, "
          f"{report.archived_count} archived)")

    unposted = 0
    for p in posts:
        if p.status in ("draft", "published"):
            all_posted = all(
                ch.get("posted", False)
                for ch in p.distribution.values()
                if isinstance(ch, dict)
            )
            if not all_posted:
                unposted += 1
    if unposted:
        print(f"  Distribution gaps: {unposted} post(s) written but not yet posted")

    print()
    return 0
