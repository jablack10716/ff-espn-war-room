"""Unit tests for Value Over Replacement (VOR/VORP) calculation."""

import pytest
from engine.ada_math import AdaQuantEngine
from engine.scoring_models import calculate_vor


@pytest.fixture
def sample_vor_players():
    return [
        {
            "player_id": "qb1",
            "full_name": "Patrick Mahomes",
            "position": "QB",
            "projection_median": 340.0,
            "is_available": True,
            "adp": 15.0,
            "tier": 1,
        },
        {
            "player_id": "qb13",
            "full_name": "Replacement QB",
            "position": "QB",
            "projection_median": 290.0,
            "is_available": True,
            "adp": 100.0,
            "tier": 3,
        },
        {
            "player_id": "rb1",
            "full_name": "Christian McCaffrey",
            "position": "RB",
            "projection_median": 300.0,
            "is_available": True,
            "adp": 1.0,
            "tier": 1,
        },
        {
            "player_id": "rb25",
            "full_name": "Replacement RB",
            "position": "RB",
            "projection_median": 180.0,
            "is_available": True,
            "adp": 80.0,
            "tier": 4,
        },
    ]


def test_vor_rb_higher_than_qb(sample_vor_players):
    roster_req = {"QB": 1, "RB": 1}  # replacement index is 1 * 1 = 1 (2nd player)
    qb_vor = calculate_vor(sample_vor_players[0], sample_vor_players, roster_req, num_teams=1)
    rb_vor = calculate_vor(sample_vor_players[2], sample_vor_players, roster_req, num_teams=1)

    # Mahomes (340) vs Replacement QB (290) -> VOR = +50
    # McCaffrey (300) vs Replacement RB (180) -> VOR = +120
    assert rb_vor > qb_vor
    assert qb_vor == 50.0
    assert rb_vor == 120.0


def test_vor_below_replacement(sample_vor_players):
    roster_req = {"QB": 1, "RB": 1}
    qb13_vor = calculate_vor(sample_vor_players[1], sample_vor_players, roster_req, num_teams=1)
    assert qb13_vor == 0.0  # replacement player vs baseline (itself) is 0


def test_vor_in_composite(sample_vor_players):
    engine = AdaQuantEngine()
    rankings = engine.compute_rankings(
        available_players=sample_vor_players,
        draft_log=[],
        user_team_slot=1,
        num_teams=1,
        roster_requirements={"QB": 1, "RB": 1},
    )
    assert len(rankings) == 4
    for r in rankings:
        assert "vor_raw" in r["breakdown"]
        assert "vor_norm" in r["breakdown"]
