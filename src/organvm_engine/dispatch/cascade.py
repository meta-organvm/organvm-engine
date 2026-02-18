"""Dependency cascade execution planning."""

from collections import defaultdict, deque

from organvm_engine.registry.query import all_repos


def plan_cascade(
    registry: dict,
    start_repo: str,
) -> list[str]:
    """Plan execution order for repos that depend on a given repo.

    Uses topological ordering from the dependency graph to determine
    which repos need updating when start_repo changes.

    Args:
        registry: Loaded registry dict.
        start_repo: The "org/repo" key that changed.

    Returns:
        Ordered list of repo keys that need cascading updates.
    """
    # Build reverse adjacency (who depends on whom)
    reverse_deps: dict[str, list[str]] = defaultdict(list)
    for organ_key, repo in all_repos(registry):
        key = f"{repo['org']}/{repo['name']}"
        for dep in repo.get("dependencies", []):
            reverse_deps[dep].append(key)

    # BFS from start_repo
    visited = set()
    queue = deque([start_repo])
    order = []

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        if current != start_repo:
            order.append(current)
        for dependent in reverse_deps.get(current, []):
            if dependent not in visited:
                queue.append(dependent)

    return order
