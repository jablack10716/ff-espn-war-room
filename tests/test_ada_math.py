"""Unit tests for Ada quant engine math and composite ranking logic."""

import random
import pytest
from engine.ada_math import (
    AdaQuantEngine,
    calculate_opportunity_cost_raw,
    estimate_best_at_next_turn,
)
from engine.scoring_models import min_max_normalize, z_score_normalize


@pytest.fixture
def sample_available_players():
    return [
        {
            "player_id": "p_qb1",
            "full_name": "Patrick Mahomes",
            "position": "QB",
            "team": "KC",
            "tier": 1,
            "adp": 15.0,
            "projection_floor": 280.0,
            "projection_median": 340.0,
            "projection_ceiling": 390.0,
            "is_available": True,
        },
        {
            "player_id": "p_qb2",
            "full_name": "Josh Allen",
            "position": "QB",
            "team": "BUF",
            "tier": 1,
            "adp": 18.0,
            "projection_floor": 270.0,
            "projection_median": 335.0,
            "projection_ceiling": 385.0,
            "is_available": True,
        },
        {
            "player_id": "p_rb1",
            "full_name": "Christian McCaffrey",
            "position": "RB",
            "team": "SF",
            "tier": 1,
            "adp": 1.0,
            "projection_floor": 260.0,
            "projection_median": 310.0,
            "projection_ceiling": 360.0,
            "depth_role": "RB1",
            "is_available": True,
        },
        {
            "player_id": "p_rb2",
            "full_name": "Jordan Mason",
            "position": "RB",
            "team": "SF",
            "tier": 4,
            "adp": 120.0,
            "projection_floor": 40.0,
            "projection_median": 90.0,
            "projection_ceiling": 130.0,
            "depth_role": "RB2",
            "handcuff_for_player_id": "p_rb1",
            "is_available": True,
        },
        {
            "player_id": "p_wr1",
            "full_name": "CeeDee Lamb",
            "position": "WR",
            "team": "DAL",
            "tier": 1,
            "adp": 2.0,
            "projection_floor": 240.0,
            "projection_median": 290.0,
            "projection_ceiling": 330.0,
            "is_available": True,
        },
    ]


def test_normalization_helpers():
    # Min-max test
    values = [10.0, 20.0, 30.0]
    norm = min_max_normalize(values)
    assert norm == [0.0, 0.5, 1.0]

    # Min-max constant values
    assert min_max_normalize([5.0, 5.0]) == [0.5, 0.5]

    # Z-score test
    z_norm = z_score_normalize([10.0, 20.0, 30.0])
    assert abs(z_norm[0] + 1.2247) < 0.01
    assert abs(z_norm[1]) < 0.01
    assert abs(z_norm[2] - 1.2247) < 0.01


def test_estimate_best_at_next_turn(sample_available_players):
    random.seed(42)
    # If 0 picks until turn, best remaining at QB is QB1 (340.0)
    best_now = estimate_best_at_next_turn("QB", sample_available_players, 0)
    assert best_now == 340.0

    # If 2 picks until turn, probabilistic ADP survival expected value incorporates top 3 QBs
    best_next = estimate_best_at_next_turn("QB", sample_available_players, 2, current_pick=1)
    assert 330.0 <= best_next <= 340.0


def test_opportunity_cost_raw(sample_available_players):
    qb1 = sample_available_players[0]
    oc = calculate_opportunity_cost_raw(qb1, sample_available_players, picks_until_next_turn=0)
    assert oc == 0.0


def test_ada_quant_engine_rankings(sample_available_players):
    engine = AdaQuantEngine()
    rankings = engine.compute_rankings(
        available_players=sample_available_players,
        draft_log=[],
        user_team_slot=1,
        current_round=1,
        current_pick=1,
    )

    assert len(rankings) == len(sample_available_players)
    assert rankings[0]["rank"] == 1
    assert "composite_score" in rankings[0]
    assert "breakdown" in rankings[0]

    # Confirm deterministic output consistency across repeated runs
    rankings_second_run = engine.compute_rankings(
        available_players=sample_available_players,
        draft_log=[],
        user_team_slot=1,
        current_round=1,
        current_pick=1,
    )
    assert rankings == rankings_second_run


def test_empty_candidates():
    engine = AdaQuantEngine()
    assert engine.compute_rankings([], []) == []


def test_roster_fit_gradient():
    from engine.scoring_models import calculate_roster_fit

    rb_player = {"position": "RB"}
    k_player = {"position": "K"}

    # Early Kicker suppressed
    assert calculate_roster_fit(k_player, user_roster=[], round_no=3) == 0.30

    # 2 RB slots needed -> 1.50
    assert calculate_roster_fit(rb_player, user_roster=[], round_no=1, roster_requirements={"RB": 2}) == 1.50

    # 1 RB slot needed, 10 remaining -> 1.40
    avail_10_rbs = [{"position": "RB", "is_available": True} for _ in range(10)]
    assert calculate_roster_fit(rb_player, user_roster=[{"position": "RB"}], round_no=2, roster_requirements={"RB": 2}, available_players=avail_10_rbs) == 1.40

