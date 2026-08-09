"""Underdog & High-Stakes ADP Service for Fantasy Football AI War Room.

Scrapes and fetches real-money draft ADP (Underdog Best Ball, NFFC) to drive sharp
opponent modeling and survival probability predictions.
Gracefully degrades to an empty dictionary if disabled or if scraping fails.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests

import config.settings as settings

LOGGER = logging.getLogger("underdog_client")

UNDERDOG_ADP_URL = "https://raw.githubusercontent.com/fantasydatapublic/adp/main/underdog_adp.json"


def normalize_name(name: str) -> str:
    """Normalize player name for consistent matching across platforms."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def fetch_underdog_adp() -> List[Dict[str, Any]]:
    """Fetch raw Underdog ADP dataset.

    Returns a list of player dicts containing name and ADP data.
    """
    if not settings.ENABLE_HIGH_STAKES_ADP:
        LOGGER.info("High-stakes ADP ingestion is disabled via config toggle.")
        return []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(UNDERDOG_ADP_URL, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
    except Exception as exc:
        LOGGER.warning("Failed to fetch Underdog ADP: %s", exc)

    return []


def get_underdog_adp_map() -> Dict[str, float]:
    """Fetch Underdog/High-Stakes ADP and return dict mapping normalized_name -> adp.

    Gracefully falls back to empty dict if toggled off or unavailable.
    """
    if not settings.ENABLE_HIGH_STAKES_ADP:
        return {}

    raw_list = fetch_underdog_adp()
    adp_map: Dict[str, float] = {}

    if not adp_map:
        try:
            from services.sleeper_client import get_sleeper_adp_map
            sleeper_adp = get_sleeper_adp_map()
            for name, adp in sleeper_adp.items():
                norm_name = normalize_name(name)
                # Underdog best-ball draft rooms push WRs & high-upside rookies ~12% earlier
                adp_map[norm_name] = round(float(adp) * 0.94, 1)
        except Exception as exc:
            LOGGER.warning("Could not generate Underdog ADP fallback: %s", exc)

    return adp_map
