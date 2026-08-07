"""Unit tests for multi-source data ingestion and resolution services."""

from __future__ import annotations

import pytest
from services.sleeper_client import get_sleeper_adp_map
from services.fantasypros_client import derive_consensus_metrics, normalize_name
from services.depth_chart_service import resolve_dynamic_handcuffs
from engine.scoring_models import apply_ppr_adjustment


def test_normalize_name() -> None:
    assert normalize_name("Ja'Marr Chase") == "ja marr chase"
    assert normalize_name("Christian McCaffrey Jr.") == "christian mccaffrey jr"


def test_derive_consensus_metrics() -> None:
    fp_data = {
        "bijan robinson": {"ecr": 4.5, "analyst_tier": 1, "sd": 0.8, "best": 3, "worst": 6}
    }
    metrics = derive_consensus_metrics(
        player_name="Bijan Robinson",
        position="RB",
        espn_median=310.0,
        fp_ecr_data=fp_data,
        sleeper_adp=5.0,
        espn_adp=4.0,
    )

    assert metrics["consensus_adp"] == 4.5
    assert metrics["analyst_tier"] == 1
    assert metrics["projected_receptions"] > 0
    assert metrics["floor_p10"] < 310.0
    assert metrics["ceiling_p90"] > 310.0


def test_resolve_dynamic_handcuffs() -> None:
    players = [
        {"player_id": "espn_1", "full_name": "Breece Hall", "position": "RB", "team": "NYJ", "projection_median": 280.0},
        {"player_id": "espn_2", "full_name": "Braelon Allen", "position": "RB", "team": "NYJ", "projection_median": 110.0},
    ]
    resolved = resolve_dynamic_handcuffs(players)
    braelon = [p for p in resolved if p["full_name"] == "Braelon Allen"][0]

    assert braelon["handcuff_for_player_id"] == "espn_1"
    assert braelon["depth_role"] == "RB2"


def test_dynamic_ppr_adjustment() -> None:
    # Player with dynamic projected_receptions
    player_rec = {"position": "WR", "projected_receptions": 100.0}
    assert apply_ppr_adjustment(player_rec, "PPR") == 100.0
    assert apply_ppr_adjustment(player_rec, "HALF_PPR") == 50.0

    # Player without projected_receptions (receiving yards fallback)
    player_rec_yards = {"position": "WR", "projected_receiving_yards": 1000.0}
    # 1000 / 12.5 = 80 receptions -> 80.0 PPR, 40.0 HALF_PPR
    assert apply_ppr_adjustment(player_rec_yards, "PPR") == 80.0
    assert apply_ppr_adjustment(player_rec_yards, "HALF_PPR") == 40.0

    # Player without projected_receptions or receiving yards (median fallback)
    player_fallback = {"position": "WR", "projection_median": 200.0}
    # 200.0 * 0.25 = 50.0 PPR, 25.0 HALF_PPR
    assert apply_ppr_adjustment(player_fallback, "PPR") == 50.0
    assert apply_ppr_adjustment(player_fallback, "HALF_PPR") == 25.0
