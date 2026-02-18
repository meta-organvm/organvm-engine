"""Route events to target organs based on seed.yaml subscriptions."""

from organvm_engine.seed.reader import get_subscriptions, seed_identity


def route_event(
    event_type: str,
    source_organ: str,
    all_seeds: dict[str, dict],
) -> list[dict]:
    """Find all repos subscribed to a given event type.

    Args:
        event_type: Event type to route (e.g., "theory.published").
        source_organ: Organ where the event originated.
        all_seeds: Dict of identity -> seed data for all repos.

    Returns:
        List of {repo, action} dicts for matching subscriptions.
    """
    matches = []
    for identity, seed in all_seeds.items():
        for sub in get_subscriptions(seed):
            if sub.get("event") == event_type and sub.get("source") == source_organ:
                matches.append({
                    "repo": identity,
                    "action": sub.get("action", ""),
                    "event": event_type,
                })
    return matches
