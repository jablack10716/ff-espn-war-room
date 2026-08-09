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

    # Hybrid Baseline = (VOLS + VORP) / 2
    # Mahomes (340) vs Hybrid Baseline (315) -> VOR = +25
    # McCaffrey (300) vs Hybrid Baseline (240) -> VOR = +60
    assert rb_vor > qb_vor
    assert qb_vor == 25.0
    assert rb_vor == 60.0


def test_vor_below_replacement(sample_vor_players):
    roster_req = {"QB": 1, "RB": 1}
    qb13_vor = calculate_vor(sample_vor_players[1], sample_vor_players, roster_req, num_teams=1)
    # Replacement player (290) vs Hybrid Baseline (315) is -25.0
    assert qb13_vor == -25.0


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

    # Standard 1QB league: hybrid baseline of 12th (345) and 13th (340) QB = 342.5 -> VOR = 57.5
    standard_req = {"QB": 1}
    vor_standard = calculate_vor(qbs[0], qbs, standard_req, num_teams=12)

    # Superflex league: hybrid baseline of 24th (285) and 25th (280) QB = 282.5 -> VOR = 117.5
    sf_req = {"QB": 1, "SUPERFLEX": 1}
    vor_sf = calculate_vor(qbs[0], qbs, sf_req, num_teams=12)

    assert vor_standard == 57.5
    assert vor_sf == 117.5
    assert vor_sf > vor_standard  # Superflex dramatically increases QB value


def test_vor_drafted_counts_adjustment():
    """Verify that VOR adjusts replacement index down when QBs have already been drafted."""
    qbs = [
        {"player_id": f"qb{i}", "position": "QB", "projection_median": 400.0 - (i * 5), "is_available": True}
        for i in range(20)
    ]
    standard_req = {"QB": 1}

    # No QBs drafted yet: hybrid baseline of 12th & 13th QB (342.5, VOR = 57.5)
    vor_initial = calculate_vor(qbs[0], qbs, standard_req, num_teams=12, drafted_counts={"QB": 0})
    assert vor_initial == 57.5

    # 5 QBs already drafted: hybrid baseline of 7th & 8th QB (367.5, VOR = 32.5)
    vor_with_drafted = calculate_vor(qbs[0], qbs, standard_req, num_teams=12, drafted_counts={"QB": 5})
    assert vor_with_drafted == 32.5
    assert vor_with_drafted < vor_initial

