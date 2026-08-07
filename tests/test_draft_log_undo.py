"""Integration and unit tests for DraftStateService pick logging and undo logic."""

import pytest
from services.draft_state_service import DraftStateService


@pytest.fixture
def draft_service():
    # Use local memory mode for fast unit test execution
    service = DraftStateService(use_supabase=False)
    sample_players = [
        {"player_id": "p1", "full_name": "Patrick Mahomes", "position": "QB", "is_available": True},
        {"player_id": "p2", "full_name": "Christian McCaffrey", "position": "RB", "is_available": True},
        {"player_id": "p3", "full_name": "CeeDee Lamb", "position": "WR", "is_available": True},
    ]
    service.set_local_players("test_draft", sample_players)
    return service


def test_record_pick_updates_availability(draft_service):
    draft_id = "test_draft"

    # Initial state: 3 available players
    available = draft_service.get_available_players(draft_id)
    assert len(available) == 3

    # Record pick for p1
    logged_event = draft_service.record_pick(
        draft_id=draft_id,
        pick_no=1,
        round_no=1,
        team_slot=1,
        player_id="p1",
        player_name="Patrick Mahomes",
        position="QB",
        picked_by_user=True,
    )

    assert logged_event["event_type"] == "PICK"
    assert logged_event["player_id"] == "p1"

    # Post-pick state: 2 available players
    available_after = draft_service.get_available_players(draft_id)
    assert len(available_after) == 2
    assert all(p["player_id"] != "p1" for p in available_after)

    log = draft_service.get_draft_log(draft_id)
    assert len(log) == 1
    assert log[0]["pick_no"] == 1


def test_atomic_undo_restores_availability(draft_service):
    draft_id = "test_draft"

    # Record pick for p2
    draft_service.record_pick(
        draft_id=draft_id,
        pick_no=1,
        round_no=1,
        team_slot=1,
        player_id="p2",
        player_name="Christian McCaffrey",
        position="RB",
    )

    assert len(draft_service.get_available_players(draft_id)) == 2

    # Execute atomic undo
    undone = draft_service.undo_last_pick(draft_id)
    assert undone is not None
    assert undone["player_id"] == "p2"

    # Post-undo state: p2 is restored, available players == 3
    available_after_undo = draft_service.get_available_players(draft_id)
    assert len(available_after_undo) == 3
    assert any(p["player_id"] == "p2" for p in available_after_undo)

    # Log is empty
    log_after_undo = draft_service.get_draft_log(draft_id)
    assert len(log_after_undo) == 0


def test_undo_on_empty_log_returns_none(draft_service):
    undone = draft_service.undo_last_pick("non_existent_draft")
    assert undone is None


def test_delete_specific_pick_vacates_slot(draft_service):
    draft_id = "test_draft"

    # Record 3 picks
    draft_service.record_pick(draft_id, 1, 1, 1, "p1", "Patrick Mahomes", "QB")
    draft_service.record_pick(draft_id, 2, 1, 2, "p2", "Christian McCaffrey", "RB")
    draft_service.record_pick(draft_id, 3, 1, 3, "p3", "CeeDee Lamb", "WR")

    assert len(draft_service.get_available_players(draft_id)) == 0

    # Delete historical pick #2 specifically (vacating McCaffrey)
    deleted = draft_service.delete_specific_pick(draft_id, 2)
    assert deleted is not None
    assert deleted["player_id"] == "p2"

    # McCaffrey is restored to available pool
    avail = draft_service.get_available_players(draft_id)
    assert len(avail) == 1
    assert avail[0]["player_id"] == "p2"

    # Log now has picks #1 and #3, but #2 is gone
    log = draft_service.get_draft_log(draft_id)
    assert len(log) == 2
    assert set(p["pick_no"] for p in log) == {1, 3}

