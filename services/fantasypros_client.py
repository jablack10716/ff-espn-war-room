"""FantasyPros API and Consensus Fetcher Service.

Fetches/derives Expert Consensus Rankings (ECR), analyst tier breaks, and consensus
stat projections (including projected receptions, floor P10, and ceiling P90).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

LOGGER = logging.getLogger("fantasypros_client")

FANTASYPROS_BASE_URL = "https://api.fantasypros.com/v2"


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", name or "")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def fetch_fantasypros_ecr(position: str = "OVERALL", scoring_format: str = "HALF_PPR") -> Dict[str, Dict[str, Any]]:
    """Fetch FantasyPros Expert Consensus Rankings.

    Returns dict mapping normalized_name -> {
        "ecr": float,
        "analyst_tier": int,
        "sd": float,
        "best": int,
        "worst": int
    }
    """
    api_key = os.getenv("FANTASYPROS_API_KEY")
    result: Dict[str, Dict[str, Any]] = {}

    if api_key:
        try:
            url = f"{FANTASYPROS_BASE_URL}/json/nfl/{scoring_format.lower()}/consensus-rankings.php"
            headers = {"x-api-key": api_key}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for player in data.get("players", []):
                    name = normalize_name(player.get("player_name", ""))
                    if name:
                        result[name] = {
                            "ecr": float(player.get("rank_ecr", 999)),
                            "analyst_tier": int(player.get("tier", 1)),
                            "sd": float(player.get("rank_std", 0.0)),
                            "best": int(player.get("rank_min", 999)),
                            "worst": int(player.get("rank_max", 999)),
                        }
                return result
        except Exception as exc:
            LOGGER.warning("FantasyPros API request failed: %s", exc)

    # Public consensus fallback scraping/fetching if API key not supplied
    try:
        url = f"https://www.fantasypros.com/nfl/rankings/{position.lower()}-cheatsheets.php"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            # Look for ecrData embedded JSON in public cheat sheet pages
            match = re.search(r"var\s+ecrData\s*=\s*(\{.*?\});", r.text, re.DOTALL)
            if match:
                import json
                ecr_json = json.loads(match.group(1))
                for item in ecr_json.get("players", []):
                    name = normalize_name(item.get("player_name", ""))
                    if name:
                        result[name] = {
                            "ecr": float(item.get("rank_ecr", 999)),
                            "analyst_tier": int(item.get("tier", 1)),
                            "sd": float(item.get("rank_std", 0.0)),
                            "best": int(item.get("rank_min", 999)),
                            "worst": int(item.get("rank_max", 999)),
                        }
    except Exception as exc:
        LOGGER.debug("FantasyPros public scrape fallback skipped/failed: %s", exc)

    return result


def derive_consensus_metrics(
    player_name: str,
    position: str,
    espn_median: float,
    fp_ecr_data: Dict[str, Dict[str, Any]],
    sleeper_adp: Optional[float] = None,
    espn_adp: Optional[float] = None,
) -> Dict[str, Any]:
    """Derive multi-source consensus metrics (blended ADP, consensus tier, projected receptions, floor/ceiling)."""
    norm_name = normalize_name(player_name)
    fp_item = fp_ecr_data.get(norm_name, {})

    # 1. Consensus ADP Calculation
    valid_adps = [adp for adp in (sleeper_adp, espn_adp) if adp is not None and adp > 0]
    if fp_item.get("ecr"):
        valid_adps.append(fp_item["ecr"])
    consensus_adp = round(sum(valid_adps) / len(valid_adps), 2) if valid_adps else (espn_adp or 999.0)

    # 2. Analyst Tier vs Positional Rank Tier
    analyst_tier = fp_item.get("analyst_tier")

    # 3. Projected Receptions (Position-based target/reception share estimates)
    pos = str(position).upper()
    proj_rec = 0.0
    if pos == "WR":
        proj_rec = round(max(30.0, espn_median * 0.38), 1)
    elif pos == "TE":
        proj_rec = round(max(20.0, espn_median * 0.32), 1)
    elif pos == "RB":
        proj_rec = round(max(15.0, espn_median * 0.20), 1)

    # 4. Consensus Floor (P10) & Ceiling (P90) using analyst standard deviation if available
    sd = fp_item.get("sd", 0.0)
    if sd > 0:
        # Standard deviation in analyst ranking translates to projection confidence variance
        floor_p10 = max(0.0, round(espn_median * max(0.60, 1.0 - (sd * 0.04)), 2))
        ceiling_p90 = round(espn_median * min(1.45, 1.0 + (sd * 0.05)), 2)
    else:
        # Defaults based on position volatility
        pos_var = {"QB": (0.88, 1.15), "RB": (0.75, 1.30), "WR": (0.78, 1.28), "TE": (0.72, 1.35), "DST": (0.70, 1.40), "K": (0.80, 1.20)}
        f_mult, c_mult = pos_var.get(pos, (0.80, 1.20))
        floor_p10 = max(0.0, round(espn_median * f_mult, 2))
        ceiling_p90 = round(max(espn_median, espn_median * c_mult), 2)

    return {
        "consensus_adp": consensus_adp,
        "sleeper_adp": sleeper_adp,
        "analyst_tier": analyst_tier,
        "projected_receptions": proj_rec,
        "floor_p10": floor_p10,
        "ceiling_p90": ceiling_p90,
        "fp_ecr": fp_item.get("ecr"),
        "fp_sd": sd,
    }
