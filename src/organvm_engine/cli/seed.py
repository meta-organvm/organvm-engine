"""Seed CLI commands."""

import argparse


def cmd_seed_discover(args: argparse.Namespace) -> int:
    from organvm_engine.seed.discover import discover_seeds

    seeds = discover_seeds(args.workspace)
    print(f"Found {len(seeds)} seed.yaml files:\n")
    for path in seeds:
        # Show as org/repo
        parts = path.parts
        repo = parts[-2]
        org = parts[-3]
        print(f"  {org}/{repo}")
    return 0


def cmd_seed_validate(args: argparse.Namespace) -> int:
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed

    seeds = discover_seeds(args.workspace)
    errors = 0

    for path in seeds:
        try:
            seed = read_seed(path)
            required = ["schema_version", "organ", "repo", "org"]
            missing = [f for f in required if f not in seed]
            if missing:
                print(f"  FAIL {path.parent.name}: missing {', '.join(missing)}")
                errors += 1
            else:
                print(f"  PASS {seed.get('org')}/{seed.get('repo')}")
        except Exception as e:
            print(f"  FAIL {path}: {e}")
            errors += 1

    print(f"\n{len(seeds) - errors} passed, {errors} failed")
    return 1 if errors > 0 else 0


def cmd_seed_graph(args: argparse.Namespace) -> int:
    from organvm_engine.seed.graph import build_seed_graph

    graph = build_seed_graph(args.workspace)
    print(graph.summary())
    return 0
