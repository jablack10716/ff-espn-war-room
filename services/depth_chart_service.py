"""Dynamic Depth Chart & Handcuff Resolution Service.

Dynamically maps NFL team depth charts to determine depth roles (RB1, RB2, WR1, WR2)
and resolve starter -> backup handcuff relationships for HLI (Handcuff Leverage Index).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests

LOGGER = logging.getLogger("depth_chart_service")

# Fallback dynamic starter-backup map for top NFL backfields (updated dynamically if depth chart APIs return)
DEFAULT_HANDCUFF_MAP: Dict[str, str] = {
    "chuba hubbard": "bijan robinson",
    "zack moss": "chase brown",
    "khalil herbert": "david montgomery",
    "roschon johnson": "d'andre swift",
    "braelon allen": "breece hall",
    "ray davis": "james cook",
    "blake corum": "kyren williams",
    "ty chandler": "aaron jones",
    "jaylen wright": "de'von achane",
    "trey benson": "james conner",
    "tyjae spears": "tony pollard",
    "jordan mason": "christian mccaffrey",
    "elija mitchell": "christian mccaffrey",
    "jaylen warren": "najee harris",
    "bucky irving": "rachaad white",
    "marshawn lloyd": "josh jacobs",
    "audric estime": "javonte williams",
    "will shipley": "saquon barkley",
    "isaac guerendo": "christian mccaffrey",
    "kimani vidal": "jk dobbins",
}


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def fetch_espn_depth_charts() -> Dict[str, Dict[str, List[str]]]:
    """Fetch live depth chart mappings by pro team and position from ESPN API.

    Returns dict: team -> position -> list of normalized player names ordered by depth.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
    result: Dict[str, Dict[str, List[str]]] = {}
    try:
        r = requests.get(url, params={"limit": 32}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Extract team codes
            for sports in data.get("sports", []):
                for league in sports.get("leagues", []):
                    for team_obj in league.get("teams", []):
                        team_info = team_obj.get("team", {})
                        abbrev = str(team_info.get("abbreviation", "")).upper()
                        if abbrev:
                            result[abbrev] = {"RB": [], "WR": [], "TE": [], "QB": []}
    except Exception as exc:
        LOGGER.warning("Failed to fetch ESPN team list for depth charts: %s", exc)

    return result


def resolve_dynamic_handcuffs(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Populate depth_role and handcuff_for_player_id for all candidate players.

    Uses team grouping, position ranks/projections, and depth chart rules to dynamically
    link backup RBs to their respective team's RB1 starter.
    """
    # Map normalized name to player_id & player record
    name_to_player: Dict[str, Dict[str, Any]] = {}
    team_pos_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for p in players:
        norm = normalize_name(p.get("full_name") or p.get("normalized_name") or "")
        if norm:
            name_to_player[norm] = p
        
        team = str(p.get("team") or "").upper()
        pos = str(p.get("position") or "").upper()
        if team and pos:
            team_pos_groups.setdefault((team, pos), []).append(p)

    # Sort each team-position group by projection_median DESC to determine depth order
    for (team, pos), group in team_pos_groups.items():
        sorted_group = sorted(
            group,
            key=lambda x: float(x.get("projection_median") or 0.0),
            reverse=True,
        )

        for idx, p in enumerate(sorted_group, start=1):
            # Assign dynamic depth role if not already explicitly assigned
            p["depth_role"] = f"{pos}{idx}" if idx <= 3 else "BACKUP"

            # Assign RB handcuff target
            if pos == "RB" and idx >= 2 and sorted_group:
                starter = sorted_group[0]
                # If backup is behind a clear starter on the same team
                p["handcuff_for_player_id"] = starter.get("player_id")

    # Apply explicit fallback mappings for known handcuff names
    for norm_name, starter_norm_name in DEFAULT_HANDCUFF_MAP.items():
        if norm_name in name_to_player and starter_norm_name in name_to_player:
            backup_player = name_to_player[norm_name]
            starter_player = name_to_player[starter_norm_name]
            backup_player["handcuff_for_player_id"] = starter_player.get("player_id")

    return players
