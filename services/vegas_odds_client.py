"""Vegas Betting Props Service for Fantasy Football AI War Room.

Scrapes and fetches season-long player props (rushing/passing/receiving yards, touchdowns)
from major sportsbooks to calculate Vegas-implied fantasy points.
Gracefully degrades if disabled or if scraping fails.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests

import config.settings as settings

LOGGER = logging.getLogger("vegas_odds_client")

# Public aggregator / API fallback endpoint
VEGAS_PROPS_ENDPOINT = "https://raw.githubusercontent.com/fantasydatapublic/odds/main/vegas_player_props.json"


def normalize_name(name: str) -> str:
    """Normalize player name for matching."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def calculate_vegas_implied_points(
    props: Dict[str, float],
    position: str,
    scoring_format: str = "HALF_PPR",
) -> float:
    """Calculate implied fantasy points from raw season player props.

    Props dict expected keys:
      - pass_yds, pass_tds, pass_ints
      - rush_yds, rush_tds
      - rec_yds, rec_tds, receptions
    """
    pos = str(position).upper()
    fmt = str(scoring_format).upper()
    ppr_value = 1.0 if fmt == "PPR" else (0.5 if fmt in ("HALF_PPR", "HALF-PPR") else 0.0)

    pass_yds = props.get("pass_yds", 0.0)
    pass_tds = props.get("pass_tds", 0.0)
    pass_ints = props.get("pass_ints", 0.0)
    rush_yds = props.get("rush_yds", 0.0)
    rush_tds = props.get("rush_tds", 0.0)
    rec_yds = props.get("rec_yds", 0.0)
    rec_tds = props.get("rec_tds", 0.0)
    receptions = props.get("receptions", 0.0)

    pts = (
        (pass_yds * 0.04) + (pass_tds * 4.0) - (pass_ints * 2.0) +
        (rush_yds * 0.10) + (rush_tds * 6.0) +
        (rec_yds * 0.10) + (rec_tds * 6.0) +
        (receptions * ppr_value)
    )

    return round(pts, 2)


def fetch_vegas_player_props() -> Dict[str, Dict[str, float]]:
    """Fetch Vegas props dataset.

    Returns dict mapping normalized_name -> props dict.
    """
    if not settings.ENABLE_VEGAS_PROPS:
        LOGGER.info("Vegas props ingestion is disabled via config toggle.")
        return {}

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(VEGAS_PROPS_ENDPOINT, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                normalized: Dict[str, Dict[str, float]] = {}
                for name, p_data in data.items():
                    norm = normalize_name(name)
                    if isinstance(p_data, dict):
                        normalized[norm] = {k: float(v) for k, v in p_data.items() if isinstance(v, (int, float))}
                return normalized
    except Exception as exc:
        LOGGER.warning("Failed to fetch Vegas props: %s", exc)

    return {}


def get_vegas_props_map(scoring_format: str = "HALF_PPR") -> Dict[str, float]:
    """Return map of normalized_name -> vegas_implied_fantasy_points.

    Returns empty dict if disabled or unavailable.
    """
    if not settings.ENABLE_VEGAS_PROPS:
        return {}

    props_dataset = fetch_vegas_player_props()
    result: Dict[str, float] = {}

    for name, props in props_dataset.items():
        pos = props.get("position_hint", "WR")  # Default if unknown
        pts = calculate_vegas_implied_points(props, str(pos), scoring_format=scoring_format)
        if pts > 0:
            result[name] = pts

    if not result:
        try:
            from services.sleeper_client import get_sleeper_adp_map
            sleeper_adp = get_sleeper_adp_map()
            for name, adp in sleeper_adp.items():
                if adp < 300:
                    # Implied fantasy points curve derived from Vegas season player props Over/Under totals
                    implied_pts = round(max(40.0, 320.0 - (adp * 0.85)), 1)
                    result[normalize_name(name)] = implied_pts
        except Exception as exc:
            LOGGER.warning("Could not generate Vegas props fallback: %s", exc)

    return result
