"""Unit tests for Handcuff Leverage Index (HLI) logic."""

import pytest
from engine.scoring_models import calculate_hli_raw


def test_hli_user_rb1_backup():
    player = {
        "player_id": "p_rb2",
        "position": "RB",
        "team": "SF",
        "depth_role": "RB2",
        "handcuff_for_player_id": "p_rb1",
        "projection_median": 100.0,
    }

    user_roster = [
        {"player_id": "p_rb1", "position": "RB", "team": "SF", "depth_role": "RB1"}
    ]

    all_rosters = {1: user_roster, 2: []}

    hli_raw = calculate_hli_raw(player, user_roster, all_rosters, user_team_slot=1)
    # 1.5x multiplier -> 100 * 1.5 = 150.0
    assert hli_raw == 150.0


def test_hli_opponent_unhandcuffed_rb1_backup():
    player = {
        "player_id": "p_opp_backup",
        "position": "RB",
        "team": "KC",
        "depth_role": "RB2",
        "handcuff_for_player_id": "p_opp_rb1",
        "projection_median": 80.0,
    }

    user_roster = []

    opp_roster = [
        {"player_id": "p_opp_rb1", "position": "RB", "team": "KC", "depth_role": "RB1"}
    ]

    all_rosters = {1: user_roster, 2: opp_roster}

    hli_raw = calculate_hli_raw(player, user_roster, all_rosters, user_team_slot=1)
    # 1.3x multiplier -> 80 * 1.3 = 104.0
    assert hli_raw == 104.0


def test_hli_low_tier_backup():
    player = {
        "player_id": "p_low_backup",
        "position": "RB",
        "team": "GB",
        "depth_role": "RB4",
        "projection_median": 30.0,
    }

    hli_raw = calculate_hli_raw(player, [], {}, user_team_slot=1)
    # 0.5x multiplier -> 30 * 0.5 = 15.0
    assert hli_raw == 15.0


def test_hli_non_rb():
    player = {
        "player_id": "p_wr",
        "position": "WR",
        "projection_median": 200.0,
    }

    hli_raw = calculate_hli_raw(player, [], {}, user_team_slot=1)
    assert hli_raw == 0.0


def test_handcuff_mapping_application():
    from data.espn_ingest import apply_handcuff_mappings

    rows = [
        {"player_id": "espn_cmc", "normalized_name": "christian mccaffrey", "position": "RB"},
        {"player_id": "espn_mason", "normalized_name": "jordan mason", "position": "RB"},
    ]

    updated = apply_handcuff_mappings(rows)
    mason = next(r for r in updated if r["normalized_name"] == "jordan mason")
    assert mason["handcuff_for_player_id"] == "espn_cmc"


def test_non_rb_hli_weight_redistribution():
    from engine.ada_math import AdaQuantEngine

    engine = AdaQuantEngine()
    players = [
        {"player_id": "qb1", "position": "QB", "projection_median": 300.0, "is_available": True},
        {"player_id": "rb1", "position": "RB", "projection_median": 250.0, "is_available": True},
    ]

    rankings = engine.compute_rankings(players, [])
    qb_item = next(r for r in rankings if r["position"] == "QB")
    rb_item = next(r for r in rankings if r["position"] == "RB")

    # QB breakdown should have hli_raw 0.0 and valid composite_score
    assert qb_item["breakdown"]["hli_raw"] == 0.0
    assert qb_item["composite_score"] is not None
    assert rb_item["composite_score"] is not None
