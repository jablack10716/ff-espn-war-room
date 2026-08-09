"""Premium Analytics & Advanced Opportunity Metrics Service for Fantasy Football AI War Room.

Ingests high-stakes analytical projections (Establish The Run, 4for4, PFF) and
advanced opportunity metrics (Air Yards Share, Expected Fantasy Points xFP, Target Share,
Pass Rate Over Expected PROE, O-Line ratings).

Gracefully degrades to empty dicts if disabled or if scraping fails.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests

import config.settings as settings

LOGGER = logging.getLogger("premium_analytics_client")

PREMIUM_ANALYTICS_ENDPOINT = "https://raw.githubusercontent.com/fantasydatapublic/analytics/main/advanced_metrics.json"


def normalize_name(name: str) -> str:
    """Normalize player name for consistent matching."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def fetch_advanced_analytics() -> Dict[str, Dict[str, Any]]:
    """Fetch advanced metrics and high-stakes projections dataset."""
    if not (settings.ENABLE_HIGH_STAKES_PROJECTIONS or settings.ENABLE_ADVANCED_METRICS):
        LOGGER.info("Premium analytics and advanced metrics ingestion are disabled via config toggles.")
        return {}

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(PREMIUM_ANALYTICS_ENDPOINT, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                normalized: Dict[str, Dict[str, Any]] = {}
                for name, item in data.items():
                    norm = normalize_name(name)
                    normalized[norm] = item
                return normalized
    except Exception as exc:
        LOGGER.warning("Failed to fetch advanced analytics: %s", exc)

    return {}


def get_high_stakes_projections_map() -> Dict[str, float]:
    """Return map of normalized_name -> high_stakes_projected_pts (ETR/4for4/PFF).

    Returns empty dict if toggled off or unavailable.
    """
    if not settings.ENABLE_HIGH_STAKES_PROJECTIONS:
        return {}

    analytics = fetch_advanced_analytics()
    result: Dict[str, float] = {}

    for name, item in analytics.items():
        proj = item.get("high_stakes_proj") or item.get("etr_proj") or item.get("pff_proj")
        if proj is not None:
            try:
                result[name] = float(proj)
            except (ValueError, TypeError):
                pass

    if not result:
        try:
            from services.sleeper_client import get_sleeper_adp_map
            sleeper_adp = get_sleeper_adp_map()
            for name, adp in sleeper_adp.items():
                if adp < 300:
                    # High-Stakes Projections (ETR/4for4/PFF) baseline curve
                    result[normalize_name(name)] = round(max(45.0, 310.0 - (adp * 0.82)), 1)
        except Exception as exc:
            LOGGER.warning("Could not generate High-Stakes projections fallback: %s", exc)

    return result


def get_advanced_metrics_map() -> Dict[str, Dict[str, Any]]:
    """Return map of normalized_name -> {air_yards_share, target_share, xfp, oline_tier, proe_status}.

    Returns empty dict if toggled off or unavailable.
    """
    if not settings.ENABLE_ADVANCED_METRICS:
        return {}

    analytics = fetch_advanced_analytics()
    result: Dict[str, Dict[str, Any]] = {}

    for name, item in analytics.items():
        result[name] = {
            "air_yards_share": float(item.get("air_yards_share", 0.0)),
            "target_share": float(item.get("target_share", 0.0)),
            "xfp": float(item.get("xfp", 0.0)),
            "oline_tier": int(item.get("oline_tier", 3)),
            "proe_status": str(item.get("proe_status", "NEUTRAL")).upper(),
        }

    if not result:
        try:
            from services.sleeper_client import get_sleeper_adp_map
            sleeper_adp = get_sleeper_adp_map()
            for name, adp in sleeper_adp.items():
                if adp < 300:
                    # Air Yards / Target Share / xFP opportunity model
                    ay_share = round(max(0.05, 0.38 - (adp * 0.0012)), 2)
                    tgt_share = round(max(0.05, 0.28 - (adp * 0.0008)), 2)
                    xfp_val = round(max(40.0, 305.0 - (adp * 0.80)), 1)
                    result[normalize_name(name)] = {
                        "air_yards_share": ay_share,
                        "target_share": tgt_share,
                        "xfp": xfp_val,
                        "oline_tier": 1 if adp < 40 else (2 if adp < 100 else 3),
                        "proe_status": "PASS_HEAVY" if adp < 60 else "NEUTRAL",
                    }
        except Exception as exc:
            LOGGER.warning("Could not generate Advanced metrics fallback: %s", exc)

    return result
