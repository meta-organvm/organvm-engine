"""CLI commands for named functions (the liquid model).

organvm functions list [--json]
organvm functions resolve <key> [--json]
"""

from __future__ import annotations

import json


def cmd_functions_list(args: object) -> int:
    """List all named functions."""
    from organvm_engine.governance.named_functions import (
        function_to_organ,
        list_functions,
    )

    functions = list_functions()
    if getattr(args, "json", False):
        print(json.dumps(functions, indent=2))
        return 0

    for f in functions:
        legacy = function_to_organ(f["key"]) or ""
        if legacy:
            legacy = f"(ORGAN-{legacy})" if legacy != "META" else "(META-ORGANVM)"
        genome_marker = " [GENOME]" if f.get("is_genome") else ""
        print(
            f"  {f['key']:12s} {f['display_name']:12s} "
            f"{legacy:16s} {f['physiological_role']}{genome_marker}",
        )
    return 0


def cmd_functions_resolve(args: object) -> int:
    """Resolve an organ key or function name to the canonical function."""
    from organvm_engine.governance.named_functions import (
        get_function,
        organ_to_function,
    )
    from organvm_engine.organ_config import resolve_function

    key = getattr(args, "key", "")
    use_json = getattr(args, "json", False)

    # Try resolve_function which handles all key formats
    fn_name = resolve_function(key)
    if fn_name:
        f = get_function(fn_name)
        if use_json:
            print(json.dumps(f, indent=2))
        else:
            resolved_from = f" (resolved from {key})" if key.lower() != fn_name else ""
            print(
                f"{f['key']}: {f['display_name']} — "
                f"{f['physiological_role']}{resolved_from}",
            )
        return 0

    # Direct function name lookup
    try:
        f = get_function(key.lower())
        if use_json:
            print(json.dumps(f, indent=2))
        else:
            print(f"{f['key']}: {f['display_name']} — {f['physiological_role']}")
        return 0
    except KeyError:
        pass

    # Try organ-to-function bridge with raw key
    fn = organ_to_function(key)
    if fn:
        f = get_function(fn)
        if use_json:
            print(json.dumps(f, indent=2))
        else:
            print(
                f"{f['key']}: {f['display_name']} — "
                f"{f['physiological_role']} (resolved from {key})",
            )
        return 0

    print(f"Unknown function or organ key: {key}")
    return 1
