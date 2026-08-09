"""Unit tests for Phase 1-3 multi-source data expansions (Underdog, Vegas, High-Stakes Projections)."""

from __future__ import annotations

import pytest

import config.settings as settings
from services.underdog_client import get_underdog_adp_map, normalize_name
from services.vegas_odds_client import calculate_vegas_implied_points, get_vegas_props_map
from services.premium_analytics_client import get_advanced_metrics_map, get_high_stakes_projections_map
from engine.scoring_models import blend_vegas_props, calculate_blended_projection, calculate_fcvs_raw
from engine.ada_math import estimate_best_at_next_turn


def test_underdog_client_toggles(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test disabled toggle returns empty dict
    monkeypatch.setattr(settings, "ENABLE_HIGH_STAKES_ADP", False)
    assert get_underdog_adp_map() == {}


def test_vegas_odds_implied_points() -> None:
    props = {
        "pass_yds": 4000.0,
        "pass_tds": 28.0,
        "pass_ints": 10.0,
        "rush_yds": 200.0,
        "rush_tds": 2.0,
    }
    # (4000*0.04) + (28*4) - (10*2) + (200*0.1) + (2*6) = 160 + 112 - 20 + 20 + 12 = 284.0
    pts = calculate_vegas_implied_points(props, "QB", "HALF_PPR")
    assert pts == 284.0


def test_vegas_odds_client_toggles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_VEGAS_PROPS", False)
    assert get_vegas_props_map() == {}


def test_premium_analytics_client_toggles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_HIGH_STAKES_PROJECTIONS", False)
    monkeypatch.setattr(settings, "ENABLE_ADVANCED_METRICS", False)
    assert get_high_stakes_projections_map() == {}
    assert get_advanced_metrics_map() == {}


def test_calculate_blended_projection() -> None:
    # Test 3-source blend: 40% high_stakes (300) + 35% vegas (280) + 25% consensus (250)
    # (300*0.40) + (280*0.35) + (250*0.25) = 120 + 98 + 62.5 = 280.5
    blended = calculate_blended_projection(
        cons_proj=250.0,
        vegas_proj=280.0,
        high_stakes_proj=300.0,
    )
    assert blended == 280.5

    # Fallback test: missing high_stakes, should re-normalize weights between vegas and consensus
    blended_fallback = calculate_blended_projection(
        cons_proj=200.0,
        vegas_proj=250.0,
        high_stakes_proj=None,
    )
    # Fallback test: missing high_stakes uses 65% consensus / 35% vegas (0.65 * 200 + 0.35 * 250 = 217.5)
    assert blended_fallback == 217.5


def test_blend_vegas_props_disabled_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENABLE_VEGAS_PROPS", False)
    monkeypatch.setattr(settings, "ENABLE_HIGH_STAKES_PROJECTIONS", False)

    player = {
        "projection_median": 200.0,
        "vegas_projected_pts": 250.0,
        "high_stakes_proj": 260.0,
    }
    assert blend_vegas_props(player) == 200.0


def test_fcvs_advanced_opportunity_ceiling_boost() -> None:
    player_standard = {
        "position": "WR",
        "projection_median": 150.0,
    }
    fcvs_standard = calculate_fcvs_raw(player_standard, round_no=7)

    player_high_air_yards = {
        "position": "WR",
        "projection_median": 150.0,
        "air_yards_share": 0.30,
    }
    fcvs_boosted = calculate_fcvs_raw(player_high_air_yards, round_no=7)

    assert fcvs_boosted > fcvs_standard


def test_estimate_best_at_next_turn_underdog_adp() -> None:
    available = [
        {"position": "WR", "projection_median": 200.0, "adp": 45.0, "underdog_adp": 25.0},
        {"position": "WR", "projection_median": 180.0, "adp": 50.0, "underdog_adp": 30.0},
    ]

    # Target pick = current pick 1 + 20 picks until next turn = pick 21
    # Underdog ADP of 25 is much closer to pick 21 than standard ADP 45, so survival probability will be lower
    best_proj = estimate_best_at_next_turn("WR", available, picks_until_next_turn=20, current_pick=1)
    assert best_proj > 0.0
