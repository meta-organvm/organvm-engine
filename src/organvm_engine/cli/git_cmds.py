"""Git superproject CLI commands."""

import argparse


def cmd_git_init_superproject(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import init_superproject

    result = init_superproject(
        organ=args.organ,
        workspace=args.workspace,
        registry_path=args.registry,
        dry_run=args.dry_run,
    )

    if result.get("already_initialized") and not args.dry_run:
        print(f"  Re-initialized superproject for {result['organ_dir']}")
    else:
        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"  {prefix}Initialized superproject: {result['organ_dir']}")

    print(f"  Submodules: {result['repos_registered']}")
    print(f"  Remote: {result['remote']}")
    if args.dry_run:
        for repo in result.get("repos", []):
            print(f"    - {repo}")
    return 0


def cmd_git_add_submodule(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import add_submodule

    result = add_submodule(
        organ=args.organ,
        repo_name=args.repo,
        repo_url=args.url,
        workspace=args.workspace,
    )

    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return 1

    print(f"  Added submodule: {result['added']}")
    print(f"  URL: {result['url']}")
    return 0


def cmd_git_sync_organ(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import sync_organ

    result = sync_organ(
        organ=args.organ,
        message=args.message,
        workspace=args.workspace,
        dry_run=args.dry_run,
    )

    if not result["changed"]:
        print(f"  {result['organ']}: no submodule pointer changes")
        return 0

    prefix = "[DRY RUN] " if result.get("dry_run") else ""
    print(
        f"  {prefix}{result['organ']}: "
        f"{len(result['changed'])} submodule(s) updated"
    )
    for path in result["changed"]:
        print(f"    - {path}")
    return 0


def cmd_git_sync_all(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import ORGAN_DIR_MAP, sync_organ

    total_changed = 0
    for organ_key in ORGAN_DIR_MAP:
        try:
            result = sync_organ(
                organ=organ_key,
                workspace=args.workspace,
                dry_run=args.dry_run,
            )
            if result["changed"]:
                prefix = "[DRY RUN] " if result.get("dry_run") else ""
                print(
                    f"  {prefix}{result['organ']}: "
                    f"{len(result['changed'])} updated"
                )
                for path in result["changed"]:
                    print(f"    - {path}")
                total_changed += len(result["changed"])
        except (RuntimeError, FileNotFoundError):
            continue  # Skip organs without superprojects

    if total_changed == 0:
        print("  No submodule pointer changes across any organ.")
    else:
        print(f"\n  Total: {total_changed} submodule pointer(s) changed")
    return 0


def cmd_git_status(args: argparse.Namespace) -> int:
    from organvm_engine.git.status import show_drift

    drift = show_drift(organ=args.organ, workspace=args.workspace)

    if not drift:
        scope = f"organ {args.organ}" if args.organ else "all organs"
        print(f"  No drift detected across {scope}.")
        return 0

    print(
        f"  {'Organ':<30} {'Repo':<40} {'Pinned':<10} "
        f"{'Current':<10} {'Status'}"
    )
    print(f"  {'─' * 100}")
    for d in drift:
        ahead_info = ""
        if d.get("ahead"):
            ahead_info = f" (+{d['ahead']})"
        if d.get("behind"):
            ahead_info += f" (-{d['behind']})"
        print(
            f"  {d['organ']:<30} {d['repo']:<40} "
            f"{d['pinned_sha']:<10} {d['current_sha']:<10} "
            f"{d['status']}{ahead_info}"
        )
    print(f"\n  {len(drift)} submodule(s) with drift")
    return 0


def cmd_git_reproduce(args: argparse.Namespace) -> int:
    from organvm_engine.git.reproduce import reproduce_workspace

    organs = [args.organ] if args.organ else None
    result = reproduce_workspace(
        target=args.target,
        manifest_path=args.manifest,
        organs=organs,
        shallow=args.shallow,
    )

    print(f"  Target: {result['target']}")
    print(f"  Cloned: {len(result['cloned_organs'])} organ(s)")
    for o in result["cloned_organs"]:
        print(f"    - {o}")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"    - {e}")
        return 1
    return 0


def cmd_git_diff_pinned(args: argparse.Namespace) -> int:
    from organvm_engine.git.status import diff_pinned

    diffs = diff_pinned(organ=args.organ, workspace=args.workspace)

    if not diffs:
        print("  No pinned diffs found.")
        return 0

    for d in diffs:
        print(f"\n  {d['organ']}/{d['repo']}")
        print(f"  Pinned: {d['pinned_sha']}  Current: {d['current_sha']}")
        if d["commit_log"]:
            for commit in d["commit_log"]:
                print(f"    {commit}")
        else:
            print("    (no commits between pinned and current)")

    return 0


def cmd_git_install_hooks(args: argparse.Namespace) -> int:
    from organvm_engine.git.superproject import install_hooks

    result = install_hooks(organ=args.organ, workspace=args.workspace)

    if result["installed"]:
        print(f"Hooks installed in {len(result['installed'])} superproject(s):")
        for o in result["installed"]:
            print(f"  - {o}")
    if result["errors"]:
        print(f"Errors installing hooks: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  - {e['organ']}: {e['error']}")
        return 1
    return 0
