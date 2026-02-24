"""Query operations on the registry."""

from typing import Iterator


def all_repos(registry: dict) -> Iterator[tuple[str, dict]]:
    """Yield (organ_key, repo_dict) for every repo in the registry."""
    for organ_key, organ in registry.get("organs", {}).items():
        for repo in organ.get("repositories", []):
            yield organ_key, repo


def find_repo(registry: dict, name: str) -> tuple[str, dict] | None:
    """Find a repo entry by name.

    Args:
        registry: Loaded registry dict.
        name: Repository name (e.g., "recursive-engine--generative-entity").

    Returns:
        (organ_key, repo_dict) or None if not found.
    """
    for organ_key, repo in all_repos(registry):
        if repo.get("name") == name:
            return organ_key, repo
    return None


def list_repos(
    registry: dict,
    organ: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    public_only: bool = False,
    promotion_status: str | None = None,
) -> list[tuple[str, dict]]:
    """List repos with optional filters.

    Args:
        registry: Loaded registry dict.
        organ: Filter by organ key (e.g., "ORGAN-I").
        status: Filter by implementation_status.
        tier: Filter by tier.
        public_only: Only include public repos.
        promotion_status: Filter by promotion_status (e.g., "LOCAL", "GRADUATED").

    Returns:
        List of (organ_key, repo_dict) tuples matching filters.
    """
    results = []
    for organ_key, repo in all_repos(registry):
        if organ and organ_key != organ:
            continue
        if status and repo.get("implementation_status") != status:
            continue
        if tier and repo.get("tier") != tier:
            continue
        if public_only and not repo.get("public"):
            continue
        if promotion_status and repo.get("promotion_status") != promotion_status:
            continue
        results.append((organ_key, repo))
    return results
