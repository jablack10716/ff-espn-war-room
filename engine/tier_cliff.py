"""Tier cliff detection and Positional Run Velocity (PRV) helpers.

Provides functionality to evaluate positional tier cliffs, calculate run share
over rolling draft windows, and compute PRV urgency boost multipliers.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple


def get_available_tier_info(
    position: str, available_players: Sequence[Dict[str, Any]]
) -> Tuple[int, int]:
    """Get the current top available tier and count of players in that tier.

    Returns (top_tier_number, count_in_top_tier).
    If no available players for position, returns (99, 0).
    """
    pos_players = [
        p for p in available_players
        if str(p.get("position", "")).upper() == position.upper()
        and p.get("is_available", True)
    ]

    if not pos_players:
        return (99, 0)

    min_tier = min(int(p.get("tier", 99)) for p in pos_players)
    count_in_tier = sum(
        1 for p in pos_players if int(p.get("tier", 99)) == min_tier
    )

    return (min_tier, count_in_tier)


def detect_tier_cliff(
    position: str, available_players: Sequence[Dict[str, Any]]
) -> bool:
    """Detect if an imminent tier cliff exists for a position.

    A tier cliff is imminent if the count of available players in the top
    remaining tier for that position is <= 2.
    """
    _, count_in_tier = get_available_tier_info(position, available_players)
    return 0 < count_in_tier <= 2


def calculate_run_share(
    recent_picks_last_10: Sequence[Dict[str, Any]], position: str
) -> float:
    """Calculate the position share in the rolling window of the last 10 picks.

    Returns float in range [0.0, 1.0].
    """
    if not recent_picks_last_10:
        return 0.0

    window = recent_picks_last_10[-10:]
    n = len(window)
    if n == 0:
        return 0.0

    pos_count = sum(
        1 for p in window
        if str(p.get("position", "")).upper() == position.upper()
        and str(p.get("event_type", "PICK")).upper() == "PICK"
    )

    return pos_count / float(n)


def calculate_prv_multiplier(
    position: str,
    available_players: Sequence[Dict[str, Any]],
    recent_picks_last_10: Sequence[Dict[str, Any]],
) -> float:
    """Calculate gradient Positional Run Velocity (PRV) multiplier based on tier cliff severity and run share."""
    run_share = calculate_run_share(recent_picks_last_10, position)
    _, count_in_tier = get_available_tier_info(position, available_players)

    if count_in_tier == 1 and run_share > 0.30:
        return 1.2500
    elif count_in_tier == 2 and run_share > 0.30:
        return 1.1800
    elif count_in_tier == 3 and run_share > 0.35:
        return 1.1200
    elif 4 <= count_in_tier <= 5 and run_share > 0.40:
        return 1.0600

    return 1.0000
