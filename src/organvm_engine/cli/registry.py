"""Registry CLI commands."""

import argparse
import json

from organvm_engine.registry.loader import load_registry, save_registry
from organvm_engine.registry.query import find_repo, list_repos
from organvm_engine.registry.updater import update_repo
from organvm_engine.registry.validator import validate_registry


def cmd_registry_show(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    result = find_repo(registry, args.repo)
    if not result:
        print(f"ERROR: Repo '{args.repo}' not found in registry")
        return 1

    organ_key, repo = result
    print(f"\n  {repo['name']}")
    print(f"  {'─' * max(len(repo['name']), 40)}")
    print(f"  Organ:       {organ_key}")
    for key, value in repo.items():
        if key == "name":
            continue
        if isinstance(value, list):
            print(f"  {key + ':':<20}{', '.join(str(v) for v in value)}")
        elif isinstance(value, dict):
            print(f"  {key + ':':<20}{json.dumps(value, indent=None)}")
        else:
            print(f"  {key + ':':<20}{value}")
    print()
    return 0


def cmd_registry_list(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    results = list_repos(
        registry,
        organ=args.organ,
        status=args.status,
        tier=args.tier,
        public_only=args.public,
    )

    if not results:
        print("No repos match the given filters.")
        return 0

    print(f"\n  {'Name':<45} {'Organ':<15} {'Status':<12} {'Tier':<12}")
    print(f"  {'─' * 84}")
    for organ_key, repo in results:
        print(
            f"  {repo['name']:<45} {organ_key:<15} "
            f"{repo.get('implementation_status', '?'):<12} "
            f"{repo.get('tier', '?'):<12}"
        )
    print(f"\n  {len(results)} repo(s)")
    return 0


def cmd_registry_validate(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    result = validate_registry(registry)
    print(result.summary())
    return 0 if result.passed else 1


def cmd_registry_update(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)

    # Type coercion — only for known boolean/integer fields
    BOOL_FIELDS = {"public", "platinum_status", "archived"}
    INT_FIELDS: set[str] = set()

    raw_value: str = args.value
    value: str | bool | int = raw_value
    if args.field in BOOL_FIELDS:
        if raw_value.lower() == "true":
            value = True
        elif raw_value.lower() == "false":
            value = False
    elif args.field in INT_FIELDS:
        try:
            value = int(value)
        except ValueError:
            pass

    ok, msg = update_repo(registry, args.repo, args.field, value)
    print(f"  {msg}")
    if ok:
        save_registry(registry, args.registry)
        print("  Registry saved.")
    return 0 if ok else 1
