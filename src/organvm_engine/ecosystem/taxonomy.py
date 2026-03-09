"""Suggested vocabularies for ecosystem pillars and platforms.

Pure data module — no I/O, no side effects. Provides suggested
pillar names and platform names for scaffolding and discovery,
but never enforces them.
"""

from __future__ import annotations

DEFAULT_PILLARS: dict[str, dict] = {
    "delivery": {
        "description": "Where users access the product",
        "suggested_platforms": [
            "web_app", "mobile_app_ios", "mobile_app_android",
            "browser_extension_chrome", "browser_extension_firefox",
            "cli", "api", "desktop_app", "npm_package", "pypi_package",
            "docker_image", "slack_app", "vscode_extension",
        ],
    },
    "revenue": {
        "description": "How the product makes money",
        "suggested_platforms": [
            "subscription", "freemium", "one_time_purchase",
            "marketplace_commission", "affiliate", "advertising",
            "sponsorship", "donation", "enterprise_license",
            "api_usage", "in_app_purchase",
        ],
    },
    "marketing": {
        "description": "How people discover the product",
        "suggested_platforms": [
            "seo", "social_organic", "producthunt", "hackernews",
            "content_marketing", "paid_ads", "email_marketing",
            "influencer", "press", "conference", "open_source",
        ],
    },
    "community": {
        "description": "Where users gather and interact",
        "suggested_platforms": [
            "discord", "slack", "subreddit", "github_discussions",
            "forum", "telegram", "mastodon",
        ],
    },
    "content": {
        "description": "Educational and marketing content",
        "suggested_platforms": [
            "youtube", "blog", "newsletter", "podcast",
            "docs_site", "tutorials", "changelog", "case_studies",
        ],
    },
    "listings": {
        "description": "Where the product is listed for discovery",
        "suggested_platforms": [
            "gumroad", "app_store_ios", "google_play",
            "chrome_web_store", "npm_registry", "pypi",
            "product_hunt", "alternativeto", "g2",
        ],
    },
}

ARM_STATUS = ["not_started", "planned", "in_progress", "live", "paused", "deprecated"]
ARM_PRIORITY = ["critical", "high", "medium", "low", "deferred"]


def suggest_pillars(
    seed_data: dict | None = None,
    registry_data: dict | None = None,
) -> list[str]:
    """Suggest relevant pillars based on seed/registry data.

    Returns a list of pillar names from DEFAULT_PILLARS that seem
    relevant for the given product. Always returns at least delivery
    and revenue.
    """
    pillars = ["delivery", "revenue"]

    if seed_data:
        tags = seed_data.get("metadata", {}).get("tags", []) or []
        tags_lower = [t.lower() for t in tags]

        if any(t in tags_lower for t in ("saas", "web", "nextjs", "react")):
            if "marketing" not in pillars:
                pillars.append("marketing")
            if "content" not in pillars:
                pillars.append("content")

        if (
            any(t in tags_lower for t in ("chrome", "browser", "extension"))
            and "listings" not in pillars
        ):
            pillars.append("listings")

    if registry_data:
        rev_model = registry_data.get("revenue_model", "")
        if rev_model and rev_model != "none" and "marketing" not in pillars:
            pillars.append("marketing")

    # Always suggest community for ORGAN-III products
    if "community" not in pillars:
        pillars.append("community")

    return pillars
