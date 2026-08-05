"""Unit tests for Pre-Draft Keeper Manager calculation and event recording."""

import pytest
from ui.components.keeper_manager import calculate_keeper_pick_no


def test_calculate_keeper_pick_no_standard_snake():
    # 12 teams, standard snake draft
    # Round 1: normal order (1 -> 12)
    assert calculate_keeper_pick_no(round_no=1, team_slot=1, num_teams=12, is_3rr=False) == 1
    assert calculate_keeper_pick_no(round_no=1, team_slot=12, num_teams=12, is_3rr=False) == 12

    # Round 2: reverse order (12 -> 1)
    assert calculate_keeper_pick_no(round_no=2, team_slot=12, num_teams=12, is_3rr=False) == 13
    assert calculate_keeper_pick_no(round_no=2, team_slot=1, num_teams=12, is_3rr=False) == 24

    # Round 3: normal order (1 -> 12)
    assert calculate_keeper_pick_no(round_no=3, team_slot=1, num_teams=12, is_3rr=False) == 25
    assert calculate_keeper_pick_no(round_no=3, team_slot=2, num_teams=12, is_3rr=False) == 26


def test_calculate_keeper_pick_no_3rr():
    # 12 teams, 3rd Round Reversal (3RR)
    # Round 1: normal order (1 -> 12)
    assert calculate_keeper_pick_no(round_no=1, team_slot=1, num_teams=12, is_3rr=True) == 1
    assert calculate_keeper_pick_no(round_no=1, team_slot=12, num_teams=12, is_3rr=True) == 12

    # Round 2: reverse order (12 -> 1)
    assert calculate_keeper_pick_no(round_no=2, team_slot=12, num_teams=12, is_3rr=True) == 13
    assert calculate_keeper_pick_no(round_no=2, team_slot=1, num_teams=12, is_3rr=True) == 24

    # Round 3: reverse order (12 -> 1) due to 3RR
    assert calculate_keeper_pick_no(round_no=3, team_slot=12, num_teams=12, is_3rr=True) == 25
    assert calculate_keeper_pick_no(round_no=3, team_slot=1, num_teams=12, is_3rr=True) == 36


def test_keeper_record_in_service():
    from services.draft_state_service import DraftStateService

    service = DraftStateService(use_supabase=False)
    service.set_local_players(
        "test_keeper_draft",
        [{"player_id": "espn_101", "full_name": "Ja'Marr Chase", "position": "WR", "is_available": True}],
    )

    event = service.record_pick(
        draft_id="test_keeper_draft",
        pick_no=13,
        round_no=2,
        team_slot=12,
        player_id="espn_101",
        player_name="Ja'Marr Chase",
        position="WR",
        team_name="Eskimo Brothers",
        picked_by_user=True,
        source="keeper",
        notes="Pre-draft keeper",
    )

    assert event["source"] == "keeper"
    assert event["notes"] == "Pre-draft keeper"
    assert event["player_name"] == "Ja'Marr Chase"

    # Verify player is now unavailable
    available = service.get_available_players("test_keeper_draft")
    assert not any(p["player_id"] == "espn_101" for p in available)
