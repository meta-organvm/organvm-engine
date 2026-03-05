"""Deadlines CLI commands."""

import argparse


def cmd_deadlines(args: argparse.Namespace) -> int:
    from organvm_engine.deadlines.parser import (
        filter_upcoming,
        format_deadlines,
        parse_deadlines,
    )

    deadlines = parse_deadlines()

    filtered = deadlines if args.all else filter_upcoming(deadlines, days=args.days)

    print(f"\n  Upcoming Deadlines (next {args.days} days)")
    print(f"  {'═' * 60}")
    print(format_deadlines(filtered))
    print(f"\n  {len(filtered)} deadline(s) shown ({len(deadlines)} total)\n")
    return 0
