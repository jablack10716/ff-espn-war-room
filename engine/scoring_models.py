"""Deterministic scoring model helpers for Ada quant engine.

Provides functions for FCVS (Floor-to-Ceiling Variance Shift), HLI (Handcuff
Leverage Index), RosterFit factors, and mathematical normalization.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence


def min_max_normalize(values: Sequence[float]) -> List[float]:
    """Min-Max normalize a sequence of floats to the range [0.0, 1.0].

    Returns 0.5 for all elements if max == min.
    """
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)
    rng = max_val - min_val

    if abs(rng) < 1e-9:
        return [0.5 for _ in values]

    return [(v - min_val) / rng for v in values]


def z_score_normalize(values: Sequence[float]) -> List[float]:
    """Z-score normalize a sequence of floats (mean=0, std=1).

    Returns 0.0 for all elements if standard deviation is zero.
    """
    if not values:
        return []

    n = len(values)
    if n == 1:
        return [0.0]

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std_dev = math.sqrt(variance)

    if std_dev < 1e-9:
        return [0.0 for _ in values]

    return [(v - mean) / std_dev for v in values]


def calculate_fcvs_raw(player: Dict[str, Any], round_no: int) -> float:
    """Calculate raw Floor-to-Ceiling Variance Shift score based on draft round.

    Rounds 1-5: 80% floor, 20% ceiling
    Rounds 6-9: 50% floor, 50% ceiling
    Rounds 10+: 10% floor, 90% ceiling
    """
    median = float(player.get("projection_median") or 0.0)
    floor = player.get("projection_floor")
    ceiling = player.get("projection_ceiling")

    floor_val = float(floor) if floor is not None else max(0.0, median * 0.85)
    ceiling_val = float(ceiling) if ceiling is not None else max(median, median * 1.15)

    if round_no <= 5:
        w_floor, w_ceiling = 0.80, 0.20
    elif round_no <= 9:
        w_floor, w_ceiling = 0.50, 0.50
    else:
        w_floor, w_ceiling = 0.10, 0.90

    return round(w_floor * floor_val + w_ceiling * ceiling_val, 4)


def calculate_hli_raw(
    player: Dict[str, Any],
    user_roster: Sequence[Dict[str, Any]],
    all_rosters: Dict[int, Sequence[Dict[str, Any]]],
    user_team_slot: int,
) -> float:
    """Calculate raw Handcuff Leverage Index (HLI) score.

    Applies protection multipliers to running back backups:
    - 1.5x for direct backup to user's own RB1
    - 1.3x for backup to an opponent's unhandcuffed RB1
    - 0.5x for unowned low-tier backup
    - 1.0x default
    """
    pos = str(player.get("position", "")).upper()
    if pos != "RB":
        return 0.0

    median = float(player.get("projection_median") or 0.0)
    depth_role = str(player.get("depth_role") or "").upper()
    handcuff_target = player.get("handcuff_for_player_id")
    player_team = str(player.get("team") or "").upper()

    # Identify user's RB1 and opponent RB1s
    user_rbs = [p for p in user_roster if str(p.get("position")).upper() == "RB"]
    user_rb1_id = user_rbs[0].get("player_id") if user_rbs else None
    user_rb1_team = str(user_rbs[0].get("team", "")).upper() if user_rbs else None

    # Check if backup to user's own RB1
    is_user_backup = False
    if user_rb1_id and handcuff_target == user_rb1_id:
        is_user_backup = True
    elif user_rb1_team and player_team == user_rb1_team and depth_role in ("RB2", "BACKUP"):
        is_user_backup = True

    if is_user_backup:
        return round(median * 1.5, 4)

    # Check if backup to an opponent's unhandcuffed RB1
    is_opponent_backup = False
    for team_slot, roster in all_rosters.items():
        if team_slot == user_team_slot:
            continue
        opp_rbs = [p for p in roster if str(p.get("position")).upper() == "RB"]
        if opp_rbs:
            opp_rb1 = opp_rbs[0]
            opp_rb1_id = opp_rb1.get("player_id")
            opp_rb1_team = str(opp_rb1.get("team", "")).upper()

            # Check if opponent already holds the handcuff
            opp_handcuff_held = any(
                p.get("handcuff_for_player_id") == opp_rb1_id
                or (str(p.get("team")).upper() == opp_rb1_team and str(p.get("depth_role")).upper() in ("RB2", "BACKUP"))
                for p in opp_rbs[1:]
            )

            if not opp_handcuff_held:
                if handcuff_target == opp_rb1_id or (player_team == opp_rb1_team and depth_role in ("RB2", "BACKUP")):
                    is_opponent_backup = True
                    break

    if is_opponent_backup:
        return round(median * 1.3, 4)

    # Low-tier backup check
    if depth_role in ("RB3", "RB4", "BACKUP", "RESERVE") and median < 50.0:
        return round(median * 0.5, 4)

    return round(median * 1.0, 4)


def calculate_roster_fit(
    player: Dict[str, Any],
    user_roster: Sequence[Dict[str, Any]],
    round_no: int,
    roster_requirements: Optional[Dict[str, int]] = None,
    available_players: Optional[Sequence[Dict[str, Any]]] = None,
) -> float:
    """Calculate gradient RosterFit multiplier based on positional demand and scarcity."""
    if roster_requirements is None:
        roster_requirements = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "K": 1,
            "DST": 1,
        }

    pos = str(player.get("position", "")).upper()

    # Early K/DST suppression
    if pos in ("K", "DST") and round_no < 10:
        return 0.30

    req_starters = roster_requirements.get(pos, 1)
    current_count = sum(
        1 for p in user_roster if str(p.get("position", "")).upper() == pos
    )

    slots_needed = req_starters - current_count

    # Calculate positional scarcity
    remaining_at_pos = 999
    if available_players:
        remaining_at_pos = sum(
            1 for p in available_players
            if str(p.get("position", "")).upper() == pos and p.get("is_available", True)
        )

    mult = 1.0
    if slots_needed >= 2:
        mult = 1.50
    elif slots_needed == 1:
        if remaining_at_pos <= 15:
            mult = 1.40
        elif remaining_at_pos <= 30:
            mult = 1.20
        else:
            mult = 1.10
    else:  # slots_needed <= 0
        if round_no <= 6:
            mult = 0.60
        else:
            mult = 0.80

    if round_no >= 8 and pos in ("QB", "TE") and current_count == 0:
        mult = max(mult, 1.50)

    return round(mult, 4)


def calculate_vor(
    player: Dict[str, Any],
    available_players: Sequence[Dict[str, Any]],
    roster_requirements: Optional[Dict[str, int]] = None,
    num_teams: int = 12,
) -> float:
    """Calculate Value Over Replacement (VOR/VORP) for a candidate player.

    Replacement level is defined as the projection of the (num_teams * starters + 1)-th player
    at that specific position.
    """
    if roster_requirements is None:
        roster_requirements = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "K": 1,
            "DST": 1,
        }

    pos = str(player.get("position", "")).upper()
    starters = roster_requirements.get(pos, 1)
    replacement_index = num_teams * starters  # 0-indexed: represents the (num_teams * starters + 1)-th player

    pos_players = [
        p for p in available_players
        if str(p.get("position", "")).upper() == pos
    ]
    if not pos_players:
        return 0.0

    pos_sorted = sorted(
        pos_players,
        key=lambda x: float(x.get("projection_median") or 0.0),
        reverse=True,
    )

    if replacement_index < len(pos_sorted):
        baseline = float(pos_sorted[replacement_index].get("projection_median") or 0.0)
    else:
        baseline = float(pos_sorted[-1].get("projection_median") or 0.0)

    player_proj = float(player.get("projection_median") or 0.0)
    return round(player_proj - baseline, 4)


def apply_ppr_adjustment(
    player: Dict[str, Any],
    scoring_format: str,  # "PPR", "HALF_PPR", "STANDARD"
) -> float:
    """Calculate PPR projection adjustment based on position and scoring format."""
    fmt = str(scoring_format).upper()
    if fmt == "STANDARD":
        return 0.0

    pos = str(player.get("position", "")).upper()
    is_full = (fmt == "PPR")

    if pos == "WR":
        return 85.0 if is_full else 42.5
    elif pos == "TE":
        return 55.0 if is_full else 27.5
    elif pos == "RB":
        return 40.0 if is_full else 20.0

    return 0.0
