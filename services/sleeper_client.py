"""Sleeper API Client for Fantasy Football AI War Room.

Fetches player metadata, live projections, ADP, and trending players from Sleeper's
free public REST API (https://api.sleeper.app/v1). No API key required.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import requests

LOGGER = logging.getLogger("sleeper_client")

SLEEPER_BASE_URL = "https://api.sleeper.app/v1"


def fetch_sleeper_players() -> Dict[str, Dict[str, Any]]:
    """Fetch full NFL player database from Sleeper.

    Returns dict mapping sleeper player_id -> player dict.
    """
    url = f"{SLEEPER_BASE_URL}/players/nfl"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        LOGGER.warning("Sleeper players endpoint returned HTTP %s", r.status_code)
    except Exception as exc:
        LOGGER.warning("Failed to fetch Sleeper players: %s", exc)
    return {}


def fetch_sleeper_projections(season_year: int = 2026) -> List[Dict[str, Any]]:
    """Fetch season projections for NFL players from Sleeper."""
    url = f"{SLEEPER_BASE_URL}/projections/nfl/{season_year}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        LOGGER.warning("Sleeper projections endpoint returned HTTP %s", r.status_code)
    except Exception as exc:
        LOGGER.warning("Failed to fetch Sleeper projections: %s", exc)
    return []


def fetch_sleeper_trending_players(type_: str = "add", lookback_hours: int = 24, limit: int = 25) -> List[Dict[str, Any]]:
    """Fetch trending players (adds or drops) over recent window.

    type_: "add" or "drop"
    """
    url = f"{SLEEPER_BASE_URL}/players/nfl/trending/{type_}"
    params = {"lookback_hours": lookback_hours, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as exc:
        LOGGER.warning("Failed to fetch Sleeper trending players: %s", exc)
    return []


def get_sleeper_adp_map(season_year: int = 2026) -> Dict[str, float]:
    """Fetch Sleeper player rankings/ADP and return dict mapping normalized_name -> sleeper_adp."""
    adp_map: Dict[str, float] = {}
    players_data = fetch_sleeper_players()
    if players_data:
        for p in players_data.values():
            first = str(p.get("first_name", "")).strip().lower()
            last = str(p.get("last_name", "")).strip().lower()
            full_name = str(p.get("full_name", "")).strip().lower() or f"{first} {last}".strip()
            rank = p.get("search_rank")
            if full_name and rank is not None:
                try:
                    val = float(rank)
                    if 0 < val < 900:
                        adp_map[full_name] = val
                except (ValueError, TypeError):
                    pass

    if not adp_map:
        projections = fetch_sleeper_projections(season_year)
        for p in projections:
            player_data = p.get("player") or {}
            first = str(player_data.get("first_name", "")).strip().lower()
            last = str(player_data.get("last_name", "")).strip().lower()
            full = f"{first} {last}".strip()
            adp = p.get("adp") or p.get("stats", {}).get("adp_half_ppr") or p.get("stats", {}).get("adp_ppr")
            if full and adp:
                try:
                    adp_map[full] = float(adp)
                except (ValueError, TypeError):
                    pass

    return adp_map
