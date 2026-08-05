"""Unit tests for bye week conflicts and injury status tags."""

import pytest
from engine.ada_math import AdaQuantEngine


@pytest.fixture
def sample_players_with_injury_and_bye():
    return [
        {
            "player_id": "p1",
            "full_name": "Christian McCaffrey",
            "position": "RB",
            "team": "SF",
            "bye_week": 9,
            "injury_status": "QUESTIONABLE",
            "projection_median": 300.0,
            "is_available": True,
            "adp": 1.0,
            "tier": 1,
        },
        {
            "player_id": "p2",
            "full_name": "CeeDee Lamb",
            "position": "WR",
            "team": "DAL",
            "bye_week": 7,
            "injury_status": "ACTIVE",
            "projection_median": 290.0,
            "is_available": True,
            "adp": 2.0,
            "tier": 1,
        },
    ]


def test_bye_and_injury_pass_through_rankings(sample_players_with_injury_and_bye):
    engine = AdaQuantEngine()
    rankings = engine.compute_rankings(
        available_players=sample_players_with_injury_and_bye,
        draft_log=[],
        user_team_slot=1,
    )

    assert len(rankings) == 2
    cmc = next(r for r in rankings if r["player_name"] == "Christian McCaffrey")
    lamb = next(r for r in rankings if r["player_name"] == "CeeDee Lamb")

    assert cmc["bye_week"] == 9
    assert cmc["injury_status"] == "QUESTIONABLE"
    assert lamb["bye_week"] == 7
    assert lamb["injury_status"] == "ACTIVE"
