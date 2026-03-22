"""CLI: organvm taxonomy — functional classification commands."""

from __future__ import annotations

import json
import sys

from organvm_engine.governance.functional_taxonomy import classify_repo
from organvm_engine.registry.loader import load_registry


def cmd_taxonomy_classify(args) -> int:
    """Classify repos by heuristic and compare with recorded class."""
    registry = load_registry()
    organ_filter = getattr(args, "organ", None)
    as_json = getattr(args, "as_json", False)

    results = []
    for organ_key, organ_data in registry.get("organs", {}).items():
        if organ_filter and organ_key != organ_filter:
            continue
        for repo in organ_data.get("repositories", []):
            heuristic = classify_repo(repo)
            recorded = repo.get("functional_class", "")
            results.append({
                "organ": organ_key,
                "repo": repo.get("name", ""),
                "heuristic": heuristic.value,
                "recorded": recorded,
                "match": heuristic.value == recorded if recorded else None,
            })

    if as_json:
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for r in results:
            marker = "[OK]" if r["match"] else ("[DRIFT]" if r["match"] is False else "[?]")
            print(
                f"  {marker} {r['organ']}/{r['repo']:40s}"
                f" heuristic={r['heuristic']:15s}"
                f" recorded={r['recorded'] or '—'}",
            )
    return 0


def cmd_taxonomy_audit(args) -> int:
    """Audit classification drift between heuristic and recorded class."""
    registry = load_registry()
    organ_filter = getattr(args, "organ", None)
    as_json = getattr(args, "as_json", False)

    total = classified = drift = 0
    drift_items = []
    for organ_key, organ_data in registry.get("organs", {}).items():
        if organ_filter and organ_key != organ_filter:
            continue
        for repo in organ_data.get("repositories", []):
            total += 1
            recorded = repo.get("functional_class", "")
            if recorded:
                classified += 1
                heuristic = classify_repo(repo)
                if heuristic.value != recorded:
                    drift += 1
                    drift_items.append({
                        "organ": organ_key,
                        "repo": repo.get("name", ""),
                        "recorded": recorded,
                        "heuristic": heuristic.value,
                    })

    if as_json:
        json.dump({
            "total": total,
            "classified": classified,
            "drift": drift,
            "coverage_pct": 100 * classified // total if total else 0,
            "drift_pct": 100 * drift // classified if classified else 0,
            "items": drift_items,
        }, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for item in drift_items:
            print(
                f"  DRIFT {item['organ']}/{item['repo']}:"
                f" recorded={item['recorded']}, heuristic={item['heuristic']}",
            )
        print(f"\nCoverage: {classified}/{total}"
              f" ({100 * classified // total if total else 0}%)")
        print(f"Drift: {drift}/{classified}"
              f" ({100 * drift // classified if classified else 0}%)")
    return 0
