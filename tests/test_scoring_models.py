"""Unit tests for advanced scoring model multipliers in engine/scoring_models.py."""

from __future__ import annotations

from engine.scoring_models import (
    apply_playoff_schedule_modifier,
    apply_scheme_and_line_scalars,
    apply_stacking_multiplier,
    blend_vegas_props,
    calculate_fcvs_raw,
)


def test_stacking_multiplier() -> None:
    user_roster = [
        {"player_id": "qb1", "position": "QB", "team": "KC"},
    ]

    # Matching primary WR
    wr1 = {"position": "WR", "team": "KC", "depth_role": "WR1", "is_primary_target": True}
    assert apply_stacking_multiplier(wr1, user_roster) == 1.07

    # Matching secondary WR
    wr2 = {"position": "WR", "team": "KC", "depth_role": "WR2"}
    assert apply_stacking_multiplier(wr2, user_roster) == 1.04

    # Non-matching team WR
    wr_other = {"position": "WR", "team": "BUF", "depth_role": "WR1"}
    assert apply_stacking_multiplier(wr_other, user_roster) == 1.0

    # Non WR/TE position
    rb = {"position": "RB", "team": "KC", "depth_role": "RB1"}
    assert apply_stacking_multiplier(rb, user_roster) == 1.0


def test_blend_vegas_props() -> None:
    player_with_vegas = {
        "projection_median": 200.0,
        "vegas_projected_pts": 220.0,
    }
    # Formula: (0.65 * 200) + (0.35 * 220) = 130 + 77 = 207.0
    assert blend_vegas_props(player_with_vegas) == 207.0

    player_no_vegas = {
        "projection_median": 200.0,
        "vegas_projected_pts": None,
    }
    assert blend_vegas_props(player_no_vegas) == 200.0


def test_scheme_and_line_scalars() -> None:
    # Top 5 O-Line RB (PHI)
    rb_top_line = {"position": "RB", "team": "PHI"}
    assert apply_scheme_and_line_scalars(rb_top_line) == 1.05

    # Bottom 5 O-Line RB (CAR)
    rb_bottom_line = {"position": "RB", "team": "CAR"}
    assert apply_scheme_and_line_scalars(rb_bottom_line) == 0.95

    # Positive PROE WR (KC)
    wr_pos_proe = {"position": "WR", "team": "KC"}
    assert apply_scheme_and_line_scalars(wr_pos_proe) == 1.04

    # Negative PROE WR (CAR)
    wr_neg_proe = {"position": "WR", "team": "CAR"}
    assert apply_scheme_and_line_scalars(wr_neg_proe) == 0.96


def test_calculate_fcvs_raw_log_normal() -> None:
    player_rookie = {
        "position": "WR",
        "projection_median": 100.0,
        "is_rookie": True,
    }

    fcvs_early = calculate_fcvs_raw(player_rookie, round_no=3)
    fcvs_late = calculate_fcvs_raw(player_rookie, round_no=10)

    # In late rounds (10+), ceiling gets log-normal expansion and ceiling weight is 90%
    assert fcvs_late > fcvs_early


def test_playoff_schedule_modifier() -> None:
    favorable_player = {
        "position": "WR",
        "playoff_dome_games": 2,
    }

    # Round < 7 should return 1.0
    assert apply_playoff_schedule_modifier(favorable_player, round_no=5) == 1.0

    # Round >= 7 with favorable conditions returns 1.03
    assert apply_playoff_schedule_modifier(favorable_player, round_no=8) == 1.03

    unfavorable_player = {
        "position": "WR",
        "playoff_dome_games": 0,
    }
    assert apply_playoff_schedule_modifier(unfavorable_player, round_no=8) == 1.0
