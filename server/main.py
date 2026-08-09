import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.ada_math import AdaQuantEngine
from agents.war_room_agents import WarRoomOrchestrator
from services.draft_state_service import DraftStateService
from server.schemas import ConfigUpdateRequest, KeeperRequest, KeeperUndoRequest, PickRequest, ResetRequest, StateQuery, SyncESPNRequest, UndoRequest

load_dotenv()

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("server.main")

app = FastAPI(title="The Best Damn Fantasy Football Drafting App Engine", version="2.0.0")

# Enable CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

draft_service = DraftStateService(use_supabase=True)
ada_engine = AdaQuantEngine()
orchestrator = WarRoomOrchestrator()

# Global memory state
_cached_agent_advisory: Dict[str, Any] = {}
_cached_seed_players: Optional[List[Dict[str, Any]]] = None
_espn_teams: List[Dict[str, Any]] = []
_user_team_slot: int = int(os.getenv("USER_TEAM_SLOT", "1"))
_num_teams: int = 12
_scoring_format: str = "HALF_PPR"
_roster_requirements: Dict[str, int] = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 1, "DST": 1}
_is_3rr: bool = False
_draft_started: bool = False


class ConnectionManager:
    """Manages active WebSockets connections and state broadcasts."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        LOGGER.info("WebSocket client connected (%d total)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            LOGGER.info("WebSocket client disconnected (%d total remaining)", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.active_connections:
            return
        dead_connections: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as exc:
                LOGGER.warning("Failed to send WS message, scheduling disconnect: %s", exc)
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()


def load_seed_players() -> List[Dict[str, Any]]:
    """Load player dataset from seed JSON file if Supabase / cache is empty."""
    global _cached_seed_players
    if _cached_seed_players is not None:
        return _cached_seed_players

    seed_path = Path("data/seed/available_players_seed_192204_2026.json")
    if not seed_path.exists():
        LOGGER.warning("Seed path %s does not exist", seed_path)
        return []

    try:
        with seed_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            _cached_seed_players = data
            return data
    except Exception as exc:
        LOGGER.error("Failed to load seed players: %s", exc)
        return []


def get_team_on_clock(pick_no: int, num_teams: int = 12) -> int:
    """Determine team slot (1-12) on clock for given pick number in snake draft format."""
    round_no = ((pick_no - 1) // num_teams) + 1
    pos_in_round = (pick_no - 1) % num_teams
    if round_no % 2 == 1:
        return pos_in_round + 1
    else:
        return num_teams - pos_in_round


def calculate_picks_until_user_turn(current_pick: int, user_team_slot: int = 1, num_teams: int = 12, total_picks: int = 204) -> int:
    """Calculate exact number of picks remaining until user's next turn on clock."""
    for p in range(current_pick, total_picks + 1):
        if get_team_on_clock(p, num_teams=num_teams) == user_team_slot:
            return p - current_pick
    return 999


def calculate_keeper_pick_no(round_no: int, team_slot: int, num_teams: int = 12, is_3rr: bool = False) -> int:
    """Calculate overall pick_no from round_no and team_slot in snake / 3RR draft."""
    if is_3rr:
        if round_no == 1:
            is_reverse = False
        elif round_no in (2, 3):
            is_reverse = True
        else:
            is_reverse = (round_no % 2 == 1)
    else:
        is_reverse = (round_no % 2 == 0)

    if is_reverse:
        pick_in_round = num_teams - team_slot + 1
    else:
        pick_in_round = team_slot

    return (round_no - 1) * num_teams + pick_in_round


def build_full_draft_state(draft_id: str = "default_draft_2026", user_team_slot: Optional[int] = None) -> Dict[str, Any]:
    """Reconcile database/cache state, calculate Ada math engine rankings, and assemble full draft payload."""
    global _cached_agent_advisory, _user_team_slot, _num_teams, _espn_teams, _scoring_format, _roster_requirements, _is_3rr, _draft_started

    active_user_slot = user_team_slot if user_team_slot is not None else _user_team_slot

    available_players = draft_service.get_available_players(draft_id)
    if not available_players:
        seed_players = load_seed_players()
        if seed_players:
            draft_service.set_local_players(draft_id, seed_players)
            available_players = draft_service.get_available_players(draft_id)

    draft_log = draft_service.get_draft_log(draft_id)

    taken_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("event_type", "")).upper() == "PICK"}
    live_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("source", "")).lower() != "keeper" and "keeper" not in str(e.get("notes", "")).lower()}

    # Clock calculation matching phase 3/4 guidelines
    if not _draft_started or not live_pick_nos:
        current_pick = 1
        while current_pick in taken_pick_nos:
            current_pick += 1
    else:
        current_pick = max(live_pick_nos) + 1
        while current_pick in taken_pick_nos:
            current_pick += 1

    num_teams = _num_teams
    current_round = ((current_pick - 1) // num_teams) + 1
    team_on_clock = get_team_on_clock(current_pick, num_teams=num_teams)
    picks_until_user_turn = calculate_picks_until_user_turn(current_pick, user_team_slot=active_user_slot, num_teams=num_teams)

    # Compute Ada quant rankings
    ada_rankings = ada_engine.compute_rankings(
        available_players=available_players,
        draft_log=draft_log,
        user_team_slot=active_user_slot,
        current_round=current_round,
        current_pick=current_pick,
        picks_until_next_turn=picks_until_user_turn,
        roster_requirements=_roster_requirements,
        scoring_format=_scoring_format,
        num_teams=num_teams,
    )

    # Build roster for active_user_slot
    user_roster: List[Dict[str, Any]] = []
    roster_by_position: Dict[str, List[Dict[str, Any]]] = {
        "QB": [], "RB": [], "WR": [], "TE": [], "FLEX": [], "SUPERFLEX": [], "K": [], "DST": [], "BENCH": []
    }

    for pick_event in draft_log:
        if str(pick_event.get("event_type", "PICK")).upper() == "PICK":
            slot = int(pick_event.get("team_slot", 1))
            if slot == active_user_slot or pick_event.get("picked_by_user", False):
                user_roster.append(pick_event)
                pos = str(pick_event.get("position", "BENCH")).upper()
                if pos in roster_by_position and len(roster_by_position[pos]) < 2:
                    roster_by_position[pos].append(pick_event)
                else:
                    roster_by_position["BENCH"].append(pick_event)

    # Top 50 available players for UI display
    top_50_available = ada_rankings[:50]

    return {
        "draft_id": draft_id,
        "user_team_slot": active_user_slot,
        "num_teams": num_teams,
        "current_pick": current_pick,
        "current_round": current_round,
        "team_on_clock": team_on_clock,
        "picks_until_user_turn": picks_until_user_turn,
        "is_user_on_clock": (team_on_clock == active_user_slot),
        "draft_log": draft_log,
        "user_roster": user_roster,
        "roster_by_position": roster_by_position,
        "ada_rankings": top_50_available,
        "agent_advisories": _cached_agent_advisory.get(draft_id),
        "espn_teams": _espn_teams,
        "scoring_format": _scoring_format,
        "roster_requirements": _roster_requirements,
        "is_3rr": _is_3rr,
        "draft_started": _draft_started,
    }


@app.get("/api/state")
async def get_state(draft_id: str = "default_draft_2026", user_team_slot: Optional[int] = None):
    """Fetch current full draft state, user roster, available players, and rankings."""
    state_payload = build_full_draft_state(draft_id=draft_id, user_team_slot=user_team_slot)
    return state_payload


@app.get("/api/config")
async def get_config():
    """Fetch current league configuration & environment variables."""
    return {
        "league_id": os.getenv("ESPN_LEAGUE_ID", ""),
        "season_year": int(os.getenv("ESPN_SEASON_YEAR", "2026")),
        "espn_s2": os.getenv("ESPN_S2_COOKIE", ""),
        "swid": os.getenv("ESPN_SWID_COOKIE", ""),
        "user_team_slot": _user_team_slot,
        "num_teams": _num_teams,
        "espn_teams": _espn_teams,
        "scoring_format": _scoring_format,
        "roster_requirements": _roster_requirements,
        "is_3rr": _is_3rr,
        "draft_started": _draft_started,
    }


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    """Update active user team slot and total teams configuration."""
    global _user_team_slot, _num_teams, _is_3rr
    if req.user_team_slot is not None:
        _user_team_slot = req.user_team_slot
    if req.num_teams is not None:
        _num_teams = req.num_teams
    if req.is_3rr is not None:
        _is_3rr = req.is_3rr

    draft_id = req.draft_id or "default_draft_2026"
    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "CONFIG_UPDATED",
        "state": new_state,
    })

    return {"success": True, "state": new_state}


@app.post("/api/draft/start")
async def start_draft(draft_id: str = "default_draft_2026"):
    """Transition draft state to started (live draft active)."""
    global _draft_started
    _draft_started = True
    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "DRAFT_STARTED",
        "state": new_state,
    })

    return {"success": True, "state": new_state}


@app.post("/api/draft/deliberate")
async def deliberate_draft(draft_id: str = "default_draft_2026"):
    """Trigger the multi-agent debate manually with a generous 25.0s timeout."""
    global _cached_agent_advisory

    state_payload = build_full_draft_state(draft_id=draft_id)
    top_candidates = state_payload.get("ada_rankings", [])[:3]
    user_roster = state_payload.get("user_roster", [])
    ada_rankings = state_payload.get("ada_rankings", [])

    try:
        advisory = await asyncio.wait_for(
            asyncio.to_thread(
                orchestrator.run_orchestration,
                candidate_players=top_candidates,
                user_roster=user_roster,
                ada_rankings=ada_rankings,
                timeout_seconds=25.0,
            ),
            timeout=25.0,
        )
        _cached_agent_advisory[draft_id] = advisory
        state_payload["agent_advisories"] = advisory
    except Exception as exc:
        LOGGER.warning("Agent manual debate failed or timed out: %s. Using Ada fallback.", exc)
        fallback = orchestrator.build_fallback_payload(ada_rankings)
        _cached_agent_advisory[draft_id] = fallback
        state_payload["agent_advisories"] = fallback

    await manager.broadcast({
        "type": "DEBATE_COMPLETED",
        "state": state_payload,
    })

    return {"success": True, "state": state_payload}


@app.post("/api/sync_espn")
async def sync_espn(req: SyncESPNRequest):
    """Programmatically sync ESPN league data, extract teams/roster/scoring, and ingest players."""
    global _espn_teams, _num_teams, _scoring_format, _roster_requirements

    league_id = req.league_id or int(os.getenv("ESPN_LEAGUE_ID", "0"))
    season_year = req.season_year or int(os.getenv("ESPN_SEASON_YEAR", "2026"))
    espn_s2 = req.espn_s2 or os.getenv("ESPN_S2_COOKIE", "")
    swid = req.swid or os.getenv("ESPN_SWID_COOKIE", "")

    if not league_id:
        raise HTTPException(status_code=400, detail="ESPN League ID is required.")

    from config.settings import update_data_source_settings
    active_sources = update_data_source_settings(
        enable_sleeper_adp=req.enable_sleeper_adp,
        enable_fantasypros_ecr=req.enable_fantasypros_ecr,
        enable_high_stakes_adp=req.enable_underdog_adp,
        enable_vegas_props=req.enable_vegas_props,
        enable_high_stakes_projections=req.enable_high_stakes_projections,
        enable_advanced_metrics=req.enable_advanced_metrics,
    )

    try:
        from data.espn_ingest import sync_espn_league_data, fetch_espn_roster_and_scoring
        res = sync_espn_league_data(
            league_id=league_id,
            season_year=season_year,
            espn_s2=espn_s2,
            swid=swid,
            upsert_supabase=True,
            use_multi_source=req.use_multi_source,
        )

        if res.get("teams"):
            _espn_teams = res["teams"]
            _num_teams = len(res["teams"])

        # Fetch extra settings
        api_settings = fetch_espn_roster_and_scoring(
            league_id=league_id,
            season_year=season_year,
            espn_s2=espn_s2,
            swid=swid,
        )
        if api_settings.get("roster_requirements"):
            _roster_requirements = api_settings["roster_requirements"]
        elif res.get("roster_requirements"):
            _roster_requirements = res["roster_requirements"]

        if api_settings.get("scoring_format"):
            _scoring_format = api_settings["scoring_format"]
        elif res.get("scoring_format"):
            _scoring_format = res["scoring_format"]

        draft_id = req.draft_id or "default_draft_2026"
        new_state = build_full_draft_state(draft_id=draft_id)

        await manager.broadcast({
            "type": "ESPN_SYNCED",
            "state": new_state,
        })

        msg = f"Successfully synced {res.get('player_count', 0)} players!"
        if res.get("used_offline_fallback", False):
            err_details = res.get("error_message") or "Invalid credentials or connection timeout"
            msg = f"Warning: ESPN Live Sync failed ({err_details}). Loaded offline fallback seed data instead (No team names fetched)."

        return {
            "success": True,
            "message": msg,
            "used_offline_fallback": res.get("used_offline_fallback", False),
            "teams": _espn_teams,
            "scoring_format": _scoring_format,
            "roster_requirements": _roster_requirements,
            "feed_status": res.get("feed_status", {}),
            "state": new_state,
        }
    except Exception as exc:
        LOGGER.error("Failed to sync ESPN league data: %s", exc)
        raise HTTPException(status_code=500, detail=f"ESPN Sync failed: {str(exc)}")


@app.post("/api/keepers")
async def record_keeper(req: KeeperRequest):
    """Log a pre-draft keeper player pick event."""
    global _cached_agent_advisory
    draft_id = req.draft_id or "default_draft_2026"
    if draft_id in _cached_agent_advisory:
        _cached_agent_advisory.pop(draft_id)

    pick_no = calculate_keeper_pick_no(
        round_no=req.round_no,
        team_slot=req.team_slot,
        num_teams=_num_teams,
        is_3rr=_is_3rr,
    )

    # Resolve player metadata
    available = draft_service.get_available_players(draft_id)
    target_player = next((p for p in available if str(p.get("player_id")) == str(req.player_id)), None)

    if not target_player:
        seed = load_seed_players()
        target_player = next((p for p in seed if str(p.get("player_id")) == str(req.player_id)), None)

    player_name = target_player.get("full_name", "Unknown Player") if target_player else "Unknown Player"
    position = target_player.get("position", "FLEX") if target_player else "FLEX"
    team_name = f"Team {req.team_slot}"
    if _espn_teams:
        matching_team = next((t for t in _espn_teams if int(t.get("team_slot", 0)) == req.team_slot), None)
        if matching_team:
            team_name = matching_team.get("team_name", team_name)

    result = draft_service.record_pick(
        draft_id=draft_id,
        pick_no=pick_no,
        round_no=req.round_no,
        team_slot=req.team_slot,
        player_id=req.player_id,
        player_name=player_name,
        position=position,
        team_name=team_name,
        picked_by_user=(req.team_slot == _user_team_slot),
        source="keeper",
        notes="Pre-draft keeper",
    )

    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "KEEPER_LOCKED",
        "keeper": result,
        "state": new_state,
    })

    return {"success": True, "keeper": result, "state": new_state}


@app.post("/api/keepers/undo")
async def undo_keeper(req: KeeperUndoRequest):
    """Remove the highest pick_no keeper player assignment."""
    global _cached_agent_advisory
    draft_id = req.draft_id or "default_draft_2026"
    if draft_id in _cached_agent_advisory:
        _cached_agent_advisory.pop(draft_id)

    log = draft_service.get_draft_log(draft_id)
    keepers = [e for e in log if str(e.get("source", "")).lower() == "keeper" or "keeper" in str(e.get("notes", "")).lower()]

    if not keepers:
        raise HTTPException(status_code=400, detail="No active keepers to undo.")

    latest_keeper = max(keepers, key=lambda x: int(x.get("pick_no", 0)))
    undone = draft_service.delete_specific_pick(draft_id, int(latest_keeper["pick_no"]))

    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "KEEPER_UNDONE",
        "undone": undone,
        "state": new_state,
    })

    return {"success": True, "undone": undone, "state": new_state}


@app.get("/api/players")
async def get_players(draft_id: str = "default_draft_2026", query: Optional[str] = None):
    """Fetch available players list for auto-complete search box."""
    available = draft_service.get_available_players(draft_id)
    if not available:
        seed = load_seed_players()
        draft_service.set_local_players(draft_id, seed)
        available = draft_service.get_available_players(draft_id)

    if query:
        q = query.lower().strip()
        available = [
            p for p in available
            if q in str(p.get("full_name", "")).lower()
            or q in str(p.get("position", "")).lower()
            or q in str(p.get("team", "")).lower()
        ]

    return available[:100]


@app.post("/api/picks")
async def record_pick(req: PickRequest):
    """Submit a draft pick event, recalculate Ada, write telemetry, and broadcast update via WebSockets."""
    global _cached_agent_advisory
    draft_id = req.draft_id or "default_draft_2026"
    if draft_id in _cached_agent_advisory:
        _cached_agent_advisory.pop(draft_id)

    draft_log = draft_service.get_draft_log(draft_id)

    taken_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("event_type", "")).upper() == "PICK"}
    live_pick_nos = {int(e.get("pick_no")) for e in draft_log if str(e.get("source", "")).lower() != "keeper" and "keeper" not in str(e.get("notes", "")).lower()}

    # Determine pick_no based on live draft starting rules
    if req.pick_number:
        current_pick = req.pick_number
    elif not _draft_started or not live_pick_nos:
        current_pick = 1
        while current_pick in taken_pick_nos:
            current_pick += 1
    else:
        current_pick = max(live_pick_nos) + 1
        while current_pick in taken_pick_nos:
            current_pick += 1

    num_teams = _num_teams
    round_no = ((current_pick - 1) // num_teams) + 1
    team_slot = req.team_slot or get_team_on_clock(current_pick, num_teams=num_teams)

    # Find player metadata
    available = draft_service.get_available_players(draft_id)
    target_player = next((p for p in available if str(p.get("player_id")) == str(req.player_id)), None)

    if not target_player:
        seed = load_seed_players()
        target_player = next((p for p in seed if str(p.get("player_id")) == str(req.player_id)), None)

    player_name = target_player.get("full_name", "Unknown Player") if target_player else "Unknown Player"
    position = target_player.get("position", "FLEX") if target_player else "FLEX"

    # 1. Record pick event atomically
    result = draft_service.record_pick(
        draft_id=draft_id,
        pick_no=current_pick,
        round_no=round_no,
        team_slot=team_slot,
        player_id=req.player_id,
        player_name=player_name,
        position=position,
        picked_by_user=req.drafted_by_user,
        source="manual",
        notes=req.notes,
    )

    # 2. Build updated state & trigger agent advisory if user turn upcoming
    new_state = build_full_draft_state(draft_id=draft_id)

    # 3. Broadcast mutation <10ms to WebSocket subscribers
    await manager.broadcast({
        "type": "PICK_RECORDED",
        "pick": result,
        "state": new_state,
    })

    return {"success": True, "pick": result, "state": new_state}


@app.delete("/api/picks/{pick_no}")
async def delete_pick(pick_no: int, draft_id: str = "default_draft_2026"):
    """Delete a specific pick from the draft log and free up the player."""
    global _cached_agent_advisory
    if draft_id in _cached_agent_advisory:
        _cached_agent_advisory.pop(draft_id)

    undone = draft_service.delete_specific_pick(draft_id, pick_no)
    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "PICK_DELETED",
        "undone": undone,
        "state": new_state,
    })

    return {"success": True, "undone": undone, "state": new_state}


@app.post("/api/undo")
async def undo_pick(req: UndoRequest):
    """Execute atomic rollback popping the latest pick off the draft stack."""
    global _cached_agent_advisory
    draft_id = req.draft_id or "default_draft_2026"
    if draft_id in _cached_agent_advisory:
        _cached_agent_advisory.pop(draft_id)

    undone_pick = draft_service.undo_last_pick(draft_id)

    if not undone_pick:
        raise HTTPException(status_code=400, detail="No active picks to undo.")

    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "PICK_UNDONE",
        "undone_pick": undone_pick,
        "state": new_state,
    })

    return {"success": True, "undone_pick": undone_pick, "state": new_state}


@app.post("/api/reset")
async def reset_draft(req: ResetRequest):
    """Reset draft log and restore player availability."""
    global _draft_started, _cached_agent_advisory
    _draft_started = False
    draft_id = req.draft_id or "default_draft_2026"
    if draft_id in _cached_agent_advisory:
        _cached_agent_advisory.pop(draft_id)

    success = draft_service.reset_draft(draft_id)
    new_state = build_full_draft_state(draft_id=draft_id)

    await manager.broadcast({
        "type": "DRAFT_RESET",
        "state": new_state,
    })

    return {"success": success, "state": new_state}


@app.websocket("/ws/draft")
async def websocket_draft_endpoint(websocket: WebSocket, draft_id: str = "default_draft_2026"):
    """Persistent WebSocket endpoint for real-time state synchronization (<10ms UI updates)."""
    await manager.connect(websocket)
    try:
        # Send initial draft state on connection
        initial_state = build_full_draft_state(draft_id=draft_id)
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "state": initial_state,
        })

        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                msg_type = payload.get("type")

                if msg_type == "PING":
                    await websocket.send_json({"type": "PONG"})
                elif msg_type == "RECORD_PICK":
                    pick_data = payload.get("data", {})
                    req = PickRequest(**pick_data)
                    await record_pick(req)
                elif msg_type == "UNDO":
                    req = UndoRequest(draft_id=payload.get("draft_id", draft_id))
                    await undo_pick(req)
            except Exception as exc:
                LOGGER.warning("Error processing WS message: %s", exc)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        LOGGER.error("WebSocket unhandled exception: %s", exc)
        manager.disconnect(websocket)
