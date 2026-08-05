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


def test_effective_starters_superflex():
    """SUPERFLEX adds +1.0 to QB effective starters; FLEX distributes fractionally."""
    from engine.scoring_models import calculate_effective_starters

    reqs = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 1, "DST": 1}
    effective = calculate_effective_starters(reqs)

    # QB: 1 base + 1.0 from SUPERFLEX = 2.0
    assert effective["QB"] == 2.0
    # RB: 2 base + 0.45 from FLEX = 2.45
    assert abs(effective["RB"] - 2.45) < 0.001
    # WR: 2 base + 0.35 from FLEX = 2.35
    assert abs(effective["WR"] - 2.35) < 0.001
    # TE: 1 base + 0.20 from FLEX = 1.20
    assert abs(effective["TE"] - 1.20) < 0.001
    # DST: 1 base, no flex/sf contribution
    assert effective["DST"] == 1.0


def test_vor_superflex_doubles_qb_baseline():
    """In Superflex, QB replacement index should be num_teams * 2 (24th QB in 12-team)."""
    # Create 30 QBs with descending projections
    qbs = [
        {"player_id": f"qb{i}", "position": "QB", "projection_median": 400.0 - (i * 5), "is_available": True}
        for i in range(30)
    ]

    # Standard 1QB league: replacement at index 12 (13th QB, proj = 400 - 60 = 340)
    standard_req = {"QB": 1}
    vor_standard = calculate_vor(qbs[0], qbs, standard_req, num_teams=12)

    # Superflex league: replacement at index 24 (25th QB, proj = 400 - 120 = 280)
    sf_req = {"QB": 1, "SUPERFLEX": 1}
    vor_sf = calculate_vor(qbs[0], qbs, sf_req, num_teams=12)

    # QB1 projection = 400
    # Standard baseline = 400 - 60 = 340 -> VOR = 60
    # Superflex baseline = 400 - 120 = 280 -> VOR = 120
    assert vor_standard == 60.0
    assert vor_sf == 120.0
    assert vor_sf > vor_standard  # Superflex dramatically increases QB value
