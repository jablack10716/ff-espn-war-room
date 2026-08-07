"""Streamlit Component: Draft Board & Player Selection (Fragment A)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import streamlit as st


def render_draft_board(
    available_players: List[Dict[str, Any]],
    draft_log: List[Dict[str, Any]],
    on_record_pick: Callable[[int, int, int, str, str, str, bool], None],
    on_undo_last_pick: Callable[[], None],
    current_pick: int = 1,
    user_team_slot: int = 1,
    num_teams: int = 12,
    is_mock_mode: bool = False,
    is_3rr: bool = False,
    espn_teams: Optional[List[Dict[str, Any]]] = None,
    on_simulate_pick: Optional[Callable[[], None]] = None,
    on_simulate_to_user_turn: Optional[Callable[[], None]] = None,
    on_reset_draft: Optional[Callable[[], None]] = None,
) -> None:
    """Render interactive draft board grid, searchbox input, and mock simulator controls."""
    if is_mock_mode:
        st.subheader("🧪 Practice Mock Draft Board")
    else:
        st.subheader("📋 Live Draft Board")

    col_input, col_actions = st.columns([3, 2])

    # Calculate current round and team slot from pick_no
    calc_round = ((current_pick - 1) // num_teams) + 1
    pick_in_round = (current_pick - 1) % num_teams

    if is_3rr:
        if calc_round == 1:
            is_even_round = False
        elif calc_round in (2, 3):
            is_even_round = True
        else:
            is_even_round = (calc_round % 2 == 1)
    else:
        is_even_round = (calc_round % 2 == 0)

    calc_slot = (num_teams - pick_in_round) if is_even_round else (pick_in_round + 1)

    # Automatically infer if current pick is user's turn
    picked_by_user = (calc_slot == user_team_slot)

    # Map team_slot to team_name if available
    teams_map: Dict[int, str] = {}
    if espn_teams:
        teams_map = {
            int(t["team_slot"]): str(t.get("team_name", f"Team {t['team_slot']}"))
            for t in espn_teams
            if "team_slot" in t
        }

    current_team_name = teams_map.get(calc_slot, f"Team Slot {calc_slot}")

    with col_input:
        st.markdown(f"**Current Pick**: #{current_pick} (Round {calc_round}, {current_team_name})")

        if picked_by_user:
            st.caption("⭐ **YOUR TURN**: Pick will be automatically added to your roster.")
        else:
            st.caption(f"👤 **Opponent Pick**: Assigned to {current_team_name}.")

        # Player search dropdown
        player_options = {
            f"{p.get('full_name')} ({p.get('position')} - {p.get('team', 'FA')})": p
            for p in available_players
        }

        selected_label = st.selectbox(
            "Search and select drafted player:",
            options=["-- Select Player --"] + list(player_options.keys()),
            key=f"searchbox_pick_{current_pick}",
        )

        if st.button("Log Pick", type="primary", use_container_width=True):
            if selected_label and selected_label != "-- Select Player --":
                player = player_options[selected_label]
                on_record_pick(
                    current_pick,
                    calc_round,
                    calc_slot,
                    str(player["player_id"]),
                    str(player["full_name"]),
                    str(player["position"]),
                    picked_by_user,
                )
                st.success(f"Logged pick: {player['full_name']}")

    with col_actions:
        if is_mock_mode:
            st.markdown("### Controls")
            if st.button("⏪ Undo Last Pick", use_container_width=True):
                on_undo_last_pick()

            if st.button("🗑️ Reset / Clear Draft", use_container_width=True):
                if on_reset_draft:
                    on_reset_draft()

            st.markdown("---")
            st.markdown("**Mock Simulator Controls**")

            if st.button("🤖 Simulate Next Bot Pick", use_container_width=True):
                if on_simulate_pick:
                    on_simulate_pick()

            if st.button("⏩ Auto-Simulate to My Turn", use_container_width=True):
                if on_simulate_to_user_turn:
                    on_simulate_to_user_turn()

    st.markdown("---")
    st.markdown("### Recent Picks Log")

    if draft_log:
        recent_log = sorted(draft_log, key=lambda x: int(x.get("pick_no", 0)), reverse=True)[:10]
        log_data = [
            {
                "Pick #": p.get("pick_no"),
                "Round": p.get("round_no"),
                "Team": p.get("team_name") or teams_map.get(int(p.get("team_slot", 0)), f"Slot {p.get('team_slot')}"),
                "Player": p.get("player_name"),
                "Pos": p.get("position"),
                "By User": "YES" if p.get("picked_by_user") else "NO",
            }
            for p in recent_log
        ]
        st.dataframe(log_data, use_container_width=True)
    else:
        st.info("No picks logged yet. Start drafting above.")
