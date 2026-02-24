"""CI triage CLI commands."""

import argparse
import json


def cmd_ci_triage(args: argparse.Namespace) -> int:
    from organvm_engine.ci.triage import triage

    report = triage()
    print(f"\n{report.summary()}\n")
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    return 0
