"""Dispatch CLI commands."""

import argparse
import json


def cmd_dispatch_validate(args: argparse.Namespace) -> int:
    from organvm_engine.dispatch.payload import validate_payload

    with open(args.file) as f:
        payload = json.load(f)

    ok, errors = validate_payload(payload)
    if ok:
        print(f"PASS: {args.file}")
    else:
        print(f"FAIL: {args.file}")
        for e in errors:
            print(f"  {e}")
    return 0 if ok else 1
