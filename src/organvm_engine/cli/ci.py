"""CI triage and infrastructure audit CLI commands."""

import argparse
import json


def cmd_ci_triage(args: argparse.Namespace) -> int:
    from organvm_engine.ci.triage import triage

    report = triage()
    print(f"\n{report.summary()}\n")
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    return 0


def cmd_ci_audit(args: argparse.Namespace) -> int:
    """Run infrastructure audit (The Descent Protocol)."""
    from organvm_engine.ci.audit import run_infra_audit
    from organvm_engine.registry.loader import load_registry

    registry_path = getattr(args, "registry", None)
    registry = load_registry(registry_path)

    organ_filter = getattr(args, "organ", None)
    repo_filter = getattr(args, "repo", None)

    report = run_infra_audit(
        registry=registry,
        organ_filter=organ_filter,
        repo_filter=repo_filter,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"\n{report.summary()}\n")

    # Exit non-zero if any repos are non-compliant
    return 0 if report.non_compliant_repos == 0 else 1


def cmd_ci_mandate(args: argparse.Namespace) -> int:
    """Verify CI workflow files exist on disk (mandate check)."""
    from organvm_engine.ci.mandate import verify_ci_mandate
    from organvm_engine.registry.loader import load_registry

    registry_path = getattr(args, "registry", None)
    registry = load_registry(registry_path)

    report = verify_ci_mandate(registry)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"\nCI Mandate — {report.has_ci}/{report.total} repos have workflows "
              f"({report.adherence_rate:.0%})\n")
        missing = report.missing_repos()
        if missing:
            print(f"  Missing CI ({len(missing)}):")
            for entry in missing:
                found = "" if entry.repo_path_found else " [NOT ON DISK]"
                print(f"    - {entry.organ}/{entry.repo_name}{found}")
        drift = report.drift_from_registry(registry)
        if drift:
            print(f"\n  Registry Drift ({len(drift)}):")
            for d in drift:
                print(f"    - {d['organ']}/{d['repo']}: "
                      f"registry={d['registry_says']}, disk={d['filesystem_says']}")
    print()
    return 0
