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


def test_keeper_unassigned_first_pick_calculation():
    """Verify pre-draft keeper starting pick #1 and historical pick deletion leading-edge stability."""
    draft_log = [
        {"pick_no": 6, "event_type": "PICK", "player_name": "Josh Allen", "source": "keeper"},
        {"pick_no": 19, "event_type": "PICK", "player_name": "A.J. Brown", "source": "keeper"},
    ]

    taken_pick_nos = {
        int(e.get("pick_no"))
        for e in draft_log
        if str(e.get("event_type", "PICK")).upper() == "PICK" and e.get("pick_no") is not None
    }
    live_pick_nos = {
        int(e.get("pick_no"))
        for e in draft_log
        if str(e.get("event_type", "PICK")).upper() == "PICK"
        and e.get("pick_no") is not None
        and str(e.get("source", "")).lower() != "keeper"
    }

    if not live_pick_nos:
        current_pick = 1
        while current_pick in taken_pick_nos:
            current_pick += 1
    else:
        current_pick = max(live_pick_nos) + 1
        while current_pick in taken_pick_nos:
            current_pick += 1

    # Before live picks, starts on Pick #1 (NOT #20)
    assert current_pick == 1

    # Simulate live picks #1..#49 (with keepers at #6 and #19)
    for p in range(1, 50):
        if p not in (6, 19):
            draft_log.append({"pick_no": p, "event_type": "PICK", "player_name": f"Player {p}", "source": "manual"})

    # Recalculate leading edge
    taken_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("event_type", "PICK")).upper() == "PICK"}
    live_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("source", "")).lower() != "keeper"}

    current_pick = max(live_pick_nos) + 1
    while current_pick in taken_pick_nos:
        current_pick += 1

    # Live draft clock should be at Pick #50
    assert current_pick == 50

    # User deletes historical Pick #25
    draft_log = [e for e in draft_log if e.get("pick_no") != 25]

    taken_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("event_type", "PICK")).upper() == "PICK"}
    live_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("source", "")).lower() != "keeper"}

    current_pick = max(live_pick_nos) + 1
    while current_pick in taken_pick_nos:
        current_pick += 1

    # Deleting Pick #25 MUST NOT pull back the live draft clock; it STAYS at Pick #50
    assert current_pick == 50
