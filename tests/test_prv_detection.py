"""Unit tests for tier cliff detection and Positional Run Velocity (PRV)."""

import pytest
from engine.tier_cliff import (
    calculate_prv_multiplier,
    calculate_run_share,
    detect_tier_cliff,
    get_available_tier_info,
)


@pytest.fixture
def players_with_cliff():
    return [
        {"player_id": "rb1", "position": "RB", "tier": 1, "is_available": True},
        {"player_id": "rb2", "position": "RB", "tier": 1, "is_available": True},
        {"player_id": "rb3", "position": "RB", "tier": 2, "is_available": True},
        {"player_id": "wr1", "position": "WR", "tier": 1, "is_available": True},
        {"player_id": "wr2", "position": "WR", "tier": 1, "is_available": True},
        {"player_id": "wr3", "position": "WR", "tier": 1, "is_available": True},
    ]


def test_detect_tier_cliff(players_with_cliff):
    # Tier 1 RB has 2 players -> cliff is imminent
    assert detect_tier_cliff("RB", players_with_cliff) is True

    # Tier 1 WR has 3 players -> no cliff yet
    assert detect_tier_cliff("WR", players_with_cliff) is False


def test_calculate_run_share():
    # 5 out of last 10 picks are RBs -> 50% share
    recent_picks = [
        {"position": "RB", "event_type": "PICK"},
        {"position": "RB", "event_type": "PICK"},
        {"position": "WR", "event_type": "PICK"},
        {"position": "RB", "event_type": "PICK"},
        {"position": "QB", "event_type": "PICK"},
        {"position": "RB", "event_type": "PICK"},
        {"position": "TE", "event_type": "PICK"},
        {"position": "RB", "event_type": "PICK"},
        {"position": "WR", "event_type": "PICK"},
        {"position": "WR", "event_type": "PICK"},
    ]

    assert calculate_run_share(recent_picks, "RB") == 0.5
    assert calculate_run_share(recent_picks, "WR") == 0.3


def test_prv_multiplier_triggered(players_with_cliff):
    # 5 out of 10 picks are RBs (share = 0.5 > 0.30) AND RB tier cliff (2 left)
    recent_picks = [{"position": "RB", "event_type": "PICK"}] * 5 + [{"position": "WR", "event_type": "PICK"}] * 5

    mult = calculate_prv_multiplier("RB", players_with_cliff, recent_picks)
    assert mult == 1.18

    # If only 1 player left in tier 1 RB
    players_single_cliff = [
        {"player_id": "rb1", "position": "RB", "tier": 1, "is_available": True},
        {"player_id": "rb3", "position": "RB", "tier": 2, "is_available": True},
    ]
    mult_severe = calculate_prv_multiplier("RB", players_single_cliff, recent_picks)
    assert mult_severe == 1.25


def test_prv_multiplier_not_triggered(players_with_cliff):
    # Run share <= 0.30
    recent_picks = [{"position": "RB", "event_type": "PICK"}] * 2 + [{"position": "WR", "event_type": "PICK"}] * 8

    mult = calculate_prv_multiplier("RB", players_with_cliff, recent_picks)
    assert mult == 1.00
