"""Main Streamlit Application for The Best Damn Fantasy Football Drafting App.

Integrates Ada quantitative recommendation engine, real-time draft log tracking,
and atomic Undo Last Pick actions across isolated @st.fragment blocks.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ui.startup

from dotenv import load_dotenv

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

import streamlit as st

from engine.ada_math import AdaQuantEngine
from services.action_logger import log_action
from services.draft_state_service import DraftStateService
from services.heartbeat import HeartbeatWorker
from services.realtime_listener import RealtimeListener
from ui.components.connectivity_status import render_connectivity_status
from ui.components.draft_board import render_draft_board
from ui.components.full_draft_grid import render_full_draft_grid
from ui.components.keeper_manager import render_keeper_manager
from ui.components.recommendations import render_recommendations

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("war_room_app")

st.set_page_config(
    page_title="The Best Damn Fantasy Football Drafting App",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    """Initialize Streamlit session state keys."""
    if "draft_mode" not in st.session_state:
        st.session_state.draft_mode = "🎯 Live ESPN Draft"
    if "draft_id" not in st.session_state:
        st.session_state.draft_id = "live_draft_2026"
    if "user_team_slot" not in st.session_state:
        st.session_state.user_team_slot = 1
    if "num_teams" not in st.session_state:
        st.session_state.num_teams = 12
    if "is_3rr" not in st.session_state:
        st.session_state.is_3rr = False
    if "espn_teams" not in st.session_state:
        st.session_state.espn_teams = []
    if "roster_requirements" not in st.session_state:
        st.session_state.roster_requirements = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "SUPERFLEX": 1, "DST": 1}
    if "scoring_format" not in st.session_state:
        st.session_state.scoring_format = "HALF_PPR"
    if "total_rounds" not in st.session_state:
        st.session_state.total_rounds = 16
    if "realtime_listener" not in st.session_state:
        st.session_state.realtime_listener = None
    if "heartbeat_worker" not in st.session_state:
        st.session_state.heartbeat_worker = None
    if "ws_connected" not in st.session_state:
        st.session_state.ws_connected = True
    if "heartbeat_healthy" not in st.session_state:
        st.session_state.heartbeat_healthy = True
    if "fallback_mode" not in st.session_state:
        st.session_state.fallback_mode = False
    if "keeper_expander_open" not in st.session_state:
        st.session_state.keeper_expander_open = False
    if "draft_started" not in st.session_state:
        st.session_state.draft_started = False
    if "agent_timeout_seconds" not in st.session_state:
        st.session_state.agent_timeout_seconds = 25


@st.cache_resource
def get_cached_draft_state_service() -> DraftStateService:
    """Return a singleton DraftStateService instance across Streamlit reruns."""
    return DraftStateService(use_supabase=True)


def main() -> None:
    init_session_state()

    # Instantiate cached draft state service singleton
    service = get_cached_draft_state_service()
    available_players, draft_log = service.reconcile_state(st.session_state.draft_id)

    # Callback handlers defined early for sidebar & board access
    def handle_record_pick(
        pick_no: int,
        round_no: int,
        team_slot: int,
        player_id: str,
        player_name: str,
        position: str,
        picked_by_user: bool,
    ) -> None:
        st.session_state["active_grid_pick_no"] = None
        st.session_state["fallback_active_grid_pick_no"] = None
        st.session_state["grid_dialog_force_close_once"] = True

        team_name = None
        if st.session_state.espn_teams:
            for t in st.session_state.espn_teams:
                if int(t.get("team_slot", 0)) == int(team_slot):
                    team_name = t.get("team_name")
                    break

        log_action(
            "RECORD_PICK",
            f"Recording pick #{pick_no} for player '{player_name}'",
            {
                "draft_id": st.session_state.draft_id,
                "pick_no": pick_no,
                "round_no": round_no,
                "team_slot": team_slot,
                "player_id": player_id,
                "player_name": player_name,
                "position": position,
                "picked_by_user": picked_by_user,
            },
        )

        is_draft_started = st.session_state.get("draft_started", False)
        if st.session_state.draft_mode == "🎯 Live ESPN Draft":
            is_draft_started = True

        pick_source = "keeper" if not is_draft_started else "manual"
        pick_notes = "Pre-draft keeper" if not is_draft_started else None

        try:
            upsert_pick = getattr(service, "upsert_pick", None)
            if callable(upsert_pick):
                upsert_pick(
                    draft_id=st.session_state.draft_id,
                    pick_no=pick_no,
                    round_no=round_no,
                    team_slot=team_slot,
                    player_id=player_id,
                    player_name=player_name,
                    position=position,
                    team_name=team_name,
                    picked_by_user=picked_by_user,
                    source=pick_source,
                    notes=pick_notes,
                )
            else:
                LOGGER.warning("DraftStateService.upsert_pick unavailable at runtime; falling back to record_pick")
                service.record_pick(
                    draft_id=st.session_state.draft_id,
                    pick_no=pick_no,
                    round_no=round_no,
                    team_slot=team_slot,
                    player_id=player_id,
                    player_name=player_name,
                    position=position,
                    team_name=team_name,
                    picked_by_user=picked_by_user,
                    source=pick_source,
                    notes=pick_notes,
                )
            st.session_state.flash_notification = (
                "success",
                f"✅ Logged pick #{pick_no}: **{player_name}** ({position}) to {team_name or f'Slot {team_slot}'}!"
            )
            log_action("RECORD_PICK_SUCCESS", f"Pick #{pick_no} successfully saved.")
        except Exception as exc:
            st.session_state.flash_notification = (
                "error",
                f"❌ Failed to save pick #{pick_no}. {exc}"
            )
            log_action("RECORD_PICK_ERROR", f"Failed to save pick #{pick_no}", {"error": str(exc)})
        st.rerun()

    def handle_record_keeper(
        pick_no: int,
        round_no: int,
        team_slot: int,
        player_id: str,
        player_name: str,
        position: str,
        team_name: str,
        picked_by_user: bool,
    ) -> None:
        log_action("RECORD_KEEPER_START", f"Locking keeper #{pick_no}: {player_name}", {
            "draft_id": st.session_state.draft_id,
            "pick_no": pick_no,
            "round_no": round_no,
            "team_slot": team_slot,
            "player_id": player_id,
            "player_name": player_name,
            "position": position,
            "team_name": team_name,
            "picked_by_user": picked_by_user,
        })
        try:
            res = service.record_pick(
                draft_id=st.session_state.draft_id,
                pick_no=pick_no,
                round_no=round_no,
                team_slot=team_slot,
                player_id=player_id,
                player_name=player_name,
                position=position,
                team_name=team_name,
                picked_by_user=picked_by_user,
                source="manual",
                notes="Pre-draft keeper",
            )
            log_action("RECORD_KEEPER_SUCCESS", f"Keeper #{pick_no} saved successfully", {"result": str(res)})
            st.session_state.flash_notification = (
                "success",
                f"🔒 Keeper Locked: **{player_name}** ({position}) assigned to {team_name} at Pick #{pick_no}!"
            )
        except Exception as exc:
            log_action("RECORD_KEEPER_ERROR", f"Failed to record keeper #{pick_no}: {exc}", {"error": str(exc)})
            st.session_state.flash_notification = (
                "error",
                f"❌ Failed to lock keeper #{pick_no}: {exc}"
            )
        st.rerun()

    def handle_undo_last_pick() -> None:
        log_action("UNDO_LAST_PICK", "Undoing last pick")
        undone = service.undo_last_pick(st.session_state.draft_id)
        if undone:
            st.session_state.flash_notification = (
                "info",
                f"⏪ Undone pick #{undone.get('pick_no')}: **{undone.get('player_name')}** restored to available pool."
            )
            log_action("UNDO_LAST_PICK_SUCCESS", f"Undone pick #{undone.get('pick_no')}")
        else:
            st.session_state.flash_notification = ("info", "ℹ️ No active pick events to undo.")
            log_action("UNDO_LAST_PICK_EMPTY", "No picks to undo")
        st.rerun()

    def handle_delete_specific_pick(pick_no: int) -> None:
        st.session_state["active_grid_pick_no"] = None
        st.session_state["fallback_active_grid_pick_no"] = None
        st.session_state["grid_dialog_force_close_once"] = True

        log_action("DELETE_SPECIFIC_PICK", f"Deleting pick #{pick_no}")
        deleted = service.delete_specific_pick(st.session_state.draft_id, pick_no)
        if deleted:
            st.session_state.flash_notification = (
                "success",
                f"🗑️ Cleared Pick #{pick_no}: **{deleted.get('player_name')}** restored to available pool."
            )
            log_action("DELETE_SPECIFIC_PICK_SUCCESS", f"Cleared Pick #{pick_no}")
        else:
            st.session_state.flash_notification = ("info", f"ℹ️ No pick found at #{pick_no} to clear.")
            log_action("DELETE_SPECIFIC_PICK_EMPTY", f"No pick found at #{pick_no}")
        st.rerun()

    def handle_reset_draft() -> None:
        service.reset_draft(st.session_state.draft_id)
        st.session_state.flash_notification = (
            "success",
            f"🗑️ Draft '{st.session_state.draft_id}' cleared! All logged picks deleted and players restored to available pool."
        )
        st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog("⚠️ Confirm Reset Draft")
        def confirm_reset_dialog() -> None:
            st.warning(
                f"⚠️ **Are you sure you want to reset draft '{st.session_state.draft_id}'?**\n\n"
                f"This will permanently delete **ALL logged picks and keepers** and restore all players to the available draft pool."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🚨 Yes, Clear Everything", type="primary", use_container_width=True):
                    st.session_state["show_reset_confirm"] = False
                    handle_reset_draft()
            with c2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state["show_reset_confirm"] = False
                    st.rerun()

    def request_reset_confirmation() -> None:
        st.session_state["show_reset_confirm"] = True

    st.title("🏈 The Best Damn Fantasy Football Drafting App")
    st.caption("Live Draft Assistant | Ada Quant Engine Active")

    # Render Reset Confirmation Modal if triggered
    if st.session_state.get("show_reset_confirm"):
        if hasattr(st, "dialog"):
            confirm_reset_dialog()

    # Render Flash Notification Toast if present (Option A: Single lightweight toast)
    if st.session_state.get("flash_notification"):
        ntype, msg = st.session_state.flash_notification
        icon_map = {"success": "✅", "info": "ℹ️", "error": "⚠️"}
        st.toast(msg, icon=icon_map.get(ntype, "ℹ️"))
        st.session_state.flash_notification = None

    # Sidebar settings
    with st.sidebar:
        st.markdown("### 🏈 The Best Damn Fantasy Football Drafting App")
        st.markdown("---")
        st.header("⚙️ Draft Settings")
        mode = st.radio(
            "Select Mode:",
            options=["🎯 Live ESPN Draft", "🧪 Practice Mock Draft"],
            key="draft_mode_radio",
        )
        st.session_state.draft_mode = mode

        if mode == "🧪 Practice Mock Draft":
            st.session_state.draft_id = st.text_input("Mock Draft ID", value="mock_practice_2026")
            st.info("🧪 Mock Practice Mode Active: Use Bot controls to simulate opponent picks!")
        else:
            st.session_state.draft_id = st.text_input("Live Draft ID", value="live_draft_2026")

        if st.button("🗑️ Reset / Clear Draft Picks", use_container_width=True, help="Deletes all logged picks and restores all players to available state."):
            request_reset_confirmation()
            st.rerun()

        st.markdown("---")
        st.subheader("🌐 Multi-Source Data Sync")
        st.caption("Blends ESPN, Sleeper ADP, FantasyPros ECR & Dynamic Depth Charts")

        espn_league_id = st.text_input("ESPN League ID", value=os.getenv("ESPN_LEAGUE_ID", ""))
        espn_year = st.number_input("Season Year", value=int(os.getenv("ESPN_SEASON_YEAR", "2026")))
        espn_s2 = os.getenv("ESPN_S2_COOKIE", "")
        espn_swid = os.getenv("ESPN_SWID_COOKIE", "")

        use_multi_source = st.checkbox("Enable Multi-Source Blending (Sleeper + FantasyPros)", value=True)

        with st.expander("⚖️ Projection Blend Weights"):
            fp_weight = st.slider("FantasyPros ECR Weight", 0.0, 1.0, 0.50, 0.05)
            sleeper_weight = st.slider("Sleeper ADP Weight", 0.0, 1.0, 0.25, 0.05)
            espn_weight = st.slider("ESPN Projection Weight", 0.0, 1.0, 0.25, 0.05)

        if st.button("🔄 Sync Multi-Source Data & Players", use_container_width=True):
            if not espn_league_id:
                st.error("Please provide your ESPN League ID above or in `.env`.")
            else:
                with st.spinner("Connecting to ESPN, Sleeper, and FantasyPros..."):
                    try:
                        from data.espn_ingest import sync_espn_league_data, fetch_espn_roster_and_scoring
                        res = sync_espn_league_data(
                            league_id=int(espn_league_id),
                            season_year=int(espn_year),
                            espn_s2=espn_s2,
                            swid=espn_swid,
                            upsert_supabase=True,
                            use_multi_source=use_multi_source,
                        )
                        st.session_state.espn_teams = res["teams"]
                        st.session_state.num_teams = len(res["teams"]) if res["teams"] else st.session_state.num_teams

                        # Fetch roster slots & scoring format from raw ESPN API
                        api_settings = fetch_espn_roster_and_scoring(
                            league_id=int(espn_league_id),
                            season_year=int(espn_year),
                            espn_s2=espn_s2,
                            swid=espn_swid,
                        )
                        if api_settings.get("roster_requirements"):
                            st.session_state.roster_requirements = api_settings["roster_requirements"]
                        else:
                            st.session_state.roster_requirements = res.get("roster_requirements", st.session_state.roster_requirements)
                        if api_settings.get("scoring_format"):
                            st.session_state.scoring_format = api_settings["scoring_format"]
                        else:
                            st.session_state.scoring_format = res.get("scoring_format", "STANDARD")
                        if api_settings.get("total_rounds"):
                            st.session_state.total_rounds = api_settings["total_rounds"]

                        if res.get("used_offline_fallback"):
                            st.warning("⚠️ Live API connection failed. Loaded offline seed data as fallback.")
                        else:
                            st.success(f"Synced {res['player_count']} players across active sources!")
                        
                        st.caption(
                            f"🟢 **Sources Active**: ESPN | Sleeper API | FantasyPros ECR\n\n"
                            f"Scoring: **{st.session_state.scoring_format}** | Roster: {st.session_state.roster_requirements}"
                        )
                    except Exception as exc:
                        st.error(f"Multi-Source Sync failed: {exc}")

        # Team Selection
        if st.session_state.espn_teams:
            team_options = {
                f"Slot {t['team_slot']}: {t['team_name']} ({t['owner']})": t["team_slot"]
                for t in st.session_state.espn_teams
            }
            default_index = 0
            for idx, label in enumerate(team_options.keys()):
                if "Eskimo Brothers" in label:
                    default_index = idx
                    break
            selected_team_label = st.selectbox(
                "Your Team (ESPN)",
                options=list(team_options.keys()),
                index=default_index,
            )
            if selected_team_label:
                st.session_state.user_team_slot = team_options[selected_team_label]
        else:
            st.session_state.user_team_slot = st.number_input("Your Team Slot", min_value=1, max_value=20, value=st.session_state.user_team_slot)

        st.session_state.num_teams = st.number_input("Total Teams", min_value=4, max_value=20, value=st.session_state.num_teams)
        st.session_state.total_rounds = st.number_input("Draft Rounds", min_value=6, max_value=25, value=st.session_state.total_rounds)

        # Custom Draft Order & 3rd Round Reversal
        with st.expander("🔀 Custom Draft Order & Rules"):
            st.session_state.is_3rr = st.checkbox("3rd Round Reversal (3RR)", value=st.session_state.is_3rr)

            if st.session_state.espn_teams:
                st.markdown("**Reorder ESPN Team Slots:**")
                for t in st.session_state.espn_teams:
                    new_slot = st.number_input(
                        f"{t['team_name']} Slot",
                        min_value=1,
                        max_value=len(st.session_state.espn_teams),
                        value=int(t["team_slot"]),
                        key=f"slot_edit_{t['team_id']}",
                    )
                    t["team_slot"] = new_slot
                # Keep sorted
                st.session_state.espn_teams = sorted(st.session_state.espn_teams, key=lambda x: int(x["team_slot"]))

        # Pre-Draft Keepers Manager
        with st.expander("📌 Pre-Draft Keepers", expanded=st.session_state.get("keeper_expander_open", False)):
            render_keeper_manager(
                available_players=available_players,
                draft_log=draft_log,
                espn_teams=st.session_state.espn_teams,
                user_team_slot=st.session_state.user_team_slot,
                num_teams=st.session_state.num_teams,
                is_3rr=st.session_state.is_3rr,
                on_record_keeper=handle_record_keeper,
                on_undo_keeper=handle_undo_last_pick,
            )

        st.markdown("---")
        st.subheader("⏱️ Agent Deliberation Timeout")
        st.session_state.agent_timeout_seconds = st.slider(
            "Max LLM Timeout (seconds)",
            min_value=3,
            max_value=30,
            value=st.session_state.get("agent_timeout_seconds", 25),
            help="Allows agents longer time for deep scouting debate when on the clock.",
        )

        st.markdown("---")
        st.subheader("📄 Offline Backup & Print")
        with st.expander("🖨️ Export Pre-Draft Cheat Sheet"):
            st.caption("Download hard-copy backups before draft day in case of power or internet loss.")
            from engine.cheat_sheet import (
                generate_csv_cheat_sheet,
                generate_printable_html_cheat_sheet,
                generate_ranked_csv_cheat_sheet,
                generate_ranked_html_cheat_sheet,
            )

            # We fetch current available players for export
            tmp_service = DraftStateService(use_supabase=True)
            tmp_players = tmp_service.get_available_players(st.session_state.draft_id)

            if tmp_players:
                csv_data = generate_csv_cheat_sheet(tmp_players)
                html_data = generate_printable_html_cheat_sheet(tmp_players, f"Draft Backup ({st.session_state.draft_id})")

                tmp_engine = AdaQuantEngine()
                tmp_rankings = tmp_engine.compute_rankings(
                    available_players=tmp_players,
                    draft_log=[],
                    user_team_slot=st.session_state.user_team_slot,
                    num_teams=st.session_state.num_teams,
                    scoring_format=st.session_state.scoring_format,
                )
                ranked_html = generate_ranked_html_cheat_sheet(tmp_rankings, f"Ada Master Ranking ({st.session_state.draft_id})")
                ranked_csv = generate_ranked_csv_cheat_sheet(tmp_rankings)

                st.markdown("**Position-Grouped Cheat Sheet:**")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.download_button(
                        label="📥 CSV (Positional)",
                        data=csv_data,
                        file_name=f"cheat_sheet_positional_{st.session_state.draft_id}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with col_c2:
                    st.download_button(
                        label="🖨️ Printable HTML",
                        data=html_data,
                        file_name=f"cheat_sheet_positional_{st.session_state.draft_id}.html",
                        mime="text/html",
                        use_container_width=True,
                    )

                st.markdown("**Ada Composite Master Ranking:**")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.download_button(
                        label="🤖 Ranked CSV",
                        data=ranked_csv,
                        file_name=f"cheat_sheet_ranked_{st.session_state.draft_id}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with col_r2:
                    st.download_button(
                        label="🖨️ Print Ranked HTML",
                        data=ranked_html,
                        file_name=f"cheat_sheet_ranked_{st.session_state.draft_id}.html",
                        mime="text/html",
                        use_container_width=True,
                    )
            else:
                st.info("Sync ESPN league or load players to enable cheat sheet export.")

        st.markdown("---")
        st.markdown("### System Health")
        render_connectivity_status(
            ws_connected=st.session_state.ws_connected,
            heartbeat_healthy=st.session_state.heartbeat_healthy,
            fallback_mode=st.session_state.fallback_mode,
        )

    # Instantiate quant engine & orchestrator
    quant_engine = AdaQuantEngine()
    
    from agents.war_room_agents import WarRoomOrchestrator

    orchestrator = WarRoomOrchestrator()

    # Wire Realtime Listener (once per session)
    if st.session_state.realtime_listener is None:
        try:
            from services.realtime_listener import RealtimeListener
            listener = RealtimeListener(draft_id=st.session_state.draft_id)
            listener.start()
            st.session_state.realtime_listener = listener
            st.session_state.ws_connected = True
        except Exception as exc:
            LOGGER.warning("Realtime Listener init failed: %s", exc)
            st.session_state.ws_connected = False

    # Wire Heartbeat Worker (once per session)
    if st.session_state.heartbeat_worker is None:
        try:
            from services.heartbeat import HeartbeatWorker
            hb = HeartbeatWorker(draft_id=st.session_state.draft_id)
            st.session_state.heartbeat_worker = hb
            st.session_state.heartbeat_healthy = True
        except Exception as exc:
            LOGGER.warning("Heartbeat Worker init failed: %s", exc)
            st.session_state.heartbeat_healthy = False

    # Poll Heartbeat health
    if st.session_state.heartbeat_worker:
        try:
            is_healthy, latest_pick = st.session_state.heartbeat_worker.check_heartbeat()
            st.session_state.heartbeat_healthy = is_healthy
        except Exception:
            st.session_state.heartbeat_healthy = False

    # Poll Realtime events queue
    if st.session_state.realtime_listener:
        rt_events = st.session_state.realtime_listener.poll_events()
        if rt_events:
            st.toast(f"📡 Realtime update: {len(rt_events)} event(s) received!")
            st.rerun()

    # Load canonical state
    available_players, draft_log = service.reconcile_state(st.session_state.draft_id)

    # Current pick calculation (Pre-Draft Keeper setup vs Live Draft Progress)
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
        and "keeper" not in str(e.get("notes", "")).lower()
    }

    is_draft_started = st.session_state.get("draft_started", False)
    if st.session_state.draft_mode == "🎯 Live ESPN Draft":
        is_draft_started = True

    if not is_draft_started or not live_pick_nos:
        # Pre-draft mode: start at the first unassigned pick slot starting from Pick 1
        current_pick = 1
        while current_pick in taken_pick_nos:
            current_pick += 1
    else:
        # Live draft in progress: clock remains anchored after the highest live pick made
        current_pick = max(live_pick_nos) + 1
        while current_pick in taken_pick_nos:
            current_pick += 1

    current_round = ((current_pick - 1) // st.session_state.num_teams) + 1

    # Snake draft slot logic helper
    def get_slot_for_pick(p_no: int) -> int:
        num = st.session_state.num_teams
        r = ((p_no - 1) // num) + 1
        p_in_r = (p_no - 1) % num

        if st.session_state.is_3rr:
            # 3rd Round Reversal logic
            if r == 1:
                is_even = False
            elif r in (2, 3):
                is_even = True
            else:
                is_even = (r % 2 == 1)
        else:
            is_even = (r % 2 == 0)

        return (num - p_in_r) if is_even else (p_in_r + 1)

    # Calculate distance to user turn (counting open/unassigned picks)
    user_slot = st.session_state.user_team_slot
    picks_until_user_turn = 0
    cur_check = current_pick
    live_steps = 0
    while cur_check < current_pick + 250:
        if cur_check not in taken_pick_nos:
            if get_slot_for_pick(cur_check) == user_slot:
                picks_until_user_turn = live_steps
                break
            live_steps += 1
        cur_check += 1

    # Simulator Callbacks

    def handle_simulate_pick() -> None:
        st.session_state.draft_started = True
        calc_slot = get_slot_for_pick(current_pick)
        simulated = service.simulate_opponent_pick(
            draft_id=st.session_state.draft_id,
            pick_no=current_pick,
            round_no=current_round,
            team_slot=calc_slot,
        )
        if simulated:
            st.toast(f"Bot Pick #{current_pick}: {simulated.get('player_name')} ({simulated.get('position')})")
        st.rerun()

    def handle_simulate_to_user_turn() -> None:
        st.session_state.draft_started = True
        max_picks = 250
        cur_p = current_pick
        simulated_count = 0
        simulated_names = []
        while cur_p < max_picks:
            # Skip pick slots that are already filled (e.g. by keepers)
            if cur_p in taken_pick_nos:
                cur_p += 1
                continue

            c_slot = get_slot_for_pick(cur_p)
            if c_slot == st.session_state.user_team_slot and simulated_count > 0:
                break

            c_round = ((cur_p - 1) // st.session_state.num_teams) + 1
            simmed = service.simulate_opponent_pick(
                draft_id=st.session_state.draft_id,
                pick_no=cur_p,
                round_no=c_round,
                team_slot=c_slot,
            )
            if simmed:
                simulated_count += 1
                simulated_names.append(f"#{cur_p} {simmed.get('player_name')} ({simmed.get('position')})")
                taken_pick_nos.add(cur_p)
            cur_p += 1

            # Break after simulating up to user's next open turn
            next_p = cur_p
            while next_p in taken_pick_nos and next_p < max_picks:
                next_p += 1
            if get_slot_for_pick(next_p) == st.session_state.user_team_slot:
                break

        if simulated_count > 0:
            summary_str = ", ".join(simulated_names[:3])
            if len(simulated_names) > 3:
                summary_str += f" (+{len(simulated_names)-3} more)"
            st.toast(f"🤖 Auto-picked {simulated_count} opponent(s): {summary_str}. Now on the clock at Pick #{cur_p}!", icon="🎯")
        else:
            st.toast(f"It's already your turn at Pick #{current_pick}!", icon="ℹ️")
        st.rerun()

    def handle_reset_draft() -> None:
        st.session_state.draft_started = False
        service.reset_draft(st.session_state.draft_id)
        st.toast("Reset draft state successfully.")
        st.rerun()

    from ui.components.my_roster import render_my_roster

    # Render Mock Draft Control Bar if in Practice Mode
    if st.session_state.draft_mode == "🧪 Practice Mock Draft":
        with st.container(border=True):
            is_in_progress = st.session_state.get("draft_started", False)
            status_badge = "🚀 **Live Draft In Progress**" if is_in_progress else "📌 **Pre-Draft Setup (Setting Keepers)**"
            st.markdown(
                f"🧪 **Mock Practice Control Bar** — Status: {status_badge} | Current Pick: **#{current_pick}** "
                f"(Round {current_round}, Slot {get_slot_for_pick(current_pick)})"
            )
            m_col1, m_col2, m_col3, m_col4 = st.columns([3, 2, 2, 2])
            with m_col1:
                if st.button("⏩ Auto-Pick All Opponents Until My Turn", type="primary", use_container_width=True, key="mock_banner_auto_pick"):
                    handle_simulate_to_user_turn()
            with m_col2:
                if st.button("🤖 Simulate 1 Bot Pick", use_container_width=True, key="mock_banner_single_pick"):
                    handle_simulate_pick()
            with m_col3:
                if not is_in_progress:
                    if st.button("🚀 Start Live Draft", type="primary", use_container_width=True, key="mock_banner_start_draft"):
                        st.session_state.draft_started = True
                        st.toast("🚀 Live Draft Started! On the clock.", icon="🏁")
                        st.rerun()
                else:
                    if st.button("📌 Return to Pre-Draft", use_container_width=True, key="mock_banner_return_predraft"):
                        st.session_state.draft_started = False
                        st.toast("📌 Returned to Pre-Draft Keeper Setup mode.", icon="ℹ️")
                        st.rerun()
            with m_col4:
                if st.button("🗑️ Reset Mock Draft", use_container_width=True, key="mock_banner_reset"):
                    request_reset_confirmation()
                    st.rerun()

    # Main Page Tabs: Live War Room | Full Draft Board Grid | My Roster
    tab_war_room, tab_full_grid, tab_roster = st.tabs(["🎯 Live War Room", "📊 Full Draft Board Grid", "📋 My Roster"])

    with tab_war_room:
        # Layout: Recommendations | Draft Board
        col_recs, col_board = st.columns([3, 2])

        with col_recs:
            # Compute Ada rankings
            rankings = quant_engine.compute_rankings(
                available_players=available_players,
                draft_log=draft_log,
                user_team_slot=st.session_state.user_team_slot,
                current_round=current_round,
                current_pick=current_pick,
                roster_requirements=st.session_state.roster_requirements,
                num_teams=st.session_state.num_teams,
                scoring_format=st.session_state.scoring_format,
            )

            # Extract user roster for bye week checking & agent context
            user_roster = [e for e in draft_log if int(e.get("team_slot", 0)) == user_slot]

            # Manual trigger for Multi-Agent Orchestrator
            if st.session_state.get("agent_payload_pick_no") != current_pick:
                st.session_state.agent_payload = None

            if st.button("🤖 Ask War Room Agents (Marcus, Winston, Arthur)", use_container_width=True, type="primary"):
                with st.spinner("Agents deliberating..."):
                    st.session_state.agent_payload = orchestrator.run_orchestration(
                        candidate_players=available_players,
                        user_roster=user_roster,
                        ada_rankings=rankings,
                        timeout_seconds=float(st.session_state.get("agent_timeout_seconds", 25)),
                    )
                    st.session_state.agent_payload_pick_no = current_pick

            agent_payload = st.session_state.get("agent_payload")
            render_recommendations(rankings, agent_payload=agent_payload, user_roster=user_roster, top_n=5)



        with col_board:
            render_draft_board(
                available_players=available_players,
                draft_log=draft_log,
                on_record_pick=handle_record_pick,
                on_undo_last_pick=handle_undo_last_pick,
                current_pick=current_pick,
                user_team_slot=st.session_state.user_team_slot,
                num_teams=st.session_state.num_teams,
                is_mock_mode=(st.session_state.draft_mode == "🧪 Practice Mock Draft"),
                is_3rr=st.session_state.is_3rr,
                espn_teams=st.session_state.espn_teams,
                on_simulate_pick=handle_simulate_pick,
                on_simulate_to_user_turn=handle_simulate_to_user_turn,
                on_reset_draft=request_reset_confirmation,
            )

    with tab_full_grid:
        render_full_draft_grid(
            draft_log=draft_log,
            available_players=available_players,
            on_record_pick=handle_record_pick,
            on_delete_specific_pick=handle_delete_specific_pick,
            user_team_slot=st.session_state.user_team_slot,
            espn_teams=st.session_state.espn_teams,
            num_teams=st.session_state.num_teams,
            is_3rr=st.session_state.is_3rr,
            total_rounds=st.session_state.total_rounds,
        )

    with tab_roster:
        render_my_roster(
            draft_log=draft_log,
            user_team_slot=st.session_state.user_team_slot,
            roster_requirements=st.session_state.roster_requirements,
        )


if __name__ == "__main__":
    main()
