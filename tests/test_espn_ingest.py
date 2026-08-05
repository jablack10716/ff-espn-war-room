"""Unit tests for ESPN Ingest projection variance."""

import pytest
from data.espn_ingest import projection_triplet


def test_position_variance_spreads():
    mock_player = {"projection_median": 200.0}

    qb_floor, qb_med, qb_ceil = projection_triplet(mock_player, position="QB")
    rb_floor, rb_med, rb_ceil = projection_triplet(mock_player, position="RB")
    te_floor, te_med, te_ceil = projection_triplet(mock_player, position="TE")

    assert qb_med == 200.0
    assert rb_med == 200.0
    assert te_med == 200.0

    # QB variance is tightest (0.88 - 1.12) -> spread = 48.0
    # RB variance is wider (0.75 - 1.30) -> spread = 110.0
    # TE variance is widest (0.72 - 1.35) -> spread = 126.0
    qb_spread = qb_ceil - qb_floor
    rb_spread = rb_ceil - rb_floor
    te_spread = te_ceil - te_floor

    assert te_spread > rb_spread > qb_spread
    assert qb_floor == 176.0
    assert qb_ceil == 224.0
    assert te_floor == 144.0
    assert te_ceil == 270.0


def test_extract_teams_pick_order():
    from data.espn_ingest import extract_teams

    class DummyTeam:
        def __init__(self, team_id: int, team_name: str):
            self.team_id = team_id
            self.team_name = team_name
            self.owner = "Owner"
            self.standing = 1

    class DummyLeague:
        def __init__(self):
            self.teams = [
                DummyTeam(1, "Alpha"),
                DummyTeam(2, "Beta"),
                DummyTeam(3, "Gamma"),
            ]

    league = DummyLeague()
    # Pick order places team 3 first, team 1 second, team 2 third
    pick_order = [3, 1, 2]
    extracted = extract_teams(league, pick_order=pick_order)

    assert len(extracted) == 3
    assert extracted[0]["team_id"] == 3
    assert extracted[0]["team_slot"] == 1
    assert extracted[1]["team_id"] == 1
    assert extracted[1]["team_slot"] == 2
    assert extracted[2]["team_id"] == 2
    assert extracted[2]["team_slot"] == 3

