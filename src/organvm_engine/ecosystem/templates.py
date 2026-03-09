"""Scaffold ecosystem.yaml from existing data sources.

Cross-references seed.yaml, registry, and kerygma profiles to infer
what arms a product needs. All inferred arms start at not_started
unless deployment_url or revenue_status suggest otherwise.
"""

from __future__ import annotations


def scaffold_ecosystem(
    repo_name: str,
    organ: str,
    registry_data: dict | None = None,
    seed_data: dict | None = None,
    kerygma_profile: dict | None = None,
    display_name: str | None = None,
) -> dict:
    """Generate ecosystem.yaml scaffold from existing data.

    Args:
        repo_name: Repository name.
        organ: Organ short key (e.g. "III").
        registry_data: Registry entry for this repo (optional).
        seed_data: Parsed seed.yaml (optional).
        kerygma_profile: Parsed kerygma profile (optional).
        display_name: Human-readable product name (optional).

    Returns:
        Dict suitable for writing as ecosystem.yaml.
    """
    eco: dict = {
        "schema_version": "1.0",
        "repo": repo_name,
        "organ": organ,
    }
    if display_name:
        eco["display_name"] = display_name

    delivery = _infer_delivery(seed_data, registry_data)
    if delivery:
        eco["delivery"] = delivery

    revenue = _infer_revenue(registry_data)
    if revenue:
        eco["revenue"] = revenue

    marketing = _infer_marketing(kerygma_profile)
    if marketing:
        eco["marketing"] = marketing

    community = _infer_community(kerygma_profile)
    if community:
        eco["community"] = community

    return eco


def _infer_delivery(
    seed_data: dict | None,
    registry_data: dict | None,
) -> list[dict]:
    """Infer delivery arms from seed tags and registry data."""
    arms: list[dict] = []

    if seed_data:
        metadata = seed_data.get("metadata", {}) or {}
        tags = metadata.get("tags", []) or []
        tags_lower = [t.lower() for t in tags]
        language = (metadata.get("language") or "").lower()
        deployment_url = metadata.get("deployment_url") or seed_data.get("deployment_url")

        # Web app inference
        if any(t in tags_lower for t in ("nextjs", "react", "vue", "svelte", "astro")):
            arm: dict = {"platform": "web_app", "status": "not_started"}
            if deployment_url:
                arm["status"] = "live"
                arm["url"] = deployment_url
            arms.append(arm)

        # Mobile inference
        if any(t in tags_lower for t in ("react-native", "expo")):
            arms.append({"platform": "mobile_app_ios", "status": "not_started"})
            arms.append({"platform": "mobile_app_android", "status": "not_started"})

        # Desktop inference
        if any(t in tags_lower for t in ("tauri", "electron")):
            arms.append({"platform": "desktop_app", "status": "not_started"})

        # Browser extension inference
        if any(t in tags_lower for t in ("chrome", "browser", "extension")):
            arms.append({"platform": "browser_extension_chrome", "status": "not_started"})

        # CLI inference
        if any(t in tags_lower for t in ("cli",)):
            arms.append({"platform": "cli", "status": "not_started"})

        # API inference
        if any(t in tags_lower for t in ("api", "rest", "graphql")):
            arms.append({"platform": "api", "status": "not_started"})

        # Package inference
        if (
            language == "typescript"
            and "npm_package" not in [a["platform"] for a in arms]
            and any(t in tags_lower for t in ("npm", "package", "library"))
        ):
            arms.append({"platform": "npm_package", "status": "not_started"})
        if language == "python" and any(
            t in tags_lower for t in ("pypi", "package", "library")
        ):
            arms.append({"platform": "pypi_package", "status": "not_started"})

    # Fallback: if we have a web deployment but no tags
    if not arms and registry_data:
        impl = registry_data.get("implementation_status", "")
        if impl == "ACTIVE":
            arms.append({"platform": "web_app", "status": "not_started"})

    return arms


def _infer_revenue(registry_data: dict | None) -> list[dict]:
    """Infer revenue arms from registry data."""
    arms: list[dict] = []
    if not registry_data:
        return arms

    rev_model = registry_data.get("revenue_model", "")
    rev_status = registry_data.get("revenue_status", "pre-launch")

    if rev_model and rev_model != "none":
        status = "not_started"
        if rev_status == "live":
            status = "live"
        elif rev_status in ("beta", "soft-launch"):
            status = "in_progress"
        elif rev_status == "pre-launch":
            status = "planned"

        arms.append({
            "platform": rev_model,
            "status": status,
            "priority": "critical",
        })

    return arms


def _infer_marketing(kerygma_profile: dict | None) -> list[dict]:
    """Infer marketing arms from kerygma profile."""
    arms: list[dict] = []
    if not kerygma_profile:
        return arms

    channels = kerygma_profile.get("channels", {}) or {}
    if any(ch in channels for ch in ("mastodon", "bluesky", "twitter")):
        arms.append({
            "platform": "social_organic",
            "status": "not_started",
        })

    return arms


def _infer_community(kerygma_profile: dict | None) -> list[dict]:
    """Infer community arms from kerygma profile."""
    arms: list[dict] = []
    if not kerygma_profile:
        return arms

    channels = kerygma_profile.get("channels", {}) or {}
    for platform in ("discord", "mastodon", "slack"):
        if platform in channels:
            arms.append({
                "platform": platform,
                "status": "not_started",
                "ref": f"kerygma:{kerygma_profile.get('repo', '')}",
            })

    return arms
