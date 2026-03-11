"""Verify CLI commands — formal verification of the dispatch pipeline."""

import argparse
import json


def cmd_verify_contracts(args: argparse.Namespace) -> int:
    from organvm_engine.verification.contracts import CONTRACTS

    event_filter = getattr(args, "event", None)

    if event_filter:
        if event_filter not in CONTRACTS:
            print(f"No contract registered for event: {event_filter}")
            print(f"Registered: {', '.join(sorted(CONTRACTS.keys()))}")
            return 1
        contracts = {event_filter: CONTRACTS[event_filter]}
    else:
        contracts = CONTRACTS

    print(f"Checking {len(contracts)} contract(s)...\n")

    all_passed = True
    for event_type, contract in sorted(contracts.items()):
        fields = ", ".join(
            f"{k}: {v.__name__}" for k, v in contract.required_payload_fields.items()
        )
        validators = len(contract.required_payload_validators)
        consumes = "yes" if contract.consumes_trigger else "no"

        print(f"  {event_type}")
        print(f"    Fields: {fields or '(none)'}")
        print(f"    Validators: {validators}")
        print(f"    Consumes trigger: {consumes}")
        print(f"    Post-condition: {contract.post_condition or '(none)'}")

        if not contract.required_payload_fields:
            print("    WARNING: vacuous contract (no required fields)")
            all_passed = False
        else:
            # Check validator consistency
            for vf in contract.required_payload_validators:
                if vf not in contract.required_payload_fields:
                    print(f"    WARNING: validator for '{vf}' has no matching field")
                    all_passed = False

        print()

    status = "PASS" if all_passed else "WARN"
    print(f"{status}: {len(contracts)} contract(s) checked")
    return 0 if all_passed else 1


def cmd_verify_temporal(args: argparse.Namespace) -> int:
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed
    from organvm_engine.verification.temporal import verify_prerequisite_chain

    workspace = getattr(args, "workspace", None)

    seeds: dict[str, dict] = {}
    try:
        for path in discover_seeds(workspace):
            seed = read_seed(path)
            identity = f"{seed.get('org', 'unknown')}/{seed.get('repo', 'unknown')}"
            seeds[identity] = seed
    except Exception as exc:
        print(f"Could not discover seeds: {exc}")
        print("Falling back to contract-registered events only.")

    from organvm_engine.verification.model_check import _collect_event_types

    event_filter = getattr(args, "event", None)
    all_events = _collect_event_types(seeds) if seeds else set()

    if event_filter:
        events_to_check = {event_filter}
    elif all_events:
        events_to_check = all_events
    else:
        from organvm_engine.verification.contracts import CONTRACTS

        events_to_check = set(CONTRACTS.keys())

    print(f"Checking temporal ordering for {len(events_to_check)} event type(s)...\n")

    violations = []
    for event_type in sorted(events_to_check):
        result = verify_prerequisite_chain(event_type, seeds)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {event_type}")
        if result.chain:
            for link in result.chain:
                print(f"         {link}")
        if result.violations:
            for v in result.violations:
                print(f"         VIOLATION: {v}")
            violations.extend(result.violations)
        print()

    if violations:
        print(f"FAIL: {len(violations)} temporal violation(s)")
        return 1
    print(f"PASS: {len(events_to_check)} event type(s) checked, no violations")
    return 0


def cmd_verify_ledger(args: argparse.Namespace) -> int:
    from organvm_engine.verification.idempotency import DispatchLedger

    ledger = DispatchLedger()
    status = ledger.status()

    use_json = getattr(args, "json", False)

    if use_json:
        print(json.dumps(status.to_dict(), indent=2))
        return 0

    print("Dispatch Ledger Status")
    print("=" * 40)
    print(f"  Total entries:  {status.total}")
    print(f"  Pending:        {status.pending}")
    print(f"  Consumed:       {status.consumed}")
    print(f"  Rejected:       {status.rejected}")
    print()

    if status.entries:
        print("Recent entries:")
        for entry in sorted(status.entries, key=lambda e: e.timestamp, reverse=True)[:10]:
            from datetime import datetime, timezone

            ts = datetime.fromtimestamp(entry.timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M",
            )
            print(f"  [{entry.status:>8}] {entry.dispatch_id[:12]} {entry.event} ({ts})")
    else:
        print("  (no entries)")

    return 0


def cmd_verify_system(args: argparse.Namespace) -> int:
    from organvm_engine.registry.loader import load_registry
    from organvm_engine.seed.discover import discover_seeds
    from organvm_engine.seed.reader import read_seed
    from organvm_engine.verification.idempotency import DispatchLedger
    from organvm_engine.verification.model_check import verify_system

    registry_path = getattr(args, "registry", None)
    workspace = getattr(args, "workspace", None)
    use_json = getattr(args, "json", False)

    # Load registry
    try:
        if registry_path:
            registry = load_registry(registry_path)
        else:
            from organvm_engine.paths import registry_path as default_reg_path

            registry = load_registry(default_reg_path())
    except Exception as exc:
        print(f"Could not load registry: {exc}")
        registry = {"organs": {}}

    # Load seeds
    seeds: dict[str, dict] = {}
    try:
        for path in discover_seeds(workspace):
            seed = read_seed(path)
            identity = f"{seed.get('org', 'unknown')}/{seed.get('repo', 'unknown')}"
            seeds[identity] = seed
    except Exception:
        pass

    # Load ledger
    ledger = DispatchLedger()

    report = verify_system(registry, seeds, ledger)

    if use_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.passed else 1

    status = "PASS" if report.passed else "FAIL"
    print(f"System Verification: {status}")
    print("=" * 50)

    print(f"\nContract Coverage: {report.contract_coverage:.1f}%")
    print(f"  Contracts checked: {report.contracts_checked}")
    print(f"  Contracts passed:  {report.contracts_passed}")
    if report.uncovered_events:
        print(f"  Uncovered events:  {', '.join(report.uncovered_events)}")

    print("\nTemporal Ordering:")
    print(f"  Checks: {report.temporal_checks}")
    print(f"  Passed: {report.temporal_passed}")

    print("\nIdempotency Ledger:")
    print(f"  Total entries: {report.ledger_total}")
    print(f"  Pending:       {report.ledger_pending}")
    print(f"  Duplicates:    {report.ledger_duplicates}")

    if report.vacuous_truths:
        print(f"\nVacuous Truths ({len(report.vacuous_truths)}):")
        for v in report.vacuous_truths:
            print(f"  - {v}")

    if report.temporal_violations:
        print(f"\nTemporal Violations ({len(report.temporal_violations)}):")
        for v in report.temporal_violations:
            print(f"  - {v}")

    if report.idempotency_risks:
        print(f"\nIdempotency Risks ({len(report.idempotency_risks)}):")
        for v in report.idempotency_risks:
            print(f"  - {v}")

    return 0 if report.passed else 1
