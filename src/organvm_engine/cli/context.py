"""Context sync CLI commands."""

import argparse


def cmd_context_sync(args: argparse.Namespace) -> int:
    from organvm_engine.contextmd.sync import sync_all

    organs = [args.organ] if args.organ else None
    result = sync_all(
        workspace=args.workspace,
        registry_path=args.registry,
        dry_run=args.dry_run,
        organs=organs,
    )

    print("System Context Sync Results")
    print("─" * 40)
    print(f"  Updated: {len(result['updated'])}")
    print(f"  Created: {len(result['created'])}")
    print(f"  Skipped: {len(result['skipped'])}")
    if result["errors"]:
        print(f"  Errors:  {len(result['errors'])}")
        for e in result["errors"]:
            print(f"    - {e['path']}: {e['error']}")

    if result.get("dry_run"):
        print("\n[DRY RUN] No files were modified.")

    return 1 if result["errors"] else 0
