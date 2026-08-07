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


POSITION_VARIANCE: Dict[str, Dict[str, float]] = {
    "QB": {"floor_mult": 0.88, "ceil_mult": 1.12},
    "RB": {"floor_mult": 0.75, "ceil_mult": 1.30},
    "WR": {"floor_mult": 0.78, "ceil_mult": 1.28},
    "TE": {"floor_mult": 0.72, "ceil_mult": 1.35},
    "K": {"floor_mult": 0.80, "ceil_mult": 1.20},
    "DST": {"floor_mult": 0.70, "ceil_mult": 1.40},
}


TEAM_SCHEME_AND_LINE: Dict[str, Dict[str, Any]] = {
    # Default Team Coaching PROE and O-Line Tiers (Tier 1: Top 5, Tier 5: Bottom 5)
    "PHI": {"oline_tier": 1, "proe": "POSITIVE"},
    "DET": {"oline_tier": 1, "proe": "POSITIVE"},
    "KC": {"oline_tier": 1, "proe": "POSITIVE"},
    "BAL": {"oline_tier": 1, "proe": "NEUTRAL"},
    "SF": {"oline_tier": 2, "proe": "NEUTRAL"},
    "BUF": {"oline_tier": 2, "proe": "POSITIVE"},
    "CIN": {"oline_tier": 3, "proe": "POSITIVE"},
    "MIA": {"oline_tier": 2, "proe": "POSITIVE"},
    "MIN": {"oline_tier": 3, "proe": "POSITIVE"},
    "DAL": {"oline_tier": 2, "proe": "POSITIVE"},
    "CAR": {"oline_tier": 5, "proe": "NEGATIVE"},
    "NE": {"oline_tier": 5, "proe": "NEGATIVE"},
    "NYG": {"oline_tier": 5, "proe": "NEGATIVE"},
    "TEN": {"oline_tier": 5, "proe": "NEGATIVE"},
    "WAS": {"oline_tier": 4, "proe": "NEUTRAL"},
}


def apply_stacking_multiplier(
    player: Dict[str, Any], user_roster: Sequence[Dict[str, Any]]
) -> float:
    """Calculate QB-WR/TE Stacking Covariance Multiplier.

    Primary Pass Catcher (WR1/TE1): 1.07x multiplier.
    Secondary Pass Catcher (WR2): 1.04x multiplier.
    """
    pos = str(player.get("position", "")).upper()
    if pos not in ("WR", "TE"):
        return 1.0

    player_team = str(player.get("team") or "").upper()
    if not player_team:
        return 1.0

    # Scan user_roster for drafted QBs
    drafted_qb_teams = {
        str(p.get("team") or "").upper()
        for p in user_roster
        if str(p.get("position", "")).upper() == "QB"
    }

    if player_team in drafted_qb_teams:
        depth_role = str(player.get("depth_role") or "").upper()
        is_primary = (
            player.get("is_primary_target") is True
            or depth_role in ("WR1", "TE1", "PRIMARY")
            or (pos == "TE" and depth_role != "TE2")
        )
        if depth_role == "WR2" or (not is_primary and depth_role != "WR1"):
            return 1.04
        return 1.07

    return 1.0


def blend_vegas_props(player: Dict[str, Any]) -> float:
    """Blend Vegas Market Over/Under prop implied points with fantasy consensus projections.

    Formula: Adjusted_Projection = (0.65 * Fantasy_Consensus_Median) + (0.35 * Vegas_Prop_Implied_Points)
    Fallbacks to pure consensus if Vegas prop data is missing or null.
    """
    median = float(player.get("projection_median") or 0.0)
    vegas_pts = player.get("vegas_projected_pts")
    if vegas_pts is not None and float(vegas_pts) > 0:
        return round(0.65 * median + 0.35 * float(vegas_pts), 4)
    return median


def apply_scheme_and_line_scalars(player: Dict[str, Any]) -> float:
    """Apply Play-Caller PROE (Pass Rate Over Expected) & Offensive Line Efficiency Scalars.

    RBs on Top-5 O-Lines get 1.05x; Bottom-5 O-Lines get 0.95x.
    WRs/TEs under positive PROE play-callers get 1.04x; heavy negative PROE get 0.96x.
    """
    pos = str(player.get("position", "")).upper()
    team = str(player.get("team") or "").upper()
    scheme_info = TEAM_SCHEME_AND_LINE.get(team, {})

    oline_tier = player.get("oline_tier", scheme_info.get("oline_tier", 3))
    proe_status = str(
        player.get("proe_status", scheme_info.get("proe", "NEUTRAL"))
    ).upper()

    mult = 1.0

    if pos == "RB":
        if oline_tier == 1:
            mult *= 1.05
        elif oline_tier == 5:
            mult *= 0.95

    if pos in ("WR", "TE"):
        if proe_status in ("POSITIVE", "HIGH"):
            mult *= 1.04
        elif proe_status in ("NEGATIVE", "HEAVY_NEGATIVE", "LOW"):
            mult *= 0.96

    return round(mult, 4)


def apply_playoff_schedule_modifier(player: Dict[str, Any], round_no: int) -> float:
    """Apply Playoff Climate & Schedule Matchup Weight (Weeks 15-17) for Round 7+.

    If player plays >=2 dome/indoor games or against bottom-10 pass/rush defenses
    in Weeks 15-17, apply a 1.03x Playoff Correlation Multiplier.
    """
    if round_no < 7:
        return 1.0

    dome_games = player.get("playoff_dome_games", 0)
    easy_matchups = player.get("playoff_easy_matchups", 0)
    favorable_flag = player.get("favorable_playoff_schedule") is True

    if dome_games >= 2 or easy_matchups >= 2 or favorable_flag:
        return 1.03

    return 1.0


def calculate_fcvs_raw(player: Dict[str, Any], round_no: int) -> float:
    """Calculate raw Floor-to-Ceiling Variance Shift score based on draft round.

    Rounds 1-5: 80% floor, 20% ceiling
    Rounds 6-9: 50% floor, 50% ceiling
    Rounds 10+: 10% floor, 90% ceiling (with Log-Normal right-tail expansion for late rounds)
    """
    pos = str(player.get("position", "")).upper()
    pos_var = POSITION_VARIANCE.get(pos, {"floor_mult": 0.85, "ceil_mult": 1.15})
    floor_mult = pos_var["floor_mult"]
    ceil_mult = pos_var["ceil_mult"]

    is_rookie = player.get("is_rookie") is True or player.get("experience", 1) == 0
    uncertainty_flag = (
        is_rookie or player.get("uncertainty_flag") is True or pos in ("WR", "TE", "RB")
    )
    if is_rookie:
        floor_mult = max(0.0, floor_mult - 0.15)
        ceil_mult += 0.20

    median = float(player.get("projection_median") or 0.0)
    floor = player.get("projection_floor")
    ceiling = player.get("projection_ceiling")

    floor_val = float(floor) if floor is not None else max(0.0, median * floor_mult)
    ceiling_val = float(ceiling) if ceiling is not None else max(median, median * ceil_mult)

    # Non-Gaussian (Log-Normal) Tail Variance expansion for Round 10+
    if round_no >= 10 and uncertainty_flag:
        flag_val = 1.0 if (is_rookie or player.get("uncertainty_flag") is True) else 0.5
        ceiling_val = ceiling_val * (1.0 + (0.15 * flag_val))

    w_floor = max(0.10, round(0.90 - 0.08 * (round_no - 1), 4))
    w_ceiling = round(1.0 - w_floor, 4)

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


# Flex eligibility sets
FLEX_ELIGIBLE = {"RB", "WR", "TE"}
SUPERFLEX_ELIGIBLE = {"QB", "RB", "WR", "TE"}

# Fractional starter weights for FLEX/SUPERFLEX slot distribution
# Reflects typical optimal usage: FLEX dominated by RBs, SUPERFLEX by QBs.
FLEX_WEIGHTS: Dict[str, float] = {"RB": 0.45, "WR": 0.35, "TE": 0.20}
SUPERFLEX_WEIGHTS: Dict[str, float] = {"QB": 1.0, "RB": 0.0, "WR": 0.0, "TE": 0.0}


def calculate_effective_starters(
    roster_requirements: Dict[str, int],
) -> Dict[str, float]:
    """Calculate effective starter counts per position, distributing FLEX/SUPERFLEX slots.

    SUPERFLEX adds +1.0 to QB starters (nearly all teams start a QB2 in SF).
    FLEX distributes fractionally: +0.45 RB, +0.35 WR, +0.20 TE.

    Returns a dict mapping position -> effective starter count (float).
    """
    effective: Dict[str, float] = {}
    flex_count = roster_requirements.get("FLEX", 0)
    sf_count = roster_requirements.get("SUPERFLEX", 0)

    for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
        base = float(roster_requirements.get(pos, 0))
        # Add FLEX fractional starters
        if flex_count > 0 and pos in FLEX_WEIGHTS:
            base += flex_count * FLEX_WEIGHTS[pos]
        # Add SUPERFLEX fractional starters
        if sf_count > 0 and pos in SUPERFLEX_WEIGHTS:
            base += sf_count * SUPERFLEX_WEIGHTS[pos]
        effective[pos] = base

    return effective


def _count_flex_slots_filled(
    user_roster: Sequence[Dict[str, Any]],
    roster_requirements: Dict[str, int],
) -> Dict[str, int]:
    """Count how many FLEX and SUPERFLEX slots the user has filled.

    Returns {"FLEX": int, "SUPERFLEX": int} representing filled slot counts.
    Assignment priority: overflow players fill FLEX first, then SUPERFLEX.
    QB overflow can only fill SUPERFLEX.
    """
    # Count players by position
    counts: Dict[str, int] = {}
    for p in user_roster:
        pos = str(p.get("position", "")).upper()
        counts[pos] = counts.get(pos, 0) + 1

    # Calculate overflow per position (players beyond base starter requirement)
    overflow: Dict[str, int] = {}
    for pos in ("QB", "RB", "WR", "TE"):
        base_req = roster_requirements.get(pos, 0)
        overflow[pos] = max(0, counts.get(pos, 0) - base_req)

    flex_max = roster_requirements.get("FLEX", 0)
    sf_max = roster_requirements.get("SUPERFLEX", 0)
    flex_filled = 0
    sf_filled = 0

    # Fill FLEX first (RB/WR/TE overflow)
    for pos in ("RB", "WR", "TE"):
        can_assign = min(overflow[pos], flex_max - flex_filled)
        flex_filled += can_assign
        overflow[pos] -= can_assign

    # Fill SUPERFLEX (QB overflow first, then remaining RB/WR/TE overflow)
    qb_to_sf = min(overflow.get("QB", 0), sf_max - sf_filled)
    sf_filled += qb_to_sf
    overflow["QB"] = overflow.get("QB", 0) - qb_to_sf

    for pos in ("RB", "WR", "TE"):
        can_assign = min(overflow[pos], sf_max - sf_filled)
        sf_filled += can_assign
        overflow[pos] -= can_assign

    return {"FLEX": flex_filled, "SUPERFLEX": sf_filled}


def calculate_roster_fit(
    player: Dict[str, Any],
    user_roster: Sequence[Dict[str, Any]],
    round_no: int,
    roster_requirements: Optional[Dict[str, int]] = None,
    available_players: Optional[Sequence[Dict[str, Any]]] = None,
) -> float:
    """Calculate gradient RosterFit multiplier based on positional demand and scarcity.

    Accounts for FLEX and SUPERFLEX slot eligibility when computing positional need.
    """
    if roster_requirements is None:
        roster_requirements = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "SUPERFLEX": 1,
            "DST": 1,
        }

    pos = str(player.get("position", "")).upper()

    # Early DST suppression (K removed from default but still handled)
    if pos in ("K", "DST") and round_no < 10:
        return 0.30

    # Base starter slots for this position
    req_starters = roster_requirements.get(pos, 0)
    current_count = sum(
        1 for p in user_roster if str(p.get("position", "")).upper() == pos
    )

    # Calculate flex slot availability
    flex_slots = _count_flex_slots_filled(user_roster, roster_requirements)
    flex_max = roster_requirements.get("FLEX", 0)
    sf_max = roster_requirements.get("SUPERFLEX", 0)

    # Determine total slots this position can fill
    total_slots = req_starters
    if pos in FLEX_ELIGIBLE:
        total_slots += flex_max
    if pos in SUPERFLEX_ELIGIBLE:
        total_slots += sf_max

    # Effective slots needed = base slots needed + unfilled flex/sf slots this position can fill
    base_slots_needed = req_starters - current_count
    unfilled_flex = (flex_max - flex_slots["FLEX"]) if pos in FLEX_ELIGIBLE else 0
    unfilled_sf = (sf_max - flex_slots["SUPERFLEX"]) if pos in SUPERFLEX_ELIGIBLE else 0
    total_slots_needed = base_slots_needed + unfilled_flex + unfilled_sf

    # Calculate positional scarcity
    remaining_at_pos = 999
    if available_players:
        remaining_at_pos = sum(
            1 for p in available_players
            if str(p.get("position", "")).upper() == pos and p.get("is_available", True)
        )

    mult = 1.0
    if base_slots_needed >= 2:
        mult = 1.50
    elif base_slots_needed == 1:
        if remaining_at_pos <= 15:
            mult = 1.40
        elif remaining_at_pos <= 30:
            mult = 1.20
        else:
            mult = 1.10
    elif total_slots_needed > 0:
        # Base slots filled but FLEX/SUPERFLEX slots available for this position
        if pos == "QB" and unfilled_sf > 0:
            # QB2 for SUPERFLEX is very high value
            if remaining_at_pos <= 20:
                mult = 1.35
            else:
                mult = 1.15
        else:
            # Generic flex fill
            mult = 1.00
    else:
        # All slots filled — bench territory
        if round_no <= 6:
            mult = 0.60
        else:
            mult = 0.80

    # Bye week collision penalty for "onesie" positions (QB, TE)
    if pos in ("QB", "TE") and user_roster:
        player_bye = player.get("bye_week")
        if player_bye is not None and str(player_bye).strip() != "":
            for r_player in user_roster:
                r_pos = str(r_player.get("position", "")).upper()
                r_bye = r_player.get("bye_week")
                if r_pos == pos and r_bye is not None and str(r_bye).strip() != "" and str(player_bye) == str(r_bye):
                    mult *= 0.60
                    break

    return round(mult, 4)


def calculate_vor(
    player: Dict[str, Any],
    available_players: Sequence[Dict[str, Any]],
    roster_requirements: Optional[Dict[str, int]] = None,
    num_teams: int = 12,
    drafted_counts: Optional[Dict[str, int]] = None,
) -> float:
    """Calculate Value Over Replacement (VOR/VORP) for a candidate player.

    Replacement level is defined as the projection of the (num_teams * effective_starters + 1)-th
    player at that specific position.  When FLEX or SUPERFLEX slots are present in
    roster_requirements, effective starters are computed via fractional distribution
    so that QB replacement level correctly accounts for Superflex.
    """
    if roster_requirements is None:
        roster_requirements = {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "SUPERFLEX": 1,
            "DST": 1,
        }

    pos = str(player.get("position", "")).upper()

    # Use effective starters (accounts for FLEX/SUPERFLEX distribution)
    effective = calculate_effective_starters(roster_requirements)
    starters = effective.get(pos, roster_requirements.get(pos, 1))
    total_starters_needed = int(round(num_teams * starters))

    # Adjust replacement index for players already drafted at this position
    drafted_at_pos = 0
    if drafted_counts:
        drafted_at_pos = drafted_counts.get(pos, 0)
    replacement_index = max(0, total_starters_needed - drafted_at_pos)  # 0-indexed

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

    is_full = (fmt == "PPR")
    ppr_multiplier = 1.0 if is_full else 0.5

    # Check for dynamic projected_receptions
    proj_rec = player.get("projected_receptions")
    if proj_rec is not None and float(proj_rec) > 0:
        return round(float(proj_rec) * ppr_multiplier, 2)

    pos = str(player.get("position", "")).upper()

    # First fallback: Calculate via projected_receiving_yards / YPR
    rec_yards = player.get("projected_receiving_yards")
    ypr_map = {"WR": 12.5, "TE": 10.5, "RB": 7.5}
    if rec_yards is not None and float(rec_yards) > 0 and pos in ypr_map:
        est_rec = float(rec_yards) / ypr_map[pos]
        return round(est_rec * ppr_multiplier, 2)

    # Second fallback: Scale PPR bonus as percentage of projection_median
    median = float(player.get("projection_median") or 0.0)
    pct_map = {"WR": 0.25, "TE": 0.20, "RB": 0.15}
    pct = pct_map.get(pos, 0.0)

    return round(median * pct * ppr_multiplier, 2)

