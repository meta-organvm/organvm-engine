# Plan: Expand Registry Features and Functions
Date: 2026-03-05
Project: organvm-engine

## Objectives
- Extend `registry.query` with broader filtering, search, dependency analysis, and summary metrics.
- Expose new functionality through the CLI with focused subcommands.
- Add comprehensive tests to validate behavior and avoid regressions.

## Execution Steps
1. Expand query API:
   - Add richer `list_repos` filters.
   - Add `search_repos` and result sorting helpers.
   - Add dependency map and traversal utilities.
   - Add registry summary dataclass + serializer.
2. Extend CLI:
   - Enhance `registry list` flags.
   - Add `registry search`, `registry deps`, `registry stats` commands.
   - Wire parser and dispatch table updates.
3. Export new public APIs from `registry.__init__`.
4. Add tests:
   - Query/filter/search/dependency/stats tests.
   - CLI parser + command behavior tests.
5. Validate:
   - Run targeted and full `organvm-engine` test suites.

## Validation Commands
- `pytest organvm-engine/tests/test_registry.py organvm-engine/tests/test_cli.py -v`
- `pytest organvm-engine/tests -q`

## Outcome
- Completed.
- Targeted suite: passing.
- Full suite: `317 passed`.
