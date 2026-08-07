"""Streamlit Component: Pre-Draft Keeper Manager."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import streamlit as st


def calculate_keeper_pick_no(
    round_no: int,
    team_slot: int,
    num_teams: int = 12,
    is_3rr: bool = False,
) -> int:
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


def render_keeper_manager(
    available_players: List[Dict[str, Any]],
    draft_log: List[Dict[str, Any]],
    espn_teams: Optional[List[Dict[str, Any]]] = None,
    user_team_slot: int = 1,
    num_teams: int = 12,
    is_3rr: bool = False,
    on_record_keeper: Optional[
        Callable[[int, int, int, str, str, str, str, bool], None]
    ] = None,
    on_undo_keeper: Optional[Callable[[], None]] = None,
) -> None:
    """Render manual Pre-Draft Keeper setup form and active keeper roster."""
    st.caption("Pre-assign keepers to teams and rounds before the live draft starts.")

    if not available_players:
        st.warning("⚠️ No players available. Please sync ESPN league data first to populate players.")

    # Team options
    if espn_teams:
        team_options = {
            f"{t['team_name']} (Slot {t['team_slot']})": int(t["team_slot"])
            for t in espn_teams
            if "team_slot" in t and "team_name" in t
        }
        team_names_map = {
            int(t["team_slot"]): str(t["team_name"])
            for t in espn_teams
            if "team_slot" in t and "team_name" in t
        }
    else:
        team_options = {f"Team Slot {i}": i for i in range(1, num_teams + 1)}
        team_names_map = {i: f"Team {i}" for i in range(1, num_teams + 1)}

    # Available players map
    player_options = {}
    for p in available_players:
        pname = p.get("full_name") or p.get("player_name") or "Unknown"
        pos = p.get("position", "FA")
        team = p.get("team", "FA")
        label = f"{pname} ({pos} - {team})"
        player_options[label] = p

    with st.form(key="keeper_entry_form", clear_on_submit=False):
        selected_player_label = st.selectbox(
            "Select Keeper Player:",
            options=["-- Select Keeper --"] + sorted(list(player_options.keys())),
            key="keeper_player_selectbox",
        )

        selected_team_label = st.selectbox(
            "Assign to Team:",
            options=list(team_options.keys()),
            key="keeper_team_selectbox",
        )

        keeper_round = st.number_input(
            "Keeper Round:",
            min_value=1,
            max_value=25,
            value=1,
            step=1,
            key="keeper_round_number",
        )

        assigned_slot = team_options.get(selected_team_label, 1)
        calc_pick_no = calculate_keeper_pick_no(
            round_no=int(keeper_round),
            team_slot=assigned_slot,
            num_teams=num_teams,
            is_3rr=is_3rr,
        )

        team_display_name = team_names_map.get(assigned_slot, f"Team Slot {assigned_slot}")
        st.info(
            f"📍 Estimated Draft Pick: **#{calc_pick_no}** (Round {keeper_round}, {team_display_name})"
        )

        # Automatically infer if this is user's team keeper
        picked_by_user = (assigned_slot == user_team_slot)

        st.caption("👇 Click below to save & lock this keeper onto the draft board:")
        submitted = st.form_submit_button("🔒 Lock in Keeper", type="primary", use_container_width=True)

    if submitted:
        st.session_state.keeper_expander_open = True
        if selected_player_label and selected_player_label != "-- Select Keeper --":
            player = player_options[selected_player_label]
            player_name = player.get("full_name") or player.get("player_name") or "Unknown"
            player_id = str(player.get("player_id", ""))
            position = str(player.get("position", "FA"))

            if on_record_keeper:
                on_record_keeper(
                    calc_pick_no,
                    int(keeper_round),
                    assigned_slot,
                    player_id,
                    player_name,
                    position,
                    team_display_name,
                    picked_by_user,
                )
                st.success(
                    f"Locked in {player_name} for {team_display_name} (Round {keeper_round}, Pick #{calc_pick_no})"
                )
        else:
            st.warning("Please select a player to lock in as keeper.")

    # Display list of locked keepers
    keepers = [
        e
        for e in draft_log
        if e.get("source") == "keeper"
        or "keeper" in str(e.get("notes", "")).lower()
    ]

    if keepers:
        st.markdown("---")
        st.markdown("**Locked Pre-Draft Keepers:**")
        keeper_rows = [
            {
                "Pick #": k.get("pick_no"),
                "Round": k.get("round_no"),
                "Team": k.get("team_name")
                or team_names_map.get(int(k.get("team_slot", 0)), f"Slot {k.get('team_slot')}"),
                "Player": k.get("player_name"),
                "Pos": k.get("position"),
                "By User": "YES" if k.get("picked_by_user") else "NO",
            }
            for k in sorted(keepers, key=lambda x: int(x.get("pick_no", 0)))
        ]
        st.dataframe(keeper_rows, use_container_width=True)

        if st.button("⏪ Undo Last Keeper", use_container_width=True):
            st.session_state.keeper_expander_open = True
            if on_undo_keeper:
                on_undo_keeper()
