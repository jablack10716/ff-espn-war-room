"""Unit tests for pre-draft printable cheat sheet generator."""

import pytest
from engine.cheat_sheet import generate_csv_cheat_sheet, generate_printable_html_cheat_sheet


@pytest.fixture
def sample_cheat_sheet_players():
    return [
        {
            "player_id": "p1",
            "full_name": "Patrick Mahomes",
            "position": "QB",
            "team": "KC",
            "tier": 1,
            "bye_week": 6,
            "adp": 15.0,
            "projection_median": 340.0,
            "projection_floor": 280.0,
            "projection_ceiling": 390.0,
            "is_available": True,
        },
        {
            "player_id": "p2",
            "full_name": "Christian McCaffrey",
            "position": "RB",
            "team": "SF",
            "tier": 1,
            "bye_week": 9,
            "adp": 1.0,
            "projection_median": 310.0,
            "projection_floor": 260.0,
            "projection_ceiling": 360.0,
            "is_available": True,
        },
    ]


def test_generate_csv_cheat_sheet(sample_cheat_sheet_players):
    csv_out = generate_csv_cheat_sheet(sample_cheat_sheet_players)
    assert "Rank/Tier,Position,Full Name" in csv_out
    assert "Patrick Mahomes" in csv_out
    assert "Christian McCaffrey" in csv_out


def test_generate_printable_html_cheat_sheet(sample_cheat_sheet_players):
    html_out = generate_printable_html_cheat_sheet(sample_cheat_sheet_players, "Test League Backup")
    assert "<!DOCTYPE html>" in html_out
    assert "Test League Backup" in html_out
    assert "Patrick Mahomes" in html_out
    assert "Christian McCaffrey" in html_out
    assert "window.print()" in html_out


def test_generate_ranked_cheat_sheets(sample_cheat_sheet_players):
    from engine.ada_math import AdaQuantEngine
    from engine.cheat_sheet import generate_ranked_csv_cheat_sheet, generate_ranked_html_cheat_sheet

    engine = AdaQuantEngine()
    rankings = engine.compute_rankings(sample_cheat_sheet_players, [])

    csv_ranked = generate_ranked_csv_cheat_sheet(rankings)
    html_ranked = generate_ranked_html_cheat_sheet(rankings, "Ada Master Ranking Test")

    assert "Overall Rank,Player Name" in csv_ranked
    assert "Composite Score" in csv_ranked
    assert "<!DOCTYPE html>" in html_ranked
    assert "Ada Master Ranking Test" in html_ranked
    assert "Composite" in html_ranked
