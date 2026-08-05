"""Unit tests for agent output schema validation and orchestration fallbacks."""

import pytest
from agents.war_room_agents import (
    ArthurAgent,
    MarcusAgent,
    WarRoomOrchestrator,
    WinstonAgent,
    validate_schema,
)


@pytest.fixture
def sample_ada_rankings():
    return [
        {
            "rank": 1,
            "player_id": "p_rb1",
            "player_name": "Christian McCaffrey",
            "position": "RB",
            "composite_score": 0.825,
            "projection_median": 310.0,
        },
        {
            "rank": 2,
            "player_id": "p_wr1",
            "player_name": "CeeDee Lamb",
            "position": "WR",
            "composite_score": 0.790,
            "projection_median": 290.0,
        },
        {
            "rank": 3,
            "player_id": "p_qb1",
            "player_name": "Patrick Mahomes",
            "position": "QB",
            "composite_score": 0.745,
            "projection_median": 340.0,
        },
    ]


def test_marcus_output_schema_validation():
    valid_marcus = {
        "agent": "Marcus",
        "player_id": "p_rb1",
        "upside_sentence": "McCaffrey offers elite receiving upside and a dominant 80% touch share.",
    }
    assert validate_schema(valid_marcus, "marcus_output.schema.json") is True

    invalid_marcus = {"agent": "Marcus", "player_id": "p_rb1"}
    assert validate_schema(invalid_marcus, "marcus_output.schema.json") is False


def test_winston_output_schema_validation():
    valid_winston = {
        "agent": "Winston",
        "player_id": "p_wr1",
        "need_sentence": "Selecting CeeDee Lamb satisfies an essential WR1 starting roster requirement.",
    }
    assert validate_schema(valid_winston, "winston_output.schema.json") is True

    invalid_winston = {"agent": "Winston", "player_id": "p_wr1", "need_sentence": 123}
    assert validate_schema(invalid_winston, "winston_output.schema.json") is False


def test_arthur_output_schema_validation(sample_ada_rankings):
    top_3 = [
        {
            "rank": r["rank"],
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "position": r["position"],
            "composite_score": r["composite_score"],
        }
        for r in sample_ada_rankings
    ]

    valid_arthur = {
        "agent": "Arthur",
        "reasoning_2_sentences": "Christian McCaffrey represents the highest upside pick for our team roster. Draft him to secure elite RB volume.",
        "top_3_picks": top_3,
        "fallback_used": False,
    }
    assert validate_schema(valid_arthur, "arthur_output.schema.json") is True


def test_orchestrator_should_trigger():
    orchestrator = WarRoomOrchestrator()
    assert orchestrator.should_trigger(picks_until_user_turn=1) is True
    assert orchestrator.should_trigger(picks_until_user_turn=2) is True
    assert orchestrator.should_trigger(picks_until_user_turn=3) is False


def test_orchestrator_fallback_mode(sample_ada_rankings):
    orchestrator = WarRoomOrchestrator()
    fallback = orchestrator.build_fallback_payload(sample_ada_rankings)

    assert fallback["agent"] == "Arthur"
    assert fallback["fallback_used"] is True
    assert len(fallback["top_3_picks"]) == 3
    assert fallback["top_3_picks"][0]["player_name"] == "Christian McCaffrey"

    arthur_strict = {k: v for k, v in fallback.items() if k in ("agent", "reasoning_2_sentences", "top_3_picks", "fallback_used")}
    assert validate_schema(arthur_strict, "arthur_output.schema.json") is True


def test_orchestration_execution_fallback_path(sample_ada_rankings):
    orchestrator = WarRoomOrchestrator()
    # Runs orchestration without valid OpenRouter key -> gracefully executes fallback path
    result = orchestrator.run_orchestration(
        candidate_players=sample_ada_rankings,
        user_roster=[],
        ada_rankings=sample_ada_rankings,
        timeout_seconds=1.0,
    )

    assert result["agent"] == "Arthur"
    assert "top_3_picks" in result
    assert len(result["top_3_picks"]) == 3
    assert "reasoning_2_sentences" in result


def test_position_aware_agent_fallbacks():
    marcus = MarcusAgent()
    winston = WinstonAgent()

    qb_player = {"player_id": "qb1", "full_name": "Patrick Mahomes", "position": "QB"}
    wr_player = {"player_id": "wr1", "full_name": "CeeDee Lamb", "position": "WR"}

    m_qb_eval = marcus.evaluate_player(qb_player, timeout_seconds=0.1)
    m_wr_eval = marcus.evaluate_player(wr_player, timeout_seconds=0.1)

    w_qb_eval = winston.evaluate_player(qb_player, user_roster=[], timeout_seconds=0.1)
    w_wr_eval = winston.evaluate_player(wr_player, user_roster=[], timeout_seconds=0.1)

    assert "passing talent" in m_qb_eval["upside_sentence"]
    assert "route-running" in m_wr_eval["upside_sentence"]
    assert "QB anchor" in w_qb_eval["need_sentence"]
    assert "WR starting slot" in w_wr_eval["need_sentence"]
