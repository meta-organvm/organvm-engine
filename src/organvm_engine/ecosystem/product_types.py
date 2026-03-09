"""Product type templates for pillar DNA generation.

Pure data module — maps product types to default pillar configurations.
Each product type defines scan scopes, artifact cadences, and gen/crit
prompts that drive the pillar DNA scaffolding.
"""

from __future__ import annotations

LIFECYCLE_STAGES = [
    "conception", "research", "planning", "building",
    "live", "optimizing", "mature", "sunset",
]

PRODUCT_TYPES: dict[str, dict] = {
    "saas": {
        "description": "Software-as-a-Service web application",
        "key_pillars": ["marketing", "revenue", "content"],
        "pillar_defaults": {
            "delivery": {
                "scan_scope": ["web_app", "api", "mobile"],
                "artifacts": [
                    {"name": "uptime-monitoring", "cadence": "weekly", "staleness_days": 14},
                    {"name": "deployment-pipeline", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "revenue": {
                "scan_scope": ["subscription", "freemium", "enterprise_license", "api_usage"],
                "artifacts": [
                    {"name": "pricing-comparison", "cadence": "monthly", "staleness_days": 45},
                    {"name": "churn-analysis", "cadence": "quarterly", "staleness_days": 120},
                    {
                        "name": "revenue-model-landscape",
                        "cadence": "quarterly",
                        "staleness_days": 120,
                    },
                ],
            },
            "marketing": {
                "scan_scope": [
                    "seo", "content_marketing", "producthunt", "hackernews",
                    "paid_ads", "saas_directories",
                ],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                    {"name": "channel-strategy", "cadence": "quarterly", "staleness_days": 120},
                    {"name": "competitor-profiles", "cadence": "monthly", "staleness_days": 60},
                ],
            },
            "content": {
                "scan_scope": ["blog", "docs_site", "tutorials", "case_studies", "newsletter"],
                "artifacts": [
                    {"name": "content-calendar", "cadence": "monthly", "staleness_days": 45},
                    {"name": "seo-audit", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "community": {
                "scan_scope": ["discord", "github_discussions", "forum"],
                "artifacts": [
                    {"name": "community-health", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "listings": {
                "scan_scope": ["g2", "alternativeto", "product_hunt", "capterra"],
                "artifacts": [
                    {"name": "listing-audit", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
        },
    },
    "browser_extension": {
        "description": "Browser extension (Chrome, Firefox, etc.)",
        "key_pillars": ["listings", "delivery"],
        "pillar_defaults": {
            "delivery": {
                "scan_scope": ["chrome_web_store", "firefox_addons", "edge_addons"],
                "artifacts": [
                    {
                        "name": "store-listing-optimization",
                        "cadence": "monthly",
                        "staleness_days": 45,
                    },
                    {"name": "review-monitoring", "cadence": "weekly", "staleness_days": 14},
                ],
            },
            "listings": {
                "scan_scope": [
                    "chrome_web_store", "alternativeto", "product_hunt",
                ],
                "artifacts": [
                    {"name": "store-ranking", "cadence": "weekly", "staleness_days": 14},
                    {"name": "competitor-extensions", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "marketing": {
                "scan_scope": ["seo", "content_marketing", "social_organic", "review_sites"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "revenue": {
                "scan_scope": ["freemium", "one_time_purchase", "subscription"],
                "artifacts": [
                    {"name": "pricing-comparison", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
        },
    },
    "trading": {
        "description": "Trading platform or DeFi tool",
        "key_pillars": ["revenue", "community"],
        "pillar_defaults": {
            "revenue": {
                "scan_scope": ["trading_fees", "defi_aggregators", "subscription"],
                "artifacts": [
                    {"name": "fee-comparison", "cadence": "monthly", "staleness_days": 45},
                    {"name": "liquidity-analysis", "cadence": "weekly", "staleness_days": 14},
                ],
            },
            "community": {
                "scan_scope": ["discord", "telegram", "trading_forums", "reddit"],
                "artifacts": [
                    {"name": "community-health", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "marketing": {
                "scan_scope": ["fintech_press", "crypto_media", "social_organic"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "delivery": {
                "scan_scope": ["web_app", "api", "mobile"],
                "artifacts": [
                    {"name": "uptime-monitoring", "cadence": "weekly", "staleness_days": 14},
                ],
            },
        },
    },
    "creative_tool": {
        "description": "Creative/design/music tool",
        "key_pillars": ["community", "content"],
        "pillar_defaults": {
            "community": {
                "scan_scope": ["discord", "creative_communities", "reddit", "forum"],
                "artifacts": [
                    {"name": "community-health", "cadence": "monthly", "staleness_days": 45},
                    {"name": "showcase-gallery", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "content": {
                "scan_scope": ["youtube", "tutorials", "blog", "docs_site"],
                "artifacts": [
                    {"name": "tutorial-funnel", "cadence": "quarterly", "staleness_days": 120},
                    {"name": "content-calendar", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "marketing": {
                "scan_scope": ["producthunt", "creative_press", "social_organic", "influencer"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "delivery": {
                "scan_scope": ["web_app", "desktop_app", "npm_package"],
                "artifacts": [
                    {"name": "deployment-pipeline", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
        },
    },
    "library": {
        "description": "Software library or package (npm, PyPI, etc.)",
        "key_pillars": ["listings", "delivery"],
        "pillar_defaults": {
            "delivery": {
                "scan_scope": ["npm_package", "pypi_package", "api"],
                "artifacts": [
                    {"name": "api-comparison", "cadence": "quarterly", "staleness_days": 120},
                    {"name": "download-tracking", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "listings": {
                "scan_scope": ["npm_registry", "pypi", "github_stars", "docs_site"],
                "artifacts": [
                    {"name": "package-ranking", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "content": {
                "scan_scope": ["docs_site", "tutorials", "blog", "changelog"],
                "artifacts": [
                    {"name": "docs-audit", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "marketing": {
                "scan_scope": ["hackernews", "reddit", "dev_communities", "open_source"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                ],
            },
        },
    },
    "content_platform": {
        "description": "Content-focused platform (blog, newsletter, publishing)",
        "key_pillars": ["content", "marketing"],
        "pillar_defaults": {
            "content": {
                "scan_scope": ["blog", "newsletter", "podcast", "social_media"],
                "artifacts": [
                    {"name": "content-calendar", "cadence": "monthly", "staleness_days": 45},
                    {"name": "seo-audit", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "marketing": {
                "scan_scope": ["seo", "social_organic", "email_marketing", "content_aggregators"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                    {"name": "channel-strategy", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "delivery": {
                "scan_scope": ["web_app", "api"],
                "artifacts": [
                    {"name": "deployment-pipeline", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
        },
    },
    "marketplace": {
        "description": "Two-sided marketplace",
        "key_pillars": ["revenue", "community"],
        "pillar_defaults": {
            "revenue": {
                "scan_scope": ["marketplace_commission", "subscription", "advertising"],
                "artifacts": [
                    {"name": "gmv-tracking", "cadence": "monthly", "staleness_days": 45},
                    {"name": "seller-acquisition", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "community": {
                "scan_scope": ["forum", "discord", "trust_systems", "review_systems"],
                "artifacts": [
                    {"name": "community-health", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "marketing": {
                "scan_scope": ["seo", "content_marketing", "paid_ads", "press"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "delivery": {
                "scan_scope": ["web_app", "mobile", "api"],
                "artifacts": [
                    {"name": "deployment-pipeline", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
        },
    },
    "game": {
        "description": "Game or interactive experience",
        "key_pillars": ["community", "marketing"],
        "pillar_defaults": {
            "community": {
                "scan_scope": ["discord", "reddit", "streaming", "game_forums"],
                "artifacts": [
                    {"name": "player-retention", "cadence": "monthly", "staleness_days": 45},
                    {"name": "streamer-outreach", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "marketing": {
                "scan_scope": ["game_press", "streaming_platforms", "social_organic", "influencer"],
                "artifacts": [
                    {"name": "landscape-snapshot", "cadence": "monthly", "staleness_days": 45},
                ],
            },
            "delivery": {
                "scan_scope": ["web_app", "desktop_app", "steam", "itch_io"],
                "artifacts": [
                    {"name": "platform-presence", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
            "revenue": {
                "scan_scope": ["one_time_purchase", "in_app_purchase", "subscription"],
                "artifacts": [
                    {"name": "pricing-comparison", "cadence": "quarterly", "staleness_days": 120},
                ],
            },
        },
    },
}

# Tag-based heuristics for product type inference
_TAG_HINTS: dict[str, list[str]] = {
    "saas": ["saas", "nextjs", "react", "web-app", "dashboard"],
    "browser_extension": ["chrome", "browser", "extension", "firefox"],
    "trading": ["trading", "defi", "blockchain", "crypto", "dex"],
    "creative_tool": ["creative", "music", "art", "design", "audio", "visual", "generative"],
    "library": ["library", "package", "npm", "pypi", "sdk", "framework"],
    "content_platform": ["blog", "newsletter", "publishing", "content", "editorial"],
    "marketplace": ["marketplace", "platform", "two-sided", "ecommerce"],
    "game": ["game", "interactive", "gaming", "play"],
}

_REVENUE_HINTS: dict[str, str] = {
    "subscription": "saas",
    "freemium": "saas",
    "marketplace_commission": "marketplace",
    "in_app_purchase": "game",
}


def infer_product_type(
    seed_data: dict | None = None,
    registry_data: dict | None = None,
) -> str:
    """Infer product type from seed tags and registry data.

    Uses tag matching heuristics, then revenue model, then falls back to 'saas'.
    """
    scores: dict[str, int] = {pt: 0 for pt in PRODUCT_TYPES}

    if seed_data:
        tags = seed_data.get("metadata", {}).get("tags", []) or []
        tags_lower = [t.lower() for t in tags]

        for ptype, hints in _TAG_HINTS.items():
            for hint in hints:
                if any(hint in tag for tag in tags_lower):
                    scores[ptype] += 1

    if registry_data:
        rev_model = (registry_data.get("revenue_model") or "").lower()
        if rev_model in _REVENUE_HINTS:
            scores[_REVENUE_HINTS[rev_model]] += 2

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return "saas"


def get_pillar_defaults(product_type: str, pillar: str) -> dict | None:
    """Return default DNA config for a pillar given product type.

    Returns None if the product type or pillar has no defaults.
    """
    pt = PRODUCT_TYPES.get(product_type)
    if not pt:
        return None
    return pt.get("pillar_defaults", {}).get(pillar)


# Default gen/crit prompts keyed by pillar
DEFAULT_GEN_PROMPTS: dict[str, list[dict]] = {
    "marketing": [
        {
            "id": "landscape_scan",
            "trigger": "monthly",
            "prompt": (
                "Scan the full marketing landscape for {product_type} products. "
                "Identify all active platforms, emerging channels, and market gaps. "
                "Compare against our current arms."
            ),
        },
        {
            "id": "competitor_deep_dive",
            "trigger": "monthly",
            "prompt": (
                "Research competitors in {scan_scope}. For each, document: "
                "positioning, pricing, channels used, content strategy, "
                "community size, and unique differentiators."
            ),
        },
    ],
    "revenue": [
        {
            "id": "pricing_landscape",
            "trigger": "quarterly",
            "prompt": (
                "Survey pricing models across {product_type} competitors. "
                "Document: tiers, feature gates, trial structures, and "
                "conversion tactics."
            ),
        },
    ],
    "delivery": [
        {
            "id": "platform_coverage",
            "trigger": "quarterly",
            "prompt": (
                "Audit delivery platforms for {product_type}. "
                "Compare our presence against top competitors."
            ),
        },
    ],
}

DEFAULT_CRIT_PROMPTS: dict[str, list[dict]] = {
    "marketing": [
        {
            "id": "coverage_check",
            "prompt": (
                "Compare our marketing arms against the landscape snapshot. "
                "Are we missing high-value platforms? "
                "Are any current arms underperforming?"
            ),
        },
    ],
    "revenue": [
        {
            "id": "model_fit",
            "prompt": (
                "Evaluate our revenue model against the competitive landscape. "
                "Are there untapped monetization opportunities?"
            ),
        },
    ],
}
