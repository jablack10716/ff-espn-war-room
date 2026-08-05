"""Main Streamlit Application for Fantasy Football AI War Room.

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

from dotenv import load_dotenv

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

import streamlit as st

from engine.ada_math import AdaQuantEngine
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
    page_title="Fantasy Football AI War Room",
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


def main() -> None:
    init_session_state()

    # Instantiate draft state service early for sidebar components
    service = DraftStateService(use_supabase=True)
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
        team_name = None
        if st.session_state.espn_teams:
            for t in st.session_state.espn_teams:
                if int(t.get("team_slot", 0)) == int(team_slot):
                    team_name = t.get("team_name")
                    break

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
        )
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
            source="keeper",
            notes="Pre-draft keeper",
        )
        st.rerun()

    def handle_undo_last_pick() -> None:
        undone = service.undo_last_pick(st.session_state.draft_id)
        if undone:
            st.toast(f"Undone pick #{undone.get('pick_no')}: {undone.get('player_name')}")
        else:
            st.toast("No active pick events to undo.")
        st.rerun()

    def handle_reset_draft() -> None:
        service.reset_draft(st.session_state.draft_id)
        st.toast("Reset draft state successfully.")
        st.rerun()

    st.title("🏈 Fantasy Football AI War Room")
    st.caption("Live Draft Assistant | Ada Quant Engine Active")

    # Sidebar settings
    with st.sidebar:
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

        st.markdown("---")
        st.subheader("🏈 ESPN League Sync")
        espn_league_id = st.text_input("ESPN League ID", value=os.getenv("ESPN_LEAGUE_ID", ""))
        espn_year = st.number_input("Season Year", value=int(os.getenv("ESPN_SEASON_YEAR", "2026")))
        espn_s2 = os.getenv("ESPN_S2_COOKIE", "")
        espn_swid = os.getenv("ESPN_SWID_COOKIE", "")

        if st.button("🔄 Sync ESPN League & Players", use_container_width=True):
            if not espn_league_id or not espn_s2 or not espn_swid:
                st.error("Please ensure ESPN credentials are in `.env` or provided above.")
            else:
                with st.spinner("Connecting to ESPN & updating database..."):
                    try:
                        from data.espn_ingest import sync_espn_league_data, fetch_espn_roster_and_scoring
                        res = sync_espn_league_data(
                            league_id=int(espn_league_id),
                            season_year=int(espn_year),
                            espn_s2=espn_s2,
                            swid=espn_swid,
                            upsert_supabase=True,
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

                        st.success(f"Synced {res['player_count']} players & {len(res['teams'])} teams from ESPN!")
                        st.caption(f"Scoring: **{st.session_state.scoring_format}** | Roster: {st.session_state.roster_requirements}")
                    except Exception as exc:
                        st.error(f"ESPN Sync failed: {exc}")

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
        with st.expander("📌 Pre-Draft Keepers"):
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
            value=st.session_state.get("agent_timeout_seconds", 15),
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

    # Current pick calculation (first unassigned pick_no)
    taken_pick_nos = {
        int(e.get("pick_no"))
        for e in draft_log
        if str(e.get("event_type", "PICK")).upper() == "PICK" and e.get("pick_no") is not None
    }
    current_pick = 1
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
            else:
                is_even = (r % 2 == 1)  # Round 2 & 3 are both reversed (N -> 1)
        else:
            is_even = (r % 2 == 0)

        return (num - p_in_r) if is_even else (p_in_r + 1)

    # Calculate distance to user turn
    user_slot = st.session_state.user_team_slot
    picks_until_user_turn = 0
    cur_check = current_pick
    while cur_check < current_pick + 20:
        if get_slot_for_pick(cur_check) == user_slot:
            picks_until_user_turn = cur_check - current_pick
            break
        cur_check += 1

    # Simulator Callbacks

    def handle_simulate_pick() -> None:
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
        max_picks = 200
        cur_p = current_pick
        while cur_p < max_picks:
            c_slot = get_slot_for_pick(cur_p)
            if c_slot == st.session_state.user_team_slot:
                break
            c_round = ((cur_p - 1) // st.session_state.num_teams) + 1
            service.simulate_opponent_pick(
                draft_id=st.session_state.draft_id,
                pick_no=cur_p,
                round_no=c_round,
                team_slot=c_slot,
            )
            cur_p += 1
        st.toast(f"Simulated picks up to your turn at Pick #{cur_p}!")
        st.rerun()

    def handle_reset_draft() -> None:
        service.reset_draft(st.session_state.draft_id)
        st.toast("Reset draft state successfully.")
        st.rerun()

    from ui.components.my_roster import render_my_roster

    # Main Page Tabs: Live War Room | Full Draft Board Grid
    tab_war_room, tab_full_grid = st.tabs(["🎯 Live War Room", "📊 Full Draft Board Grid"])

    with tab_war_room:
        # Layout: Recommendations | My Roster | Draft Board
        col_recs, col_roster, col_board = st.columns([2, 1, 2])

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

            # Trigger Multi-Agent Orchestrator if picks_until_user_turn <= 2
            agent_payload = None
            if orchestrator.should_trigger(picks_until_user_turn):
                agent_payload = orchestrator.run_orchestration(
                    candidate_players=available_players,
                    user_roster=user_roster,
                    ada_rankings=rankings,
                    timeout_seconds=float(st.session_state.get("agent_timeout_seconds", 15)),
                )

            render_recommendations(rankings, agent_payload=agent_payload, user_roster=user_roster, top_n=5)

        with col_roster:
            render_my_roster(
                draft_log=draft_log,
                user_team_slot=st.session_state.user_team_slot,
                roster_requirements=st.session_state.roster_requirements,
            )

        with col_board:
            render_draft_board(
                available_players=available_players,
                draft_log=draft_log,
                on_record_pick=handle_record_pick,
                on_undo_last_pick=handle_undo_last_pick,
                current_pick=current_pick,
                num_teams=st.session_state.num_teams,
                is_mock_mode=(st.session_state.draft_mode == "🧪 Practice Mock Draft"),
                is_3rr=st.session_state.is_3rr,
                espn_teams=st.session_state.espn_teams,
                on_simulate_pick=handle_simulate_pick,
                on_simulate_to_user_turn=handle_simulate_to_user_turn,
                on_reset_draft=handle_reset_draft,
            )

    with tab_full_grid:
        render_full_draft_grid(
            draft_log=draft_log,
            espn_teams=st.session_state.espn_teams,
            num_teams=st.session_state.num_teams,
            is_3rr=st.session_state.is_3rr,
            total_rounds=st.session_state.total_rounds,
        )


if __name__ == "__main__":
    main()
