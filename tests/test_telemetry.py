"""Unit tests for draft decision telemetry logging in services/draft_state_service.py."""

from __future__ import annotations

from services.draft_state_service import DraftStateService


def test_log_user_pick_local() -> None:
    service = DraftStateService(use_supabase=False)

    telemetry_data = {
        "ada_rank_recommended": 1,
        "ada_composite_score": 8.75,
        "projected_points_median": 250.0,
        "projected_floor": 180.0,
        "projected_ceiling": 320.0,
        "dynamic_vorp": 45.2,
        "opportunity_cost_delta": 12.5,
        "fcvs_weight_applied": "10% floor / 90% ceiling",
        "hli_multiplier_applied": 1.3,
        "prv_alert_active": True,
        "consensus_ecr_rank": 15,
        "adp_at_draft_time": 18.5,
        "adp_survival_prob_to_next_turn": 0.12,
        "qbs_drafted_count": 2,
        "rbs_drafted_count": 5,
        "wrs_drafted_count": 8,
    }

    result = service.log_user_pick(
        draft_id="test_draft_123",
        pick_number=15,
        round_no=2,
        selected_player_id="player_99",
        selected_player_name="Puka Nacua",
        telemetry_data=telemetry_data,
        marcus_pitch="Marcus says draft Nacua for upside.",
        winston_pitch="Winston agrees with WR value.",
        arthur_gm_reasoning="GM approves selection.",
    )

    assert result["draft_id"] == "test_draft_123"
    assert result["pick_number"] == 15
    assert result["selected_player_id"] == "player_99"
    assert result["ada_composite_score"] == 8.75
    assert result["marcus_pitch"] == "Marcus says draft Nacua for upside."
    assert len(service._local_telemetry) == 1
    assert service._local_telemetry[0]["selected_player_name"] == "Puka Nacua"


def test_record_pick_triggers_telemetry() -> None:
    service = DraftStateService(use_supabase=False)

    pick_event = service.record_pick(
        draft_id="test_draft_456",
        pick_no=1,
        round_no=1,
        team_slot=1,
        player_id="player_01",
        player_name="Christian McCaffrey",
        position="RB",
        picked_by_user=True,
        marcus_pitch="Smash pick CMC.",
    )

    assert pick_event["player_name"] == "Christian McCaffrey"
    assert len(service._local_telemetry) == 1
    assert service._local_telemetry[0]["selected_player_name"] == "Christian McCaffrey"
    assert service._local_telemetry[0]["marcus_pitch"] == "Smash pick CMC."
