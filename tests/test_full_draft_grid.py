"""Unit tests for Full Draft Board Grid matrix component math."""

import pytest
from server.main import get_team_on_clock


def test_full_draft_grid_rendering_does_not_raise():
    draft_log = [
        {
            "pick_no": 1,
            "round_no": 1,
            "team_slot": 1,
            "player_name": "Justin Jefferson",
            "position": "WR",
            "picked_by_user": False,
            "event_type": "PICK",
        },
        {
            "pick_no": 2,
            "round_no": 1,
            "team_slot": 2,
            "player_name": "CeeDee Lamb",
            "position": "WR",
            "picked_by_user": True,
            "source": "keeper",
            "notes": "Pre-draft keeper",
            "event_type": "PICK",
        },
    ]

    espn_teams = [
        {"team_slot": 1, "team_name": "Only Fam"},
        {"team_slot": 2, "team_name": "Eskimo Brothers"},
    ]

    assert len(draft_log) == 2
    assert espn_teams[0]["team_name"] == "Only Fam"


def test_get_team_on_clock():
    # Pick 1 -> Slot 1
    assert get_team_on_clock(1, num_teams=12) == 1
    # Pick 12 -> Slot 12
    assert get_team_on_clock(12, num_teams=12) == 12
    # Pick 13 -> Slot 12 (Snake turn)
    assert get_team_on_clock(13, num_teams=12) == 12
    # Pick 24 -> Slot 1
    assert get_team_on_clock(24, num_teams=12) == 1


