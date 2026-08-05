"""Unit tests for PPR scoring format adjustment."""

import pytest
from engine.scoring_models import apply_ppr_adjustment


def test_ppr_boosts_wr_and_te_over_standard():
    wr = {"position": "WR", "projection_median": 200.0}
    te = {"position": "TE", "projection_median": 150.0}
    rb = {"position": "RB", "projection_median": 200.0}
    qb = {"position": "QB", "projection_median": 300.0}

    # Standard -> 0.0
    assert apply_ppr_adjustment(wr, "STANDARD") == 0.0
    assert apply_ppr_adjustment(rb, "STANDARD") == 0.0

    # Full PPR -> WR +85, TE +55, RB +40
    assert apply_ppr_adjustment(wr, "PPR") == 85.0
    assert apply_ppr_adjustment(te, "PPR") == 55.0
    assert apply_ppr_adjustment(rb, "PPR") == 40.0
    assert apply_ppr_adjustment(qb, "PPR") == 0.0

    # Half PPR -> WR +42.5, TE +27.5, RB +20
    assert apply_ppr_adjustment(wr, "HALF_PPR") == 42.5
    assert apply_ppr_adjustment(te, "HALF_PPR") == 27.5
    assert apply_ppr_adjustment(rb, "HALF_PPR") == 20.0
