"""Status CLI command."""

import argparse
import json

from organvm_engine.registry.loader import load_registry


def cmd_status(args: argparse.Namespace) -> int:
    from organvm_engine.metrics.calculator import compute_metrics
    from organvm_engine.omega.scorecard import evaluate

    registry = load_registry(args.registry)
    metrics = compute_metrics(registry)
    scorecard = evaluate(registry=registry)
    soak = scorecard.soak

    print("\n  ORGANVM System Pulse")
    print(f"  {'═' * 50}")

    # Repo counts by organ
    print(f"\n  Organs ({metrics['operational_organs']}/{metrics['total_organs']} operational)")
    print(f"  {'─' * 50}")
    for organ_key, organ_data in metrics["per_organ"].items():
        print(f"    {organ_key:<18} {organ_data['repos']:>3} repos  ({organ_data['name']})")
    print(f"    {'─' * 40}")
    print(
        f"    {'Total':<18} {metrics['total_repos']:>3} repos  ({metrics['active_repos']} active)",
    )

    # Soak test
    print("\n  Soak Test (VIGILIA)")
    print(f"  {'─' * 50}")
    if soak.total_snapshots > 0:
        pct = min(100, int(soak.streak_days / soak.target_days * 100))
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        print(f"    Streak:    {soak.streak_days}/{soak.target_days} days [{bar}] {pct}%")
        print(f"    Remaining: {soak.days_remaining} days")
        if soak.critical_incidents > 0:
            print(f"    Incidents: {soak.critical_incidents}")
    else:
        print("    No soak data found.")

    # Omega score
    print("\n  Omega Score")
    print(f"  {'─' * 50}")
    pct = int(scorecard.met_count / scorecard.total * 100) if scorecard.total else 0
    print(
        f"    {scorecard.met_count}/{scorecard.total} MET ({pct}%), "
        f"{scorecard.in_progress_count} in progress",
    )

    # CI
    print("\n  Infrastructure")
    print(f"  {'─' * 50}")
    print(f"    CI workflows:  {metrics['ci_workflows']}")
    print(f"    Dep edges:     {metrics['dependency_edges']}")

    # Atoms
    try:
        from organvm_engine.paths import atoms_dir

        manifest_path = atoms_dir() / "pipeline-manifest.json"
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            counts = m.get("counts", {})
            print("\n  Atoms Pipeline")
            print(f"  {'─' * 50}")
            print(f"    Tasks:     {counts.get('tasks', 0)} ({counts.get('prompts', 0)} prompts)")
            print(f"    Links:     {counts.get('links', 0)}")
            print(f"    Last run:  {m.get('generated', '?')[:19]}")
    except Exception:
        pass

    print()
    return 0
